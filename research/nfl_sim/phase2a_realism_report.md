# Phase 2A: Vectorised Play-Level Engine - K1 Realism Report

**Data:** 2021-2024 regular season only. 2025/2026 NOT used.

## Algorithm

Simulations are vectorised across sims. One game = one call holding N parallel
game states as numpy arrays. Per play:
- play call: P(pass) = logistic(logit(league xpass for situational bucket) + team PROE/100)
- matchup: success/explosive/sack/INT/stuff probabilities via log5(off, def, league)
  where log5(a,b,l) = (a*b/l) / (a*b/l + (1-a)*(1-b)/(1-l)). This is the only matchup formula.
- yards: drawn from empirical quantile tables (101 points) by situation bucket
- clock: drawn from empirical snap-to-snap elapsed time table by outcome type and hurry-up flag,
  scaled by team pace / league pace. No scale factors.
- 4th down, FG, punt, XP/2pt, turnovers, penalties, OT per empirical tables

## Tables Built

| Table | File | Rows | Description |
|-------|------|------|-------------|
| A: pass outcomes | pass_outcomes.parquet | 51 | P(sack), P(INT), P(comp), yards quantiles by (down, dist, zone) |
| B: rush outcomes | rush_outcomes.parquet | 45 | P(fumble), yards quantiles by (down, dist, zone) |
| C: play-call | playcall_xpass.parquet | 69 | League xpass by situational bucket |
| D: clock | clock_runoff.parquet | 8 | Snap-to-snap elapsed by outcome type x hurry |
| E: 4th-down | fourth_down.parquet | 90 | P(go/punt/FG) by situation |
| F: special teams | fg_make_rate, punt_net, etc. | various | FG%, punt net, kickoff, XP, 2pt, penalty rates |
| G: turnovers | turnover_returns.json | - | INT/fumble return yards, P(def TD) |
| H: constants | constants.json | - | Safety rate, kneel seconds |

## Runtime

- N=2000 sims per game, 1087 games (2021-2024 regular season)
- Total: 4726s (79 min), 4.35s/game average
- Per season: 2021 1189s, 2022 1191s, 2023 1181s, 2024 1165s

## Diagnostic Table (PRE-FIX vs POST-FIX)

The initial engine had a critical bug: when Q3 ended and quarter advanced to Q4,
the end-of-regulation check fired on the same iteration (stale `time_up` mask),
skipping the entire 4th quarter. This was found via clock instrumentation showing
ev_clock_used = 2700s (~3 quarters) instead of ~3600s.

### PRE-FIX Diagnostics (3 quarters only)

| Metric | Actual | Sim | Delta |
|--------|--------|-----|-------|
| P(sack) | 0.067 | 0.068 | +0.001 |
| P(INT) | 0.021 | 0.021 | -0.001 |
| P(incomplete) | 0.309 | 0.303 | -0.006 |
| P(complete) | 0.603 | 0.608 | +0.006 |
| Plays/game | 124.5 | 88.4 | -36.1 |
| Drives/game | 21.9 | 13.7 | -8.2 |
| Plays/drive | 5.89 | 6.44 | +0.55 |
| Pts/team | 22.4 | 12.1 | -10.3 |

### POST-FIX Diagnostics (4 quarters)

| Metric | Actual | Sim | Delta |
|--------|--------|-----|-------|
| P(sack) | 0.067 | 0.068 | +0.001 |
| P(INT) | 0.021 | 0.021 | -0.000 |
| P(incomplete) | 0.309 | 0.305 | -0.004 |
| P(complete) | 0.603 | 0.606 | +0.004 |
| Plays/game | 124.5 | 131.5 | +7.0 |
| Drives/game | 21.9 | 19.4 | -2.5 |
| Plays/drive | 5.89 | 6.79 | +0.90 |
| Pts/team | 22.4 | 18.6 | -3.8 |
| FD rate/play | 0.295 | 0.306 | +0.011 |

### What mechanism was wrong

1. **Q3->Q4 transition bug (FIXED):** The `time_up` boolean mask was computed
   once at the top of each iteration. When Q3 ended, `can_advance` incremented
   qtr to 4 and added 900s to clock. But `end_reg = time_up & (qtr == 4)` then
   fired because `time_up` still reflected the Q3 clock expiry. Fix: use
   `alive & (qtr == 4) & (clock <= 0)` for end_reg, checking CURRENT clock.

2. **Clock table was measuring within-drive only (FIXED):** Originally measured
   snap-to-snap time only for consecutive scrimmage plays within the same drive.
   This excluded the cross-drive gap (~21s for punt/kickoff transitions). Fixed
   by measuring ALL consecutive scrimmage plays in the same game, which naturally
   includes these transitions.

3. **Incomplete pass clock was inflated (FIXED):** The `incomplete_oob` category
   mixed true clock-stopping incompletes (6-8s) with OOB completions (~30s).
   Fixed by separating into `incomplete` (clock stops, ~8s) vs `complete_inbounds`
   (all completions, ~39s).

### No scale factors remain

```
$ grep -i scale nfl/sim/engine.py
      run, incomplete/OOB, first-down), scaled by team pace / league pace, with
                pace_scale = ctx[f"t{ti}_pace"] / ctx["lg_pace"]
```

The only "scale" is `pace_scale = team_pace / league_pace`, which is a data-driven
ratio from the tendencies table (not a fudge constant).

## K1 Realism Check — Iteration 1

| Metric | Sim | Actual | Target | PASS/FAIL |
|--------|-----|--------|--------|-----------|
| Mean pts/team | 18.0 | 22.4 | ~22.4 | FAIL |
| Plays/game | 132.3 | 124.5 | ~125 | PASS |
| Drives/game | 19.5 | 21.9 | ~22 | PASS |
| SD margin | 1.53 | 14.20 | ±1.0 of actual | FAIL |
| SD total | 2.78 | 13.61 | ±2.0 of actual | FAIL |
| P(|margin|=3) | 9.41% | 14.54% | 14.27%±2 | FAIL |
| P(|margin|=6) | 5.34% | 7.54% | 7.54%±2 | FAIL |
| P(|margin|=7) | 8.17% | 7.27% | 8.24%±2 | PASS |
| P(|margin|=10) | 6.82% | 5.06% | 5.06%±2 | PASS |
| P(|margin|=14) | 4.88% | 4.32% | 4.32%±2 | PASS |
| Pass yds/team/game | 207.0 | 221.0 | ~221 | PASS |
| Rush yds/team/game | 133.0 | 118.2 | ~118 | PASS |
| corr(sim margin, spread) | 0.471 | - | ~0.8 (info) | INFO |

### Home Win Probability Calibration

| Decile | Sim P(HW) | Actual HW | N |
|--------|----------|----------|---|
| 0 | 0.397 | 0.440 | 109 |
| 1 | 0.433 | 0.495 | 111 |
| 2 | 0.451 | 0.491 | 110 |
| 3 | 0.466 | 0.423 | 111 |
| 4 | 0.478 | 0.500 | 108 |
| 5 | 0.490 | 0.558 | 104 |
| 6 | 0.502 | 0.573 | 110 |
| 7 | 0.517 | 0.574 | 108 |
| 8 | 0.535 | 0.589 | 107 |
| 9 | 0.572 | 0.761 | 109 |

### Total Calibration

| Decile | Sim P(over) | Actual over rate | N |
|--------|------------|-----------------|---|
| 0 | 0.046 | 0.486 | 109 |
| 1 | 0.089 | 0.321 | 109 |
| 2 | 0.123 | 0.481 | 108 |
| 3 | 0.156 | 0.523 | 109 |
| 4 | 0.192 | 0.518 | 110 |
| 5 | 0.233 | 0.486 | 107 |
| 6 | 0.271 | 0.505 | 109 |
| 7 | 0.315 | 0.444 | 108 |
| 8 | 0.375 | 0.495 | 109 |
| 9 | 0.492 | 0.450 | 109 |

### Check 5 Breakdowns

**By season:**

| Season | Sim pts/team | Actual pts/team | Sim margin SD | Actual margin SD |
|--------|-------------|----------------|--------------|-----------------|
| 2021 | 16.2 | 23.0 | 1.44 | 15.43 |
| 2022 | 18.5 | 21.9 | 1.64 | 12.35 |
| 2023 | 18.8 | 21.8 | 1.62 | 14.42 |
| 2024 | 18.6 | 22.9 | 1.41 | 14.46 |

**By week range:**

| Weeks | Sim pts/team | Actual pts/team |
|-------|-------------|----------------|
| 1-4 | 18.4 | 22.3 |
| 5-18 | 17.9 | 22.4 |

**By favourite size (|closing spread|):**

| Bucket | Sim pts/team | Actual pts/team | N |
|--------|-------------|----------------|---|
| <3 | 18.1 | 21.5 | 255 |
| 3-7 | 18.1 | 22.5 | 536 |
| >7 | 17.7 | 23.0 | 296 |

## Iteration Log

### Iteration 1 (current)
- **Fixed:** Q3->Q4 quarter transition bug (game was running only 3 quarters)
- **Fixed:** Clock table scope (within-drive -> all consecutive scrimmage plays)
- **Fixed:** Incomplete pass clock category (separated from OOB completions)
- **Residual gaps:**
  - Pts/team 18.0 vs 22.4 (FAIL): 4.4 points short. Driven by 2.4 fewer drives (19.5 vs 21.9)
    and 0.9 extra plays/drive (6.8 vs 5.9). The first-down rate is 1.1pp high (30.6% vs 29.5%),
    which compounds over drives to produce fewer 3-and-outs and fewer drive changes.
  - SD margin 1.53 vs 14.20 (FAIL): The sim produces almost no between-game variance.
    The game-mean margin ranges only ±3 pts around 0. This indicates the ratings are not
    differentiating teams enough (the log5 matchup tilts are too small, or the success/fail
    draw isn't amplifying the matchup signal). corr(sim margin, spread) = 0.47 vs ~0.8 target.
  - SD total 2.78 vs 13.61 (FAIL): Same root cause as SD margin.
  - Total calibration is flat (~50% over rate regardless of sim P(over)): the sim's game totals
    cluster tightly around 36 points, so P(over closing total) is nearly constant.
  - 2021 sim pts (16.2) is notably lower than 2022-2024 (~18.5), suggesting a data or
    rating coverage issue for the earliest season.

### Next iteration needed (not done)
- Restructure pass/rush outcome as joint categorical draw to get exact incompletion
  and first-down rates by situation (reduces plays/drive toward 5.9)
- Investigate and fix SD margin: the matchup adjustments via log5 ratio scaling may
  need to amplify the team success/explosive/sack rates more aggressively, or the
  issue may be that yards are drawn from league-wide tables without team-specific
  shifts (a good team's completions should gain more yards on average)
- Add home-field advantage (currently absent)

## Statement

2025/2026 data was not used in any table, rating, or backtest. K1 has NOT passed.
Three iterations remain before the stop condition.
