# Phase 3 Lite — LT01 & LT02 Results

**Date:** 2026-03-29
**Lineup source:** reconstructed_actual_lineups (actual boxscore starters, not projected)

## Summary Table

| Feature | Coverage | delta_AUC | delta_Brier | delta_UR_57 | delta_UR_60 | Year Stable | Verdict |
|---------|----------|-----------|-------------|-------------|-------------|-------------|---------|
| LT01 (lineup K-rate) | 100.0% | +0.00075 | -0.00009 | -0.0390 | +0.0262 | Yes | **SHELVE** |
| LT02 (contact x whiff) | 100.0% | +0.02048 | -0.00181 | -0.0213 | -0.0126 | Yes | **SHELVE** |

## Baseline (V1 Ridge, train 2022-24, validate 2025)
- AUC: 0.54333
- Brier: 0.24864
- UR@0.57: 0.6009 (N=213)
- UR@0.60: 0.5738 (N=61)

## Year Stability

### LT01
| Window | Base AUC | Aug AUC | delta_AUC | Base UR57 | Aug UR57 | delta_UR57 |
|--------|----------|---------|-----------|-----------|----------|------------|
| 2022→2023 | 0.54873 | 0.5412 | -0.00753 | 0.549 | 0.5682 | 0.0192 |
| 2022-23→2024 | 0.55908 | 0.56119 | 0.00211 | 0.5589 | 0.5671 | 0.0082 |
| 2022-24→2025 | 0.54333 | 0.54408 | 0.00075 | 0.6009 | 0.5619 | -0.039 |

### LT02
| Window | Base AUC | Aug AUC | delta_AUC | Base UR57 | Aug UR57 | delta_UR57 |
|--------|----------|---------|-----------|-----------|----------|------------|
| 2022→2023 | 0.54873 | 0.56139 | 0.01266 | 0.549 | 0.663 | 0.114 |
| 2022-23→2024 | 0.55908 | 0.57282 | 0.01374 | 0.5589 | 0.5788 | 0.0199 |
| 2022-24→2025 | 0.54333 | 0.56381 | 0.02048 | 0.6009 | 0.5796 | -0.0213 |

## Pass Gates

### LT01
- coverage_70: PASS
- d_auc_positive: PASS
- d_ur57_positive: FAIL
- year_stable: PASS
- **VERDICT: SHELVE**

### LT02
- coverage_70: PASS
- d_auc_positive: PASS
- d_ur57_positive: FAIL
- year_stable: PASS
- coef_direction: FAIL
- **VERDICT: SHELVE**
