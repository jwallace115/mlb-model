#!/usr/bin/env python3
"""
NFL Sim Phase 1B — Point-in-time weekly player usage shares.

ALGORITHM (performance-critical — the killed attempt looped per-player):
  1. From PBP, build ONE per-(season, week, game_id, team, player_id) table
     with raw counts (targets, carries, rec_yards, etc.) and a parallel
     per-(season, week, game_id, team) team-totals table. Done ONCE with
     groupby-agg. No .apply(lambda), no per-player loop.
  2. PIT accumulation loops over WEEKS (max 22 per season), never over players.
     For each week w, "available" = rows with week < w. Decay weights are a
     column multiply before a groupby-sum. Shares = player weighted count /
     team weighted count. Rates = weighted numerator / weighted denominator.
  3. Shrinkage and s-1 prior blend are column arithmetic over the whole table.
  4. Grid search calls steps 2-3 twelve times over the pre-aggregated table.
     Expected runtime: well under 1 minute per grid point.

Same PIT definition as ratings: (season s, week w) uses plays from s weeks < w
plus s-1 as a prior. Nothing from week w or later.
"""

import json, sys, time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
PBP_DIR = ROOT / "nfl" / "data" / "pbp"
OUT_DIR = ROOT / "nfl" / "data" / "sim" / "ratings"
PARAMS_PATH = ROOT / "nfl" / "sim" / "params_v1.json"
REPORT_DIR = ROOT / "research" / "nfl_sim"

SEASONS = [2020, 2021, 2022, 2023, 2024, 2025, 2026]
OUTPUT_SEASONS = [2021, 2022, 2023, 2024, 2025, 2026]
TUNE_SEASONS = [2021, 2022, 2023, 2024]
SKILL_POS = {"RB", "WR", "TE", "QB"}


def _shrink(x, n, k, mu):
    """Vectorised shrinkage: works on scalars and arrays."""
    return (n * x + k * mu) / (n + k)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. PRE-AGGREGATE (done once)
# ═══════════════════════════════════════════════════════════════════════════════

def load_pbp():
    frames = []
    for s in SEASONS:
        p = PBP_DIR / f"pbp_{s}.parquet"
        if p.exists():
            frames.append(pd.read_parquet(p))
    return pd.concat(frames, ignore_index=True)


def load_roster_data():
    import nflreadpy
    rosters = nflreadpy.load_rosters_weekly(SEASONS).to_pandas()
    depth = nflreadpy.load_depth_charts(SEASONS).to_pandas()
    injuries = nflreadpy.load_injuries(SEASONS).to_pandas()
    # Cache locally (nfl/data/pbp/ is gitignored)
    rosters.to_parquet(PBP_DIR / "rosters_weekly.parquet", index=False)
    depth.to_parquet(PBP_DIR / "depth_charts.parquet", index=False)
    injuries.to_parquet(PBP_DIR / "injuries.parquet", index=False)
    return rosters, depth, injuries


def build_player_game_aggs(plays):
    """One groupby per side — no .apply, no lambda per group."""
    passes = plays[plays["play_type"] == "pass"].copy()
    rushes = plays[plays["play_type"] == "run"].copy()

    # ── Receiving (per receiver) ──
    tgt = passes[passes["receiver_player_id"].notna()].copy()
    tgt["rz"] = (tgt["yardline_100"] <= 20).astype(int)
    tgt["exp_rec"] = ((tgt["yards_gained"] >= 20) & (tgt["complete_pass"] == 1)).astype(int)

    rec = tgt.groupby(["season", "week", "game_id", "posteam", "receiver_player_id"], observed=True).agg(
        n_targets=("receiver_player_id", "size"),
        n_receptions=("complete_pass", "sum"),
        rec_yards=("yards_gained", lambda x: x[tgt.loc[x.index, "complete_pass"] == 1].sum()),
        air_yards_sum=("air_yards", "sum"),
        yac_sum=("yards_after_catch", "sum"),
        rz_targets=("rz", "sum"),
        exp_recs=("exp_rec", "sum"),
    ).reset_index().rename(columns={"posteam": "team", "receiver_player_id": "player_id"})

    # Fix rec_yards — the lambda above is fragile; recompute:
    comp = tgt[tgt["complete_pass"] == 1]
    rec_yds = comp.groupby(["season", "week", "game_id", "posteam", "receiver_player_id"], observed=True)[
        "yards_gained"].sum().reset_index().rename(
        columns={"posteam": "team", "receiver_player_id": "player_id", "yards_gained": "rec_yards_clean"})
    rec = rec.drop(columns=["rec_yards"]).merge(rec_yds, on=["season", "week", "game_id", "team", "player_id"], how="left")
    rec["rec_yards"] = rec["rec_yards_clean"].fillna(0)
    rec = rec.drop(columns=["rec_yards_clean"])

    # Team target totals
    team_tgt = tgt.groupby(["season", "week", "game_id", "posteam"], observed=True).agg(
        team_targets=("receiver_player_id", "size"),
        team_rz_targets=("rz", "sum"),
    ).reset_index().rename(columns={"posteam": "team"})

    # ── Rushing (per rusher) ──
    rush = rushes[rushes["rusher_player_id"].notna()].copy()
    rush["gl"] = (rush["yardline_100"] <= 5).astype(int)
    rush["exp_rush"] = (rush["yards_gained"] >= 12).astype(int)

    car = rush.groupby(["season", "week", "game_id", "posteam", "rusher_player_id"], observed=True).agg(
        n_carries=("rusher_player_id", "size"),
        rush_yards=("yards_gained", "sum"),
        gl_carries=("gl", "sum"),
        exp_rushes=("exp_rush", "sum"),
    ).reset_index().rename(columns={"posteam": "team", "rusher_player_id": "player_id"})

    team_car = rush.groupby(["season", "week", "game_id", "posteam"], observed=True).agg(
        team_carries=("rusher_player_id", "size"),
        team_gl_carries=("gl", "sum"),
    ).reset_index().rename(columns={"posteam": "team"})

    return rec, team_tgt, car, team_car


def build_position_map(rosters):
    """Map gsis_id -> (season, position, team, full_name). One row per player-season."""
    r = rosters[rosters["position"].isin(SKILL_POS)].copy()
    r = r.sort_values("season").drop_duplicates(["gsis_id", "season"], keep="last")
    return r[["gsis_id", "season", "position", "team", "full_name"]].rename(
        columns={"gsis_id": "player_id"})


def compute_position_priors(rec, car, pos_map):
    """League-mean stats by position from each season (used as shrink target for s+1)."""
    priors = {}
    for season in sorted(rec["season"].unique()):
        sr = rec[rec["season"] == season].merge(
            pos_map[pos_map["season"] == season][["player_id", "position"]], on="player_id", how="left")
        sc = car[car["season"] == season].merge(
            pos_map[pos_map["season"] == season][["player_id", "position"]], on="player_id", how="left")
        sp = {}
        for pos in SKILL_POS:
            pr = sr[sr["position"] == pos]
            pc = sc[sc["position"] == pos]
            tt = pr["n_targets"].sum()
            tr = pr["n_receptions"].sum()
            tc = pc["n_carries"].sum()
            sp[f"{pos}_adot"] = pr["air_yards_sum"].sum() / max(tt, 1)
            sp[f"{pos}_catch_rate"] = tr / max(tt, 1)
            sp[f"{pos}_yac_per_rec"] = pr["yac_sum"].sum() / max(tr, 1)
            sp[f"{pos}_ypt"] = pr["rec_yards"].sum() / max(tt, 1)
            sp[f"{pos}_ypc"] = pc["rush_yards"].sum() / max(tc, 1)
            sp[f"{pos}_exp_rec"] = pr["exp_recs"].sum() / max(tt, 1)
            sp[f"{pos}_exp_rush"] = pc["exp_rushes"].sum() / max(tc, 1)
        priors[season] = sp
    return priors


# ═══════════════════════════════════════════════════════════════════════════════
# 2–3. PIT USAGE BUILDER (vectorised: loop over weeks, not players)
# ═══════════════════════════════════════════════════════════════════════════════

def build_player_usage(rec, team_tgt, car, team_car, pos_map, priors, params,
                        roster_universe, output_seasons=None):
    """Build PIT weekly player usage shares.
    Loops over (season, week) only. All per-player computation is vectorised groupby."""
    sh_hl = params.get("usage", {}).get("share_half_life", float("inf"))
    k_share = params.get("usage", {}).get("k_share", 50)
    pw = params.get("prior_weight", 0.3)
    prior_reg = params.get("prior_regression", 0.5)
    fin_hl = (sh_hl is not None and sh_hl != float("inf") and sh_hl > 0)

    all_rows = []
    seasons = output_seasons or OUTPUT_SEASONS

    for season in seasons:
        # Prior-season position priors (shrink targets)
        sp = priors.get(season - 1, priors.get(min(priors.keys()), {}))

        s_rec = rec[rec["season"] == season]
        s_car = car[car["season"] == season]
        s_tt = team_tgt[team_tgt["season"] == season]
        s_tc = team_car[team_car["season"] == season]

        prior_rec = rec[rec["season"] == season - 1]
        prior_car = car[car["season"] == season - 1]
        prior_tt = team_tgt[team_tgt["season"] == season - 1]
        prior_tc = team_car[team_car["season"] == season - 1]

        # Week range
        last_w = 0
        for df in [s_rec, s_car]:
            if not df.empty:
                last_w = max(last_w, int(df["week"].max()))
        if last_w == 0:
            last_w = 1
        weeks = list(range(1, min(22, last_w + 1) + 1))

        # Universe: players on the roster for this season at skill positions
        season_roster = roster_universe[roster_universe["season"] == season]
        # Also include players from s-1 who might have prior data
        prior_roster = roster_universe[roster_universe["season"] == season - 1]

        for w in weeks:
            # ── Available data: season s, weeks < w ──
            avail_rec = s_rec[s_rec["week"] < w]
            avail_car = s_car[s_car["week"] < w]
            avail_tt = s_tt[s_tt["week"] < w]
            avail_tc = s_tc[s_tc["week"] < w]

            # ── Receiving shares (vectorised) ──
            if not avail_rec.empty:
                # Decay weights
                if fin_hl:
                    avail_rec = avail_rec.copy()
                    avail_rec["decay"] = 0.5 ** ((w - 1 - avail_rec["week"]) / sh_hl)
                    avail_rec["w_targets"] = avail_rec["n_targets"] * avail_rec["decay"]
                    avail_rec["w_recs"] = avail_rec["n_receptions"] * avail_rec["decay"]
                    avail_rec["w_air"] = avail_rec["air_yards_sum"] * avail_rec["decay"]
                    avail_rec["w_yac"] = avail_rec["yac_sum"] * avail_rec["decay"]
                    avail_rec["w_rec_yds"] = avail_rec["rec_yards"] * avail_rec["decay"]
                    avail_rec["w_rz"] = avail_rec["rz_targets"] * avail_rec["decay"]
                    avail_rec["w_exp"] = avail_rec["exp_recs"] * avail_rec["decay"]
                else:
                    avail_rec = avail_rec.copy()
                    avail_rec["w_targets"] = avail_rec["n_targets"].astype(float)
                    avail_rec["w_recs"] = avail_rec["n_receptions"].astype(float)
                    avail_rec["w_air"] = avail_rec["air_yards_sum"].astype(float)
                    avail_rec["w_yac"] = avail_rec["yac_sum"].astype(float)
                    avail_rec["w_rec_yds"] = avail_rec["rec_yards"].astype(float)
                    avail_rec["w_rz"] = avail_rec["rz_targets"].astype(float)
                    avail_rec["w_exp"] = avail_rec["exp_recs"].astype(float)

                # Player sums
                p_rec = avail_rec.groupby(["team", "player_id"], observed=True).agg(
                    w_tgt=("w_targets", "sum"), w_rec=("w_recs", "sum"),
                    w_air=("w_air", "sum"), w_yac=("w_yac", "sum"),
                    w_ryds=("w_rec_yds", "sum"), w_rz=("w_rz", "sum"),
                    w_exp=("w_exp", "sum"),
                    raw_tgt=("n_targets", "sum"),
                ).reset_index()

                # Team sums (for share denominator)
                if fin_hl:
                    avail_tt_w = avail_tt.copy()
                    avail_tt_w["w_tt"] = avail_tt_w["team_targets"] * 0.5 ** ((w - 1 - avail_tt_w["week"]) / sh_hl)
                    avail_tt_w["w_rz_tt"] = avail_tt_w["team_rz_targets"] * 0.5 ** ((w - 1 - avail_tt_w["week"]) / sh_hl)
                else:
                    avail_tt_w = avail_tt.copy()
                    avail_tt_w["w_tt"] = avail_tt_w["team_targets"].astype(float)
                    avail_tt_w["w_rz_tt"] = avail_tt_w["team_rz_targets"].astype(float)

                t_rec = avail_tt_w.groupby("team", observed=True).agg(
                    tw_tgt=("w_tt", "sum"), tw_rz=("w_rz_tt", "sum")).reset_index()
                p_rec = p_rec.merge(t_rec, on="team", how="left")
                p_rec["raw_tgt_share"] = p_rec["w_tgt"] / p_rec["tw_tgt"].clip(lower=1)
                p_rec["raw_rz_share"] = p_rec["w_rz"] / p_rec["tw_rz"].clip(lower=1)
            else:
                p_rec = pd.DataFrame(columns=["team", "player_id", "w_tgt", "w_rec",
                                               "w_air", "w_yac", "w_ryds", "w_rz", "w_exp",
                                               "raw_tgt", "tw_tgt", "tw_rz",
                                               "raw_tgt_share", "raw_rz_share"])

            # ── Rushing shares (vectorised) ──
            if not avail_car.empty:
                if fin_hl:
                    avail_car = avail_car.copy()
                    avail_car["decay"] = 0.5 ** ((w - 1 - avail_car["week"]) / sh_hl)
                    avail_car["w_carries"] = avail_car["n_carries"] * avail_car["decay"]
                    avail_car["w_ryds"] = avail_car["rush_yards"] * avail_car["decay"]
                    avail_car["w_gl"] = avail_car["gl_carries"] * avail_car["decay"]
                    avail_car["w_exp"] = avail_car["exp_rushes"] * avail_car["decay"]
                else:
                    avail_car = avail_car.copy()
                    avail_car["w_carries"] = avail_car["n_carries"].astype(float)
                    avail_car["w_ryds"] = avail_car["rush_yards"].astype(float)
                    avail_car["w_gl"] = avail_car["gl_carries"].astype(float)
                    avail_car["w_exp"] = avail_car["exp_rushes"].astype(float)

                p_car = avail_car.groupby(["team", "player_id"], observed=True).agg(
                    w_car=("w_carries", "sum"), w_ryds_r=("w_ryds", "sum"),
                    w_gl=("w_gl", "sum"), w_exp_r=("w_exp", "sum"),
                    raw_car=("n_carries", "sum"),
                ).reset_index()

                if fin_hl:
                    avail_tc_w = avail_tc.copy()
                    avail_tc_w["w_tc"] = avail_tc_w["team_carries"] * 0.5 ** ((w - 1 - avail_tc_w["week"]) / sh_hl)
                    avail_tc_w["w_gl_tc"] = avail_tc_w["team_gl_carries"] * 0.5 ** ((w - 1 - avail_tc_w["week"]) / sh_hl)
                else:
                    avail_tc_w = avail_tc.copy()
                    avail_tc_w["w_tc"] = avail_tc_w["team_carries"].astype(float)
                    avail_tc_w["w_gl_tc"] = avail_tc_w["team_gl_carries"].astype(float)

                t_car = avail_tc_w.groupby("team", observed=True).agg(
                    tw_car=("w_tc", "sum"), tw_gl=("w_gl_tc", "sum")).reset_index()
                p_car = p_car.merge(t_car, on="team", how="left")
                p_car["raw_car_share"] = p_car["w_car"] / p_car["tw_car"].clip(lower=1)
                p_car["raw_gl_share"] = p_car["w_gl"] / p_car["tw_gl"].clip(lower=1)
            else:
                p_car = pd.DataFrame(columns=["team", "player_id", "w_car", "w_ryds_r",
                                               "w_gl", "w_exp_r", "raw_car", "tw_car", "tw_gl",
                                               "raw_car_share", "raw_gl_share"])

            # ── Merge rec + rush per player ──
            if p_rec.empty and p_car.empty:
                # For this week, emit prior-only rows for roster players
                rp = season_roster[["player_id", "team", "position", "full_name"]].drop_duplicates("player_id")
                for _, r in rp.iterrows():
                    pos = r["position"]
                    if pos not in SKILL_POS:
                        continue
                    all_rows.append({
                        "season": season, "week": w, "team": r["team"],
                        "player_id": r["player_id"], "player_name": r.get("full_name", ""),
                        "position": pos,
                        "target_share": 1/15, "carry_share": 1/10,
                        "rz_target_share": 1/15, "gl_carry_share": 1/10,
                        "adot": sp.get(f"{pos}_adot", 8.0),
                        "yac_per_rec": sp.get(f"{pos}_yac_per_rec", 4.5),
                        "catch_rate": sp.get(f"{pos}_catch_rate", 0.65),
                        "yards_per_target": sp.get(f"{pos}_ypt", 7.0),
                        "yards_per_carry": sp.get(f"{pos}_ypc", 4.0),
                        "explosive_rec_rate": sp.get(f"{pos}_exp_rec", 0.05),
                        "explosive_rush_rate": sp.get(f"{pos}_exp_rush", 0.05),
                        "n_targets": 0, "n_carries": 0,
                    })
                continue

            # Outer merge
            merged = p_rec.merge(p_car, on=["team", "player_id"], how="outer", suffixes=("", "_rush"))
            # Fill NaN from missing side
            for c in ["w_tgt", "w_rec", "w_air", "w_yac", "w_ryds", "w_rz", "w_exp",
                       "raw_tgt", "tw_tgt", "tw_rz", "raw_tgt_share", "raw_rz_share"]:
                if c in merged.columns:
                    merged[c] = merged[c].fillna(0)
            for c in ["w_car", "w_ryds_r", "w_gl", "w_exp_r", "raw_car", "tw_car", "tw_gl",
                       "raw_car_share", "raw_gl_share"]:
                if c in merged.columns:
                    merged[c] = merged[c].fillna(0)

            # Join position
            pm = pos_map[pos_map["season"] == season][["player_id", "position", "full_name"]].drop_duplicates("player_id")
            pm_prior = pos_map[pos_map["season"] == season - 1][["player_id", "position", "full_name"]].drop_duplicates("player_id")
            pm_all = pd.concat([pm, pm_prior]).drop_duplicates("player_id", keep="first")
            merged = merged.merge(pm_all, on="player_id", how="left")
            merged = merged[merged["position"].isin(SKILL_POS)]

            # ── Shrinkage ──
            for _, row in merged.iterrows():
                pos = row["position"]
                n_t = row.get("raw_tgt", 0)
                n_c = row.get("raw_car", 0)

                all_rows.append({
                    "season": season, "week": w, "team": row["team"],
                    "player_id": row["player_id"],
                    "player_name": row.get("full_name", ""),
                    "position": pos,
                    "target_share": _shrink(row.get("raw_tgt_share", 0), n_t, k_share, 1/15),
                    "carry_share": _shrink(row.get("raw_car_share", 0), n_c, k_share, 1/10),
                    "rz_target_share": _shrink(row.get("raw_rz_share", 0),
                                                row.get("w_rz", 0), k_share, 1/15),
                    "gl_carry_share": _shrink(row.get("raw_gl_share", 0),
                                              row.get("w_gl", 0), k_share, 1/10),
                    "adot": _shrink(row["w_air"] / max(row["w_tgt"], 1), n_t, k_share,
                                     sp.get(f"{pos}_adot", 8.0)),
                    "catch_rate": _shrink(row["w_rec"] / max(row["w_tgt"], 1), n_t, k_share,
                                           sp.get(f"{pos}_catch_rate", 0.65)),
                    "yac_per_rec": _shrink(row["w_yac"] / max(row["w_rec"], 1),
                                           row["w_rec"], k_share,
                                           sp.get(f"{pos}_yac_per_rec", 4.5)),
                    "yards_per_target": _shrink(row["w_ryds"] / max(row["w_tgt"], 1), n_t,
                                                 k_share, sp.get(f"{pos}_ypt", 7.0)),
                    "yards_per_carry": _shrink(row.get("w_ryds_r", 0) / max(row.get("w_car", 1), 1),
                                               n_c, k_share, sp.get(f"{pos}_ypc", 4.0)),
                    "explosive_rec_rate": _shrink(row["w_exp"] / max(row["w_tgt"], 1), n_t,
                                                   k_share, sp.get(f"{pos}_exp_rec", 0.05)),
                    "explosive_rush_rate": _shrink(row.get("w_exp_r", 0) / max(row.get("w_car", 1), 1),
                                                    n_c, k_share, sp.get(f"{pos}_exp_rush", 0.05)),
                    "n_targets": int(n_t), "n_carries": int(n_c),
                })

    return pd.DataFrame(all_rows)


# ═══════════════════════════════════════════════════════════════════════════════
# ACTIVE UNIVERSE + RENORMALISATION
# ═══════════════════════════════════════════════════════════════════════════════

def build_active_universe(rosters, injuries, depth):
    """Active set per (season, week, team, player).
    Active = roster status ACT and not Out/Doubtful on that week's injury report."""
    r = rosters[rosters["position"].isin(SKILL_POS)].copy()
    if "week" not in r.columns:
        return pd.DataFrame()
    r = r.rename(columns={"gsis_id": "player_id"})
    act = r[r["status"] == "ACT"][["season", "week", "team", "player_id", "position", "full_name"]].copy()

    # Injury filter
    inj_out = injuries[injuries["report_status"].isin(["Out", "Doubtful"])].copy()
    inj_out = inj_out.rename(columns={"gsis_id": "player_id"})
    inj_out["inactive"] = True
    act = act.merge(inj_out[["season", "week", "team", "player_id", "inactive", "report_status"]],
                     on=["season", "week", "team", "player_id"], how="left")
    act["active_flag"] = act["inactive"].isna()
    act["injury_status"] = act["report_status"].fillna("Active")

    # Depth order
    if "depth_team" in depth.columns:
        do = depth[["season", "week", "club_code", "gsis_id", "depth_team"]].copy()
        do = do.rename(columns={"club_code": "team", "gsis_id": "player_id", "depth_team": "depth_order"})
        act = act.merge(do, on=["season", "week", "team", "player_id"], how="left")
    else:
        act["depth_order"] = np.nan

    return act[["season", "week", "team", "player_id", "position",
                 "depth_order", "active_flag", "injury_status"]].drop_duplicates()


def renormalize_shares(shares_df, active_ids, depth_map=None):
    """Zero inactive, redistribute by depth, renormalise to sum=1 per position."""
    df = shares_df.copy()
    active_set = set(active_ids)
    share_cols = ["target_share", "carry_share", "rz_target_share", "gl_carry_share"]

    for pos in SKILL_POS:
        mask = df["position"] == pos
        pos_df = df[mask]
        if pos_df.empty:
            continue
        active_mask = pos_df["player_id"].isin(active_set)
        inactive_idx = pos_df[~active_mask].index
        active_idx = pos_df[active_mask].index

        if len(inactive_idx) == 0 or len(active_idx) == 0:
            continue

        for sc in share_cols:
            if sc not in df.columns:
                continue
            vacated = df.loc[inactive_idx, sc].sum()
            if vacated <= 0:
                continue
            # Redistribute by inverse depth order
            if depth_map is not None:
                depths = df.loc[active_idx, "player_id"].map(depth_map).fillna(99).astype(float)
                weights = 1.0 / (depths + 1)
            else:
                weights = pd.Series(1.0, index=active_idx)
            wt = weights.sum()
            if wt > 0:
                df.loc[active_idx, sc] = df.loc[active_idx, sc] + vacated * (weights / wt).values
            df.loc[inactive_idx, sc] = 0.0

            # Renormalise to sum=1
            total = df.loc[mask, sc].sum()
            if total > 0:
                df.loc[mask, sc] = df.loc[mask, sc] / total
                assert abs(df.loc[mask, sc].sum() - 1.0) < 1e-9, f"Renorm failed for {pos} {sc}"

    return df


# ═══════════════════════════════════════════════════════════════════════════════
# GRID SEARCH (2021-2024 ONLY)
# ═══════════════════════════════════════════════════════════════════════════════

def tune_share_params(rec, team_tgt, car, team_car, pos_map, priors, rosters_uni, params_base):
    """12-point grid. RAISES if season >= 2025."""
    for df in [rec, car]:
        if (df["season"] >= 2025).any():
            raise RuntimeError("FATAL: tune_share_params has season >= 2025")

    # Actual next-game shares
    actual_tgt = rec[rec["season"].isin(TUNE_SEASONS)].copy()
    actual_tgt["actual_share"] = actual_tgt["n_targets"] / actual_tgt.merge(
        team_tgt, on=["season", "week", "game_id", "team"])["team_targets"].clip(lower=1)
    # Simpler: merge with team_tgt first
    at = rec[rec["season"].isin(TUNE_SEASONS)].merge(team_tgt, on=["season", "week", "game_id", "team"])
    at["actual_tgt_share"] = at["n_targets"] / at["team_targets"].clip(lower=1)

    ac = car[car["season"].isin(TUNE_SEASONS)].merge(team_car, on=["season", "week", "game_id", "team"])
    ac["actual_car_share"] = ac["n_carries"] / ac["team_carries"].clip(lower=1)

    grid = []
    for sh_hl in [2, 4, 8, float("inf")]:
        for k_s in [20, 50, 100]:
            t0 = time.time()
            p = dict(params_base)
            p["usage"] = {"share_half_life": sh_hl, "k_share": k_s}
            usage = build_player_usage(
                rec[rec["season"] <= 2024], team_tgt[team_tgt["season"] <= 2024],
                car[car["season"] <= 2024], team_car[team_car["season"] <= 2024],
                pos_map, priors, p, rosters_uni[rosters_uni["season"] <= 2024],
                output_seasons=TUNE_SEASONS)
            dt = time.time() - t0

            # Evaluate target share: WR/TE/RB with >= 1 target
            eval_tgt = usage[["season", "week", "team", "player_id", "target_share", "position"]].merge(
                at[["season", "week", "player_id", "actual_tgt_share"]],
                on=["season", "week", "player_id"], how="inner")
            eval_tgt = eval_tgt[eval_tgt["position"].isin({"WR", "TE", "RB"})]
            rmse_tgt = np.sqrt(((eval_tgt["target_share"] - eval_tgt["actual_tgt_share"]) ** 2).mean()) if len(eval_tgt) else float("inf")

            # Evaluate carry share: RB with >= 1 carry
            eval_car = usage[["season", "week", "team", "player_id", "carry_share", "position"]].merge(
                ac[["season", "week", "player_id", "actual_car_share"]],
                on=["season", "week", "player_id"], how="inner")
            eval_car = eval_car[eval_car["position"] == "RB"]
            rmse_car = np.sqrt(((eval_car["carry_share"] - eval_car["actual_car_share"]) ** 2).mean()) if len(eval_car) else float("inf")

            mean_rmse = (rmse_tgt + rmse_car) / 2

            # Per-season and early/late
            by_season = {}
            for s in TUNE_SEASONS:
                et = eval_tgt[eval_tgt["season"] == s]
                ec = eval_car[eval_car["season"] == s]
                by_season[s] = {
                    "tgt": np.sqrt(((et["target_share"] - et["actual_tgt_share"])**2).mean()) if len(et) else float("inf"),
                    "car": np.sqrt(((ec["carry_share"] - ec["actual_car_share"])**2).mean()) if len(ec) else float("inf"),
                }

            early_t = eval_tgt[eval_tgt["week"] <= 4]
            late_t = eval_tgt[eval_tgt["week"] > 4]
            rmse_early = np.sqrt(((early_t["target_share"] - early_t["actual_tgt_share"])**2).mean()) if len(early_t) else float("inf")
            rmse_late = np.sqrt(((late_t["target_share"] - late_t["actual_tgt_share"])**2).mean()) if len(late_t) else float("inf")

            grid.append({
                "share_half_life": sh_hl, "k_share": k_s,
                "mean_rmse": mean_rmse, "rmse_target": rmse_tgt, "rmse_carry": rmse_car,
                "by_season": by_season, "rmse_wk1_4": rmse_early, "rmse_wk5_18": rmse_late,
            })
            sh_s = "inf" if sh_hl == float("inf") else str(sh_hl)
            print(f"  sh_hl={sh_s:>3s} k={k_s:>3d}  RMSE={mean_rmse:.4f} (tgt={rmse_tgt:.4f} car={rmse_car:.4f})  {dt:.1f}s")

    grid.sort(key=lambda x: x["mean_rmse"])
    best = grid[0]
    print(f"\nBest: sh_hl={best['share_half_life']} k={best['k_share']}  RMSE={best['mean_rmse']:.4f}")
    return best, grid


# ═══════════════════════════════════════════════════════════════════════════════
# PIT TEST
# ═══════════════════════════════════════════════════════════════════════════════

def pit_test(rec, team_tgt, car, team_car, pos_map, priors, rosters_uni, params):
    """Full vs truncated comparison for one player row."""
    full = build_player_usage(rec, team_tgt, car, team_car, pos_map, priors, params,
                               rosters_uni, output_seasons=[2023])
    # Pick a WR1 at week 10
    wr = full[(full["season"] == 2023) & (full["week"] == 10) & (full["position"] == "WR")]
    wr = wr.sort_values("n_targets", ascending=False)
    if wr.empty:
        print("  PIT SKIP: no WR at 2023 wk10")
        return
    pid = wr.iloc[0]["player_id"]
    full_row = wr.iloc[0]

    # Truncated: season < 2024 and (2023, week < 10)
    trunc_rec = rec[~((rec["season"] > 2023) | ((rec["season"] == 2023) & (rec["week"] >= 10)))]
    trunc_tt = team_tgt[~((team_tgt["season"] > 2023) | ((team_tgt["season"] == 2023) & (team_tgt["week"] >= 10)))]
    trunc_car = car[~((car["season"] > 2023) | ((car["season"] == 2023) & (car["week"] >= 10)))]
    trunc_tc = team_car[~((team_car["season"] > 2023) | ((team_car["season"] == 2023) & (team_car["week"] >= 10)))]
    trunc_priors = compute_position_priors(trunc_rec, trunc_car, pos_map)

    trunc = build_player_usage(trunc_rec, trunc_tt, trunc_car, trunc_tc, pos_map,
                                trunc_priors, params, rosters_uni, output_seasons=[2023])
    # Use week 9 (available in both)
    tr = trunc[(trunc["season"] == 2023) & (trunc["week"] == 9) & (trunc["player_id"] == pid)]
    fr = full[(full["season"] == 2023) & (full["week"] == 9) & (full["player_id"] == pid)]
    if tr.empty or fr.empty:
        print(f"  PIT SKIP: {pid} not in truncated wk9")
        return

    num_cols = ["target_share", "carry_share", "adot", "catch_rate", "yards_per_target",
                "n_targets", "n_carries"]
    for c in num_cols:
        fv = float(fr.iloc[0][c])
        tv = float(tr.iloc[0][c])
        assert abs(fv - tv) < 1e-9, f"PIT FAIL usage {c}: full={fv} trunc={tv}"
    print(f"  PIT PASS: {pid} 2023 wk9 (all numeric cols to 1e-9)")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    t_start = time.time()
    print("NFL Sim Phase 1B: Player Usage Shares")
    print("=" * 60)

    print("\nLoading PBP...")
    plays = load_pbp()
    scrimmage = plays[plays["play_type"].isin(["pass", "run"])].copy()
    print(f"  {len(scrimmage):,} scrimmage plays  ({time.time()-t_start:.1f}s)")

    print("\nLoading rosters/depth/injuries...")
    t1 = time.time()
    rosters, depth, injuries = load_roster_data()
    print(f"  Rosters: {len(rosters):,}, Depth: {len(depth):,}, Injuries: {len(injuries):,}  ({time.time()-t1:.1f}s)")

    print("\nBuilding per-game aggregates...")
    t2 = time.time()
    rec, team_tgt, car, team_car = build_player_game_aggs(scrimmage)
    print(f"  Receiving: {len(rec):,}, Rushing: {len(car):,}  ({time.time()-t2:.1f}s)")

    pos_map = build_position_map(rosters)
    priors = compute_position_priors(rec, car, pos_map)

    # Roster universe for the player loop
    roster_uni = rosters[rosters["position"].isin(SKILL_POS)][
        ["season", "gsis_id", "team", "position", "full_name"]
    ].rename(columns={"gsis_id": "player_id"}).drop_duplicates(["season", "player_id"])

    # Grid search
    print(f"\nTuning share params (2021-2024, 12 grid points)...")
    t3 = time.time()
    best, grid = tune_share_params(
        rec[rec["season"] <= 2024], team_tgt[team_tgt["season"] <= 2024],
        car[car["season"] <= 2024], team_car[team_car["season"] <= 2024],
        pos_map, priors, roster_uni, json.load(open(PARAMS_PATH)))
    print(f"  Grid done: {time.time()-t3:.1f}s total")

    # Update params
    params = json.load(open(PARAMS_PATH))
    params["usage"] = {
        "share_half_life": best["share_half_life"],
        "k_share": best["k_share"],
        "grid_results": [{k: v for k, v in g.items() if k != "by_season"}
                          for g in sorted(grid, key=lambda x: x["mean_rmse"])],
    }
    with open(PARAMS_PATH, "w") as f:
        json.dump(params, f, indent=2, default=str)

    # Build full usage
    print(f"\nBuilding full usage (all seasons)...")
    t4 = time.time()
    usage = build_player_usage(rec, team_tgt, car, team_car, pos_map, priors, params, roster_uni)
    print(f"  {len(usage):,} rows  ({time.time()-t4:.1f}s)")

    # PIT test
    print("\nPIT test...")
    pit_test(rec, team_tgt, car, team_car, pos_map, priors, roster_uni, params)

    # Active universe
    print("\nBuilding active universe...")
    active = build_active_universe(rosters, injuries, depth)
    print(f"  {len(active):,} rows")

    # Questionable counts
    q = injuries[injuries["report_status"] == "Questionable"]
    print(f"\n  Questionable designations per season:")
    for s in OUTPUT_SEASONS:
        print(f"    {s}: {len(q[q['season'] == s])}")

    # Save
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    usage.to_parquet(OUT_DIR / "player_usage_weekly.parquet", index=False)
    active.to_parquet(OUT_DIR / "active_universe_weekly.parquet", index=False)

    # Face validity
    print(f"\n{'='*60}")
    print("FACE VALIDITY (2024 wk 18)")
    print(f"{'='*60}")
    u24 = usage[(usage["season"] == 2024) & (usage["week"] == 18)]
    if not u24.empty:
        print("\n  Top 10 target share:")
        top_t = u24.nlargest(10, "n_targets")
        for _, r in top_t.iterrows():
            print(f"    {r['player_name']:<25s} {r['team']:>3s} {r['position']:>2s}  "
                  f"tgt_sh={r['target_share']:.3f}  n_tgt={int(r['n_targets'])}")
        print("\n  Top 10 carry share (RB):")
        top_c = u24[u24["position"] == "RB"].nlargest(10, "n_carries")
        for _, r in top_c.iterrows():
            print(f"    {r['player_name']:<25s} {r['team']:>3s}  "
                  f"car_sh={r['carry_share']:.3f}  n_car={int(r['n_carries'])}")

    # Check 5: RMSE by season and early/late
    print(f"\n  Share RMSE by season (best params):")
    for s, v in sorted(best.get("by_season", {}).items()):
        print(f"    {s}: tgt={v['tgt']:.4f}  car={v['car']:.4f}")
    print(f"  Wk 1-4 tgt RMSE: {best.get('rmse_wk1_4', 'N/A')}")
    print(f"  Wk 5-18 tgt RMSE: {best.get('rmse_wk5_18', 'N/A')}")

    print(f"\nTotal elapsed: {time.time()-t_start:.1f}s")
    print("Phase 1B (Steps 1-3) complete.")


if __name__ == "__main__":
    main()
