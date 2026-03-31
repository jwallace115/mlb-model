# TB Model v1.1 — Calibration Report

**Date:** 2026-03-27

## Approach

- **GBT trained on:** 2022-2023 (91,970 batter-games)
- **Isotonic calibration fit on:** 2024 (49,153 batter-games)
- **Validation:** 2025 (49,306 batter-games)

This avoids any leakage: the calibrator never sees 2025 data.

## Calibration Metrics

| Model | Metric | Raw | Calibrated | Change |
|:------|:-------|---:|---:|---:|
| tb_zero | AUC | 0.6151 | 0.6148 | -0.0003 |
| tb_zero | LogLoss | 0.6655 | 0.6658 | +0.0003 |
| tb_zero | Brier | 0.2365 | 0.2365 | +0.0001 |
| tb_over_1_5 | AUC | 0.6058 | 0.6054 | -0.0004 |
| tb_over_1_5 | LogLoss | 0.6105 | 0.6105 | -0.0000 |
| tb_over_1_5 | Brier | 0.2107 | 0.2107 | -0.0001 |
| tb_over_2_5 | AUC | 0.6064 | 0.6059 | -0.0005 |
| tb_over_2_5 | LogLoss | 0.4681 | 0.4681 | -0.0000 |
| tb_over_2_5 | Brier | 0.1477 | 0.1477 | -0.0001 |

**Result:** Isotonic calibration produces negligible change. The v1.1 model (trained on 2022-2023 only, a smaller training set than v1's 2022-2024) was already well-calibrated through most of the probability range.

## Calibration at Extremes — tb_zero (P = 0)

| Probability Bin | Type | N | Predicted | Actual | Gap |
|:----------------|:-----|---:|---:|---:|---:|
| [0.00-0.30) | Raw | 2,180 | 0.278 | 0.305 | -0.026 |
| [0.00-0.30) | Cal | 2,030 | 0.283 | 0.299 | **-0.015** |
| [0.30-0.40) | Raw | 17,708 | 0.354 | 0.353 | +0.001 |
| [0.30-0.40) | Cal | 15,216 | 0.344 | 0.348 | **-0.004** |
| [0.40-0.50) | Raw | 18,261 | 0.448 | 0.456 | -0.007 |
| [0.40-0.50) | Cal | 20,334 | 0.444 | 0.446 | **-0.003** |
| [0.50-0.60) | Raw | 8,208 | 0.539 | 0.558 | -0.019 |
| [0.50-0.60) | Cal | 9,270 | 0.551 | 0.558 | **-0.007** |
| [0.60-0.70) | Raw | 2,398 | 0.640 | 0.663 | -0.022 |
| [0.60-0.70) | Cal | 1,597 | 0.651 | 0.658 | **-0.007** |
| [0.70-0.75) | Raw | 360 | 0.722 | 0.753 | -0.031 |
| [0.70-0.75) | Cal | 222 | 0.717 | 0.730 | **-0.013** |
| [0.75-0.80) | Raw | 145 | 0.773 | 0.807 | -0.034 |
| [0.75-0.80) | Cal | 231 | 0.781 | 0.710 | **+0.071** |
| [0.80-0.85) | Raw | 34 | 0.818 | 0.735 | +0.082 |
| [0.80-0.85) | Cal | 322 | 0.813 | 0.789 | +0.024 |

**Key finding:** Calibration reduced the gap at most probability levels, but at [0.75-0.80) the calibrated model now *over-predicts* by 7.1pp (gap reversed from -3.4pp raw to +7.1pp calibrated). The extreme tail (0.80+) remains over-confident.

**Interpretation:** The v1 over-confidence problem at extremes was partly caused by training on all of 2022-2024. By training on 2022-2023 and calibrating on 2024, the model is better behaved through 0.70, but the extreme tail still has limited calibration data (N=231 in the 0.75-0.80 bin) and remains unreliable.

## Conclusion

Isotonic calibration provides modest improvement in the mid-range but does not fully solve the extreme-probability over-confidence. The practical implication is that **confidence-based cohort selection (top N%) works better than edge-based thresholds**, because edge thresholds over-select the unreliable extreme tail.
