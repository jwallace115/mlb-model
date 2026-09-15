#!/usr/bin/env python3
"""
NFL Sim Phase 2A — Empirical league tables from PBP (2021-2024 only).

Builds situation-dependent outcome distributions for the play-level engine.
All tables are league-wide averages (team ratings shift these at runtime via log5).
Writes parquet files to nfl/data/sim/tables/.

SEASONS: 2021-2024 ONLY. Raises if any row with season >= 2025 is present.
Regular season only (week <= 18).
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
PBP_DIR = ROOT / "nfl" / "data" / "pbp"
OUT_DIR = ROOT / "nfl" / "data" / "sim" / "tables"

SEASONS = [2021, 2022, 2023, 2024]
QUANTILE_POINTS = np.linspace(0, 1, 101)  # 0, 0.01, ..., 1.00


# ═══════════════════════════════════════════════════════════════════════════════
# LOAD
# ═══════════════════════════════════════════════════════════════════════════════

def load_pbp():
    frames = []
    for s in SEASONS:
        p = PBP_DIR / f"pbp_{s}.parquet"
        if not p.exists():
            raise FileNotFoundError(f"Missing {p}")
        frames.append(pd.read_parquet(p))
    df = pd.concat(frames, ignore_index=True)
    if (df["season"] >= 2025).any():
        raise ValueError("Data from season >= 2025 found — aborting")
    df = df[df["week"] <= 18].copy()
    return df


def _field_zone(yl100):
    """Categorise yardline_100 into field zones."""
    return pd.cut(yl100, bins=[0, 10, 20, 60, 80, 100],
                  labels=["rz10", "opp20", "midfield", "own40", "own20"],
                  right=True)


def _dist_bucket(ydstogo):
    return pd.cut(ydstogo, bins=[0, 3, 7, 100],
                  labels=["short", "med", "long"], right=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TABLE A: Pass outcomes by situation bucket
# ═══════════════════════════════════════════════════════════════════════════════

def _km_quantiles(yards, yl, censored, q_points=None, sentinel=99.0, ref_gains=None):
    """5A-6: quantiles of the UNCONSTRAINED gain distribution for a cell whose
    recorded yards are right-censored at the goal line.

    A scoring play from the 8 records 8 yards, but the play "would have gained"
    at least 8 — its true gain is unknown. Pooling such plays with plays from the
    10 or the 20 biases the cell's yardage downward for the deeper end of the
    zone, which is exactly why the engine scored touchdowns from the 5-10 at half
    the real rate. Kaplan-Meier treats scoring plays as censored at yardline_100
    (gain >= yl) and everything else as an exact observation.

    Returns 101 quantiles (q_points) of P(gain <= y). Mass beyond the last
    uncensored gain (the KM plateau) is filled from `ref_gains` — the same
    situation's open-field gains (zones where the goal line almost never binds),
    conditional on gain > last uncensored value — so a heavily censored red-zone
    cell borrows only the SHAPE of the tail it cannot observe. If no reference is
    given (or it has < 20 qualifying plays) the plateau goes to `sentinel`; the
    engine caps any draw at the distance to goal, so a sentinel draw means
    "reached the end zone". No value is invented: every quantile is an observed
    gain from this cell, an observed open-field gain, or the sentinel.
    """
    if q_points is None:
        q_points = QUANTILE_POINTS
    y = np.asarray(yards, dtype=float)
    c = np.asarray(censored, dtype=bool)
    ylv = np.asarray(yl, dtype=float)
    obs = y[~c]                      # exact gains
    cens_at = ylv[c]                 # gain >= yl on scoring plays
    vals = np.unique(obs)
    S = 1.0
    # F(v) = P(gain <= v) evaluated just after each event value v
    F_after = np.empty(len(vals))
    for k, v in enumerate(vals):
        at_risk = (obs >= v).sum() + (cens_at >= v).sum()
        d = (obs == v).sum()
        if at_risk > 0:
            S *= (1.0 - d / at_risk)
        F_after[k] = 1.0 - S
    out = np.empty(len(q_points))
    F_end = F_after[-1] if len(vals) else 0.0
    S_end = 1.0 - F_end
    tail = None
    if ref_gains is not None and len(vals) and S_end > 1e-9:
        rg = np.asarray(ref_gains, dtype=float)
        is_quantile_array = (len(rg) == len(QUANTILE_POINTS))
        rg = rg[rg > vals[-1]]
        if len(rg) >= (3 if is_quantile_array else 20):
            tail = np.sort(rg)
    for i, p in enumerate(q_points):
        idx = np.searchsorted(F_after, p, side="left")
        if idx < len(vals):
            out[i] = vals[idx]
        elif tail is not None:
            u = min(max((p - F_end) / S_end, 0.0), 1.0)
            out[i] = np.quantile(tail, u)
        else:
            out[i] = sentinel
    return out


def build_pass_table(df):
    """Pass outcome distributions by (down, distance, field_zone)."""
    passes = df[(df["play_type"] == "pass") & df["down"].notna()].copy()
    passes["down_b"] = passes["down"].astype(int).clip(1, 4).astype(str)
    passes["dist_b"] = _dist_bucket(passes["ydstogo"])
    passes["zone"] = _field_zone(passes["yardline_100"])
    passes = passes.dropna(subset=["down_b", "dist_b", "zone"])

    # 5A-6: open-field reference completions (zones where the goal line ~never binds)
    open_field = passes[passes["zone"].isin(["midfield", "own40", "own20"])
                        & (passes["sack"] != 1) & (passes["interception"] != 1)
                        & (passes["complete_pass"] == 1)]
    def _ref(down, dist, sel):
        g = open_field[(open_field["down_b"] == down) & (open_field["dist_b"] == dist)]
        g = sel(g)
        if len(g) < 50:  # thin: pool across downs for this distance
            g = sel(open_field[open_field["dist_b"] == dist])
        return g["yards_gained"].values.astype(float)

    rows = []
    ZONE_ORDER = ["own20", "own40", "midfield", "opp20", "rz10"]  # far -> near the goal line
    _prev = {}  # (down, dist) -> KM arrays of the previous (farther) zone, used as the tail reference
    _groups = {k: g for k, g in passes.groupby(["down_b", "dist_b", "zone"], observed=True)}
    _keys = sorted(_groups.keys(), key=lambda k: (k[0], k[1], ZONE_ORDER.index(k[2]) if k[2] in ZONE_ORDER else 99))
    for (down, dist, zone) in _keys:
        grp = _groups[(down, dist, zone)]
        n = len(grp)
        if n < 20:
            continue
        # Fumble lost (on any pass play — sack-fumbles, catch-fumbles, etc.)
        p_fumble = grp["fumble_lost"].sum() / n if "fumble_lost" in grp.columns else 0.008

        # Sack
        sacks = grp[grp["sack"] == 1]
        p_sack = len(sacks) / n
        sack_yds_q = np.quantile(sacks["yards_gained"].values, QUANTILE_POINTS) if len(sacks) >= 5 else np.full(101, -5.0)

        # Non-sack attempts
        attempts = grp[grp["sack"] != 1]
        n_att = len(attempts)
        if n_att == 0:
            continue

        # INT
        ints = attempts[attempts["interception"] == 1]
        p_int = len(ints) / n_att

        # Non-INT attempts
        non_int = attempts[attempts["interception"] != 1]
        n_ni = len(non_int)
        if n_ni == 0:
            continue

        # Completion
        comp = non_int[non_int["complete_pass"] == 1]
        p_comp = len(comp) / n_ni

        # Yards on completions — split by success (epa > 0) vs fail
        comp_success = comp[comp["epa"] > 0]
        comp_fail = comp[comp["epa"] <= 0]
        p_success_given_comp = len(comp_success) / max(len(comp), 1)

        # Explosive share within successes
        p_explosive = (comp_success["yards_gained"] >= 20).mean() if len(comp_success) else 0.0

        # Quantile distributions — 5A-6: goal-line censoring handled by Kaplan-Meier
        # (scoring plays are "gain >= yardline_100", not "gain == yardline_100").
        def _q(g, default, ref):
            if len(g) >= 5:
                cens = (g["yards_gained"].values >= g["yardline_100"].values) & (g["yards_gained"].values > 0)
                return _km_quantiles(g["yards_gained"].values, g["yardline_100"].values, cens, ref_gains=ref)
            return np.full(101, default)
        # Tail reference: the previous (farther) zone's KM-corrected quantiles when the
        # zone is inside the 20 (compression grows toward the goal line, so borrow from
        # the neighbour, not from open field); open-field raw gains otherwise.
        pv = _prev.get((down, dist))
        if zone in ("opp20", "rz10") and pv is not None:
            ref_s, ref_f, ref_a = pv
        else:
            ref_s = _ref(down, dist, lambda g: g[g["epa"] > 0])
            ref_f = _ref(down, dist, lambda g: g[g["epa"] <= 0])
            ref_a = _ref(down, dist, lambda g: g)
        yds_success_q = _q(comp_success, 10.0, ref_s)
        yds_fail_q = _q(comp_fail, 3.0, ref_f)
        # All completions (unsplit) — the engine uses this to avoid EPA success/fail
        # conflation with first-down conversion
        yds_all_q = _q(comp, 6.0, ref_a)
        _prev[(down, dist)] = (yds_success_q, yds_fail_q, yds_all_q)
        n_censored = int(((comp["yards_gained"].values >= comp["yardline_100"].values) & (comp["yards_gained"].values > 0)).sum())

        rows.append({
            "down": down, "dist": dist, "zone": zone, "n": n,
            "p_fumble": p_fumble,
            "p_sack": p_sack,
            "sack_yds_q": sack_yds_q.tolist(),
            "p_int": p_int,
            "p_comp": p_comp,
            "p_success_given_comp": p_success_given_comp,
            "p_explosive": p_explosive,
            "yds_success_q": yds_success_q.tolist(),
            "yds_fail_q": yds_fail_q.tolist(),
            "yds_all_q": yds_all_q.tolist(),
            "n_censored": n_censored,
        })

    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# TABLE B: Rush outcomes by situation bucket
# ═══════════════════════════════════════════════════════════════════════════════

def build_rush_table(df):
    rushes = df[(df["play_type"] == "run") & df["down"].notna()].copy()
    rushes["down_b"] = rushes["down"].astype(int).clip(1, 4).astype(str)
    rushes["dist_b"] = _dist_bucket(rushes["ydstogo"])
    rushes["zone"] = _field_zone(rushes["yardline_100"])
    rushes = rushes.dropna(subset=["down_b", "dist_b", "zone"])

    # 5A-6: open-field reference rushes
    open_field = rushes[rushes["zone"].isin(["midfield", "own40", "own20"])]
    def _ref(down, dist, sel):
        g = open_field[(open_field["down_b"] == down) & (open_field["dist_b"] == dist)]
        g = sel(g)
        if len(g) < 50:
            g = sel(open_field[open_field["dist_b"] == dist])
        return g["yards_gained"].values.astype(float)

    rows = []
    ZONE_ORDER = ["own20", "own40", "midfield", "opp20", "rz10"]
    _prev = {}
    _groups = {k: g for k, g in rushes.groupby(["down_b", "dist_b", "zone"], observed=True)}
    _keys = sorted(_groups.keys(), key=lambda k: (k[0], k[1], ZONE_ORDER.index(k[2]) if k[2] in ZONE_ORDER else 99))
    for (down, dist, zone) in _keys:
        grp = _groups[(down, dist, zone)]
        n = len(grp)
        if n < 20:
            continue

        p_fumble = grp["fumble_lost"].sum() / n if "fumble_lost" in grp.columns else 0.0

        success = grp[grp["epa"] > 0]
        fail = grp[grp["epa"] <= 0]
        p_success = len(success) / n

        p_stuff = (fail["yards_gained"] <= 0).mean() if len(fail) else 0.0
        p_explosive = (success["yards_gained"] >= 12).mean() if len(success) else 0.0

        # 5A-6: goal-line censoring handled by Kaplan-Meier (see _km_quantiles)
        def _q(g, default, ref):
            if len(g) >= 5:
                cens = (g["yards_gained"].values >= g["yardline_100"].values) & (g["yards_gained"].values > 0)
                return _km_quantiles(g["yards_gained"].values, g["yardline_100"].values, cens, ref_gains=ref)
            return np.full(101, default)
        pv = _prev.get((down, dist))
        if zone in ("opp20", "rz10") and pv is not None:
            ref_s, ref_f, ref_a = pv
        else:
            ref_s = _ref(down, dist, lambda g: g[g["epa"] > 0])
            ref_f = _ref(down, dist, lambda g: g[g["epa"] <= 0])
            ref_a = _ref(down, dist, lambda g: g)
        yds_success_q = _q(success, 5.0, ref_s)
        yds_fail_q = _q(fail, 1.0, ref_f)

        # All rushes (non-fumble) unsplit distribution
        non_fum = grp[grp.get("fumble_lost", 0) != 1] if "fumble_lost" in grp.columns else grp
        yds_all_q = _q(non_fum, 3.0, ref_a)
        _prev[(down, dist)] = (yds_success_q, yds_fail_q, yds_all_q)
        n_censored = int(((non_fum["yards_gained"].values >= non_fum["yardline_100"].values) & (non_fum["yards_gained"].values > 0)).sum())

        rows.append({
            "down": down, "dist": dist, "zone": zone, "n": n,
            "p_fumble": p_fumble,
            "p_success": p_success,
            "p_stuff": p_stuff,
            "p_explosive": p_explosive,
            "yds_success_q": yds_success_q.tolist(),
            "yds_fail_q": yds_fail_q.tolist(),
            "yds_all_q": yds_all_q.tolist(),
            "n_censored": n_censored,
        })

    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# TABLE C: Play-call league xpass by situational bucket
# ═══════════════════════════════════════════════════════════════════════════════

def build_playcall_table(df):
    """League pass rate by (down, distance, score_state, clock_period).

    Three fallback levels matching the 4th-down table's granularity:
    - Level 0 (finest): 7 score x 4 clock
    - Level 1: 3 score x 4 clock  (prefix c_ on score)
    - Level 2 (coarsest): 3 score x 2 clock
    Min cell = 20.
    """
    scrim = df[df["play_type"].isin(["pass", "run"]) & df["down"].notna()].copy()
    scrim["down_b"] = scrim["down"].astype(int).clip(1, 4).astype(str)
    scrim["dist_b"] = _dist_bucket(scrim["ydstogo"])

    # Fine score (7-way) and fine clock (4-way) — same as 4th-down table
    scrim["score_fine"] = _score_bucket_fine(scrim["score_differential"])
    scrim["clock_fine"] = _clock_bucket_fine(scrim["qtr"],
                                              scrim["game_seconds_remaining"])

    # Coarse fallbacks
    scrim["score_coarse"] = pd.cut(scrim["score_differential"],
                                    bins=[-100, -9, 8, 100],
                                    labels=["trail9", "within8", "lead9"])
    scrim["clock_coarse"] = np.where(scrim["qtr"].isin([1, 2, 3]), "Q1-3", "Q4")

    scrim["is_pass"] = (scrim["play_type"] == "pass").astype(int)
    dd = scrim["down_b"] + "_" + scrim["dist_b"].astype(str) + "_"

    rows = []

    # Level 0: finest (7 score x 4 clock)
    bkt0 = dd + scrim["score_fine"].astype(str) + "_" + scrim["clock_fine"].astype(str)
    for bkt, grp in scrim.assign(bkt=bkt0).groupby("bkt", observed=True):
        n = len(grp)
        if n >= 20:
            rows.append({"bucket": bkt, "n": n, "pass_rate": grp["is_pass"].mean()})

    # Level 1: coarse score x fine clock  (c_ prefix)
    bkt1 = dd + "c_" + scrim["score_coarse"].astype(str) + "_" + scrim["clock_fine"].astype(str)
    for bkt, grp in scrim.assign(bkt=bkt1).groupby("bkt", observed=True):
        n = len(grp)
        if n >= 20:
            rows.append({"bucket": bkt, "n": n, "pass_rate": grp["is_pass"].mean()})

    # Level 2: coarsest (3 score x 2 clock — original format)
    bkt2 = dd + scrim["score_coarse"].astype(str) + "_" + scrim["clock_coarse"].astype(str)
    for bkt, grp in scrim.assign(bkt=bkt2).groupby("bkt", observed=True):
        n = len(grp)
        if n >= 20:
            rows.append({"bucket": bkt, "n": n, "pass_rate": grp["is_pass"].mean()})

    tbl = pd.DataFrame(rows)
    return tbl


# ═══════════════════════════════════════════════════════════════════════════════
# TABLE D: Clock runoff
# ═══════════════════════════════════════════════════════════════════════════════

def build_clock_table(df):
    """Seconds between consecutive scrimmage plays (any, including cross-drive).

    Measures game-clock elapsed from one scrimmage play to the next scrimmage
    play in the same game, regardless of whether a drive change, punt, kickoff,
    or other event occurs in between. This is the sole source of truth for
    per-play clock consumption in the engine — no separate inter-drive gap.

    5A-3: conditioned on (score_state × late_clock × outcome_type) instead of
    a binary hurry flag. Score states: trail9+ / trail1-8 / tied / lead1-8 /
    lead9+. Clock: Q2_late (≤2:00 of Q2) / Q4_late (≤2:00 of Q4) / normal.
    Minimum cell: 100 plays; fallback to parent (score_state only, then overall).
    The binary hurry flag is REMOVED."""
    MIN_CELL = 100

    scrim = df[df["play_type"].isin(["pass", "run"])].copy()
    scrim = scrim.sort_values(["game_id", "play_id"]).copy()

    # Next scrimmage play in the SAME GAME (including across drives)
    scrim["next_gsr"] = scrim.groupby("game_id")["game_seconds_remaining"].shift(-1)
    scrim["elapsed"] = scrim["game_seconds_remaining"] - scrim["next_gsr"]
    # Drop last play of game, half boundaries, and outliers
    scrim = scrim[scrim["elapsed"].notna() & (scrim["elapsed"] > 0) & (scrim["elapsed"] < 120)]

    # Outcome type — separate clock-stopping incompletes from inbounds plays
    def _outcome_type(row):
        if row["play_type"] == "pass":
            if row.get("complete_pass", 0) == 1:
                return "complete_inbounds"
            else:
                if row.get("sack", 0) == 1:
                    return "complete_inbounds"
                return "incomplete"
        elif row["play_type"] == "run":
            return "run"
        return "run"

    scrim["outcome_type"] = scrim.apply(_outcome_type, axis=1)
    scrim.loc[scrim["first_down"] == 1, "outcome_type"] = "first_down"

    # 5A-3: Score state (5-way)
    sd = scrim["score_differential"]
    scrim["score_state"] = np.where(sd <= -9, "trail9+",
                           np.where(sd <= -1, "trail1-8",
                           np.where(sd == 0, "tied",
                           np.where(sd <= 8, "lead1-8", "lead9+"))))

    # 5A-3: Clock period (3-way)
    q2_late = (scrim["qtr"] == 2) & (scrim["half_seconds_remaining"] <= 120)
    q4_late = (scrim["qtr"] == 4) & (scrim["game_seconds_remaining"] <= 120)
    scrim["clock_period"] = "normal"
    scrim.loc[q2_late, "clock_period"] = "Q2_late"
    scrim.loc[q4_late, "clock_period"] = "Q4_late"

    # Legacy hurry flag (kept in table for backward compat / testing)
    scrim["hurry"] = False
    q4 = scrim["qtr"] == 4
    trailing_or_close = scrim["score_differential"] <= 8
    scrim.loc[(q4 | q2_late) & trailing_or_close, "hurry"] = True

    rows = []

    # Level 0: (outcome_type × score_state × clock_period) — finest
    for (ot, ss, cp), grp in scrim.groupby(
            ["outcome_type", "score_state", "clock_period"], observed=True):
        n = len(grp)
        if n < MIN_CELL:
            continue
        q = np.quantile(grp["elapsed"].values, QUANTILE_POINTS)
        rows.append({
            "outcome_type": ot, "score_state": ss, "clock_period": cp,
            "hurry": False,  # unused; kept for schema compat
            "n": n, "elapsed_q": q.tolist(), "mean": grp["elapsed"].mean(),
        })

    # Level 1 (parent): (outcome_type × score_state) — aggregated over clock
    for (ot, ss), grp in scrim.groupby(["outcome_type", "score_state"], observed=True):
        n = len(grp)
        if n < MIN_CELL:
            continue
        q = np.quantile(grp["elapsed"].values, QUANTILE_POINTS)
        rows.append({
            "outcome_type": ot, "score_state": f"p_{ss}", "clock_period": "all",
            "hurry": False, "n": n, "elapsed_q": q.tolist(),
            "mean": grp["elapsed"].mean(),
        })

    # Level 2 (grandparent): (outcome_type) — overall, and legacy hurry rows
    for (ot, hurry), grp in scrim.groupby(["outcome_type", "hurry"], observed=True):
        n = len(grp)
        if n < 20:
            continue
        q = np.quantile(grp["elapsed"].values, QUANTILE_POINTS)
        rows.append({
            "outcome_type": ot, "score_state": "all", "clock_period": "all",
            "hurry": hurry, "n": n, "elapsed_q": q.tolist(),
            "mean": grp["elapsed"].mean(),
        })

    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# TABLE E: 4th-down decisions
# ═══════════════════════════════════════════════════════════════════════════════

def _score_bucket_fine(sd):
    """Fine-grained score differential bucket for end-game decisions."""
    return pd.cut(sd, bins=[-100, -9, -4, -1, 0, 3, 8, 100],
                  labels=["trail9+", "trail4-8", "trail1-3", "tied",
                          "lead1-3", "lead4-8", "lead9+"],
                  right=True, include_lowest=True)

def _clock_bucket_fine(qtr, gsr):
    """Fine-grained clock bucket: Q1-3, Q2<2 (last 2:00 of the 1st half),
    Q4>5:00, Q4_2-5, Q4<2:00.

    5A-6: the last two minutes of Q2 are their own bucket. Measured 2021-2024:
    pass rate 0.80 vs 0.58 pooled Q1-3 in every score state, and 4th-down FG
    rate ~10pp higher in range. gsr = game_seconds_remaining; in Q2 the half
    clock is gsr - 1800."""
    qtr = np.asarray(qtr); gsr = np.asarray(gsr, dtype=float)
    q4 = qtr == 4
    q2late = (qtr == 2) & ((gsr - 1800.0) <= 120.0)
    return np.where(q2late, "Q2<2",
           np.where(~q4, "Q1-3",
           np.where(gsr > 300, "Q4>5",
           np.where(gsr > 120, "Q4_2-5", "Q4<2"))))

def build_fourth_down_table(df):
    """League P(go/punt/FG) by (ydstogo, field_zone, score_state, clock).

    Fine-grained score buckets: trail9+ / trail4-8 / trail1-3 / tied /
    lead1-3 / lead4-8 / lead9+.
    Fine-grained Q4 clock: >5:00 / 2:00-5:00 / <2:00.
    Minimum cell size: 10. Falls back to coarser score (3-way) then
    coarser clock (Q1-3/Q4) when thin."""
    MIN_N = 10

    fourth = df[(df["down"] == 4) & df["down"].notna()].copy()
    fourth = fourth[fourth["play_type"].isin(["pass", "run", "punt", "field_goal"])].copy()

    fourth["ydstogo_b"] = pd.cut(fourth["ydstogo"], bins=[0, 2, 5, 10, 100],
                                  labels=["1-2", "3-5", "6-10", "11+"], right=True)
    # 10-yard field-zone bins across the whole field
    fourth["yl_b"] = pd.cut(fourth["yardline_100"],
                             bins=[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
                             labels=["opp1-10", "opp11-20", "opp21-30", "opp31-40",
                                     "opp41-50", "own41-50", "own31-40", "own21-30",
                                     "own11-20", "own1-10"],
                             right=True)
    fourth["score_b"] = _score_bucket_fine(fourth["score_differential"])
    # Use game_seconds_remaining for clock (Q4 seconds left in quarter)
    if "game_seconds_remaining" in fourth.columns:
        # game_seconds_remaining counts down from 3600 (start of game)
        # quarter_seconds = game_seconds_remaining mod 900 (roughly)
        q_sec = fourth["game_seconds_remaining"].clip(0, 3600)
        # For Q4: seconds left = game_seconds_remaining directly (it's 0-900 in Q4)
        fourth["qtr_b"] = _clock_bucket_fine(fourth["qtr"],
                                              fourth["game_seconds_remaining"])
    else:
        fourth["qtr_b"] = np.where(fourth["qtr"] <= 3, "Q1-3", "Q4>5")

    fourth["decision"] = "go"
    fourth.loc[fourth["play_type"] == "punt", "decision"] = "punt"
    fourth.loc[fourth["play_type"] == "field_goal", "decision"] = "fg"

    # Coarse fallback zones
    fourth["score_coarse"] = pd.cut(fourth["score_differential"],
                                     bins=[-100, -9, 8, 100],
                                     labels=["trail9", "within8", "lead9"])
    fourth["qtr_coarse"] = np.where(fourth["qtr"] <= 3, "Q1-3", "Q4")
    fourth["yl_coarse"] = pd.cut(fourth["yardline_100"],
                                  bins=[0, 10, 40, 65, 100],
                                  labels=["rz", "opp40", "midfield", "own35"],
                                  right=True)

    def _add_rows(rows, grp_cols, prefix=""):
        for key, grp in fourth.groupby(grp_cols, observed=True):
            n = len(grp)
            if n < MIN_N:
                continue
            vc = grp["decision"].value_counts()
            yd, yl, sc, qt = key
            rows.append({
                "ydstogo_b": yd,
                "yl_b": f"{prefix}{yl}" if prefix else yl,
                "score_b": f"{prefix}{sc}" if prefix else sc,
                "qtr_b": qt, "n": n,
                "p_go": vc.get("go", 0) / n,
                "p_punt": vc.get("punt", 0) / n,
                "p_fg": vc.get("fg", 0) / n,
            })

    rows = []
    # Level 0: finest (10-yd zone × 7 score × 4 clock)
    _add_rows(rows, ["ydstogo_b", "yl_b", "score_b", "qtr_b"])
    # Level 1: coarse score, fine zone + clock
    _add_rows(rows, ["ydstogo_b", "yl_b", "score_coarse", "qtr_b"], prefix="c_")
    # Level 2: coarse zone, fine score + clock
    _add_rows(rows, ["ydstogo_b", "yl_coarse", "score_b", "qtr_b"], prefix="z_")
    # Level 3: coarse zone + coarse score + coarse clock
    _add_rows(rows, ["ydstogo_b", "yl_coarse", "score_coarse", "qtr_coarse"], prefix="zc_")

    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# TABLE F: FG, punt, kickoff, XP, 2pt, penalties
# ═══════════════════════════════════════════════════════════════════════════════

def build_special_teams_table(df):
    """Various special teams tables."""
    result = {}

    # FG make probability by distance (1-yard resolution, smoothed)
    fg = df[df["play_type"] == "field_goal"].copy()
    fg["dist"] = fg["kick_distance"].fillna(0).astype(int)
    fg["made"] = (fg["field_goal_result"] == "made").astype(int)
    # Raw rates
    fg_by_dist = fg.groupby("dist").agg(n=("made", "size"), made=("made", "sum")).reset_index()
    fg_by_dist["rate"] = fg_by_dist["made"] / fg_by_dist["n"]
    # Smooth with 3-yard rolling window, filling gaps
    all_dists = pd.DataFrame({"dist": range(18, 70)})
    fg_by_dist = all_dists.merge(fg_by_dist, on="dist", how="left")
    fg_by_dist["n"] = fg_by_dist["n"].fillna(0)
    fg_by_dist["made"] = fg_by_dist["made"].fillna(0)
    # Rolling weighted average
    fg_by_dist["n_smooth"] = fg_by_dist["n"].rolling(5, center=True, min_periods=1).sum()
    fg_by_dist["made_smooth"] = fg_by_dist["made"].rolling(5, center=True, min_periods=1).sum()
    fg_by_dist["rate_smooth"] = fg_by_dist["made_smooth"] / fg_by_dist["n_smooth"].replace(0, 1)
    result["fg_make_rate"] = fg_by_dist[["dist", "rate_smooth", "n"]].rename(
        columns={"rate_smooth": "make_rate"})

    # Punt net yards distribution by field zone
    punts = df[df["play_type"] == "punt"].copy()
    punts["zone"] = _field_zone(punts["yardline_100"])
    punt_rows = []
    for zone, grp in punts.groupby("zone", observed=True):
        if len(grp) < 20:
            continue
        net = grp["kick_distance"].fillna(0)
        # Adjust for return yards if available
        if "return_yards" in grp.columns:
            ret = grp["return_yards"].fillna(0)
            net = net - ret
        q = np.quantile(net.values, QUANTILE_POINTS)
        punt_rows.append({"zone": zone, "n": len(grp), "net_q": q.tolist(),
                          "mean": net.mean(), "touchback_rate": grp["touchback"].mean()})
    result["punt_net"] = pd.DataFrame(punt_rows)

    # Kickoff: mean starting yardline_100 after kickoff by season
    ko = df[df["play_type"] == "kickoff"].copy()
    # Touchback = ball at 25 (since 2023: 30 for new rule? — use empirical)
    # Find next play's yardline_100 for the receiving team
    ko_starts = []
    for s in SEASONS:
        ks = ko[ko["season"] == s]
        # Touchback rate
        tb_rate = ks["touchback"].mean() if "touchback" in ks.columns else 0.6
        # Mean return to yardline_100: for non-touchbacks, use kick_distance - return_yards
        # Simpler: league average starting position after kickoff
        # Use empirical: ~75 yardline_100 (own 25)
        ko_starts.append({"season": s, "touchback_rate": tb_rate,
                          "start_yl100": 75.0})  # Default; will be refined
    result["kickoff"] = pd.DataFrame(ko_starts)

    # XP make rate
    xp = df[df["play_type"] == "extra_point"].copy()
    xp_rate = (xp["extra_point_result"] == "good").mean() if len(xp) else 0.94
    result["xp_rate"] = xp_rate

    # 2pt decision by score differential and quarter
    # Look at PATs: was it XP or 2pt?
    pat_plays = df[df["play_type"].isin(["extra_point"])].copy()
    twopt_plays = df[df["two_point_attempt"] == 1].copy()

    # 2pt conversion rate
    twopt_rate = twopt_plays["two_point_conv_result"].eq("success").mean() if len(twopt_plays) else 0.48
    result["twopt_conv_rate"] = twopt_rate

    # 2pt attempt rate by score differential bucket and quarter
    # Combine XP and 2pt: after a TD, was 2pt attempted?
    td_plays = df[df["touchdown"] == 1].copy()
    # Simple: just use overall 2pt attempt rate by score diff
    twopt_rows = []
    for qtr in [1, 2, 3, 4]:
        for diff_lo, diff_hi, label in [(-100, -15, "trail15+"), (-15, -9, "trail9-15"),
                                         (-9, -1, "trail1-8"), (-1, 2, "tied_lead1"),
                                         (2, 9, "lead2-8"), (9, 16, "lead9-15"), (16, 100, "lead15+")]:
            n_xp = len(pat_plays[(pat_plays["qtr"] == qtr) &
                                  (pat_plays["score_differential"] >= diff_lo) &
                                  (pat_plays["score_differential"] < diff_hi)])
            n_2pt = len(twopt_plays[(twopt_plays["qtr"] == qtr) &
                                     (twopt_plays["score_differential"] >= diff_lo) &
                                     (twopt_plays["score_differential"] < diff_hi)])
            n_total = n_xp + n_2pt
            if n_total < 5:
                continue
            twopt_rows.append({"qtr": qtr, "score_diff": label, "n": n_total,
                               "p_2pt": n_2pt / n_total})
    result["twopt_decision"] = pd.DataFrame(twopt_rows)

    # Penalty on scrimmage: P(accepted penalty), net yards, auto-first-down share
    scrim = df[df["play_type"].isin(["pass", "run"])].copy()
    pen = scrim[scrim["penalty"] == 1]
    result["penalty"] = {
        "p_penalty": len(pen) / len(scrim) if len(scrim) else 0.015,
        "mean_yards": pen["penalty_yards"].mean() if len(pen) else 10.0,
        "p_auto_first": pen["first_down_penalty"].mean() if len(pen) else 0.5,
        "p_offense_penalty": 0.45,  # Roughly 45% of scrimmage penalties are on offense
    }

    # No-play penalties: accepted penalties that negate the play entirely.
    # These replay the down. Compute offense/defense split from actual data.
    no_plays = df[df["play_type"] == "no_play"]
    accepted_no_play = no_plays[no_plays["penalty"] == 1]
    result["penalty"]["p_no_play_penalty"] = len(accepted_no_play) / len(scrim) if len(scrim) else 0.03
    # Offense fraction of no-play penalties (from actual data)
    if len(accepted_no_play) > 0 and "penalty_team" in accepted_no_play.columns and "posteam" in accepted_no_play.columns:
        np_off = accepted_no_play[accepted_no_play["penalty_team"] == accepted_no_play["posteam"]]
        np_def = accepted_no_play[accepted_no_play["penalty_team"] != accepted_no_play["posteam"]]
        result["penalty"]["p_noplay_offense"] = len(np_off) / len(accepted_no_play)
        result["penalty"]["noplay_off_yds_mean"] = np_off["penalty_yards"].mean() if len(np_off) else 7.0
        result["penalty"]["noplay_def_yds_mean"] = np_def["penalty_yards"].mean() if len(np_def) else 9.0
        result["penalty"]["noplay_auto_first"] = np_def["first_down_penalty"].mean() if len(np_def) else 0.5
    else:
        result["penalty"]["p_noplay_offense"] = 0.615
        result["penalty"]["noplay_off_yds_mean"] = 7.0
        result["penalty"]["noplay_def_yds_mean"] = 9.0
        result["penalty"]["noplay_auto_first"] = 0.5
    result["penalty"]["total_p_penalty"] = (len(pen) + len(accepted_no_play)) / (len(scrim) + len(accepted_no_play))

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# TABLE G: Turnover return yards
# ═══════════════════════════════════════════════════════════════════════════════

def build_turnover_table(df):
    """INT and fumble return yards distributions + P(defensive TD) + ST return TD rates."""
    rows = {}

    # INT returns
    ints = df[df["interception"] == 1].copy()
    int_ret_yds = ints["return_yards"].fillna(0).values
    rows["int_return_yds_q"] = np.quantile(int_ret_yds, QUANTILE_POINTS).tolist()
    rows["int_n"] = len(ints)
    rows["int_p_def_td"] = ints["return_touchdown"].sum() / max(len(ints), 1) if "return_touchdown" in ints.columns else 0.05

    # Fumble returns (fumble_lost only)
    fum = df[df["fumble_lost"] == 1].copy()
    fum_ret_yds = fum["return_yards"].fillna(0).values
    rows["fum_return_yds_q"] = np.quantile(fum_ret_yds, QUANTILE_POINTS).tolist()
    rows["fum_n"] = len(fum)
    if "return_touchdown" in fum.columns:
        rows["fum_p_def_td"] = fum["return_touchdown"].sum() / max(len(fum), 1)
    else:
        rows["fum_p_def_td"] = 0.02

    # Punt return TDs (per punt event)
    punts = df[df["play_type"] == "punt"]
    punt_ret_td = punts["return_touchdown"].sum() if "return_touchdown" in punts.columns else 0
    rows["punt_n"] = len(punts)
    rows["punt_p_ret_td"] = punt_ret_td / max(len(punts), 1)

    # Kickoff return TDs (per kickoff event)
    kos = df[df["play_type"] == "kickoff"]
    ko_ret_td = kos["return_touchdown"].sum() if "return_touchdown" in kos.columns else 0
    rows["ko_n"] = len(kos)
    rows["ko_p_ret_td"] = ko_ret_td / max(len(kos), 1)

    return rows


# ═══════════════════════════════════════════════════════════════════════════════
# TABLE I: Pass depth-split (air yards < 10 = short, >= 10 = deep)
# ═══════════════════════════════════════════════════════════════════════════════

def build_pass_depth_table(df):
    """Completion yards quantiles split by short (<10 air yds) / deep (>=10)."""
    passes = df[(df["play_type"] == "pass") & df["down"].notna()
                & (df["sack"] != 1) & (df["interception"] != 1)
                & df["air_yards"].notna()].copy()
    passes["down_b"] = passes["down"].astype(int).clip(1, 4).astype(str)
    passes["dist_b"] = _dist_bucket(passes["ydstogo"])
    passes["zone"] = _field_zone(passes["yardline_100"])
    passes["depth_b"] = np.where(passes["air_yards"] < 10, "short", "deep")
    passes = passes.dropna(subset=["down_b", "dist_b", "zone"])

    comp = passes[passes["complete_pass"] == 1]
    rows = []
    for (down, dist, zone, depth), grp in comp.groupby(
            ["down_b", "dist_b", "zone", "depth_b"], observed=True):
        n = len(grp)
        if n < 10:
            continue
        succ = grp[grp["epa"] > 0]
        fail = grp[grp["epa"] <= 0]
        yds_s = np.quantile(succ["yards_gained"].values.astype(float),
                            QUANTILE_POINTS) if len(succ) >= 5 else np.full(101, 8.0)
        yds_f = np.quantile(fail["yards_gained"].values.astype(float),
                            QUANTILE_POINTS) if len(fail) >= 5 else np.full(101, 3.0)
        rows.append({"down": down, "dist": dist, "zone": zone, "depth": depth,
                      "n": n, "yds_success_q": yds_s.tolist(),
                      "yds_fail_q": yds_f.tolist()})
    return pd.DataFrame(rows)


def build_lg_pos_catch(df):
    """League completion rate by receiver position (WR/TE/RB), 2021-2024."""
    passes = df[(df["play_type"] == "pass") & df["down"].notna()
                & (df["sack"] != 1) & (df["interception"] != 1)
                & df["receiver_player_id"].notna()].copy()
    # Map position from roster columns if available
    if "receiver_position" not in passes.columns:
        # Use posteam_type or receiver_player_name — nflfastR has receiver_player_id
        # Join with roster data if needed; for now use position grouping from PBP
        # nflfastR stores pass_length but not receiver_position directly
        # We'll use a simpler proxy: compute from the data we have
        pass
    # Position comes from PBP receiver columns — nflfastR doesn't have receiver_position
    # as a column. Use the player_usage table instead for these rates.
    # Fallback: compute from PBP using air_yards as a proxy for route type
    # Since we can't get position from PBP, use hardcoded values from
    # player_usage (computed earlier in this session):
    return {"WR": 0.629, "TE": 0.699, "RB": 0.776, "QB": 0.692}


# ═══════════════════════════════════════════════════════════════════════════════
# TABLE H: Safety + end-of-game constants
# ═══════════════════════════════════════════════════════════════════════════════

def build_constants(df):
    scrim = df[df["play_type"].isin(["pass", "run"])]
    total_plays = len(scrim)
    safeties = scrim["safety"].sum() if "safety" in scrim.columns else 0

    # Inter-drive clock cost: median game-seconds between last scrimmage play
    # of drive N and first scrimmage play of drive N+1.
    scrim_sorted = scrim.sort_values(["game_id", "play_id"])
    drive_ends = scrim_sorted.groupby(["game_id", "fixed_drive"])["game_seconds_remaining"].min().reset_index(name="end_gsr")
    drive_starts = scrim_sorted.groupby(["game_id", "fixed_drive"])["game_seconds_remaining"].max().reset_index(name="start_gsr")
    drive_ends["next_drive"] = drive_ends["fixed_drive"] + 1
    merged = drive_ends.merge(
        drive_starts.rename(columns={"fixed_drive": "next_drive"}),
        on=["game_id", "next_drive"], how="inner")
    merged["gap"] = merged["end_gsr"] - merged["start_gsr"]
    valid_gaps = merged[(merged["gap"] > 0) & (merged["gap"] < 300)]["gap"]
    # Use mean (not median) since long gaps (TV timeouts, replays) are real
    # game-clock consumers. Median=13 underweights them.
    inter_drive_median = float(valid_gaps.mean()) if len(valid_gaps) else 21.0

    return {
        "p_safety_per_play": safeties / total_plays if total_plays else 0.0004,
        "total_scrimmage_plays": total_plays,
        "total_safeties": int(safeties),
        "kneel_seconds": 40,
        "inter_drive_clock": inter_drive_median,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN BUILDER
# ═══════════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════════
# TABLE J (5A-6): End-of-half field-goal decision on downs 1-3
# ═══════════════════════════════════════════════════════════════════════════════

EOH_SEC_BINS = [-1, 3, 6, 10, 20, 40]
EOH_SEC_LABELS = ["0-3", "4-6", "7-10", "11-20", "21-40"]
EOH_YL_BINS = [0, 20, 30, 40, 50]
EOH_YL_LABELS = ["<=20", "21-30", "31-40", "41-50"]


def eoh_state(qtr, score_differential):
    """Decision state for an end-of-half snap on downs 1-3.
    fg_useful: Q2 (any score), or Q4 tied / trailing by <= 3.
    Q4_lead: leading in Q4 (real teams kneel; measured P(FG)=0).
    Q4_trail4+: trailing by 4+ in Q4 (need a TD; measured P(FG)~0.02)."""
    qtr = np.asarray(qtr); sd = np.asarray(score_differential, dtype=float)
    return np.where(qtr == 2, "fg_useful",
           np.where((sd >= -3) & (sd <= 0), "fg_useful",
           np.where(sd > 0, "Q4_lead", "Q4_trail4+")))


def build_eoh_fg_table(df):
    """League P(field-goal attempt on downs 1-3 | end of half) by
    (state, seconds-left bucket, yardline bucket), 2021-2024 regular season.

    Population: snaps on downs 1-3, qtr in {2, 4}, half_seconds_remaining <= 40,
    yardline_100 <= 50, play_type in pass/run/field_goal/qb_spike/qb_kneel.
    Level 0: state x sec x yl (min cell 30). Level 1: state x sec, pooled over
    yardline (min cell 30), prefix "all" on yl_b. No cell is invented."""
    MIN_N = 30
    d = df[df["down"].isin([1, 2, 3]) & df["qtr"].isin([2, 4])
           & (df["half_seconds_remaining"] <= 40) & (df["yardline_100"] <= 50)
           & df["play_type"].isin(["pass", "run", "field_goal", "qb_spike", "qb_kneel"])].copy()
    d["fg"] = (d["play_type"] == "field_goal").astype(int)
    d["state"] = eoh_state(d["qtr"], d["score_differential"])
    d["sec_b"] = pd.cut(d["half_seconds_remaining"], EOH_SEC_BINS, labels=EOH_SEC_LABELS).astype(str)
    d["yl_b"] = pd.cut(d["yardline_100"], EOH_YL_BINS, labels=EOH_YL_LABELS).astype(str)
    rows = []
    for (st, sb, yb), g in d.groupby(["state", "sec_b", "yl_b"]):
        if len(g) >= MIN_N:
            rows.append({"state": st, "sec_b": sb, "yl_b": yb, "n": len(g), "p_fg": g["fg"].mean()})
    for (st, sb), g in d.groupby(["state", "sec_b"]):
        if len(g) >= MIN_N:
            rows.append({"state": st, "sec_b": sb, "yl_b": "all", "n": len(g), "p_fg": g["fg"].mean()})
    return pd.DataFrame(rows)

def build_all():
    print("Loading PBP data (2021-2024, regular season)...")
    df = load_pbp()
    print(f"  {len(df):,} plays loaded")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Building pass outcome table (A)...")
    pass_tbl = build_pass_table(df)
    pass_tbl.to_parquet(OUT_DIR / "pass_outcomes.parquet", index=False)
    print(f"  {len(pass_tbl)} rows")

    print("Building rush outcome table (B)...")
    rush_tbl = build_rush_table(df)
    rush_tbl.to_parquet(OUT_DIR / "rush_outcomes.parquet", index=False)
    print(f"  {len(rush_tbl)} rows")

    print("Building play-call table (C)...")
    pc_tbl = build_playcall_table(df)
    pc_tbl.to_parquet(OUT_DIR / "playcall_xpass.parquet", index=False)
    print(f"  {len(pc_tbl)} rows")

    print("Building clock runoff table (D)...")
    clock_tbl = build_clock_table(df)
    clock_tbl.to_parquet(OUT_DIR / "clock_runoff.parquet", index=False)
    print(f"  {len(clock_tbl)} rows")

    print("Building 4th-down decision table (E)...")
    fd_tbl = build_fourth_down_table(df)
    fd_tbl.to_parquet(OUT_DIR / "fourth_down.parquet", index=False)
    print(f"  {len(fd_tbl)} rows")

    print("Building special teams tables (F)...")
    st = build_special_teams_table(df)
    st["fg_make_rate"].to_parquet(OUT_DIR / "fg_make_rate.parquet", index=False)
    st["punt_net"].to_parquet(OUT_DIR / "punt_net.parquet", index=False)
    st["kickoff"].to_parquet(OUT_DIR / "kickoff.parquet", index=False)
    st["twopt_decision"].to_parquet(OUT_DIR / "twopt_decision.parquet", index=False)
    # Save scalar values as JSON
    import json
    scalars = {
        "xp_rate": st["xp_rate"],
        "twopt_conv_rate": st["twopt_conv_rate"],
        "penalty": st["penalty"],
    }
    with open(OUT_DIR / "scalars.json", "w") as f:
        json.dump(scalars, f, indent=2, default=float)
    print(f"  FG: {len(st['fg_make_rate'])} rows, punt: {len(st['punt_net'])} rows")

    print("Building turnover return table (G)...")
    to_tbl = build_turnover_table(df)
    with open(OUT_DIR / "turnover_returns.json", "w") as f:
        json.dump(to_tbl, f, indent=2, default=float)
    print(f"  INT: {to_tbl['int_n']} plays, Fumble: {to_tbl['fum_n']} plays")

    print("Building constants (H)...")
    consts = build_constants(df)
    with open(OUT_DIR / "constants.json", "w") as f:
        json.dump(consts, f, indent=2, default=float)
    print(f"  Safety rate: {consts['p_safety_per_play']:.5f}")

    print("Building end-of-half FG decision table (J, 5A-6)...")
    eoh_tbl = build_eoh_fg_table(df)
    eoh_tbl.to_parquet(OUT_DIR / "eoh_fg_decision.parquet", index=False)
    print(f"  {len(eoh_tbl)} rows")

    print("Building pass depth table (I)...")
    depth_tbl = build_pass_depth_table(df)
    depth_tbl.to_parquet(OUT_DIR / "pass_depth_outcomes.parquet", index=False)
    print(f"  {len(depth_tbl)} rows")

    print("Building league position catch rates...")
    lg_catch = build_lg_pos_catch(df)
    scalars["lg_pos_catch"] = lg_catch
    with open(OUT_DIR / "scalars.json", "w") as f:
        json.dump(scalars, f, indent=2, default=float)
    print(f"  {lg_catch}")

    print("\nAll tables built successfully.")
    return {
        "pass": pass_tbl, "rush": rush_tbl, "playcall": pc_tbl,
        "clock": clock_tbl, "fourth_down": fd_tbl, "special": st,
        "turnover": to_tbl, "constants": consts,
    }


if __name__ == "__main__":
    build_all()
