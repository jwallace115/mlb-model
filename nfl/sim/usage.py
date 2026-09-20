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
    prior    = p's own s-1 aggregate share (opp-weighted across all depth
               groups) if >= 50 team opp while active in s-1;
               else league mean share for (position, depth_order) from s-1.
               depth_order from new-schema snapshots with dt < week's first
               kickoff only (D59). NaN depth → position-only league prior.
    shrunk   = (n_eff * obs + k_share * prior) / (n_eff + k_share)
    pw_eff   = prior_weight * k_share / (n_eff + k_share)   [decays with evidence]
    blend    = (1 - pw_eff) * shrunk + pw_eff * (prior_regression * prior
               + (1 - prior_regression) * league_mean_for_position_depth)
  Then renormalise each share within (season, week, team) to sum to 1.
  Decay weight per game = 0.5**((w-1-game_week)/share_half_life).

Rate attributes (adot, catch_rate, yac, ypt, ypc, explosive rates) keep n = player's
own targets or carries — that IS the right sample size for a rate.

Carries EXCLUDE qb_scramble and qb_kneel (designed runs + QB sneaks only).
"""

import argparse, json, os, subprocess, sys, time, gc
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
PBP_DIR = ROOT / "nfl" / "data" / "pbp"
OUT_DIR = Path(os.environ.get("NFL_USAGE_OUT_DIR",
               str(ROOT / "nfl" / "data" / "sim" / "ratings")))
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
            "rusher_player_name", "receiver_player_name",
            "passer_player_name"]


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
    depth_cols = ["season", "week", "club_code", "gsis_id", "position", "depth_team",
                   "pos_rank", "pos_abb", "team", "dt"]
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
# STARTING-QB IDENTIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

def derive_starting_qbs(depth, plays, active_universe=None):
    """
    Identify starting QB per (season, week, team).

    Priority:
    1. Per-week depth chart (old schema, depth_team=1, 2020-2024)
    2. Most recent previous game's leading passer (search back ≤3 weeks)
    3. Static depth chart snapshot (new schema, pos_rank=1, current season only)

    Roster-at-game-time: a QB is a candidate only if on that team's
    roster/active universe for that week.

    Returns: dict[(season, week, team)] -> {'gsis_id': str, 'source': str}
    """
    starting = {}

    # Build roster lookup for validation: (season, week, team, player_id) → True
    roster_set = set()
    if active_universe is not None and not active_universe.empty:
        for cols in active_universe[["season", "week", "team", "player_id"]].itertuples(index=False):
            roster_set.add((int(cols[0]), int(cols[1]), cols[2], cols[3]))

    def _on_roster(s, w, team, gsis_id):
        if not roster_set:
            return True  # no roster data → skip validation
        return (s, w, team, gsis_id) in roster_set

    # Layer 1: Old schema per-week depth charts (2020-2024)
    if "depth_team" in depth.columns and "season" in depth.columns:
        old_qb = depth[
            (depth["position"] == "QB")
            & depth["season"].notna()
            & depth["depth_team"].notna()
        ].copy()
        old_qb["depth_team"] = pd.to_numeric(old_qb["depth_team"], errors="coerce")
        qb1 = old_qb[old_qb["depth_team"] == 1].drop_duplicates(
            ["season", "week", "club_code"], keep="first"
        )
        for _, r in qb1.iterrows():
            s = int(r["season"])
            w = r["week"]
            if pd.isna(w):
                continue
            w = int(w)
            if _on_roster(s, w, r["club_code"], r["gsis_id"]):
                starting[(s, w, r["club_code"])] = {
                    "gsis_id": r["gsis_id"],
                    "source": "depth_chart",
                }

    # Layer 2: PBP leading passer from the team's most recent previous game.
    # Searches back up to 3 weeks to cross bye weeks.
    if plays is not None:
        passes = plays[
            (plays["play_type"] == "pass") & plays["passer_player_id"].notna()
        ]
        if not passes.empty:
            leader = (
                passes.groupby(
                    ["season", "week", "posteam", "passer_player_id"], observed=True
                )
                .size()
                .reset_index(name="att")
            )
            leader = leader.sort_values("att", ascending=False).drop_duplicates(
                ["season", "week", "posteam"]
            )
            # Build a lookup: (season, team) -> list of (week, gsis_id) sorted by week desc
            team_passers = {}
            for _, r in leader.iterrows():
                key = (int(r["season"]), r["posteam"])
                team_passers.setdefault(key, []).append(
                    (int(r["week"]), r["passer_player_id"]))
            for k in team_passers:
                team_passers[k].sort(key=lambda x: -x[0])

            # For each team-week, find the most recent game within 3 weeks back
            for (s, team), games_list in team_passers.items():
                weeks_played = [w for w, _ in games_list]
                max_week = max(weeks_played)
                for target_w in range(2, max_week + 2):  # fill week 2 through max+1
                    key = (s, target_w, team)
                    if key in starting:
                        continue
                    # Search back up to 3 weeks
                    for lookback in range(1, 4):
                        prev_w = target_w - lookback
                        for gw, gsis_id in games_list:
                            if gw == prev_w:
                                if _on_roster(s, target_w, team, gsis_id):
                                    starting[key] = {
                                        "gsis_id": gsis_id,
                                        "source": "prev_game_passer",
                                    }
                                break
                        if key in starting:
                            break

    # Layer 3: Static depth chart (new schema, prospective only: current season).
    # D59/5J: use the latest rank-1 QB snapshot per team with dt STRICTLY
    # BEFORE that week's first kickoff, same rule as depth_order layer.
    current_season = max(OUTPUT_SEASONS)
    for s in sorted(OUTPUT_SEASONS, reverse=True):
        if (PBP_DIR / f"pbp_{s}.parquet").exists():
            current_season = s
            break

    n_layer3_unset = 0
    n_layer3_set = 0
    if "pos_rank" in depth.columns:
        new_qb = depth[
            (depth.get("pos_abb", pd.Series(dtype=str)) == "QB")
            & depth["pos_rank"].notna()
        ].copy()
        if not new_qb.empty:
            new_qb["pos_rank"] = pd.to_numeric(new_qb["pos_rank"], errors="coerce")
            new_qb["_dt"] = pd.to_datetime(new_qb["dt"], errors="coerce", utc=True)
            qb1_all = new_qb[new_qb["pos_rank"] == 1].copy()

            # Build first-kickoff lookup: PBP game_date, then nflverse schedule
            _l3_kickoff = {}
            for s in OUTPUT_SEASONS:
                if s < current_season:
                    continue
                pbp_path = PBP_DIR / f"pbp_{int(s)}.parquet"
                if pbp_path.exists():
                    gdf = pd.read_parquet(pbp_path, columns=["season", "week", "game_date"]).drop_duplicates(["season", "week", "game_date"])
                    gdf["game_date"] = pd.to_datetime(gdf["game_date"], errors="coerce", utc=True)
                    for w in gdf["week"].unique():
                        wg = gdf[gdf["week"] == w]
                        _l3_kickoff[(int(s), int(w))] = wg["game_date"].min()
            # For weeks with no PBP (future), use nflverse schedule
            try:
                import nflreadpy
                for s in OUTPUT_SEASONS:
                    if s < current_season:
                        continue
                    sched = nflreadpy.load_schedules([s]).to_pandas()
                    sched["_ko"] = pd.to_datetime(sched["gameday"].astype(str) + " " + sched["gametime"].fillna("13:00"),
                                                  errors="coerce", utc=True)
                    for w in sched["week"].unique():
                        key = (int(s), int(w))
                        if key not in _l3_kickoff:
                            wg = sched[sched["week"] == w]
                            ko = wg["_ko"].min()
                            if pd.notna(ko):
                                _l3_kickoff[key] = ko
            except Exception:
                pass  # nflreadpy not available; PBP-only kickoffs

            for s in OUTPUT_SEASONS:
                if s < current_season:
                    continue
                for w in range(1, 23):
                    kickoff = _l3_kickoff.get((s, w))
                    if kickoff is None or pd.isna(kickoff):
                        continue
                    # Latest rank-1 QB per team with dt < kickoff
                    eligible = qb1_all[qb1_all["_dt"] < kickoff]
                    if eligible.empty:
                        continue
                    week_qb1 = (
                        eligible.sort_values("_dt", ascending=False, na_position="last")
                        .drop_duplicates("team", keep="first")
                    )
                    for _, r in week_qb1.iterrows():
                        key = (s, w, r["team"])
                        if key not in starting:
                            starting[key] = {
                                "gsis_id": r["gsis_id"],
                                "source": "depth_chart",
                            }
                            n_layer3_set += 1

    # Count team-weeks left unset (no eligible snapshot before kickoff)
    for s in OUTPUT_SEASONS:
        if s < current_season:
            continue
        for w in range(1, 23):
            for team in depth["team"].unique() if "team" in depth.columns else []:
                if (s, w, team) not in starting:
                    n_layer3_unset += 1
    if n_layer3_unset:
        print(f"  derive_starting_qbs: {n_layer3_unset} team-weeks unset after layer 3 "
              f"(no eligible snapshot before kickoff)")
    if n_layer3_set:
        print(f"  derive_starting_qbs: layer 3 set {n_layer3_set} team-weeks")

    return starting


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

    # Depth order — handle both old schema (depth_team, club_code, season/week) and
    # new schema (pos_rank, team, gsis_id — from nflreadpy 2025+)
    base["depth_order"] = np.nan

    # Old schema (2020-2024): has season, week, club_code, depth_team
    if "depth_team" in depth.columns and "season" in depth.columns:
        old = depth[depth["position"].isin(SKILL_POS) & depth["season"].notna()].copy()
        old["depth_team"] = pd.to_numeric(old["depth_team"], errors="coerce")
        old = old.groupby(["season", "week", "club_code", "gsis_id"], observed=True)[
            "depth_team"].min().reset_index()
        old = old.rename(columns={"club_code": "team", "gsis_id": "player_id", "depth_team": "depth_order"})
        base = base.drop(columns="depth_order").merge(
            old[["season", "week", "team", "player_id", "depth_order"]],
            on=["season", "week", "team", "player_id"], how="left")

    # New schema (2025+): has pos_rank, team, gsis_id, pos_abb, dt.
    # D59: only use snapshots with dt strictly before the week's first kickoff
    # to prevent future depth-chart data from leaking into historical seasons.
    if "pos_rank" in depth.columns and "gsis_id" in depth.columns:
        pos_filter = depth["pos_abb"].isin(["QB", "RB", "WR", "TE"]) if "pos_abb" in depth.columns else pd.Series(True, index=depth.index)
        new_all = depth[pos_filter].copy()
        new_all["_depth"] = pd.to_numeric(new_all["pos_rank"], errors="coerce")
        new_all["_dt"] = pd.to_datetime(new_all["dt"], errors="coerce", utc=True)

        # Build first-kickoff lookup from PBP game_date
        kickoff_by_sw = {}
        for s in base["season"].unique():
            pbp_path = PBP_DIR / f"pbp_{int(s)}.parquet"
            if not pbp_path.exists():
                continue
            gdf = pd.read_parquet(pbp_path, columns=["season", "week", "game_date"]).drop_duplicates(["season", "week", "game_date"])
            gdf["game_date"] = pd.to_datetime(gdf["game_date"], errors="coerce", utc=True)
            for w in gdf["week"].unique():
                wg = gdf[gdf["week"] == w]
                kickoff_by_sw[(int(s), int(w))] = wg["game_date"].min()

        # Per (season, week): take the latest snapshot per (team, player_id)
        # with dt strictly before the first kickoff of that week.
        new_depths = []
        for (s, w), grp in base.groupby(["season", "week"]):
            kickoff = kickoff_by_sw.get((int(s), int(w)))
            if kickoff is None or pd.isna(kickoff):
                continue  # no PBP → no new-schema depth
            eligible = new_all[new_all["_dt"] < kickoff]
            if eligible.empty:
                continue
            # Latest snapshot per (team, player_id), take min pos_rank
            latest = (eligible.sort_values("_dt", ascending=False)
                      .drop_duplicates(["team", "gsis_id"], keep="first"))
            chunk = latest[["team", "gsis_id", "_depth"]].copy()
            chunk = chunk.rename(columns={"gsis_id": "player_id", "_depth": "new_depth"})
            chunk["season"] = s
            chunk["week"] = w
            new_depths.append(chunk)

        if new_depths:
            nd = pd.concat(new_depths, ignore_index=True)
            base = base.merge(nd, on=["season", "week", "team", "player_id"], how="left")
            fill_mask = base["depth_order"].isna() & base["new_depth"].notna()
            base.loc[fill_mask, "depth_order"] = base.loc[fill_mask, "new_depth"]
            base = base.drop(columns="new_depth")
        # Rows with no eligible snapshot keep depth_order NaN → position-only prior

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
                        player_season_shares, output_seasons=None, starting_qbs=None):
    if "usage" not in params:
        raise ValueError(
            "params_v1.json missing required 'usage' block — "
            "write share_half_life and k_share, then rerun"
        )
    sh_hl = params["usage"]["share_half_life"]
    k_share = params["usage"]["k_share"]
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
            # Share universe = 53-man roster (ACT or INA status) for this week.
            # Team-specific: a player must be on THAT team's roster, not just any team.
            act_roster = w_roster_full[w_roster_full["status"].isin({"ACT", "INA"})]
            act_roster_by_team = {}
            for t_name, t_grp in act_roster.groupby("team"):
                act_roster_by_team[t_name] = set(t_grp["player_id"].unique())
            act_roster_pids = set(act_roster["player_id"].unique())

            week_roster = s_roster[s_roster["week"] == w] if "week" in s_roster.columns else s_roster
            if week_roster.empty:
                week_roster = s_roster
            roster_pids = week_roster[["player_id", "team", "position", "full_name"]].drop_duplicates("player_id")
            roster_pids = roster_pids[roster_pids["position"].isin(SKILL_POS)]
            roster_pids = roster_pids[roster_pids["player_id"].isin(act_roster_pids)]

            # D60: Key on (player_id, team) not player_id alone.
            # A traded player with old-team PBP history still gets a
            # new-team row on his first week with the new team.
            if not merged.empty:
                existing_tp = set(zip(merged["player_id"], merged["team"]))
                new_roster = roster_pids[
                    ~roster_pids.apply(
                        lambda r: (r["player_id"], r["team"]) in existing_tp,
                        axis=1)]
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
            # Filter to team-specific roster: player must be on THAT team's
            # roster for this week (prevents cross-team leakage via PBP history).
            roster_tp = set()
            for t_name, pid_set in act_roster_by_team.items():
                for pid in pid_set:
                    roster_tp.add((t_name, pid))
            keep_mask = pd.Series(
                [(t, p) in roster_tp for t, p in zip(merged["team"], merged["player_id"])],
                index=merged.index)
            merged = merged[keep_mask]
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

            # D61: Player's own s-1 aggregate prior (across all depth groups).
            # If player was on multiple teams, take the one with the most opp.
            if not pss.empty:
                # Aggregate across depth groups: opp-weighted mean share
                _p = pss.copy()
                _p["_w_tgt"] = _p["tgt_share"] * _p["opp_tgt"]
                _p["_w_car"] = _p["car_share"] * _p["opp_car"]
                _p["_w_rz"] = _p["rz_tgt_share"] * _p["opp_tgt"]
                _p["_w_gl"] = _p["gl_car_share"] * _p["opp_car"]
                p_agg = _p.groupby(["player_id", "team"]).agg(
                    opp_tgt=("opp_tgt", "sum"), opp_car=("opp_car", "sum"),
                    _w_tgt=("_w_tgt", "sum"), _w_car=("_w_car", "sum"),
                    _w_rz=("_w_rz", "sum"), _w_gl=("_w_gl", "sum"),
                ).reset_index()
                p_agg["tgt_share"] = np.where(p_agg["opp_tgt"] > 0, p_agg["_w_tgt"] / p_agg["opp_tgt"], 0.0)
                p_agg["car_share"] = np.where(p_agg["opp_car"] > 0, p_agg["_w_car"] / p_agg["opp_car"], 0.0)
                p_agg["rz_tgt_share"] = np.where(p_agg["opp_tgt"] > 0, p_agg["_w_rz"] / p_agg["opp_tgt"], 0.0)
                p_agg["gl_car_share"] = np.where(p_agg["opp_car"] > 0, p_agg["_w_gl"] / p_agg["opp_car"], 0.0)
                # Dedup across teams: keep the one with the most total opp
                p_agg["_total_opp"] = p_agg["opp_tgt"] + p_agg["opp_car"]
                p_prev = (p_agg.sort_values("_total_opp", ascending=False)
                          .drop_duplicates("player_id")
                          .drop(columns=["_total_opp", "_w_tgt", "_w_car", "_w_rz", "_w_gl", "team"]))
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

            # Blend: weight the prior into the estimate. The prior_weight
            # decays with evidence (n_eff / k_share) to avoid adding a fixed
            # floor to shares that must sum to 1.
            pw_eff_tgt = prior_weight * k_share / (opp_tgt + k_share)
            pw_eff_rz = prior_weight * k_share / (opp_rz + k_share)
            pw_eff_car = prior_weight * k_share / (opp_car + k_share)
            pw_eff_gl = prior_weight * k_share / (opp_gl + k_share)

            blend_tgt = (1 - pw_eff_tgt) * shrunk_tgt + pw_eff_tgt * (
                prior_regression * p_tgt_v + (1 - prior_regression) * dg_tgt_v)
            blend_rz = (1 - pw_eff_rz) * shrunk_rz + pw_eff_rz * (
                prior_regression * p_rz_v + (1 - prior_regression) * dg_rz_v)
            blend_car = (1 - pw_eff_car) * shrunk_car + pw_eff_car * (
                prior_regression * p_car_v + (1 - prior_regression) * dg_car_v)
            blend_gl = (1 - pw_eff_gl) * shrunk_gl + pw_eff_gl * (
                prior_regression * p_gl_v + (1 - prior_regression) * dg_gl_v)

            # ── Starting-QB allocation ──
            raw_tgt_arr = merged["raw_tgt"].values if "raw_tgt" in merged.columns else np.zeros(len(merged))
            raw_car_arr = merged["raw_car"].values if "raw_car" in merged.columns else np.zeros(len(merged))

            is_qb = merged["position"].values == "QB"
            is_starter = np.zeros(len(merged), dtype=bool)
            no_starter_teams = []
            if starting_qbs is not None:
                pids = merged["player_id"].values
                teams_arr_qb = merged["team"].values
                for i in range(len(merged)):
                    if is_qb[i]:
                        sq = starting_qbs.get((season, w, teams_arr_qb[i]))
                        if sq and sq["gsis_id"] == pids[i]:
                            is_starter[i] = True

                # D54: if flagged starter is Out/inactive, re-flag to first
                # active QB by depth_order. No touches heuristic.
                w_act = s_active[(s_active["week"] == w) & (s_active["active_flag"])]
                act_set = set(w_act["player_id"].values) if not w_act.empty else set()
                depths = merged["depth_order"].values

                for t in np.unique(teams_arr_qb):
                    team_qb_mask = is_qb & (teams_arr_qb == t)
                    if not team_qb_mask.any():
                        continue
                    ok = False
                    for i in np.where(team_qb_mask)[0]:
                        if is_starter[i] and pids[i] in act_set:
                            ok = True
                            break
                    if ok:
                        continue
                    # Clear all, pick first active QB by depth_order
                    is_starter[team_qb_mask] = False
                    qb_idx_list = np.where(team_qb_mask)[0].tolist()
                    act_qbs = [qi for qi in qb_idx_list if pids[qi] in act_set]
                    if act_qbs:
                        best = min(act_qbs,
                                   key=lambda qi: depths[qi] if pd.notna(depths[qi]) else 99)
                        is_starter[best] = True
                    else:
                        no_starter_teams.append(t)

                if no_starter_teams:
                    print(f"  WARNING: {season} wk{w}: no active QB for {no_starter_teams}")

            backup_qb = is_qb & ~is_starter

            # Backup QBs: observed share only (no prior), zero if no touches
            if backup_qb.any():
                for arr, obs_arr, opp_arr, raw_arr in [
                    (blend_tgt, obs_tgt, opp_tgt, raw_tgt_arr),
                    (blend_rz, obs_rz, opp_rz, raw_tgt_arr),
                    (blend_car, obs_car, opp_car, raw_car_arr),
                    (blend_gl, obs_gl, opp_gl, raw_car_arr),
                ]:
                    arr[backup_qb] = np.where(
                        (raw_arr[backup_qb] > 0) & (opp_arr[backup_qb] > 0),
                        obs_arr[backup_qb],
                        1e-8,
                    )

            # D53: opp==0 players get the D14 prior (already computed by the
            # shrinkage formula above). No 1e-8 override — absence of evidence
            # is not evidence of zero share.

            # Strong evidence override: player was active for team opportunities
            # with 0 own touches → evidence of ~0 share.
            zero_tgt_evidence = (raw_tgt_arr == 0) & (opp_tgt > 0)
            zero_car_evidence = (raw_car_arr == 0) & (opp_car > 0)
            blend_tgt[zero_tgt_evidence] = 1e-8
            blend_rz[zero_tgt_evidence] = 1e-8
            blend_car[zero_car_evidence] = 1e-8
            blend_gl[zero_car_evidence] = 1e-8

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
                "is_starting_qb": is_starter,
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

def _load_common():
    """Load data shared by build and tune paths. Returns a dict."""
    t_start = time.time()
    plays = load_pbp()
    scrimmage = plays[plays["play_type"].isin(["pass", "run"])].copy()
    n_scramble = int(((plays["play_type"] == "run") & (plays.get("qb_scramble", pd.Series(0, index=plays.index)) == 1)).sum())
    del plays
    gc.collect()
    print(f"Loaded {len(scrimmage):,} scrimmage plays, {n_scramble:,} QB scrambles excluded ({time.time()-t_start:.1f}s)")

    rosters, depth, injuries = load_roster_data()
    print(f"Rosters: {len(rosters):,}, Depth: {len(depth):,}, Injuries: {len(injuries):,}")

    rec, team_tgt, car, team_car = build_player_game_aggs(scrimmage)
    print(f"Aggregates: rec={len(rec):,} rush={len(car):,}")

    pos_map = build_position_map(rosters)
    rate_priors = compute_position_priors(rec, car, pos_map)
    roster_uni = rosters[rosters["position"].isin(SKILL_POS)][
        ["season", "week", "gsis_id", "team", "position", "full_name"]
    ].rename(columns={"gsis_id": "player_id"}).drop_duplicates(["season", "week", "player_id"])

    print("Building active universe...")
    active = build_active_universe(rosters, injuries, depth)
    print(f"  {len(active):,} rows, active_flag mean: {active['active_flag'].mean():.3f}")

    starting_qbs = derive_starting_qbs(depth, scrimmage, active_universe=active)
    n_dc = sum(1 for v in starting_qbs.values() if v["source"] == "depth_chart")
    n_pbp = sum(1 for v in starting_qbs.values() if v["source"] == "prev_game_passer")
    print(f"Starting QBs: {len(starting_qbs)} entries ({n_dc} depth_chart, {n_pbp} prev_game_passer)")

    del scrimmage, rosters, depth, injuries; gc.collect()

    print("Computing depth-order priors and player season shares...")
    depth_order_priors, player_season_shares = compute_season_share_data(
        active, rec, team_tgt, car, team_car)
    print(f"  PSS rows: {len(player_season_shares):,}")

    return {
        "rec": rec, "team_tgt": team_tgt, "car": car, "team_car": team_car,
        "pos_map": pos_map, "rate_priors": rate_priors,
        "roster_uni": roster_uni, "active": active,
        "depth_order_priors": depth_order_priors,
        "player_season_shares": player_season_shares,
        "starting_qbs": starting_qbs,
    }


def main():
    parser = argparse.ArgumentParser(description="NFL usage builder")
    parser.add_argument("--tune", action="store_true",
                        help="Run the grid search on 2021-2024 and write the "
                             "usage block to params_v1.json (then exit)")
    args = parser.parse_args()

    t_start = time.time()
    print("NFL Sim: Player Usage Shares")
    print("=" * 60)

    d = _load_common()
    rec, team_tgt, car, team_car = d["rec"], d["team_tgt"], d["car"], d["team_car"]
    pos_map, rate_priors = d["pos_map"], d["rate_priors"]
    roster_uni, active = d["roster_uni"], d["active"]
    depth_order_priors = d["depth_order_priors"]
    player_season_shares = d["player_season_shares"]
    starting_qbs = d["starting_qbs"]

    # ── Read frozen params (always required) ──
    params = json.load(open(PARAMS_PATH))

    if args.tune:
        # ── TUNE MODE ──────────────────────────────────────────────────
        print(f"\n--tune: grid search (12 points, 2021-2024)...")
        t5 = time.time()
        best, grid = tune_share_params(
            rec[rec["season"] <= 2024], team_tgt[team_tgt["season"] <= 2024],
            car[car["season"] <= 2024], team_car[team_car["season"] <= 2024],
            pos_map, rate_priors, roster_uni, active[active["season"] <= 2024],
            depth_order_priors, player_season_shares, params)
        print(f"Grid done: {time.time()-t5:.1f}s")

        # Extension if boundary
        extended = False
        if best["share_half_life"] == 2 and best["k_share"] == 20:
            print(f"\nBoundary winner (2,20) — running pre-declared extension...")
            ext_spec = [(sh, k) for sh in [1, 2] for k in [5, 10, 20]]
            existing = set((g["share_half_life"], g["k_share"]) for g in grid)
            ext_spec = [(sh, k) for sh, k in ext_spec if (sh, k) not in existing]
            if ext_spec:
                _, ext_grid = tune_share_params(
                    rec[rec["season"] <= 2024], team_tgt[team_tgt["season"] <= 2024],
                    car[car["season"] <= 2024], team_car[team_car["season"] <= 2024],
                    pos_map, rate_priors, roster_uni, active[active["season"] <= 2024],
                    depth_order_priors, player_season_shares, params, grid_spec=ext_spec)
                combined = grid + ext_grid
                combined.sort(key=lambda x: x["mean_rmse"])
                best = combined[0]
                grid = combined
                extended = True
                print(f"Combined best: sh_hl={best['share_half_life']} k={best['k_share']}  "
                      f"RMSE={best['mean_rmse']:.4f}")

        all_hls = sorted(set(g["share_half_life"] for g in grid))
        all_ks = sorted(set(g["k_share"] for g in grid))
        on_boundary = (best["share_half_life"] == min(all_hls) or best["share_half_life"] == max(all_hls) or
                        best["k_share"] == min(all_ks) or best["k_share"] == max(all_ks))
        boundary_str = "BOUNDARY" if on_boundary else "INTERIOR"

        commit_hash = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True
        ).strip()

        params["usage"] = {
            "share_half_life": best["share_half_life"],
            "k_share": best["k_share"],
            "frozen_at": time.strftime("%Y-%m-%d", time.gmtime()),
            "frozen_commit": commit_hash,
            "extended_grid": extended,
            "boundary": boundary_str,
            "formula": "n_eff=team_opp_while_active, prior=own_s-1_share_if_50+opp_else_(pos,depth)_league_mean",
            "grid_results": [{k: v for k, v in g.items() if k != "by_season"}
                              for g in sorted(grid, key=lambda x: x["mean_rmse"])],
        }
        with open(PARAMS_PATH, "w") as f:
            json.dump(params, f, indent=2, default=str)
        print(f"\nWrote usage block to {PARAMS_PATH} "
              f"(sh_hl={best['share_half_life']}, k={best['k_share']}, "
              f"frozen_commit={commit_hash})")
        print(f"Total elapsed: {time.time()-t_start:.1f}s")
        return

    # ── BUILD MODE (default) ──────────────────────────────────────────
    if "usage" not in params:
        raise ValueError(
            "params_v1.json missing required 'usage' block — "
            "run with --tune first, or write share_half_life and k_share manually"
        )
    print(f"\nBuilding with frozen params: share_half_life={params['usage']['share_half_life']}, "
          f"k_share={params['usage']['k_share']} "
          f"(frozen_at={params['usage'].get('frozen_at', '?')})")

    t7 = time.time()
    usage = build_player_usage(rec, team_tgt, car, team_car, pos_map, rate_priors, params,
                                roster_uni, active, depth_order_priors, player_season_shares,
                                starting_qbs=starting_qbs)
    print(f"  {len(usage):,} rows ({time.time()-t7:.1f}s)")

    # Log starting QBs for 2026 week 2
    print(f"\n  Starting QBs (2026 wk2):")
    for team in sorted(set(k[2] for k in starting_qbs if k[0] == 2026 and k[1] == 2)):
        sq = starting_qbs.get((2026, 2, team))
        if sq:
            name_row = usage[(usage["season"] == 2026) & (usage["week"] == 2)
                             & (usage["player_id"] == sq["gsis_id"])]
            name = name_row["player_name"].iloc[0] if not name_row.empty else sq["gsis_id"]
            print(f"    {team}: {name} ({sq['source']})")

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

    print(f"  (e) active_flag = {active['active_flag'].mean():.3f}: DEV/RES/INA + Out/Doubtful → PASS")

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

    print(f"\nTotal elapsed: {time.time()-t_start:.1f}s")
    print("Usage build complete.")


if __name__ == "__main__":
    main()
