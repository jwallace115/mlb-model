# V1 Simulation Probability Calibration

**Date:** 2026-03-28
**Data:** 4,666 games (2024-2025, pushes excluded)

## Step 1 — Full Dataset Calibration

| p_under Bucket | N | Avg p_under | Actual Under% | Gap | Assessment |
|----------------|---|-------------|--------------|-----|-----------|
| 0.00–0.44 | 1,023 | 0.3845 | **0.4712** | **+0.087** | Underconfident |
| 0.44–0.50 | 1,236 | 0.4717 | **0.5065** | **+0.035** | Underconfident |
| 0.50–0.54 | 885 | 0.5194 | 0.4870 | -0.032 | Overconfident |
| 0.54–0.57 | 632 | 0.5547 | 0.5364 | -0.018 | Calibrated |
| 0.57–0.60 | 434 | 0.5833 | 0.5415 | **-0.042** | Overconfident |
| 0.60–0.63 | 241 | 0.6132 | 0.5768 | **-0.036** | Overconfident |
| 0.63–0.66 | 119 | 0.6426 | 0.5882 | **-0.054** | Overconfident |
| 0.66+ | 96 | 0.6892 | 0.5625 | **-0.127** | Strongly overconfident |

### Calibration Metrics

| Metric | Value |
|--------|-------|
| Mean calibration gap | -0.024 (model overestimates under probability) |
| Mean absolute gap | 0.054 |
| Brier score (model) | 0.2525 |
| Brier score (naive 50/50) | 0.2500 |
| **Brier skill score** | **-0.010** |

**The model's Brier score is marginally WORSE than naive 50/50.** The probability
estimates do not outperform coin-flip calibration. This means the simulation
probabilities are not well-calibrated in absolute terms.

## Step 2 — Signal Zone Calibration

| Signal Tier | N | Avg p_under | Actual Under% | Gap | ROI |
|-------------|---|-------------|---------------|-----|-----|
| 0.57–0.60 (0.5u) | 434 | 0.5833 | 0.5415 | **-0.042** | **+3.4%** |
| 0.60+ (1.0u) | 456 | 0.6369 | 0.5768 | **-0.060** | **+10.1%** |
| **Combined** | **890** | **0.6107** | **0.5596** | **-0.051** | **+6.8%** |

The model says 61.1% under probability. Reality is 56.0%. The gap is 5.1pp.

**Despite being overconfident, the signal is profitable.** The 56% actual
under rate produces +6.8% ROI at -110. The model doesn't need perfect
calibration to make money — it just needs to identify games with >50%
true under probability, which it does.

## Step 3 — Over Side Calibration

| Zone | N | Predicted Over% | Actual Over% | Gap |
|------|---|-----------------|-------------|-----|
| Strong OVER (p_over > 0.57) | 864 | 62.5% | **52.9%** | **-9.6pp** |
| Moderate OVER (p_over 0.50-0.57) | 1,395 | 53.2% | 49.8% | -3.5pp |

The OVER side is **much more overconfident** than the UNDER side. When the
model says 62.5% over probability, actual is only 52.9% — a 9.6pp gap.
This is nearly 2x the UNDER-side gap (5.1pp).

This confirms why V1 fires UNDER only in production. The OVER probability
estimates are not trustworthy enough for signal generation.

## Key Finding: Systematic Overconfidence

The model is **overconfident in both directions** at the extremes:

| Direction | Predicted | Actual | Overconfidence |
|-----------|-----------|--------|----------------|
| Strong UNDER (0.66+) | 68.9% | 56.3% | **12.7pp** |
| Strong OVER (p_over > 0.57) | 62.5% | 52.9% | **9.6pp** |
| Signal UNDER (0.57-0.60) | 58.3% | 54.2% | **4.2pp** |

The simulation produces probability distributions that are **too wide** —
it pushes too much mass into the tails. A game that the simulation says
is 65% under is really about 57% under. The ranking is preserved (higher
p_under → higher actual under%), but the magnitudes are inflated.

## Calibration Shape

```
p_under < 0.44:  actual HIGHER than predicted (underconfident on OVER side)
p_under 0.44-0.50: actual HIGHER than predicted (still underconfident)
p_under 0.50-0.57: actual CLOSE to predicted (near-calibrated)
p_under 0.57+:     actual LOWER than predicted (overconfident on UNDER side)
```

The model is underconfident when it leans OVER and overconfident when it
leans UNDER. This asymmetry likely stems from the model's systematic
+0.47 run bias vs market — it pushes too many games into the "UNDER
relative to market" zone with inflated confidence.

## Practical Implication

**The model's probability RANKINGS are useful even though the MAGNITUDES
are not calibrated.** Higher p_under → higher actual under rate. The
0.60+ tier (actual 57.7%) materially outperforms the 0.57–0.60 tier
(actual 54.2%). The tier structure is working correctly for signal
selection despite the absolute calibration being off.

A post-hoc calibration (e.g., Platt scaling or isotonic regression)
could compress the probabilities toward 50% and improve the Brier score,
but would not change signal selection since rankings are preserved.
