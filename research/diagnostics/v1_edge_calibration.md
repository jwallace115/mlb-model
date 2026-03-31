# V1 Edge Calibration vs Market Error

**Date:** 2026-03-28
**Data:** 4,855 games (2024-2025)

## Definitions

- `edge = model_projection - closing_line` (positive = model says OVER)
- `market_error = actual_runs - closing_line` (positive = actual exceeded line)

## Edge vs Market Error — Main Table

| Edge Bucket | N | Avg Edge | Avg Market Error | Avg |Market Error| |
|-------------|---|----------|-----------------|-------------------|
| Below -1.25 | 109 | -1.895 | **+0.312** | 3.440 |
| -1.25 to -0.75 | 126 | -0.954 | **-0.837** | 3.218 |
| -0.75 to -0.25 | 501 | -0.455 | +0.182 | 3.475 |
| -0.25 to 0.00 | 411 | -0.122 | -0.213 | 3.145 |
| 0.00 to +0.25 | 542 | +0.137 | -0.168 | 3.677 |
| +0.25 to +0.75 | 1,443 | +0.499 | **+0.546** | 3.377 |
| +0.75 to +1.25 | 1,056 | +0.974 | **+0.844** | 3.511 |
| Above +1.25 | 667 | +1.599 | **+0.941** | 3.388 |

## Key Question: Does Edge Predict Market Error?

**YES — with caveats.**

| Metric | Value |
|--------|-------|
| Pearson correlation(edge, market_error) | **0.086** |
| Edge < -0.25: avg market error | +0.026 (near zero) |
| Edge > +0.25: avg market error | **+0.728** |
| Delta | **+0.702 runs** |
| Direction matches | **YES** |
| Monotonic | **NO** (Below -1.25 bucket breaks pattern) |

When the model projects OVER the market by 0.25+ runs, actual scoring
exceeds the line by 0.73 runs on average. When the model projects UNDER,
actual scoring is near the line (+0.03). The model's directional signal
is real but noisy (r=0.086).

**The non-monotonicity matters:** The most extreme negative edge bucket
(Below -1.25, where the model projects far under the line) has a
*positive* market error (+0.312). These are games where the model says
"very low scoring" but actual runs come in above the line. This is the
model's overconfidence zone on the UNDER side.

## V1 UNDER Signals — Secondary Check

| Metric | V1 UNDER | All Games | Lift |
|--------|----------|-----------|------|
| N | 932 | 4,855 | — |
| Avg edge (model - line) | **-0.075** | +0.471 | — |
| Avg market error (actual - line) | **+0.131** | +0.442 | -0.311 |
| % actual below line | **53.4%** | 48.9% | **+4.5pp** |

V1 UNDER fires on games where actual runs come in below the line
53.4% of the time — a 4.5pp lift over the 48.9% base rate. The model
identifies real suppression.

**Avg edge for V1 UNDER is -0.075** — these are games where the model
projects *barely below* the market, not far below. The signal is not
about large disagreement; it's about the model's probability estimate
(p_under >= 0.57) from the full simulation distribution.

### V1 UNDER by Edge Bucket

| Edge Bucket | N | Avg Market Error | % Below Line |
|-------------|---|-----------------|-------------|
| Below -1.25 | 59 | +0.042 | 54.2% |
| -1.25 to -0.75 | 59 | **-0.441** | **59.3%** |
| -0.75 to -0.25 | 215 | -0.005 | **56.3%** |
| **-0.25 to 0.00** | **125** | **-0.352** | **60.8%** |
| 0.00 to +0.25 | 126 | +0.083 | 54.0% |
| +0.25 to +0.75 | 270 | +0.652 | 48.1% |
| +0.75 to +1.25 | 71 | -0.035 | 46.5% |
| Above +1.25 | 7 | +1.000 | 42.9% |

**The best-performing UNDER signals have small negative edges (-0.25 to 0.00):**
60.8% below-line rate. This aligns with the earlier edge structure finding —
V1 UNDER works best when the model barely disagrees with the market, not
when it disagrees a lot.

**V1 UNDER signals with positive edges (+0.25 to +1.25) perform poorly:**
46-48% below-line rate. These are games where the model actually projects
ABOVE the line but the p_under simulation probability still crossed 0.57
due to distribution shape. These are the weakest signals.

## Interpretation

1. **The model has real directional signal** (r=0.086, delta=0.70 runs).
   When the model says higher than market, actual scoring is higher.

2. **V1 UNDER's edge is concentrated in small-edge territory.** The
   best UNDER signals are where the model projects just below the line
   (-0.25 to 0.00), not far below it. The p_under probability from the
   simulation distribution captures uncertainty that the raw edge does not.

3. **Large negative edges are NOT the best UNDER signals.** Below -1.25,
   the model's confidence exceeds its accuracy — actual runs don't
   cooperate. The model overestimates its ability to predict extreme
   low-scoring games.

4. **Non-V1 games confirm the lift:** non-V1 games have 47.9% below-line
   rate (below the 48.9% overall because V1 selects the best UNDER
   games, leaving the remainder slightly OVER-skewed).
