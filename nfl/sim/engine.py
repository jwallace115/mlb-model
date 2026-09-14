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

ROOT = Path(__file__).resolve().parent.parent.parent
TABLES_DIR = ROOT / "nfl" / "data" / "sim" / "tables"
RATINGS_DIR = ROOT / "nfl" / "data" / "sim" / "ratings"

# Module-level cache
_CACHE = {}


def _load_tables():
    if "tables" in _CACHE:
        return
    _CACHE["pass"] = pd.read_parquet(TABLES_DIR / "pass_outcomes.parquet")
    _CACHE["rush"] = pd.read_parquet(TABLES_DIR / "rush_outcomes.parquet")
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

def _build_pass_arrays():
    """Build 4D numpy arrays indexed by (down, dist_bucket, zone) for fast lookup."""
    tbl = _CACHE["pass"]
    dist_map = {"short": 0, "med": 1, "long": 2}
    zone_map = {"own20": 0, "own40": 1, "midfield": 2, "opp20": 3, "rz10": 4}

    shape = (5, 3, 5)
    p_fumble = np.full(shape, 0.008)
    p_sack = np.full(shape, 0.06)
    sack_yds_q = np.full(shape + (101,), -5.0)
    p_int = np.full(shape, 0.02)
    p_comp = np.full(shape, 0.65)
    p_succ = np.full(shape, 0.50)
    yds_succ_q = np.full(shape + (101,), 12.0)
    yds_fail_q = np.full(shape + (101,), 3.0)

    for _, r in tbl.iterrows():
        d = int(r["down"])
        di = dist_map.get(r["dist"])
        zi = zone_map.get(r["zone"])
        if di is None or zi is None:
            continue
        p_fumble[d, di, zi] = r.get("p_fumble", 0.008)
        p_sack[d, di, zi] = r["p_sack"]
        sack_yds_q[d, di, zi] = np.array(r["sack_yds_q"])
        p_int[d, di, zi] = r["p_int"]
        p_comp[d, di, zi] = r["p_comp"]
        p_succ[d, di, zi] = r["p_success_given_comp"]
        yds_succ_q[d, di, zi] = np.array(r["yds_success_q"])
        yds_fail_q[d, di, zi] = np.array(r["yds_fail_q"])

    return p_fumble, p_sack, sack_yds_q, p_int, p_comp, p_succ, yds_succ_q, yds_fail_q


def _build_rush_arrays():
    tbl = _CACHE["rush"]
    dist_map = {"short": 0, "med": 1, "long": 2}
    zone_map = {"own20": 0, "own40": 1, "midfield": 2, "opp20": 3, "rz10": 4}

    shape = (5, 3, 5)
    p_fum = np.full(shape, 0.01)
    p_succ = np.full(shape, 0.43)
    yds_succ_q = np.full(shape + (101,), 5.0)
    yds_fail_q = np.full(shape + (101,), 1.0)

    for _, r in tbl.iterrows():
        d = int(r["down"])
        di = dist_map.get(r["dist"])
        zi = zone_map.get(r["zone"])
        if di is None or zi is None:
            continue
        p_fum[d, di, zi] = r["p_fumble"]
        p_succ[d, di, zi] = r["p_success"]
        yds_succ_q[d, di, zi] = np.array(r["yds_success_q"])
        yds_fail_q[d, di, zi] = np.array(r["yds_fail_q"])

    return p_fum, p_succ, yds_succ_q, yds_fail_q


def _build_clock_arrays():
    """Build clock quantile arrays: key=(outcome_type, hurry) -> (101,) quantiles."""
    tbl = _CACHE["clock"]
    d = {}
    for _, r in tbl.iterrows():
        d[(r["outcome_type"], r["hurry"])] = np.array(r["elapsed_q"])
    return d


def _build_4th_down_lookup():
    tbl = _CACHE["4th"]
    d = {}
    for _, r in tbl.iterrows():
        d[(r["ydstogo_b"], r["yl_b"], r["score_b"], r["qtr_b"])] = (r["p_go"], r["p_punt"], r["p_fg"])
    return d


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
        else:
            ctx[f"t{ti}_proe"] = 0.0
            ctx[f"t{ti}_pace"] = 30.0
            ctx[f"t{ti}_4th_go"] = 0.15

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

    # League pace for scaling
    ctx["lg_pace"] = tend["pace_sec"].mean() if len(tend) else 30.0

    # League average 4th-down go rate (from tendencies, for team override scaling)
    ctx["lg_4th_go"] = tend["fourth_down_go_rate"].mean() if len(tend) else 0.68

    return ctx


# ═══════════════════════════════════════════════════════════════════════════════
# VECTORISED GAME SIMULATION
# ═══════════════════════════════════════════════════════════════════════════════

def simulate_game(home, away, season, week, n_sims=2000, seed=42,
                  team_r=None, tend=None, sit=None, kicker=None, league=None,
                  _dummy_draw=False):
    _load_tables()
    if team_r is None:
        team_r, tend, sit, kicker, league = _load_ratings()

    rng = np.random.default_rng(seed)
    ctx = _build_game_context(home, away, season, week, team_r, tend, sit, kicker, league)

    # Build lookup arrays
    (pa_fumble, pa_sack, pa_sack_yds, pa_int, pa_comp, pa_succ,
     pa_yds_succ, pa_yds_fail) = _build_pass_arrays()
    (ru_fum, ru_succ, ru_yds_succ, ru_yds_fail) = _build_rush_arrays()
    clock_q = _build_clock_arrays()
    fd_lookup = _build_4th_down_lookup()
    fg_lookup = _build_fg_lookup()
    punt_lookup = _build_punt_lookup()

    pc_lookup = dict(zip(_CACHE["playcall"]["bucket"], _CACHE["playcall"]["pass_rate"]))
    scalars = _CACHE["scalars"]
    to_ret = _CACHE["turnover"]
    consts = _CACHE["constants"]

    int_ret_q = np.array(to_ret["int_return_yds_q"])
    fum_ret_q = np.array(to_ret["fum_return_yds_q"])
    p_int_def_td = to_ret["int_p_def_td"]
    p_fum_def_td = to_ret["fum_p_def_td"]

    p_penalty_nop = scalars["penalty"]["p_no_play_penalty"]
    p_off_pen = scalars["penalty"].get("p_noplay_offense", 0.615)
    p_auto_first = scalars["penalty"].get("noplay_auto_first", 0.5)

    p_punt_ret_td = to_ret.get("punt_p_ret_td", 0.0024)
    p_ko_ret_td = to_ret.get("ko_p_ret_td", 0.0025)

    lb = ctx["lb"]

    N = n_sims

    # State arrays
    poss = np.ones(N, dtype=np.int8)  # 0=home, 1=away; away receives first
    down = np.ones(N, dtype=np.int8)
    dist = np.full(N, 10, dtype=np.int16)
    yl = np.full(N, 75, dtype=np.int16)  # yardline_100
    qtr = np.ones(N, dtype=np.int8)
    clock = np.full(N, 900, dtype=np.float32)  # seconds in quarter

    score_h = np.zeros(N, dtype=np.int16)
    score_a = np.zeros(N, dtype=np.int16)
    score_h_1h = np.zeros(N, dtype=np.int16)
    score_a_1h = np.zeros(N, dtype=np.int16)
    half_recorded = np.zeros(N, dtype=bool)

    n_plays = np.zeros(N, dtype=np.int16)
    n_drives = np.ones(N, dtype=np.int16)
    h_pass_yds = np.zeros(N, dtype=np.int32)
    h_rush_yds = np.zeros(N, dtype=np.int32)
    a_pass_yds = np.zeros(N, dtype=np.int32)
    a_rush_yds = np.zeros(N, dtype=np.int32)
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
    ev_fg_made = np.zeros(N, dtype=np.int16)
    ev_tds = np.zeros(N, dtype=np.int16)
    ev_penalties = np.zeros(N, dtype=np.int16)
    ev_clock_used = np.zeros(N, dtype=np.float32)  # Total clock consumed by play draws

    # No scale factors — all numbers come from tables built from data

    # OT state: track first-possession-complete for OT rules
    ot_first_poss_team = np.full(N, -1, dtype=np.int8)
    ot_first_poss_done = np.zeros(N, dtype=bool)

    def _new_drive(m):
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
        # XP: use kicker rate for scoring team
        xp_prob = np.full(N, 0.94)
        for ti in [0, 1]:
            tm = m & (scoring_team_idx == ti)
            xp_prob[tm] = ctx[f"t{ti}_xp"]
        made = m & (u_pat < xp_prob)
        score_h[made & (scoring_team_idx == 0)] += 1
        score_a[made & (scoring_team_idx == 1)] += 1

    def _do_kickoff(m):
        poss[m] = 1 - poss[m]
        yl[m] = 75
        _new_drive(m)

    def _check_ko_ret_td(m):
        """After a kickoff, check for return TD from empirical rate.
        Scores directly (no recursive kickoff) since P(consecutive) ≈ 0."""
        for i in np.where(m)[0]:
            if u_ko_td[i] < p_ko_ret_td:
                ret_team = poss[i]
                m1 = np.zeros(N, dtype=bool); m1[i] = True
                ev_tds[m1] += 1
                _score_td(m1, np.full(N, ret_team, dtype=np.int8))
                _do_pat(m1, np.full(N, ret_team, dtype=np.int8))
                # After KO return TD PAT, opponent gets ball
                _do_kickoff(m1)

    def _handle_td(m, scoring_poss):
        """Full TD sequence: score, PAT, kickoff. scoring_poss = who had the ball."""
        ev_tds[m] += 1
        _score_td(m, scoring_poss)
        _do_pat(m, scoring_poss)
        _do_kickoff(m)
        _check_ko_ret_td(m & (qtr < 5))  # no KO return TD in OT
        # In OT: any score ends the game
        ot_m = m & (qtr >= 5)
        if ot_m.any():
            game_over[ot_m] = True

    def _dist_idx(d):
        return np.where(d <= 3, 0, np.where(d <= 7, 1, 2)).astype(np.intp)

    def _zone_idx(y):
        return np.where(y > 80, 0,
               np.where(y > 60, 1,
               np.where(y > 20, 2,
               np.where(y > 10, 3, 4)))).astype(np.intp)

    # ═══════════════════════════════════════════════════════════════════════════
    # MAIN LOOP
    # ═══════════════════════════════════════════════════════════════════════════

    max_steps = 500
    for step in range(max_steps):
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
        u_punt_net = rng.random(N)
        u_fg_mk = rng.random(N)
        u_pen = rng.random(N)
        u_pen_side = rng.random(N)
        u_pen_auto = rng.random(N)
        u_call = rng.random(N)
        u_sack = rng.random(N)
        u_int_ = rng.random(N)
        u_comp = rng.random(N)
        u_succ = rng.random(N)
        u_yards = rng.random(N)
        u_pfum = rng.random(N)
        u_int_dtd = rng.random(N)
        u_int_ret = rng.random(N)
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
        u_ot = rng.random(N)
        u_punt_td = rng.random(N)
        u_ko_td = rng.random(N)

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
                poss[ht] = 0  # Home receives 2nd half
                yl[ht] = 75
                _new_drive(ht)

            # End of regulation (Q4 over) — only if clock is STILL <= 0
            # after the quarter advance (not just from the previous quarter ending)
            end_reg = alive & (qtr == 4) & (clock <= 0)
            if end_reg.any():
                tied = end_reg & (score_h == score_a)
                not_tied = end_reg & ~tied
                game_over[not_tied] = True

                # OT
                if tied.any():
                    ot_flag[tied] = 1
                    qtr[tied] = 5
                    clock[tied] = 600.0
                    ct = (u_ot >= 0.5).astype(np.int8)
                    poss[tied] = ct[tied]
                    ot_first_poss_team[tied] = ct[tied]
                    yl[tied] = 75
                    _new_drive(tied)

            # End of OT — only if clock is still <= 0
            end_ot = alive & (qtr >= 5) & (clock <= 0)
            game_over[end_ot] = True
            continue

        alive = ~game_over
        if not alive.any():
            break

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
        kneels_avail = (5 - down).astype(np.float32)  # knees left including this one
        effective_kneels = np.maximum(kneels_avail - 1.0, 1.0)  # subtract ~1 for timeouts
        can_kneel = (alive & (qtr == 4) & (score_diff_poss > 0) &
                     (clock <= effective_kneels * 40) & (clock > 0))
        if can_kneel.any():
            clock[can_kneel] -= 40
            ev_clock_used[can_kneel] += 40
            continue

        # --- 4th down decision ---
        is_4th = alive & (down == 4)
        punt_m = np.zeros(N, dtype=bool)
        fg_m = np.zeros(N, dtype=bool)

        if is_4th.any():
            idx4 = np.where(is_4th)[0]

            for i in idx4:
                yd = int(dist[i])
                y = int(yl[i])
                sd = int(score_diff_poss[i])
                qt = int(qtr[i])
                cl = float(clock[i])

                yd_b = "1-2" if yd <= 2 else ("3-5" if yd <= 5 else ("6-10" if yd <= 10 else "11+"))
                # 10-yard field-zone bins
                if y <= 10: yl_b = "opp1-10"
                elif y <= 20: yl_b = "opp11-20"
                elif y <= 30: yl_b = "opp21-30"
                elif y <= 40: yl_b = "opp31-40"
                elif y <= 50: yl_b = "opp41-50"
                elif y <= 60: yl_b = "own41-50"
                elif y <= 70: yl_b = "own31-40"
                elif y <= 80: yl_b = "own21-30"
                elif y <= 90: yl_b = "own11-20"
                else: yl_b = "own1-10"

                # Fine-grained score bucket
                if sd < -8: sc_fine = "trail9+"
                elif sd < -3: sc_fine = "trail4-8"
                elif sd < 0: sc_fine = "trail1-3"
                elif sd == 0: sc_fine = "tied"
                elif sd <= 3: sc_fine = "lead1-3"
                elif sd <= 8: sc_fine = "lead4-8"
                else: sc_fine = "lead9+"

                # Fine-grained clock bucket
                if qt <= 3:
                    qt_fine = "Q1-3"
                elif cl > 300:
                    qt_fine = "Q4>5"
                elif cl > 120:
                    qt_fine = "Q4_2-5"
                else:
                    qt_fine = "Q4<2"

                # Coarse fallback keys
                sc_coarse = "trail9" if sd < -8 else ("within8" if sd <= 8 else "lead9")
                qt_coarse = "Q1-3" if qt <= 3 else "Q4"
                # Coarse 4-zone field position
                if y <= 10: yl_coarse = "rz"
                elif y <= 40: yl_coarse = "opp40"
                elif y <= 65: yl_coarse = "midfield"
                else: yl_coarse = "own35"

                # Lookup with 4-level fallback
                probs = fd_lookup.get((yd_b, yl_b, sc_fine, qt_fine))
                if probs is None:
                    probs = fd_lookup.get((yd_b, yl_b, f"c_{sc_coarse}", qt_fine))
                if probs is None:
                    probs = fd_lookup.get((yd_b, f"z_{yl_coarse}", sc_fine, qt_fine))
                if probs is None:
                    probs = fd_lookup.get((yd_b, f"zc_{yl_coarse}", f"zc_{sc_coarse}", qt_coarse))
                if probs is None:
                    if y <= 35:
                        probs = (0.1, 0.1, 0.8)
                    elif y <= 50 and yd <= 2:
                        probs = (0.4, 0.4, 0.2)
                    else:
                        probs = (0.1, 0.8, 0.1)

                p_go, p_punt, p_fg = probs

                # Team 4th-down aggressiveness override (Q1-Q3 only;
                # late-game decisions are situation-driven, not style-driven)
                if qt <= 3:
                    ti = poss[i]
                    team_go = ctx[f"t{ti}_4th_go"]
                    lg_go = ctx["lg_4th_go"]
                    if team_go > 0 and lg_go > 0:
                        ratio = team_go / lg_go
                        p_go_adj = np.clip(p_go * ratio, 0, 0.95)
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
                    pass  # Go for it — normal play
                elif r < p_go + p_punt:
                    punt_m[i] = True
                else:
                    fg_m[i] = True

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
                    new_yl = int(np.clip(100 - (yl[i] - net), 1, 99))
                    if new_yl < 1:
                        new_yl = 80  # Touchback
                    yl[i] = new_yl
                # Punt return TD (empirical rate from table G)
                punt_ret_td_m = punt_m.copy()
                for i in np.where(punt_m)[0]:
                    if u_punt_td[i] < p_punt_ret_td:
                        # Return team scores a TD
                        ret_team = 1 - poss[i]  # Receiving team
                        m1 = np.zeros(N, dtype=bool); m1[i] = True
                        poss[i] = 1 - poss[i]
                        _handle_td(m1, np.full(N, ret_team, dtype=np.int8))
                        punt_ret_td_m[i] = False  # Don't do normal punt handling
                normal_punt = punt_m & punt_ret_td_m
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
                score_h[made_full & (poss == 0)] += 3
                score_a[made_full & (poss == 1)] += 3

                # OT: FG ends game if second possession or first possession team scored
                ot_fg = made_full & (qtr >= 5)
                # Simple: in OT, any score on 2nd possession ends game
                # First possession: FG doesn't end game (other team gets a chance)
                ot_first_scoring = ot_fg & (poss == ot_first_poss_team) & ~ot_first_poss_done
                ot_first_poss_done[ot_first_scoring] = True
                ot_second = ot_fg & ~ot_first_scoring
                game_over[ot_second] = True

                _do_kickoff(made_full)
                _check_ko_ret_td(made_full & (qtr < 5))
                # FG/kickoff clock captured in cross-play elapsed table

                # Miss: opponent gets ball
                if miss_full.any():
                    yl[miss_full] = np.clip(100 - yl[miss_full], 20, 99)
                    poss[miss_full] = 1 - poss[miss_full]
                    _new_drive(miss_full)

        # --- Scrimmage plays (non-punt/FG) ---
        alive = ~game_over
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
            off_pen = pen_nop & (u_pen_side < p_off_pen)
            def_pen = pen_nop & ~off_pen

            # Offense penalty: move back ~7 yds, replay down
            yl[off_pen] = np.clip(yl[off_pen] + 7, 1, 99).astype(np.int16)

            # Defense penalty: advance ~9 yds, 72.5% auto first down
            # Check for penalty in end zone (ball at 1-yd line)
            pen_td = def_pen.copy()
            pen_td[def_pen] = yl[def_pen] <= 9
            pen_no_td = def_pen & ~pen_td

            yl[pen_no_td] = np.clip(yl[pen_no_td] - 9, 1, 99).astype(np.int16)
            auto_1st = pen_no_td & (u_pen_auto < p_auto_first)
            down[auto_1st] = 1
            dist[auto_1st] = np.minimum(10, yl[auto_1st]).astype(np.int16)
            ev_first_downs[auto_1st] += 1
            non_auto_def = pen_no_td & ~auto_1st
            dist[non_auto_def] = np.maximum(1, dist[non_auto_def] - 9).astype(np.int16)

            # Penalty near goal line: ball at 1, first and goal
            if pen_td.any():
                yl[pen_td] = 1
                down[pen_td] = 1
                dist[pen_td] = 1
                ev_first_downs[pen_td] += 1

            ev_penalties[pen_nop] += 1
            playing = playing & ~pen_nop

        if not playing.any():
            continue

        n_live = playing.sum()
        live_idx = np.where(playing)[0]

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

        # Pass probability — vectorised bucket construction
        d_s = np.char.add(down_live.astype(str), ".0")
        di_s = np.where(dist_live <= 3, "short", np.where(dist_live <= 7, "med", "long"))
        sc_s = np.where(sd_live < -8, "trail9", np.where(sd_live <= 8, "within8", "lead9"))
        cl_s = np.where(qtr_live <= 3, "Q1-3", "Q4")
        bkt_arr = np.char.add(np.char.add(np.char.add(np.char.add(
            d_s, "_"), di_s), "_"), np.char.add(np.char.add(sc_s, "_"), cl_s))
        lg_xpass = np.array([pc_lookup.get(b, 0.55) for b in bkt_arr])
        team_proe = np.empty(n_live)
        for ti in [0, 1]:
            tm = poss_live == ti
            sit = ctx[f"t{ti}_sit_proe"]
            overall = ctx[f"t{ti}_proe"]
            team_proe[tm] = np.array([sit.get(b, overall) for b in bkt_arr[tm]])
        p_pass = _sigmoid(_logit(lg_xpass) + team_proe / 100.0)

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

            # Apply matchup via log5 ratio adjustment
            for ti in [0, 1]:
                tm = poss_p == ti
                if tm.any():
                    tbl_sack[tm] *= ctx[f"t{ti}_sack_rate"] / max(lb["pass_sack_rate"], 0.001)
                    tbl_int[tm] *= ctx[f"t{ti}_int_rate"] / max(lb["pass_int_rate"], 0.001)
                    r_succ = ctx[f"t{ti}_pass_success"] / max(lb["pass_success"], 0.001)
                    tbl_succ[tm] *= r_succ
            tbl_sack = np.clip(tbl_sack, 0, 0.4)
            tbl_int = np.clip(tbl_int, 0, 0.2)
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
                        for zi_v in range(5):
                            m = sk[(d_p[sk]==d_v)&(di_p[sk]==di_v)&(zi_p[sk]==zi_v)]
                            if len(m):
                                yards[m] = np.interp(u5[m], xs101, pa_sack_yds[d_v, di_v, zi_v])

            # Completion yards — success/fail split with matchup tilt
            comp_succ = completed & (u4 < tbl_succ)
            comp_fail = completed & ~comp_succ
            for yds_mask, yds_tbl in [(comp_succ, pa_yds_succ), (comp_fail, pa_yds_fail)]:
                if yds_mask.any():
                    idx = np.where(yds_mask)[0]
                    for d_v in range(1, 5):
                        for di_v in range(3):
                            for zi_v in range(5):
                                m = idx[(d_p[idx]==d_v)&(di_p[idx]==di_v)&(zi_p[idx]==zi_v)]
                                if len(m):
                                    yards[m] = np.interp(u5[m], xs101, yds_tbl[d_v, di_v, zi_v])

            # --- Apply results to state (vectorised where possible) ---
            yds_int = np.round(yards).astype(int)
            td_mask = completed & (yl_p - yds_int <= 0) & (yds_int > 0)
            safety_mask = sacked & (yl_p - yds_int >= 100)
            normal_comp = completed & ~td_mask
            normal_sack = sacked & ~safety_mask

            # Normal completions (vectorised)
            nc_g = g_idx[normal_comp]
            nc_yds = yds_int[normal_comp]
            if len(nc_g):
                yl[nc_g] = np.clip(yl[nc_g] - nc_yds, 1, 99).astype(np.int16)
                nc_home = poss[nc_g] == 0
                h_pass_yds[nc_g[nc_home]] += np.maximum(nc_yds[nc_home], 0)
                a_pass_yds[nc_g[~nc_home]] += np.maximum(nc_yds[~nc_home], 0)
                nc_fd = nc_yds >= dist[nc_g]
                down[nc_g[nc_fd]] = 1
                dist[nc_g[nc_fd]] = np.minimum(10, yl[nc_g[nc_fd]]).astype(np.int16)
                dist[nc_g[~nc_fd]] = np.maximum(1, dist[nc_g[~nc_fd]] - nc_yds[~nc_fd]).astype(np.int16)
                down[nc_g[~nc_fd]] += 1
                n_plays[nc_g] += 1

            # Normal sacks (vectorised)
            ns_g = g_idx[normal_sack]
            ns_yds = yds_int[normal_sack]
            if len(ns_g):
                yl[ns_g] = np.clip(yl[ns_g] - ns_yds, 1, 99).astype(np.int16)
                dist[ns_g] = np.maximum(1, dist[ns_g] - ns_yds).astype(np.int16)
                down[ns_g] += 1
                n_plays[ns_g] += 1

            # Incompletes (vectorised)
            inc_g = g_idx[incomplete]
            if len(inc_g):
                down[inc_g] += 1
                n_plays[inc_g] += 1

            # TDs (per-sim — rare, ~3/game)
            for j in np.where(td_mask)[0]:
                gi = g_idx[j]
                if poss[gi] == 0: h_pass_yds[gi] += int(yl[gi])
                else: a_pass_yds[gi] += int(yl[gi])
                n_plays[gi] += 1
                m = np.zeros(N, dtype=bool); m[gi] = True
                _handle_td(m, np.full(N, poss[gi], dtype=np.int8))

            # Safeties (per-sim — extremely rare)
            for j in np.where(safety_mask)[0]:
                gi = g_idx[j]
                n_plays[gi] += 1
                dt = 1 - poss[gi]
                score_h[gi] += 2 * (dt == 0); score_a[gi] += 2 * (dt == 1)
                yl[gi] = 75; poss[gi] = 1 - poss[gi]
                m = np.zeros(N, dtype=bool); m[gi] = True; _new_drive(m)

            # Interceptions (per-sim — ~1-2/game)
            for j in np.where(intercepted)[0]:
                gi = g_idx[j]
                turnovers[gi] += 1; n_plays[gi] += 1
                if u_int_dtd[gi] < p_int_def_td:
                    m = np.zeros(N, dtype=bool); m[gi] = True
                    _handle_td(m, np.full(N, 1 - poss[gi], dtype=np.int8))
                else:
                    ret = int(np.interp(u_int_ret[gi], np.linspace(0, 1, 101), int_ret_q))
                    yl[gi] = int(np.clip(100 - (yl[gi] + ret), 1, 99))
                    poss[gi] = 1 - poss[gi]
                    m = np.zeros(N, dtype=bool); m[gi] = True; _new_drive(m)

            # Pass fumbles (per-sim — ~0.5/game)
            for j in np.where(pass_fumbled)[0]:
                gi = g_idx[j]
                turnovers[gi] += 1; n_plays[gi] += 1
                if u_pfum_dtd[gi] < p_fum_def_td:
                    m = np.zeros(N, dtype=bool); m[gi] = True
                    _handle_td(m, np.full(N, 1 - poss[gi], dtype=np.int8))
                else:
                    ret = int(np.interp(u_pfum_ret[gi], np.linspace(0, 1, 101), fum_ret_q))
                    yl[gi] = int(np.clip(100 - (yl[gi] + ret), 1, 99))
                    poss[gi] = 1 - poss[gi]
                    m = np.zeros(N, dtype=bool); m[gi] = True; _new_drive(m)

            # Track events (vectorised)
            ev_pass_plays[g_idx] += 1
            ev_sacks[g_idx[sacked]] += 1
            ev_ints[g_idx[intercepted]] += 1
            ev_incomp[g_idx[incomplete]] += 1
            ev_comp[g_idx[completed]] += 1
            fd_comp = normal_comp & (yds_int >= dist_live[p_idx])
            ev_first_downs[g_idx[fd_comp | td_mask]] += 1

            # Clock: pass plays — vectorised
            # Map outcome type: 0=incomplete, 1=first_down, 2=complete_inbounds, 3=drive_ending
            ot_idx = np.full(n_p, 2, dtype=np.int8)
            ot_idx[incomplete] = 0
            fd_pass = completed & (yds_int >= dist_live[p_idx])
            ot_idx[fd_pass] = 1
            # Drive-ending plays (TD, INT, fumble) stop the game clock —
            # actual elapsed is ~8-10s, not the 33-39s of the regular category
            ot_idx[td_mask | intercepted | pass_fumbled] = 3
            # Hurry-up flag
            gi_arr = g_idx
            sd_arr = np.where(poss[gi_arr] == 0,
                              score_h[gi_arr] - score_a[gi_arr],
                              score_a[gi_arr] - score_h[gi_arr])
            hurry_arr = ((qtr[gi_arr] == 4) |
                         ((qtr[gi_arr] == 2) & (clock[gi_arr] <= 120))) & (sd_arr <= 8)
            ot_strs = ["incomplete", "first_down", "complete_inbounds"]
            xs101 = np.linspace(0, 1, 101)
            # Pace scale per sim
            pace_arr = np.where(poss[gi_arr] == 0,
                                ctx["t0_pace"], ctx["t1_pace"]) / ctx["lg_pace"]
            for oi in range(3):
                for hi in [False, True]:
                    mask = (ot_idx == oi) & (hurry_arr == hi) & ~game_over[gi_arr]
                    if not mask.any():
                        continue
                    cq = clock_q.get((ot_strs[oi], hi),
                                      clock_q.get((ot_strs[oi], False), np.full(101, 30.0)))
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

            # Apply matchup tilt on rush success
            for ti in [0, 1]:
                tm = poss_r == ti
                if tm.any():
                    r_succ = ctx[f"t{ti}_rush_success"] / max(lb["rush_success"], 0.001)
                    tbl_succ_r[tm] *= r_succ
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
                            for zi_v in range(5):
                                m = idx[(d_r[idx]==d_v)&(di_r[idx]==di_v)&(zi_r[idx]==zi_v)]
                                if len(m):
                                    yards_r[m] = np.interp(u5[m], xs101, yds_tbl[d_v, di_v, zi_v])

            yds_r = np.round(yards_r).astype(int)
            td_r = not_fum & (yl_r - yds_r <= 0) & (yds_r > 0)
            safety_r = not_fum & (yl_r - yds_r >= 100)
            normal_r = not_fum & ~td_r & ~safety_r

            # Normal rushes (vectorised)
            nr_g = g_idx_r[normal_r]
            nr_yds = yds_r[normal_r]
            if len(nr_g):
                yl[nr_g] = np.clip(yl[nr_g] - nr_yds, 1, 99).astype(np.int16)
                nr_home = poss[nr_g] == 0
                h_rush_yds[nr_g[nr_home]] += np.maximum(nr_yds[nr_home], 0)
                a_rush_yds[nr_g[~nr_home]] += np.maximum(nr_yds[~nr_home], 0)
                nr_fd = nr_yds >= dist[nr_g]
                down[nr_g[nr_fd]] = 1
                dist[nr_g[nr_fd]] = np.minimum(10, yl[nr_g[nr_fd]]).astype(np.int16)
                dist[nr_g[~nr_fd]] = np.maximum(1, dist[nr_g[~nr_fd]] - nr_yds[~nr_fd]).astype(np.int16)
                down[nr_g[~nr_fd]] += 1
                n_plays[nr_g] += 1

            # Rush TDs (per-sim — rare)
            for j in np.where(td_r)[0]:
                gi = g_idx_r[j]
                if poss[gi] == 0: h_rush_yds[gi] += int(yl[gi])
                else: a_rush_yds[gi] += int(yl[gi])
                n_plays[gi] += 1
                m = np.zeros(N, dtype=bool); m[gi] = True
                _handle_td(m, np.full(N, poss[gi], dtype=np.int8))

            # Rush safeties (per-sim — extremely rare)
            for j in np.where(safety_r)[0]:
                gi = g_idx_r[j]; n_plays[gi] += 1
                dt = 1 - poss[gi]
                score_h[gi] += 2 * (dt == 0); score_a[gi] += 2 * (dt == 1)
                yl[gi] = 75; poss[gi] = 1 - poss[gi]
                m = np.zeros(N, dtype=bool); m[gi] = True; _new_drive(m)

            # Fumbles (per-sim — ~1/game)
            for j in np.where(fumbled)[0]:
                gi = g_idx_r[j]; turnovers[gi] += 1; n_plays[gi] += 1
                if u_rfum_dtd[gi] < p_fum_def_td:
                    m = np.zeros(N, dtype=bool); m[gi] = True
                    _handle_td(m, np.full(N, 1 - poss[gi], dtype=np.int8))
                else:
                    ret = int(np.interp(u_rfum_ret[gi], np.linspace(0, 1, 101), fum_ret_q))
                    yl[gi] = int(np.clip(100 - (yl[gi] + ret), 1, 99))
                    poss[gi] = 1 - poss[gi]
                    m = np.zeros(N, dtype=bool); m[gi] = True; _new_drive(m)

            # Track rush play events (vectorised)
            ev_rush_plays[g_idx_r] += 1
            normal_rush = not_fum & ~td_r & ~safety_r
            fd_rush = normal_rush & (yds_r >= dist_live[r_idx])
            ev_first_downs[g_idx_r[fd_rush | td_r]] += 1

            # Clock: rush plays — vectorised
            ot_idx_r = np.ones(n_r, dtype=np.int8)  # 1=run, 0=first_down, 2=drive_ending
            fd_rush_all = not_fum & (yds_r >= dist_live[r_idx])
            ot_idx_r[fd_rush_all] = 0  # 0=first_down
            ot_idx_r[td_r | fumbled] = 2  # drive-ending: short clock
            gi_r = g_idx_r
            sd_r_arr = np.where(poss[gi_r] == 0,
                                score_h[gi_r] - score_a[gi_r],
                                score_a[gi_r] - score_h[gi_r])
            hurry_r = ((qtr[gi_r] == 4) |
                       ((qtr[gi_r] == 2) & (clock[gi_r] <= 120))) & (sd_r_arr <= 8)
            ot_strs_r = ["first_down", "run"]
            xs101 = np.linspace(0, 1, 101)
            pace_r = np.where(poss[gi_r] == 0,
                              ctx["t0_pace"], ctx["t1_pace"]) / ctx["lg_pace"]
            for oi in range(2):
                for hi in [False, True]:
                    mask = (ot_idx_r == oi) & (hurry_r == hi) & ~game_over[gi_r]
                    if not mask.any():
                        continue
                    cq = clock_q.get((ot_strs_r[oi], hi),
                                      clock_q.get((ot_strs_r[oi], False), np.full(101, 35.0)))
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
            _change_poss(tod)

            # OT: change of possession after first team's drive
            ot_tod = tod & (qtr >= 5) & ~ot_first_poss_done
            ot_first_poss_done[ot_tod] = True

    # If half was never recorded (0-0 at half), record it
    not_rec = ~half_recorded
    score_h_1h[not_rec] = 0
    score_a_1h[not_rec] = 0

    return pd.DataFrame({
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
        "ev_fg_made": ev_fg_made,
        "ev_tds": ev_tds,
        "ev_penalties": ev_penalties,
        "ev_clock_used": ev_clock_used,
    })


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
            seed = hash((game["game_id"], 42)) % (2**31)
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
