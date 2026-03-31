# Soccer V3 Poisson Challenger Model — Evaluation

Generated: 2026-03-28

## Model Description

Independent Poisson simulation model using rolling 10-game team attack/defense strengths,
league-level home/away factors, early-season prior blending, and rest adjustments.
xG-based where available, falling back to actual goals.

## Diagnostics

=== PART 5: OOS EVALUATION (2024-25) ===
======================================================================

OOS games: 1372
OOS actual O2.5 rate: 0.5474
OOS avg p_over_2_5: 0.5367
OOS avg market_fair_p: 0.5494

--- Diagnostic 1: Calibration ---

Bucket           N  Avg Pred   Actual     Gap
---------------------------------------------
<0.40          162    0.3388   0.4506 +0.1118
0.40-0.45      152    0.4275   0.5461 +0.1185
0.45-0.50      220    0.4758   0.4773 +0.0015
0.50-0.55      230    0.5265   0.5522 +0.0257
0.55-0.60      214    0.5756   0.5607 -0.0148
0.60-0.65      155    0.6251   0.6000 -0.0251
0.65+          239    0.7141   0.6276 -0.0865

Platt calibration slope: 1.77 (ideal=1.0)
Platt intercept: -0.76
Brier score: 0.2497
Overall bias: -1.1pp

--- Diagnostic 2: Edge Calibration ---

Edge Bucket         N  Avg Edge  Actual O2.5  Avg Mkt Err
----------------------------------------------------------
<=-0.06           451   -0.1250       0.5898      +0.0158
-0.06:-0.03       154   -0.0444       0.5714      +0.0036
-0.03:0.00        168   -0.0154       0.5595      +0.0013
0.00:0.03         150   +0.0143       0.5267      -0.0146
0.03:0.06         138   +0.0442       0.5145      -0.0189
0.06:0.10         109   +0.0783       0.4862      -0.0374
0.10+             202   +0.1561       0.4950      -0.0093

Spearman correlation (edge bucket rank vs avg market error): -0.79 (p=0.036)

--- Diagnostic 3A: Closing Line Test (V2.2 thresholds) ---

Active bets (|edge| >= 0.06): 762
Overall: N=762, hit=0.444, ROI@actual=-9.7%, ROI@-110=-15.3%

By Tier:
  LOW: N=140, hit=0.464, ROI@actual=-7.6%, ROI@-110=-11.4%
  MEDIUM: N=135, hit=0.422, ROI@actual=-15.5%, ROI@-110=-19.4%
  HIGH: N=487, hit=0.444, ROI@actual=-8.7%, ROI@-110=-15.3%

By League:
  EPL: N=211, hit=0.441, ROI@actual=-2.6%, ROI@-110=-15.9%
  BUN: N=161, hit=0.398, ROI@actual=-20.1%, ROI@-110=-24.1%
  SEA: N=229, hit=0.472, ROI@actual=-10.1%, ROI@-110=-10.0%
  LG1: N=161, hit=0.453, ROI@actual=-8.0%, ROI@-110=-13.4%

MEDIUM-only: N=135, ROI@actual=-15.5%
BUN+MEDIUM: N=28, hit=0.500, ROI@actual=-7.2%

--- Diagnostic 3B: V3-Native Thresholds (tuned on validation) ---
Validation games: 1372

 Threshold     N    Hit%   ROI@-110
------------------------------------
      0.02  1155   0.476       -9.1%
      0.03  1043   0.475       -9.4%
      0.04   946   0.461      -12.0%
      0.05   853   0.458      -12.5%
      0.06   755   0.457      -12.8%
      0.07   657   0.444      -15.2%
      0.08   574   0.441      -15.9%
      0.09   507   0.434      -17.2%
      0.10   441   0.431      -17.7%
      0.11   379   0.441      -15.9%
      0.12   332   0.443      -15.5%
      0.13   285   0.442      -15.6%
      0.14   240   0.429      -18.1%
      0.15   207   0.430      -17.9%
      0.16   177   0.424      -19.1%

Optimal validation threshold: 0.02 (N=1155, ROI@-110=-9.1%)

OOS with V3-native threshold (0.02):
  Overall: N=1157, hit=0.459, ROI@actual=-7.6%, ROI@-110=-12.4%
  EPL: N=309, hit=0.463, ROI@actual=-0.5%
  BUN: N=260, hit=0.412, ROI@actual=-18.5%
  SEA: N=332, hit=0.485, ROI@actual=-8.0%
  LG1: N=256, hit=0.469, ROI@actual=-4.6%

--- Diagnostic 4: Edge Overstatement ---

Version A (threshold=0.06):
  OVER bets: N=311
  Mean claimed edge: 0.1289
  Mean actual edge:  -0.0191
  Overstatement: -6.7x

Version B (threshold=0.02):
  OVER bets: N=494
  Mean claimed edge: 0.0958
  Mean actual edge:  -0.0169
  Overstatement: -5.7x

======================================================================
=== PART 6: Comparison Table ===
======================================================================

| Metric                    | V2.2     | V2.2b    | V3 (A)    | V3 (B)    |
|---------------------------|----------|----------|-----------|-----------|
| Calibration slope         | 0.64     | 0.99     | 1.77      | 1.77      |
| Overall bias (pp)         | -3.8     | -4.2     |      -1.1 |      -1.1 |
| Brier score               | 0.2393   | 0.2391   | 0.2497    | 0.2497    |
| Spearman (edge->mkt err)  | 0.93     | 0.36     |     -0.79 |     -0.79 |
| Edge overstatement        | 4.4x     | 6.8x     |     -6.7x |     -5.7x |
| Overall ROI @ actual      | -1.3%    | -2.9%    |     -9.7% |     -7.6% |
| BUN ROI @ actual          | +7.5%    | +7.1%    |    -20.1% |    -18.5% |
| EPL ROI @ actual          | -4.9%    | -2.0%    |     -2.6% |     -0.5% |
| LG1 ROI @ actual          | -3.0%    | +1.8%    |     -8.0% |     -4.6% |
| SEA ROI @ actual          | -9.2%    | -46.4%   |    -10.1% |     -8.0% |
| MEDIUM ROI @ actual       | +10.1%   | -3.7%    |    -15.5% |    -15.5% |
| N active bets             | 413      | 357      |       762 |      1157 |

======================================================================
=== PART 7: Decision Gate ===
======================================================================

1. BUN ROI > V2.2b (+7.1%): best=-18.5% -> FAIL
2. Calibration slope >= 0.85: slope=1.77 -> PASS
3. Edge overstatement < 2x: best=-6.7x -> PASS

Final verdict: V2.2b REMAINS CHALLENGER

=== PART 8: Saving outputs ===
Saved: soccer/models/v3/v3_parameters.json
Saved: soccer/models/v3/v3_predictions_oos.parquet


## Root Cause Analysis

The quintile check reveals V3 has weak but real discriminative power — higher V3 predictions
do correspond to higher actual over rates (Q1=48.7% to Q5=63.3%). The model is not broken
at ranking. But it is **anti-predictive relative to the market**:

| Quintile | V3 Pred | Market P | Actual | V3 Edge | Market Better? |
|----------|---------|----------|--------|---------|----------------|
| Q1 (low) | 0.373 | 0.481 | 0.487 | -0.108 | YES (market closer) |
| Q2 | 0.473 | 0.524 | 0.504 | -0.051 | YES |
| Q3 | 0.534 | 0.542 | 0.544 | -0.008 | ~tie |
| Q4 | 0.599 | 0.579 | 0.569 | +0.020 | YES (market closer) |
| Q5 (high) | 0.705 | 0.621 | 0.633 | +0.084 | YES (market closer) |

V3's probability estimates are **wider than reality** (too extreme in both tails):
- When V3 says 0.37, actual is 0.49 — too pessimistic
- When V3 says 0.71, actual is 0.63 — too optimistic
- The market nails the middle and tails better

This is the classic independent Poisson over-dispersion problem. Rolling 10-game xG windows
produce noisy attack/defense estimates that amplify team differences. The market already
prices in the mean-reversion that V3 misses.

Correlation with actual outcome: V3=0.103 vs V2.2=0.204 vs Market=0.211.
V3 has roughly half the discriminative power of V2.2 or the market.

## Verdict

**V2.2b REMAINS CHALLENGER**

V3 fails decisively. The independent Poisson approach with rolling team strengths cannot
compete with the market-relative Ridge approach. The market already incorporates team
strength information more accurately than 10-game rolling xG windows can provide.

Potential improvements that would NOT fix the core issue:
- Dixon-Coles correction (helps low-scoring bias, not the anti-prediction problem)
- Opponent adjustment (would reduce noise but not enough to beat market)
- Longer rolling windows (reduces variance but increases lag)

The fundamental problem is that a Poisson model built from public xG cannot beat a market
that already prices in private information (lineups, injuries, tactical matchups, money flow).
The market-relative approach (V2.2) succeeds precisely because it starts from the market
price and only tries to find residual edges.
