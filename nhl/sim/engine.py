#!/usr/bin/env python3
"""
NHL game simulation engine (S34, Cowork rewrite of S32 — see decision S34 for the defects fixed).

Vectorised over N sims (numpy), 1-second clock. Start from puck drop or from any mid-game StartState.
Every rate comes from constants files through league_average_inputs(); the only numbers written here are
structural (period length, skater counts, 2/4/5-minute penalty lengths, 3 shootout rounds).

State per sim: period clock, score, each team's penalty slots (remaining seconds + nominal length),
each team's goalie-pulled flag. Strength = skaters from penalties (+1 extra attacker if the goalie is pulled).
Regulation: 5 skaters base, a penalty removes one (floor 3). Overtime: 3v3 base, a penalty ADDS a skater to
the other side (4v3, 5v3), as NHL regular-season OT rules. Shootout: 3 rounds, then sudden-death rounds.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
C2_PATH = ROOT / "nhl" / "data" / "sim" / "constants_v2.json"
C7_PATH = ROOT / "nhl" / "data" / "sim" / "constants_v7.json"

PERIOD_SECONDS = 1200
REG_SECONDS = 3 * PERIOD_SECONDS
OT_SECONDS = 300
PULL_WINDOW = 300          # pull hazard is measured over the last 300 s of the 3rd period
PULL_BIN = 30
MAX_PEN = 4
MINOR, DOUBLE, MAJOR = 120, 240, 300
SO_ROUNDS = 3
SO_MAX_EXTRA = 30          # sudden-death rounds before a coin flip (never reached in practice)
STATE_PAIRS = [(5, 5), (4, 4), (3, 3), (5, 4), (4, 5), (5, 3), (3, 5), (4, 3), (3, 4)]


@dataclass
class TeamMultipliers:
    """Per-team multipliers on the league rates (1.0 = league average). S-WO4b fills these from ratings."""
    ev_att_for: float = 1.0
    ev_att_against: float = 1.0
    ev_q_for: float = 1.0
    ev_q_against: float = 1.0
    pp_q_for: float = 1.0          # PP goals per attempt, own power play
    pk_q_against: float = 1.0      # goals per attempt allowed on own penalty kill
    pen_taken: float = 1.0
    pen_drawn: float = 1.0
    goalie_save: float = 1.0       # multiplier on goals allowed per attempt (<1 = better goalie)
    finishing: float = 1.0         # league finishing term F(D), applied to non-empty-net goals


@dataclass
class GameInputs:
    att_per_sec: dict              # (own_skaters, opp_skaters) -> attempts per second, both goalies in
    goal_per_att: dict             # (own_skaters, opp_skaters) -> goals per attempt, both goalies in
    ea_att_per_sec: float          # extra attacker side (own goalie pulled)
    ea_goal_per_att: float
    en_att_per_sec: float          # shooting at an empty net
    en_goal_per_att: float
    pp_pen_per_sec: float          # PP-creating penalties per team per second
    pen_len_shares: tuple          # (share 2-min, share 4-min, share 5-min) among PP-creating penalties
    score_effects: dict            # (score diff clipped +-3, period 1..3) -> (attempt mult, goal-per-attempt mult)
    home_att_mult: float
    away_att_mult: float
    home_q_mult: float
    away_q_mult: float
    pull_hazard: dict              # (k = 1..3 behind, bin of seconds remaining) -> hazard per second
    so_conversion: float
    home: TeamMultipliers = field(default_factory=TeamMultipliers)
    away: TeamMultipliers = field(default_factory=TeamMultipliers)


def league_average_inputs():
    c7 = json.loads(C7_PATH.read_text())["constants"]
    c2 = json.loads(C2_PATH.read_text())["constants"]

    def key(own, opp):
        if own == opp:
            return f"per_team_{own}v{opp}"
        return (f"advantaged_{own}v{opp}" if own > opp else f"disadvantaged_{opp}v{own}")

    att, gpa = {}, {}
    for own, opp in STATE_PAIRS:
        k = key(own, opp)
        att[(own, opp)] = c7[f"attempt_rate_per_60_{k}"]["value"] / 3600.0
        gpa[(own, opp)] = c7[f"goals_per_attempt_{k.replace('per_team_', '')}"]["value"]
    se = {(sd, p): (c2[f"score_effect_attempt_mult_sd{sd}_p{p}"]["value"], c2[f"score_effect_xg_mult_sd{sd}_p{p}"]["value"])
          for sd in range(-3, 4) for p in range(1, 4)}
    ph = {(-int(k), int(b)): v["hazard_per_sec"] for k, bins in c7["pull_hazard_per_second"]["data"].items() for b, v in bins.items()}
    pp = c7["pp_penalty"]
    share = c2["home_attempt_share"]["value"]
    qm = c2["home_xg_per_attempt_mult"]["value"]
    return GameInputs(
        att_per_sec=att, goal_per_att=gpa,
        ea_att_per_sec=c7["attempt_rate_per_60_advantaged_6v5"]["value"] / 3600.0,
        ea_goal_per_att=c7["goals_per_attempt_advantaged_6v5"]["value"],
        en_att_per_sec=c7["attempt_rate_per_60_disadvantaged_6v5"]["value"] / 3600.0,
        en_goal_per_att=c7["goals_per_attempt_disadvantaged_6v5"]["value"],
        pp_pen_per_sec=pp["per_team_per_second"],
        pen_len_shares=(pp["nominal_share_2min"], pp["nominal_share_4min"], pp["nominal_share_5min"]),
        score_effects=se,
        home_att_mult=share / 0.5, away_att_mult=(1 - share) / 0.5,
        home_q_mult=float(np.sqrt(qm)), away_q_mult=float(1 / np.sqrt(qm)),
        pull_hazard=ph,
        so_conversion=c2["shootout_conversion"]["value"],
    )


@dataclass
class StartState:
    period: int = 1                 # 1-3 regulation, 4 = overtime
    second: int = 0                 # seconds elapsed in the period
    home_score: int = 0
    away_score: int = 0
    home_penalties: list = field(default_factory=list)   # [(seconds remaining, nominal seconds 120/240/300), ...]
    away_penalties: list = field(default_factory=list)
    home_pulled: bool = False
    away_pulled: bool = False


def _skaters(base, own_act, opp_act):
    if base == 5:
        return np.clip(5 - own_act, 3, 5), np.clip(5 - opp_act, 3, 5)
    extra_opp = np.clip(own_act - opp_act, 0, 2)          # OT: my penalty gives the opponent an extra skater
    extra_own = np.clip(opp_act - own_act, 0, 2)
    return 3 + extra_own, 3 + extra_opp


def simulate(inputs: GameInputs, n_sims: int, seed: int, start_state: Optional[StartState] = None):
    rng = np.random.default_rng(seed)
    N, inp = n_sims, inputs
    ss = start_state if start_state is not None else StartState()

    # rate tables indexed [own_skaters, opp_skaters]
    ATT = np.zeros((6, 6)); GPA = np.zeros((6, 6))
    for (o, p), v in inp.att_per_sec.items():
        ATT[o, p] = v
        GPA[o, p] = inp.goal_per_att[(o, p)]
    shares = np.cumsum(inp.pen_len_shares)
    shares = shares / shares[-1]
    HM, AM = inp.home, inp.away

    score = {"h": np.full(N, ss.home_score, np.int32), "a": np.full(N, ss.away_score, np.int32)}
    pen_rem = {"h": np.zeros((N, MAX_PEN), np.int32), "a": np.zeros((N, MAX_PEN), np.int32)}
    pen_nom = {"h": np.zeros((N, MAX_PEN), np.int32), "a": np.zeros((N, MAX_PEN), np.int32)}
    for t, lst in (("h", ss.home_penalties), ("a", ss.away_penalties)):
        for i, (rem, nom) in enumerate(lst[:MAX_PEN]):
            pen_rem[t][:, i] = rem
            pen_nom[t][:, i] = nom
    pulled = {"h": np.full(N, ss.home_pulled), "a": np.full(N, ss.away_pulled)}
    out = {f"{k}_{t}": np.zeros(N, np.int32) for k in ("pp_goals", "en_goals", "attempts", "pp_opps", "pp_seconds") for t in ("h", "a")}
    decided = np.zeros(N, np.int8)                       # 0 REG, 1 OT, 2 SO
    live = np.ones(N, bool)
    reg = {}
    mult = {"h": (HM, AM, inp.home_att_mult, inp.home_q_mult), "a": (AM, HM, inp.away_att_mult, inp.away_q_mult)}

    start_sec = (ss.period - 1) * PERIOD_SECONDS + ss.second
    end_sec = REG_SECONDS + OT_SECONDS
    for sec in range(start_sec, end_sec):
        if sec == REG_SECONDS:                           # end of regulation
            reg = {t: score[t].copy() for t in ("h", "a")}
            live = score["h"] == score["a"]
            pulled["h"][:] = False
            pulled["a"][:] = False
            if not live.any():
                break
        in_ot = sec >= REG_SECONDS
        period = min(sec // PERIOD_SECONDS + 1, 3)
        base = 3 if in_ot else 5
        act = {t: (pen_rem[t] > 0).sum(axis=1) for t in ("h", "a")}
        sk = {}
        sk["h"], sk["a"] = _skaters(base, act["h"], act["a"])
        goals = {}
        for t, o in (("h", "a"), ("a", "h")):
            me, opp, side_att, side_q = mult[t]
            own_sk, opp_sk = sk[t], sk[o]
            att = ATT[own_sk, opp_sk].copy()
            gpa = GPA[own_sk, opp_sk].copy()
            ev = (own_sk == 5) & (opp_sk == 5) & ~pulled[t] & ~pulled[o] & ~in_ot
            if ev.any():
                sd = np.clip(score[t] - score[o], -3, 3)
                am = np.ones(N); qm = np.ones(N)
                for s in range(-3, 4):
                    m = ev & (sd == s)
                    if m.any():
                        a_, q_ = inp.score_effects[(s, period)]
                        am[m] = a_; qm[m] = q_
                att *= am; gpa *= qm
                att = np.where(ev, att * me.ev_att_for * opp.ev_att_against, att)
                gpa = np.where(ev, gpa * me.ev_q_for * opp.ev_q_against, gpa)
            pp = (own_sk > opp_sk) & ~pulled[t] & ~pulled[o]
            gpa = np.where(pp, gpa * me.pp_q_for * opp.pk_q_against, gpa)
            gpa = gpa * opp.goalie_save * me.finishing
            att = np.where(pulled[t], inp.ea_att_per_sec, att)
            gpa = np.where(pulled[t], inp.ea_goal_per_att * opp.goalie_save * me.finishing, gpa)
            att = np.where(pulled[o], inp.en_att_per_sec, att)
            gpa = np.where(pulled[o], inp.en_goal_per_att, gpa)
            att = att * side_att
            gpa = np.where(pulled[o], gpa, gpa * side_q)
            shot = live & (rng.random(N) < att)
            g = shot & (rng.random(N) < gpa)
            out[f"attempts_{t}"] += shot
            out[f"pp_seconds_{t}"] += (live & (own_sk > opp_sk)).astype(np.int32)
            goals[t] = (g, own_sk > opp_sk, pulled[o].copy())
        if in_ot:                                        # sudden death: one goal per sim
            both = goals["h"][0] & goals["a"][0]
            coin = rng.random(N) < 0.5
            goals["h"] = (goals["h"][0] & (~both | coin),) + goals["h"][1:]
            goals["a"] = (goals["a"][0] & (~both | ~coin),) + goals["a"][1:]
        for t, o in (("h", "a"), ("a", "h")):
            g, was_pp, empty = goals[t]
            score[t] += g
            out[f"pp_goals_{t}"] += g & was_pp
            out[f"en_goals_{t}"] += g & empty
            # a power-play goal ends the opponent's shortest minor, or the current half of a double minor
            end = g & was_pp
            if end.any():
                rem, nom = pen_rem[o], pen_nom[o]
                ends_minor = (rem > 0) & (nom == MINOR)
                cand = np.where(ends_minor, rem, 10**6)
                j = cand.argmin(axis=1)
                has_minor = ends_minor.any(axis=1)
                rows = np.where(end & has_minor)[0]
                rem[rows, j[rows]] = 0
                dbl = end & ~has_minor & ((rem > 0) & (nom == DOUBLE)).any(axis=1)
                if dbl.any():
                    cand = np.where((rem > 0) & (nom == DOUBLE), rem, 10**6)
                    jd = cand.argmin(axis=1)
                    rows = np.where(dbl)[0]
                    r_ = rem[rows, jd[rows]]
                    rem[rows, jd[rows]] = np.where(r_ > MINOR, r_ - (r_ - MINOR), 0)  # first half ends -> 120 left; second half ends -> 0
        any_goal = goals["h"][0] | goals["a"][0]
        pulled["h"] &= ~any_goal
        pulled["a"] &= ~any_goal
        if in_ot:
            won = live & any_goal
            decided[won] = 1
            live &= ~any_goal
        # PP-creating penalties (not during a sim that is already decided)
        for t, o in (("h", "a"), ("a", "h")):
            me, opp = mult[t][0], mult[t][1]
            p = inp.pp_pen_per_sec * me.pen_taken * opp.pen_drawn
            ev_ = live & (rng.random(N) < p)
            if ev_.any():
                u = rng.random(N)
                nom = np.where(u < shares[0], MINOR, np.where(u < shares[1], DOUBLE, MAJOR)).astype(np.int32)
                free = pen_rem[t] == 0
                slot = free.argmax(axis=1)
                ok = ev_ & free.any(axis=1)
                rows = np.where(ok)[0]
                pen_rem[t][rows, slot[rows]] = nom[rows]
                pen_nom[t][rows, slot[rows]] = nom[rows]
                out[f"pp_opps_{o}"] += ok
        for t in ("h", "a"):
            pen_rem[t] = np.maximum(pen_rem[t] - 1, 0)
        # pulled goalie: last 300 s of the 3rd period, trailing, goalie in, not on a PP, opponent's goalie in
        if (not in_ot) and period == 3 and sec >= REG_SECONDS - PULL_WINDOW:
            rem_s = REG_SECONDS - sec - 1
            b = (rem_s // PULL_BIN) * PULL_BIN
            for t, o in (("h", "a"), ("a", "h")):
                behind = np.clip(score[o] - score[t], 0, 3)
                can = live & ~pulled[t] & ~pulled[o] & (behind >= 1) & (sk[t] <= sk[o])
                if can.any():
                    hz = np.zeros(N)
                    for k in (1, 2, 3):
                        hz[behind == k] = inp.pull_hazard.get((k, b), 0.0)
                    pulled[t] |= can & (rng.random(N) < hz)
    if not reg:                                          # started in OT
        reg = {"h": score["h"].copy() - 0, "a": score["a"].copy() - 0}
        live = score["h"] == score["a"]
    # shootout
    so = (score["h"] == score["a"])
    if so.any():
        idx = np.where(so)[0]
        n = len(idx)
        hs = (rng.random((n, SO_ROUNDS)) < inp.so_conversion).sum(axis=1)
        as_ = (rng.random((n, SO_ROUNDS)) < inp.so_conversion).sum(axis=1)
        tied = hs == as_
        for _ in range(SO_MAX_EXTRA):
            if not tied.any():
                break
            h1 = rng.random(n) < inp.so_conversion
            a1 = rng.random(n) < inp.so_conversion
            hs = hs + (tied & h1)
            as_ = as_ + (tied & a1)
            tied = tied & (h1 == a1)
        coin = rng.random(n) < 0.5
        home_wins = (hs > as_) | (tied & coin)
        score["h"][idx[home_wins]] += 1
        score["a"][idx[~home_wins]] += 1
        decided[idx] = 2
    names = {"REG": 0, "OT": 1, "SO": 2}
    res = {"home_score": score["h"], "away_score": score["a"],
           "reg_home_score": reg["h"], "reg_away_score": reg["a"],
           "decided": np.array(["REG", "OT", "SO"])[decided]}
    for k in ("pp_goals", "en_goals", "attempts", "pp_opps", "pp_seconds"):
        res[f"home_{k}"] = out[f"{k}_h"]
        res[f"away_{k}"] = out[f"{k}_a"]
    return res
