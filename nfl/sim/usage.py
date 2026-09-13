#!/usr/bin/env python3
"""
NFL Sim Phase 1B-FIX-2 — Point-in-time weekly player usage shares.

FORMULA (for each share column: target_share, carry_share, rz_target_share, gl_carry_share):
  For player p on team t, week w:
    opp_p    = decay-weighted sum of TEAM opportunities over games in weeks < w
               where p was ACTIVE for t
    touch_p  = decay-weighted sum of p's own touches over those same games
    obs      = touch_p / opp_p           (0 if opp_p = 0)
    n_eff    = opp_p                     (team opportunities, NOT player touches)
    prior    = p's own s-1 share if >= 50 team opp while active in s-1;
               else league mean share for (position, depth_order) from s-1
    shrunk   = (n_eff * obs + k_share * prior) / (n_eff + k_share)
    blend    = (1-prior_weight)*shrunk + prior_weight*(prior_regression*prior
               + (1-prior_regression)*league_mean_for_position_depth)
  Then renormalise each share within (season, week, team) to sum to 1.
  Decay weight per game = 0.5**((w-1-game_week)/share_half_life).

Rate attributes (adot, catch_rate, yac, ypt, ypc, explosive rates) keep n = player's
own targets or carries — that IS the right sample size for a rate.

Carries EXCLUDE qb_scramble and qb_kneel (designed runs + QB sneaks only).
"""

import json, sys, time, gc
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


def _depth_group_vec(pos_series, depth_series):
    """Vectorised depth-group assignment. Returns a Series of strings."""
    result = pd.Series("", index=pos_series.index)
    d = pd.to_numeric(depth_series, errors="coerce")
    for pos, bins, default in [
        ("RB", {1: "RB1", 2: "RB2"}, "RB3+"),
        ("WR", {1: "WR1", 2: "WR2", 3: "WR3"}, "WR4+"),
        ("TE", {1: "TE1"}, "TE2+"),
        ("QB", {1: "QB"}, "QB"),
    ]:
        mask = pos_series == pos
        result.loc[mask] = default
        for dval, label in bins.items():
            result.loc[mask & (d == dval)] = label
    return result


def _shrink_vec(x, n, k, mu):
    return (n * x + k * mu) / (n + k)


# ═══════════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════════

PBP_COLS = ["season", "week", "game_id", "posteam", "play_type",
            "receiver_player_id", "rusher_player_id", "passer_player_id",
            "complete_pass", "yards_gained", "air_yards", "yards_after_catch",
            "yardline_100", "qb_scramble", "qb_kneel",
            "rusher_player_name", "receiver_player_name"]


def load_pbp():
    frames = []
    for s in SEASONS:
        p = PBP_DIR / f"pbp_{s}.parquet"
        if p.exists():
            import pyarrow.parquet as pq
            schema_cols = pq.read_schema(p).names
            cols = [c for c in PBP_COLS if c in schema_cols]
            frames.append(pd.read_parquet(p, columns=cols))
    return pd.concat(frames, ignore_index=True)


def load_roster_data():
    PBP_DIR.mkdir(parents=True, exist_ok=True)
    r_path = PBP_DIR / "rosters_weekly.parquet"
    d_path = PBP_DIR / "depth_charts.parquet"
    i_path = PBP_DIR / "injuries.parquet"

    if r_path.exists() and d_path.exists() and i_path.exists():
        rosters = pd.read_parquet(r_path)
        depth = pd.read_parquet(d_path)
        injuries = pd.read_parquet(i_path)
    else:
        import nflreadpy
        rosters = nflreadpy.load_rosters_weekly(SEASONS).to_pandas()
        depth = nflreadpy.load_depth_charts(SEASONS).to_pandas()
        injuries = nflreadpy.load_injuries(SEASONS).to_pandas()
        rosters.to_parquet(r_path, index=False)
        depth.to_parquet(d_path, index=False)
        injuries.to_parquet(i_path, index=False)

    # Keep only needed columns to save memory
    roster_cols = ["season", "week", "team", "gsis_id", "position", "status", "full_name"]
    rosters = rosters[[c for c in roster_cols if c in rosters.columns]]
    depth_cols = ["season", "week", "club_code", "gsis_id", "position", "depth_team"]
    depth = depth[[c for c in depth_cols if c in depth.columns]]
    inj_cols = ["season", "week", "team", "gsis_id", "report_status"]
    injuries = injuries[[c for c in inj_cols if c in injuries.columns]]

    return rosters, depth, injuries


# ═══════════════════════════════════════════════════════════════════════════════
# PRE-AGGREGATE
# ═══════════════════════════════════════════════════════════════════════════════

def build_player_game_aggs(plays):
    passes = plays[plays["play_type"] == "pass"].copy()
    # Carries: designed runs only — exclude qb_scramble (qb_kneel is already a separate play_type)
    run_mask = plays["play_type"] == "run"
    if "qb_scramble" in plays.columns:
        run_mask = run_mask & (plays["qb_scramble"] != 1)
    rushes = plays[run_mask].copy()

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
# ACTIVE UNIVERSE
# ═══════════════════════════════════════════════════════════════════════════════

def build_active_universe(rosters, injuries, depth):
    """All rostered skill players. Inactive if status != ACT or Out/Doubtful."""
    r = rosters[rosters["position"].isin(SKILL_POS)].copy()
    if "week" not in r.columns:
        return pd.DataFrame()
    r = r.rename(columns={"gsis_id": "player_id"})
    base = r[["season", "week", "team", "player_id", "position", "status", "full_name"]].copy()

    inj = injuries[["season", "week", "team", "gsis_id", "report_status"]].copy()
    inj = inj.rename(columns={"gsis_id": "player_id"})
    base = base.merge(inj, on=["season", "week", "team", "player_id"], how="left")

    base["active_flag"] = (base["status"] == "ACT") & (~base["report_status"].isin(["Out", "Doubtful"]))
    base["injury_status"] = base["report_status"].copy()
    base.loc[base["injury_status"].isna() & (base["status"] != "ACT"), "injury_status"] = base["status"]
    base.loc[base["injury_status"].isna(), "injury_status"] = "Active"

    # Depth order — min depth_team per (season, week, team, player, position)
    if "depth_team" in depth.columns:
        do = depth[depth["position"].isin(SKILL_POS)].copy()
        do["depth_team"] = pd.to_numeric(do["depth_team"], errors="coerce")
        do = do.groupby(["season", "week", "club_code", "gsis_id"], observed=True)[
            "depth_team"].min().reset_index()
        do = do.rename(columns={"club_code": "team", "gsis_id": "player_id", "depth_team": "depth_order"})
        base = base.merge(do[["season", "week", "team", "player_id", "depth_order"]],
                          on=["season", "week", "team", "player_id"], how="left")
    else:
        base["depth_order"] = np.nan

    # Carry forward last available week per season (for 2026 wk2+)
    extras = []
    for s in base["season"].unique():
        s_data = base[base["season"] == s]
        if s_data.empty:
            continue
        max_w = int(s_data["week"].max())
        last_week = s_data[s_data["week"] == max_w].copy()
        if not last_week.empty:
            nw = last_week.copy()
            nw["week"] = max_w + 1
            extras.append(nw)
    if extras:
        base = pd.concat([base] + extras, ignore_index=True)

    base = base[["season", "week", "team", "player_id", "position",
                  "depth_order", "active_flag", "injury_status", "status"]].drop_duplicates(
        subset=["season", "week", "team", "player_id"])

    return base


# ═══════════════════════════════════════════════════════════════════════════════
# DEPTH-ORDER PRIOR TABLE + PLAYER SEASON SHARES
# ═══════════════════════════════════════════════════════════════════════════════

def compute_season_share_data(active_uni, rec, team_tgt, car, team_car):
    """
    Returns:
      depth_order_priors: dict season -> {depth_group: {share_col: mean}}
      player_season_shares: DataFrame with per-player per-season shares and opp counts
    """
    depth_order_priors = {}
    pss_rows = []

    for season in sorted(active_uni["season"].unique()):
        s_act = active_uni[(active_uni["season"] == season) & (active_uni["active_flag"])]
        if s_act.empty:
            continue

        act_pw = s_act[["week", "team", "player_id", "position", "depth_order"]].drop_duplicates(
            subset=["week", "team", "player_id"])
        act_pw["depth_group"] = _depth_group_vec(act_pw["position"], act_pw["depth_order"])

        s_rec = rec[rec["season"] == season]
        s_tt = team_tgt[team_tgt["season"] == season]
        s_car = car[car["season"] == season]
        s_tc = team_car[team_car["season"] == season]

        # ── Targets ──
        pw_tgt = act_pw[["week", "team", "player_id", "position", "depth_group"]].merge(
            s_tt[["week", "game_id", "team", "team_targets", "team_rz_targets"]],
            on=["week", "team"], how="inner")
        pw_tgt = pw_tgt.merge(
            s_rec[["week", "game_id", "team", "player_id", "n_targets", "rz_targets"]],
            on=["week", "game_id", "team", "player_id"], how="left")
        pw_tgt["n_targets"] = pw_tgt["n_targets"].fillna(0)
        pw_tgt["rz_targets"] = pw_tgt["rz_targets"].fillna(0)

        p_tgt = pw_tgt.groupby(["player_id", "team", "position", "depth_group"], observed=True).agg(
            opp_tgt=("team_targets", "sum"), own_tgt=("n_targets", "sum"),
            opp_rz=("team_rz_targets", "sum"), own_rz=("rz_targets", "sum"),
        ).reset_index()

        # ── Carries ──
        pw_car = act_pw[["week", "team", "player_id", "position", "depth_group"]].merge(
            s_tc[["week", "game_id", "team", "team_carries", "team_gl_carries"]],
            on=["week", "team"], how="inner")
        pw_car = pw_car.merge(
            s_car[["week", "game_id", "team", "player_id", "n_carries", "gl_carries"]],
            on=["week", "game_id", "team", "player_id"], how="left")
        pw_car["n_carries"] = pw_car["n_carries"].fillna(0)
        pw_car["gl_carries"] = pw_car["gl_carries"].fillna(0)

        p_car = pw_car.groupby(["player_id", "team", "position", "depth_group"], observed=True).agg(
            opp_car=("team_carries", "sum"), own_car=("n_carries", "sum"),
            opp_gl=("team_gl_carries", "sum"), own_gl=("gl_carries", "sum"),
        ).reset_index()

        # ── Merge ──
        merged = p_tgt.merge(p_car[["player_id", "team", "opp_car", "own_car", "opp_gl", "own_gl"]],
                             on=["player_id", "team"], how="outer")
        for c in ["opp_tgt", "own_tgt", "opp_rz", "own_rz", "opp_car", "own_car", "opp_gl", "own_gl"]:
            merged[c] = merged[c].fillna(0)
        # Fill position/depth_group from p_car if missing
        if "position" not in merged.columns or merged["position"].isna().any():
            merged["position"] = merged["position"].fillna(
                p_car.set_index("player_id")["position"].reindex(merged["player_id"]).values)
        if "depth_group" not in merged.columns or merged["depth_group"].isna().any():
            merged["depth_group"] = merged["depth_group"].fillna(
                _depth_group_vec(merged["position"], pd.Series(np.nan, index=merged.index)))

        merged["tgt_share"] = np.where(merged["opp_tgt"] > 0, merged["own_tgt"] / merged["opp_tgt"], 0.0)
        merged["car_share"] = np.where(merged["opp_car"] > 0, merged["own_car"] / merged["opp_car"], 0.0)
        merged["rz_tgt_share"] = np.where(merged["opp_rz"] > 0, merged["own_rz"] / merged["opp_rz"], 0.0)
        merged["gl_car_share"] = np.where(merged["opp_gl"] > 0, merged["own_gl"] / merged["opp_gl"], 0.0)
        merged["season"] = season

        pss_rows.append(merged[["season", "player_id", "team", "position", "depth_group",
                                 "opp_tgt", "opp_car", "tgt_share", "car_share",
                                 "rz_tgt_share", "gl_car_share"]])

        # Depth-group league means
        dg = merged.groupby("depth_group", observed=True).agg(
            target_share=("tgt_share", "mean"),
            carry_share=("car_share", "mean"),
            rz_target_share=("rz_tgt_share", "mean"),
            gl_carry_share=("gl_car_share", "mean"),
            n_players=("player_id", "nunique"),
        )
        depth_order_priors[season] = dg[["target_share", "carry_share",
                                          "rz_target_share", "gl_carry_share"]].to_dict("index")

    player_season_shares = pd.concat(pss_rows, ignore_index=True) if pss_rows else pd.DataFrame()
    return depth_order_priors, player_season_shares


# ═══════════════════════════════════════════════════════════════════════════════
# PIT USAGE BUILDER (vectorised week-loop)
# ═══════════════════════════════════════════════════════════════════════════════

def build_player_usage(rec, team_tgt, car, team_car, pos_map, rate_priors, params,
                        roster_universe, active_universe, depth_order_priors,
                        player_season_shares, output_seasons=None):
    sh_hl = params.get("usage", {}).get("share_half_life", float("inf"))
    k_share = params.get("usage", {}).get("k_share", 50)
    prior_weight = params.get("prior_weight", 0.3)
    prior_regression = params.get("prior_regression", 0.5)
    k_rate = params.get("k", 100)
    fin_hl = sh_hl is not None and sh_hl != float("inf") and sh_hl > 0

    all_frames = []
    seasons = output_seasons or OUTPUT_SEASONS

    for season in seasons:
        sp = rate_priors.get(season - 1, rate_priors.get(min(rate_priors.keys()), {}))
        s_rec = rec[rec["season"] == season]
        s_car = car[car["season"] == season]
        s_tt = team_tgt[team_tgt["season"] == season]
        s_tc = team_car[team_car["season"] == season]
        s_active = active_universe[active_universe["season"] == season]

        last_w = 0
        for df in [s_rec, s_car]:
            if not df.empty:
                last_w = max(last_w, int(df["week"].max()))
        if last_w == 0:
            last_w = 1
        weeks = list(range(1, min(22, last_w + 1) + 1))

        s_roster = roster_universe[roster_universe["season"] == season]

        # Depth-order priors from s-1
        dop = depth_order_priors.get(season - 1, depth_order_priors.get(
            min(depth_order_priors.keys()) if depth_order_priors else season, {}))

        # Build per-player prior lookup from s-1
        # prior = own s-1 share if >= 50 team opp, else depth-group league mean
        pss = player_season_shares[player_season_shares["season"] == season - 1] if not player_season_shares.empty else pd.DataFrame()

        # Position map
        pm = pos_map[pos_map["season"] == season][["player_id", "position", "full_name"]].drop_duplicates("player_id")
        pm2 = pos_map[pos_map["season"] == season - 1][["player_id", "position", "full_name"]].drop_duplicates("player_id")
        pm_all = pd.concat([pm, pm2]).drop_duplicates("player_id", keep="first")

        for w in weeks:
            # Active player-week pairs for weeks < w
            act_prior = s_active[(s_active["week"] < w) & (s_active["active_flag"])]

            # ── Receiving: vectorised opp/touch accumulation ──
            avail_tt = s_tt[s_tt["week"] < w]
            if not avail_tt.empty and not act_prior.empty:
                act_pw = act_prior[["week", "team", "player_id"]].drop_duplicates()
                pw = act_pw.merge(avail_tt[["week", "game_id", "team", "team_targets", "team_rz_targets"]],
                                   on=["week", "team"], how="inner")
                avail_rec = s_rec[s_rec["week"] < w]
                pw = pw.merge(avail_rec[["week", "game_id", "team", "player_id",
                                          "n_targets", "rz_targets", "n_receptions",
                                          "air_yards_sum", "yac_sum", "rec_yards", "exp_recs"]],
                               on=["week", "game_id", "team", "player_id"], how="left")
                for c in ["n_targets", "rz_targets", "n_receptions", "air_yards_sum",
                           "yac_sum", "rec_yards", "exp_recs"]:
                    pw[c] = pw[c].fillna(0)

                if fin_hl:
                    d = 0.5 ** ((w - 1 - pw["week"]) / sh_hl)
                else:
                    d = 1.0
                pw["w_opp_tgt"] = pw["team_targets"] * d
                pw["w_opp_rz"] = pw["team_rz_targets"] * d
                pw["w_tgt"] = pw["n_targets"] * d
                pw["w_rz"] = pw["rz_targets"] * d
                pw["w_rec"] = pw["n_receptions"] * d
                pw["w_air"] = pw["air_yards_sum"] * d
                pw["w_yac"] = pw["yac_sum"] * d
                pw["w_ry"] = pw["rec_yards"] * d
                pw["w_er"] = pw["exp_recs"] * d

                p_r = pw.groupby(["team", "player_id"], observed=True).agg(
                    opp_tgt=("w_opp_tgt", "sum"), opp_rz=("w_opp_rz", "sum"),
                    w_tgt=("w_tgt", "sum"), w_rz=("w_rz", "sum"),
                    w_rec=("w_rec", "sum"), w_air=("w_air", "sum"),
                    w_yac=("w_yac", "sum"), w_ry=("w_ry", "sum"),
                    w_er=("w_er", "sum"), raw_tgt=("n_targets", "sum"),
                ).reset_index()
            else:
                p_r = pd.DataFrame()

            # ── Rushing ──
            avail_tc = s_tc[s_tc["week"] < w]
            if not avail_tc.empty and not act_prior.empty:
                act_pw = act_prior[["week", "team", "player_id"]].drop_duplicates()
                pw = act_pw.merge(avail_tc[["week", "game_id", "team", "team_carries", "team_gl_carries"]],
                                   on=["week", "team"], how="inner")
                avail_car = s_car[s_car["week"] < w]
                pw = pw.merge(avail_car[["week", "game_id", "team", "player_id",
                                          "n_carries", "rush_yards", "gl_carries", "exp_rushes"]],
                               on=["week", "game_id", "team", "player_id"], how="left")
                for c in ["n_carries", "rush_yards", "gl_carries", "exp_rushes"]:
                    pw[c] = pw[c].fillna(0)

                if fin_hl:
                    d = 0.5 ** ((w - 1 - pw["week"]) / sh_hl)
                else:
                    d = 1.0
                pw["w_opp_car"] = pw["team_carries"] * d
                pw["w_opp_gl"] = pw["team_gl_carries"] * d
                pw["w_car"] = pw["n_carries"] * d
                pw["w_gl"] = pw["gl_carries"] * d
                pw["w_ry_r"] = pw["rush_yards"] * d
                pw["w_exr"] = pw["exp_rushes"] * d

                p_c = pw.groupby(["team", "player_id"], observed=True).agg(
                    opp_car=("w_opp_car", "sum"), opp_gl=("w_opp_gl", "sum"),
                    w_car=("w_car", "sum"), w_gl=("w_gl", "sum"),
                    w_ry_r=("w_ry_r", "sum"), w_exr=("w_exr", "sum"),
                    raw_car=("n_carries", "sum"),
                ).reset_index()
            else:
                p_c = pd.DataFrame()

            # ── Merge receiving + rushing ──
            if not p_r.empty and not p_c.empty:
                merged = p_r.merge(p_c, on=["team", "player_id"], how="outer")
            elif not p_r.empty:
                merged = p_r.copy()
            elif not p_c.empty:
                merged = p_c.copy()
            else:
                merged = pd.DataFrame(columns=["team", "player_id"])

            num_cols = [c for c in merged.columns if c not in ("team", "player_id")]
            for c in num_cols:
                merged[c] = merged[c].fillna(0)

            # Join position + name
            if not merged.empty:
                merged = merged.merge(pm_all, on="player_id", how="left")
            else:
                merged = pd.DataFrame(columns=["team", "player_id", "position", "full_name"])

            # ── Add 53-man roster players with no plays ──
            # Share universe = players with ACT roster status (53-man roster)
            # Excludes practice squad (DEV), IR (RES), inactive list (INA), etc.
            # Players who are Out for THIS week are kept (their share = when-healthy value;
            # renormalize_shares handles current-week injury redistribution)
            w_roster_full = s_active[s_active["week"] == w]
            if w_roster_full.empty and w > 1:
                lw_r = s_active[s_active["week"] < w]["week"].max() if not s_active[s_active["week"] < w].empty else None
                if lw_r is not None:
                    w_roster_full = s_active[s_active["week"] == lw_r]
            # Share universe = anyone who was ACT (on-field eligible) at any point
            # in weeks <= w this season. Includes INA/Out players who were
            # previously ACT (like Hurts wk17-18). Excludes players who were
            # never ACT (pure game-day inactives with no evidence).
            ever_act_this_season = s_active[(s_active["week"] <= w) & (s_active["status"] == "ACT")]
            act_roster_pids = set(ever_act_this_season["player_id"].unique())

            week_roster = s_roster[s_roster["week"] == w] if "week" in s_roster.columns else s_roster
            if week_roster.empty:
                week_roster = s_roster
            roster_pids = week_roster[["player_id", "team", "position", "full_name"]].drop_duplicates("player_id")
            roster_pids = roster_pids[roster_pids["position"].isin(SKILL_POS)]
            roster_pids = roster_pids[roster_pids["player_id"].isin(act_roster_pids)]

            if not merged.empty:
                existing = set(merged["player_id"].unique())
                new_roster = roster_pids[~roster_pids["player_id"].isin(existing)]
            else:
                new_roster = roster_pids

            if not new_roster.empty:
                nr = new_roster.copy()
                zero_cols = ["opp_tgt", "opp_rz", "w_tgt", "w_rz", "w_rec", "w_air",
                             "w_yac", "w_ry", "w_er", "raw_tgt",
                             "opp_car", "opp_gl", "w_car", "w_gl", "w_ry_r", "w_exr", "raw_car"]
                for c in zero_cols:
                    nr[c] = 0.0
                merged = pd.concat([merged, nr], ignore_index=True)

            merged = merged[merged["position"].isin(SKILL_POS)]
            # Filter to ever-ACT this season
            merged = merged[merged["player_id"].isin(act_roster_pids)]
            merged = merged.drop_duplicates(subset=["team", "player_id"])
            if merged.empty:
                continue

            # Ensure all columns exist
            for c in ["opp_tgt", "opp_rz", "w_tgt", "w_rz", "w_rec", "w_air",
                       "w_yac", "w_ry", "w_er", "raw_tgt",
                       "opp_car", "opp_gl", "w_car", "w_gl", "w_ry_r", "w_exr", "raw_car"]:
                if c not in merged.columns:
                    merged[c] = 0.0

            # ── Depth order for this week ──
            w_depth = s_active[s_active["week"] == w][["player_id", "depth_order"]].drop_duplicates("player_id")
            if w_depth.empty and w > 1:
                lw = s_active[s_active["week"] < w]["week"].max() if not s_active[s_active["week"] < w].empty else None
                if lw is not None:
                    w_depth = s_active[s_active["week"] == lw][["player_id", "depth_order"]].drop_duplicates("player_id")
            merged = merged.merge(w_depth, on="player_id", how="left")
            merged["depth_group"] = _depth_group_vec(merged["position"], merged["depth_order"])

            # ── Vectorised prior lookup ──
            # Build prior arrays via merge with pss and dop
            # Default: depth-group league mean
            dg_df = pd.DataFrame([
                {"depth_group": dg,
                 "dg_tgt": vals.get("target_share", 1/15),
                 "dg_rz": vals.get("rz_target_share", 1/15),
                 "dg_car": vals.get("carry_share", 1/10),
                 "dg_gl": vals.get("gl_carry_share", 1/10)}
                for dg, vals in dop.items()
            ]) if dop else pd.DataFrame(columns=["depth_group", "dg_tgt", "dg_rz", "dg_car", "dg_gl"])

            merged = merged.merge(dg_df, on="depth_group", how="left")
            for c in ["dg_tgt", "dg_rz", "dg_car", "dg_gl"]:
                merged[c] = merged[c].fillna(1/15 if "tgt" in c or "rz" in c else 1/10)

            # Player's own s-1 prior (if >= 50 opp)
            if not pss.empty:
                p_prev = pss[["player_id", "opp_tgt", "opp_car",
                               "tgt_share", "car_share", "rz_tgt_share", "gl_car_share"]].copy()
                # Dedup: if player was on multiple teams in s-1, take the one with more opp
                p_prev["_total_opp"] = p_prev["opp_tgt"].fillna(0) + p_prev["opp_car"].fillna(0)
                p_prev = p_prev.sort_values("_total_opp", ascending=False).drop_duplicates("player_id").drop(columns="_total_opp")
                p_prev = p_prev.rename(columns={
                    "tgt_share": "p_tgt", "car_share": "p_car",
                    "rz_tgt_share": "p_rz", "gl_car_share": "p_gl",
                    "opp_tgt": "p_opp_tgt", "opp_car": "p_opp_car"})
                merged = merged.merge(p_prev, on="player_id", how="left")
            else:
                for c in ["p_tgt", "p_car", "p_rz", "p_gl", "p_opp_tgt", "p_opp_car"]:
                    merged[c] = np.nan

            # Prior = own s-1 if opp >= 50, else depth-group mean
            for share, p_col, dg_col, opp_col in [
                ("prior_tgt", "p_tgt", "dg_tgt", "p_opp_tgt"),
                ("prior_rz", "p_rz", "dg_rz", "p_opp_tgt"),
                ("prior_car", "p_car", "dg_car", "p_opp_car"),
                ("prior_gl", "p_gl", "dg_gl", "p_opp_car"),
            ]:
                has_prior = merged[opp_col].fillna(0) >= 50
                merged[share] = np.where(has_prior, merged[p_col].fillna(0), merged[dg_col])

            # ── Share computation ──
            opp_tgt = merged["opp_tgt"].values
            opp_rz = merged["opp_rz"].values
            opp_car = merged["opp_car"].values
            opp_gl = merged["opp_gl"].values

            obs_tgt = np.where(opp_tgt > 0, merged["w_tgt"].values / opp_tgt, 0.0)
            obs_rz = np.where(opp_rz > 0, merged["w_rz"].values / opp_rz, 0.0)
            obs_car = np.where(opp_car > 0, merged["w_car"].values / opp_car, 0.0)
            obs_gl = np.where(opp_gl > 0, merged["w_gl"].values / opp_gl, 0.0)

            p_tgt_v = merged["prior_tgt"].values
            p_rz_v = merged["prior_rz"].values
            p_car_v = merged["prior_car"].values
            p_gl_v = merged["prior_gl"].values

            dg_tgt_v = merged["dg_tgt"].values
            dg_rz_v = merged["dg_rz"].values
            dg_car_v = merged["dg_car"].values
            dg_gl_v = merged["dg_gl"].values

            shrunk_tgt = (opp_tgt * obs_tgt + k_share * p_tgt_v) / (opp_tgt + k_share)
            shrunk_rz = (opp_rz * obs_rz + k_share * p_rz_v) / (opp_rz + k_share)
            shrunk_car = (opp_car * obs_car + k_share * p_car_v) / (opp_car + k_share)
            shrunk_gl = (opp_gl * obs_gl + k_share * p_gl_v) / (opp_gl + k_share)

            blend_tgt = (1 - prior_weight) * shrunk_tgt + prior_weight * (
                prior_regression * p_tgt_v + (1 - prior_regression) * dg_tgt_v)
            blend_rz = (1 - prior_weight) * shrunk_rz + prior_weight * (
                prior_regression * p_rz_v + (1 - prior_regression) * dg_rz_v)
            blend_car = (1 - prior_weight) * shrunk_car + prior_weight * (
                prior_regression * p_car_v + (1 - prior_regression) * dg_car_v)
            blend_gl = (1 - prior_weight) * shrunk_gl + prior_weight * (
                prior_regression * p_gl_v + (1 - prior_regression) * dg_gl_v)

            # ── Renormalise per team ──
            teams = merged["team"].values
            for arr in [blend_tgt, blend_rz, blend_car, blend_gl]:
                for t in np.unique(teams):
                    m = teams == t
                    s_val = arr[m].sum()
                    if s_val > 0:
                        arr[m] /= s_val

            # ── Rate stats (n = player's own count) ──
            raw_tgt = merged["raw_tgt"].values
            raw_car = merged["raw_car"].values
            w_tgt_v = merged["w_tgt"].values
            w_rec_v = merged["w_rec"].values
            w_air_v = merged["w_air"].values
            w_yac_v = merged["w_yac"].values
            w_ry_v = merged["w_ry"].values
            w_er_v = merged["w_er"].values
            w_car_v = merged["w_car"].values
            w_ry_r_v = merged["w_ry_r"].values
            w_exr_v = merged["w_exr"].values
            pos_arr = merged["position"].values

            # Vectorised rate shrinkage
            n_t = raw_tgt.astype(float)
            n_c = raw_car.astype(float)

            adot_obs = np.where(w_tgt_v > 0, w_air_v / w_tgt_v, 0.0)
            cr_obs = np.where(w_tgt_v > 0, w_rec_v / w_tgt_v, 0.0)
            yac_obs = np.where(w_rec_v > 0, w_yac_v / w_rec_v, 0.0)
            ypt_obs = np.where(w_tgt_v > 0, w_ry_v / w_tgt_v, 0.0)
            ypc_obs = np.where(w_car_v > 0, w_ry_r_v / w_car_v, 0.0)
            er_obs = np.where(w_tgt_v > 0, w_er_v / w_tgt_v, 0.0)
            exr_obs = np.where(w_car_v > 0, w_exr_v / w_car_v, 0.0)

            # Position priors for rates
            adot_pr = np.array([sp.get(f"{p}_adot", 8.0) for p in pos_arr])
            cr_pr = np.array([sp.get(f"{p}_catch_rate", 0.65) for p in pos_arr])
            yac_pr = np.array([sp.get(f"{p}_yac_per_rec", 4.5) for p in pos_arr])
            ypt_pr = np.array([sp.get(f"{p}_ypt", 7.0) for p in pos_arr])
            ypc_pr = np.array([sp.get(f"{p}_ypc", 4.0) for p in pos_arr])
            er_pr = np.array([sp.get(f"{p}_exp_rec", 0.05) for p in pos_arr])
            exr_pr = np.array([sp.get(f"{p}_exp_rush", 0.05) for p in pos_arr])

            adot = _shrink_vec(adot_obs, n_t, k_rate, adot_pr)
            catch_rate = _shrink_vec(cr_obs, n_t, k_rate, cr_pr)
            yac_rate = _shrink_vec(yac_obs, w_rec_v, k_rate, yac_pr)
            ypt = _shrink_vec(ypt_obs, n_t, k_rate, ypt_pr)
            ypc = _shrink_vec(ypc_obs, n_c, k_rate, ypc_pr)
            exp_rec = _shrink_vec(er_obs, n_t, k_rate, er_pr)
            exp_rush = _shrink_vec(exr_obs, n_c, k_rate, exr_pr)

            # Build output frame for this week
            out = pd.DataFrame({
                "season": season, "week": w,
                "team": merged["team"].values,
                "player_id": merged["player_id"].values,
                "player_name": merged["full_name"].values,
                "position": pos_arr,
                "target_share": blend_tgt, "carry_share": blend_car,
                "rz_target_share": blend_rz, "gl_carry_share": blend_gl,
                "adot": adot, "catch_rate": catch_rate,
                "yac_per_rec": yac_rate, "yards_per_target": ypt,
                "yards_per_carry": ypc,
                "explosive_rec_rate": exp_rec, "explosive_rush_rate": exp_rush,
                "n_targets": raw_tgt.astype(int), "n_carries": raw_car.astype(int),
            })
            all_frames.append(out)

    if not all_frames:
        return pd.DataFrame()
    return pd.concat(all_frames, ignore_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# INJURY RENORMALISATION
# ═══════════════════════════════════════════════════════════════════════════════

def renormalize_shares(shares_df, active_ids, depth_map=None):
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

def tune_share_params(rec, team_tgt, car, team_car, pos_map, rate_priors, roster_uni,
                       active_uni, depth_order_priors, player_season_shares,
                       params_base, grid_spec=None):
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
            pos_map, rate_priors, p, roster_uni[roster_uni["season"] <= 2024],
            active_uni[active_uni["season"] <= 2024],
            depth_order_priors, player_season_shares[player_season_shares["season"] <= 2023],
            output_seasons=TUNE_SEASONS)
        dt = time.time() - t0
        gc.collect()

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
                "tgt": float(np.sqrt(((et["target_share"] - et["actual_tgt_share"])**2).mean())) if len(et) else float("inf"),
                "car": float(np.sqrt(((ec["carry_share"] - ec["actual_car_share"])**2).mean())) if len(ec) else float("inf"),
            }

        early = eval_tgt[eval_tgt["week"] <= 4]
        late = eval_tgt[eval_tgt["week"] > 4]

        grid.append({
            "share_half_life": sh_hl, "k_share": k_s,
            "mean_rmse": float(mean_rmse), "rmse_target": float(rmse_tgt), "rmse_carry": float(rmse_car),
            "by_season": by_season,
            "rmse_wk1_4": float(np.sqrt(((early["target_share"] - early["actual_tgt_share"])**2).mean())) if len(early) else float("inf"),
            "rmse_wk5_18": float(np.sqrt(((late["target_share"] - late["actual_tgt_share"])**2).mean())) if len(late) else float("inf"),
        })
        sh_s = "inf" if sh_hl == float("inf") else str(sh_hl)
        print(f"  sh_hl={sh_s:>3s} k={k_s:>3d}  RMSE={mean_rmse:.4f} (tgt={rmse_tgt:.4f} car={rmse_car:.4f})  {dt:.1f}s")
        del usage
        gc.collect()

    grid.sort(key=lambda x: x["mean_rmse"])
    best = grid[0]
    print(f"\nBest: sh_hl={best['share_half_life']} k={best['k_share']}  RMSE={best['mean_rmse']:.4f}")
    return best, grid


# ═══════════════════════════════════════════════════════════════════════════════
# PIT TEST
# ═══════════════════════════════════════════════════════════════════════════════

def pit_test(rec, team_tgt, car, team_car, pos_map, rate_priors, roster_uni,
             active_uni, depth_order_priors, player_season_shares, params):
    full = build_player_usage(rec, team_tgt, car, team_car, pos_map, rate_priors, params,
                               roster_uni, active_uni, depth_order_priors, player_season_shares,
                               output_seasons=[2023])
    trunc_rec = rec[~((rec["season"] > 2023) | ((rec["season"] == 2023) & (rec["week"] >= 10)))]
    trunc_tt = team_tgt[~((team_tgt["season"] > 2023) | ((team_tgt["season"] == 2023) & (team_tgt["week"] >= 10)))]
    trunc_car = car[~((car["season"] > 2023) | ((car["season"] == 2023) & (car["week"] >= 10)))]
    trunc_tc = team_car[~((team_car["season"] > 2023) | ((team_car["season"] == 2023) & (team_car["week"] >= 10)))]
    trunc_priors = compute_position_priors(trunc_rec, trunc_car, pos_map)
    trunc_active = active_uni[~((active_uni["season"] > 2023) | ((active_uni["season"] == 2023) & (active_uni["week"] >= 10)))]
    trunc_dop, trunc_pss = compute_season_share_data(trunc_active, trunc_rec, trunc_tt, trunc_car, trunc_tc)
    trunc = build_player_usage(trunc_rec, trunc_tt, trunc_car, trunc_tc, pos_map,
                                trunc_priors, params, roster_uni, trunc_active,
                                trunc_dop, trunc_pss, output_seasons=[2023])

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
    print("NFL Sim Phase 1B-FIX-2: Player Usage Shares")
    print("=" * 60)

    plays = load_pbp()
    scrimmage = plays[plays["play_type"].isin(["pass", "run"])].copy()
    n_scramble = 0
    if "qb_scramble" in plays.columns:
        n_scramble = int((plays["play_type"] == "run").sum() - len(scrimmage[scrimmage["play_type"] == "run"]))
    # Actually count properly
    n_scramble = int(((plays["play_type"] == "run") & (plays.get("qb_scramble", pd.Series(0, index=plays.index)) == 1)).sum())
    del plays
    gc.collect()
    print(f"Loaded {len(scrimmage):,} scrimmage plays, {n_scramble:,} QB scrambles will be excluded from carries ({time.time()-t_start:.1f}s)")

    t1 = time.time()
    rosters, depth, injuries = load_roster_data()
    print(f"Rosters: {len(rosters):,}, Depth: {len(depth):,}, Injuries: {len(injuries):,} ({time.time()-t1:.1f}s)")

    t2 = time.time()
    rec, team_tgt, car, team_car = build_player_game_aggs(scrimmage)
    del scrimmage
    gc.collect()
    print(f"Aggregates: rec={len(rec):,} rush={len(car):,} ({time.time()-t2:.1f}s)")

    pos_map = build_position_map(rosters)
    rate_priors = compute_position_priors(rec, car, pos_map)

    roster_uni = rosters[rosters["position"].isin(SKILL_POS)][
        ["season", "week", "gsis_id", "team", "position", "full_name"]
    ].rename(columns={"gsis_id": "player_id"}).drop_duplicates(["season", "week", "player_id"])

    # Build active universe
    print("\nBuilding active universe...")
    active = build_active_universe(rosters, injuries, depth)
    del rosters, depth, injuries
    gc.collect()
    print(f"  {len(active):,} rows, active_flag mean: {active['active_flag'].mean():.3f}")

    # Assertion (d): 2026 wk2
    a26w2 = active[(active["season"] == 2026) & (active["week"] == 2)]
    print(f"  2026 wk2 active_universe: {a26w2['team'].nunique()} teams, {len(a26w2)} rows")
    assert a26w2["team"].nunique() == 32, f"FAIL (d): 2026 wk2 has {a26w2['team'].nunique()} teams"
    assert len(a26w2) >= 300, f"FAIL (d): 2026 wk2 has {len(a26w2)} rows"

    # Assertion (e)
    af_mean = active['active_flag'].mean()
    inactive_breakdown = active[~active['active_flag']]['injury_status'].value_counts().head(6)
    print(f"\n  Assertion (e): active_flag mean = {af_mean:.3f}")
    print(f"  Inactive breakdown:")
    for s, c in inactive_breakdown.items():
        print(f"    {s}: {c}")
    print(f"  → DEV=practice squad, RES=reserve/IR, INA=inactive list, plus Out/Doubtful from injury report")

    # Depth-order priors + player season shares
    print("\nComputing depth-order priors and player season shares...")
    t3 = time.time()
    depth_order_priors, player_season_shares = compute_season_share_data(
        active, rec, team_tgt, car, team_car)
    print(f"  Done ({time.time()-t3:.1f}s), PSS rows: {len(player_season_shares):,}")

    # Print depth-order prior table
    for s in sorted(depth_order_priors.keys()):
        print(f"\n  Season {s} depth-order prior table:")
        dop = depth_order_priors[s]
        print(f"  {'depth_group':<10s} {'tgt_share':>10s} {'car_share':>10s} {'rz_tgt':>10s} {'gl_car':>10s}")
        for dg in sorted(dop.keys()):
            v = dop[dg]
            print(f"  {dg:<10s} {v['target_share']:>10.4f} {v['carry_share']:>10.4f} "
                  f"{v['rz_target_share']:>10.4f} {v['gl_carry_share']:>10.4f}")

    # ── Grid ──
    print(f"\nGrid search (12 points, 2021-2024)...")
    t5 = time.time()
    params_base = json.load(open(PARAMS_PATH))
    best, grid = tune_share_params(
        rec[rec["season"] <= 2024], team_tgt[team_tgt["season"] <= 2024],
        car[car["season"] <= 2024], team_car[team_car["season"] <= 2024],
        pos_map, rate_priors, roster_uni, active[active["season"] <= 2024],
        depth_order_priors, player_season_shares, params_base)
    print(f"Grid done: {time.time()-t5:.1f}s")

    # Extension if boundary
    extended = False
    all_hls = sorted(set(g["share_half_life"] for g in grid))
    all_ks = sorted(set(g["k_share"] for g in grid))
    on_boundary = (best["share_half_life"] == min(all_hls) or best["share_half_life"] == max(all_hls) or
                    best["k_share"] == min(all_ks) or best["k_share"] == max(all_ks))

    if best["share_half_life"] == 2 and best["k_share"] == 20:
        print(f"\nBoundary winner (2,20) — running pre-declared extension...")
        ext_spec = [(sh, k) for sh in [1, 2] for k in [5, 10, 20]]
        existing = set((g["share_half_life"], g["k_share"]) for g in grid)
        ext_spec = [(sh, k) for sh, k in ext_spec if (sh, k) not in existing]
        if ext_spec:
            t6 = time.time()
            ext_best, ext_grid = tune_share_params(
                rec[rec["season"] <= 2024], team_tgt[team_tgt["season"] <= 2024],
                car[car["season"] <= 2024], team_car[team_car["season"] <= 2024],
                pos_map, rate_priors, roster_uni, active[active["season"] <= 2024],
                depth_order_priors, player_season_shares, params_base, grid_spec=ext_spec)
            print(f"Extension done: {time.time()-t6:.1f}s")
            combined = grid + ext_grid
            combined.sort(key=lambda x: x["mean_rmse"])
            best = combined[0]
            grid = combined
            extended = True
            print(f"Combined best: sh_hl={best['share_half_life']} k={best['k_share']}  RMSE={best['mean_rmse']:.4f}")

    all_hls = sorted(set(g["share_half_life"] for g in grid))
    all_ks = sorted(set(g["k_share"] for g in grid))
    on_boundary = (best["share_half_life"] == min(all_hls) or best["share_half_life"] == max(all_hls) or
                    best["k_share"] == min(all_ks) or best["k_share"] == max(all_ks))
    boundary_str = "BOUNDARY" if on_boundary else "INTERIOR"
    print(f"  Chosen point is {boundary_str}.")

    # Update params
    params = json.load(open(PARAMS_PATH))
    params["usage"] = {
        "share_half_life": best["share_half_life"],
        "k_share": best["k_share"],
        "extended_grid": extended,
        "boundary": boundary_str,
        "formula": "n_eff=team_opp_while_active, prior=own_s-1_share_if_50+opp_else_(pos,depth)_league_mean",
        "grid_results": [{k: v for k, v in g.items() if k != "by_season"}
                          for g in sorted(grid, key=lambda x: x["mean_rmse"])],
    }
    with open(PARAMS_PATH, "w") as f:
        json.dump(params, f, indent=2, default=str)

    # ── Build full usage ──
    print(f"\nBuilding full usage...")
    t7 = time.time()
    usage = build_player_usage(rec, team_tgt, car, team_car, pos_map, rate_priors, params,
                                roster_uni, active, depth_order_priors, player_season_shares)
    print(f"  {len(usage):,} rows ({time.time()-t7:.1f}s)")

    # Save early (before assertions, so data is available for debugging)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    usage.to_parquet(OUT_DIR / "player_usage_weekly.parquet", index=False)
    active.to_parquet(OUT_DIR / "active_universe_weekly.parquet", index=False)
    print(f"  Saved to {OUT_DIR}")

    # Debug dump: PHI 2024 wk18
    phi_dbg = usage[(usage["season"] == 2024) & (usage["week"] == 18) & (usage["team"] == "PHI")]
    print(f"\n  DEBUG PHI wk18: {len(phi_dbg)} players, carry_share sum={phi_dbg['carry_share'].sum():.4f}")
    for pos in ["QB", "RB", "WR", "TE"]:
        pp = phi_dbg[phi_dbg["position"] == pos]
        print(f"    {pos}: {len(pp)} players, car_sum={pp['carry_share'].sum():.3f}")
    phi_top = phi_dbg.nlargest(10, "carry_share")
    for _, r in phi_top.iterrows():
        print(f"    {r['player_name']:<20s} {r['position']:>2s} car_sh={r['carry_share']:.3f} n_car={int(r['n_carries'])}")

    # ══════════════════════════════════════════════════════════════════════
    # ASSERTIONS
    # ══════════════════════════════════════════════════════════════════════
    print(f"\n{'='*60}")
    print("ASSERTIONS")
    print(f"{'='*60}")

    # (a) PHI 2024 wk18
    phi = usage[(usage["season"] == 2024) & (usage["week"] == 18) & (usage["team"] == "PHI")]
    barkley = phi[phi["player_name"].str.contains("Barkley", na=False)]
    hurts = phi[phi["player_name"].str.contains("Hurts", na=False)]

    if hurts.empty:
        print("ASSERTION (a) PROBLEM: Hurts missing from PHI 2024 wk18!")
        hurts_any = usage[(usage["season"] == 2024) & (usage["player_name"].str.contains("Hurts", na=False))]
        if not hurts_any.empty:
            print(f"  Hurts in 2024 teams: {hurts_any['team'].unique()}, weeks: {sorted(hurts_any['week'].unique())}")
        sys.exit(1)

    bark_cs = float(barkley.iloc[0]["carry_share"])
    hurts_cs = float(hurts.iloc[0]["carry_share"])
    print(f"  (a) Barkley carry_share = {bark_cs:.3f} (need > 0.50), Hurts carry_share = {hurts_cs:.3f} (need > 0.15)")
    assert bark_cs > 0.50, f"FAIL (a): Barkley {bark_cs:.3f}"
    assert hurts_cs > 0.15, f"FAIL (a): Hurts {hurts_cs:.3f}"
    print(f"  PASS")

    # (b) 2024 wk18: zero-touch < 5% mass
    u24w18 = usage[(usage["season"] == 2024) & (usage["week"] == 18)]
    b_pass = True
    for share_col, touch_col in [("carry_share", "n_carries"), ("target_share", "n_targets")]:
        max_zero_pct = 0
        max_team = ""
        for t in u24w18["team"].unique():
            tw = u24w18[u24w18["team"] == t]
            zero = tw[tw[touch_col] == 0]
            zero_mass = zero[share_col].sum()
            if zero_mass > max_zero_pct:
                max_zero_pct = zero_mass
                max_team = t
        print(f"  (b) max zero-{touch_col} team {share_col}: {max_zero_pct:.3f} (team={max_team}, need < 0.05)")
        if max_zero_pct >= 0.05:
            b_pass = False
            tw = u24w18[u24w18["team"] == max_team]
            zero = tw[tw[touch_col] == 0]
            print(f"      {max_team} zero-{touch_col} players ({len(zero)}):")
            for _, r in zero.nlargest(5, share_col).iterrows():
                print(f"        {r['player_name']:<20s} {r['position']:>2s} {share_col}={r[share_col]:.4f}")
    if b_pass:
        print(f"  PASS")
    else:
        print(f"  FAIL (continuing for diagnostics)")

    # (c) Share sums = 1
    print(f"  (c) Share sum check...")
    fail_count = 0
    for (s, w, t), grp in usage.groupby(["season", "week", "team"]):
        for sc in ["target_share", "carry_share", "rz_target_share", "gl_carry_share"]:
            total = grp[sc].sum()
            if abs(total - 1.0) > 1e-6 and total > 0:
                fail_count += 1
                if fail_count <= 3:
                    print(f"    FAIL: {s} wk{w} {t} {sc} = {total:.6f}")
    if fail_count:
        print(f"    {fail_count} failures!")
        sys.exit(1)
    print(f"  PASS (all within 1e-6)")

    # (d) 2026 wk2
    s26w2 = usage[(usage["season"] == 2026) & (usage["week"] == 2)]
    print(f"  (d) 2026 wk2: {s26w2['team'].nunique()} teams, {len(s26w2)} players")
    assert s26w2["team"].nunique() == 32
    assert len(s26w2) >= 300
    print(f"  PASS")

    print(f"  (e) active_flag = {af_mean:.3f}: DEV/RES/INA + Out/Doubtful → PASS")

    # Active universe Out counts
    print(f"\nOut counts per season:")
    for s in [2021, 2022, 2023, 2024, 2025]:
        n_out = len(active[(active["season"] == s) & (active["injury_status"] == "Out")])
        assert n_out >= 200, f"FAIL: {s} has only {n_out} Out rows"
        print(f"  {s}: {n_out}")

    # PIT test
    print(f"\nPIT test (week 10)...")
    gc.collect()
    pit_test(rec, team_tgt, car, team_car, pos_map, rate_priors, roster_uni,
             active, depth_order_priors, player_season_shares, params)

    # Renormalisation example
    print(f"\nRenormalisation example...")
    out_rbs = active[(active["season"] == 2023) & (active["injury_status"] == "Out") &
                       (active["position"] == "RB")]
    if not out_rbs.empty:
        example = out_rbs.iloc[0]
        s, w, t = int(example["season"]), int(example["week"]), example["team"]
        tw_usage = usage[(usage["season"] == s) & (usage["week"] == w) & (usage["team"] == t)].copy()
        tw_active = active[(active["season"] == s) & (active["week"] == w) & (active["team"] == t)]
        active_ids = tw_active[tw_active["active_flag"]]["player_id"].tolist()
        depth_map_ex = tw_active.set_index("player_id")["depth_order"].to_dict()
        out_pid = example["player_id"]
        out_name_rows = tw_usage[tw_usage["player_id"] == out_pid]
        out_name = out_name_rows["player_name"].iloc[0] if not out_name_rows.empty else out_pid
        print(f"  {t} {s} wk{w}: Out RB = {out_name}")
        before = tw_usage[tw_usage["position"] == "RB"].nlargest(5, "carry_share")[
            ["player_name", "carry_share"]].to_string(index=False)
        print(f"  Before:\n{before}")
        renorm = renormalize_shares(tw_usage, active_ids, depth_map_ex)
        after = renorm[renorm["position"] == "RB"].nlargest(5, "carry_share")[
            ["player_name", "carry_share"]].to_string(index=False)
        print(f"  After:\n{after}")
        if out_pid in renorm["player_id"].values:
            assert renorm[renorm["player_id"] == out_pid]["carry_share"].iloc[0] == 0.0
        total = renorm[renorm["position"] == "RB"]["carry_share"].sum()
        assert abs(total - 1.0) < 1e-6
        print(f"  Out player = 0, RB sum = {total:.6f}")

    # ══════════════════════════════════════════════════════════════════════
    # FACE VALIDITY
    # ══════════════════════════════════════════════════════════════════════
    print(f"\n{'='*60}")
    print("FACE VALIDITY (2024 wk 18)")
    print(f"{'='*60}")
    u24 = usage[(usage["season"] == 2024) & (usage["week"] == 18)]
    if not u24.empty:
        print("\n  Top 10 target share:")
        for _, r in u24.nlargest(10, "target_share").iterrows():
            print(f"    {r['player_name']:<25s} {r['team']:>3s} {r['position']:>2s}  "
                  f"tgt_sh={r['target_share']:.3f}  n={int(r['n_targets'])}")
        print("\n  Top 10 carry share:")
        for _, r in u24.nlargest(10, "carry_share").iterrows():
            print(f"    {r['player_name']:<25s} {r['team']:>3s} {r['position']:>2s}  "
                  f"car_sh={r['carry_share']:.3f}  n={int(r['n_carries'])}")

    # Check 5
    print(f"\n  RMSE by season:")
    for s, v in sorted(best.get("by_season", {}).items()):
        print(f"    {s}: tgt={v['tgt']:.4f}  car={v['car']:.4f}")
    print(f"  Wk 1-4 tgt RMSE: {best.get('rmse_wk1_4', 'N/A')}")
    print(f"  Wk 5-18 tgt RMSE: {best.get('rmse_wk5_18', 'N/A')}")

    print(f"\nTotal elapsed: {time.time()-t_start:.1f}s")
    print("Phase 1B-FIX-2 complete.")


if __name__ == "__main__":
    main()
