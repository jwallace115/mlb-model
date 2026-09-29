#!/usr/bin/env python3
"""
NHL game simulation engine. Vectorised over N sims (numpy), 1-second clock steps.

Supports start_state for mid-game entry (situation hunter: live pulled-goalie / PP markets).
No literal rates: everything comes from GameInputs built from constants.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
C2_PATH = ROOT / "nhl" / "data" / "sim" / "constants_v2.json"
C5_PATH = ROOT / "nhl" / "data" / "sim" / "constants_v5.json"
C6_PATH = ROOT / "nhl" / "data" / "sim" / "constants_v6.json"

REG_SECONDS = 3600  # 3 x 20 min
OT_SECONDS = 300    # 5 min OT
PERIOD_SECONDS = 1200


@dataclass
class GameInputs:
    """Every rate the engine uses. No literal rates in the engine."""
    # 5v5 per-team per second
    ev_att_rate: float       # attempts per second per team at 5v5
    ev_goal_prob: float      # goals per attempt at 5v5
    # PP/PK rates
    pp_att_rate: float       # advantaged-side attempts per second
    pp_goal_prob: float      # advantaged-side goals per attempt
    sh_att_rate: float       # disadvantaged-side attempts per second
    sh_goal_prob: float      # disadvantaged-side goals per attempt
    # 4v4, 3v3
    ev44_att_rate: float
    ev44_goal_prob: float
    ev33_att_rate: float
    ev33_goal_prob: float
    # Empty net / extra attacker (6v5)
    en_att_rate: float       # advantaged side (6 skaters)
    en_goal_prob: float
    en_against_att_rate: float  # disadvantaged side (shooting at empty net)
    en_against_goal_prob: float
    # Penalties
    penalty_rate_per_sec: float   # per team per second
    minor_share: float
    double_minor_share: float
    major_share: float
    # Score effects (dict: (sd, period) -> (att_mult, xg_mult))
    score_effects: dict = field(default_factory=dict)
    # Home effects
    home_att_mult: float = 1.0
    home_xg_mult: float = 1.0
    # Pull hazard (dict: (sd, bin) -> hazard_per_sec)
    pull_hazard: dict = field(default_factory=dict)
    # OT
    ot_att_rate: float = 0.0
    ot_goal_prob: float = 0.0
    # Shootout
    so_conversion: float = 0.33
    so_past_r3_share: float = 0.30


def league_average_inputs():
    """Build GameInputs from constants v5/v6/v2."""
    with open(C5_PATH) as f:
        c5 = json.load(f)["constants"]
    with open(C6_PATH) as f:
        c6 = json.load(f)["constants"]
    with open(C2_PATH) as f:
        c2 = json.load(f)["constants"]

    # Score effects
    se = {}
    for sd in range(-3, 4):
        for p in range(1, 4):
            ka = f"score_effect_attempt_mult_sd{sd}_p{p}"
            kx = f"score_effect_xg_mult_sd{sd}_p{p}"
            se[(sd, p)] = (c2.get(ka, {}).get("value", 1.0), c2.get(kx, {}).get("value", 1.0))

    # Pull hazard
    ph = {}
    hazard_data = c6.get("pull_hazard_per_second", {}).get("data", {})
    for sd_str, bins in hazard_data.items():
        for bin_str, v in bins.items():
            ph[(int(sd_str), int(bin_str))] = v["hazard_per_sec"]

    return GameInputs(
        ev_att_rate=c5["attempt_rate_per_60_per_team_5v5"]["value"] / 3600,
        ev_goal_prob=c5["goals_per_attempt_5v5"]["value"],
        pp_att_rate=c5.get("attempt_rate_per_60_advantaged_5v4", {}).get("value", 70) / 3600,
        pp_goal_prob=c5.get("goals_per_attempt_advantaged_5v4", {}).get("value", 0.10),
        sh_att_rate=c5.get("attempt_rate_per_60_disadvantaged_5v4", {}).get("value", 12) / 3600,
        sh_goal_prob=c5.get("goals_per_attempt_disadvantaged_5v4", {}).get("value", 0.07),
        ev44_att_rate=c5["attempt_rate_per_60_per_team_4v4"]["value"] / 3600,
        ev44_goal_prob=c5["goals_per_attempt_4v4"]["value"],
        ev33_att_rate=c5["attempt_rate_per_60_per_team_3v3"]["value"] / 3600,
        ev33_goal_prob=c5["goals_per_attempt_3v3"]["value"],
        en_att_rate=c5.get("attempt_rate_per_60_advantaged_6v5", {}).get("value", 100) / 3600,
        en_goal_prob=c5.get("goals_per_attempt_advantaged_6v5", {}).get("value", 0.22),
        en_against_att_rate=c5.get("attempt_rate_per_60_disadvantaged_6v5", {}).get("value", 40) / 3600,
        en_against_goal_prob=c5.get("goals_per_attempt_disadvantaged_6v5", {}).get("value", 0.63),
        penalty_rate_per_sec=c2.get("penalties_per_team_per_game", {}).get("value", 3.8) / 3600,
        minor_share=c2.get("penalty_shares", {}).get("minor_2min", 0.85),
        double_minor_share=c2.get("penalty_shares", {}).get("double_minor_4min", 0.05),
        major_share=c2.get("penalty_shares", {}).get("major_5min", 0.10),
        score_effects=se,
        home_att_mult=c2.get("home_attempt_share", {}).get("value", 0.514) / 0.5,
        home_xg_mult=c2.get("home_xg_per_attempt_mult", {}).get("value", 1.01),
        pull_hazard=ph,
        ot_att_rate=c5["attempt_rate_per_60_per_team_3v3"]["value"] / 3600,
        ot_goal_prob=c5["goals_per_attempt_3v3"]["value"],
        so_conversion=c2.get("shootout_conversion", {}).get("value", 0.33),
        so_past_r3_share=c2.get("shootout_past_r3_share", {}).get("value", 0.30),
    )


@dataclass
class StartState:
    """Optional mid-game start state."""
    period: int = 1
    second: int = 0
    home_score: int = 0
    away_score: int = 0
    home_penalties: list = field(default_factory=list)  # list of remaining seconds per penalty
    away_penalties: list = field(default_factory=list)
    home_pulled: bool = False
    away_pulled: bool = False


def simulate(inputs: GameInputs, n_sims: int, seed: int, start_state: Optional[StartState] = None):
    """Simulate n_sims games. Returns dict of arrays."""
    rng = np.random.RandomState(seed)
    N = n_sims
    inp = inputs

    # State arrays
    home_score = np.zeros(N, dtype=np.int32)
    away_score = np.zeros(N, dtype=np.int32)
    home_pp_goals = np.zeros(N, dtype=np.int32)
    away_pp_goals = np.zeros(N, dtype=np.int32)
    home_en_goals = np.zeros(N, dtype=np.int32)
    away_en_goals = np.zeros(N, dtype=np.int32)
    home_attempts = np.zeros(N, dtype=np.int32)
    away_attempts = np.zeros(N, dtype=np.int32)
    home_pp_opps = np.zeros(N, dtype=np.int32)
    away_pp_opps = np.zeros(N, dtype=np.int32)
    decided = np.full(N, 0, dtype=np.int8)  # 0=REG, 1=OT, 2=SO
    home_pulled = np.zeros(N, dtype=bool)
    pull_time = np.zeros(N, dtype=np.float32)

    # Penalty clocks: max 4 concurrent penalties per team
    MAX_PEN = 4
    home_pen = np.zeros((N, MAX_PEN), dtype=np.int32)  # seconds remaining per penalty slot
    away_pen = np.zeros((N, MAX_PEN), dtype=np.int32)

    if start_state is not None:
        ss = start_state
        home_score[:] = ss.home_score
        away_score[:] = ss.away_score
        home_pulled[:] = ss.home_pulled
        for i, p in enumerate(ss.home_penalties[:MAX_PEN]):
            home_pen[:, i] = p
        for i, p in enumerate(ss.away_penalties[:MAX_PEN]):
            away_pen[:, i] = p
        start_sec = (ss.period - 1) * PERIOD_SECONDS + ss.second
    else:
        start_sec = 0

    reg_home = np.zeros(N, dtype=np.int32)
    reg_away = np.zeros(N, dtype=np.int32)

    # --- REGULATION (3 periods) ---
    for sec in range(start_sec, REG_SECONDS):
        period = sec // PERIOD_SECONDS + 1
        sec_in_period = sec % PERIOD_SECONDS

        # Strength state: count active penalties
        home_active = (home_pen > 0).sum(axis=1)  # N array
        away_active = (away_pen > 0).sum(axis=1)
        home_sk = np.clip(5 - home_active, 3, 5)
        away_sk = np.clip(5 - away_active, 3, 5)

        # Extra attacker if pulled
        home_sk_eff = np.where(home_pulled, home_sk + 1, home_sk)
        away_sk_eff = away_sk  # only home can pull for now (trailing)

        sd = home_score - away_score  # from home view

        # Determine rates based on strength
        is_5v5 = (home_sk == 5) & (away_sk == 5) & ~home_pulled
        is_pp_home = (home_sk > away_sk) & ~home_pulled  # home has more skaters
        is_pp_away = (away_sk > home_sk) & ~home_pulled
        is_4v4 = (home_sk == 4) & (away_sk == 4)
        is_en = home_pulled

        # Base attempt rates per second (per team)
        home_att = np.where(is_5v5, inp.ev_att_rate,
                   np.where(is_pp_home, inp.pp_att_rate,
                   np.where(is_pp_away, inp.sh_att_rate,
                   np.where(is_4v4, inp.ev44_att_rate,
                   np.where(is_en, inp.en_att_rate,
                   inp.ev_att_rate)))))

        away_att = np.where(is_5v5, inp.ev_att_rate,
                   np.where(is_pp_away, inp.pp_att_rate,
                   np.where(is_pp_home, inp.sh_att_rate,
                   np.where(is_4v4, inp.ev44_att_rate,
                   np.where(is_en, inp.en_against_att_rate,
                   inp.ev_att_rate)))))

        # Goal probability
        home_gp = np.where(is_5v5, inp.ev_goal_prob,
                  np.where(is_pp_home, inp.pp_goal_prob,
                  np.where(is_pp_away, inp.sh_goal_prob,
                  np.where(is_4v4, inp.ev44_goal_prob,
                  np.where(is_en, inp.en_goal_prob,
                  inp.ev_goal_prob)))))

        away_gp = np.where(is_5v5, inp.ev_goal_prob,
                  np.where(is_pp_away, inp.pp_goal_prob,
                  np.where(is_pp_home, inp.sh_goal_prob,
                  np.where(is_4v4, inp.ev44_goal_prob,
                  np.where(is_en, inp.en_against_goal_prob,
                  inp.ev_goal_prob)))))

        # Score effects (5v5 only)
        sd_clipped = np.clip(sd, -3, 3)
        for s in range(-3, 4):
            for p in range(1, 4):
                if p != period:
                    continue
                mask_s = (sd_clipped == s) & is_5v5
                if mask_s.any():
                    am, xm = inp.score_effects.get((s, p), (1.0, 1.0))
                    home_att = np.where(mask_s, home_att * am, home_att)
                    home_gp = np.where(mask_s, home_gp * xm, home_gp)
                    # Away gets the mirror
                    am_a, xm_a = inp.score_effects.get((-s, p), (1.0, 1.0))
                    away_att = np.where(mask_s, away_att * am_a, away_att)
                    away_gp = np.where(mask_s, away_gp * xm_a, away_gp)

        # Home effect
        home_att = home_att * inp.home_att_mult
        home_gp = home_gp * inp.home_xg_mult
        away_att = away_att * (2 - inp.home_att_mult)
        away_gp = away_gp * (1 / inp.home_xg_mult)

        # Attempt + goal events
        h_shot = rng.random(N) < home_att
        a_shot = rng.random(N) < away_att
        h_goal = h_shot & (rng.random(N) < home_gp)
        a_goal = a_shot & (rng.random(N) < away_gp)

        home_score += h_goal.astype(np.int32)
        away_score += a_goal.astype(np.int32)
        home_attempts += h_shot.astype(np.int32)
        away_attempts += a_shot.astype(np.int32)

        # PP goals
        home_pp_goals += (h_goal & is_pp_home).astype(np.int32)
        away_pp_goals += (a_goal & is_pp_away).astype(np.int32)

        # EN goals
        home_en_goals += (h_goal & is_en).astype(np.int32)
        away_en_goals += (a_goal & is_en & (away_gp > 0.5)).astype(np.int32)  # empty-net goals by away

        # PP goal ends a minor
        for pen_arr, opp_goal, is_pp in [(home_pen, a_goal, is_pp_away), (away_pen, h_goal, is_pp_home)]:
            end_mask = opp_goal & is_pp
            if end_mask.any():
                for slot in range(MAX_PEN):
                    can_end = end_mask & (pen_arr[:, slot] > 0) & (pen_arr[:, slot] <= 120)
                    pen_arr[:, slot] = np.where(can_end, 0, pen_arr[:, slot])
                    end_mask = end_mask & ~can_end

        # Penalties
        h_pen = rng.random(N) < inp.penalty_rate_per_sec
        a_pen = rng.random(N) < inp.penalty_rate_per_sec
        for pen_event, pen_arr, opp_pp_opps in [(h_pen, home_pen, away_pp_opps), (a_pen, away_pen, home_pp_opps)]:
            if pen_event.any():
                # Draw type
                pen_type = rng.random(pen_event.sum())
                dur = np.where(pen_type < inp.minor_share, 120,
                      np.where(pen_type < inp.minor_share + inp.double_minor_share, 240, 300))
                # Find first empty slot
                for slot in range(MAX_PEN):
                    can_add = pen_event & (pen_arr[:, slot] == 0)
                    if can_add.any():
                        idx = np.where(can_add)[0]
                        n_add = min(len(idx), len(dur))
                        pen_arr[idx[:n_add], slot] = dur[:n_add]
                        dur = dur[n_add:]
                        opp_pp_opps[idx[:n_add]] += 1
                        pen_event[idx[:n_add]] = False
                        if len(dur) == 0:
                            break

        # Tick penalty clocks
        home_pen = np.maximum(home_pen - 1, 0)
        away_pen = np.maximum(away_pen - 1, 0)

        # Pulled goalie (home team only, trailing, 3rd period, last 5 min)
        if period == 3 and sec_in_period >= 900:
            sec_remaining = PERIOD_SECONDS - sec_in_period
            can_pull = ~home_pulled & (sd < 0) & (home_active == 0)
            sd_for_pull = np.clip(sd, -3, -1)
            for s in [-1, -2, -3]:
                b = (sec_remaining // 30) * 30
                h = inp.pull_hazard.get((s, min(b, 270)), 0.0)
                pull_now = can_pull & (sd_for_pull == s) & (rng.random(N) < h)
                home_pulled = home_pulled | pull_now

        # Goalie back after goal or end of period
        home_pulled = home_pulled & (sd < 0)  # goalie comes back if scored
        pull_time += home_pulled.astype(np.float32)

    reg_home[:] = home_score
    reg_away[:] = away_score
    tied = home_score == away_score

    # --- OVERTIME (5 min, 3v3, sudden death) ---
    ot_mask = tied.copy()
    for sec in range(OT_SECONDS):
        if not ot_mask.any():
            break
        h_shot = ot_mask & (rng.random(N) < inp.ot_att_rate)
        a_shot = ot_mask & (rng.random(N) < inp.ot_att_rate)
        h_goal = h_shot & (rng.random(N) < inp.ot_goal_prob)
        a_goal = a_shot & (rng.random(N) < inp.ot_goal_prob)

        # Sudden death: only first goal counts
        both = h_goal & a_goal
        # If both score in same second, home wins (arbitrary tiebreak)
        a_goal = a_goal & ~both

        home_score += (h_goal & ot_mask).astype(np.int32)
        away_score += (a_goal & ot_mask).astype(np.int32)
        home_attempts += (h_shot & ot_mask).astype(np.int32)
        away_attempts += (a_shot & ot_mask).astype(np.int32)

        # Game over for sims where a goal was scored
        scored = (h_goal | a_goal) & ot_mask
        decided[scored] = 1  # OT
        ot_mask = ot_mask & ~scored

    # --- SHOOTOUT (remaining tied games) ---
    so_mask = ot_mask.copy()
    if so_mask.any():
        # 3 rounds, then sudden death
        h_so = np.zeros(N, dtype=np.int32)
        a_so = np.zeros(N, dtype=np.int32)
        for rd in range(10):  # max 10 rounds (3 regular + 7 sudden death)
            if not so_mask.any():
                break
            h_conv = so_mask & (rng.random(N) < inp.so_conversion)
            a_conv = so_mask & (rng.random(N) < inp.so_conversion)
            h_so += h_conv.astype(np.int32)
            a_so += a_conv.astype(np.int32)

            if rd >= 2:  # After round 3, sudden death
                h_ahead = so_mask & (h_so > a_so)
                a_ahead = so_mask & (a_so > h_so)
                decided[h_ahead] = 2
                home_score[h_ahead] += 1
                so_mask = so_mask & ~h_ahead
                decided[a_ahead] = 2
                away_score[a_ahead] += 1
                so_mask = so_mask & ~a_ahead

        # Any remaining: random winner
        if so_mask.any():
            h_wins = so_mask & (rng.random(N) < 0.5)
            decided[h_wins] = 2
            home_score[h_wins] += 1
            decided[so_mask & ~h_wins] = 2
            away_score[so_mask & ~h_wins] += 1

    decided_str = np.where(decided == 0, "REG", np.where(decided == 1, "OT", "SO"))

    return {
        "home_score": home_score,
        "away_score": away_score,
        "reg_home_score": reg_home,
        "reg_away_score": reg_away,
        "decided": decided_str,
        "home_pp_goals": home_pp_goals,
        "away_pp_goals": away_pp_goals,
        "home_pp_opps": home_pp_opps,
        "away_pp_opps": away_pp_opps,
        "home_en_goals": home_en_goals,
        "away_en_goals": away_en_goals,
        "home_attempts": home_attempts,
        "away_attempts": away_attempts,
        "pull_time": pull_time,
    }
