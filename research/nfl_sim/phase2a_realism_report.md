# Phase 2A: Vectorised Play-Level Engine - K1 Realism Report

**Data:** 2021-2024 regular season only. 2025/2026 NOT used.

## Algorithm

Simulations are vectorised across sims. One game = one call holding N parallel
game states as numpy arrays. Per play:
- play call: P(pass) = logistic(logit(league xpass for situational bucket) + team PROE/100)
- matchup: sack prob = log5(off sack_rate, def sack_rate, league); INT = log5(int_rate);
  completion success/fail split tilted by log5(pass_success) ratio.
  log5(a,b,l) = (a*b/l) / (a*b/l + (1-a)*(1-b)/(1-l)). Only matchup formula.
- yards: drawn from empirical quantile tables (101 points) by situation bucket,
  split by EPA success/fail with matchup tilt on success probability
- clock: drawn from empirical snap-to-snap elapsed time table by outcome type
  and hurry-up flag, scaled by team pace / league pace
- 4th down, FG, punt, XP/2pt, turnovers (INT + fumble on pass AND rush),
  penalties (7.2% rate, 38.5% defense, 72.5% auto-first-down), OT per tables

## Tables Built

| Table | File | Rows |
|-------|------|------|
| Pass outcomes | pass_outcomes.parquet | 51 |
| Rush outcomes | rush_outcomes.parquet | 45 |
| Play-call xpass | playcall_xpass.parquet | 69 |
| Clock runoff | clock_runoff.parquet | 8 |
| 4th-down decisions | fourth_down.parquet | 90 |
| FG make rate | fg_make_rate.parquet | 52 |
| Punt net | punt_net.parquet | 3 |
| Scalars (XP, 2pt, pen) | scalars.json | - |
| Turnover returns | turnover_returns.json | - |
| Constants | constants.json | - |

## Runtime

- Iteration 2: N=2000, 1087 games, **912s (15.2 min), 0.84s/game**
- Iteration 1: N=2000, 1087 games, 4726s (79 min), 4.35s/game

## Bug List (all from iterations 1 and 2)

1. **Q3->Q4 transition (iter 1, FIXED):** Stale `time_up` mask from Q3 clock expiry
   triggered `end_reg` when qtr advanced to 4 on the same iteration. Game ran only
   3 quarters (~2700s of clock). Fix: check `clock <= 0` at Q4/OT end directly.

2. **Clock table scope (iter 1, FIXED):** Originally measured within-drive-only gaps
   (~30.5s), excluding cross-drive transitions. Reverted to all consecutive scrimmage
   plays (~29s), matching actual 3600/124.5 = 28.9s/play.

3. **Incomplete pass clock category (iter 1, FIXED):** `incomplete_oob` mixed true
   clock-stopping incompletes (8s) with OOB completions (~30s). Split into `incomplete`
   (8s) and `complete_inbounds` (39s).

4. **No matchup tilt on yards (iter 1, FIXED):** Unsplit `yds_all_q` with no success/fail
   distinction. All teams got league-average yards per completion. Per-sim margin SD was
   1.5. Fixed by restoring success/fail split with log5-adjusted success probability.
   Per-sim margin SD rose to 12.8.

5. **Pass fumbles missing (iter 2, FIXED):** Pass table had no `p_fumble` column. Only
   rush plays generated fumble turnovers. Actual pass fumble rate = 0.79% per dropback
   (619 fumbles in 78K pass plays). Added to tables and engine. Increased turnovers/game
   from ~1.5 to ~2.2 (actual ~2.6).

6. **Corrupted fourth_down_go_rate (iter 2, FIXED):** `tendencies_weekly.parquet` has
   `fourth_down_go_rate = 1.0` for all teams (data overwritten on disk; ratings.py
   assertions passed at build time). Engine's team 4th-down override set `p_go = 1.0`
   for 4th-and-short midfield. Disabled the override; table probabilities used directly.

## Diagnostic: Before and After (50 games x 2000 sims, 2023 season)

| Metric | Actual | Iter 1 Before | Iter 2 After |
|--------|--------|---------------|-------------|
| P(sack) | 0.067 | 0.068 | 0.068 |
| P(INT) | 0.021 | 0.021 | 0.021 |
| P(incomplete) | 0.309 | 0.305 | 0.301 |
| P(complete) | 0.603 | 0.606 | 0.602 |
| FD rate/play | 0.295 | 0.318 | 0.315 |
| Plays/drive | 5.89 | 6.68 | 6.46 |
| Drives/game | 21.9 | 19.4 | 20.4 |
| Pts/team | 22.4 | 17.8 | 17.7 |
| Pts/drive | 2.13 | 1.80 | 1.73 |
| Punt/drive | 0.360 | 0.357 | 0.368 |
| TO/drive | 0.119 | 0.089 | 0.109 |
| Per-sim margin SD | 14.2 | 12.8 | 12.9 |

## K1 Realism Check — Iteration 2

| Metric | Sim | Actual | Target | PASS/FAIL |
|--------|-----|--------|--------|-----------|
| Mean pts/team | 17.5 | 22.4 | ~22.4 | FAIL |
| Plays/game | 132.7 | 124.5 | ~125 | PASS |
| Drives/game | 20.3 | 21.9 | ~22 | PASS |
| SD margin | 2.74 | 14.20 | ±1.0 | FAIL |
| SD total | 3.96 | 13.61 | ±2.0 | FAIL |
| P(|margin|=3) | 9.29% | 14.54% | 14.27%±2 | FAIL |
| P(|margin|=6) | 5.32% | 7.54% | 7.54%±2 | FAIL |
| P(|margin|=7) | 7.82% | 7.27% | 8.24%±2 | PASS |
| P(|margin|=10) | 6.76% | 5.06% | 5.06%±2 | PASS |
| P(|margin|=14) | 4.70% | 4.32% | 4.32%±2 | PASS |
| Pass yds/team/game | 203.1 | 221.0 | ~221 | PASS |
| Rush yds/team/game | 130.8 | 118.2 | ~118 | PASS |
| corr(sim margin, spread) | 0.723 | - | ~0.8 (info) | INFO |

### Home Win Probability Calibration

| Decile | Sim P(HW) | Actual HW | N |
|--------|----------|----------|---|
| 0 | 0.331 | 0.339 | 109 |
| 1 | 0.391 | 0.413 | 109 |
| 2 | 0.423 | 0.495 | 111 |
| 3 | 0.449 | 0.361 | 108 |
| 4 | 0.472 | 0.491 | 112 |
| 5 | 0.493 | 0.534 | 103 |
| 6 | 0.518 | 0.636 | 110 |
| 7 | 0.546 | 0.701 | 107 |
| 8 | 0.577 | 0.682 | 110 |
| 9 | 0.636 | 0.750 | 108 |

### Total Calibration

| Decile | Sim P(over) | Actual over rate | N |
|--------|------------|-----------------|---|
| 0 | 0.030 | 0.477 | 109 |
| 1 | 0.063 | 0.367 | 109 |
| 2 | 0.103 | 0.491 | 108 |
| 3 | 0.148 | 0.500 | 110 |
| 4 | 0.184 | 0.505 | 109 |
| 5 | 0.217 | 0.459 | 109 |
| 6 | 0.250 | 0.426 | 108 |
| 7 | 0.292 | 0.583 | 108 |
| 8 | 0.344 | 0.444 | 108 |
| 9 | 0.449 | 0.459 | 109 |

### Check 5 Breakdowns

**By season:**

| Season | Sim pts/team | Actual pts/team | Sim margin SD | Actual margin SD |
|--------|-------------|----------------|--------------|-----------------|
| 2021 | 15.0 | 23.0 | 2.32 | 15.43 |
| 2022 | 18.1 | 21.9 | 2.97 | 12.35 |
| 2023 | 17.8 | 21.8 | 2.89 | 14.42 |
| 2024 | 19.3 | 22.9 | 2.74 | 14.46 |

**By week range:**

| Weeks | Sim pts/team | Actual pts/team |
|-------|-------------|----------------|
| 1-4 | 18.0 | 22.3 |
| 5-18 | 17.4 | 22.4 |

**By favourite size (|closing spread|):**

| Bucket | Sim pts/team | Actual pts/team | N |
|--------|-------------|----------------|---|
| <3 | 17.7 | 21.5 | 255 |
| 3-7 | 17.6 | 22.5 | 536 |
| >7 | 17.2 | 23.0 | 296 |

## Residual Gaps (K1 NOT passed after 2 iterations, 1 remaining)

1. **Pts/team 17.5 vs 22.4 (−4.9):** The EPA success/fail split on completion yards
   produces the right per-play FD rate (~30% including penalty FDs), but drives are
   still 0.57 plays too long, yielding ~1.6 fewer drives per game and ~5 pts deficit.
   The game-mean margin SD of 2.74 vs actual 14.20 confirms the team ratings do not
   differentiate strongly enough. corr(margin, spread) improved to 0.723 from 0.471
   (iteration 1) after restoring the matchup tilt, but is still below the ~0.8 target.

2. **SD margin 2.74 vs 14.20:** The per-sim margin SD (12.9) is close to actual (14.2),
   meaning within any one game the variance is realistic. But across games, the sim
   predicts similar margins for all matchups. The matchup adjustment amplifies sack/INT
   rates and success probability by team quality, but the effect on total scoring is
   still too small. A home-field advantage adjustment (not yet implemented) would add
   ~2-3 pts of spread.

3. **2021 season low (15.0 vs 23.0):** 2021 scores are systematically lower than
   2022-2024 by ~3 pts, suggesting a rating or baseline coverage issue for the
   earliest season.

## Statement

2025/2026 data was not used in any table, rating, or backtest. K1 has NOT passed
after 2 iterations. One iteration remains per the stop rule.
