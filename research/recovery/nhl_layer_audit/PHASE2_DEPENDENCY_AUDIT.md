# NHL Layer Dependency Audit (Phase 2)

## Date: 2026-04-10

---

## Layer 1: DRIFT CORRECTION — CRITICAL DEPENDENCY ON OLD MODEL

**Consumes from base model:** Raw lambda predictions (lh_raw, la_raw)

**Dependency chain:**
- `VALIDATE_DRIFT = 0.4458` was calibrated on the OLD MoneyPuck-based model
- The old model's validate-season (2023-24) raw predictions averaged 5.7798
- Actual totals averaged 6.2256
- Gap = +0.4458 goals

**Problem with rebuilt model:**
- Rebuild Model A on the same OOS data (2024-25) has raw bias = -0.163
- Rebuild validate (2023-24) has raw bias = -0.019
- The correct drift for Model A would be ~+0.16 (OOS) or ~+0.02 (validate)
- The pipeline applies +0.4458 — OVER-correcting by ~+0.28 goals

**But live results show the opposite:**
- Live lambda_total_calibrated mean: 5.674
- Live actual totals mean: 6.569
- Live bias: -0.896 goals (model still too LOW even after +0.4458 correction)
- Lambda_raw (approx) = 5.228, actual = 6.569, raw gap = -1.341

**Root cause:** The live feature computation (rolling stats from NHL API boxscores)
produces systematically different feature values than the historical feature table
used to train Model A. The live shrinkage priors, rolling windows, and goalie
tracking differ enough to create a ~1.18 goal feature-level discrepancy beyond
what the historical bias predicted.

**VERDICT: NOT PORTABLE.** The +0.4458 constant is wrong for the rebuilt model.
The live pipeline needs a fresh drift calibration based on 2025-26 season data.

---

## Layer 2: POISSON SIMULATION — CONDITIONALLY PORTABLE

**Consumes from base model:** Calibrated lambdas only

**Dependencies:**
- Push corrections (6.0: -0.0471, 7.0: -0.0422) were calibrated on old model's
  Poisson distribution. With different lambdas, the push probabilities change.
- The corrections are small adjustments (< 5pp) and directionally correct for any
  model that uses Poisson simulation with similar lambda ranges.

**VERDICT: PORTABLE** with caveat that push corrections should be re-validated
when drift is re-calibrated.

---

## Layer 3: GOALIE HANDLING — NATIVE TO REBUILD

**Consumes from base model:** Is part of the base model (Model A features)

**Dependencies:** None external. Goalie features (sv_pct_rolling_10,
goalie_vs_team_baseline, backup_flag, goalie_b2b, goalie_fatigue) are all
Model A features that the rebuild was trained on.

**VERDICT: NATIVE** — not a layer to carry forward; it IS the model.

---

## Layer 4: CONFIDENCE TIER SYSTEM — DEPENDS ON EDGE DISTRIBUTION

**Consumes from base model:** Edge values

**Dependencies:**
- Threshold 0.15 for HIGH was set based on old model edge distribution
- Old model historical edge distribution: mean=0.134, range varies by split
- Live model edge distribution: mean=0.146 (already different due to bias)

**Problem:** With the current systematic under-prediction, almost all signals
are UNDER (92.3%), and edges are artificially inflated because the model
is far from the market line. Once drift is corrected, the edge distribution
will change dramatically.

**VERDICT: RECALIBRATE.** Thresholds need re-evaluation after drift fix.

---

## Layer 5: STOP RULES — CORRECTLY RESPONDING TO BAD PERFORMANCE

**Consumes:** Win/loss record by tier

**Dependencies:** None on base model directly. Responds to observed results.

**Current state:** MEDIUM and LOW are correctly shadowed given 33.3% and 26.7%
hit rates. The poor performance is a downstream symptom of the drift miscalibration.

**VERDICT: PORTABLE** but will need re-evaluation after drift fix. The stop rules
are a safety mechanism that worked as designed.

---

## Layer 6: EDGE CALCULATION — FULLY PORTABLE

**Consumes:** Model probabilities + market prices

**Dependencies:** Standard math. No calibration constants.

**VERDICT: PORTABLE** — model-agnostic.

---

## Layer 7: SIGNAL QUALIFICATION — PORTABLE

**Consumes:** Edge values + feature snapshots

**Dependencies:** THRESHOLD = 0.12 was set in Phase 4.5 as the lowest edge
band with hit >= 52.5% AND n >= 30. This was calibrated on the old model.

**VERDICT: RECALIBRATE** threshold after drift fix, but mechanism is portable.

---

## Layer 8: GRADING — FULLY PORTABLE

**Consumes:** Final scores from NHL API + signal records

**Dependencies:** None on base model. Standard W/L/P grading.

**VERDICT: PORTABLE** — model-agnostic.

---

## Layer 9: OT/SO DIAGNOSTICS — FULLY PORTABLE

**Consumes:** Canonical game data + graded signals

**Dependencies:** None on base model. Pure diagnostic.

**VERDICT: PORTABLE** — model-agnostic.

---

## Layer 10: SUMMARIES — CONDITIONALLY PORTABLE

**Consumes:** Signal feature values (goals_scored_rolling_10, goalie_vs_team_baseline, etc.)

**Dependencies:** League average benchmarks hardcoded:
- `_LEAGUE_AVG_GS = 2.95`
- `_LEAGUE_AVG_GA = 2.95`

These are from 2024-25 season and may need updating for 2025-26.

**VERDICT: PORTABLE** with minor benchmark updates.

---

## Layer 11: CLV SNAPSHOT INFRASTRUCTURE — FULLY PORTABLE

**Consumes:** Lines from signals at two time points

**Dependencies:** None on base model.

**VERDICT: PORTABLE** — model-agnostic infrastructure.

---

## Layer 12: LINE MOVEMENT TRACKING — FULLY PORTABLE

**Consumes:** Open line snapshots + current lines

**Dependencies:** None on base model.

**VERDICT: PORTABLE** — model-agnostic.

---

## Layer 13: DATA QUALITY AUDIT — FULLY PORTABLE

**Consumes:** Signal field values

**Dependencies:** None on base model.

**VERDICT: PORTABLE** — model-agnostic.

---

## Layer 14: SEASON PERFORMANCE AGGREGATION — FULLY PORTABLE

**Consumes:** Graded historical results

**Dependencies:** None on base model. Uses results.parquet from Phase 5.

**VERDICT: PORTABLE** — model-agnostic.

---

## Layer 15: LIVE SEASON FEATURE COMPUTATION — CRITICAL DEPENDENCY

**Consumes from base model:** Feeds directly into Model A predictions

**Dependencies:**
- Shrinkage priors from 2024-25 league averages
- Rolling window sizes (10 for goals/goalie, 20 for shots/PP/PK)
- NHL API boxscore fields for SOG, PP, goalie stats

**Problem:** The live feature computation produces systematically different
feature distributions than the historical training data. This is the primary
source of the ~1.34 goal raw bias in live predictions.

Possible causes:
1. Different goalie tracking (live uses team-level proxy, historical had
   goalie-specific matching)
2. Early-season shrinkage pulling features toward 2024-25 averages
3. SOG/PP opportunity counting differences between live API and historical data

**VERDICT: ROOT CAUSE INVESTIGATION NEEDED.** This layer is the most likely
source of the live prediction failure.
