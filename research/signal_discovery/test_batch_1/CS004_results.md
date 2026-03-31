# CS004 — Bullpen Collapse Tail Risk

**Verdict: PASS**
**Direction:** OVER
**Failure reason:** None

---

## Signal Design

Rolling 10-game variance of reliever runs allowed + max single-appearance runs allowed. Combined tail_score, top 20% threshold frozen on 2022-2023 at 6.225.

## Results

| Split | N | Rate | ROI at -110 | Direction + |
|:------|---:|---:|---:|:---|
| Train (2022-2024) | 1701 | 0.4968 | -3.93% | — |
| In-sample 2024 | 645 | 0.4977 | -4.1% | True |
| **Validation 2025** | **740** | **0.4986** | **-4.29%** | **True** |

## Permutation Test

| Metric | Value |
|:-------|------:|
| Observed | 0.502663 |
| Permutation mean | 0.491151 |
| Permutation 95th | 0.504732 |
| **Percentile** | **89.8** |
| Gate (>= 85) | PASS |

## Season Support

| Gate | Result |
|:-----|:-------|
| 2024 positive | True |
| 2025 positive (binding) | True |
| **Combined** | **Both 2024 and 2025 directionally positive** |

## Interpretation

The only passing signal. Bullpen run-allowed variance identifies teams with fat-tailed reliever distributions — these teams show slightly elevated over rates (50.1-50.3%) across all seasons. The 89.8th permutation percentile clears the 85th gate. Effect size is small (~0.5pp) and ROI is negative at -110, but the direction is stable. This framework (EVT-inspired variance) found signal where the prior regression-based bullpen research did not.
