#!/usr/bin/env python3
"""
NFL Sim Phase 1B — Point-in-time weekly player usage shares.

ALGORITHM (vectorised — no per-player loops):
  1. From PBP, build per-(season, week, game_id, team, player_id) aggregate
     and per-(season, week, game_id, team) team-totals. One groupby-agg each.
  2. PIT accumulation loops over WEEKS (max 22), not players. Decay weights
     are column multiply before groupby-sum. Shares = player / team.
  3. Shrinkage, prior blend, and RENORMALISATION (FIX 1) are column arithmetic.
     After shrinkage, shares are renormalised to sum=1 per (team, share_type).
  4. Grid search calls steps 2-3 twelve times. ~2-3s per grid point.

Universe: every RB/WR/TE/QB on the weekly roster for that (season, week, team)
gets a row (prior-only if no plays yet). 32-team universe from s-1 (FIX 3).

Active universe (FIX 2): all rostered skill-position players, marked inactive
if roster status != ACT or injury report_status in (Out, Doubtful).
"""

import json, sys, time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
PBP_DIR = ROOT / "nfl" / "data" / "pbp"
OUT_DIR = ROOT / "nfl" / "data" / "sim" / "ratings"
PARAMS_PATH = ROOT / "nfl" / "sim" / "params_v1.json"

SEASONS = [2020, 2021, 2022, 2023, 2024, 2025, 2026]
OUTPUT_SEASONS = [2021, 2022, 2023, 2024, 2025, 2026]
TUNE_SEASONS = [2021, 2022, 2023, 2024]
SKILL_POS = {"RB", "WR", "TE", "QB"}


def _shrink(x, n, k, mu):
    return (n * x + k * mu) / (n + k)


# ═══════════════════════════════════════════════════════════════════════════════
# DATA LOADING
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
    PBP_DIR.mkdir(parents=True, exist_ok=True)
    rosters.to_parquet(PBP_DIR / "rosters_weekly.parquet", index=False)
    depth.to_parquet(PBP_DIR / "depth_charts.parquet", index=False)
    injuries.to_parquet(PBP_DIR / "injuries.parquet", index=False)
    return rosters, depth, injuries


# ═══════════════════════════════════════════════════════════════════════════════
# PRE-AGGREGATE
# ═══════════════════════════════════════════════════════════════════════════════

def build_player_game_aggs(plays):
    passes = plays[plays["play_type"] == "pass"].copy()
    rushes = plays[plays["play_type"] == "run"].copy()

    tgt = passes[passes["receiver_player_id"].notna()].copy()
    tgt["rz"] = (tgt["yardline_100"] <= 20).astype(int)
    tgt["exp_rec"] = ((tgt["yards_gained"] >= 20) & (tgt["complete_pass"] == 1)).astype(int)

    rec = tgt.groupby(["season", "week", "game_id", "posteam", "receiver_player_id"], observed=True).agg(
        n_targets=("receiver_player_id", "size"),
        n_receptions=("complete_pass", "sum"),
        air_yards_sum=("air_yards", "sum"),
        yac_sum=("yards_after_catch", "sum"),
        rz_targets=("rz", "sum"),
        exp_recs=("exp_rec", "sum"),
    ).reset_index().rename(columns={"posteam": "team", "receiver_player_id": "player_id"})

    comp = tgt[tgt["complete_pass"] == 1]
    rec_yds = comp.groupby(["season", "week", "game_id", "posteam", "receiver_player_id"], observed=True)[
        "yards_gained"].sum().reset_index().rename(
        columns={"posteam": "team", "receiver_player_id": "player_id", "yards_gained": "rec_yards"})
    rec = rec.merge(rec_yds, on=["season", "week", "game_id", "team", "player_id"], how="left")
    rec["rec_yards"] = rec["rec_yards"].fillna(0)

    team_tgt = tgt.groupby(["season", "week", "game_id", "posteam"], observed=True).agg(
        team_targets=("receiver_player_id", "size"),
        team_rz_targets=("rz", "sum"),
    ).reset_index().rename(columns={"posteam": "team"})

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
    r = rosters[rosters["position"].isin(SKILL_POS)].copy()
    r = r.sort_values("season").drop_duplicates(["gsis_id", "season"], keep="last")
    return r[["gsis_id", "season", "position", "team", "full_name"]].rename(
        columns={"gsis_id": "player_id"})


def compute_position_priors(rec, car, pos_map):
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
            tt, tr, tc = pr["n_targets"].sum(), pr["n_receptions"].sum(), pc["n_carries"].sum()
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
# PIT USAGE BUILDER (vectorised)
# ═══════════════════════════════════════════════════════════════════════════════

def build_player_usage(rec, team_tgt, car, team_car, pos_map, priors, params,
                        roster_universe, output_seasons=None):
    sh_hl = params.get("usage", {}).get("share_half_life", float("inf"))
    k_share = params.get("usage", {}).get("k_share", 50)
    fin_hl = sh_hl is not None and sh_hl != float("inf") and sh_hl > 0

    all_rows = []
    seasons = output_seasons or OUTPUT_SEASONS

    for season in seasons:
        sp = priors.get(season - 1, priors.get(min(priors.keys()), {}))
        s_rec = rec[rec["season"] == season]
        s_car = car[car["season"] == season]
        s_tt = team_tgt[team_tgt["season"] == season]
        s_tc = team_car[team_car["season"] == season]

        # Week range (32-team universe: FIX 3)
        last_w = 0
        for df in [s_rec, s_car]:
            if not df.empty:
                last_w = max(last_w, int(df["week"].max()))
        if last_w == 0:
            last_w = 1
        weeks = list(range(1, min(22, last_w + 1) + 1))

        # Roster universe for this season (FIX 3)
        s_roster = roster_universe[roster_universe["season"] == season]
        # Also include players from s-1 who are on a roster
        p_roster = roster_universe[roster_universe["season"] == season - 1]

        for w in weeks:
            avail_rec = s_rec[s_rec["week"] < w]
            avail_car = s_car[s_car["week"] < w]
            avail_tt = s_tt[s_tt["week"] < w]
            avail_tc = s_tc[s_tc["week"] < w]

            # ── Vectorised receiving stats ──
            if not avail_rec.empty:
                ar = avail_rec.copy()
                if fin_hl:
                    d = 0.5 ** ((w - 1 - ar["week"]) / sh_hl)
                else:
                    d = 1.0
                ar["wt"] = ar["n_targets"] * d
                ar["wr"] = ar["n_receptions"] * d
                ar["wa"] = ar["air_yards_sum"] * d
                ar["wy"] = ar["yac_sum"] * d
                ar["wry"] = ar["rec_yards"] * d
                ar["wrz"] = ar["rz_targets"] * d
                ar["we"] = ar["exp_recs"] * d

                p_r = ar.groupby(["team", "player_id"], observed=True).agg(
                    wt=("wt", "sum"), wr=("wr", "sum"), wa=("wa", "sum"),
                    wy=("wy", "sum"), wry=("wry", "sum"), wrz=("wrz", "sum"),
                    we=("we", "sum"), raw_tgt=("n_targets", "sum"),
                ).reset_index()

                at = avail_tt.copy()
                if fin_hl:
                    at["wtt"] = at["team_targets"] * 0.5 ** ((w - 1 - at["week"]) / sh_hl)
                    at["wrzt"] = at["team_rz_targets"] * 0.5 ** ((w - 1 - at["week"]) / sh_hl)
                else:
                    at["wtt"] = at["team_targets"].astype(float)
                    at["wrzt"] = at["team_rz_targets"].astype(float)
                t_r = at.groupby("team", observed=True).agg(
                    twt=("wtt", "sum"), twrz=("wrzt", "sum")).reset_index()
                p_r = p_r.merge(t_r, on="team", how="left")
            else:
                p_r = pd.DataFrame()

            # ── Vectorised rushing stats ──
            if not avail_car.empty:
                ac = avail_car.copy()
                if fin_hl:
                    d = 0.5 ** ((w - 1 - ac["week"]) / sh_hl)
                else:
                    d = 1.0
                ac["wc"] = ac["n_carries"] * d
                ac["wry_r"] = ac["rush_yards"] * d
                ac["wgl"] = ac["gl_carries"] * d
                ac["wer"] = ac["exp_rushes"] * d

                p_c = ac.groupby(["team", "player_id"], observed=True).agg(
                    wc=("wc", "sum"), wry_r=("wry_r", "sum"),
                    wgl=("wgl", "sum"), wer=("wer", "sum"),
                    raw_car=("n_carries", "sum"),
                ).reset_index()

                atc = avail_tc.copy()
                if fin_hl:
                    atc["wtc"] = atc["team_carries"] * 0.5 ** ((w - 1 - atc["week"]) / sh_hl)
                    atc["wglc"] = atc["team_gl_carries"] * 0.5 ** ((w - 1 - atc["week"]) / sh_hl)
                else:
                    atc["wtc"] = atc["team_carries"].astype(float)
                    atc["wglc"] = atc["team_gl_carries"].astype(float)
                t_c = atc.groupby("team", observed=True).agg(
                    twc=("wtc", "sum"), twgl=("wglc", "sum")).reset_index()
                p_c = p_c.merge(t_c, on="team", how="left")
            else:
                p_c = pd.DataFrame()

            # ── Merge play-based data ──
            if not p_r.empty and not p_c.empty:
                merged = p_r.merge(p_c, on=["team", "player_id"], how="outer")
            elif not p_r.empty:
                merged = p_r.copy()
            elif not p_c.empty:
                merged = p_c.copy()
            else:
                merged = pd.DataFrame()

            # Fill NaN
            for c in merged.columns:
                if c not in ["team", "player_id"]:
                    merged[c] = merged[c].fillna(0)

            # Join position + name
            pm = pos_map[pos_map["season"] == season][["player_id", "position", "full_name"]].drop_duplicates("player_id")
            pm2 = pos_map[pos_map["season"] == season - 1][["player_id", "position", "full_name"]].drop_duplicates("player_id")
            pm_all = pd.concat([pm, pm2]).drop_duplicates("player_id", keep="first")

            if not merged.empty:
                merged = merged.merge(pm_all, on="player_id", how="left")
            else:
                merged = pd.DataFrame(columns=["team", "player_id", "position", "full_name"])

            # ── Add roster players with no plays yet (FIX 3: prior-only) ──
            week_roster = s_roster[s_roster["week"] == w] if "week" in s_roster.columns else s_roster
            if week_roster.empty:
                week_roster = s_roster  # fallback to all-season roster

            roster_pids = week_roster[["player_id", "team", "position", "full_name"]].drop_duplicates("player_id")
            roster_pids = roster_pids[roster_pids["position"].isin(SKILL_POS)]

            # Players on roster but not in merged
            if not merged.empty:
                existing = set(merged["player_id"].unique())
                new_roster = roster_pids[~roster_pids["player_id"].isin(existing)]
            else:
                new_roster = roster_pids

            if not new_roster.empty:
                new_rows = new_roster.copy()
                for c in ["wt", "wr", "wa", "wy", "wry", "wrz", "we", "raw_tgt",
                           "twt", "twrz", "wc", "wry_r", "wgl", "wer", "raw_car", "twc", "twgl"]:
                    new_rows[c] = 0.0
                merged = pd.concat([merged, new_rows], ignore_index=True)

            merged = merged[merged["position"].isin(SKILL_POS)]
            if merged.empty:
                continue

            # ── Compute shares with shrinkage ──
            n_t = merged["raw_tgt"].values if "raw_tgt" in merged.columns else np.zeros(len(merged))
            n_c = merged["raw_car"].values if "raw_car" in merged.columns else np.zeros(len(merged))
            twt = merged["twt"].values if "twt" in merged.columns else np.ones(len(merged))
            twrz = merged["twrz"].values if "twrz" in merged.columns else np.ones(len(merged))
            twc = merged["twc"].values if "twc" in merged.columns else np.ones(len(merged))
            twgl = merged["twgl"].values if "twgl" in merged.columns else np.ones(len(merged))

            wt = merged["wt"].values if "wt" in merged.columns else np.zeros(len(merged))
            wrz = merged["wrz"].values if "wrz" in merged.columns else np.zeros(len(merged))
            wc = merged["wc"].values if "wc" in merged.columns else np.zeros(len(merged))
            wgl = merged["wgl"].values if "wgl" in merged.columns else np.zeros(len(merged))

            raw_tgt_share = wt / np.maximum(twt, 1)
            raw_rz_share = wrz / np.maximum(twrz, 1)
            raw_car_share = wc / np.maximum(twc, 1)
            raw_gl_share = wgl / np.maximum(twgl, 1)

            tgt_share = _shrink(raw_tgt_share, n_t, k_share, 1/15)
            rz_share = _shrink(raw_rz_share, wrz, k_share, 1/15)
            car_share = _shrink(raw_car_share, n_c, k_share, 1/10)
            gl_share = _shrink(raw_gl_share, wgl, k_share, 1/10)

            # FIX 1: renormalise shares per team
            teams_in_week = merged["team"].unique()
            tgt_arr = tgt_share.copy()
            rz_arr = rz_share.copy()
            car_arr = car_share.copy()
            gl_arr = gl_share.copy()

            for t in teams_in_week:
                tmask = merged["team"].values == t
                # Target shares: normalise across all players with any share
                ts = tgt_arr[tmask].sum()
                if ts > 0:
                    tgt_arr[tmask] = tgt_arr[tmask] / ts
                rs = rz_arr[tmask].sum()
                if rs > 0:
                    rz_arr[tmask] = rz_arr[tmask] / rs
                cs = car_arr[tmask].sum()
                if cs > 0:
                    car_arr[tmask] = car_arr[tmask] / cs
                gs = gl_arr[tmask].sum()
                if gs > 0:
                    gl_arr[tmask] = gl_arr[tmask] / gs

            # Rate stats
            wr = merged["wr"].values if "wr" in merged.columns else np.zeros(len(merged))
            wa = merged["wa"].values if "wa" in merged.columns else np.zeros(len(merged))
            wy = merged["wy"].values if "wy" in merged.columns else np.zeros(len(merged))
            wry = merged["wry"].values if "wry" in merged.columns else np.zeros(len(merged))
            we = merged["we"].values if "we" in merged.columns else np.zeros(len(merged))
            wry_r = merged["wry_r"].values if "wry_r" in merged.columns else np.zeros(len(merged))
            wer = merged["wer"].values if "wer" in merged.columns else np.zeros(len(merged))

            pos_arr = merged["position"].values
            adot = np.array([_shrink(wa[i] / max(wt[i], 1), n_t[i], k_share,
                                      sp.get(f"{pos_arr[i]}_adot", 8.0)) for i in range(len(merged))])
            catch_rate = np.array([_shrink(wr[i] / max(wt[i], 1), n_t[i], k_share,
                                            sp.get(f"{pos_arr[i]}_catch_rate", 0.65)) for i in range(len(merged))])
            yac = np.array([_shrink(wy[i] / max(wr[i], 1), wr[i], k_share,
                                     sp.get(f"{pos_arr[i]}_yac_per_rec", 4.5)) for i in range(len(merged))])
            ypt = np.array([_shrink(wry[i] / max(wt[i], 1), n_t[i], k_share,
                                     sp.get(f"{pos_arr[i]}_ypt", 7.0)) for i in range(len(merged))])
            ypc = np.array([_shrink(wry_r[i] / max(wc[i], 1), n_c[i], k_share,
                                     sp.get(f"{pos_arr[i]}_ypc", 4.0)) for i in range(len(merged))])
            exp_rec = np.array([_shrink(we[i] / max(wt[i], 1), n_t[i], k_share,
                                         sp.get(f"{pos_arr[i]}_exp_rec", 0.05)) for i in range(len(merged))])
            exp_rush = np.array([_shrink(wer[i] / max(wc[i], 1), n_c[i], k_share,
                                          sp.get(f"{pos_arr[i]}_exp_rush", 0.05)) for i in range(len(merged))])

            # Build output rows
            for i in range(len(merged)):
                all_rows.append({
                    "season": season, "week": w,
                    "team": merged.iloc[i]["team"],
                    "player_id": merged.iloc[i]["player_id"],
                    "player_name": merged.iloc[i].get("full_name", ""),
                    "position": pos_arr[i],
                    "target_share": tgt_arr[i], "carry_share": car_arr[i],
                    "rz_target_share": rz_arr[i], "gl_carry_share": gl_arr[i],
                    "adot": adot[i], "catch_rate": catch_rate[i],
                    "yac_per_rec": yac[i], "yards_per_target": ypt[i],
                    "yards_per_carry": ypc[i],
                    "explosive_rec_rate": exp_rec[i], "explosive_rush_rate": exp_rush[i],
                    "n_targets": int(n_t[i]), "n_carries": int(n_c[i]),
                })

    return pd.DataFrame(all_rows)


# ═══════════════════════════════════════════════════════════════════════════════
# ACTIVE UNIVERSE (FIX 2)
# ═══════════════════════════════════════════════════════════════════════════════

def build_active_universe(rosters, injuries, depth):
    """All rostered skill players. Inactive if status != ACT or Out/Doubtful."""
    r = rosters[rosters["position"].isin(SKILL_POS)].copy()
    if "week" not in r.columns:
        return pd.DataFrame()
    r = r.rename(columns={"gsis_id": "player_id"})
    base = r[["season", "week", "team", "player_id", "position", "status", "full_name"]].copy()

    # Join injury report
    inj = injuries[["season", "week", "team", "gsis_id", "report_status"]].copy()
    inj = inj.rename(columns={"gsis_id": "player_id"})
    base = base.merge(inj, on=["season", "week", "team", "player_id"], how="left")

    # Active = roster ACT AND not (Out or Doubtful on injury report)
    base["active_flag"] = (base["status"] == "ACT") & (~base["report_status"].isin(["Out", "Doubtful"]))
    # injury_status: prefer injury report, then roster status, then "Active"
    base["injury_status"] = base["report_status"].copy()
    base.loc[base["injury_status"].isna() & (base["status"] != "ACT"), "injury_status"] = base["status"]
    base.loc[base["injury_status"].isna(), "injury_status"] = "Active"

    # Depth order
    if "depth_team" in depth.columns:
        do = depth[["season", "week", "club_code", "gsis_id", "depth_team"]].copy()
        do = do.rename(columns={"club_code": "team", "gsis_id": "player_id", "depth_team": "depth_order"})
        base = base.merge(do, on=["season", "week", "team", "player_id"], how="left")
    else:
        base["depth_order"] = np.nan

    return base[["season", "week", "team", "player_id", "position",
                  "depth_order", "active_flag", "injury_status"]].drop_duplicates()


def renormalize_shares(shares_df, active_ids, depth_map=None):
    """Zero inactive, redistribute by depth, renormalise to sum=1 per position."""
    df = shares_df.copy()
    active_set = set(active_ids)
    share_cols = ["target_share", "carry_share", "rz_target_share", "gl_carry_share"]

    for pos in SKILL_POS:
        mask = df["position"] == pos
        if not mask.any():
            continue
        active_mask = mask & df["player_id"].isin(active_set)
        inactive_mask = mask & ~df["player_id"].isin(active_set)

        for sc in share_cols:
            if sc not in df.columns:
                continue
            vacated = df.loc[inactive_mask, sc].sum()
            if vacated <= 0:
                continue
            if depth_map is not None:
                depths = df.loc[active_mask, "player_id"].map(depth_map).fillna(99).astype(float)
                weights = 1.0 / (depths + 1)
            else:
                weights = pd.Series(1.0, index=df.loc[active_mask].index)
            wt = weights.sum()
            if wt > 0:
                df.loc[active_mask, sc] += vacated * (weights / wt).values
            df.loc[inactive_mask, sc] = 0.0
            total = df.loc[mask, sc].sum()
            if total > 0:
                df.loc[mask, sc] /= total
                assert abs(df.loc[mask, sc].sum() - 1.0) < 1e-6, f"Renorm failed {pos} {sc}"

    return df


# ═══════════════════════════════════════════════════════════════════════════════
# GRID SEARCH
# ═══════════════════════════════════════════════════════════════════════════════

def tune_share_params(rec, team_tgt, car, team_car, pos_map, priors, roster_uni, params_base,
                       grid_spec=None):
    for df in [rec, car]:
        if (df["season"] >= 2025).any():
            raise RuntimeError("FATAL: tune_share_params has season >= 2025")

    at = rec[rec["season"].isin(TUNE_SEASONS)].merge(team_tgt, on=["season", "week", "game_id", "team"])
    at["actual_tgt_share"] = at["n_targets"] / at["team_targets"].clip(lower=1)
    ac = car[car["season"].isin(TUNE_SEASONS)].merge(team_car, on=["season", "week", "game_id", "team"])
    ac["actual_car_share"] = ac["n_carries"] / ac["team_carries"].clip(lower=1)

    if grid_spec is None:
        grid_spec = [(sh, k) for sh in [2, 4, 8, float("inf")] for k in [20, 50, 100]]

    grid = []
    for sh_hl, k_s in grid_spec:
        t0 = time.time()
        p = dict(params_base)
        p["usage"] = {"share_half_life": sh_hl, "k_share": k_s}
        usage = build_player_usage(
            rec[rec["season"] <= 2024], team_tgt[team_tgt["season"] <= 2024],
            car[car["season"] <= 2024], team_car[team_car["season"] <= 2024],
            pos_map, priors, p, roster_uni[roster_uni["season"] <= 2024],
            output_seasons=TUNE_SEASONS)
        dt = time.time() - t0

        eval_tgt = usage[["season", "week", "team", "player_id", "target_share", "position"]].merge(
            at[["season", "week", "player_id", "actual_tgt_share"]], on=["season", "week", "player_id"], how="inner")
        eval_tgt = eval_tgt[eval_tgt["position"].isin({"WR", "TE", "RB"})]
        rmse_tgt = np.sqrt(((eval_tgt["target_share"] - eval_tgt["actual_tgt_share"]) ** 2).mean()) if len(eval_tgt) else float("inf")

        eval_car = usage[["season", "week", "team", "player_id", "carry_share", "position"]].merge(
            ac[["season", "week", "player_id", "actual_car_share"]], on=["season", "week", "player_id"], how="inner")
        eval_car = eval_car[eval_car["position"] == "RB"]
        rmse_car = np.sqrt(((eval_car["carry_share"] - eval_car["actual_car_share"]) ** 2).mean()) if len(eval_car) else float("inf")

        mean_rmse = (rmse_tgt + rmse_car) / 2

        by_season = {}
        for s in TUNE_SEASONS:
            et = eval_tgt[eval_tgt["season"] == s]
            ec = eval_car[eval_car["season"] == s]
            by_season[s] = {
                "tgt": np.sqrt(((et["target_share"] - et["actual_tgt_share"])**2).mean()) if len(et) else float("inf"),
                "car": np.sqrt(((ec["carry_share"] - ec["actual_car_share"])**2).mean()) if len(ec) else float("inf"),
            }

        early = eval_tgt[eval_tgt["week"] <= 4]
        late = eval_tgt[eval_tgt["week"] > 4]

        grid.append({
            "share_half_life": sh_hl, "k_share": k_s,
            "mean_rmse": mean_rmse, "rmse_target": rmse_tgt, "rmse_carry": rmse_car,
            "by_season": by_season,
            "rmse_wk1_4": np.sqrt(((early["target_share"] - early["actual_tgt_share"])**2).mean()) if len(early) else float("inf"),
            "rmse_wk5_18": np.sqrt(((late["target_share"] - late["actual_tgt_share"])**2).mean()) if len(late) else float("inf"),
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

def pit_test(rec, team_tgt, car, team_car, pos_map, priors, roster_uni, params):
    full = build_player_usage(rec, team_tgt, car, team_car, pos_map, priors, params,
                               roster_uni, output_seasons=[2023])
    trunc_rec = rec[~((rec["season"] > 2023) | ((rec["season"] == 2023) & (rec["week"] >= 10)))]
    trunc_tt = team_tgt[~((team_tgt["season"] > 2023) | ((team_tgt["season"] == 2023) & (team_tgt["week"] >= 10)))]
    trunc_car = car[~((car["season"] > 2023) | ((car["season"] == 2023) & (car["week"] >= 10)))]
    trunc_tc = team_car[~((team_car["season"] > 2023) | ((team_car["season"] == 2023) & (team_car["week"] >= 10)))]
    trunc_priors = compute_position_priors(trunc_rec, trunc_car, pos_map)
    trunc = build_player_usage(trunc_rec, trunc_tt, trunc_car, trunc_tc, pos_map,
                                trunc_priors, params, roster_uni, output_seasons=[2023])

    # Compare at week 10 (now in the universe thanks to FIX 3)
    for test_week in [9, 10]:
        wr = full[(full["season"] == 2023) & (full["week"] == test_week) & (full["position"] == "WR")]
        wr = wr.sort_values("n_targets", ascending=False)
        if wr.empty:
            print(f"  PIT SKIP wk{test_week}: no WR")
            continue
        pid = wr.iloc[0]["player_id"]
        fr = full[(full["season"] == 2023) & (full["week"] == test_week) & (full["player_id"] == pid)]
        tr = trunc[(trunc["season"] == 2023) & (trunc["week"] == test_week) & (trunc["player_id"] == pid)]
        if tr.empty:
            print(f"  PIT SKIP wk{test_week}: {pid} not in truncated")
            continue
        for c in ["target_share", "carry_share", "adot", "catch_rate", "yards_per_target", "n_targets"]:
            fv = float(fr.iloc[0][c])
            tv = float(tr.iloc[0][c])
            assert abs(fv - tv) < 1e-9, f"PIT FAIL wk{test_week} {c}: {fv} vs {tv}"
        print(f"  PIT PASS wk{test_week}: {pid}")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    t_start = time.time()
    print("NFL Sim Phase 1B-FIX: Player Usage Shares")
    print("=" * 60)

    plays = load_pbp()
    scrimmage = plays[plays["play_type"].isin(["pass", "run"])].copy()
    print(f"Loaded {len(scrimmage):,} scrimmage plays ({time.time()-t_start:.1f}s)")

    t1 = time.time()
    rosters, depth, injuries = load_roster_data()
    print(f"Rosters: {len(rosters):,}, Depth: {len(depth):,}, Injuries: {len(injuries):,} ({time.time()-t1:.1f}s)")

    t2 = time.time()
    rec, team_tgt, car, team_car = build_player_game_aggs(scrimmage)
    print(f"Aggregates: rec={len(rec):,} rush={len(car):,} ({time.time()-t2:.1f}s)")

    pos_map = build_position_map(rosters)
    priors = compute_position_priors(rec, car, pos_map)

    roster_uni = rosters[rosters["position"].isin(SKILL_POS)][
        ["season", "week", "gsis_id", "team", "position", "full_name"]
    ].rename(columns={"gsis_id": "player_id"}).drop_duplicates(["season", "week", "player_id"])

    # ── Grid (12-point) ──
    print(f"\nGrid search (12 points, 2021-2024, shares normalised)...")
    t3 = time.time()
    params_base = json.load(open(PARAMS_PATH))
    best, grid = tune_share_params(
        rec[rec["season"] <= 2024], team_tgt[team_tgt["season"] <= 2024],
        car[car["season"] <= 2024], team_car[team_car["season"] <= 2024],
        pos_map, priors, roster_uni, params_base)
    print(f"Grid done: {time.time()-t3:.1f}s")

    # Extension if (2, 20) wins
    extended = False
    if best["share_half_life"] == 2 and best["k_share"] == 20:
        print(f"\nBoundary winner (2,20) — running pre-declared extension (6 points)...")
        ext_spec = [(sh, k) for sh in [1, 2] for k in [5, 10, 20]]
        t4 = time.time()
        ext_best, ext_grid = tune_share_params(
            rec[rec["season"] <= 2024], team_tgt[team_tgt["season"] <= 2024],
            car[car["season"] <= 2024], team_car[team_car["season"] <= 2024],
            pos_map, priors, roster_uni, params_base, grid_spec=ext_spec)
        print(f"Extension done: {time.time()-t4:.1f}s")
        # Combine: remove the duplicate (2, 20)
        combined = grid.copy()
        for g in ext_grid:
            if not any(abs(g["share_half_life"] - x["share_half_life"]) < 0.01 and
                       abs(g["k_share"] - x["k_share"]) < 0.01 for x in combined):
                combined.append(g)
        combined.sort(key=lambda x: x["mean_rmse"])
        best = combined[0]
        grid = combined
        extended = True
        print(f"Combined best: sh_hl={best['share_half_life']} k={best['k_share']}  RMSE={best['mean_rmse']:.4f}")

    # Boundary check
    all_hls = sorted(set(g["share_half_life"] for g in grid))
    all_ks = sorted(set(g["k_share"] for g in grid))
    on_boundary = (best["share_half_life"] == min(all_hls) or best["share_half_life"] == max(all_hls) or
                    best["k_share"] == min(all_ks) or best["k_share"] == max(all_ks))
    boundary_str = "BOUNDARY" if on_boundary else "INTERIOR"
    print(f"  Chosen point is {boundary_str} of the grid.")

    # Update params
    params = json.load(open(PARAMS_PATH))
    params["usage"] = {
        "share_half_life": best["share_half_life"],
        "k_share": best["k_share"],
        "extended_grid": extended,
        "boundary": boundary_str,
        "grid_results": [{k: v for k, v in g.items() if k != "by_season"}
                          for g in sorted(grid, key=lambda x: x["mean_rmse"])],
    }
    with open(PARAMS_PATH, "w") as f:
        json.dump(params, f, indent=2, default=str)

    # ── Build full usage ──
    print(f"\nBuilding full usage...")
    t5 = time.time()
    usage = build_player_usage(rec, team_tgt, car, team_car, pos_map, priors, params, roster_uni)
    print(f"  {len(usage):,} rows ({time.time()-t5:.1f}s)")

    # FIX 1 assertion: shares sum to 1 per team-week
    print("\nFIX 1: share sum assertions...")
    played = usage[(usage["n_targets"] > 0) | (usage["n_carries"] > 0)]
    teams_weeks = played.groupby(["season", "week", "team"]).size().reset_index()
    fail_count = 0
    for _, tw in teams_weeks.iterrows():
        s, w, t = tw["season"], tw["week"], tw["team"]
        tw_data = usage[(usage["season"] == s) & (usage["week"] == w) & (usage["team"] == t)]
        for sc in ["target_share", "carry_share", "rz_target_share", "gl_carry_share"]:
            total = tw_data[sc].sum()
            if abs(total - 1.0) > 1e-6 and total > 0:
                fail_count += 1
                if fail_count <= 3:
                    print(f"  FAIL: {s} wk{w} {t} {sc} sums to {total:.6f}")
    if fail_count == 0:
        print(f"  All team-week share sums within 1e-6 of 1.0 ✓")
    else:
        print(f"  {fail_count} failures!")
        sys.exit(1)

    # FIX 2: active universe
    print("\nFIX 2: active universe...")
    active = build_active_universe(rosters, injuries, depth)
    print(f"  {len(active):,} rows")
    print(f"  Active status distribution:")
    print(f"    {active['active_flag'].value_counts().to_dict()}")
    print(f"  Injury status top values:")
    print(f"    {active['injury_status'].value_counts().head(6).to_dict()}")
    for s in [2021, 2022, 2023, 2024, 2025]:
        n_out = len(active[(active["season"] == s) & (active["injury_status"] == "Out")])
        assert n_out >= 200, f"FAIL: {s} has only {n_out} Out rows (expected >= 200)"
        print(f"    {s}: {n_out} Out")
    print(f"  Out count assertions (>= 200 per season): ✓")

    # Questionable-but-inactive: players Questionable who had 0 snaps
    # Use snap_counts to check
    try:
        import nflreadpy
        snaps = nflreadpy.load_snap_counts(list(range(2021, 2027))).to_pandas()
        q_inj = injuries[injuries["report_status"] == "Questionable"][
            ["season", "week", "team", "gsis_id"]].rename(columns={"gsis_id": "player_id"})
        q_snaps = q_inj.merge(
            snaps[["season", "week", "player", "offense_snaps"]].rename(columns={"player": "player_id"}),
            on=["season", "week", "player_id"], how="left")
        q_snaps["zero_snaps"] = q_snaps["offense_snaps"].fillna(0) == 0
        print(f"\n  Questionable-but-inactive (zero offensive snaps) per season:")
        for s in OUTPUT_SEASONS:
            qs = q_snaps[q_snaps["season"] == s]
            n_q = len(qs)
            n_inactive = qs["zero_snaps"].sum()
            print(f"    {s}: {int(n_inactive)}/{n_q} Questionable players had 0 offensive snaps")
    except Exception as e:
        print(f"\n  Questionable-but-inactive: SKIP (snap_counts not available: {e})")

    # FIX 3: 32-team universe
    print(f"\nFIX 3: 32-team universe...")
    s26 = usage[usage["season"] == 2026]
    s26_w2 = s26[s26["week"] == 2]
    print(f"  2026 wk2: {s26_w2['team'].nunique()} teams, {len(s26_w2)} players")
    assert s26_w2["team"].nunique() == 32, f"FAIL: 2026 wk2 has {s26_w2['team'].nunique()} teams"
    assert len(s26_w2) >= 300, f"FAIL: 2026 wk2 has {len(s26_w2)} players"
    print(f"  Assertions: 32 teams ✓, {len(s26_w2)} >= 300 players ✓")

    # Identity check on rate attributes (FIX 1 changed shares, rates should be same)
    old_path = Path("/tmp/usage_old.parquet")
    if old_path.exists():
        old = pd.read_parquet(old_path)
        rate_cols = ["adot", "catch_rate", "yac_per_rec", "yards_per_target",
                      "yards_per_carry", "explosive_rec_rate", "explosive_rush_rate",
                      "n_targets", "n_carries"]
        merge_keys = ["season", "week", "team", "player_id"]
        merged = old.merge(usage, on=merge_keys, suffixes=("_old", "_new"), how="inner")
        mismatches = 0
        for c in rate_cols:
            old_c, new_c = f"{c}_old", f"{c}_new"
            if old_c in merged.columns and new_c in merged.columns:
                diff = (merged[old_c].astype(float) - merged[new_c].astype(float)).abs()
                bad = diff[diff > 1e-9]
                if len(bad):
                    mismatches += len(bad)
                    print(f"  RATE MISMATCH: {c} has {len(bad)} rows > 1e-9")
        if mismatches == 0:
            print(f"  Rate identity check: {len(merged)} rows, all rates match to 1e-9 ✓")
    else:
        print(f"  Rate identity check: SKIP (no old file)")

    # Save
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    usage.to_parquet(OUT_DIR / "player_usage_weekly.parquet", index=False)
    active.to_parquet(OUT_DIR / "active_universe_weekly.parquet", index=False)

    # PIT test
    print(f"\nPIT test...")
    pit_test(rec, team_tgt, car, team_car, pos_map, priors, roster_uni, params)

    # Renormalisation example
    print(f"\nRenormalisation example...")
    # Find a 2023 team-week with an Out RB1
    out_rbs = active[(active["season"] == 2023) & (active["injury_status"] == "Out") &
                       (active["position"] == "RB")]
    if not out_rbs.empty:
        example = out_rbs.iloc[0]
        s, w, t = int(example["season"]), int(example["week"]), example["team"]
        tw_usage = usage[(usage["season"] == s) & (usage["week"] == w) & (usage["team"] == t)].copy()
        tw_active = active[(active["season"] == s) & (active["week"] == w) & (active["team"] == t)]
        active_ids = tw_active[tw_active["active_flag"]]["player_id"].tolist()
        depth_map = tw_active.set_index("player_id")["depth_order"].to_dict()
        print(f"  {t} {s} wk{w}: Out RB = {example['player_id']}")
        print(f"  Before: carry shares = {dict(zip(tw_usage['player_id'], tw_usage['carry_share'].round(3)))}")
        renorm = renormalize_shares(tw_usage, active_ids, depth_map)
        print(f"  After:  carry shares = {dict(zip(renorm['player_id'], renorm['carry_share'].round(3)))}")
        out_pid = example["player_id"]
        assert renorm[renorm["player_id"] == out_pid]["carry_share"].iloc[0] == 0.0, "Renorm: Out player share != 0"
        rb_total = renorm[renorm["position"] == "RB"]["carry_share"].sum()
        assert abs(rb_total - 1.0) < 1e-6, f"Renorm: RB carry shares sum {rb_total}"
        print(f"  Out player share = 0 ✓, RB carry sum = {rb_total:.6f} ✓")

    # Face validity
    print(f"\n{'='*60}")
    print("FACE VALIDITY (2024 wk 18)")
    print(f"{'='*60}")
    u24 = usage[(usage["season"] == 2024) & (usage["week"] == 18)]
    if not u24.empty:
        print("\n  Top 10 target share:")
        top_t = u24.nlargest(10, "target_share")
        for _, r in top_t.iterrows():
            print(f"    {r['player_name']:<25s} {r['team']:>3s} {r['position']:>2s}  "
                  f"tgt_sh={r['target_share']:.3f}  n_tgt={int(r['n_targets'])}")
        print("\n  Top 10 RB carry share:")
        top_c = u24[u24["position"] == "RB"].nlargest(10, "carry_share")
        for _, r in top_c.iterrows():
            print(f"    {r['player_name']:<25s} {r['team']:>3s}  "
                  f"car_sh={r['carry_share']:.3f}  n_car={int(r['n_carries'])}")

    # Check 5
    print(f"\n  Share RMSE by season (best params):")
    for s, v in sorted(best.get("by_season", {}).items()):
        print(f"    {s}: tgt={v['tgt']:.4f}  car={v['car']:.4f}")
    print(f"  Wk 1-4 tgt RMSE: {best.get('rmse_wk1_4', 'N/A'):.4f}")
    print(f"  Wk 5-18 tgt RMSE: {best.get('rmse_wk5_18', 'N/A'):.4f}")

    print(f"\nTotal elapsed: {time.time()-t_start:.1f}s")
    print("Phase 1B-FIX complete.")


if __name__ == "__main__":
    main()
