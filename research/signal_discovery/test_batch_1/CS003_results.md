# CS003 — Pitcher Latent Fatigue State

**Verdict: FAIL**
**Direction:** OVER
**Failure reason:** Permutation percentile 21.0 < 85 required

---

## Signal Design

Whiff rate decline > 3pp from 5-start mean AND BB rate rise > 2pp from 5-start mean, using previous start values.

## Results

| Split | N | Rate | ROI at -110 | Direction + |
|:------|---:|---:|---:|:---|
| Train (2022-2024) | 788 | 0.5178 | -7.94% | — |
| In-sample 2024 | 332 | 0.5271 | -9.72% | False |
| **Validation 2025** | **315** | **0.5270** | **-9.7%** | **False** |

## Permutation Test

| Metric | Value |
|:-------|------:|
| Observed | 0.479601 |
| Permutation mean | 0.491554 |
| Permutation 95th | 0.515866 |
| **Percentile** | **21.0** |
| Gate (>= 85) | FAIL |

## Season Support

| Gate | Result |
|:-----|:-------|
| 2024 positive | False |
| 2025 positive (binding) | False |
| **Combined** | **FAIL: Neither 2024 nor 2025 directionally positive** |

## Interpretation

The fatigue proxy is anti-directional (47.3% over rate vs 50% baseline). The most likely explanation: whiff decline + BB rise in the previous start reflects regression to mean after a strong run, not true fatigue. The market captures this through ERA/xFIP adjustments that naturally update after poor starts. The 21.0th permutation percentile confirms no signal.
