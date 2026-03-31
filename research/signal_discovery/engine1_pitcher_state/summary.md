# Engine 1 — Pitcher State Collapse

All thresholds frozen on 2022-2023. Training: 2022-2024. Validation: 2025.

## Signal Results

| signal | train_N | val_N | train_rate | val_rate | ROI | perm | yr_stable | verdict |
|---|---|---|---|---|---|---|---|---|
| PS001 | 1496 | 653 | 0.488 | 0.4839 | -6.84% | 24.2 | False | FAIL (perm=24.2; val=0.4839; yr=1/3) |
| PS002 | 121 | 70 | 0.5372 | 0.4714 | 2.55% | 82.4 | True | FAIL (perm=82.4; val=0.4714) |
| PS003 | 661 | 286 | 0.5053 | 0.5 | -3.53% | 70.6 | True | FAIL (perm=70.6; val=0.5) |
| PS004 | 9 | 4 | 0.3333 | 0.5 | -36.36% | 10.6 | False | FAIL (THIN_SAMPLE) |
| PS005 | 312 | 166 | 0.5128 | 0.4518 | -2.1% | 70.6 | False | FAIL (perm=70.6; val=0.4518; yr=1/3) |

## Component Analysis

| Component | N Top Q | Over Rate | Baseline | Lift |
|---|---|---|---|---|
| velo_drift | 1539 | 0.4945 | 0.4915 | 0.3pp |
| release_variance_delta | 1520 | 0.4803 | 0.4915 | -1.12pp |
| shape_drift_magnitude | 1682 | 0.4946 | 0.4915 | 0.31pp |
| csw_drift | 1634 | 0.5031 | 0.4915 | 1.16pp |
| entropy_drift | 1578 | 0.5019 | 0.4915 | 1.04pp |

**All 5 signals: FAIL.** Pitcher state degradation as measured by velocity drift, release variance,
shape drift, CSW drift, and entropy drift does NOT predict over outcomes in MLB totals.
