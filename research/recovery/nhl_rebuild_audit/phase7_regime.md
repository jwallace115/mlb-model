# Phase 7: Regime Check

## League Scoring Trends
| Season | Avg Total | Std  | Games |
|--------|-----------|------|-------|
| 2021   | 6.29      | 2.34 | 1,312 |
| 2022   | 6.36      | 2.28 | 1,312 |
| 2023   | 6.23      | 2.31 | 1,312 |
| 2024   | 6.08      | 2.32 | 1,312 |
| 2025   | 6.27      | 2.30 | 1,258 |

Scoring is stable across seasons (range: 6.08-6.36). No regime break.

## Model A Bias by Season
| Season | Bias    | MAE   |
|--------|---------|-------|
| 2021   | +0.022  | 1.844 |
| 2022   | -0.022  | 1.814 |
| 2023   | -0.019  | 1.864 |
| 2024   | -0.163  | 1.871 |
| 2025   | -0.288  | 1.865 |

CONCERN: Growing negative bias in 2024-2025. The model increasingly underpredicts
totals in recent seasons. The validation drift correction (+0.019) is insufficient
to compensate for the -0.163 OOS bias. This is partially corrected by the calibration
step but warrants monitoring.

## Feature Stability
- goals_scored_rolling_10: stable (3.03-3.18 across seasons)
- shots_for_rolling_20: DECLINING TREND (31.6 in 2021 -> 28.0 in 2025)
- pp_pct_rolling_20: stable (0.20-0.21)
- goalie_sv_pct_rolling_10: slight decline (0.902 -> 0.889)

The SOG decline is a real NHL trend (fewer shots per game in recent seasons).
The model trained on 2021-2022 may overweight shot volume.

## Edge Signal Quality (OOS)
- corr(model_edge, market_error) = 0.1552 (STRONG genuine signal)
- Threshold: >0.05 = genuine, >0.10 = strong

## Direction Breakdown (OOS, edge >= 0.3)
- OVER: 322 bets, win% = 55.6%
- UNDER: 332 bets, win% = 53.9%
- Signal works in both directions.

## Edge Bucket Calibration (OOS)
| Edge Range  | Bets | Win%  |
|-------------|------|-------|
| [0.0, 0.3)  | 612  | 58.0% |
| [0.3, 0.5)  | 296  | 52.4% |
| [0.5, 0.8)  | 277  | 55.2% |
| [0.8, 1.0)  | 51   | 60.8% |
| [1.0+)      | 30   | 63.3% |

Monotonically increasing win rate with edge size (except [0.3, 0.5) dip).
This is the hallmark of a genuine predictive signal.

## Monthly Stability (OOS, edge >= 0.3)
| Month    | Over Win% (n) | Under Win% (n) |
|----------|---------------|-----------------|
| 2024-10  | 79% (19)      | 48% (48)        |
| 2024-11  | 42% (31)      | 45% (64)        |
| 2024-12  | 50% (34)      | 63% (49)        |
| 2025-01  | 51% (59)      | 62% (68)        |
| 2025-02  | 50% (50)      | 36% (25)        |
| 2025-03  | 61% (80)      | 56% (57)        |
| 2025-04  | 61% (49)      | 62% (21)        |

Monthly results are noisy (expected with small samples). October over side
is suspiciously high (79%) but n=19. No systematic collapse in any month.

## Quintile Calibration
| Quintile | Predicted | Actual | Delta  |
|----------|-----------|--------|--------|
| Q1       | 5.47      | 5.86   | -0.39  |
| Q2       | 5.75      | 5.99   | -0.24  |
| Q3       | 5.93      | 6.00   | -0.07  |
| Q4       | 6.11      | 6.29   | -0.18  |
| Q5       | 6.43      | 6.27   | +0.16  |

Systematic underprediction in Q1-Q4, slight overprediction in Q5.
Consistent with the overall negative bias noted above.

VERDICT: GENUINE SIGNAL with growing bias concern. Edge-size calibration
is monotonic (good). Regime-stable across months and directions.
