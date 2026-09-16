#!/usr/bin/env python3
"""
NFL Sim Phase 2A — Empirical league tables from PBP (2021-2024 only).

Builds situation-dependent outcome distributions for the play-level engine.
All tables are league-wide averages (team ratings shift these at runtime via log5).
Writes parquet files to nfl/data/sim/tables/.

SEASONS: 2021-2024 ONLY. Raises if any row with season >= 2025 is present.
Regular season only (week <= 18).
"""

import json
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


# 5A-7: 10-yard zones. Label = upper bound of yardline_100 (y10 = inside the 10).
ZONE10_LABELS = [f"y{k}" for k in range(10, 101, 10)]
ZONE10_TO_ZONE5 = {"y10": "rz10", "y20": "opp20", "y30": "midfield", "y40": "midfield",
                   "y50": "midfield", "y60": "midfield", "y70": "own40", "y80": "own40",
                   "y90": "own20", "y100": "own20"}


def _field_zone10(yl100):
    return pd.cut(yl100, bins=list(range(0, 101, 10)), labels=ZONE10_LABELS, right=True)


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


def build_pass_table(df, zones="z5"):
    """Pass outcome distributions by (down, distance, field_zone).

    zones="z5": rz10/opp20/midfield/own40/own20 (v1). zones="z10": 10-yard zones
    (5A-7) — the engine reads z10 and falls back to the z5 parent for thin cells."""
    passes = df[(df["play_type"] == "pass") & df["down"].notna()].copy()
    passes["down_b"] = passes["down"].astype(int).clip(1, 4).astype(str)
    passes["dist_b"] = _dist_bucket(passes["ydstogo"])
    if zones == "z10":
        passes["zone"] = _field_zone10(passes["yardline_100"])
        ZONE_ORDER = list(reversed(ZONE10_LABELS))        # far -> near the goal line
        BORROW = set(ZONE10_LABELS[:6])                    # y10..y60 borrow from the next zone out
    else:
        passes["zone"] = _field_zone(passes["yardline_100"])
        ZONE_ORDER = ["own20", "own40", "midfield", "opp20", "rz10"]
        BORROW = {"opp20", "rz10"}
    passes = passes.dropna(subset=["down_b", "dist_b", "zone"])

    # 5A-6: open-field reference completions (zones where the goal line ~never binds)
    open_field = passes[(passes["yardline_100"] > 60)
                        & (passes["sack"] != 1) & (passes["interception"] != 1)
                        & (passes["complete_pass"] == 1)]
    def _ref(down, dist, sel):
        g = open_field[(open_field["down_b"] == down) & (open_field["dist_b"] == dist)]
        g = sel(g)
        if len(g) < 50:  # thin: pool across downs for this distance
            g = sel(open_field[open_field["dist_b"] == dist])
        return g["yards_gained"].values.astype(float)

    rows = []
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
        if zone in BORROW and pv is not None:
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

def build_rush_table(df, zones="z5"):
    rushes = df[(df["play_type"] == "run") & df["down"].notna()].copy()
    rushes["down_b"] = rushes["down"].astype(int).clip(1, 4).astype(str)
    rushes["dist_b"] = _dist_bucket(rushes["ydstogo"])
    if zones == "z10":
        rushes["zone"] = _field_zone10(rushes["yardline_100"])
        ZONE_ORDER = list(reversed(ZONE10_LABELS))
        BORROW = set(ZONE10_LABELS[:6])
    else:
        rushes["zone"] = _field_zone(rushes["yardline_100"])
        ZONE_ORDER = ["own20", "own40", "midfield", "opp20", "rz10"]
        BORROW = {"opp20", "rz10"}
    rushes = rushes.dropna(subset=["down_b", "dist_b", "zone"])

    # 5A-6: open-field reference rushes
    open_field = rushes[rushes["yardline_100"] > 60]
    def _ref(down, dist, sel):
        g = open_field[(open_field["down_b"] == down) & (open_field["dist_b"] == dist)]
        g = sel(g)
        if len(g) < 50:
            g = sel(open_field[open_field["dist_b"] == dist])
        return g["yards_gained"].values.astype(float)

    rows = []
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
        if zone in BORROW and pv is not None:
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

    rows.extend(_eoh_runoff_rows(df))
    rows.extend(_fgs_runoff_rows(df))
    return pd.DataFrame(rows)


def _fgs_runoff_rows(df):
    """5A-9 (D33): clock runoff after a scrimmage snap in the FG-setup state (Q4/OT, tied
    or trailing by 1-3, inside the 35, <= 3:00, downs 1-3), keyed by seconds-left bucket
    and outcome type. In this state the offence manages the clock to the kick: a run
    at 0:45 is followed by a timeout at ~0:05, so the elapsed depends on the time left
    (measured: run at 41-120 s median 6 s, q75 38 s; the half expires before the next
    snap on 1-2% of snaps). Same measurement as the EOH cells (next snap of any type in
    the same half, KM with the 99-s sentinel for expiry). Min cell 30; fallbacks pool
    outcome type ("all") then seconds ("all")."""
    d = df.sort_values(["game_id", "play_id"]).copy()
    d["half_id"] = np.where(d["qtr"] <= 2, 1, np.where(d["qtr"] <= 4, 2, 3))
    snaps = d[d["play_type"].isin(["pass", "run", "field_goal", "punt", "qb_kneel", "qb_spike"])].copy()
    snaps["next_sec"] = snaps.groupby(["game_id", "half_id"])["half_seconds_remaining"].shift(-1)
    e = snaps[snaps["play_type"].isin(["pass", "run"])].copy()
    e["state"] = fg_setup_state(e["qtr"], e["score_differential"], e["yardline_100"],
                                e["half_seconds_remaining"], e["down"])
    e = e[e["state"] != ""].copy()
    e["sec_b"] = pd.cut(e["half_seconds_remaining"], FGS_SEC_BINS, labels=FGS_SEC_LABELS).astype(str)
    e["outcome_type"] = np.where(e["play_type"] == "run", "run",
                        np.where((e["complete_pass"] == 1) | (e["sack"] == 1), "complete_inbounds", "incomplete"))
    e.loc[e["first_down"] == 1, "outcome_type"] = "first_down"
    cens = e["next_sec"].isna()
    e["elapsed"] = np.where(cens, e["half_seconds_remaining"], e["half_seconds_remaining"] - e["next_sec"])
    e = e[e["elapsed"] >= 0]
    rows = []
    def _row(g, sb, ot):
        c = g["next_sec"].isna().to_numpy()
        if sb in ("0-20", "21-40"):
            # <= 40 s: the offence manages to the kick, so the stable quantity is the time
            # left at the NEXT snap (kind = next_sec; the half expiring = 0), not the elapsed
            ns = g["next_sec"].fillna(0.0).to_numpy(dtype=float)
            return {"outcome_type": ot, "score_state": f"fgs_{sb}", "clock_period": "fgs", "hurry": False,
                    "n": len(g), "elapsed_q": np.quantile(ns, QUANTILE_POINTS).tolist(),
                    "mean": float(ns.mean()), "n_censored": int(c.sum()), "kind": "next_sec"}
        q = _km_quantiles(g["elapsed"].to_numpy(), g["elapsed"].to_numpy(), c)
        return {"outcome_type": ot, "score_state": f"fgs_{sb}", "clock_period": "fgs", "hurry": False,
                "n": len(g), "elapsed_q": q.tolist(), "mean": float(g.loc[~c, "elapsed"].mean()),
                "n_censored": int(c.sum()), "kind": "elapsed"}
    for (sb, ot), g in e.groupby(["sec_b", "outcome_type"]):
        if len(g) >= EOH_RUNOFF_MIN:
            rows.append(_row(g, sb, ot))
    for sb, g in e.groupby("sec_b"):
        if len(g) >= EOH_RUNOFF_MIN:
            rows.append(_row(g, sb, "all"))
    for ot, g in e.groupby("outcome_type"):
        if len(g) >= EOH_RUNOFF_MIN:
            rows.append(_row(g, "all", ot))
    rows.append(_row(e, "all", "all"))
    # Kneels in the state: the offence kneels TO THE KICK. Measured (every in-state kneel
    # 2021-2024): with <= 40 s left the next snap is the field goal with 1-4 s on the
    # clock; with more time the next snap comes ~35-40 s later (running clock) or at
    # once if the defence calls timeout. Two rows: the <= 40 s row stores quantiles of
    # the SECONDS LEFT AT THE NEXT SNAP (kind = "next_sec"); the > 40 s row stores
    # elapsed like every other cell. Cells this small are kept because the behaviour is
    # deterministic (22 of 22 and 23 of 23 cases), and reported with their n.
    k = snaps[snaps["play_type"] == "qb_kneel"].copy()
    k["state"] = fg_setup_state(k["qtr"], k["score_differential"], k["yardline_100"],
                                k["half_seconds_remaining"], k["down"])
    k = k[k["state"] != ""]
    k_lo = k[k["half_seconds_remaining"] <= 40]; k_hi = k[k["half_seconds_remaining"] > 40]
    if len(k_lo):
        ns = k_lo["next_sec"].fillna(0.0).to_numpy(dtype=float)
        rows.append({"outcome_type": "kneel", "score_state": "fgs_0-40", "clock_period": "fgs", "hurry": False,
                     "n": len(k_lo), "elapsed_q": np.quantile(ns, QUANTILE_POINTS).tolist(),
                     "mean": float(ns.mean()), "n_censored": int(k_lo["next_sec"].isna().sum()),
                     "kind": "next_sec"})
    if len(k_hi):
        c = k_hi["next_sec"].isna().to_numpy()
        el = np.where(c, k_hi["half_seconds_remaining"], k_hi["half_seconds_remaining"] - k_hi["next_sec"]).astype(float)
        rows.append({"outcome_type": "kneel", "score_state": "fgs_41-180", "clock_period": "fgs", "hurry": False,
                     "n": len(k_hi), "elapsed_q": _km_quantiles(el, el, c).tolist(),
                     "mean": float(el[~c].mean()), "n_censored": int(c.sum()), "kind": "elapsed"})
    return rows


EOH_RUNOFF_MIN = 30


def _eoh_runoff_rows(df):
    """5A-9 (D31): clock runoff after a scrimmage snap taken in the end-of-half
    field-goal setup — qtr 2 / 4 / OT, <= 40 s left in the half, ball inside the 50,
    keyed by the EOH decision state (fg_useful / Q4_lead / Q4_trail4+, `eoh_state`)
    and the play's outcome type. 5A-8 found the sim drew these snaps from the pooled
    Q4_late cell (mean 20-35 s) while real teams spike, kneel to centre or call
    timeout (median 5 s after a pass), so 14% of tied late drives expired inside the
    35 without a kick. Elapsed is measured to the NEXT SNAP OF ANY TYPE in the same
    half (pass/run/FG/punt/kneel/spike) and is right-censored when the half ends
    first: Kaplan-Meier with the plateau at the 99-second sentinel, which the engine
    reads as "the clock runs out". Elapsed 0 is kept (a timeout called at the whistle).
    Min cell 30; fallback rows pool outcome types ("all") and then states ("eoh_all")."""
    d = df.sort_values(["game_id", "play_id"]).copy()
    d["half_id"] = np.where(d["qtr"] <= 2, 1, np.where(d["qtr"] <= 4, 2, 3))
    snaps = d[d["play_type"].isin(["pass", "run", "field_goal", "punt", "qb_kneel", "qb_spike"])].copy()
    snaps["next_sec"] = snaps.groupby(["game_id", "half_id"])["half_seconds_remaining"].shift(-1)
    e = snaps[snaps["play_type"].isin(["pass", "run"]) & snaps["qtr"].isin([2, 4, 5, 6])
              & (snaps["half_seconds_remaining"] <= 40) & (snaps["yardline_100"] <= 50)].copy()
    e["state"] = eoh_state(e["qtr"], e["score_differential"])
    # Q2 hurry-up (score before the half) and Q4/OT (kneel it down, deny the opponent
    # time) are different behaviours in the same decision state: keep them apart
    e["state"] = np.where(e["state"] == "fg_useful",
                          np.where(e["qtr"] == 2, "fg_useful_Q2", "fg_useful_Q4"), e["state"])
    e["outcome_type"] = np.where(e["play_type"] == "run", "run",
                        np.where((e["complete_pass"] == 1) | (e["sack"] == 1), "complete_inbounds", "incomplete"))
    e.loc[e["first_down"] == 1, "outcome_type"] = "first_down"
    cens = e["next_sec"].isna()
    e["elapsed"] = np.where(cens, e["half_seconds_remaining"], e["half_seconds_remaining"] - e["next_sec"])
    e = e[e["elapsed"] >= 0]
    cens = e["next_sec"].isna()
    rows = []
    def _row(g, st, ot):
        c = g["next_sec"].isna().to_numpy()
        q = _km_quantiles(g["elapsed"].to_numpy(), g["elapsed"].to_numpy(), c)
        return {"outcome_type": ot, "score_state": st, "clock_period": "eoh", "hurry": False,
                "n": len(g), "elapsed_q": q.tolist(), "mean": float(g.loc[~c, "elapsed"].mean()),
                "n_censored": int(c.sum())}
    for (st, ot), g in e.groupby(["state", "outcome_type"]):
        if len(g) >= EOH_RUNOFF_MIN:
            rows.append(_row(g, f"eoh_{st}", ot))
    for st, g in e.groupby("state"):
        if len(g) >= EOH_RUNOFF_MIN:
            rows.append(_row(g, f"eoh_{st}", "all"))
    rows.append(_row(e, "eoh_all", "all"))
    return rows


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

FD_YD_LABELS = ["1-2", "3-5", "6-10", "11+"]
FD_YL_LABELS = ["opp1-10", "opp11-20", "opp21-30", "opp31-40", "opp41-50",
                "own41-50", "own31-40", "own21-30", "own11-20", "own1-10"]
FD_SC_LABELS = ["trail9+", "trail4-8", "trail1-3", "tied", "lead1-3", "lead4-8", "lead9+"]
FD_CK_LABELS = ["Q1-3", "Q2<2", "Q4>5", "Q4_2-5", "Q4<2", "OT"]
FD_YL_COARSE = {"opp1-10": "rz", "opp11-20": "opp40", "opp21-30": "opp40", "opp31-40": "opp40",
                "opp41-50": "midfield", "own41-50": "midfield", "own31-40": "midfield",
                "own21-30": "own35", "own11-20": "own35", "own1-10": "own35"}
FD_CK_COARSE = {"Q1-3": "Q1-3", "Q2<2": "Q2<2", "Q4>5": "Q4>5", "Q4_2-5": "Q4late", "Q4<2": "Q4late", "OT": "Q4late"}


def fd_score_coarse(sc7, yl4):
    """Coarse score grouping for the shrinkage parent, by what the decision turns on:
    inside the opponent's 40 (rz / opp40) it is whether three points help —
    need_td (trail 4+) / fg_useful (trail 1-3, tied) / lead; outside it is whether the
    offence can afford to give the ball back — trail / tied / lead (sign only).
    Structural, not fitted: the 5A-9 check showed sign-only pooling makes a team down 3
    in range go instead of kick, and FG-usefulness pooling makes a team down 3 in its
    own end punt like a tied team."""
    sc7 = np.asarray(sc7, dtype=object); yl4 = np.asarray(yl4, dtype=object)
    in_range = np.isin(yl4, ["rz", "opp40"])
    trail = np.isin(sc7, ["trail9+", "trail4-8", "trail1-3"])
    need_td = np.isin(sc7, ["trail9+", "trail4-8"])
    fg_useful = np.isin(sc7, ["trail1-3", "tied"])
    lead = np.isin(sc7, ["lead1-3", "lead4-8", "lead9+"])
    out = np.where(in_range, np.where(need_td, "need_td", np.where(fg_useful, "fg_useful", "lead")),
                   np.where(trail, "trail", np.where(lead, "lead", "tied")))
    return out.astype(object)


def fourth_down_keys(ydstogo, yardline_100, score_diff, qtr, sec_left_in_qtr):
    """5A-9 (D30): the ONE bucketing used by both the table builder and the engine.
    Returns (ydstogo_b, yl_b, score_b, clock_b) as object arrays. Clock: Q1-3, Q2<2
    (last 2:00 of the half), Q4>5, Q4_2-5, Q4<2, OT (any overtime period)."""
    yd = np.asarray(ydstogo, dtype=float); y = np.asarray(yardline_100, dtype=float)
    sd = np.asarray(score_diff, dtype=float); q = np.asarray(qtr, dtype=float)
    cl = np.asarray(sec_left_in_qtr, dtype=float)
    yd_b = np.where(yd <= 2, "1-2", np.where(yd <= 5, "3-5", np.where(yd <= 10, "6-10", "11+")))
    zi = np.clip(np.ceil(y / 10.0) - 1, 0, 9).astype(int)
    yl_b = np.asarray(FD_YL_LABELS, dtype=object)[zi]
    sc_b = np.where(sd < -8, "trail9+", np.where(sd < -3, "trail4-8", np.where(sd < 0, "trail1-3",
           np.where(sd == 0, "tied", np.where(sd <= 3, "lead1-3", np.where(sd <= 8, "lead4-8", "lead9+"))))))
    ck_b = np.where(q >= 5, "OT",
           np.where((q == 2) & (cl <= 120), "Q2<2",
           np.where(q <= 3, "Q1-3",
           np.where(cl > 300, "Q4>5", np.where(cl > 120, "Q4_2-5", "Q4<2")))))
    return yd_b.astype(object), yl_b.astype(object), sc_b.astype(object), ck_b.astype(object)


def _mom_k(child_n, child_x, parent_p):
    """Method-of-moments Beta-binomial concentration for a set of child cells around
    their (raw) parent proportions, on a binary indicator. tau^2 = between-cell variance
    of the true proportion beyond binomial noise; k = p(1-p)/tau^2 - 1. Returns inf when
    the children are consistent with pure binomial scatter (no extra information)."""
    n = np.asarray(child_n, dtype=float); x = np.asarray(child_x, dtype=float)
    pp = np.asarray(parent_p, dtype=float)
    m = n > 0
    n, x, pp = n[m], x[m], pp[m]
    if len(n) < 2:
        return np.inf
    p_i = x / n
    Q = np.sum(n * (p_i - pp) ** 2)
    binom = np.sum(pp * (1 - pp) * (1 - n / n.sum()))  # E[Q] under no between-cell variance
    denom = n.sum() - np.sum(n ** 2) / n.sum()
    tau2 = (Q - binom) / denom if denom > 0 else 0.0
    if tau2 <= 0:
        return np.inf
    pbar = x.sum() / n.sum()
    return max(pbar * (1 - pbar) / tau2 - 1.0, 0.0)


def build_fourth_down_table(df):
    """League P(go / punt / FG) on 4th down, 2021-2024 regular season.

    5A-9 (D30): hierarchical Dirichlet shrinkage on a COMPLETE fine grid instead of a
    min-cell fallback chain. Fine key = ydstogo (4) x 10-yard field zone (10) x score
    state (7) x clock (6: Q1-3, Q2<2, Q4>5, Q4_2-5, Q4<2, OT) = 1,680 rows, every one
    present, so the engine does one exact lookup and can never fall through to a
    hand-written default. Each cell's probabilities are its own counts blended with
    its parent's estimate, p = (x + k * p_parent) / (n + k), with k measured per level
    by method of moments on the go indicator (no chosen number). Parent chain, coarsest
    dimension first and NEVER pooling across the sign of the score until level 3:
      L0 (yd, zone10, score7, clock6)
      L1 (yd, zone4,  score7, clock6)      field position coarsened
      L2 (yd, zone4,  score7, clock4)      clock: Q1-3 / Q2<2 / Q4>5 / Q4late(=Q4_2-5, Q4<2, OT)
      L3 (yd, zone4,  score3, clock3)      score: need_td / fg_useful / lead in range,
                                            trail / tied / lead outside (fd_score_coarse)
      L4 (yd, zone4,  score3)              all clock
      L5 (yd, zone4)                       L6 (yd)                 L7 league
    The 5A-8 finding: the old chain's levels 2-3 were unreachable (key mismatch) and
    51.7% of Q4 / 99.1% of OT decisions used a cell that pooled trailing with leading."""
    d = df[(df["down"] == 4) & df["down"].notna()].copy()
    d = d[d["play_type"].isin(["pass", "run", "punt", "field_goal"])].copy()
    yd_b, yl_b, sc_b, ck_b = fourth_down_keys(d["ydstogo"], d["yardline_100"], d["score_differential"],
                                              d["qtr"], d["quarter_seconds_remaining"])
    d["yd"] = yd_b; d["yl10"] = yl_b; d["sc7"] = sc_b; d["ck6"] = ck_b
    d["yl4"] = d["yl10"].map(FD_YL_COARSE); d["sc3"] = fd_score_coarse(d["sc7"], d["yl4"]); d["ck3"] = d["ck6"].map(FD_CK_COARSE)
    d["go"] = (d["play_type"].isin(["pass", "run"])).astype(int)
    d["punt"] = (d["play_type"] == "punt").astype(int)
    d["fg"] = (d["play_type"] == "field_goal").astype(int)

    levels = [["yd", "yl10", "sc7", "ck6"], ["yd", "yl4", "sc7", "ck6"], ["yd", "yl4", "sc7", "ck3"],
              ["yd", "yl4", "sc3", "ck3"], ["yd", "yl4", "sc3"], ["yd", "yl4"], ["yd"], []]

    # complete fine grid with its own counts
    grid = pd.MultiIndex.from_product([FD_YD_LABELS, FD_YL_LABELS, FD_SC_LABELS, FD_CK_LABELS],
                                      names=["yd", "yl10", "sc7", "ck6"]).to_frame(index=False)
    grid["yl4"] = grid["yl10"].map(FD_YL_COARSE); grid["sc3"] = fd_score_coarse(grid["sc7"], grid["yl4"])
    grid["ck3"] = grid["ck6"].map(FD_CK_COARSE)
    fine = d.groupby(["yd", "yl10", "sc7", "ck6"], observed=True)[["go", "punt", "fg"]].sum().reset_index()
    grid = grid.merge(fine, on=["yd", "yl10", "sc7", "ck6"], how="left").fillna({"go": 0, "punt": 0, "fg": 0})
    grid["n"] = grid["go"] + grid["punt"] + grid["fg"]
    grid["_all"] = 0

    def _lvl_cols(L):
        return levels[L] if levels[L] else ["_all"]

    # level sums per grid row (rows sharing a level key get the same sums)
    for L in range(8):
        g = grid.groupby(_lvl_cols(L), observed=True)[["go", "punt", "fg", "n"]].transform("sum")
        for c in ("go", "punt", "fg", "n"):
            grid[f"{c}_{L}"] = g[c]

    # top-down shrinkage: est at level 7 is the league proportion
    k_by_level = {}
    for c in ("go", "punt", "fg"):
        grid[f"p{c}_7"] = grid[f"{c}_7"] / grid["n_7"]
    for L in range(6, -1, -1):
        # k from the distinct child cells at level L around raw parent proportions;
        # one k per coarse score group while the score is still in the key (levels 0-3),
        # because the clock and field dimensions carry far more information for a
        # trailing offence than for a leading one
        cells = grid.drop_duplicates(_lvl_cols(L))
        cells = cells[cells[f"n_{L}"] > 0]
        groups = cells["sc3"].unique() if L <= 3 else ["all"]
        k_by_level[L] = {}
        grid[f"k_{L}"] = np.nan
        for gname in groups:
            cg = cells if gname == "all" else cells[cells["sc3"] == gname]
            k = _mom_k(cg[f"n_{L}"], cg[f"go_{L}"], cg[f"go_{L+1}"] / cg[f"n_{L+1}"])
            k_by_level[L][str(gname)] = float(k)
            rowsel = slice(None) if gname == "all" else (grid["sc3"] == gname)
            grid.loc[rowsel, f"k_{L}"] = k
        kcol = grid[f"k_{L}"].to_numpy(dtype=float)
        for c in ("go", "punt", "fg"):
            shr = (grid[f"{c}_{L}"] + kcol * grid[f"p{c}_{L+1}"]) / (grid[f"n_{L}"] + kcol)
            grid[f"p{c}_{L}"] = np.where(np.isinf(kcol), grid[f"p{c}_{L+1}"], shr)

    tbl = pd.DataFrame({"ydstogo_b": grid["yd"], "yl_b": grid["yl10"], "score_b": grid["sc7"],
                        "qtr_b": grid["ck6"], "n": grid["n"].astype(int),
                        "p_go": grid["pgo_0"], "p_punt": grid["ppunt_0"], "p_fg": grid["pfg_0"]})
    # rows are complete by construction; probabilities sum to 1 up to float error
    assert len(tbl) == 4 * 10 * 7 * 6 and np.allclose(tbl[["p_go", "p_punt", "p_fg"]].sum(axis=1), 1.0)
    tbl.attrs["k_by_level"] = k_by_level
    return tbl


# ═══════════════════════════════════════════════════════════════════════════════
# TABLE F: FG, punt, kickoff, XP, 2pt, penalties
# ═══════════════════════════════════════════════════════════════════════════════

TWOPT_BUCKETS = [(-100, -15, "trail15+"), (-15, -9, "trail9-15"), (-9, -1, "trail1-8"), (-1, 2, "tied_lead1"),
                 (2, 9, "lead2-8"), (9, 16, "lead9-15"), (16, 100, "lead15+")]


def twopt_bucket(sd):
    sd = np.asarray(sd, dtype=float)
    out = np.full(sd.shape, "", dtype=object)
    for lo, hi, lab in TWOPT_BUCKETS:
        out[(sd >= lo) & (sd < hi)] = lab
    return out


def build_twopt_table(pat_plays, twopt_plays):
    """See build_special_teams_table. Rows: period ('Q1-3' / 'Q4+') x sd_post (-16..16,
    values beyond pooled into the end cells) -> p_2pt, n (own), with k_by_level attrs."""
    x = pd.concat([pat_plays.assign(two=0), twopt_plays.assign(two=1)], ignore_index=True)
    x = x[x["score_differential"].notna()].copy()
    x["period"] = np.where(x["qtr"] >= 4, "Q4+", "Q1-3")
    x["sd"] = x["score_differential"].clip(-16, 16).astype(int)
    x["bkt"] = twopt_bucket(x["score_differential"])
    grid = pd.MultiIndex.from_product([["Q1-3", "Q4+"], list(range(-16, 17))], names=["period", "sd"]).to_frame(index=False)
    grid["bkt"] = twopt_bucket(grid["sd"])
    fine = x.groupby(["period", "sd"])["two"].agg(["sum", "size"]).reset_index().rename(columns={"sum": "x", "size": "n"})
    grid = grid.merge(fine, on=["period", "sd"], how="left").fillna({"x": 0, "n": 0})
    levels = [["period", "sd"], ["period", "bkt"], ["period"], []]
    for L, cols in enumerate(levels):
        if cols:
            g = grid.groupby(cols)[["x", "n"]].transform("sum")
        else:
            g = pd.DataFrame({"x": grid["x"].sum(), "n": grid["n"].sum()}, index=grid.index)
        grid[f"x_{L}"] = g["x"]; grid[f"n_{L}"] = g["n"]
    k_by_level = {}
    grid["p_3"] = grid["x_3"] / grid["n_3"]
    for L in (2, 1, 0):
        cells = grid.drop_duplicates(levels[L]); cells = cells[cells[f"n_{L}"] > 0]
        k = _mom_k(cells[f"n_{L}"], cells[f"x_{L}"], cells[f"x_{L+1}"] / cells[f"n_{L+1}"])
        k_by_level[L] = float(k)
        grid[f"p_{L}"] = np.where(np.isinf(k), grid[f"p_{L+1}"], (grid[f"x_{L}"] + k * grid[f"p_{L+1}"]) / (grid[f"n_{L}"] + k))
    out = pd.DataFrame({"period": grid["period"], "sd_post": grid["sd"], "n": grid["n"].astype(int), "p_2pt": grid["p_0"]})
    out.attrs["k_by_level"] = k_by_level
    return out


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

    # 5A-10 (D35): 2-pt decision by EXACT post-TD score differential x period (Q1-3 / Q4+).
    # The decision is nearly deterministic at specific numbers (down 2 -> 100%, down 5 ->
    # 100%, up 1 -> 100%, down 10 -> 100%, down 3 -> 0%, down 7 -> 0%) and the old 7-bucket
    # table smeared them (trail1-8 in Q4 = 34% everywhere), putting margins on 1/2/4 instead
    # of 3/7. Complete grid -16..+16 (pooled beyond) x 2 periods, each cell shrunk toward
    # its period x 7-bucket parent, then the period, with k by method of moments.
    result["twopt_decision"] = build_twopt_table(pat_plays, twopt_plays)

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

    # 5A-7: per-play safety rates by own-goal-line bucket, RAW (the 5A-4 engine carried
    # these as hand-typed numbers scaled by 1/1.84 "because the sim generated too many
    # deep plays"; deep-play counts now match reality, so the measured rates are used).
    saf_by_zone = {}
    for key, lo, hi in (("98-100", 98, 100), ("95-97", 95, 97), ("90-94", 90, 94)):
        g = scrim[(scrim["yardline_100"] >= lo) & (scrim["yardline_100"] <= hi)]
        saf_by_zone[key] = {"n": int(len(g)),
                            "p": float(g["safety"].sum() / len(g)) if len(g) else 0.0}

    return {
        "p_safety_per_play": safeties / total_plays if total_plays else 0.0004,
        "total_scrimmage_plays": total_plays,
        "total_safeties": int(safeties),
        "inter_drive_clock": inter_drive_median,
        "safety_rate_by_zone": saf_by_zone,
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
    fg_useful: Q2 (any score), or Q4/OT tied / trailing by <= 3 (5A-9: OT included).
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
    d = df[df["down"].isin([1, 2, 3]) & df["qtr"].isin([2, 4, 5, 6])
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


def build_eoh_spike_table(df):
    """5A-9 (D34): P(spike | end-of-half snap on downs 1-3 in the fg_useful state) by half
    (Q2 / Q4-OT) and seconds-left bucket. The sim had no spike: at 4-10 s left in range a
    real Q4 offence spikes 29-37% of the time (Q2: 5-20%) and kicks on the next snap; the
    engine ran a play instead and the half expired. A spike takes 1 s (measured q90 = 1)
    and a down. Same population as the EOH FG table; min cell 30, pooled over yardline."""
    MIN_N = 30
    d = df[df["down"].isin([1, 2, 3]) & df["qtr"].isin([2, 4, 5, 6])
           & (df["half_seconds_remaining"] <= 40) & (df["yardline_100"] <= 50)
           & df["play_type"].isin(["pass", "run", "field_goal", "qb_spike", "qb_kneel"])].copy()
    d["state"] = eoh_state(d["qtr"], d["score_differential"])
    d = d[d["state"] == "fg_useful"].copy()
    d["half"] = np.where(d["qtr"] == 2, "Q2", "Q4")
    d["sec_b"] = pd.cut(d["half_seconds_remaining"], EOH_SEC_BINS, labels=EOH_SEC_LABELS).astype(str)
    d["spike"] = (d["play_type"] == "qb_spike").astype(int)
    rows = []
    for (h, sb), g in d.groupby(["half", "sec_b"]):
        if len(g) >= MIN_N:
            rows.append({"half": h, "sec_b": sb, "n": len(g), "p_spike": g["spike"].mean()})
    for sb, g in d.groupby("sec_b"):
        rows.append({"half": "all", "sec_b": sb, "n": len(g), "p_spike": g["spike"].mean()})
    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# TABLES K/L (5A-7): timeout policy and kneel decision at the end of halves
# ═══════════════════════════════════════════════════════════════════════════════

TO_SEC_BINS = [-1, 30, 60, 120, 180]
TO_SEC_LABELS = ["0-30", "31-60", "61-120", "121-180"]
KNEEL_SEC_BINS = [-1, 40, 80, 120, 180]
KNEEL_SEC_LABELS = ["0-40", "41-80", "81-120", "121-180"]


def _late_frame(df):
    """Scrimmage snaps in the last 3:00 of Q2/Q4 with the next-event timeout flags."""
    d = df.sort_values(["game_id", "play_id"]).copy()
    d["next_timeout"] = d.groupby("game_id")["timeout"].shift(-1)
    d["next_to_team"] = d.groupby("game_id")["timeout_team"].shift(-1)
    sc = d[d["play_type"].isin(["pass", "run", "qb_kneel", "qb_spike"])].copy()
    running = ((sc["play_type"] == "run") | ((sc["play_type"] == "pass") & (sc["complete_pass"] == 1)))
    running = running & (sc["out_of_bounds"] != 1)
    running = running | (sc["sack"] == 1)
    sc["clock_running"] = running
    sc["to_by_off"] = (sc["next_timeout"] == 1) & (sc["next_to_team"] == sc["posteam"])
    sc["to_by_def"] = (sc["next_timeout"] == 1) & (sc["next_to_team"] == sc["defteam"])
    sc["off_state"] = np.where(sc["score_differential"] < 0, "trail",
                      np.where(sc["score_differential"] == 0, "tied", "lead"))
    return sc[(sc["half_seconds_remaining"] <= 180) & sc["qtr"].isin([2, 4])].copy()


def build_timeout_policy(df):
    """P(timeout called after a snap) by side, keyed (qtr, seconds-left bucket,
    offense score state, clock running after the play). Measured only where the
    calling side still has a timeout. Min cell 80; fallback rows pool clock_running
    (key 'any'), then off_state ('all'). 2021-2024 regular season."""
    MIN_N = 80
    late = _late_frame(df)
    late["sec_b"] = pd.cut(late["half_seconds_remaining"], TO_SEC_BINS, labels=TO_SEC_LABELS).astype(str)
    rows = []
    for side, col, rem in (("off", "to_by_off", "posteam_timeouts_remaining"),
                           ("def", "to_by_def", "defteam_timeouts_remaining")):
        d = late[late[rem] > 0]
        for (q, sb, st, cr), g in d.groupby(["qtr", "sec_b", "off_state", "clock_running"]):
            if len(g) >= MIN_N:
                rows.append({"side": side, "qtr": int(q), "sec_b": sb, "off_state": st,
                             "clock_running": str(bool(cr)), "n": len(g), "p_to": g[col].mean()})
        for (q, sb, st), g in d.groupby(["qtr", "sec_b", "off_state"]):
            if len(g) >= MIN_N:
                rows.append({"side": side, "qtr": int(q), "sec_b": sb, "off_state": st,
                             "clock_running": "any", "n": len(g), "p_to": g[col].mean()})
        for (q, sb), g in d.groupby(["qtr", "sec_b"]):
            if len(g) >= MIN_N:
                rows.append({"side": side, "qtr": int(q), "sec_b": sb, "off_state": "all",
                             "clock_running": "any", "n": len(g), "p_to": g[col].mean()})
    return pd.DataFrame(rows)


def build_kneel_table(df):
    """P(kneel | snap on downs 1-3 in the last 3:00 of Q2/Q4) keyed (qtr, seconds
    bucket, defence timeouts remaining, down, situation). Situation: Q4 -> 'lead'
    (score_differential > 0; trailing/tied teams do not kneel); Q2 -> 'own' (yl >= 60)
    or 'opp'. Min cell 30; fallback rows pool down ('any'), then timeouts ('any')."""
    MIN_N = 30
    late = _late_frame(df)
    late = late[late["down"].isin([1, 2, 3])].copy()
    late["kneel"] = (late["play_type"] == "qb_kneel").astype(int)
    late["sec_b"] = pd.cut(late["half_seconds_remaining"], KNEEL_SEC_BINS, labels=KNEEL_SEC_LABELS).astype(str)
    late["def_to"] = late["defteam_timeouts_remaining"].clip(0, 3).astype(int).astype(str)
    late["situation"] = np.where(late["qtr"] == 4,
                                 np.where(late["score_differential"] > 0, "lead", "not_lead"),
                                 np.where(late["yardline_100"] >= 60, "own", "opp"))
    late = late[late["situation"] != "not_lead"]
    late["down_s"] = late["down"].astype(int).astype(str)
    rows = []
    for (q, sb, dt, dn, sit), g in late.groupby(["qtr", "sec_b", "def_to", "down_s", "situation"]):
        if len(g) >= MIN_N:
            rows.append({"qtr": int(q), "sec_b": sb, "def_to": dt, "down": dn, "situation": sit,
                         "n": len(g), "p_kneel": g["kneel"].mean()})
    for (q, sb, dt, sit), g in late.groupby(["qtr", "sec_b", "def_to", "situation"]):
        if len(g) >= MIN_N:
            rows.append({"qtr": int(q), "sec_b": sb, "def_to": dt, "down": "any", "situation": sit,
                         "n": len(g), "p_kneel": g["kneel"].mean()})
    for (q, sb, sit), g in late.groupby(["qtr", "sec_b", "situation"]):
        if len(g) >= MIN_N:
            rows.append({"qtr": int(q), "sec_b": sb, "def_to": "any", "down": "any", "situation": sit,
                         "n": len(g), "p_kneel": g["kneel"].mean()})
    return pd.DataFrame(rows)

FGS_SEC_BINS = [-1, 20, 40, 60, 90, 120, 180]
FGS_SEC_LABELS = ["0-20", "21-40", "41-60", "61-90", "91-120", "121-180"]
FGS_MIN_N = 20


def fg_setup_state(qtr, score_differential, yardline_100, sec_left_in_half, down):
    """5A-9 (D33): the field-goal-setup state — Q4 or OT, offence tied or trailing by
    1-3, ball inside the 35, <= 3:00 left, downs 1-3. Real offences here kneel to
    centre the ball (45-56% of snaps at 21-60 s when the defence is out of timeouts),
    run 62-78% of the time, and score a TD on 9% of snaps; the general tied/Q4<2
    play-call cell passes 69% of the time. Returns 'tied' / 'trail1-3' / '' (not in state)."""
    q = np.asarray(qtr, dtype=float); sd = np.asarray(score_differential, dtype=float)
    y = np.asarray(yardline_100, dtype=float); sec = np.asarray(sec_left_in_half, dtype=float)
    dn = np.asarray(down, dtype=float)
    m = (q >= 4) & (sd >= -3) & (sd <= 0) & (y <= 35) & (sec <= 180) & (dn >= 1) & (dn <= 3)
    return np.where(m, np.where(sd == 0, "tied", "trail1-3"), "").astype(object)


def build_fg_setup_rush(df):
    """5A-9 (D33): yardage quantiles for RUNS in the FG-setup state (Kaplan-Meier,
    censored at the goal line like every other yardage cell). Measured: mean 2.5-2.9
    yards and a 4-7% TD rate vs 3.7 yards / 10% for the same field position earlier in
    the game — the offence is protecting the kick, not attacking. One cell (n ~320),
    all downs and distances pooled; the pass game in this state is not overridden."""
    r = df[(df["play_type"] == "run")].copy()
    r["state"] = fg_setup_state(r["qtr"], r["score_differential"], r["yardline_100"],
                                r["half_seconds_remaining"], r["down"])
    r = r[r["state"] != ""]
    y = r["yards_gained"].to_numpy(dtype=float); yl = r["yardline_100"].to_numpy(dtype=float)
    cens = (r["touchdown"] == 1).to_numpy()
    q = _km_quantiles(y, yl, cens)
    return pd.DataFrame([{"state": "any", "n": len(r), "n_censored": int(cens.sum()),
                          "yds_q": q.tolist(), "mean_uncensored": float(y[~cens].mean())}])


def build_fg_setup_table(df):
    """P(kneel) and P(pass | not kneel) in the FG-setup state, keyed (state, seconds
    bucket, defence timeouts remaining 0/1/2+, down). Population: pass / run /
    qb_kneel / qb_spike snaps (a spike counts as a pass; the FG decision itself belongs
    to the EOH and 4th-down tables). Min cell 20; fallback rows pool down ('any'),
    then timeouts ('any'), then state ('any'); plus (state 'any', seconds, timeouts)
    rows because the kneel decision turns on the defence's timeouts and the play call on
    the score state. Engine lookup: kneel (any, sec, def_to) -> (any, any, def_to) ->
    all; pass (state, sec) -> (any, sec) -> all. 2021-2024 regular season."""
    d = df[df["play_type"].isin(["pass", "run", "qb_kneel", "qb_spike"])].copy()
    d["state"] = fg_setup_state(d["qtr"], d["score_differential"], d["yardline_100"],
                                d["half_seconds_remaining"], d["down"])
    d = d[d["state"] != ""].copy()
    d["sec_b"] = pd.cut(d["half_seconds_remaining"], FGS_SEC_BINS, labels=FGS_SEC_LABELS).astype(str)
    d["def_to"] = np.where(d["defteam_timeouts_remaining"] >= 2, "2+",
                           d["defteam_timeouts_remaining"].fillna(0).astype(int).astype(str))
    d["down_s"] = d["down"].astype(int).astype(str)
    d["kneel"] = (d["play_type"] == "qb_kneel").astype(int)
    d["is_pass"] = d["play_type"].isin(["pass", "qb_spike"]).astype(int)
    rows = []
    def _emit(g, st, sb, dt, dn):
        nk = g[g["kneel"] == 0]
        rows.append({"state": st, "sec_b": sb, "def_to": dt, "down": dn, "n": len(g),
                     "p_kneel": g["kneel"].mean(),
                     "pass_rate": nk["is_pass"].mean() if len(nk) else np.nan})
    for (st, sb, dt, dn), g in d.groupby(["state", "sec_b", "def_to", "down_s"]):
        if len(g) >= FGS_MIN_N:
            _emit(g, st, sb, dt, dn)
    for (st, sb, dt), g in d.groupby(["state", "sec_b", "def_to"]):
        if len(g) >= FGS_MIN_N:
            _emit(g, st, sb, dt, "any")
    for (st, sb), g in d.groupby(["state", "sec_b"]):
        if len(g) >= FGS_MIN_N:
            _emit(g, st, sb, "any", "any")
    for (sb, dt), g in d.groupby(["sec_b", "def_to"]):
        if len(g) >= FGS_MIN_N:
            _emit(g, "any", sb, dt, "any")
    for sb, g in d.groupby("sec_b"):
        if len(g) >= FGS_MIN_N:
            _emit(g, "any", sb, "any", "any")
    for (dt,), g in d.groupby(["def_to"]):
        _emit(g, "any", "any", dt, "any")
    _emit(d, "any", "any", "any", "any")
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

    print("Building 10-yard-zone outcome tables (A10/B10, 5A-7)...")
    pass10 = build_pass_table(df, zones="z10")
    pass10.to_parquet(OUT_DIR / "pass_outcomes_z10.parquet", index=False)
    rush10 = build_rush_table(df, zones="z10")
    rush10.to_parquet(OUT_DIR / "rush_outcomes_z10.parquet", index=False)
    print(f"  pass z10 {len(pass10)} rows, rush z10 {len(rush10)} rows")

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
    with open(OUT_DIR / "fourth_down_meta.json", "w") as f:
        json.dump({"k_by_level": fd_tbl.attrs["k_by_level"],
                   "levels": ["yd x zone10 x score7 x clock6", "yd x zone4 x score7 x clock6",
                              "yd x zone4 x score7 x clock4", "yd x zone4 x score3(fd_score_coarse) x clock4",
                              "yd x zone4 x score3", "yd x zone4", "yd", "league"],
                   "method": "Dirichlet shrinkage toward parent, k by method of moments on the go indicator (5A-9, D30)"},
                  f, indent=2, default=float)
    print(f"  {len(fd_tbl)} rows (complete grid); k_by_level {fd_tbl.attrs['k_by_level']}")

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

    print("Building timeout policy and kneel tables (K/L, 5A-7)...")
    to_tbl2 = build_timeout_policy(df)
    to_tbl2.to_parquet(OUT_DIR / "timeout_policy.parquet", index=False)
    kn_tbl = build_kneel_table(df)
    kn_tbl.to_parquet(OUT_DIR / "kneel_decision.parquet", index=False)
    fgs_tbl = build_fg_setup_table(df)
    fgs_tbl.to_parquet(OUT_DIR / "fg_setup.parquet", index=False)
    build_fg_setup_rush(df).to_parquet(OUT_DIR / "fg_setup_rush.parquet", index=False)
    build_eoh_spike_table(df).to_parquet(OUT_DIR / "eoh_spike.parquet", index=False)
    print(f"  fg_setup {len(fgs_tbl)} rows (+ fg_setup_rush)")
    print(f"  timeout policy {len(to_tbl2)} rows, kneel {len(kn_tbl)} rows")

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
