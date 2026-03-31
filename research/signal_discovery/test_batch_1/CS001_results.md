# CS001 — Pitcher Command Regime Shift

**Verdict: FAIL**
**Direction:** UNDER
**Failure reason:** Permutation percentile 64.4 < 85 required

---

## Signal Design

Rolling 10-start z-score of CSW (whiff_rate proxy) and BB rate. Bad-command flag: CSW z < -1.0 AND BB z > 1.0 in previous start.

## Results

| Split | N | Rate | ROI at -110 | Direction + |
|:------|---:|---:|---:|:---|
| Train (2022-2024) | 245 | 0.5184 | -1.04% | — |
| In-sample 2024 | 115 | 0.5043 | -3.72% | True |
| **Validation 2025** | **98** | **0.5204** | **-0.65%** | **True** |

## Permutation Test

| Metric | Value |
|:-------|------:|
| Observed | 0.51895 |
| Permutation mean | 0.508466 |
| Permutation 95th | 0.55102 |
| **Percentile** | **64.4** |
| Gate (>= 85) | FAIL |

## Season Support

| Gate | Result |
|:-----|:-------|
| 2024 positive | True |
| 2025 positive (binding) | True |
| **Combined** | **Both 2024 and 2025 directionally positive** |

## Interpretation

The bad-command state was too rare (343 flagged games across 4 seasons, 98 in 2025) to generate reliable signal. The dual z-score condition is highly restrictive. Relaxing thresholds would increase N but dilute mechanism purity. The 52.0% under rate in flagged games is directionally correct but indistinguishable from noise at 64.4th permutation percentile.
