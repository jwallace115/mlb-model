#!/usr/bin/env python3
"""
NFL Sim Phase 2A — Vectorised play-level game engine.

ALGORITHM (stated before implementation, per CLAUDE.md):
    Simulations are VECTORISED ACROSS SIMS. One game = one call that holds
    N parallel game states as numpy arrays (possession, down, distance,
    yardline_100, quarter, seconds_remaining, score_home, score_away) and
    advances all N states one play per step until every sim's game is over.
    No `for sim in range(N)`. Per-play draws are vectorised numpy random calls.

    Per play:
    - play call: P(pass) = logistic(logit(league xpass for bucket) + team PROE/100)
      PROE is in percentage points, converted to logit shift.
    - matchup: success probability for the play = log5(off_success, def_success,
      league_success) using pass_off/pass_def or rush_off/rush_def `success` ratings;
      explosive share within success = log5 of explosive ratings; sack probability =
      log5(off sack_rate, def sack_rate, league); INT = log5(int_rate);
      stuff = log5(stuff_rate). Then draw success/fail, explosive/not, and yards from
      the matching empirical quantile table by inverse-CDF.
      log5(a, b, l) = (a*b/l) / (a*b/l + (1-a)*(1-b)/(1-l)).
      This is the only matchup formula.
    - pace: seconds per play drawn from clock table by outcome type (complete-inbounds,
      run, incomplete/OOB, first-down), scaled by team pace / league pace, with
      hurry-up override in Q4 or last 2:00 of Q2 when trailing or within 8.
    - 4th down, kicks, XP/2pt, turnovers, penalties, OT (2025-26 regular season rules:
      10-minute OT, both teams possess unless first possession ends in defensive score;
      ties allowed), and end-of-half/game per tables.

    Output per sim: home_score, away_score, home_1h, away_1h, plays, drives,
    home_pass_yds, home_rush_yds, away_pass_yds, away_rush_yds, turnovers, ot_flag.

    Determinism: same seed -> identical output.
"""

import json, time
from pathlib import Path

import numpy as np
import pandas as pd

from nfl.sim.seed_util import stable_seed
from nfl.sim.tables import fourth_down_keys, eoh_state, fg_setup_state

ROOT = Path(__file__).resolve().parent.parent.parent
TABLES_DIR = ROOT / "nfl" / "data" / "sim" / "tables"
RATINGS_DIR = ROOT / "nfl" / "data" / "sim" / "ratings"

class _DriveLog(pd.DataFrame):
    """5A-11 (D41): the drive log lives in `team_df.attrs`. pandas decides whether to keep
    attrs on `pd.concat` by comparing the attrs dicts with `==`, which compares the two
    drive logs element-wise and raises when their shapes differ (it only got that far
    when the other attr, playcall_fallback_count, happened to be equal — a latent flake
    that surfaced in the 5A-11 suite run). Frame-level equality on a drive log is
    identity; everything else is a plain DataFrame."""
    @property
    def _constructor(self):
        return pd.DataFrame

    def __eq__(self, other):
        return self is other

    def __ne__(self, other):
        return self is not other

    __hash__ = object.__hash__


# Module-level cache
_CACHE = {}
_DEBUG_YDS = None  # 5A-6 diag: set to a list to collect per-play yards
_DEBUG_4TH = None  # 5A-9 diag: set to a list to collect (yd_b, yl_b, score_b, clock_b, decision)


def _load_tables():
    if "tables" in _CACHE:
        return
    _CACHE["pass"] = pd.read_parquet(TABLES_DIR / "pass_outcomes.parquet")
    _CACHE["rush"] = pd.read_parquet(TABLES_DIR / "rush_outcomes.parquet")
    # 5A-7: 10-yard-zone outcome tables (engine reads these; z5 is the thin-cell fallback)
    for k, fn in (("pass_z10", "pass_outcomes_z10.parquet"), ("rush_z10", "rush_outcomes_z10.parquet")):
        fp = TABLES_DIR / fn
        _CACHE[k] = pd.read_parquet(fp) if fp.exists() else None
    _CACHE["playcall"] = pd.read_parquet(TABLES_DIR / "playcall_xpass.parquet")
    _CACHE["clock"] = pd.read_parquet(TABLES_DIR / "clock_runoff.parquet")
    _CACHE["4th"] = pd.read_parquet(TABLES_DIR / "fourth_down.parquet")
    _CACHE["fg"] = pd.read_parquet(TABLES_DIR / "fg_make_rate.parquet")
    _CACHE["punt"] = pd.read_parquet(TABLES_DIR / "punt_net.parquet")
    with open(TABLES_DIR / "scalars.json") as f:
        _CACHE["scalars"] = json.load(f)
    with open(TABLES_DIR / "turnover_returns.json") as f:
        _CACHE["turnover"] = json.load(f)
    with open(TABLES_DIR / "constants.json") as f:
        _CACHE["constants"] = json.load(f)
    depth_path = TABLES_DIR / "pass_depth_outcomes.parquet"
    if depth_path.exists():
        _CACHE["pass_depth"] = pd.read_parquet(depth_path)
    # 5S: INT air-yards spot table
    int_spot_path = TABLES_DIR / "int_spot.parquet"
    if int_spot_path.exists():
        _CACHE["int_spot"] = pd.read_parquet(int_spot_path)
    # 5A-7: timeout policy and kneel decision tables
    for k, fn in (("timeout_policy", "timeout_policy.parquet"), ("kneel", "kneel_decision.parquet"),
                  ("fg_setup", "fg_setup.parquet"), ("fg_setup_rush", "fg_setup_rush.parquet"),
                  ("eoh_spike", "eoh_spike.parquet"), ("twopt", "twopt_decision.parquet")):
        fp = TABLES_DIR / fn
        _CACHE[k] = pd.read_parquet(fp) if fp.exists() else None
    # 5A-6: end-of-half FG decision table (downs 1-3)
    eoh_path = TABLES_DIR / "eoh_fg_decision.parquet"
    if eoh_path.exists():
        _CACHE["eoh_fg"] = pd.read_parquet(eoh_path)
    # 5A-4: penalty detail table
    pen_detail_path = TABLES_DIR / "penalty_detail.json"
    if pen_detail_path.exists():
        with open(pen_detail_path) as f:
            _CACHE["penalty_detail"] = json.load(f)
    _CACHE["tables"] = True


def _load_ratings():
    return (
        pd.read_parquet(RATINGS_DIR / "team_ratings_weekly.parquet"),
        pd.read_parquet(RATINGS_DIR / "tendencies_weekly.parquet"),
        pd.read_parquet(RATINGS_DIR / "tendencies_situational_weekly.parquet"),
        pd.read_parquet(RATINGS_DIR / "kicker_weekly.parquet"),
        pd.read_parquet(RATINGS_DIR / "league_baselines.parquet"),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _log5(a, b, l):
    a, b, l = np.clip(a, 0.001, 0.999), np.clip(b, 0.001, 0.999), np.clip(l, 0.001, 0.999)
    num = a * b / l
    return num / (num + (1 - a) * (1 - b) / (1 - l))


def _logit(p):
    p = np.clip(p, 0.001, 0.999)
    return np.log(p / (1 - p))


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -20, 20)))


def _quantile_sample(q101, u):
    """Vectorised: q101 is (K, 101), u is (K,). Returns (K,)."""
    xs = np.linspace(0, 1, 101)
    out = np.empty(len(u))
    for i in range(len(u)):
        out[i] = np.interp(u[i], xs, q101[i])
    return out


def _quantile_sample_single(q101, u_arr):
    """q101 is (101,), u_arr is (N,). Returns (N,)."""
    xs = np.linspace(0, 1, 101)
    return np.interp(u_arr, xs, q101)


# ═══════════════════════════════════════════════════════════════════════════════
# TABLE INDEX BUILDERS
# ═══════════════════════════════════════════════════════════════════════════════

# 5A-7: engine zone index = 10-yard zones. Index k covers yardline_100 in (10k, 10k+10].
NZONES = 10
_Z10_LABELS = [f"y{k}" for k in range(10, 101, 10)]           # y10 -> idx 0 ... y100 -> idx 9
_Z10_INDEX = {lab: i for i, lab in enumerate(_Z10_LABELS)}
_Z5_INDEX = {"rz10": [0], "opp20": [1], "midfield": [2, 3, 4, 5], "own40": [6, 7], "own20": [8, 9]}


def _fill_zone_arrays(tbl5, tbl10, fields, defaults):
    """Fill (5, 3, NZONES[, 101]) arrays from the z10 table, using the z5 parent row
    wherever the z10 cell is absent (thin-cell fallback). `fields` maps array name ->
    (table column, per-cell transform)."""
    dist_map = {"short": 0, "med": 1, "long": 2}
    arrs = {}
    for name, (col, is_q) in fields.items():
        shape = (5, 3, NZONES) + ((101,) if is_q else ())
        arrs[name] = np.full(shape, defaults[name], dtype=float)
    filled = np.zeros((5, 3, NZONES), dtype=bool)
    # z5 parents first, then z10 overrides
    if tbl5 is not None:
        for _, r in tbl5.iterrows():
            d = int(r["down"]); di = dist_map.get(r["dist"]); zs = _Z5_INDEX.get(r["zone"])
            if di is None or zs is None:
                continue
            for zi in zs:
                for name, (col, is_q) in fields.items():
                    if col in r.index:
                        arrs[name][d, di, zi] = np.array(r[col]) if is_q else r[col]
    n10 = 0
    if tbl10 is not None:
        for _, r in tbl10.iterrows():
            d = int(r["down"]); di = dist_map.get(r["dist"]); zi = _Z10_INDEX.get(r["zone"])
            if di is None or zi is None:
                continue
            for name, (col, is_q) in fields.items():
                if col in r.index:
                    arrs[name][d, di, zi] = np.array(r[col]) if is_q else r[col]
            filled[d, di, zi] = True; n10 += 1
    arrs["_z10_cells"] = n10
    return arrs


def _build_pass_arrays():
    """Build numpy arrays indexed by (down, dist_bucket, zone10) for fast lookup.
    5A-7: 10-yard zones from pass_outcomes_z10, z5 parents as fallback."""
    fields = {"p_fumble": ("p_fumble", False), "p_sack": ("p_sack", False),
              "sack_yds_q": ("sack_yds_q", True), "p_int": ("p_int", False),
              "p_comp": ("p_comp", False), "p_succ": ("p_success_given_comp", False),
              "yds_succ_q": ("yds_success_q", True), "yds_fail_q": ("yds_fail_q", True)}
    defaults = {"p_fumble": 0.008, "p_sack": 0.06, "sack_yds_q": -5.0, "p_int": 0.02,
                "p_comp": 0.65, "p_succ": 0.50, "yds_succ_q": 12.0, "yds_fail_q": 3.0}
    a = _fill_zone_arrays(_CACHE["pass"], _CACHE.get("pass_z10"), fields, defaults)
    _CACHE["_pass_z10_cells"] = a["_z10_cells"]
    return (a["p_fumble"], a["p_sack"], a["sack_yds_q"], a["p_int"], a["p_comp"],
            a["p_succ"], a["yds_succ_q"], a["yds_fail_q"])


def _build_rush_arrays():
    fields = {"p_fum": ("p_fumble", False), "p_succ": ("p_success", False),
              "yds_succ_q": ("yds_success_q", True), "yds_fail_q": ("yds_fail_q", True)}
    defaults = {"p_fum": 0.01, "p_succ": 0.43, "yds_succ_q": 5.0, "yds_fail_q": 1.0}
    a = _fill_zone_arrays(_CACHE["rush"], _CACHE.get("rush_z10"), fields, defaults)
    _CACHE["_rush_z10_cells"] = a["_z10_cells"]
    return a["p_fum"], a["p_succ"], a["yds_succ_q"], a["yds_fail_q"]


def _build_clock_arrays():
    """Build clock quantile arrays.
    5A-3: primary key = (outcome_type, score_state, clock_period).
    Fallback chain: (ot, score_state, clock_period) -> (ot, p_score_state, all)
                  -> (ot, all, all, hurry=True/False) for legacy compat."""
    tbl = _CACHE["clock"]
    d = {}
    for _, r in tbl.iterrows():
        q = np.array(r["elapsed_q"])
        # 5A-3 keys: (outcome_type, score_state, clock_period)
        ss = r.get("score_state", "all")
        cp = r.get("clock_period", "all")
        d[(r["outcome_type"], ss, cp)] = q
        # Legacy keys for backward compat
        if ss == "all":
            d[(r["outcome_type"], r["hurry"])] = q
    return d


def _build_4th_down_lookup():
    tbl = _CACHE["4th"]
    d = {}
    for _, r in tbl.iterrows():
        d[(r["ydstogo_b"], r["yl_b"], r["score_b"], r["qtr_b"])] = (r["p_go"], r["p_punt"], r["p_fg"])
    return d


def _build_timeout_lookup():
    """5A-7: (side, qtr, sec_b, off_state, clock_running_str) -> P(timeout after the snap)."""
    tbl = _CACHE.get("timeout_policy")
    if tbl is None:
        return None
    return {(r["side"], int(r["qtr"]), r["sec_b"], r["off_state"], r["clock_running"]): float(r["p_to"])
            for _, r in tbl.iterrows()}


def _build_fg_setup_lookup():
    """5A-9 (D33): (state, sec_b, def_to, down) -> (p_kneel, pass_rate)."""
    tbl = _CACHE.get("fg_setup")
    if tbl is None:
        return None
    return {(r["state"], r["sec_b"], r["def_to"], r["down"]): (float(r["p_kneel"]), float(r["pass_rate"]),
                                                                float(r["p_fg"]) if "p_fg" in tbl and pd.notna(r["p_fg"]) else 0.0)
            for _, r in tbl.iterrows()}


def _fgs_sec_bucket(cl):
    return "0-20" if cl <= 20 else "21-40" if cl <= 40 else "41-60" if cl <= 60 else \
           "61-90" if cl <= 90 else "91-120" if cl <= 120 else "121-180"


def _build_kneel_lookup():
    """5A-7: (qtr, sec_b, def_to, down, situation) -> P(kneel)."""
    tbl = _CACHE.get("kneel")
    if tbl is None:
        return None
    return {(int(r["qtr"]), r["sec_b"], r["def_to"], r["down"], r["situation"]): float(r["p_kneel"])
            for _, r in tbl.iterrows()}


def _to_sec_bucket(cl):
    return "0-30" if cl <= 30 else ("31-60" if cl <= 60 else ("61-120" if cl <= 120 else "121-180"))


def _kneel_sec_bucket(cl):
    return "0-40" if cl <= 40 else ("41-80" if cl <= 80 else ("81-120" if cl <= 120 else "121-180"))


def _build_eoh_lookup():
    """5A-6: (state, sec_b, yl_b) -> P(FG attempt on downs 1-3); yl_b 'all' is the
    pooled-over-yardline fallback. Returns None when the table is absent."""
    tbl = _CACHE.get("eoh_fg")
    if tbl is None:
        return None
    return {(r["state"], r["sec_b"], r["yl_b"]): float(r["p_fg"]) for _, r in tbl.iterrows()}


def _eoh_bucket(cl, y):
    sec_b = "0-3" if cl <= 3 else ("4-6" if cl <= 6 else ("7-10" if cl <= 10 else ("11-20" if cl <= 20 else "21-40")))
    yl_b = "<=20" if y <= 20 else ("21-30" if y <= 30 else ("31-40" if y <= 40 else "41-50"))
    return sec_b, yl_b


def _build_fg_lookup():
    tbl = _CACHE["fg"]
    return dict(zip(tbl["dist"].astype(int), tbl["make_rate"]))


def _build_punt_lookup():
    tbl = _CACHE["punt"]
    d = {}
    for _, r in tbl.iterrows():
        d[r["zone"]] = np.array(r["net_q"])
    return d


# ═══════════════════════════════════════════════════════════════════════════════
# PASS DEPTH ARRAYS (for player allocation)
# ═══════════════════════════════════════════════════════════════════════════════

def _build_pass_depth_arrays():
    """Build 5D arrays (down, dist, zone, depth) for depth-split yards."""
    if "pass_depth" not in _CACHE:
        return None, None
    tbl = _CACHE["pass_depth"]
    dist_map = {"short": 0, "med": 1, "long": 2}
    zone_map = {"own20": 0, "own40": 1, "midfield": 2, "opp20": 3, "rz10": 4}
    depth_map = {"short": 0, "deep": 1}

    shape = (5, 3, 5, 2)
    yds_succ = np.full(shape + (101,), 10.0)
    yds_fail = np.full(shape + (101,), 3.0)

    for _, r in tbl.iterrows():
        d = int(r["down"])
        di = dist_map.get(r["dist"])
        zi = zone_map.get(r["zone"])
        dpi = depth_map.get(r["depth"])
        if di is None or zi is None or dpi is None:
            continue
        yds_succ[d, di, zi, dpi] = np.array(r["yds_success_q"])
        yds_fail[d, di, zi, dpi] = np.array(r["yds_fail_q"])

    return yds_succ, yds_fail


LG_POS_CATCH = {"WR": 0.629, "TE": 0.699, "RB": 0.776, "QB": 0.692}

# FIX 1: Beta-binomial overdispersion (phi) by position, MLE-fitted 2021-2024
PHI_TARGET = {"WR": 42.9, "TE": 85.0, "RB": 71.3}
PHI_CARRY = {"RB": 7.9, "QB": 20.0, "WR": 200.0, "TE": 200.0}  # WR/TE carry phi high = near-deterministic

# FIX 2: Measured redistribution PROPORTIONAL weights (normalized to sum=1).
# Derived from 2021-2024 mean deltas, N >= 20 per cell.
# When absent WR: delta WR=.0313 TE=.0151 RB=.0074 → proportional 58/28/14
# When absent TE: delta TE=.0354 WR=.0192 RB=.0020 → proportional 63/34/4
# When absent RB: delta WR=.0304 RB=.0145 TE=.0068 → proportional 59/28/13
REDIST_TARGET = {
    ("WR", "WR"): 0.582, ("WR", "TE"): 0.281, ("WR", "RB"): 0.138, ("WR", "QB"): 0.0,
    ("TE", "WR"): 0.339, ("TE", "TE"): 0.625, ("TE", "RB"): 0.035, ("TE", "QB"): 0.0,
    ("RB", "WR"): 0.588, ("RB", "TE"): 0.131, ("RB", "RB"): 0.280, ("RB", "QB"): 0.0,
    ("QB", "WR"): 0.50,  ("QB", "TE"): 0.30,  ("QB", "RB"): 0.20,  ("QB", "QB"): 0.0,
}
# Carry redistribution when RB out: RB=.1485 QB=.0319 WR=.0013 TE=.0001 → 82/18/1/0
REDIST_CARRY = {
    ("RB", "RB"): 0.817, ("RB", "QB"): 0.175, ("RB", "WR"): 0.007, ("RB", "TE"): 0.001,
    ("QB", "RB"): 0.60,  ("QB", "QB"): 0.40,  ("QB", "WR"): 0.0,   ("QB", "TE"): 0.0,
    ("WR", "RB"): 0.50,  ("WR", "QB"): 0.20,  ("WR", "WR"): 0.30,  ("WR", "TE"): 0.0,
    ("TE", "RB"): 0.50,  ("TE", "QB"): 0.20,  ("TE", "WR"): 0.20,  ("TE", "TE"): 0.10,
}


def _renormalize_measured(shares_df, active_ids, depth_map=None):
    """Renormalize with position-aware redistribution (FIX 2).

    Vacated share from inactive player at position P is distributed to active
    players using measured proportional weights (sum to 1 per absent position).
    Within each beneficiary position, distributed equally among active players.
    """
    df = shares_df.copy()
    active_set = set(active_ids)
    SKILL_POS = {"RB", "WR", "TE", "QB"}

    for sc, redist_table in [
        ("target_share", REDIST_TARGET),
        ("rz_target_share", REDIST_TARGET),
        ("carry_share", REDIST_CARRY),
        ("gl_carry_share", REDIST_CARRY),
    ]:
        if sc not in df.columns:
            continue
        for pos in SKILL_POS:
            mask = df["position"] == pos
            inactive_mask = mask & ~df["player_id"].isin(active_set)
            vacated = df.loc[inactive_mask, sc].sum()
            if vacated <= 0:
                continue
            df.loc[inactive_mask, sc] = 0.0

            # Distribute vacated share using proportional weights
            # Weights are (absent_pos, beneficiary_pos) -> fraction of vacated
            distributed = 0.0
            for ben_pos in SKILL_POS:
                ben_mask = (df["position"] == ben_pos) & df["player_id"].isin(active_set)
                if not ben_mask.any():
                    continue
                wt = redist_table.get((pos, ben_pos), 0.0)
                if wt <= 0:
                    continue
                n_ben = ben_mask.sum()
                df.loc[ben_mask, sc] += vacated * wt / n_ben
                distributed += vacated * wt
            # Any undistributed (from missing beneficiary positions) goes to same-pos
            residual = vacated - distributed
            if residual > 1e-8:
                same_mask = (df["position"] == pos) & df["player_id"].isin(active_set)
                if same_mask.any():
                    df.loc[same_mask, sc] += residual / same_mask.sum()

        # Final renormalize to 1
        active_mask = df["player_id"].isin(active_set)
        total = df.loc[active_mask, sc].sum()
        if total > 0:
            df.loc[active_mask, sc] /= total
            df.loc[~active_mask, sc] = 0.0

    return df


def _build_player_context(home, away, season, week, player_usage, active_uni,
                           qb_ratings=None, n_sims=1, rng=None):
    """Build per-team player context with per-sim dispersed shares (FIX 1)."""
    teams = [home, away]
    pctx = [None, None]

    for ti, team in enumerate(teams):
        au = active_uni[(active_uni["season"] == season) &
                        (active_uni["week"] == week) &
                        (active_uni["team"] == team)]
        if au.empty:
            au = active_uni[(active_uni["season"] == season) &
                            (active_uni["week"] <= week) &
                            (active_uni["team"] == team)]
            if not au.empty:
                mx = au["week"].max()
                au = au[au["week"] == mx]
        active_ids = au[au["active_flag"] == True]["player_id"].tolist()

        pu = player_usage[(player_usage["season"] == season) &
                          (player_usage["week"] == week) &
                          (player_usage["team"] == team)]
        if pu.empty:
            pu = player_usage[(player_usage["season"] == season) &
                              (player_usage["week"] <= week) &
                              (player_usage["team"] == team)]
            if not pu.empty:
                mx = pu["week"].max()
                pu = pu[pu["week"] == mx]
        if pu.empty or not active_ids:
            pctx[ti] = None
            continue

        # FIX 2: measured redistribution
        renormed = _renormalize_measured(pu, active_ids)
        renormed = renormed[renormed["player_id"].isin(active_ids)].copy()
        renormed = renormed.sort_values(
            ["target_share", "player_id"], ascending=[False, True], kind="stable"
        ).reset_index(drop=True)

        positions = renormed["position"].values
        is_receiver = np.isin(positions, ["WR", "TE", "RB"])

        # Mean shares (before dispersion)
        ts_mean = renormed["target_share"].values.copy()
        ts_mean[~is_receiver] = 0.0
        ts_sum = max(ts_mean.sum(), 1e-12)
        ts_mean /= ts_sum

        rts_mean = renormed["rz_target_share"].values.copy()
        rts_mean[~is_receiver] = 0.0
        rts_sum = max(rts_mean.sum(), 1e-12)
        rts_mean /= rts_sum

        cs_mean = renormed["carry_share"].values.copy()
        cs_sum = max(cs_mean.sum(), 1e-12)
        cs_mean /= cs_sum

        gcs_mean = renormed["gl_carry_share"].values.copy()
        gcs_sum = max(gcs_mean.sum(), 1e-12)
        gcs_mean /= gcs_sum

        n_pl = len(renormed)
        N = n_sims

        # FIX 1: per-sim Beta-dispersed shares
        # For each player, draw game-level share from Beta(share*phi, (1-share)*phi)
        # then renormalise within the sim.
        def _disperse(mean_shares, phi_map, pos_arr, rng_obj):
            """Draw (N, n_pl) dispersed shares, renormalize per sim."""
            out = np.empty((N, n_pl), dtype=np.float64)
            for j in range(n_pl):
                p = max(mean_shares[j], 1e-6)
                phi = phi_map.get(pos_arr[j], 100.0)
                a = p * phi
                b = (1 - p) * phi
                a = max(a, 0.01)
                b = max(b, 0.01)
                out[:, j] = rng_obj.beta(a, b, size=N)
            # Renormalize each sim
            row_sums = out.sum(axis=1, keepdims=True)
            row_sums[row_sums == 0] = 1.0
            out /= row_sums
            return out

        if rng is not None:
            tgt_shares = _disperse(ts_mean, PHI_TARGET, positions, rng)       # (N, n_pl)
            rz_tgt_shares = _disperse(rts_mean, PHI_TARGET, positions, rng)
            car_shares = _disperse(cs_mean, PHI_CARRY, positions, rng)
            gl_car_shares = _disperse(gcs_mean, PHI_CARRY, positions, rng)
            # Precompute cumulative sums per sim: (N, n_pl)
            tgt_cumsum = np.cumsum(tgt_shares, axis=1)
            rz_tgt_cumsum = np.cumsum(rz_tgt_shares, axis=1)
            car_cumsum = np.cumsum(car_shares, axis=1)
            gl_car_cumsum = np.cumsum(gl_car_shares, axis=1)
        else:
            # Fallback: no dispersion
            tgt_cumsum = np.tile(np.cumsum(ts_mean), (N, 1))
            rz_tgt_cumsum = np.tile(np.cumsum(rts_mean), (N, 1))
            car_cumsum = np.tile(np.cumsum(cs_mean), (N, 1))
            gl_car_cumsum = np.tile(np.cumsum(gcs_mean), (N, 1))

        catch_rates = np.clip(renormed["catch_rate"].fillna(0.65).values, 0.2, 0.95)
        adots = renormed["adot"].fillna(8.0).values
        lg_catch = np.array([LG_POS_CATCH.get(p, 0.65) for p in positions])

        qb_mask = positions == "QB"
        qb_idx = -1
        if qb_mask.any():
            qb_candidates = renormed[qb_mask]
            # D50: Use is_starting_qb — raises for ANY season if missing.
            if "is_starting_qb" not in renormed.columns:
                raise ValueError(
                    f"is_starting_qb column missing for {team} {season} wk{week}. "
                    f"Rebuild player_usage_weekly.parquet with usage.py."
                )
            starter = qb_candidates[qb_candidates["is_starting_qb"] == True]
            if len(starter) >= 1:
                qb_idx = starter.index[0]
                qb_idx = renormed.index.get_loc(qb_idx)
            else:
                raise ValueError(
                    f"No is_starting_qb=True for {team} {season} wk{week}. "
                    f"QB candidates: {qb_candidates['player_id'].tolist()}. "
                    f"Run usage.py to set the flag."
                )

        pctx[ti] = {
            "ids": renormed["player_id"].values,
            "names": renormed["player_name"].values,
            "positions": positions,
            "tgt_cumsum": tgt_cumsum,         # (N, n_pl)
            "rz_tgt_cumsum": rz_tgt_cumsum,
            "car_cumsum": car_cumsum,
            "gl_car_cumsum": gl_car_cumsum,
            "catch_rates": catch_rates,
            "lg_catch": lg_catch,
            "adots": adots,
            "n_players": n_pl,
            "qb_idx": qb_idx,
            "team": team,
        }

    return pctx


# ═══════════════════════════════════════════════════════════════════════════════
# TEAM CONTEXT (pre-computed per game)
# ═══════════════════════════════════════════════════════════════════════════════

def _get_team_rating(team_r, team, season, week, unit):
    mask = (team_r["season"] == season) & (team_r["week"] == week) & \
           (team_r["team"] == team) & (team_r["unit"] == unit)
    rows = team_r[mask]
    if len(rows):
        return rows.iloc[0]
    mask2 = (team_r["season"] == season) & (team_r["week"] <= week) & \
            (team_r["team"] == team) & (team_r["unit"] == unit)
    rows2 = team_r[mask2].sort_values("week")
    if len(rows2):
        return rows2.iloc[-1]
    return None


def _build_game_context(home, away, season, week, team_r, tend, sit, kicker, league):
    """Pre-compute all matchup parameters for one game."""
    ctx = {}

    # League baselines (s-1)
    lb_row = league[league["season"] == season - 1]
    if lb_row.empty:
        lb_row = league[league["season"] == league["season"].max()]
    lb = lb_row.iloc[0]
    ctx["lb"] = lb

    teams = [home, away]
    ctx["teams"] = teams

    # Matchup rates: [home_off, away_off] (each team when on offense)
    for ti, (off, dft) in enumerate([(home, away), (away, home)]):
        po = _get_team_rating(team_r, off, season, week, "pass_off")
        pd_ = _get_team_rating(team_r, dft, season, week, "pass_def")
        ro = _get_team_rating(team_r, off, season, week, "rush_off")
        rd = _get_team_rating(team_r, dft, season, week, "rush_def")

        # Use league if missing
        if po is None:
            po = lb
        if pd_ is None:
            pd_ = lb
        if ro is None:
            ro = lb
        if rd is None:
            rd = lb

        prefix = f"t{ti}_"
        ctx[prefix + "pass_success"] = _log5(po["success"], pd_["success"], lb["pass_success"])
        ctx[prefix + "pass_explosive"] = _log5(po["explosive"], pd_["explosive"], lb["pass_explosive"])
        ctx[prefix + "sack_rate"] = _log5(po["sack_rate"], pd_["sack_rate"], lb["pass_sack_rate"])
        ctx[prefix + "int_rate"] = _log5(po["int_rate"], pd_["int_rate"], lb["pass_int_rate"])
        ctx[prefix + "rush_success"] = _log5(ro["success"], rd["success"], lb["rush_success"])
        ctx[prefix + "rush_explosive"] = _log5(ro["explosive"], rd["explosive"], lb["rush_explosive"])
        ctx[prefix + "rush_stuff"] = _log5(ro["stuff_rate"], rd["stuff_rate"], lb["rush_stuff_rate"])

        # D6 additive EPA component: yards shift per play
        # S = 5.20 yards per EPA unit (fitted from 2021-2024 within-bucket regression)
        S_EPA = 5.20
        off_pass_epa = po["epa"] if "epa" in po.index else 0.0
        def_pass_epa = pd_["epa"] if "epa" in pd_.index else 0.0
        off_rush_epa = ro["epa"] if "epa" in ro.index else 0.0
        def_rush_epa = rd["epa"] if "epa" in rd.index else 0.0
        # def_epa is EPA opponents achieve: positive = bad defense, negative = good defense
        # Net matchup EPA = off + def - league (additive, not subtractive on def)
        ctx[prefix + "pass_epa_shift"] = (off_pass_epa + def_pass_epa - lb.get("pass_epa", 0.0)) * S_EPA
        ctx[prefix + "rush_epa_shift"] = (off_rush_epa + def_rush_epa - lb.get("rush_epa", 0.0)) * S_EPA

    # Tendencies
    for ti, t in enumerate(teams):
        tr = tend[(tend["season"] == season) & (tend["week"] == week) & (tend["team"] == t)]
        if tr.empty:
            tr = tend[(tend["season"] == season) & (tend["week"] <= week) & (tend["team"] == t)]
            if not tr.empty:
                tr = tr.sort_values("week").iloc[[-1]]
        if not tr.empty:
            ctx[f"t{ti}_proe"] = tr.iloc[0]["proe"]
            ctx[f"t{ti}_pace"] = tr.iloc[0]["pace_sec"]
            ctx[f"t{ti}_4th_go"] = tr.iloc[0]["fourth_down_go_rate"]
            ctx[f"t{ti}_4th_goe"] = tr.iloc[0].get("fourth_down_goe", 0.0)
        else:
            ctx[f"t{ti}_proe"] = 0.0
            ctx[f"t{ti}_pace"] = 30.0
            ctx[f"t{ti}_4th_go"] = 0.15
            ctx[f"t{ti}_4th_goe"] = 0.0

    # Situational PROE
    for ti, t in enumerate(teams):
        sr = sit[(sit["season"] == season) & (sit["week"] == week) & (sit["team"] == t)]
        if sr.empty:
            sr = sit[(sit["season"] == season) & (sit["week"] <= week) & (sit["team"] == t)]
            if not sr.empty:
                mx = sr["week"].max()
                sr = sr[sr["week"] == mx]
        ctx[f"t{ti}_sit_proe"] = dict(zip(sr["bucket"], sr["proe"])) if len(sr) else {}

    # Kicker
    for ti, t in enumerate(teams):
        kr = kicker[(kicker["season"] == season) & (kicker["week"] == week) & (kicker["team"] == t)]
        if kr.empty:
            kr = kicker[(kicker["season"] == season) & (kicker["week"] <= week) & (kicker["team"] == t)]
            if not kr.empty:
                kr = kr.sort_values("week").iloc[[-1]]
        if not kr.empty:
            k = kr.iloc[0]
            ctx[f"t{ti}_fg"] = {
                "<30": float(k.get("fg_<30", 0.98)),
                "30-39": float(k.get("fg_30-39", 0.93)),
                "40-49": float(k.get("fg_40-49", 0.78)),
                "50+": float(k.get("fg_50+", 0.68)),
            }
            ctx[f"t{ti}_xp"] = float(k.get("xp_rate", 0.94))
        else:
            ctx[f"t{ti}_fg"] = {"<30": 0.98, "30-39": 0.93, "40-49": 0.78, "50+": 0.68}
            ctx[f"t{ti}_xp"] = 0.94

    # League pace for scaling — PIT: only data strictly before this game
    tend_pit = tend[((tend["season"] == season - 1)) |
                    ((tend["season"] == season) & (tend["week"] < week))]
    ctx["lg_pace"] = tend_pit["pace_sec"].mean() if len(tend_pit) else 30.0

    # League average 4th-down go rate — PIT: same filter
    ctx["lg_4th_go"] = tend_pit["fourth_down_go_rate"].mean() if len(tend_pit) else 0.68

    return ctx


# ═══════════════════════════════════════════════════════════════════════════════
# VECTORISED GAME SIMULATION
# ═══════════════════════════════════════════════════════════════════════════════

def simulate_game(home, away, season, week, n_sims=2000, seed=42,
                  team_r=None, tend=None, sit=None, kicker=None, league=None,
                  _dummy_draw=False,
                  player_usage=None, active_uni=None, qb_ratings=None,
                  epa_home_offset=0.0, epa_away_offset=0.0,
                  season_type="REG", drive_log=False):
    _load_tables()
    if team_r is None:
        team_r, tend, sit, kicker, league = _load_ratings()

    rng = np.random.default_rng(seed)
    ctx = _build_game_context(home, away, season, week, team_r, tend, sit, kicker, league)

    # D7 anchoring offsets: added to the D6 EPA shift channel (same mechanism)
    if epa_home_offset != 0.0:
        ctx["t0_pass_epa_shift"] += epa_home_offset
        ctx["t0_rush_epa_shift"] += epa_home_offset
    if epa_away_offset != 0.0:
        ctx["t1_pass_epa_shift"] += epa_away_offset
        ctx["t1_rush_epa_shift"] += epa_away_offset

    # Player allocation context — 5M: child generator so the player layer
    # cannot shift the team-level RNG stream.
    has_players = player_usage is not None and active_uni is not None
    player_ctx = None
    if has_players:
        player_rng = np.random.default_rng(stable_seed((seed, "player")))
        player_ctx = _build_player_context(home, away, season, week,
                                            player_usage, active_uni, qb_ratings,
                                            n_sims=n_sims, rng=player_rng)
        if player_ctx[0] is None or player_ctx[1] is None:
            has_players = False
            player_ctx = None

    # Build lookup arrays
    (pa_fumble, pa_sack, pa_sack_yds, pa_int, pa_comp, pa_succ,
     pa_yds_succ, pa_yds_fail) = _build_pass_arrays()
    (ru_fum, ru_succ, ru_yds_succ, ru_yds_fail) = _build_rush_arrays()

    # Depth-split pass yards (for player allocation)
    pd_yds_succ, pd_yds_fail = (None, None)
    if has_players and "pass_depth" in _CACHE:
        pd_yds_succ, pd_yds_fail = _build_pass_depth_arrays()
    clock_q = _build_clock_arrays()
    fd_lookup = _build_4th_down_lookup()
    eoh_lookup = _build_eoh_lookup()  # 5A-6
    to_lookup = _build_timeout_lookup()  # 5A-7
    kneel_lookup = _build_kneel_lookup()  # 5A-7
    fgs_lookup = _build_fg_setup_lookup()  # 5A-9
    fgs_rush_q = (np.array(_CACHE["fg_setup_rush"]["yds_q"].iloc[0], dtype=float)
                  if _CACHE.get("fg_setup_rush") is not None else None)
    spike_lookup = None
    if _CACHE.get("eoh_spike") is not None:
        spike_lookup = {(r["half"], r["sec_b"]): float(r["p_spike"]) for _, r in _CACHE["eoh_spike"].iterrows()}
    fgs_kneel_q = None
    _kn = _CACHE["clock"]
    _kn = _kn[(_kn["outcome_type"] == "kneel") & (_kn["clock_period"] == "fgs")] if "clock_period" in _kn else _kn.iloc[0:0]
    if len(_kn) == 2:
        fgs_kneel_q = {"next_sec": np.array(_kn[_kn["score_state"] == "fgs_0-40"]["elapsed_q"].iloc[0], dtype=float),
                       "elapsed": np.array(_kn[_kn["score_state"] == "fgs_41-180"]["elapsed_q"].iloc[0], dtype=float)}
    xs101_top = np.linspace(0, 1, 101)
    fg_lookup = _build_fg_lookup()
    punt_lookup = _build_punt_lookup()

    pc_lookup = dict(zip(_CACHE["playcall"]["bucket"], _CACHE["playcall"]["pass_rate"]))
    pc_bucket_set = set(pc_lookup.keys())
    _fallback_count = 0  # FIX 5: count playcall fallbacks
    _sit_proe_miss = 0  # 5C-1b: count sit PROE lookups that miss
    scalars = _CACHE["scalars"]
    to_ret = _CACHE["turnover"]
    consts = _CACHE["constants"]
    # 5A-7: per-play safety rates by own-goal-line bucket, measured in tables.build_constants
    _srz = consts.get("safety_rate_by_zone", {})
    p_saf_98 = float(_srz.get("98-100", {}).get("p", 0.0))
    p_saf_95 = float(_srz.get("95-97", {}).get("p", 0.0))
    p_saf_90 = float(_srz.get("90-94", {}).get("p", 0.0))

    # FIX 6a: 2pt decision table
    twopt_tbl = _CACHE.get("twopt")
    if twopt_tbl is None:
        twopt_tbl = pd.read_parquet(TABLES_DIR / "twopt_decision.parquet")
    # 5A-10 (D35): exact post-TD differential x period; every key present (complete grid)
    twopt_lookup = {(r["period"], int(r["sd_post"])): float(r["p_2pt"]) for _, r in twopt_tbl.iterrows()}
    twopt_conv_rate = scalars.get("twopt_conv_rate", 0.48)

    # FIX 6d: kickoff start position from table
    ko_tbl = pd.read_parquet(TABLES_DIR / "kickoff.parquet")
    ko_start = 75  # default
    ko_row = ko_tbl[ko_tbl["season"] == season]
    if ko_row.empty:
        ko_row = ko_tbl[ko_tbl["season"] == ko_tbl["season"].max()]
    if not ko_row.empty:
        ko_start = int(ko_row.iloc[0]["start_yl100"])

    int_ret_q = np.array(to_ret["int_return_yds_q"])
    fum_ret_q = np.array(to_ret["fum_return_yds_q"])
    p_int_def_td = to_ret["int_p_def_td"]
    p_fum_def_td = to_ret["fum_p_def_td"]

    # 5S: INT air-yards spot table — quantiles by LOS bucket
    _int_spot_tbl = _CACHE.get("int_spot")
    _int_spot_q = {}  # los_bucket -> quantile array
    if _int_spot_tbl is not None:
        for _, row in _int_spot_tbl.iterrows():
            _int_spot_q[row["los_bucket"]] = np.array(row["quantiles"])

    p_penalty_nop = scalars["penalty"]["p_no_play_penalty"]
    p_off_pen = scalars["penalty"].get("p_noplay_offense", 0.615)
    p_auto_first = scalars["penalty"].get("noplay_auto_first", 0.5)

    # 5A-4: category-based penalty model from penalty_detail.json
    _pen_detail = _CACHE.get("penalty_detail")
    _pen_cats_enabled = _pen_detail is not None
    if _pen_cats_enabled:
        # Build categorical CDF for penalty type selection
        _pen_cat_order = [
            "offense_5yd", "offense_10yd", "offense_15yd", "offense_other",
            "defense_auto_short", "defense_auto_long", "defense_dpi",
            "defense_noauto", "defense_other",
        ]
        _pen_counts = np.array([_pen_detail.get(c, {}).get("count", 0)
                                for c in _pen_cat_order], dtype=np.float64)
        _pen_total = _pen_counts.sum()
        _pen_probs = _pen_counts / _pen_total
        _pen_cdf = np.cumsum(_pen_probs)
        # Per-category: is_offense, yardage quantiles, auto-first rate
        _pen_is_off = np.array([c.startswith("offense") for c in _pen_cat_order])
        _pen_auto_first = np.array([
            _pen_detail.get(c, {}).get("auto_first_rate", 0.0)
            for c in _pen_cat_order])
        _pen_mean_yds = np.array([
            _pen_detail.get(c, {}).get("mean_yds", 5.0)
            for c in _pen_cat_order])
        _pen_yds_q = []
        for c in _pen_cat_order:
            q = _pen_detail.get(c, {}).get("yds_q")
            if q is not None:
                _pen_yds_q.append(np.array(q))
            else:
                _pen_yds_q.append(np.full(101, _pen_detail.get(c, {}).get("mean_yds", 5.0)))
        # DPI spot-of-foul: need a separate yardage draw since it depends on yardline
        _pen_dpi_idx = _pen_cat_order.index("defense_dpi")
        _pen_dpi_yds_q = _pen_yds_q[_pen_dpi_idx]
        # Keep p_penalty_nop from scalars (0.072 = no-play penalties / scrimmage plays)
        xs101_pen = np.linspace(0, 1, 101)

    p_punt_ret_td = to_ret.get("punt_p_ret_td", 0.0024)
    p_ko_ret_td = to_ret.get("ko_p_ret_td", 0.0025)

    lb = ctx["lb"]

    N = n_sims

    # State arrays
    # FIX 6c: random receiving team per sim
    u_coin = rng.random(N)
    poss = (u_coin >= 0.5).astype(np.int8)  # 0=home receives, 1=away receives
    opening_receiver = poss.copy()  # track for 2nd-half kickoff
    down = np.ones(N, dtype=np.int8)
    dist = np.full(N, 10.0, dtype=np.float32)
    yl = np.full(N, float(ko_start), dtype=np.float32)  # FIX 6d + FIX 7: float for continuity
    qtr = np.ones(N, dtype=np.int8)
    clock = np.full(N, 900, dtype=np.float32)  # seconds in quarter

    score_h = np.zeros(N, dtype=np.int16)
    score_a = np.zeros(N, dtype=np.int16)
    score_h_1h = np.zeros(N, dtype=np.int16)
    score_a_1h = np.zeros(N, dtype=np.int16)
    half_recorded = np.zeros(N, dtype=bool)

    n_plays = np.zeros(N, dtype=np.int16)
    n_drives = np.ones(N, dtype=np.int16)
    h_pass_yds = np.zeros(N, dtype=np.float32)
    h_rush_yds = np.zeros(N, dtype=np.float32)
    a_pass_yds = np.zeros(N, dtype=np.float32)
    a_rush_yds = np.zeros(N, dtype=np.float32)
    turnovers = np.zeros(N, dtype=np.int16)
    ot_flag = np.zeros(N, dtype=np.int8)
    game_over = np.zeros(N, dtype=bool)

    # Per-play event counters for diagnostics
    ev_sacks = np.zeros(N, dtype=np.int16)
    ev_ints = np.zeros(N, dtype=np.int16)
    ev_incomp = np.zeros(N, dtype=np.int16)
    ev_comp = np.zeros(N, dtype=np.int16)
    ev_pass_plays = np.zeros(N, dtype=np.int16)
    ev_rush_plays = np.zeros(N, dtype=np.int16)
    ev_first_downs = np.zeros(N, dtype=np.int16)
    ev_punts = np.zeros(N, dtype=np.int16)
    ev_fg_att = np.zeros(N, dtype=np.int16)
    ev_fg_non4th = np.zeros(N, dtype=np.int16)  # 5A-6: FG attempts on downs 1-3
    ev_eoh_snaps = np.zeros(N, dtype=np.int16)  # 5A-6: snaps on downs 1-3, <=40s left in half, yl<=50
    to_rem = np.full((2, N), 3, dtype=np.int8)   # 5A-7: timeouts remaining per team, per half
    ev_to_off = np.zeros(N, dtype=np.int16)      # 5A-7: offensive timeouts taken (last 3:00 of halves)
    ev_to_def = np.zeros(N, dtype=np.int16)      # 5A-7: defensive timeouts taken
    ev_kneels = np.zeros(N, dtype=np.int16)      # 5A-7: kneel-downs
    ev_late_snaps_q2 = np.zeros(N, dtype=np.int16)  # 5A-6: scrimmage snaps with <=120s left in Q2
    ev_late_snaps_q4 = np.zeros(N, dtype=np.int16)  # 5A-6: scrimmage snaps with <=120s left in Q4
    # 5A-8 diag: score state (home - away) and possession when the Q4 clock first reads
    # <= 5:00 and <= 2:00 at the start of a play. Pure observation: no RNG draws, no
    # behaviour change. -999 = never reached (cannot happen for a finished game).
    m_q4_300 = np.full(N, -999, dtype=np.int16)
    m_q4_120 = np.full(N, -999, dtype=np.int16)
    poss_q4_300 = np.full(N, -1, dtype=np.int8)
    poss_q4_120 = np.full(N, -1, dtype=np.int8)
    yl_q4_120 = np.full(N, -1, dtype=np.int16)
    _cap300 = np.zeros(N, dtype=bool)
    _cap120 = np.zeros(N, dtype=bool)
    ev_eoh_runoff = np.zeros(N, dtype=np.int16)   # 5A-9: snaps whose runoff came from the EOH cells
    ev_fgs_snaps = np.zeros(N, dtype=np.int16)    # 5A-9: scrimmage snaps called from the FG-setup cell
    ev_fgs_runs = np.zeros(N, dtype=np.int16)     # 5A-9: runs drawn from the FG-setup yardage cell
    ev_fgs_runoff = np.zeros(N, dtype=np.int16)   # 5A-9: snaps whose runoff came from the FG-setup cells
    ev_spikes = np.zeros(N, dtype=np.int16)       # 5A-9 (D34): spikes
    ev_fg_made = np.zeros(N, dtype=np.int16)
    ev_tds = np.zeros(N, dtype=np.int16)
    ev_penalties = np.zeros(N, dtype=np.int16)
    ev_clock_used = np.zeros(N, dtype=np.float32)  # Total clock consumed by play draws

    # Phase 5A-2 drive-log counters (always allocated, no perf impact)
    ev_pass_fumbles = np.zeros(N, dtype=np.int16)
    ev_rush_fumbles = np.zeros(N, dtype=np.int16)
    ev_3rd_att = np.zeros(N, dtype=np.int16)
    ev_3rd_long = np.zeros(N, dtype=np.int16)  # 5I: 3rd-and-11+ counter
    ev_3rd_conv = np.zeros(N, dtype=np.int16)
    ev_4th_go = np.zeros(N, dtype=np.int16)
    ev_4th_conv = np.zeros(N, dtype=np.int16)
    ev_fg_dist_sum = np.zeros(N, dtype=np.float32)
    ev_explosive_pass = np.zeros(N, dtype=np.int16)  # 5A-3: completions 20+ yds
    ev_explosive_rush = np.zeros(N, dtype=np.int16)  # 5A-3: rushes 10+ yds
    ev_pass_40 = np.zeros(N, dtype=np.int16)   # 5A-6 diag: completions 40+ yds
    ev_rush_20 = np.zeros(N, dtype=np.int16)   # 5A-6 diag: rushes 20+ yds
    ev_td_long = np.zeros(N, dtype=np.int16)   # 5A-6 diag: TDs scored from >= 20 yds out
    ev_td_short = np.zeros(N, dtype=np.int16)  # 5A-6 diag: TDs scored from < 20 yds out
    ev_xp_att = np.zeros(N, dtype=np.int16)
    ev_xp_made = np.zeros(N, dtype=np.int16)
    ev_2pt_att = np.zeros(N, dtype=np.int16)
    ev_2pt_made = np.zeros(N, dtype=np.int16)
    ev_def_tds = np.zeros(N, dtype=np.int16)  # defensive/ST TDs
    # 5A-4: penalty and first-down breakdown counters
    ev_pen_offense = np.zeros(N, dtype=np.int16)
    ev_pen_defense = np.zeros(N, dtype=np.int16)
    ev_pen_off_yds = np.zeros(N, dtype=np.float32)
    ev_pen_def_yds = np.zeros(N, dtype=np.float32)
    ev_fd_rush = np.zeros(N, dtype=np.int16)
    ev_fd_pass = np.zeros(N, dtype=np.int16)
    ev_fd_penalty = np.zeros(N, dtype=np.int16)
    ev_safeties = np.zeros(N, dtype=np.int16)
    # 5A-5: non-offensive scoring counters
    ev_int_ret_td = np.zeros(N, dtype=np.int16)
    ev_fum_ret_td = np.zeros(N, dtype=np.int16)
    ev_punt_ret_td = np.zeros(N, dtype=np.int16)
    ev_ko_ret_td = np.zeros(N, dtype=np.int16)
    # Per-quarter scoring (cumulative snapshot at quarter transitions)
    score_h_q = np.zeros((N, 5), dtype=np.int16)  # [q1..q4, OT]
    score_a_q = np.zeros((N, 5), dtype=np.int16)
    _prev_score_h = np.zeros(N, dtype=np.int16)
    _prev_score_a = np.zeros(N, dtype=np.int16)

    # No scale factors — all numbers come from tables built from data

    # Player-level stat accumulators: (N, n_players) per team, 13 stats
    # 0=targets 1=recs 2=rec_yds 3=rec_td 4=carries 5=rush_yds 6=rush_td
    # 7=pass_att 8=pass_cmp 9=pass_yds 10=pass_td 11=ints 12=sacks
    PL_TGT, PL_REC, PL_RECYD, PL_RECTD = 0, 1, 2, 3
    PL_CAR, PL_RUSHYD, PL_RUSHTD = 4, 5, 6
    PL_PATT, PL_PCMP, PL_PYD, PL_PTD, PL_INT, PL_SACK = 7, 8, 9, 10, 11, 12
    N_PL_STATS = 13
    pl_stats = None
    if has_players:
        pl_stats = [
            np.zeros((N, player_ctx[0]["n_players"], N_PL_STATS), dtype=np.int32),
            np.zeros((N, player_ctx[1]["n_players"], N_PL_STATS), dtype=np.int32),
        ]

    # --- Drive log instrumentation (Step 1, Phase 5A-2) ---
    # Tracks per-drive state using score diffs + pending result codes.
    _dl_start_yl = np.full(N, float(ko_start), dtype=np.float32)
    _dl_start_qtr = np.ones(N, dtype=np.int8)
    _dl_start_clock = np.full(N, 900.0, dtype=np.float32)
    _dl_start_sh = np.zeros(N, dtype=np.int16)
    _dl_start_sa = np.zeros(N, dtype=np.int16)
    _dl_plays = np.zeros(N, dtype=np.int16)
    _dl_yards = np.zeros(N, dtype=np.float32)
    _dl_reached_rz = np.zeros(N, dtype=bool)
    _dl_reached_gl = np.zeros(N, dtype=bool)
    _dl_team = np.zeros(N, dtype=np.int8)  # team that HAD the ball during this drive
    _dl_result = np.zeros(N, dtype=np.uint8)  # pending result code
    # 5A-5: end-state tracking for conditional drive analysis
    _dl_end_yl = np.zeros(N, dtype=np.float32)
    _dl_end_down = np.zeros(N, dtype=np.int8)
    _dl_end_dist = np.zeros(N, dtype=np.float32)
    _DLR_NONE = 0
    _DLR_TD, _DLR_FGM, _DLR_FGMISS, _DLR_PUNT = 1, 2, 3, 4
    _DLR_INT, _DLR_FUM, _DLR_DOWNS, _DLR_ENDHALF, _DLR_ENDGAME, _DLR_SAFETY = 5, 6, 7, 8, 9, 10
    _DLR_NAMES = {1:"TD",2:"FG_made",3:"FG_missed",4:"punt",5:"turnover_int",
                  6:"turnover_fumble",7:"downs",8:"end_half",9:"end_game",10:"safety"}
    _dl_rows = []
    _dl_int_rows = []  # 5T: per-INT chain log (LOS, air, catch_yl, ez, ret, six, next_start)

    def _dl_new_drive(m):
        """Record ending drive (if result set), then reset for next drive."""
        if not drive_log or not m.any():
            return
        has = m & (_dl_result > 0)
        if has.any():
            for i in np.where(has)[0]:
                # Points scored = total score change from drive start
                dh = int(score_h[i] - _dl_start_sh[i])
                da = int(score_a[i] - _dl_start_sa[i])
                team = int(_dl_team[i])
                pts = dh if team == 0 else da
                # 5A-5: score state at drive start
                sd_start = int(_dl_start_sh[i] - _dl_start_sa[i]) if team == 0 \
                           else int(_dl_start_sa[i] - _dl_start_sh[i])
                if sd_start <= -9: ss = "trail9+"
                elif sd_start <= -1: ss = "trail1-8"
                elif sd_start == 0: ss = "tied"
                elif sd_start <= 8: ss = "lead1-8"
                else: ss = "lead9+"
                _dl_rows.append((
                    i, team, int(n_drives[i]),
                    float(_dl_start_yl[i]), int(_dl_start_qtr[i]),
                    float(_dl_start_clock[i]),
                    int(_dl_plays[i]), float(_dl_yards[i]),
                    _DLR_NAMES[_dl_result[i]], pts,
                    bool(_dl_reached_rz[i]), bool(_dl_reached_gl[i]),
                    float(_dl_end_yl[i]), int(_dl_end_down[i]),
                    float(_dl_end_dist[i]), ss,
                    sd_start,  # 5A-8: exact offence score differential at drive start
                    (da if team == 0 else dh),  # 5A-8: points the DEFENCE scored during the drive
                ))
        # 5A-5: capture end state before reset (for drives that just recorded)
        # Note: yl/down/dist may already reflect post-drive state for TDs/turnovers
        # so we track _dl_end_* throughout the drive and read them here
        # Reset
        _dl_team[m] = poss[m]
        _dl_start_yl[m] = yl[m]
        _dl_start_qtr[m] = qtr[m]
        _dl_start_clock[m] = clock[m]
        _dl_start_sh[m] = score_h[m]
        _dl_start_sa[m] = score_a[m]
        _dl_plays[m] = 0
        _dl_yards[m] = 0
        _dl_reached_rz[m] = yl[m] <= 20
        _dl_reached_gl[m] = yl[m] <= 5
        _dl_result[m] = _DLR_NONE

    # OT state: track first-possession-complete for OT rules
    ot_first_poss_team = np.full(N, -1, dtype=np.int8)
    ot_first_poss_done = np.zeros(N, dtype=bool)

    # Initialize drive-log team tracking
    _dl_team[:] = poss

    def _new_drive(m):
        # 5A-11 (D38): in OT the first possession is complete when the first team's drive
        # ends for ANY reason (punt, turnover, downs, safety, missed FG) — not only on a
        # score. Until 5A-11 only a score or a turnover on downs marked it, so after a
        # first-drive punt the other team's field goal was treated as a first-possession
        # score and the game went on. Every caller switches `poss` to the receiving team
        # before calling, so the team whose drive just ended is 1 - poss; at the OT kickoff
        # itself that is the team NOT receiving, never the first-possession team. Game
        # state only — the drive-log fields are not maintained when the log is off, and
        # the live object must behave like the research object.
        # ... and once both teams have possessed, a drive that ends with the score NOT tied
        # ends the game (the first team kicked a field goal, the second team's possession
        # came up empty). Until 5A-11 the first team got the ball back and kicked again.
        first_done = m & (qtr >= 5) & (ot_first_poss_team >= 0) & ((1 - poss) == ot_first_poss_team)
        ot_first_poss_done[first_done] = True
        # the drive that ended belonged to the SECOND team (the first team's own scoring
        # drive is followed by a kickoff, and the second team must still get its possession)
        over_now = m & (qtr >= 5) & (ot_first_poss_team >= 0) & ((1 - poss) != ot_first_poss_team) \
                   & ot_first_poss_done & (score_h != score_a) & ~game_over
        if over_now.any():
            game_over[over_now] = True
            _dl_result[over_now] = np.where(_dl_result[over_now] > 0, _dl_result[over_now], _DLR_ENDGAME)
        _dl_new_drive(m)
        down[m] = 1
        dist[m] = np.minimum(10, yl[m])
        n_drives[m] += 1
        # No separate inter-drive clock deduction — the clock table
        # measures all-play gaps including cross-drive transitions

    def _change_poss(m):
        poss[m] = 1 - poss[m]
        yl[m] = np.clip(100 - yl[m], 1, 99)
        _new_drive(m)

    def _score_td(m, team_idx):
        """team_idx: 0=home scored, 1=away scored (array or scalar)."""
        home_scored = m & (team_idx == 0)
        away_scored = m & (team_idx == 1)
        score_h[home_scored] += 6
        score_a[away_scored] += 6

    def _do_pat(m, scoring_team_idx):
        if not m.any():
            return
        # FIX 6a: 2pt decision from twopt_decision.parquet
        go_2pt = np.zeros(N, dtype=bool)
        for i in np.where(m)[0]:
            q = int(qtr[i])
            sd_poss = int(score_h[i] - score_a[i]) if scoring_team_idx[i] == 0 \
                      else int(score_a[i] - score_h[i])
            # 5A-10 (D35): exact post-TD differential (the 6 is already added), Q1-3 vs Q4+
            p2 = twopt_lookup[("Q4+" if q >= 4 else "Q1-3", int(np.clip(sd_poss, -16, 16)))]
            go_2pt[i] = u_pat[i] < p2

        # 2pt attempts
        m_2pt = m & go_2pt
        if m_2pt.any():
            conv = m_2pt & (u_pat < twopt_conv_rate)  # reuse u_pat is fine (conditional)
            # Actually need a separate draw for conversion; u_pat was used for the decision.
            # Use a deterministic split: if u_pat < p2 (decided 2pt), then
            # the "conversion" draw can use the residual part of u_pat.
            # Cleaner: use the next available uniform. But we draw fixed per step.
            # For correctness, draw the conversion from a different uniform.
            # We'll use u_ot as a secondary draw for 2pt conversion (it's independent).
            conv = m_2pt & (u_2pt < twopt_conv_rate)  # 5A-10 (D36): own uniform
            score_h[conv & (scoring_team_idx == 0)] += 2
            score_a[conv & (scoring_team_idx == 1)] += 2

        # XP attempts (non-2pt)
        m_xp = m & ~go_2pt
        if m_xp.any():
            xp_prob = np.full(N, 0.94)
            for ti in [0, 1]:
                tm = m_xp & (scoring_team_idx == ti)
                xp_prob[tm] = ctx[f"t{ti}_xp"]
            # 5A-10 (D36): u_pat decided the 2-pt question, so conditional on kicking it is
            # >= p2 and biased high — reusing it made the XP miss rate 6.2% instead of 5.1%
            made = m_xp & (u_xp < xp_prob)
            score_h[made & (scoring_team_idx == 0)] += 1
            score_a[made & (scoring_team_idx == 1)] += 1

    def _do_kickoff(m):
        poss[m] = 1 - poss[m]
        yl[m] = ko_start  # FIX 6d: from kickoff table
        _new_drive(m)

    def _check_ko_ret_td(m):
        """After a kickoff, check for return TD from empirical rate.
        Scores directly (no recursive kickoff) since P(consecutive) ≈ 0."""
        for i in np.where(m)[0]:
            if u_ko_td[i] < p_ko_ret_td:
                ret_team = poss[i]
                m1 = np.zeros(N, dtype=bool); m1[i] = True
                ev_ko_ret_td[m1] += 1  # 5A-5
                ev_tds[m1] += 1
                _score_td(m1, np.full(N, ret_team, dtype=np.int8))
                _do_pat(m1, np.full(N, ret_team, dtype=np.int8))
                # After KO return TD PAT, opponent gets ball
                _do_kickoff(m1)

    def _handle_td(m, scoring_poss):
        """D66: Full TD sequence. Determine walk-off BEFORE the Try.
        Walk-off OT TDs get NO PAT. A Try is attempted only where play continues."""
        ev_tds[m] += 1
        _score_td(m, scoring_poss)

        ot_m = m & (qtr >= 5)
        reg_m = m & (qtr < 5)

        # ── Determine which OT sims are walk-offs (no Try attempted) ──
        walkoff = np.zeros(N, dtype=bool)

        if ot_m.any():
            if season < 2025 and season_type == "REG":
                # Pre-2025 REG: ANY OT TD ends it — all are walk-offs
                walkoff[ot_m] = True
            else:
                # 2025+ REG or any postseason: paired possessions first
                ot_first = ot_m & ~ot_first_poss_done

                # Defensive TD on first possession: walk-off, no Try
                ot_def_td_first = ot_first & (scoring_poss != ot_first_poss_team)
                walkoff[ot_def_td_first] = True

                # After first possession done: sudden-death TDs
                ot_sudden = ot_m & ot_first_poss_done & ~ot_first
                if season_type == "REG":
                    # D66: 2025+ REG sudden death — only walk-off if LEADS
                    ot_sudden_ahead = ot_sudden & (
                        ((scoring_poss == 0) & (score_h + 6 > score_a)) |
                        ((scoring_poss == 1) & (score_a + 6 > score_h))
                    )
                    # Wait — scores already incremented by _score_td. Check current score.
                    ot_sudden_ahead = ot_sudden & (
                        ((scoring_poss == 0) & (score_h > score_a)) |
                        ((scoring_poss == 1) & (score_a > score_h))
                    )
                    walkoff[ot_sudden_ahead] = True
                else:
                    # Postseason sudden death: walk-off if leading
                    ot_sudden_ahead = ot_sudden & (
                        ((scoring_poss == 0) & (score_h > score_a)) |
                        ((scoring_poss == 1) & (score_a > score_h))
                    )
                    walkoff[ot_sudden_ahead] = True

                # First-possession offensive TDs: Try IS attempted (decides ahead/tied)
                # These are NOT walk-offs.

        # ── PAT: only where NOT a walk-off ──
        pat_mask = m & ~walkoff
        _do_pat(pat_mask, scoring_poss)

        # ── Kickoff for regulation TDs ──
        if reg_m.any():
            _do_kickoff(reg_m)
            _check_ko_ret_td(reg_m)

        # ── OT game-over logic (AFTER PAT, so scores reflect the Try) ──
        if ot_m.any():
            if season < 2025 and season_type == "REG":
                # Pre-2025 REG: all OT TDs end it (already flagged as walk-off)
                game_over[ot_m] = True
            else:
                ot_first = ot_m & ~ot_first_poss_done

                # First-possession offensive TD: mark possession done, kick off
                ot_first_off = ot_first & (scoring_poss == ot_first_poss_team)
                ot_first_poss_done[ot_first_off] = True
                if ot_first_off.any():
                    _do_kickoff(ot_first_off)

                # Defensive TD on first possession: game over (already walk-off)
                ot_def_td_first = ot_first & (scoring_poss != ot_first_poss_team)
                ot_first_poss_done[ot_def_td_first] = True
                game_over[ot_def_td_first] = True

                # After both possessions: check score
                ot_sudden = ot_m & ot_first_poss_done & ~ot_first

                if season_type == "REG":
                    # D66: 2025+ REG — end if LEADING, continue if TIED (sudden death)
                    ot_sudden_ahead = ot_sudden & (
                        ((scoring_poss == 0) & (score_h > score_a)) |
                        ((scoring_poss == 1) & (score_a > score_h))
                    )
                    game_over[ot_sudden_ahead] = True

                    # Tied after both possessions: sudden death continues
                    # (next score wins — NOT another round of paired possessions)
                    ot_sudden_tied = ot_sudden & (score_h == score_a)
                    if ot_sudden_tied.any():
                        _do_kickoff(ot_sudden_tied)
                else:
                    # Postseason: end if leading
                    ot_sudden_ahead = ot_sudden & (
                        ((scoring_poss == 0) & (score_h > score_a)) |
                        ((scoring_poss == 1) & (score_a > score_h))
                    )
                    game_over[ot_sudden_ahead] = True
                    # Tied → reset for another round of paired possessions
                    ot_sudden_tied = ot_sudden & (score_h == score_a)
                    if ot_sudden_tied.any():
                        ot_first_poss_done[ot_sudden_tied] = False
                        ot_first_poss_team[ot_sudden_tied] = 1 - scoring_poss[ot_sudden_tied]
                        _do_kickoff(ot_sudden_tied)

    def _dist_idx(d):
        return np.where(d <= 3, 0, np.where(d <= 7, 1, 2)).astype(np.intp)

    def _zone_idx(y):
        # 5A-7: 10-yard zones; yardline_100 in (10k, 10k+10] -> k (0 = inside the 10)
        return np.clip(np.ceil(np.asarray(y, dtype=float) / 10.0) - 1, 0, NZONES - 1).astype(np.intp)

    def _eoh_runoff(gi_arr, sd_arr, yl_snap, ot_names, u_arr, exclude):
        """5A-9 (D31): snaps taken in the end-of-half FG setup (Q2/Q4/OT, <= 40 s, inside the
        50) draw their runoff from the EOH clock cells measured in that state — real teams
        spike, kneel to centre or call timeout, so the elapsed to the next snap is ~5-7 s and
        the Kaplan-Meier plateau (99 s) means the half expires. No pace scaling, no floor,
        and no separate timeout draw (the measured elapsed already contains the timeouts).
        Returns the boolean mask (over gi_arr) of snaps handled here."""
        in_fgs = (fgs_state[gi_arr] != "") & ((fgs_state[gi_arr] != "ot_sd") | (clock[gi_arr] <= 180.0))
        m_eoh = (((qtr[gi_arr] == 2) | (qtr[gi_arr] >= 4)) & (clock[gi_arr] <= 40.0)
                 & (np.asarray(yl_snap) <= 50) & ~game_over[gi_arr] & ~exclude & ~in_fgs)
        m_fgs = in_fgs & ~game_over[gi_arr] & ~exclude
        m = m_eoh | m_fgs
        if not m.any():
            return m
        st = eoh_state(qtr[gi_arr][m], sd_arr[m])
        q_m = qtr[gi_arr][m]
        st = np.where(st == "fg_useful", np.where(q_m == 2, "fg_useful_Q2", "fg_useful_Q4"), st)
        idx = np.where(m)[0]
        for j, s_ in zip(idx, st):
            gi = gi_arr[j]
            if m_fgs[j]:
                sbf = _fgs_sec_bucket(float(clock[gi]))
                sb = f"fgs_{sbf}"
                cq = clock_q.get((ot_names[j], sb, "fgs"))
                if cq is None:
                    cq = clock_q.get(("all", sb, "fgs"))
                if cq is None:
                    cq = clock_q.get((ot_names[j], "fgs_all", "fgs"))
                if cq is None:
                    cq = clock_q.get(("all", "fgs_all", "fgs"))
                ev_fgs_runoff[gi] += 1
                if sbf in ("0-20", "21-40") and cq is not None:
                    # next-snap time cell: elapsed = time now - time at the next snap
                    nxt = float(np.interp(u_arr[gi], xs101_top, cq))
                    el = float(np.clip(float(clock[gi]) - nxt, 1.0, float(clock[gi])))
                    clock[gi] -= np.float32(el); ev_clock_used[gi] += np.float32(el)
                    continue
            else:
                key_state = f"eoh_{s_}"
                cq = clock_q.get((ot_names[j], key_state, "eoh"))
                if cq is None:
                    cq = clock_q.get(("all", key_state, "eoh"))
                if cq is None:
                    cq = clock_q.get(("all", "eoh_all", "eoh"))
                ev_eoh_runoff[gi] += 1
            if cq is None:
                raise RuntimeError("clock table has no EOH / FG-setup runoff cells")
            el = float(np.interp(u_arr[gi], xs101_top, cq))
            clock[gi] -= np.float32(el); ev_clock_used[gi] += np.float32(el)
        return m

    def _apply_timeouts(gi_arr, ot_idx_arr, sd_arr, u_arr, running_codes=(1, 2), de_code=3, stop_code=0, skip=None):
        """5A-7: after a scrimmage play in the last 3:00 of Q2/Q4, the offence or the
        defence may call a timeout (empirical policy); a timeout makes the runoff to the
        next snap the stopped-clock kind (`stop_code`). Pass encoding: 0 incomplete /
        1 first down / 2 complete in bounds / 3 drive-ending. Rush encoding: 0 first down /
        1 run / 2 drive-ending / 3 stopped (timeout)."""
        if to_lookup is None:
            return
        # 5A-11 (D39): overtime's last 3:00 is the same situation as Q4's (the period ends
        # the game); the policy table's Q4 rows are used for it
        late = ((qtr[gi_arr] == 2) | (qtr[gi_arr] >= 4)) & (clock[gi_arr] <= 180) & \
               ~game_over[gi_arr] & (ot_idx_arr != de_code)
        if skip is not None:
            late &= ~skip
        for j in np.where(late)[0]:
            gi = gi_arr[j]
            q = min(int(qtr[gi]), 4); sb = _to_sec_bucket(float(clock[gi]))
            sd_j = int(sd_arr[j])
            st = "trail" if sd_j < 0 else ("tied" if sd_j == 0 else "lead")
            run_s = "True" if ot_idx_arr[j] in running_codes else "False"
            def _p(side):
                return (to_lookup.get((side, q, sb, st, run_s)) or
                        to_lookup.get((side, q, sb, st, "any")) or
                        to_lookup.get((side, q, sb, "all", "any"), 0.0))
            p_off = _p("off") if to_rem[poss[gi], gi] > 0 else 0.0
            p_def = _p("def") if to_rem[1 - poss[gi], gi] > 0 else 0.0
            u = u_arr[gi]
            if u < p_off:
                to_rem[poss[gi], gi] -= 1; ev_to_off[gi] += 1; ot_idx_arr[j] = stop_code
            elif u < p_off + p_def:
                to_rem[1 - poss[gi], gi] -= 1; ev_to_def[gi] += 1; ot_idx_arr[j] = stop_code

    # ═══════════════════════════════════════════════════════════════════════════
    # MAIN LOOP
    # ═══════════════════════════════════════════════════════════════════════════

    MAX_STEPS = 800  # Safety cap; hitting this is an error, not a stopping condition
    for step in range(MAX_STEPS):
        alive = ~game_over
        if not alive.any():
            break

        # RNG insensitivity: optionally insert a dummy draw to verify
        # that adding one extra draw cannot shift statistics
        if _dummy_draw:
            rng.random(N)

        # --- Pre-draw all decision uniforms (constant consumption per step) ---
        # Each decision gets its own independent U(0,1) vector of size N.
        # Drawing a fixed count per step makes the sim insensitive to RNG
        # stream shifts (inserting a dummy draw cannot change statistics).
        u_4th = rng.random(N)
        u_eoh = rng.random(N)  # 5A-6: end-of-half FG decision on downs 1-3
        u_to = rng.random(N)     # 5A-7: timeout decision after the snap
        u_kneel = rng.random(N)  # 5A-7: kneel decision
        u_spike = rng.random(N)  # 5A-9 (D34): spike decision
        u_punt_net = rng.random(N)
        u_fg_mk = rng.random(N)
        u_pen = rng.random(N)
        u_pen_side = rng.random(N)
        u_pen_auto = rng.random(N)
        u_pen_yds = rng.random(N)   # 5A-4: penalty yardage draw
        u_safety = rng.random(N)    # 5A-4: conditional safety draw
        u_call = rng.random(N)
        u_sack = rng.random(N)
        u_int_ = rng.random(N)
        u_comp = rng.random(N)
        u_succ = rng.random(N)
        u_yards = rng.random(N)
        u_pfum = rng.random(N)
        u_int_dtd = rng.random(N)
        u_int_ret = rng.random(N)
        u_int_air = rng.random(N)  # 5S: draw for INT air-yards (catch point)
        u_pfum_dtd = rng.random(N)
        u_pfum_ret = rng.random(N)
        u_pclock = rng.random(N)
        u_rfum = rng.random(N)
        u_rsucc = rng.random(N)
        u_ryards = rng.random(N)
        u_rfum_dtd = rng.random(N)
        u_rfum_ret = rng.random(N)
        u_rclock = rng.random(N)
        u_pat = rng.random(N)
        u_xp = rng.random(N)     # 5A-10 (D36): XP make
        u_2pt = rng.random(N)    # 5A-10 (D36): 2-pt conversion
        u_ot = rng.random(N)
        u_punt_td = rng.random(N)
        u_ko_td = rng.random(N)
        u_target = rng.random(N)
        u_rusher = rng.random(N)
        u_epa_pass = rng.random(N)   # FIX 7: per-play dither for EPA shift
        u_epa_rush = rng.random(N)

        # --- Quarter / half / game end ---
        time_up = alive & (clock <= 0)
        if time_up.any():
            # Advance quarter — carry over negative clock so time isn't lost
            can_advance = time_up & (qtr < 4)
            qtr[can_advance] += 1
            clock[can_advance] += 900.0  # Add 900, preserving any negative overshoot

            # Halftime (entering Q3)
            ht = time_up & (qtr == 3) & ~half_recorded
            if ht.any():
                score_h_1h[ht] = score_h[ht]
                score_a_1h[ht] = score_a[ht]
                half_recorded[ht] = True
                _dl_result[ht] = _DLR_ENDHALF
                # FIX 6c: 2nd-half kickoff to the team that did NOT receive opening
                poss[ht] = 1 - opening_receiver[ht]
                yl[ht] = ko_start
                _new_drive(ht)
                to_rem[:, ht] = 3  # 5A-7: timeouts reset for the second half

            # End of regulation (Q4 over) — only if clock is STILL <= 0
            # after the quarter advance (not just from the previous quarter ending)
            end_reg = alive & (qtr == 4) & (clock <= 0)
            if end_reg.any():
                tied = end_reg & (score_h == score_a)
                not_tied = end_reg & ~tied
                _dl_result[not_tied] = _DLR_ENDGAME
                game_over[not_tied] = True

                # OT
                if tied.any():
                    _dl_result[tied] = _DLR_ENDHALF  # end of regulation, going to OT
                    ot_flag[tied] = 1
                    qtr[tied] = 5
                    clock[tied] = 600.0
                    to_rem[:, tied] = 2  # 5A-7: two timeouts each in overtime
                    ct = (u_ot >= 0.5).astype(np.int8)
                    poss[tied] = ct[tied]
                    ot_first_poss_team[tied] = ct[tied]
                    yl[tied] = ko_start  # FIX 6d
                    _new_drive(tied)

            # End of OT — only if clock is still <= 0
            end_ot = alive & (qtr >= 5) & (clock <= 0)
            if end_ot.any():
                if season_type == "REG":
                    # Regular season: ties allowed
                    _dl_result[end_ot] = _DLR_ENDGAME
                    game_over[end_ot] = True
                else:
                    # FIX 6b: Postseason — no ties, additional OT periods
                    still_tied = end_ot & (score_h == score_a)
                    not_tied_ot = end_ot & ~still_tied
                    _dl_result[not_tied_ot] = _DLR_ENDGAME
                    game_over[not_tied_ot] = True
                    # Additional period for still-tied postseason games
                    if still_tied.any():
                        qtr[still_tied] += 1
                        clock[still_tied] = 600.0
                        # Flip possession for new OT period
                        ot_first_poss_team[still_tied] = 1 - ot_first_poss_team[still_tied]
                        poss[still_tied] = ot_first_poss_team[still_tied]
                        ot_first_poss_done[still_tied] = False
                        yl[still_tied] = ko_start
                        _new_drive(still_tied)
            # FIX 1: removed batch-wide continue — fall through to plays

        alive = ~game_over
        if not alive.any():
            break

        # 5A-8 diag: snapshot the score state the first time the Q4 clock reads <= 5:00 / <= 2:00
        c300 = alive & (qtr == 4) & (clock <= 300.0) & ~_cap300
        if c300.any():
            m_q4_300[c300] = score_h[c300] - score_a[c300]
            poss_q4_300[c300] = poss[c300]
            _cap300[c300] = True
        c120 = alive & (qtr == 4) & (clock <= 120.0) & ~_cap120
        if c120.any():
            m_q4_120[c120] = score_h[c120] - score_a[c120]
            poss_q4_120[c120] = poss[c120]
            yl_q4_120[c120] = yl[c120]
            _cap120[c120] = True

        # --- Kneel-down: leading team can run out the clock ---
        # Each kneel takes ~40 seconds. A team can kneel out if:
        #   remaining_clock <= kneels_available * 40
        # kneels_available = (4 - down) + 1 (current down counts as a kneel)
        # Simplified timeout model: the opponent has ~1.5 timeouts left in
        # Q4 on average (3 per half, ~1.5 used by late Q4). Each timeout
        # stops the clock after a kneel, negating one kneel's clock burn.
        # Effective kneels = kneels_available - 1.5 (rounded to 1 to be
        # conservative — ensures we don't kneel when the opponent can stop us).
        score_diff_poss = np.where(poss == 0, score_h - score_a, score_a - score_h)
        # 5A-7: the 40-second / "opponent has ~1.5 timeouts" heuristic is replaced by the
        # empirical kneel table (qtr x seconds x DEFENCE TIMEOUTS REMAINING x down x
        # situation) and the empirical timeout policy. A kneel is a play: -1 yard, next
        # down, running-clock runoff from the clock table, defence may call a timeout.
        can_kneel = np.zeros(N, dtype=bool)
        fgs_state = np.full(N, "", dtype=object)
        if fgs_lookup is not None:
            fgs_state = fg_setup_state(qtr, score_diff_poss, yl, clock, down)
            # 5A-11 (D40): overtime — the first possession is played for the touchdown (no
            # FG-setup behaviour); after it, sudden death inside the 35 is its own state
            in_ot = qtr >= 5
            fgs_state[in_ot & ~ot_first_poss_done] = ""
            fgs_state[in_ot & ot_first_poss_done & (yl <= 35) & (down <= 3) & alive] = "ot_sd"
        if kneel_lookup is not None:
            fgs_m = alive & (clock > 0) & (fgs_state != "")
            kn_cand = alive & (down < 4) & (clock > 0) & (clock <= 180) & (
                ((qtr == 4) & (score_diff_poss > 0)) | (qtr == 2))
            for i in np.where(kn_cand | fgs_m)[0]:
                q = int(qtr[i]); cl = float(clock[i])
                dt = str(int(to_rem[1 - poss[i], i]))
                dn = str(int(down[i]))
                if fgs_m[i]:
                    # 5A-9 (D33): kneel to centre the ball for the field goal
                    dt3 = "2+" if to_rem[1 - poss[i], i] >= 2 else dt
                    sbf = _fgs_sec_bucket(cl)
                    if fgs_state[i] == "ot_sd":
                        row = fgs_lookup.get(("ot_sd", "any", "any", "any"))
                    else:
                        row = (fgs_lookup.get(("any", sbf, dt3, "any")) or
                               fgs_lookup.get(("any", "any", dt3, "any")) or
                               fgs_lookup.get(("any", "any", "any", "any")))
                    pk = row[0]
                else:
                    sit = "lead" if q == 4 else ("own" if yl[i] >= 60 else "opp")
                    sb = _kneel_sec_bucket(cl)
                    pk = kneel_lookup.get((q, sb, dt, dn, sit))
                    if pk is None:
                        pk = kneel_lookup.get((q, sb, dt, "any", sit))
                    if pk is None:
                        pk = kneel_lookup.get((q, sb, "any", "any", sit), 0.0)
                if u_kneel[i] < pk:
                    can_kneel[i] = True
            if can_kneel.any():
                for i in np.where(can_kneel)[0]:
                    ev_kneels[i] += 1
                    n_plays[i] += 1; _dl_plays[i] += 1; _dl_yards[i] -= 1.0
                    yl[i] = min(yl[i] + 1.0, 99.0)
                    dist[i] = dist[i] + 1.0
                    down[i] += 1
                    if fgs_m[i] and fgs_kneel_q is not None:
                        # 5A-9 (D33): kneel to the kick — measured next-snap time (<= 40 s)
                        # or measured elapsed (> 40 s); the defence timeout is inside the data
                        if clock[i] <= 40.0:
                            nxt = float(np.interp(u_pclock[i], xs101_top, fgs_kneel_q["next_sec"]))
                            el = max(float(clock[i]) - nxt, 0.0)
                        else:
                            el = float(np.interp(u_pclock[i], xs101_top, fgs_kneel_q["elapsed"]))
                        clock[i] -= np.float32(el); ev_clock_used[i] += np.float32(el)
                        ev_fgs_runoff[i] += 1
                        continue
                    # clock: running-clock runoff for this score state / period
                    sd_i = int(score_diff_poss[i])
                    ss_i = ("trail9+" if sd_i <= -9 else "trail1-8" if sd_i <= -1 else
                            "tied" if sd_i == 0 else "lead1-8" if sd_i <= 8 else "lead9+")
                    cp_i = ("Q2_late" if (qtr[i] == 2 and clock[i] <= 120) else
                            "Q4_late" if (qtr[i] >= 4 and clock[i] <= 120) else
                            "Q4_mid_b" if (qtr[i] == 4 and clock[i] <= 180) else
                            "Q4_mid_a" if (qtr[i] == 4 and clock[i] <= 300) else "normal")
                    ot_name = "complete_inbounds"
                    # defence timeout after the kneel?
                    if to_lookup is not None and to_rem[1 - poss[i], i] > 0 and clock[i] <= 180:
                        st_i = "trail" if sd_i < 0 else ("tied" if sd_i == 0 else "lead")
                        q_i = min(int(qtr[i]), 4)  # 5A-11 (D39): OT uses the Q4 rows
                        p_def = (to_lookup.get(("def", q_i, _to_sec_bucket(float(clock[i])), st_i, "True"))
                                 or to_lookup.get(("def", q_i, _to_sec_bucket(float(clock[i])), st_i, "any"))
                                 or to_lookup.get(("def", q_i, _to_sec_bucket(float(clock[i])), "all", "any"), 0.0))
                        if u_to[i] < p_def:
                            to_rem[1 - poss[i], i] -= 1; ev_to_def[i] += 1
                            ot_name = "incomplete"  # clock stopped
                    cq = clock_q.get((ot_name, ss_i, cp_i))
                    # 5M: Q4_mid_a/Q4_mid_b fall back to unsplit Q4_mid
                    if cq is None and cp_i in ("Q4_mid_a", "Q4_mid_b"):
                        cq = clock_q.get((ot_name, ss_i, "Q4_mid"))
                    if cq is None:
                        cq = clock_q.get((ot_name, f"p_{ss_i}", "all"))
                    if cq is None:
                        cq = clock_q.get((ot_name, False), np.full(101, 30.0))
                    pace_i = (ctx["t0_pace"] if poss[i] == 0 else ctx["t1_pace"]) / ctx["lg_pace"]
                    el = max(float(np.interp(u_pclock[i], xs101_top, cq)) * pace_i, 3.0)
                    clock[i] -= np.float32(el); ev_clock_used[i] += np.float32(el)

        # --- 4th down decision ---
        # Exclude kneeling sims and sims with expired clock from play execution
        alive = alive & ~can_kneel & (clock > 0)
        is_4th = alive & (down == 4)
        punt_m = np.zeros(N, dtype=bool)
        fg_m = np.zeros(N, dtype=bool)

        # --- 5A-6: end-of-half FG on downs 1-3 (empirical table J) ---
        # Real teams kick before the half expires on any down; the engine only
        # considered FGs on 4th down (measured deficit: 0.33 non-4th FG att/game).
        spiked = np.zeros(N, dtype=bool)
        if eoh_lookup is not None:
            eoh_cand = alive & (down < 4) & ((qtr == 2) | (qtr >= 4)) & (clock <= 40) & (yl <= 50)  # 5A-9: OT included
            if eoh_cand.any():
                ev_eoh_snaps[eoh_cand] += 1
                for i in np.where(eoh_cand)[0]:
                    sd = int(score_diff_poss[i])
                    if qtr[i] == 2:
                        st = "fg_useful"
                    elif -3 <= sd <= 0:
                        st = "fg_useful"
                    elif sd > 0:
                        st = "Q4_lead"
                    else:
                        st = "Q4_trail4+"
                    sec_b, yl_b = _eoh_bucket(float(clock[i]), float(yl[i]))
                    p_fg_e = eoh_lookup.get((st, sec_b, yl_b))
                    if p_fg_e is None:
                        p_fg_e = eoh_lookup.get((st, sec_b, "all"), 0.0)
                    # 5A-9 (D34): spike first; the FG rate in the table was measured over all
                    # snaps including spikes, so conditional on not spiking it is p_fg / (1 - p_spike)
                    p_sp = 0.0
                    if st == "fg_useful" and spike_lookup is not None:
                        half = "Q2" if qtr[i] == 2 else "Q4"
                        p_sp = spike_lookup.get((half, sec_b), spike_lookup.get(("all", sec_b), 0.0))
                        if u_spike[i] < p_sp:
                            spiked[i] = True
                            ev_spikes[i] += 1
                            n_plays[i] += 1; _dl_plays[i] += 1
                            down[i] += 1
                            clock[i] -= np.float32(1.0); ev_clock_used[i] += np.float32(1.0)
                            continue
                        p_fg_e = min(p_fg_e / (1.0 - p_sp), 1.0) if p_sp < 1.0 else p_fg_e
                    if u_eoh[i] < p_fg_e:
                        fg_m[i] = True
                        ev_fg_non4th[i] += 1

        # 5A-11 (D40): OT sudden death inside the 35 — kick on any down at the measured rate
        if fgs_lookup is not None:
            ot_sd_cand = alive & ~spiked & (down < 4) & (fgs_state == "ot_sd") & ~fg_m & ~can_kneel
            if ot_sd_cand.any():
                row = fgs_lookup.get(("ot_sd", "any", "any", "any"))
                if row is not None and row[2] > 0:
                    kick = ot_sd_cand & (u_eoh < row[2])
                    fg_m[kick] = True
                    ev_fg_non4th[kick] += 1
        alive = alive & ~spiked
        is_4th = is_4th & ~spiked
        if is_4th.any() or fg_m.any():
            idx4 = np.where(is_4th)[0]

            for i in idx4:
                yd = int(round(dist[i]))  # 5A-3: round, not truncate (FIX 7 float dist)
                yd = max(yd, 1)
                y = int(round(yl[i]))
                sd = int(score_diff_poss[i])
                qt = int(qtr[i])
                cl = float(clock[i])

                # 5A-9 (D30): one bucketing shared with the table builder; the table is a
                # complete grid, so the lookup is exact and there is no fallback chain.
                yd_b, yl_b, sc_fine, qt_fine = (str(v[0]) for v in fourth_down_keys([yd], [y], [sd], [qt], [cl]))
                probs = fd_lookup.get((yd_b, yl_b, sc_fine, qt_fine))
                if probs is None:
                    raise RuntimeError(f"fourth_down table has no cell for {(yd_b, yl_b, sc_fine, qt_fine)}")

                p_go, p_punt, p_fg = probs

                # 5A-3: Team 4th-down GOE override — logit-additive, like PROE.
                # GOE is in percentage points. Applied Q1-Q3 only (late-game
                # decisions are situation-driven, not style-driven).
                if qt <= 3:
                    ti = poss[i]
                    goe = ctx[f"t{ti}_4th_goe"]
                    if abs(goe) > 0.01:
                        p_go_adj = _sigmoid(_logit(np.clip(p_go, 0.01, 0.99)) + goe / 100.0)
                        p_go_adj = float(np.clip(p_go_adj, 0.0, 0.95))
                        leftover = 1.0 - p_go_adj
                        if p_punt + p_fg > 0:
                            scale = leftover / (p_punt + p_fg)
                            p_punt *= scale
                            p_fg *= scale
                        else:
                            p_punt = leftover / 2
                            p_fg = leftover / 2
                        p_go = p_go_adj

                r = u_4th[i]
                if r < p_go:
                    ev_4th_go[i] += 1  # Go for it — normal play
                    dec = "go"
                elif r < p_go + p_punt:
                    punt_m[i] = True
                    dec = "punt"
                else:
                    fg_m[i] = True
                    dec = "fg"
                if _DEBUG_4TH is not None:
                    _DEBUG_4TH.append((yd_b, yl_b, sc_fine, qt_fine, dec))

            # Execute punts
            if punt_m.any():
                ev_punts[punt_m] += 1
                # Punt net yards
                for i in np.where(punt_m)[0]:
                    y = int(yl[i])
                    if y <= 10:
                        zn = "rz10"
                    elif y <= 20:
                        zn = "opp20"
                    elif y <= 60:
                        zn = "midfield"
                    else:
                        zn = "own20"
                    q = punt_lookup.get(zn)
                    if q is None:
                        q = punt_lookup.get("midfield", np.full(101, 42.0))
                    net = np.interp(u_punt_net[i], np.linspace(0, 1, 101), q)
                    # FIX 6f: removed unreachable touchback branch (clip already ensures >=1);
                    # touchbacks are encoded in the punt net yards distribution from tables.py
                    yl[i] = float(np.clip(100 - (yl[i] - net), 1, 99))
                # Punt return TD (empirical rate from table G)
                punt_ret_td_m = punt_m.copy()
                for i in np.where(punt_m)[0]:
                    if u_punt_td[i] < p_punt_ret_td:
                        # Return team scores a TD
                        ret_team = 1 - poss[i]  # Receiving team
                        m1 = np.zeros(N, dtype=bool); m1[i] = True
                        ev_punt_ret_td[i] += 1  # 5A-5
                        _dl_result[i] = _DLR_PUNT  # drive ended by punt (ret TD is separate)
                        poss[i] = 1 - poss[i]
                        _handle_td(m1, np.full(N, ret_team, dtype=np.int8))
                        punt_ret_td_m[i] = False  # Don't do normal punt handling
                normal_punt = punt_m & punt_ret_td_m
                _dl_result[normal_punt] = _DLR_PUNT
                poss[normal_punt] = 1 - poss[normal_punt]
                _new_drive(normal_punt)
                # Punt clock is captured in the cross-play elapsed table

            # Execute FGs
            if fg_m.any():
                ev_fg_att[fg_m] += 1
                fg_dist_arr = yl[fg_m] + 17
                made_arr = np.zeros(fg_m.sum(), dtype=bool)
                fg_idx = np.where(fg_m)[0]
                for j, i in enumerate(fg_idx):
                    d = int(np.clip(fg_dist_arr[j], 18, 69))
                    base_rate = fg_lookup.get(d, 0.3)
                    # Kicker adjustment
                    ti = poss[i]
                    if d < 30:
                        bk = "<30"
                    elif d < 40:
                        bk = "30-39"
                    elif d < 50:
                        bk = "40-49"
                    else:
                        bk = "50+"
                    team_rate = ctx[f"t{ti}_fg"][bk]
                    lg_rate = {"<30": 0.98, "30-39": 0.93, "40-49": 0.78, "50+": 0.68}[bk]
                    adj_rate = np.clip(base_rate * team_rate / max(lg_rate, 0.01), 0, 0.999)
                    made_arr[j] = u_fg_mk[i] < adj_rate

                made_full = np.zeros(N, dtype=bool)
                made_full[fg_idx[made_arr]] = True
                miss_full = fg_m & ~made_full

                # Score
                ev_fg_made[made_full] += 1
                ev_fg_dist_sum[fg_idx] += fg_dist_arr
                score_h[made_full & (poss == 0)] += 3
                score_a[made_full & (poss == 1)] += 3

                # OT: FG handling
                ot_fg = made_full & (qtr >= 5)
                # First possession FG: other team gets a chance (all eras)
                ot_first_scoring = ot_fg & (poss == ot_first_poss_team) & ~ot_first_poss_done
                ot_first_poss_done[ot_first_scoring] = True
                # Second possession or later: a FG ends the game only if the kicking team
                # now leads. 5A-11 (D38): matched field goals (3-3 after both possessions)
                # used to END the game as a tie in the regular season; the rule is sudden
                # death from there (2 of 12 real first-drive FGs were matched, both games
                # went on). Postseason keeps its own branch.
                ot_second = ot_fg & ~ot_first_scoring
                if season_type == "REG":
                    ot_leading_reg = ot_second & (
                        ((poss == 0) & (score_h > score_a)) |
                        ((poss == 1) & (score_a > score_h))
                    )
                    game_over[ot_leading_reg] = True
                else:
                    # Postseason: game ends ONLY if the scoring team is ahead
                    ot_leading = ot_second & (
                        ((poss == 0) & (score_h > score_a)) |
                        ((poss == 1) & (score_a > score_h))
                    )
                    game_over[ot_leading] = True
                    # If still tied after matching FGs, extend to another possession
                    ot_still_tied = ot_second & (score_h == score_a)
                    # Reset for another round of possessions
                    ot_first_poss_done[ot_still_tied] = False
                    ot_first_poss_team[ot_still_tied] = 1 - poss[ot_still_tied]

                # Kickoff only for non-game-over sims
                _dl_result[made_full] = _DLR_FGM
                ko_eligible = made_full & ~game_over
                _do_kickoff(ko_eligible)
                _check_ko_ret_td(ko_eligible & (qtr < 5))
                # FG/kickoff clock captured in cross-play elapsed table

                # Miss: opponent gets ball
                if miss_full.any():
                    _dl_result[miss_full] = _DLR_FGMISS
                    yl[miss_full] = np.clip(100 - yl[miss_full], 20, 99)
                    poss[miss_full] = 1 - poss[miss_full]
                    _new_drive(miss_full)

        # --- Scrimmage plays (non-punt/FG) ---
        # 5A-9 (D32): re-derive from game_over (punt/FG blocks can end games) but KEEP the
        # kneel and expired-clock exclusions. Until 5A-9 this line reset `alive` to
        # ~game_over, so every kneel was followed by a scrimmage snap in the same
        # iteration (a 3rd-down kneel became a 4th-down play with no decision -> turnover
        # on downs) and snaps were run with the clock already at zero.
        alive = ~game_over & ~can_kneel & ~spiked & (clock > 0)
        playing = alive & ~punt_m & ~fg_m
        if not playing.any():
            continue

        n_live = playing.sum()
        live_idx = np.where(playing)[0]

        # --- Penalty (no-play) check ---
        # Total accepted penalty rate ~8.1% (no-play 6.7% + on-scrimmage 1.4%).
        # Offense penalties (61.5%): move back ~7 yds, replay down.
        # Defense penalties (38.5%): advance ~9 yds, 72.5% auto first down.
        # Defensive penalties are a real source of yards and first downs;
        # their absence would lower scoring by ~3 first downs/game.
        pen_nop = playing & (u_pen < p_penalty_nop)
        if pen_nop.any():
            if _pen_cats_enabled:
                # 5A-4: Category-based penalty model
                pen_idx = np.where(pen_nop)[0]
                # Determine penalty category for each flagged sim
                cat_idx = np.searchsorted(_pen_cdf, u_pen_side[pen_idx])
                cat_idx = np.clip(cat_idx, 0, len(_pen_cat_order) - 1)

                is_off = _pen_is_off[cat_idx]
                off_pen = np.zeros(N, dtype=bool)
                def_pen = np.zeros(N, dtype=bool)
                off_pen[pen_idx[is_off]] = True
                def_pen[pen_idx[~is_off]] = True

                # Draw yardage from category-specific quantile distribution
                pen_yds = np.zeros(N, dtype=np.float32)
                for ci in range(len(_pen_cat_order)):
                    cm = pen_idx[cat_idx == ci]
                    if len(cm) == 0:
                        continue
                    yds_drawn = np.interp(u_pen_yds[cm], xs101_pen, _pen_yds_q[ci])
                    pen_yds[cm] = yds_drawn

                # DPI: spot-of-foul — cap yardage at distance to goal line
                dpi_mask = np.zeros(N, dtype=bool)
                dpi_sims = pen_idx[cat_idx == _pen_dpi_idx]
                dpi_mask[dpi_sims] = True
                # DPI yardage = min(drawn yardage, yardline - 1)
                if dpi_mask.any():
                    pen_yds[dpi_mask] = np.minimum(pen_yds[dpi_mask],
                                                    yl[dpi_mask] - 1)
                    pen_yds[dpi_mask] = np.maximum(pen_yds[dpi_mask], 1)

                # Offense penalty: move back by drawn yardage, replay down
                if off_pen.any():
                    yl_before = yl[off_pen].copy()
                    yl[off_pen] = np.clip(yl[off_pen] + pen_yds[off_pen], 1, 99)
                    # Yards-to-go rises by the yards actually marched off (clipped at 99)
                    dist[off_pen] = dist[off_pen] + (yl[off_pen] - yl_before)

                # Defense penalty: advance by drawn yardage
                auto_1st = np.zeros(N, dtype=bool)
                if def_pen.any():
                    # Check for penalty reaching end zone
                    pen_td = def_pen.copy()
                    pen_td[def_pen] = yl[def_pen] <= pen_yds[def_pen]
                    pen_no_td = def_pen & ~pen_td

                    yl[pen_no_td] = np.clip(yl[pen_no_td] - pen_yds[pen_no_td], 1, 99)
                    # Auto first down: per-category rate
                    auto_rate = np.zeros(N)
                    for ci in range(len(_pen_cat_order)):
                        cm = pen_idx[cat_idx == ci]
                        auto_rate[cm] = _pen_auto_first[ci]
                    auto_1st = pen_no_td & (u_pen_auto < auto_rate)
                    # Non-auto-first: still award first down if yardage >= distance
                    yds_fd = pen_no_td & ~auto_1st & (pen_yds >= dist)
                    auto_1st = auto_1st | yds_fd
                    down[auto_1st] = 1
                    dist[auto_1st] = np.minimum(10, yl[auto_1st])
                    ev_first_downs[auto_1st] += 1
                    non_auto_def = pen_no_td & ~auto_1st
                    dist[non_auto_def] = np.maximum(1, dist[non_auto_def] - pen_yds[non_auto_def])
                    # Penalty reaching end zone: ball at 1, first and goal
                    if pen_td.any():
                        yl[pen_td] = 1
                        down[pen_td] = 1
                        dist[pen_td] = 1
                        ev_first_downs[pen_td] += 1

                ev_penalties[pen_nop] += 1
                ev_pen_offense[off_pen] += 1
                ev_pen_defense[def_pen] += 1
                ev_pen_off_yds[off_pen] += pen_yds[off_pen]
                ev_pen_def_yds[def_pen] += pen_yds[def_pen]
                ev_fd_penalty[auto_1st] += 1
                if def_pen.any() and pen_td.any():
                    ev_fd_penalty[pen_td] += 1
            else:
                # Legacy penalty model (pre-5A-4)
                off_pen = pen_nop & (u_pen_side < p_off_pen)
                def_pen = pen_nop & ~off_pen
                yl_before_leg = yl[off_pen].copy()
                yl[off_pen] = np.clip(yl[off_pen] + 7, 1, 99)
                dist[off_pen] = dist[off_pen] + (yl[off_pen] - yl_before_leg)
                pen_td = def_pen.copy()
                pen_td[def_pen] = yl[def_pen] <= 9
                pen_no_td = def_pen & ~pen_td
                yl[pen_no_td] = np.clip(yl[pen_no_td] - 9, 1, 99)
                auto_1st = pen_no_td & (u_pen_auto < p_auto_first)
                down[auto_1st] = 1
                dist[auto_1st] = np.minimum(10, yl[auto_1st])
                ev_first_downs[auto_1st] += 1
                non_auto_def = pen_no_td & ~auto_1st
                dist[non_auto_def] = np.maximum(1, dist[non_auto_def] - 9)
                if pen_td.any():
                    yl[pen_td] = 1
                    down[pen_td] = 1
                    dist[pen_td] = 1
                    ev_first_downs[pen_td] += 1
                ev_penalties[pen_nop] += 1
                ev_pen_offense[off_pen] += 1
                ev_pen_defense[def_pen] += 1
                ev_pen_off_yds[off_pen] += 7.0
                ev_pen_def_yds[def_pen] += 9.0
                ev_fd_penalty[auto_1st] += 1
                ev_fd_penalty[pen_td] += 1
            playing = playing & ~pen_nop

        if not playing.any():
            continue

        # --- Pre-play safety at deep field positions (5A-4 mechanism, 5A-7 rates) ---
        # Rates are the measured per-play safety rates from constants.json; the 5A-4
        # hand-typed values scaled by 1/1.84 are gone.
        deep_play = playing & (yl >= 90)
        if deep_play.any():
            p_saf_pre = np.zeros(N)
            p_saf_pre[playing & (yl >= 98)] = p_saf_98
            p_saf_pre[playing & (yl >= 95) & (yl < 98)] = p_saf_95
            p_saf_pre[playing & (yl >= 90) & (yl < 95)] = p_saf_90
            safety_pre = deep_play & (u_safety < p_saf_pre)
            if safety_pre.any():
                for i in np.where(safety_pre)[0]:
                    n_plays[i] += 1; _dl_plays[i] += 1
                    _dl_result[i] = _DLR_SAFETY
                    ev_safeties[i] += 1
                    dt = 1 - poss[i]
                    score_h[i] += 2 * (dt == 0); score_a[i] += 2 * (dt == 1)
                    yl[i] = 75; poss[i] = 1 - poss[i]
                    m = np.zeros(N, dtype=bool); m[i] = True; _new_drive(m)
                playing = playing & ~safety_pre

        if not playing.any():
            continue

        n_live = playing.sum()
        live_idx = np.where(playing)[0]
        ev_late_snaps_q2[live_idx[(qtr[live_idx] == 2) & (clock[live_idx] <= 120)]] += 1  # 5A-6 diag
        ev_late_snaps_q4[live_idx[(qtr[live_idx] == 4) & (clock[live_idx] <= 120)]] += 1  # 5A-6 diag

        # --- Play call ---
        # Build situation bucket for each live sim
        poss_live = poss[live_idx]
        down_live = np.clip(down[live_idx], 1, 4)
        dist_live = dist[live_idx]
        yl_live = yl[live_idx]
        qtr_live = qtr[live_idx]
        sd_live = np.where(poss_live == 0,
                           score_h[live_idx] - score_a[live_idx],
                           score_a[live_idx] - score_h[live_idx])

        # Pass probability — 7 score × 4 clock with 3-level fallback
        clock_live = clock[live_idx]
        d_s = down_live.astype(str)
        di_s = np.where(dist_live <= 3, "short", np.where(dist_live <= 7, "med", "long"))
        dd = np.char.add(np.char.add(d_s, "_"), di_s)

        # Fine score (7-way, matching 4th-down table)
        sc_fine = np.where(sd_live < -8, "trail9+",
                  np.where(sd_live < -3, "trail4-8",
                  np.where(sd_live < 0, "trail1-3",
                  np.where(sd_live == 0, "tied",
                  np.where(sd_live <= 3, "lead1-3",
                  np.where(sd_live <= 8, "lead4-8", "lead9+"))))))
        # Fine clock (4-way)
        cl_fine = np.where((qtr_live == 2) & (clock_live <= 120), "Q2<2",
                  np.where(qtr_live <= 3, "Q1-3",
                  np.where(clock_live > 300, "Q4>5",
                  np.where(clock_live > 120, "Q4_2-5", "Q4<2"))))
        # Coarse fallbacks
        sc_coarse = np.where(sd_live < -8, "trail9",
                    np.where(sd_live <= 8, "within8", "lead9"))
        cl_coarse = np.where(qtr_live <= 3, "Q1-3", "Q4")

        # Level 0: fine score × fine clock
        bkt0 = np.char.add(np.char.add(dd, "_"),
                           np.char.add(np.char.add(sc_fine, "_"), cl_fine))
        # Level 1: coarse score × fine clock (c_ prefix)
        bkt1 = np.char.add(np.char.add(dd, "_c_"),
                           np.char.add(np.char.add(sc_coarse, "_"), cl_fine))
        # Level 2: coarse score × coarse clock
        bkt2 = np.char.add(np.char.add(dd, "_"),
                           np.char.add(np.char.add(sc_coarse, "_"), cl_coarse))

        # FIX 5: track fallback count
        lg_xpass_list = []
        for b0, b1, b2 in zip(bkt0, bkt1, bkt2):
            if b0 in pc_lookup:
                lg_xpass_list.append(pc_lookup[b0])
            elif b1 in pc_lookup:
                lg_xpass_list.append(pc_lookup[b1])
                _fallback_count += 1
            elif b2 in pc_lookup:
                lg_xpass_list.append(pc_lookup[b2])
                _fallback_count += 1
            else:
                # A4: three-level miss raises. The playcall table must have
                # parent-pooled entries for every engine key combination.
                raise KeyError(
                    f"Playcall three-level miss: L0={b0} L1={b1} L2={b2}. "
                    f"Rebuild tables with parent pooling."
                )
        lg_xpass = np.array(lg_xpass_list)
        team_proe = np.empty(n_live)
        for ti in [0, 1]:
            tm = poss_live == ti
            sit_dict = ctx[f"t{ti}_sit_proe"]
            overall = ctx[f"t{ti}_proe"]
            vals = []
            for b in bkt2[tm]:
                v = sit_dict.get(b)
                if v is None:
                    _sit_proe_miss += 1
                    vals.append(overall)
                else:
                    vals.append(v)
            team_proe[tm] = np.array(vals)
        p_pass = _sigmoid(_logit(lg_xpass) + team_proe / 100.0)

        # 5A-9 (D33): in the FG-setup state the play call is situation-driven — the
        # measured in-state pass rate replaces the general cell and the team PROE tilt
        if fgs_lookup is not None:
            fgs_live = fgs_state[live_idx]
            for j in np.where(fgs_live != "")[0]:
                gi = live_idx[j]
                sbf = _fgs_sec_bucket(float(clock[gi]))
                if fgs_live[j] == "ot_sd":
                    row = fgs_lookup.get(("ot_sd", "any", "any", "any"))
                else:
                    row = (fgs_lookup.get((fgs_live[j], sbf, "any", "any")) or
                           fgs_lookup.get(("any", sbf, "any", "any")) or
                           fgs_lookup.get(("any", "any", "any", "any")))
                if row is not None and not np.isnan(row[1]):
                    p_pass[j] = row[1]
                    ev_fgs_snaps[gi] += 1

        is_pass = u_call[live_idx] < p_pass

        # Table lookup indices
        di_arr = _dist_idx(dist_live)
        zi_arr = _zone_idx(yl_live)

        # --- PASS PLAYS (vectorised) ---
        pm = is_pass
        n_p = pm.sum()
        if n_p > 0:
            p_idx = np.where(pm)[0]  # Indices into live arrays
            g_idx = live_idx[p_idx]   # Global indices

            d_p = down_live[p_idx]
            di_p = di_arr[p_idx]
            zi_p = zi_arr[p_idx]
            poss_p = poss_live[p_idx]
            yl_p = yl_live[p_idx]

            # Lookup table values
            tbl_sack = pa_sack[d_p, di_p, zi_p]
            tbl_int = pa_int[d_p, di_p, zi_p]
            tbl_comp = pa_comp[d_p, di_p, zi_p]
            tbl_succ = pa_succ[d_p, di_p, zi_p].copy()

            # Apply matchup via logit-additive shift on bucket base rates
            # logit(p_adj) = logit(bucket_rate) + logit(matchup) - logit(league)
            for ti in [0, 1]:
                tm = poss_p == ti
                if tm.any():
                    sack_shift = _logit(ctx[f"t{ti}_sack_rate"]) - _logit(lb["pass_sack_rate"])
                    tbl_sack[tm] = _sigmoid(_logit(tbl_sack[tm]) + sack_shift)
                    int_shift = _logit(ctx[f"t{ti}_int_rate"]) - _logit(lb["pass_int_rate"])
                    tbl_int[tm] = _sigmoid(_logit(tbl_int[tm]) + int_shift)
                    succ_shift = _logit(ctx[f"t{ti}_pass_success"]) - _logit(lb["pass_success"])
                    tbl_succ[tm] = _sigmoid(_logit(tbl_succ[tm]) + succ_shift)
            tbl_sack = np.clip(tbl_sack, 0.001, 0.4)
            tbl_int = np.clip(tbl_int, 0.001, 0.2)
            tbl_comp = np.clip(tbl_comp, 0.2, 0.95)
            tbl_succ = np.clip(tbl_succ, 0.05, 0.95)

            # Each decision uses its own pre-drawn uniform (indexed by global sim)
            u1 = u_sack[g_idx]
            u2 = u_int_[g_idx]
            u3 = u_comp[g_idx]
            u4 = u_succ[g_idx]
            u5 = u_yards[g_idx]
            u_pfum_p = u_pfum[g_idx]

            # Pass fumble: ~0.8% of pass plays, drawn from table
            tbl_pfum = pa_fumble[d_p, di_p, zi_p] if hasattr(pa_fumble, '__getitem__') else np.full(n_p, 0.008)
            pass_fumbled = u_pfum_p < tbl_pfum

            sacked = ~pass_fumbled & (u1 < tbl_sack)
            not_sacked = ~pass_fumbled & ~sacked
            intercepted = not_sacked & (u2 < tbl_int)
            attempt_ok = not_sacked & ~intercepted

            # --- Player allocation: target selection + completion tilt ---
            play_target_idx = np.full(n_p, -1, dtype=np.int32)
            play_target_team = np.full(n_p, -1, dtype=np.int8)
            play_depth = np.zeros(n_p, dtype=np.int8)  # 0=short, 1=deep

            if has_players:
                for ti in [0, 1]:
                    tm = poss_p == ti
                    if not tm.any() or player_ctx[ti] is None:
                        continue
                    pc = player_ctx[ti]
                    tm_idx = np.where(tm)[0]
                    tm_g = g_idx[tm_idx]
                    tm_yl = yl_p[tm_idx]
                    u_tgt = u_target[tm_g]

                    # Select target using per-sim cumsum (dispersed shares)
                    use_rz = tm_yl <= 20
                    tidx = np.empty(len(tm_idx), dtype=np.int32)
                    for jj in range(len(tm_idx)):
                        si = tm_g[jj]
                        cs_row = pc["rz_tgt_cumsum"][si] if use_rz[jj] else pc["tgt_cumsum"][si]
                        tidx[jj] = np.searchsorted(cs_row, u_tgt[jj])
                    tidx = np.clip(tidx, 0, pc["n_players"] - 1)

                    play_target_idx[tm_idx] = tidx
                    play_target_team[tm_idx] = ti
                    play_depth[tm_idx] = (pc["adots"][tidx] >= 10).astype(np.int8)

                # D19: player attributes are allocation-only in v2.
                # Completion decided by team-level table + matchup tilt, NOT player catch_rate.

            completed = attempt_ok & (u3 < tbl_comp)

            incomplete = attempt_ok & ~completed

            # Compute yards
            yards = np.zeros(n_p, dtype=np.float64)

            # Sack yards — batched by bucket
            xs101 = np.linspace(0, 1, 101)
            if sacked.any():
                sk = np.where(sacked)[0]
                for d_v in range(1, 5):
                    for di_v in range(3):
                        for zi_v in range(NZONES):
                            m = sk[(d_p[sk]==d_v)&(di_p[sk]==di_v)&(zi_p[sk]==zi_v)]
                            if len(m):
                                yards[m] = np.interp(u5[m], xs101, pa_sack_yds[d_v, di_v, zi_v])
                # 5A-7: the 5A-4 hand scale (0.687) on deep sacks is removed — the y90/y100
                # zone cells carry their own measured sack-yardage distributions.

            # Completion yards — success/fail split with matchup tilt
            comp_succ = completed & (u4 < tbl_succ)
            comp_fail = completed & ~comp_succ

            # D19: play outcomes use team-level tables in BOTH modes.
            # Depth-split tables are NOT used for play outcome yards.
            for yds_mask, yds_tbl in [(comp_succ, pa_yds_succ), (comp_fail, pa_yds_fail)]:
                if yds_mask.any():
                    idx = np.where(yds_mask)[0]
                    for d_v in range(1, 5):
                        for di_v in range(3):
                            for zi_v in range(NZONES):
                                m = idx[(d_p[idx]==d_v)&(di_p[idx]==di_v)&(zi_p[idx]==zi_v)]
                                if len(m):
                                    yards[m] = np.interp(u5[m], xs101, yds_tbl[d_v, di_v, zi_v])

            # D6 additive EPA shift: after drawing yards, shift by matchup EPA
            # FIX 7: stochastic rounding of the shift prevents staircase response.
            # Each play gets floor(shift) or ceil(shift) with P(ceil) = frac.
            # E[shift_per_play] = shift exactly, but different plays round differently.
            for ti in [0, 1]:
                tm = poss_p == ti
                if tm.any():
                    comp_tm = completed & tm
                    if comp_tm.any():
                        shift = ctx[f"t{ti}_pass_epa_shift"]
                        shift_floor = np.floor(shift)
                        shift_frac = shift - shift_floor
                        dithered = shift_floor + (u_epa_pass[g_idx[comp_tm]] < shift_frac).astype(float)
                        yards[comp_tm] += dithered

            # Clamp: shifted yards cannot exceed yardline (goal-line cap),
            # and a negative-yard play cannot be shifted beyond +1 (no synthetic explosives)
            yards[completed] = np.minimum(yards[completed], yl_p[completed].astype(float))
            yards[completed] = np.maximum(yards[completed], -15.0)  # floor at empirical min

            # --- Apply results to state ---
            # FIX 7: use float yards (no rounding) so the EPA offset enters continuously
            yds = yards  # float — no np.round
            td_mask = completed & (yl_p - yds <= 0) & (yds > 0)
            # 5A-4: safeties handled as pre-play events above; mechanistic safety disabled.
            # Cap sack yardage at yl=99 (own 1) to prevent endzone penetration.
            would_be_safety = sacked & (yl_p - yds >= 100)
            safety_mask = np.zeros(n_p, dtype=bool)  # no mechanistic safeties
            if would_be_safety.any():
                yds[would_be_safety] = -(99 - yl_p[would_be_safety])
            normal_comp = completed & ~td_mask
            normal_sack = sacked & ~safety_mask

            # 3rd/4th-down tracking (before play outcomes change down)
            is_3rd = down_live[p_idx] == 3
            is_4th_go_pass = down_live[p_idx] == 4
            ev_3rd_att[g_idx[is_3rd]] += 1
            ev_3rd_long[g_idx[is_3rd & (dist_live[p_idx] >= 11)]] += 1

            # Normal completions (vectorised)
            nc_g = g_idx[normal_comp]
            nc_yds = yds[normal_comp]
            if len(nc_g):
                yl[nc_g] = np.clip(yl[nc_g] - nc_yds, 1, 99)
                nc_home = poss[nc_g] == 0
                # FIX 6e: do NOT clip negative yards (sacks, losses are real)
                h_pass_yds[nc_g[nc_home]] += nc_yds[nc_home]
                a_pass_yds[nc_g[~nc_home]] += nc_yds[~nc_home]
                nc_fd = nc_yds >= dist[nc_g]
                down[nc_g[nc_fd]] = 1
                dist[nc_g[nc_fd]] = np.minimum(10, yl[nc_g[nc_fd]])
                dist[nc_g[~nc_fd]] = np.maximum(1, dist[nc_g[~nc_fd]] - nc_yds[~nc_fd])
                down[nc_g[~nc_fd]] += 1
                n_plays[nc_g] += 1
                # Drive log: plays + yards + RZ/GL
                _dl_plays[nc_g] += 1
                _dl_yards[nc_g] += nc_yds
                _dl_reached_rz[nc_g] |= yl[nc_g] <= 20
                _dl_reached_gl[nc_g] |= yl[nc_g] <= 5
                _dl_end_yl[nc_g] = yl[nc_g]; _dl_end_down[nc_g] = down[nc_g]; _dl_end_dist[nc_g] = dist[nc_g]

            # Normal sacks (vectorised)
            ns_g = g_idx[normal_sack]
            ns_yds = yds[normal_sack]
            if len(ns_g):
                yl[ns_g] = np.clip(yl[ns_g] - ns_yds, 1, 99)
                dist[ns_g] = np.maximum(1, dist[ns_g] - ns_yds)
                down[ns_g] += 1
                n_plays[ns_g] += 1
                _dl_plays[ns_g] += 1
                _dl_yards[ns_g] += ns_yds
                _dl_end_yl[ns_g] = yl[ns_g]; _dl_end_down[ns_g] = down[ns_g]; _dl_end_dist[ns_g] = dist[ns_g]

            # Incompletes (vectorised)
            inc_g = g_idx[incomplete]
            if len(inc_g):
                down[inc_g] += 1
                n_plays[inc_g] += 1
                _dl_plays[inc_g] += 1
                _dl_end_yl[inc_g] = yl[inc_g]; _dl_end_down[inc_g] = down[inc_g]; _dl_end_dist[inc_g] = dist[inc_g]

            # TDs (per-sim — rare, ~3/game)
            for j in np.where(td_mask)[0]:
                gi = g_idx[j]
                if poss[gi] == 0: h_pass_yds[gi] += yl[gi]
                else: a_pass_yds[gi] += yl[gi]
                n_plays[gi] += 1
                _dl_plays[gi] += 1; _dl_yards[gi] += yl[gi]
                _dl_reached_rz[gi] = True; _dl_reached_gl[gi] = True
                _dl_result[gi] = _DLR_TD
                m = np.zeros(N, dtype=bool); m[gi] = True
                _handle_td(m, np.full(N, poss[gi], dtype=np.int8))

            # Safeties (per-sim — extremely rare)
            for j in np.where(safety_mask)[0]:
                gi = g_idx[j]
                n_plays[gi] += 1; _dl_plays[gi] += 1
                _dl_result[gi] = _DLR_SAFETY
                ev_safeties[gi] += 1  # 5A-4
                dt = 1 - poss[gi]
                score_h[gi] += 2 * (dt == 0); score_a[gi] += 2 * (dt == 1)
                yl[gi] = 75; poss[gi] = 1 - poss[gi]
                m = np.zeros(N, dtype=bool); m[gi] = True; _new_drive(m)

            # Interceptions (per-sim — ~1-2/game)
            for j in np.where(intercepted)[0]:
                gi = g_idx[j]
                # 5T: record end_yl BEFORE the spot changes (fixes stale first-play INT)
                _dl_end_yl[gi] = yl[gi]; _dl_end_down[gi] = down[gi]; _dl_end_dist[gi] = dist[gi]
                turnovers[gi] += 1; n_plays[gi] += 1; _dl_plays[gi] += 1
                _dl_result[gi] = _DLR_INT
                if u_int_dtd[gi] < p_int_def_td:
                    # 5T: log pick-six when drive_log on
                    if drive_log:
                        _dl_int_rows.append((gi, float(yl[gi]), 0, float(yl[gi]), False, 0, True, float("nan")))
                    m = np.zeros(N, dtype=bool); m[gi] = True
                    ev_int_ret_td[gi] += 1  # 5A-5
                    _handle_td(m, np.full(N, 1 - poss[gi], dtype=np.int8))
                else:
                    ret = int(np.interp(u_int_ret[gi], np.linspace(0, 1, 101), int_ret_q))
                    # 5S: spot the INT at the catch point, not the LOS
                    air = 0
                    if _int_spot_q:
                        cur_yl = yl[gi]
                        if cur_yl <= 20: bkt = "1-20"
                        elif cur_yl <= 40: bkt = "21-40"
                        elif cur_yl <= 60: bkt = "41-60"
                        elif cur_yl <= 80: bkt = "61-80"
                        else: bkt = "81-99"
                        q_arr = _int_spot_q.get(bkt)
                        if q_arr is not None:
                            air = int(np.interp(u_int_air[gi], np.linspace(0, 1, 101), q_arr))
                    catch_yl = yl[gi] - air  # catch point (yards to EZ)
                    ez_flag = catch_yl <= 0
                    if ez_flag:
                        # Pick in the end zone → touchback at 80 (own 20)
                        yl[gi] = 80.0
                    else:
                        yl[gi] = float(np.clip(100 - (catch_yl + ret), 1, 99))
                    # 5T: log INT chain when drive_log on
                    if drive_log:
                        _dl_int_rows.append((gi, float(_dl_end_yl[gi]), air, float(catch_yl), ez_flag, ret, False, float(yl[gi])))
                    poss[gi] = 1 - poss[gi]
                    m = np.zeros(N, dtype=bool); m[gi] = True; _new_drive(m)

            # Pass fumbles (per-sim — ~0.5/game)
            for j in np.where(pass_fumbled)[0]:
                gi = g_idx[j]
                turnovers[gi] += 1; n_plays[gi] += 1; _dl_plays[gi] += 1
                _dl_result[gi] = _DLR_FUM
                if u_pfum_dtd[gi] < p_fum_def_td:
                    m = np.zeros(N, dtype=bool); m[gi] = True
                    ev_fum_ret_td[gi] += 1  # 5A-5
                    _handle_td(m, np.full(N, 1 - poss[gi], dtype=np.int8))
                else:
                    ret = int(np.interp(u_pfum_ret[gi], np.linspace(0, 1, 101), fum_ret_q))
                    yl[gi] = float(np.clip(100 - (yl[gi] + ret), 1, 99))
                    poss[gi] = 1 - poss[gi]
                    m = np.zeros(N, dtype=bool); m[gi] = True; _new_drive(m)

            # Track events (vectorised)
            ev_pass_plays[g_idx] += 1
            ev_sacks[g_idx[sacked]] += 1
            ev_ints[g_idx[intercepted]] += 1
            ev_incomp[g_idx[incomplete]] += 1
            ev_comp[g_idx[completed]] += 1
            fd_comp = normal_comp & (yds >= dist_live[p_idx])
            ev_first_downs[g_idx[fd_comp | td_mask]] += 1
            ev_fd_pass[g_idx[fd_comp | td_mask]] += 1  # 5A-4
            # 3rd-down conversions (pass)
            conv_3rd = is_3rd & (fd_comp | td_mask)
            ev_3rd_conv[g_idx[conv_3rd]] += 1
            # 4th-down conversions (pass)
            conv_4th = is_4th_go_pass & (fd_comp | td_mask)
            ev_4th_conv[g_idx[conv_4th]] += 1
            # 5A-3: explosive pass (20+ yds)
            expl_p = completed & (yds >= 20)
            ev_explosive_pass[g_idx[expl_p]] += 1
            ev_pass_40[g_idx[completed & (yds >= 40)]] += 1
            if _DEBUG_YDS is not None:
                _DEBUG_YDS.append(("pass", np.asarray(yds[completed], dtype=float), np.asarray(yl_p[completed], dtype=float), np.asarray(down_live[p_idx][completed]) if 'down_live' in dir() else None))
            ev_td_long[g_idx[td_mask & (yl_p >= 20)]] += 1
            ev_td_short[g_idx[td_mask & (yl_p < 20)]] += 1

            # --- Player stat tracking (pass) ---
            if has_players:
                for ti in [0, 1]:
                    tm = play_target_team == ti
                    if not tm.any() or player_ctx[ti] is None:
                        continue
                    pc = player_ctx[ti]
                    qb = pc["qb_idx"]

                    # Targets: thrown passes (non-sacked, non-fumbled)
                    for j in np.where(tm & not_sacked & ~pass_fumbled)[0]:
                        pl_stats[ti][g_idx[j], play_target_idx[j], PL_TGT] += 1
                    # Receptions: all completions (count only)
                    for j in np.where(tm & completed)[0]:
                        pl_stats[ti][g_idx[j], play_target_idx[j], PL_REC] += 1
                    # Normal completion yards (non-TD, matching team code)
                    # FIX 6e: don't clip negative yards
                    for j in np.where(tm & normal_comp)[0]:
                        pl_stats[ti][g_idx[j], play_target_idx[j], PL_RECYD] += int(round(yds[j]))
                    # Receiving TDs: yards = yl_p (distance to EZ)
                    for j in np.where(tm & td_mask)[0]:
                        gi, pi = g_idx[j], play_target_idx[j]
                        pl_stats[ti][gi, pi, PL_RECTD] += 1
                        pl_stats[ti][gi, pi, PL_RECYD] += int(round(yl_p[j]))
                    # QB stats
                    if qb >= 0:
                        # Attempts = thrown passes (excludes sacks, fumbles)
                        for j in np.where(tm & not_sacked & ~pass_fumbled)[0]:
                            pl_stats[ti][g_idx[j], qb, PL_PATT] += 1
                        for j in np.where(tm & completed)[0]:
                            pl_stats[ti][g_idx[j], qb, PL_PCMP] += 1
                        # Pass yards: normal comps (FIX 6e: no clip)
                        for j in np.where(tm & normal_comp)[0]:
                            pl_stats[ti][g_idx[j], qb, PL_PYD] += int(round(yds[j]))
                        # Pass TDs + their yards
                        for j in np.where(tm & td_mask)[0]:
                            pl_stats[ti][g_idx[j], qb, PL_PTD] += 1
                            pl_stats[ti][g_idx[j], qb, PL_PYD] += int(round(yl_p[j]))
                        for j in np.where(tm & intercepted)[0]:
                            pl_stats[ti][g_idx[j], qb, PL_INT] += 1
                        for j in np.where(tm & sacked)[0]:
                            pl_stats[ti][g_idx[j], qb, PL_SACK] += 1

            # Clock: pass plays — vectorised
            # 5A-3: score_state × clock_period conditioned clock tables
            ot_idx = np.full(n_p, 2, dtype=np.int8)
            ot_idx[incomplete] = 0
            fd_pass = completed & (yds >= dist_live[p_idx])
            ot_idx[fd_pass] = 1
            ot_idx[td_mask | intercepted | pass_fumbled] = 3
            gi_arr = g_idx
            sd_arr = np.where(poss[gi_arr] == 0,
                              score_h[gi_arr] - score_a[gi_arr],
                              score_a[gi_arr] - score_h[gi_arr])
            ot_names_p = np.asarray(["incomplete", "first_down", "complete_inbounds", "drive_end"], dtype=object)[ot_idx]
            eoh_p = _eoh_runoff(gi_arr, sd_arr, yl_p, ot_names_p, u_pclock, exclude=(ot_idx == 3))   # 5A-9
            _apply_timeouts(gi_arr, ot_idx, sd_arr, u_to, skip=eoh_p)  # 5A-7
            # 5A-3: score state (5-way)
            ss_arr = np.where(sd_arr <= -9, "trail9+",
                     np.where(sd_arr <= -1, "trail1-8",
                     np.where(sd_arr == 0, "tied",
                     np.where(sd_arr <= 8, "lead1-8", "lead9+"))))
            # 5I/5M: clock period — Q4_mid split at 180 s
            cp_arr = np.full(len(gi_arr), "normal", dtype=object)
            q2_late_m = (qtr[gi_arr] == 2) & (clock[gi_arr] <= 120)
            q4_mid_b_m = (qtr[gi_arr] == 4) & (clock[gi_arr] > 120) & (clock[gi_arr] <= 180)
            q4_mid_a_m = (qtr[gi_arr] == 4) & (clock[gi_arr] > 180) & (clock[gi_arr] <= 300)
            q4_late_m = (qtr[gi_arr] >= 4) & (clock[gi_arr] <= 120)   # 5A-11 (D39): OT included
            cp_arr[q2_late_m] = "Q2_late"
            cp_arr[q4_mid_a_m] = "Q4_mid_a"
            cp_arr[q4_mid_b_m] = "Q4_mid_b"
            cp_arr[q4_late_m] = "Q4_late"
            ot_strs = ["incomplete", "first_down", "complete_inbounds"]
            xs101 = np.linspace(0, 1, 101)
            pace_arr = np.where(poss[gi_arr] == 0,
                                ctx["t0_pace"], ctx["t1_pace"]) / ctx["lg_pace"]
            for oi in range(3):
                ot_name = ot_strs[oi]
                for ss_val in ["trail9+", "trail1-8", "tied", "lead1-8", "lead9+"]:
                    for cp_val in ["normal", "Q2_late", "Q4_mid_a", "Q4_mid_b", "Q4_late"]:
                        mask = ((ot_idx == oi) & (ss_arr == ss_val) &
                                (cp_arr == cp_val) & ~game_over[gi_arr] & ~eoh_p)
                        if not mask.any():
                            continue
                        # 5M: 4-level fallback: split -> Q4_mid -> parent -> legacy
                        cq = clock_q.get((ot_name, ss_val, cp_val))
                        if cq is None and cp_val in ("Q4_mid_a", "Q4_mid_b"):
                            cq = clock_q.get((ot_name, ss_val, "Q4_mid"))
                        if cq is None:
                            cq = clock_q.get((ot_name, f"p_{ss_val}", "all"))
                        if cq is None:
                            hurry_legacy = cp_val != "normal" and ss_val in ("trail9+", "trail1-8", "tied")
                            cq = clock_q.get((ot_name, hurry_legacy),
                                              clock_q.get((ot_name, False), np.full(101, 30.0)))
                        m_idx = np.where(mask)[0]
                        elapsed = np.interp(u_pclock[gi_arr[m_idx]], xs101, cq) * pace_arr[m_idx]
                        elapsed = np.maximum(elapsed, 3.0)
                        clock[gi_arr[m_idx]] -= elapsed.astype(np.float32)
                        ev_clock_used[gi_arr[m_idx]] += elapsed.astype(np.float32)
            # Drive-ending plays: short clock (game clock stops on scoring/turnovers)
            de_mask = (ot_idx == 3) & ~game_over[gi_arr]
            if de_mask.any():
                de_idx = np.where(de_mask)[0]
                de_elapsed = np.maximum(u_pclock[gi_arr[de_idx]] * 16.0, 3.0)  # ~8s mean
                clock[gi_arr[de_idx]] -= de_elapsed.astype(np.float32)
                ev_clock_used[gi_arr[de_idx]] += de_elapsed.astype(np.float32)

        # --- RUSH PLAYS (vectorised) ---
        rm = ~is_pass
        n_r = rm.sum()
        if n_r > 0:
            r_idx = np.where(rm)[0]
            g_idx_r = live_idx[r_idx]

            d_r = down_live[r_idx]
            di_r = di_arr[r_idx]
            zi_r = zi_arr[r_idx]
            poss_r = poss_live[r_idx]
            yl_r = yl_live[r_idx]

            # Table lookup
            tbl_fum = ru_fum[d_r, di_r, zi_r].copy()
            tbl_succ_r = ru_succ[d_r, di_r, zi_r].copy()

            # Apply matchup via logit-additive shift on bucket base rates
            for ti in [0, 1]:
                tm = poss_r == ti
                if tm.any():
                    succ_shift = _logit(ctx[f"t{ti}_rush_success"]) - _logit(lb["rush_success"])
                    tbl_succ_r[tm] = _sigmoid(_logit(tbl_succ_r[tm]) + succ_shift)
            tbl_succ_r = np.clip(tbl_succ_r, 0.05, 0.95)

            u1 = u_rfum[g_idx_r]
            u2 = u_rsucc[g_idx_r]
            u5 = u_ryards[g_idx_r]

            fumbled = u1 < tbl_fum
            not_fum = ~fumbled
            success_r = not_fum & (u2 < tbl_succ_r)
            fail_r = not_fum & ~success_r

            xs101 = np.linspace(0, 1, 101)
            yards_r = np.zeros(n_r, dtype=np.float64)
            for yds_mask, yds_tbl in [(success_r, ru_yds_succ), (fail_r, ru_yds_fail)]:
                if yds_mask.any():
                    idx = np.where(yds_mask)[0]
                    for d_v in range(1, 5):
                        for di_v in range(3):
                            for zi_v in range(NZONES):
                                m = idx[(d_r[idx]==d_v)&(di_r[idx]==di_v)&(zi_r[idx]==zi_v)]
                                if len(m):
                                    yards_r[m] = np.interp(u5[m], xs101, yds_tbl[d_v, di_v, zi_v])

            # 5A-9 (D33): runs in the FG-setup state draw from the in-state KM cell (the
            # offence is protecting the kick); no team EPA shift on those snaps
            fgs_r = np.zeros(n_r, dtype=bool)
            if fgs_rush_q is not None:
                fgs_r = not_fum & (fgs_state[g_idx_r] != "") & (fgs_state[g_idx_r] != "ot_sd")  # OT runs are not the Q4 clock-kill runs (4.1 yds vs 2.7)
                if fgs_r.any():
                    yards_r[fgs_r] = np.interp(u5[fgs_r], xs101, fgs_rush_q)
                    ev_fgs_runs[g_idx_r[fgs_r]] += 1

            # D6 additive EPA shift for rush yards (FIX 7: stochastic rounding)
            for ti in [0, 1]:
                tm = poss_r == ti
                rush_ok = not_fum & tm & ~fgs_r
                if rush_ok.any():
                    shift = ctx[f"t{ti}_rush_epa_shift"]
                    shift_floor = np.floor(shift)
                    shift_frac = shift - shift_floor
                    dithered = shift_floor + (u_epa_rush[g_idx_r[rush_ok]] < shift_frac).astype(float)
                    yards_r[rush_ok] += dithered
            yards_r[not_fum] = np.minimum(yards_r[not_fum], yl_r[not_fum].astype(float))
            yards_r[not_fum] = np.maximum(yards_r[not_fum], -10.0)

            yds_r = yards_r  # FIX 7: float — no rounding
            td_r = not_fum & (yl_r - yds_r <= 0) & (yds_r > 0)
            # 5A-4: safeties handled as pre-play events; mechanistic disabled.
            would_be_safety_r = not_fum & (yl_r - yds_r >= 100)
            safety_r = np.zeros(n_r, dtype=bool)  # no mechanistic safeties
            capped_rush = would_be_safety_r & ~safety_r
            if capped_rush.any():
                yds_r[capped_rush] = -(99 - yl_r[capped_rush])
            normal_r = not_fum & ~td_r & ~safety_r

            # 3rd/4th-down tracking (rush)
            is_3rd_r = down_live[r_idx] == 3
            is_4th_go_rush = down_live[r_idx] == 4

            # Normal rushes (vectorised)
            nr_g = g_idx_r[normal_r]
            nr_yds = yds_r[normal_r]
            if len(nr_g):
                yl[nr_g] = np.clip(yl[nr_g] - nr_yds, 1, 99)
                nr_home = poss[nr_g] == 0
                # FIX 6e: do NOT clip negative yards
                h_rush_yds[nr_g[nr_home]] += nr_yds[nr_home]
                a_rush_yds[nr_g[~nr_home]] += nr_yds[~nr_home]
                nr_fd = nr_yds >= dist[nr_g]
                down[nr_g[nr_fd]] = 1
                dist[nr_g[nr_fd]] = np.minimum(10, yl[nr_g[nr_fd]])
                dist[nr_g[~nr_fd]] = np.maximum(1, dist[nr_g[~nr_fd]] - nr_yds[~nr_fd])
                down[nr_g[~nr_fd]] += 1
                n_plays[nr_g] += 1
                # Drive log tracking
                _dl_plays[nr_g] += 1
                _dl_yards[nr_g] += nr_yds
                _dl_reached_rz[nr_g] |= yl[nr_g] <= 20
                _dl_reached_gl[nr_g] |= yl[nr_g] <= 5
                _dl_end_yl[nr_g] = yl[nr_g]; _dl_end_down[nr_g] = down[nr_g]; _dl_end_dist[nr_g] = dist[nr_g]

            # Rush TDs (per-sim — rare)
            for j in np.where(td_r)[0]:
                gi = g_idx_r[j]
                if poss[gi] == 0: h_rush_yds[gi] += yl[gi]
                else: a_rush_yds[gi] += yl[gi]
                n_plays[gi] += 1
                _dl_plays[gi] += 1; _dl_yards[gi] += yl[gi]
                _dl_reached_rz[gi] = True; _dl_reached_gl[gi] = True
                _dl_result[gi] = _DLR_TD
                m = np.zeros(N, dtype=bool); m[gi] = True
                _handle_td(m, np.full(N, poss[gi], dtype=np.int8))

            # Rush safeties (per-sim — extremely rare)
            for j in np.where(safety_r)[0]:
                gi = g_idx_r[j]; n_plays[gi] += 1; _dl_plays[gi] += 1
                _dl_result[gi] = _DLR_SAFETY
                ev_safeties[gi] += 1  # 5A-4
                dt = 1 - poss[gi]
                score_h[gi] += 2 * (dt == 0); score_a[gi] += 2 * (dt == 1)
                yl[gi] = 75; poss[gi] = 1 - poss[gi]
                m = np.zeros(N, dtype=bool); m[gi] = True; _new_drive(m)

            # Fumbles (per-sim — ~1/game)
            for j in np.where(fumbled)[0]:
                gi = g_idx_r[j]; turnovers[gi] += 1; n_plays[gi] += 1; _dl_plays[gi] += 1
                _dl_result[gi] = _DLR_FUM
                if u_rfum_dtd[gi] < p_fum_def_td:
                    m = np.zeros(N, dtype=bool); m[gi] = True
                    ev_fum_ret_td[gi] += 1  # 5A-5
                    _handle_td(m, np.full(N, 1 - poss[gi], dtype=np.int8))
                else:
                    ret = int(np.interp(u_rfum_ret[gi], np.linspace(0, 1, 101), fum_ret_q))
                    yl[gi] = float(np.clip(100 - (yl[gi] + ret), 1, 99))
                    poss[gi] = 1 - poss[gi]
                    m = np.zeros(N, dtype=bool); m[gi] = True; _new_drive(m)

            # Track rush play events (vectorised)
            ev_rush_plays[g_idx_r] += 1
            ev_3rd_att[g_idx_r[is_3rd_r]] += 1
            ev_3rd_long[g_idx_r[is_3rd_r & (dist_live[r_idx] >= 11)]] += 1
            normal_rush = not_fum & ~td_r & ~safety_r
            fd_rush = normal_rush & (yds_r >= dist_live[r_idx])
            ev_first_downs[g_idx_r[fd_rush | td_r]] += 1
            ev_fd_rush[g_idx_r[fd_rush | td_r]] += 1  # 5A-4
            conv_3rd_r = is_3rd_r & (fd_rush | td_r)
            ev_3rd_conv[g_idx_r[conv_3rd_r]] += 1
            conv_4th_r = is_4th_go_rush & (fd_rush | td_r)
            ev_4th_conv[g_idx_r[conv_4th_r]] += 1
            # 5A-3: explosive rush (10+ yds)
            expl_r = not_fum & (yds_r >= 10)
            ev_explosive_rush[g_idx_r[expl_r]] += 1
            ev_rush_20[g_idx_r[not_fum & (yds_r >= 20)]] += 1
            if _DEBUG_YDS is not None:
                _DEBUG_YDS.append(("rush", np.asarray(yds_r[not_fum], dtype=float), np.asarray(yl_r[not_fum], dtype=float), None))
            ev_td_long[g_idx_r[td_r & (yl_r >= 20)]] += 1
            ev_td_short[g_idx_r[td_r & (yl_r < 20)]] += 1

            # --- Player stat tracking (rush) ---
            if has_players:
                # Build rusher index for all rush plays (like pass target selection)
                play_rusher_idx = np.full(n_r, -1, dtype=np.int32)
                play_rusher_team = np.full(n_r, -1, dtype=np.int8)
                for ti in [0, 1]:
                    tm = poss_r == ti
                    if not tm.any() or player_ctx[ti] is None:
                        continue
                    pc = player_ctx[ti]
                    tm_idx = np.where(tm)[0]
                    tm_g = g_idx_r[tm_idx]
                    tm_yl = yl_r[tm_idx]
                    u_rsh = u_rusher[tm_g]

                    use_gl = tm_yl <= 5
                    ridx = np.empty(len(tm_idx), dtype=np.int32)
                    # Per-sim lookup (FIX 1: dispersed shares)
                    for jj in range(len(tm_idx)):
                        si = tm_g[jj]
                        cs_row = pc["gl_car_cumsum"][si] if use_gl[jj] else pc["car_cumsum"][si]
                        ridx[jj] = np.searchsorted(cs_row, u_rsh[jj])
                    ridx = np.clip(ridx, 0, pc["n_players"] - 1)
                    play_rusher_idx[tm_idx] = ridx
                    play_rusher_team[tm_idx] = ti

                    # Carry count (all rushes including fumbles)
                    for j in range(len(tm_idx)):
                        pl_stats[ti][tm_g[j], ridx[j], PL_CAR] += 1
                    # Normal rush yards (non-TD, non-fumble, non-safety)
                    # FIX 6e: don't clip negative yards
                    for j in np.where(tm & normal_r)[0]:
                        loc = np.searchsorted(tm_idx, j)
                        if loc < len(tm_idx) and tm_idx[loc] == j:
                            pl_stats[ti][g_idx_r[j], ridx[loc], PL_RUSHYD] += int(round(yds_r[j]))
                    # Rush TDs: yards = yl_r (distance to EZ)
                    for j in np.where(tm & td_r)[0]:
                        loc = np.searchsorted(tm_idx, j)
                        if loc < len(tm_idx) and tm_idx[loc] == j:
                            pi = ridx[loc]
                            gi = g_idx_r[j]
                            pl_stats[ti][gi, pi, PL_RUSHTD] += 1
                            pl_stats[ti][gi, pi, PL_RUSHYD] += int(round(yl_r[j]))

            # Clock: rush plays — vectorised (5A-3: score_state × clock_period)
            ot_idx_r = np.ones(n_r, dtype=np.int8)  # 1=run, 0=first_down, 2=drive_ending
            fd_rush_all = not_fum & (yds_r >= dist_live[r_idx])
            ot_idx_r[fd_rush_all] = 0  # 0=first_down
            ot_idx_r[td_r | fumbled] = 2  # drive-ending: short clock
            gi_r = g_idx_r
            sd_r_arr = np.where(poss[gi_r] == 0,
                                score_h[gi_r] - score_a[gi_r],
                                score_a[gi_r] - score_h[gi_r])
            ot_names_r = np.asarray(["first_down", "run", "drive_end", "incomplete"], dtype=object)[ot_idx_r]
            eoh_r = _eoh_runoff(gi_r, sd_r_arr, yl_r, ot_names_r, u_rclock, exclude=(ot_idx_r == 2))   # 5A-9
            _apply_timeouts(gi_r, ot_idx_r, sd_r_arr, u_to, running_codes=(0, 1), de_code=2, stop_code=3, skip=eoh_r)  # 5A-7
            ss_r_arr = np.where(sd_r_arr <= -9, "trail9+",
                       np.where(sd_r_arr <= -1, "trail1-8",
                       np.where(sd_r_arr == 0, "tied",
                       np.where(sd_r_arr <= 8, "lead1-8", "lead9+"))))
            cp_r_arr = np.full(len(gi_r), "normal", dtype=object)
            q2l_r = (qtr[gi_r] == 2) & (clock[gi_r] <= 120)
            q4mb_r = (qtr[gi_r] == 4) & (clock[gi_r] > 120) & (clock[gi_r] <= 180)
            q4ma_r = (qtr[gi_r] == 4) & (clock[gi_r] > 180) & (clock[gi_r] <= 300)
            q4l_r = (qtr[gi_r] >= 4) & (clock[gi_r] <= 120)   # 5A-11 (D39): OT included
            cp_r_arr[q2l_r] = "Q2_late"
            cp_r_arr[q4ma_r] = "Q4_mid_a"
            cp_r_arr[q4mb_r] = "Q4_mid_b"
            cp_r_arr[q4l_r] = "Q4_late"
            ot_strs_r = {0: "first_down", 1: "run", 3: "incomplete"}  # 3 = clock stopped by a timeout (5A-7)
            xs101 = np.linspace(0, 1, 101)
            pace_r = np.where(poss[gi_r] == 0,
                              ctx["t0_pace"], ctx["t1_pace"]) / ctx["lg_pace"]
            for oi in (0, 1, 3):
                ot_name_r = ot_strs_r[oi]
                for ss_val in ["trail9+", "trail1-8", "tied", "lead1-8", "lead9+"]:
                    for cp_val in ["normal", "Q2_late", "Q4_mid_a", "Q4_mid_b", "Q4_late"]:
                        mask = ((ot_idx_r == oi) & (ss_r_arr == ss_val) &
                                (cp_r_arr == cp_val) & ~game_over[gi_r] & ~eoh_r)
                        if not mask.any():
                            continue
                        cq = clock_q.get((ot_name_r, ss_val, cp_val))
                        if cq is None and cp_val in ("Q4_mid_a", "Q4_mid_b"):
                            cq = clock_q.get((ot_name_r, ss_val, "Q4_mid"))
                        if cq is None:
                            cq = clock_q.get((ot_name_r, f"p_{ss_val}", "all"))
                        if cq is None:
                            hurry_legacy = cp_val != "normal" and ss_val in ("trail9+", "trail1-8", "tied")
                            cq = clock_q.get((ot_name_r, hurry_legacy),
                                              clock_q.get((ot_name_r, False), np.full(101, 35.0)))
                        m_idx = np.where(mask)[0]
                        elapsed = np.interp(u_rclock[gi_r[m_idx]], xs101, cq) * pace_r[m_idx]
                        elapsed = np.maximum(elapsed, 3.0)
                        clock[gi_r[m_idx]] -= elapsed.astype(np.float32)
                        ev_clock_used[gi_r[m_idx]] += elapsed.astype(np.float32)
            # Drive-ending rush plays (TDs, fumbles): short clock
            de_r = (ot_idx_r == 2) & ~game_over[gi_r]
            if de_r.any():
                de_idx = np.where(de_r)[0]
                de_elapsed = np.maximum(u_rclock[gi_r[de_idx]] * 16.0, 3.0)
                clock[gi_r[de_idx]] -= de_elapsed.astype(np.float32)
                ev_clock_used[gi_r[de_idx]] += de_elapsed.astype(np.float32)

        # --- Turnover on downs ---
        tod = ~game_over & (down > 4)
        if tod.any():
            _dl_result[tod] = _DLR_DOWNS
            _change_poss(tod)

            # OT: change of possession after first team's drive
            ot_tod = tod & (qtr >= 5) & ~ot_first_poss_done
            ot_first_poss_done[ot_tod] = True

    # FIX 1: safety cap check — hitting MAX_STEPS is an error
    if not game_over.all():
        n_unfinished = (~game_over).sum()
        raise RuntimeError(
            f"Safety cap hit: {n_unfinished}/{N} sims unfinished after {MAX_STEPS} steps. "
            f"This indicates a bug in game termination logic."
        )

    # Record any remaining unrecorded drives at game end
    if drive_log:
        unrecorded = game_over & (_dl_result > 0)
        if unrecorded.any():
            _dl_new_drive(unrecorded)  # This records + resets

    # If half was never recorded (0-0 at half), record it
    not_rec = ~half_recorded
    score_h_1h[not_rec] = 0
    score_a_1h[not_rec] = 0

    # FIX 1: compute clock_remaining for output
    clock_remaining = np.maximum(clock, 0.0)

    team_df = pd.DataFrame({
        "home_score": score_h,
        "away_score": score_a,
        "home_1h": score_h_1h,
        "away_1h": score_a_1h,
        "plays": n_plays,
        "drives": n_drives,
        "home_pass_yds": h_pass_yds,
        "home_rush_yds": h_rush_yds,
        "away_pass_yds": a_pass_yds,
        "away_rush_yds": a_rush_yds,
        "turnovers": turnovers,
        "ot_flag": ot_flag,
        "ev_sacks": ev_sacks,
        "ev_ints": ev_ints,
        "ev_incomp": ev_incomp,
        "ev_comp": ev_comp,
        "ev_pass_plays": ev_pass_plays,
        "ev_rush_plays": ev_rush_plays,
        "ev_first_downs": ev_first_downs,
        "ev_punts": ev_punts,
        "ev_fg_att": ev_fg_att,
        "ev_fg_non4th": ev_fg_non4th,
        "ev_eoh_snaps": ev_eoh_snaps,
        "ev_to_off": ev_to_off, "ev_to_def": ev_to_def, "ev_kneels": ev_kneels,
        "ev_late_snaps_q2": ev_late_snaps_q2,
        "ev_late_snaps_q4": ev_late_snaps_q4,
        "m_q4_300": m_q4_300, "m_q4_120": m_q4_120,           # 5A-8 diag
        "ev_eoh_runoff": ev_eoh_runoff, "ev_fgs_snaps": ev_fgs_snaps, "ev_fgs_runs": ev_fgs_runs, "ev_fgs_runoff": ev_fgs_runoff, "ev_spikes": ev_spikes,   # 5A-9
        "poss_q4_300": poss_q4_300, "poss_q4_120": poss_q4_120,
        "yl_q4_120": yl_q4_120,
        "ev_pass_40": ev_pass_40, "ev_rush_20": ev_rush_20,
        "ev_td_long": ev_td_long, "ev_td_short": ev_td_short,
        "ev_fg_made": ev_fg_made,
        "ev_tds": ev_tds,
        "ev_penalties": ev_penalties,
        "ev_clock_used": ev_clock_used,
        "ev_3rd_att": ev_3rd_att,
        "ev_3rd_long": ev_3rd_long,
        "ev_3rd_conv": ev_3rd_conv,
        "ev_4th_go": ev_4th_go,
        "ev_4th_conv": ev_4th_conv,
        "ev_fg_dist_sum": ev_fg_dist_sum,
        "ev_explosive_pass": ev_explosive_pass,
        "ev_explosive_rush": ev_explosive_rush,
        "ev_pen_offense": ev_pen_offense,
        "ev_pen_defense": ev_pen_defense,
        "ev_pen_off_yds": ev_pen_off_yds,
        "ev_pen_def_yds": ev_pen_def_yds,
        "ev_fd_rush": ev_fd_rush,
        "ev_fd_pass": ev_fd_pass,
        "ev_fd_penalty": ev_fd_penalty,
        "ev_safeties": ev_safeties,
        "ev_int_ret_td": ev_int_ret_td,
        "ev_fum_ret_td": ev_fum_ret_td,
        "ev_punt_ret_td": ev_punt_ret_td,
        "ev_ko_ret_td": ev_ko_ret_td,
        "game_over": game_over,
        "clock_remaining": clock_remaining,
    })
    # FIX 5: attach fallback count as metadata
    team_df.attrs["playcall_fallback_count"] = _fallback_count
    team_df.attrs["sit_proe_miss_count"] = _sit_proe_miss

    # Drive log output
    if drive_log and _dl_rows:
        dl_df = pd.DataFrame(_dl_rows, columns=[
            "sim_id", "team", "drive_no", "start_yardline", "start_quarter",
            "start_clock", "plays", "yards", "result", "points",
            "reached_rz", "reached_gl",
            "end_yardline", "end_down", "end_dist", "score_state",
            "sd_start", "opp_points",
        ])
        team_df.attrs["drive_log"] = _DriveLog(dl_df)
    # 5T: INT chain log
    if drive_log and _dl_int_rows:
        int_df = pd.DataFrame(_dl_int_rows, columns=[
            "sim_id", "los", "air", "catch_yl", "ez", "ret", "six", "next_start",
        ])
        team_df.attrs["int_chain_log"] = int_df

    if not has_players:
        return team_df

    # Build long-form player stats table
    stat_names = ["targets", "receptions", "rec_yds", "rec_td",
                   "carries", "rush_yds", "rush_td",
                   "pass_att", "pass_cmp", "pass_yds", "pass_td",
                   "interceptions", "sacks"]
    pl_rows = []
    for ti in [0, 1]:
        pc = player_ctx[ti]
        if pc is None:
            continue
        arr = pl_stats[ti]  # (N, n_players, 13)
        any_stat = arr.any(axis=(0, 2))  # (n_players,) — players with any stat
        for pi in np.where(any_stat)[0]:
            for si in range(N):
                if arr[si, pi].any():
                    row = {
                        "sim_id": si,
                        "player_id": pc["ids"][pi],
                        "player_name": pc["names"][pi],
                        "position": pc["positions"][pi],
                        "team": pc["team"],
                    }
                    for k, nm in enumerate(stat_names):
                        row[nm] = int(arr[si, pi, k])
                    row["anytime_td"] = int(arr[si, pi, PL_RECTD] + arr[si, pi, PL_RUSHTD])
                    pl_rows.append(row)

    player_df = pd.DataFrame(pl_rows) if pl_rows else pd.DataFrame(
        columns=["sim_id", "player_id", "player_name", "position", "team"] + stat_names + ["anytime_td"])

    return team_df, player_df


# ═══════════════════════════════════════════════════════════════════════════════
# K1 BACKTEST
# ═══════════════════════════════════════════════════════════════════════════════

def k1_backtest(n_sims=2000, seasons=None):
    if seasons is None:
        seasons = [2021, 2022, 2023, 2024]

    _load_tables()
    team_r, tend, sit, kicker, league = _load_ratings()

    frames = []
    for s in seasons:
        p = ROOT / "nfl" / "data" / "pbp" / f"pbp_{s}.parquet"
        df = pd.read_parquet(p, columns=["game_id", "season", "week", "home_team",
                                          "away_team", "home_score", "away_score",
                                          "spread_line", "total_line"])
        games = df.drop_duplicates("game_id")
        games = games[games["week"] <= 18]
        frames.append(games)
    actuals = pd.concat(frames, ignore_index=True)

    print(f"K1 backtest: {len(actuals)} games, N={n_sims} sims/game")

    results = []
    for s in seasons:
        s_games = actuals[actuals["season"] == s]
        t0 = time.time()
        for _, game in s_games.iterrows():
            seed = stable_seed((game["game_id"], 42))
            sim = simulate_game(
                game["home_team"], game["away_team"], s, int(game["week"]),
                n_sims=n_sims, seed=seed,
                team_r=team_r, tend=tend, sit=sit, kicker=kicker, league=league
            )
            sim["game_id"] = game["game_id"]
            sim["actual_home"] = game["home_score"]
            sim["actual_away"] = game["away_score"]
            sim["spread_line"] = game.get("spread_line", np.nan)
            sim["total_line"] = game.get("total_line", np.nan)
            sim["season"] = s
            sim["week"] = game["week"]
            results.append(sim)

        elapsed = time.time() - t0
        print(f"  Season {s}: {len(s_games)} games, {elapsed:.1f}s "
              f"({elapsed/len(s_games):.2f}s/game)")

    all_sims = pd.concat(results, ignore_index=True)
    return all_sims, actuals


def k1_report(all_sims, actuals):
    lines = []

    all_sims = all_sims.copy()
    all_sims["sim_margin"] = all_sims["home_score"] - all_sims["away_score"]
    all_sims["sim_total"] = all_sims["home_score"] + all_sims["away_score"]

    game_means = all_sims.groupby("game_id").agg(
        sim_margin=("sim_margin", "mean"),
        sim_total=("sim_total", "mean"),
        sim_plays=("plays", "mean"),
        sim_drives=("drives", "mean"),
        sim_h_pass=("home_pass_yds", "mean"),
        sim_h_rush=("home_rush_yds", "mean"),
        sim_a_pass=("away_pass_yds", "mean"),
        sim_a_rush=("away_rush_yds", "mean"),
        actual_home=("actual_home", "first"),
        actual_away=("actual_away", "first"),
        spread_line=("spread_line", "first"),
        total_line=("total_line", "first"),
        season=("season", "first"),
        week=("week", "first"),
    ).reset_index()
    game_means["actual_margin"] = game_means["actual_home"] - game_means["actual_away"]
    game_means["actual_total"] = game_means["actual_home"] + game_means["actual_away"]

    sim_pts = (all_sims["home_score"].mean() + all_sims["away_score"].mean()) / 2
    act_pts = (actuals["home_score"].mean() + actuals["away_score"].mean()) / 2

    # Pooled SD: SD of ALL individual simulated margins (every sim of every game)
    pooled_sim_margin_sd = all_sims["sim_margin"].std()
    actual_margins_all = actuals["home_score"] - actuals["away_score"]
    act_margin_sd = float(actual_margins_all.std())  # ~14.2

    # Pooled total SD
    pooled_sim_total_sd = all_sims["sim_total"].std()
    act_total_sd = float((actuals["home_score"] + actuals["away_score"]).std())

    # Team differentiation (informational): SD of sim MEAN margin across games
    # vs SD of closing spreads — D7 anchoring supplies the mean
    diff_sim_sd = game_means["sim_margin"].std()
    spread_sd = game_means["spread_line"].astype(float).std()

    lines.append("## K1 Realism Check\n")
    lines.append("| Metric | Sim | Actual | Target | PASS/FAIL |")
    lines.append("|--------|-----|--------|--------|-----------|")

    def pf(cond):
        return "PASS" if cond else "FAIL"

    lines.append(f"| Mean pts/team | {sim_pts:.1f} | {act_pts:.1f} | ±1.5 of actual | {pf(abs(sim_pts-act_pts)<1.5)} |")

    sim_ppg = game_means["sim_plays"].mean()
    lines.append(f"| Plays/game | {sim_ppg:.1f} | 124.5 | ~125 | {pf(abs(sim_ppg-124.5)<20)} |")

    sim_dpg = game_means["sim_drives"].mean()
    lines.append(f"| Drives/game | {sim_dpg:.1f} | 21.9 | ~22 | {pf(abs(sim_dpg-21.9)<5)} |")

    lines.append(f"| SD margin (pooled) | {pooled_sim_margin_sd:.2f} | {act_margin_sd:.2f} | ±1.0 of actual | {pf(abs(pooled_sim_margin_sd-act_margin_sd)<=1.0)} |")
    lines.append(f"| SD total (pooled) | {pooled_sim_total_sd:.2f} | {act_total_sd:.2f} | ±2.0 of actual | {pf(abs(pooled_sim_total_sd-act_total_sd)<=2.0)} |")
    lines.append(f"| SD sim mean margin | {diff_sim_sd:.2f} | spread SD {spread_sd:.2f} | INFO | INFO |")

    actual_margins = actuals["home_score"] - actuals["away_score"]
    for m, target, tol in [(3, 14.27, 2), (6, 7.54, 2), (7, 8.24, 2), (10, 5.06, 2), (14, 4.32, 2)]:
        sim_pct = all_sims.groupby("game_id")["sim_margin"].apply(
            lambda x: (x.abs() == m).mean()).mean() * 100
        act_pct = (actual_margins.abs() == m).mean() * 100
        lines.append(f"| P(|margin|={m}) | {sim_pct:.2f}% | {act_pct:.2f}% | {target}%±{tol} | {pf(abs(sim_pct-target)<=tol)} |")

    sim_pass = (all_sims["home_pass_yds"].mean() + all_sims["away_pass_yds"].mean()) / 2
    sim_rush = (all_sims["home_rush_yds"].mean() + all_sims["away_rush_yds"].mean()) / 2
    lines.append(f"| Pass yds/team/game | {sim_pass:.1f} | 221.0 | ~221 | {pf(abs(sim_pass-221)<40)} |")
    lines.append(f"| Rush yds/team/game | {sim_rush:.1f} | 118.2 | ~118 | {pf(abs(sim_rush-118)<30)} |")

    corr = game_means["sim_margin"].corr(game_means["spread_line"].astype(float))
    lines.append(f"| corr(sim margin, spread) | {corr:.3f} | - | ~0.8 (info) | INFO |")
    lines.append("")

    # Home win prob calibration
    lines.append("### Home Win Probability Calibration\n")
    game_hw = all_sims.groupby("game_id").agg(
        p_home_win=("sim_margin", lambda x: (x > 0).mean()),
        actual_home=("actual_home", "first"),
        actual_away=("actual_away", "first"),
    ).reset_index()
    game_hw["actual_hw"] = (game_hw["actual_home"] > game_hw["actual_away"]).astype(int)
    try:
        game_hw["dec"] = pd.qcut(game_hw["p_home_win"], 10, labels=False, duplicates="drop")
    except ValueError:
        game_hw["dec"] = pd.cut(game_hw["p_home_win"], 10, labels=False)

    lines.append("| Decile | Sim P(HW) | Actual HW | N |")
    lines.append("|--------|----------|----------|---|")
    for d in sorted(game_hw["dec"].dropna().unique()):
        g = game_hw[game_hw["dec"] == d]
        lines.append(f"| {int(d)} | {g['p_home_win'].mean():.3f} | {g['actual_hw'].mean():.3f} | {len(g)} |")

    # Total calibration
    lines.append("\n### Total Calibration\n")
    game_tot = all_sims.groupby("game_id").agg(
        actual_total=("actual_home", lambda x: x.iloc[0] + all_sims.loc[x.index, "actual_away"].iloc[0]),
        total_line=("total_line", "first"),
    )
    # P(over actual closing total) per game
    for gid in game_tot.index:
        gm = all_sims[all_sims["game_id"] == gid]
        game_tot.loc[gid, "p_over"] = (gm["sim_total"] > game_tot.loc[gid, "total_line"]).mean()
        game_tot.loc[gid, "actual_over"] = int(game_tot.loc[gid, "actual_total"] > game_tot.loc[gid, "total_line"])

    game_tot = game_tot.dropna(subset=["p_over"])
    try:
        game_tot["dec"] = pd.qcut(game_tot["p_over"], 10, labels=False, duplicates="drop")
    except ValueError:
        game_tot["dec"] = pd.cut(game_tot["p_over"], 5, labels=False)

    lines.append("| Decile | Sim P(over) | Actual over rate | N |")
    lines.append("|--------|------------|-----------------|---|")
    for d in sorted(game_tot["dec"].dropna().unique()):
        g = game_tot[game_tot["dec"] == d]
        lines.append(f"| {int(d)} | {g['p_over'].mean():.3f} | {g['actual_over'].mean():.3f} | {len(g)} |")

    lines.append("")

    # Check 5 breakdowns
    lines.append("### Check 5 Breakdowns\n")
    lines.append("**By season:**\n")
    lines.append("| Season | Sim pts/team | Actual pts/team | Sim margin SD | Actual margin SD |")
    lines.append("|--------|-------------|----------------|--------------|-----------------|")
    for s in sorted(game_means["season"].unique()):
        sg = game_means[game_means["season"] == s]
        ss = all_sims[all_sims["season"] == s]
        sp = (ss["home_score"].mean() + ss["away_score"].mean()) / 2
        ap = (sg["actual_home"].mean() + sg["actual_away"].mean()) / 2
        ssd = sg["sim_margin"].std()
        asd = sg["actual_margin"].std()
        lines.append(f"| {s} | {sp:.1f} | {ap:.1f} | {ssd:.2f} | {asd:.2f} |")

    lines.append("\n**By week range:**\n")
    lines.append("| Weeks | Sim pts/team | Actual pts/team |")
    lines.append("|-------|-------------|----------------|")
    for wl, wh, label in [(1, 4, "1-4"), (5, 18, "5-18")]:
        sg = game_means[(game_means["week"] >= wl) & (game_means["week"] <= wh)]
        ss = all_sims[(all_sims["week"] >= wl) & (all_sims["week"] <= wh)]
        sp = (ss["home_score"].mean() + ss["away_score"].mean()) / 2
        ap = (sg["actual_home"].mean() + sg["actual_away"].mean()) / 2
        lines.append(f"| {label} | {sp:.1f} | {ap:.1f} |")

    lines.append("\n**By favourite size (|closing spread|):**\n")
    lines.append("| Bucket | Sim pts/team | Actual pts/team | N |")
    lines.append("|--------|-------------|----------------|---|")
    for lo, hi, label in [(0, 3, "<3"), (3, 7, "3-7"), (7, 100, ">7")]:
        sg = game_means[(game_means["spread_line"].abs() >= lo) & (game_means["spread_line"].abs() < hi)]
        if len(sg) == 0:
            continue
        ss = all_sims[all_sims["game_id"].isin(sg["game_id"])]
        sp = (ss["home_score"].mean() + ss["away_score"].mean()) / 2
        ap = (sg["actual_home"].mean() + sg["actual_away"].mean()) / 2
        lines.append(f"| {label} | {sp:.1f} | {ap:.1f} | {len(sg)} |")

    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    print(f"Running K1 backtest with N={n}...")
    t0 = time.time()
    all_sims, actuals = k1_backtest(n_sims=n)
    total = time.time() - t0
    print(f"\nTotal: {total:.1f}s")

    report = k1_report(all_sims, actuals)
    print("\n" + report)

    out = ROOT / "research" / "nfl_sim" / "phase2a_realism_report.md"
    with open(out, "w") as f:
        f.write("# Phase 2A: Vectorised Play-Level Engine - K1 Realism Report\n\n")
        f.write("**Data:** 2021-2024 regular season only. 2025/2026 NOT used.\n\n")
        f.write(f"**Runtime:** {total:.1f}s total for {len(actuals)} games x {n} sims\n\n")
        f.write(report)
    print(f"\nSaved to {out}")
