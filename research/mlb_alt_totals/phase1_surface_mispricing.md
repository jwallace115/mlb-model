# Phase 1: Alternate Totals Surface Mispricing

**Date:** 2026-04-10
**Status:** CLOSE
**Data Source:** The Odds API historical endpoint, alternate_totals market
**Sample:** 97 MLB games with matched actuals (Jul 1-14 + Sep 1-14, 2024)

---

## 1. Data Coverage and API Feasibility

### Alt-total market availability
The Odds API historical endpoint returns `alternate_totals` for MLB via per-event odds queries. Coverage is partial: 85 of 191 unique events in Jul 1-14, 2024 had alt-total data (44%), and 64 of 199 in Sep 1-14, 2024 (32%). Combined: 149 events with alt-total data, 97 matched to actual scores in game_table.

### Books and ladder structure

| Book | Ladder Rows | Avg Hold |
|------|-------------|----------|
| betmgm | 6,350 | 6.45% |
| draftkings | 4,764 | 6.42% |
| williamhill_us | 4,190 | 7.89% |
| betrivers | 3,156 | 6.94% |
| fanduel | 2,662 | 6.09% |
| bovada | 1,820 | 6.63% |
| wynnbet | 1,158 | 5.67% |

- **Ladder range:** 3.5 to 18.5 (half-run increments)
- **Points per event-book:** mean 13.0, range 1-23
- **Pairing rate:** 100% — every ladder point has both Over and Under prices
- **No single-sided points** in this dataset

### De-vig methodology
All implied probabilities computed via multiplicative de-vig:
- Raw implied = standard American-to-probability conversion
- De-vigged: `p_over = raw_over / (raw_over + raw_under)`, `p_under = 1 - p_over`
- Consensus implied = mean de-vigged probability across all books for each event/point

---

## 2. Hold Analysis

Mean hold: 6.69% across all paired points.

### Hold by distance from main line

| Distance | Hold (%) | N |
|----------|----------|---|
| -6.0 | 6.41 | 50 |
| -5.0 | 6.55 | 79 |
| -4.0 | 6.98 | 769 |
| -3.0 | 7.08 | 446 |
| -2.0 | 7.01 | 1,960 |
| -1.0 | 6.49 | 865 |
| 0.0 | 5.86 | 1,833 |
| +1.0 | 6.48 | 867 |
| +2.0 | 6.91 | 2,085 |
| +3.0 | 7.19 | 591 |
| +4.0 | 6.81 | 1,390 |
| +5.0 | 6.83 | 382 |
| +6.0 | 6.66 | 664 |

**Finding:** Hold is lowest at the main line (5.86%) and widens modestly at extremes (6.5-7.2%). The widening is symmetric and moderate -- roughly 1pp above baseline at +/-3 runs. This is expected: books add more margin where they have less confidence in pricing.

---

## 3. Implied vs. Actual Distribution (Full Ladder)

For each ladder point, computed consensus de-vigged implied Over probability across books, then compared to actual over rate across all games hitting that distance bucket. Restricted to points covered by 2+ books.

### Integer-distance buckets (2+ books required)

| Distance | N pts | Implied Over | Actual Over | Residual | SE | Sig |
|----------|-------|-------------|-------------|----------|-----|-----|
| -6.0 | 39 | 0.897 | 0.949 | +0.052 | 0.035 | |
| -5.0 | 50 | 0.880 | 0.900 | +0.020 | 0.042 | |
| -4.0 | 247 | 0.836 | 0.794 | -0.043 | 0.026 | |
| -3.0 | 98 | 0.777 | 0.704 | -0.072 | 0.046 | |
| -2.0 | 287 | 0.694 | 0.655 | -0.039 | 0.028 | |
| -1.0 | 100 | 0.600 | 0.550 | -0.050 | 0.050 | |
| 0.0 | 285 | 0.502 | 0.512 | +0.011 | 0.030 | |
| +1.0 | 100 | 0.408 | 0.400 | -0.008 | 0.049 | |
| +2.0 | 288 | 0.328 | 0.271 | -0.058 | 0.026 | * |
| +3.0 | 100 | 0.262 | 0.190 | -0.072 | 0.039 | |
| +4.0 | 288 | 0.207 | 0.156 | -0.051 | 0.021 | * |
| +5.0 | 99 | 0.165 | 0.141 | -0.024 | 0.035 | |
| +6.0 | 229 | 0.133 | 0.096 | -0.037 | 0.019 | * |

`*` = |residual| > 1.96 * SE (significant at 95%)

### Half-run distance buckets (2+ books, N >= 10)

| Dist | N | Imp Over | Act Over | Residual | SE | Flag |
|------|---|----------|----------|----------|-----|------|
| -4.5 | 36 | 0.8507 | 0.7778 | -0.0729 | 0.0693 | |
| -4.0 | 76 | 0.8388 | 0.8026 | -0.0361 | 0.0457 | |
| -3.5 | 84 | 0.8092 | 0.7619 | -0.0473 | 0.0465 | |
| -3.0 | 90 | 0.7761 | 0.7222 | -0.0539 | 0.0472 | |
| -2.5 | 88 | 0.7351 | 0.6705 | -0.0646 | 0.0501 | |
| -2.0 | 99 | 0.6967 | 0.6364 | -0.0604 | 0.0483 | |
| -1.5 | 94 | 0.6486 | 0.6489 | +0.0003 | 0.0492 | |
| -1.0 | 100 | 0.5996 | 0.5500 | -0.0496 | 0.0497 | |
| -0.5 | 92 | 0.5511 | 0.5761 | +0.0250 | 0.0515 | |
| 0.0 | 99 | 0.5012 | 0.5152 | +0.0140 | 0.0502 | |
| +0.5 | 92 | 0.4511 | 0.4565 | +0.0055 | 0.0519 | |
| +1.0 | 99 | 0.4081 | 0.4040 | -0.0041 | 0.0493 | |
| +1.5 | 94 | 0.3657 | 0.3298 | -0.0359 | 0.0485 | |
| +2.0 | 100 | 0.3280 | 0.2800 | -0.0480 | 0.0449 | |
| +2.5 | 88 | 0.2945 | 0.2159 | -0.0786 | 0.0439 | * |
| +3.0 | 99 | 0.2608 | 0.1919 | -0.0689 | 0.0396 | * |
| +3.5 | 86 | 0.2342 | 0.1744 | -0.0598 | 0.0409 | |
| +4.0 | 99 | 0.2068 | 0.1616 | -0.0452 | 0.0370 | |
| +4.5 | 84 | 0.1857 | 0.1190 | -0.0667 | 0.0353 | * |
| +5.0 | 84 | 0.1654 | 0.1310 | -0.0345 | 0.0368 | |
| +5.5 | 76 | 0.1473 | 0.1184 | -0.0289 | 0.0371 | |
| +6.0 | 45 | 0.1334 | 0.1333 | -0.0000 | 0.0507 | |
| +6.5 | 22 | 0.1139 | 0.0000 | -0.1139 | 0.0000 | thin |

### Key finding: Systematic one-directional curvature error

**Books consistently overestimate Over probability at high ladder points (distance > +1.5).** The implied probability CDF is too smooth/shallow on the right tail -- it assigns too much probability to high-scoring outcomes.

The pattern is:
- **At the main line (distance 0):** Implied and actual are well-calibrated (residual +0.01)
- **At +1 to +1.5:** Small or negligible residual (-0.004 to -0.036)
- **At +2.0 to +5.5:** Persistent negative residuals of -3% to -8% (overs hit less often than implied)
- **At -2.5 to -4.5:** Also negative residuals (-3% to -7%), meaning overs hit less than implied on the low side too

This creates a potential edge on the **Under side** of high alt-total lines.

---

## 4. Stability: July vs. September 2024

| Distance | Jul N | Jul Residual | Sep N | Sep Residual | Same Direction |
|----------|-------|-------------|-------|-------------|---------------|
| -4 | 124 | -0.059 | 72 | -0.028 | YES |
| -3 | 52 | -0.076 | 38 | -0.024 | YES |
| -2 | 157 | -0.031 | 124 | -0.054 | YES |
| -1 | 56 | -0.025 | 44 | -0.081 | YES |
| 0 | 157 | +0.041 | 126 | -0.017 | NO |
| +1 | 55 | -0.011 | 44 | +0.005 | NO |
| +2 | 158 | -0.048 | 124 | -0.061 | YES |
| +3 | 55 | -0.084 | 44 | -0.050 | YES |
| +4 | 152 | -0.068 | 117 | -0.042 | YES |
| +5 | 50 | -0.050 | 34 | -0.012 | YES |
| +6 | 83 | -0.056 | 60 | -0.001 | YES |

**Directional consistency: 9/11 buckets (82%).** The curvature error is stable across both periods, with the two inconsistent buckets being near-zero residuals at the main line and +1 (where we would not expect systematic error). This is the strongest evidence that the pattern is structural rather than noise.

---

## 5. Edge Quantification

### Under bets at high ladder (distance +1.5 to +3.5)

This is the zone with the largest residuals and where under prices are in the -200 to -400 range (heavy favorites but not extreme).

| Book | N | Actual Under | Implied Under | Raw Edge | ROI |
|------|---|-------------|---------------|----------|-----|
| williamhill_us | 366 | 0.779 | 0.688 | +9.1% | **+5.0%** |
| wynnbet | 83 | 0.711 | 0.649 | +6.2% | **+3.6%** |
| draftkings | 482 | 0.763 | 0.705 | +5.9% | **+1.7%** |
| betmgm | 444 | 0.759 | 0.702 | +5.7% | **+1.6%** |
| fanduel | 243 | 0.749 | 0.712 | +3.7% | -1.1% |
| betrivers | 335 | 0.737 | 0.691 | +4.6% | -1.5% |
| bovada | 106 | 0.660 | 0.637 | +2.3% | -3.1% |

**Critical finding:** Raw edge is 3-9% across all books, but **only 2 books (williamhill_us, wynnbet) show positive ROI**, and only **williamhill_us** has substantial sample (366 bets, +5.0% ROI). At most other books, the ~7% hold on these extreme lines absorbs the raw edge entirely.

### Over bets at low ladder (distance -4.5 to -2.5)

| Book | N | Actual Over | Implied Over | Raw Edge | ROI |
|------|---|------------|-------------|----------|-----|
| betmgm | 414 | 0.761 | 0.804 | -4.3% | -11.4% |
| williamhill_us | 327 | 0.743 | 0.787 | -4.4% | -12.7% |
| draftkings | 270 | 0.707 | 0.776 | -6.9% | -14.6% |

**No exploitable edge.** At the low side, the residuals go the wrong way for over bettors -- books overprice overs (overs hit less than implied), and the heavy juice makes under bets at these points deeply negative EV.

### Sweet spot search: Under at distance +1.0 to +2.0

| Book | N | Actual Under | Implied Under | Avg Price | ROI |
|------|---|-------------|---------------|-----------|-----|
| wynnbet | 129 | 0.682 | 0.627 | -201 | **+2.9%** |
| williamhill_us | 216 | 0.676 | 0.620 | -207 | **+1.0%** |
| draftkings | 286 | 0.664 | 0.632 | -211 | -1.5% |
| betmgm | 278 | 0.658 | 0.634 | -213 | -2.5% |
| bovada | 199 | 0.633 | 0.615 | -194 | -3.9% |
| betrivers | 259 | 0.653 | 0.637 | -220 | -4.3% |
| fanduel | 142 | 0.620 | 0.639 | -217 | -9.3% |

Only wynnbet and williamhill_us show marginal positive ROI, and both are within noise given sample sizes.

---

## 6. V1 Signal Interaction

Matched all 97 games to V1 model projections from `sim/data/bet_decisions.parquet`.

### Under bets at +1.5 to +3.5, split by V1 direction

| V1 Signal | N Points | N Events | Implied Under | Actual Under | Edge | SE |
|-----------|----------|----------|---------------|-------------|------|-----|
| V1-UNDER | 71 | 15 | 0.698 | 0.775 | +0.076 | 0.050 |
| V1-OVER | 396 | 82 | 0.703 | 0.758 | +0.055 | 0.022 |
| ALL | 467 | 97 | 0.702 | 0.760 | +0.058 | 0.020 |

### By V1 edge magnitude

| V1 Edge Range | N | Implied Under | Actual Under | Edge | SE |
|---------------|---|---------------|-------------|------|-----|
| < -0.5 (strong under) | 13 | 0.710 | 1.000 | +0.290 | 0.000 |
| -0.5 to 0 (mild under) | 58 | 0.696 | 0.724 | +0.028 | 0.059 |
| > 0 (over) | 396 | 0.703 | 0.758 | +0.055 | 0.022 |

**The "strong V1-UNDER" bucket shows a huge residual (+29%), but N=13 is far too thin to be actionable.** The V1-UNDER vs V1-OVER split (7.6% vs 5.5% edge) is suggestive but not statistically different given sample sizes. The curvature error exists regardless of V1 direction, which suggests it is a market-structural phenomenon rather than a model-signal phenomenon.

---

## 7. Interpretation: Why the Curvature Error Exists But Is Not Exploitable

The data clearly shows a structural pattern:

1. **Books use smooth interpolation** to price alt-total ladders. The implied CDF follows a logistic or normal-like shape that is too smooth compared to the actual run-scoring distribution, which has heavier mass at moderate totals and thinner tails than the smooth model implies.

2. **The error is real and stable** -- 82% directional consistency across periods, statistically significant at multiple distance buckets.

3. **But the hold is the problem.** At distance +2 to +4, where the raw edge is 4-7%, the typical hold is 6.8-7.2%. The under side at these points prices around -250 to -500, meaning you risk $250-$500 to win $100. Even a 5% edge in probability translates to only ~1-2% ROI, which is within noise and requires enormous volume.

4. **Only 1-2 books (williamhill_us, wynnbet) show positive ROI**, and williamhill_us at +5.0% ROI with N=366 is the strongest result. But this is a single-book finding, which is inherently lower confidence for a structural thesis.

5. **Game frequency is limited.** Only ~45% of games have alt-total lines on the API, projecting to ~630 games/season with coverage. At 97 games with actuals, the sample fails the N >= 100 minimum threshold for actionable conclusions at most individual ladder distances.

---

## 8. Verdict: CLOSE

**The implied distribution closely tracks actual across the full ladder, with curvature errors that are real but too small to overcome the hold.**

### Why not ADVANCE:
- Raw edge 4-7% at high ladder points, but hold of 6.5-7.2% at those same points absorbs nearly all of it
- ROI is positive at only 1-2 of 7 books, and only at +1.6% to +5.0% -- within normal variance for these sample sizes
- N=97 total games falls short of the 100-game minimum, and individual distance buckets are thinner
- The one promising result (williamhill_us +5.0% ROI, N=366 ladder points) is single-book and could reflect book-specific pricing error rather than structural mispricing

### Why not NEAR MISS:
- While the directional pattern is stable (82% consistency), the magnitude after vig is too small to be called "near miss." The structural finding is interesting but the economics do not work at current hold levels
- There is no clear path to improve: the edge is in the shape of the distribution, and books would need to significantly increase their hold errors or decrease their vig for this to become actionable

### What would change the verdict:
- A book offering alt totals with significantly lower hold (< 4%) at the +2 to +4 distance range
- A much larger sample (500+ games) revealing that the +5.0% ROI at williamhill_us is persistent
- Discovery that specific game conditions (e.g., Coors Field, extreme weather) amplify the curvature error
- A live collection period showing the same pattern with 2025-2026 data

### API cost:
- ~652 API calls used across events + alt_totals + standard totals for both sample periods
- Remaining credits: 4,843,397

---

## Appendix: Data Pipeline Notes

- Alt-total data pulled via: `GET /v4/historical/sports/baseball_mlb/events/{id}/odds?markets=alternate_totals`
- No alt-total data exists in the local odds archive (only h2h, spreads, totals, F5 variants)
- Game actuals matched from `sim/data/game_table.parquet` (2024 season, 2,427 games)
- V1 signals matched from `sim/data/bet_decisions.parquet` (4,855 rows, 2024-2025)
- Main line consensus computed as median of standard totals market across books
- All analysis in-memory; no data files created on remote server
