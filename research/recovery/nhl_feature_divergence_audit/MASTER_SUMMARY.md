# NHL Feature Divergence Audit - Master Summary

## Executive Summary

The live NHL pipeline produces predictions that systematically differ from the
canonical rebuild by -0.107 goals on average (live predicts lower totals).
This divergence does NOT converge as the season progresses - it persists at
roughly the same magnitude from game 1 through game 1258.

Five distinct divergence sources were identified. The most impactful is the
stale live cache issue, but even with perfect cache data, three code-level
bugs produce persistent feature mismatches.

---

## Divergence Sources (Ranked by Impact)

### D1: Stale Live Cache (CRITICAL)
- Severity: HIGH - renders most features useless
- Location: nhl/cache/nhl_live_season.parquet
- Problem: Cache contains only 375 games (through 2025-11-26) with 6 columns
  (game_id, game_date, home_team, away_team, home_score, away_score). Missing all
  extended boxscore fields (home_sog, home_pp_goals, home_pp_opportunities,
  home_goalie_id, home_goalie_sa, home_goalie_ga, etc.).
- Effect: When the pipeline reads this cache, .get(home_sog) returns NaN
  for ALL games. SOG, PP pct, PK pct, goalie SV pct rolling features ALL fall back to
  prior values and never update. Only goals_scored/goals_allowed update from
  actual game data.
- Impact: With stale cache, mean prediction delta = -0.193, correlation
  with actuals drops to 0.000 (from 0.015 canonical).
- Note: The pipeline code correctly detects missing home_sog and forces
  a refresh, but the refresh requires ~1300 API calls. If the pipeline has not
  run since the extended boxscore code was added, or if a previous refresh
  failed, the cache remains stale.

### D2: Prior / Shrinkage Initialization (MODERATE)
- Severity: MODERATE - affects first ~20 games per team, then washes out
- Location:
  - Canonical: nhl_rebuild.py line 207-219 - computes league averages from
    CURRENT season raw data (look-ahead)
  - Live: nhl_daily_pipeline.py line 121-159 - uses mean of 2024 OOS
    FEATURE VALUES (no look-ahead, but different quantity)
- Problem: Canonical priors are league averages of raw game stats for the
  2025-26 season. Live priors are means of computed rolling features from the
  2024 OOS split. These are fundamentally different quantities (raw vs rolling,
  different season).
- Key deltas:
  - goals_scored: canon=3.133, live=3.028 (delta=-0.105)
  - shots_for: canon=27.962, live=28.312 (delta=+0.350)
  - goalie_sv_pct: canon=0.886, live=0.895 (delta=+0.009)
  - pp_opportunities: canon=2.897, live=2.712 (delta=-0.186)
- Impact: Contributes ~0.06 total prediction delta in early-season games.
  Decays as real data accumulates (w -> 1.0 after 20 games).

### D3: Goalie Save Pct - Team-Wide vs Goalie-Specific (MODERATE)
- Severity: MODERATE - persistent throughout season
- Location:
  - Canonical: nhl_rebuild.py line 278 - filters prior[prior.goalie_id == goalie_id]
  - Live: nhl_daily_pipeline.py line 528 - uses ALL team games (no goalie filter)
- Problem: Canonical computes goalie_sv_pct_rolling_10 using ONLY the
  starting goalies prior starts. Live uses ALL team games regardless of which
  goalie started.
- Effect: Live smooths over goalie platoon splits. A team with a .920 starter
  and .900 backup would show ~.910 in live for both, vs .920/.900 in canonical.
- Impact: Persistent ~0.01-0.03 prediction delta per game depending on
  goalie quality spread.

### D4: Goalie vs Team Baseline (LOW-MODERATE)
- Severity: LOW-MODERATE - effectively dead feature in live
- Location:
  - Canonical: nhl_rebuild.py line 285-290 - compares per-goalie mean to team mean
  - Live: nhl_daily_pipeline.py line 535-539 - compares team-wide rolling_10
    to team-wide all_mean
- Problem: Because goalie_sv_pct_rolling_10 is already team-wide (D3),
  the baseline comparison becomes rolling_10 team - all_time team, which is
  nearly zero except for minor window effects. The feature is EFFECTIVELY DEAD.
- Impact: Feature coefficient in model is non-trivial (goalie quality
  differentiation), but the signal is zeroed out.

### D5: Goalie Fatigue - Team vs Goalie Games (LOW)
- Severity: LOW
- Location:
  - Canonical: nhl_rebuild.py line 293-298 - counts goalies games in last 3 days
  - Live: nhl_daily_pipeline.py line 574-579 - counts ALL team games in last 3 days
- Problem: Live counts team games, not goalie starts. A backup starting on
  a B2B shows fatigue=1 in live but fatigue=0 in canonical (backup did not play yesterday).
- Impact: Overstates goalie fatigue in ~15 pct of games (B2B with backup starts).
  Coefficient is small, so prediction impact is less than 0.01 per game.

---

## Prediction-Level Impact

### Scenario 1: Live with correct raw data (bugs D2-D5 only)
- Mean total pred: Canonical 5.978, Live-simulated 5.871, Delta -0.107
- MAE: Canonical 1.865, Live-simulated 1.870, Delta +0.005
- Correlation: Canonical 0.015, Live-simulated 0.004, Delta -0.011
- Mean abs delta: 0.166
- Max abs delta: 0.690

### Scenario 2: Live with stale 6-col cache (all bugs)
- Mean total pred: Canonical 5.978, Stale-cache 5.785, Delta -0.193
- MAE: Canonical 1.865, Stale-cache 1.877, Delta +0.012
- Correlation: Canonical 0.015, Stale-cache 0.000, Delta -0.015
- Mean abs delta: 0.234
- Max abs delta: 0.884

### Divergence does NOT converge with season progression
- Games 1-20: mean delta=-0.059, std=0.061, max_abs=0.181
- Games 21-50: mean delta=-0.020, std=0.089, max_abs=0.168
- Games 51-100: mean delta=-0.056, std=0.134, max_abs=0.362
- Games 101-200: mean delta=-0.089, std=0.164, max_abs=0.517
- Games 201-500: mean delta=-0.124, std=0.184, max_abs=0.628
- Games 501-1258: mean delta=-0.111, std=0.183, max_abs=0.690

The divergence GROWS until ~game 200 and then stabilizes. This confirms the
persistent code-level bugs (D3, D4, D5) are the dominant factor, not the
decaying prior mismatch (D2).

---

## Root Cause Classification

MULTIPLE MISMATCHES - 5 independent divergence sources:
1. D1: Operational (stale cache)
2. D2: Design (different prior definitions)
3. D3: Code bug (team-wide vs goalie-specific)
4. D4: Code bug (dead feature from D3 cascading)
5. D5: Code bug (team vs goalie fatigue counting)

---

## Files Produced
- canonical_vs_live_predictions.csv - game-level prediction comparison (1258 rows)
- MASTER_SUMMARY.md - this file
- NHL_FEATURE_DIVERGENCE_FINAL_VERDICT.md - verdict and fix specification
