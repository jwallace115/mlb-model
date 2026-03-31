# CS005 — Bullpen Latent Fatigue State

**Verdict: FAIL**
**Direction:** OVER
**Failure reason:** Permutation percentile 30.0 < 85 required

---

## Signal Design

High-leverage IP in last 3 days normalized by team season average. Top 20% threshold frozen on 2022-2023 at 1.408x season average.

## Results

| Split | N | Rate | ROI at -110 | Direction + |
|:------|---:|---:|---:|:---|
| Train (2022-2024) | 1217 | 0.5103 | -6.51% | — |
| In-sample 2024 | 451 | 0.5033 | -5.18% | False |
| **Validation 2025** | **461** | **0.5228** | **-8.89%** | **False** |

## Permutation Test

| Metric | Value |
|:-------|------:|
| Observed | 0.486293 |
| Permutation mean | 0.491565 |
| Permutation 95th | 0.510757 |
| **Percentile** | **30.0** |
| Gate (>= 85) | FAIL |

## Season Support

| Gate | Result |
|:-----|:-------|
| 2024 positive | False |
| 2025 positive (binding) | False |
| **Combined** | **FAIL: Neither 2024 nor 2025 directionally positive** |

## Interpretation

Anti-directional: 47.7% over rate in high-fatigue games vs 50% baseline. High leverage-weighted fatigue likely correlates with teams in competitive, tight games — which are lower-scoring environments. The fatigue→OVER hypothesis assumes tired bullpens allow more runs, but the confound is that bullpens worked hard *because* games were close, not because the scoring environment is high. The 30.0th permutation percentile confirms no usable signal.
