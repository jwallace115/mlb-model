# CS002 — Starter Short-Leash / Early Exit

**Verdict: FAIL**
**Direction:** OVER
**Failure reason:** Permutation percentile 60.2 < 85 required

---

## Signal Design

Rolling 5-start early exit rate (IP < 5.0). Top 20% threshold frozen on 2022-2023 at exit_rate >= 0.40.

## Results

| Split | N | Rate | ROI at -110 | Direction + |
|:------|---:|---:|---:|:---|
| Train (2022-2024) | 2635 | 0.4983 | -4.22% | — |
| In-sample 2024 | 1056 | 0.5066 | -5.81% | False |
| **Validation 2025** | **1105** | **0.5267** | **-9.64%** | **False** |

## Permutation Test

| Metric | Value |
|:-------|------:|
| Observed | 0.493316 |
| Permutation mean | 0.491644 |
| Permutation 95th | 0.501604 |
| **Percentile** | **60.2** |
| Gate (>= 85) | FAIL |

## Season Support

| Gate | Result |
|:-----|:-------|
| 2024 positive | False |
| 2025 positive (binding) | False |
| **Combined** | **FAIL: Neither 2024 nor 2025 directionally positive** |

## Interpretation

The hypothesis that early starter exits create excess scoring is directionally wrong after market adjustment. Games with high early-exit risk already have lower closing totals set by oddsmakers. The 47.3% over rate in 2025 flagged games is below the 50% baseline — the market over-corrects for short starters. This is consistent with the combined_short_exit shadow signal which also showed limited edge.
