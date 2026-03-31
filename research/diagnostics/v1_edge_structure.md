# V1 Edge Structure Analysis

**Date:** 2026-03-28
**Data:** 2024-2025 resolved V1 signals (N=1,757 excl pushes)

## Field Definitions

| Field | Source | Description |
|-------|--------|-------------|
| `projection_total` | `sim/data/model_outputs.parquet` → `sim_mean` | V1 Monte Carlo simulation mean (model's projected total runs) |
| `closing_total` | `sim/data/market_snapshots.parquet` → `close_total` | Actual market closing line from Odds API |
| `edge` | `abs(sim_mean - close_total)` | Model-vs-market disagreement in runs |

These are model projection vs market line — NOT two market lines.

Note: `ridge_pred` and `sim_mean` are nearly identical (correlation ~0.999).
The model's mean projection is ~0.47 runs higher than the market on average
(8.87 vs 8.40), reflecting the model's systematic lean.

## Combined — All V1 Signals

| Edge Bucket | N | Win Rate | ROI |
|-------------|---|----------|-----|
| 0.00–0.25 | 330 | 53.0% | +1.2% |
| 0.25–0.75 | 701 | 55.2% | +5.4% |
| 0.75–1.25 | 340 | 55.9% | +6.7% |
| 1.25–1.75 | 263 | 51.3% | -2.0% |
| 1.75+ | 123 | 56.9% | +8.7% |

## V1 UNDER Signals Only (N=890)

| Edge Bucket | N | Win Rate | ROI |
|-------------|---|----------|-----|
| 0.00–0.25 | 245 | **58.8%** | **+12.2%** |
| 0.25–0.75 | 467 | 53.8% | +2.6% |
| 0.75–1.25 | 113 | **60.2%** | **+14.9%** |
| 1.25–1.75 | 34 | 47.1% | -10.2% |
| 1.75+ | 31 | **61.3%** | **+17.0%** |

## V1 OVER Signals Only (N=867)

| Edge Bucket | N | Win Rate | ROI |
|-------------|---|----------|-----|
| 0.00–0.25 | 85 | 36.5% | -30.4% |
| 0.25–0.75 | 234 | **58.1%** | **+11.0%** |
| 0.75–1.25 | 227 | 53.7% | +2.6% |
| 1.25–1.75 | 229 | 52.0% | -0.8% |
| 1.75+ | 92 | 55.4% | +5.8% |

## Edge Distribution (UNDER signals)

| Metric | Value |
|--------|-------|
| Mean | 0.535 runs |
| Median | 0.444 runs |
| P25 | 0.222 runs |
| P75 | 0.662 runs |
| Max | 3.029 runs |

## Key Findings

**1. UNDER signals: edge-performance is NON-MONOTONIC.**

The 0.00–0.25 bucket (smallest edge) has the second-highest
win rate (58.8%, +12.2% ROI). The 1.25–1.75 bucket collapses
(47.1%, -10.2% ROI). Then 1.75+ recovers (61.3%, +17.0%).

This is unusual — bigger edge does not consistently mean better
performance. The 1.25–1.75 dip (N=34) is likely noise, but the
pattern across 890 signals is not cleanly monotonic.

**2. OVER signals: very small edges are catastrophic.**

The 0.00–0.25 bucket has 36.5% win rate (-30.4% ROI). OVER
signals only work with edge >= 0.25. This confirms the model's
systematic OVER bias — when the model barely thinks OVER, it's
wrong 2/3 of the time.

**3. The UNDER sweet spot is broad.**

UNDER signals are profitable across most edge sizes (0.00–0.25,
0.25–0.75, 0.75–1.25, 1.75+). Only the 1.25–1.75 range dips.
The model's UNDER lean is real and not purely driven by large
disagreements with the market.

**4. OVER's sweet spot is narrow.**

OVER signals work best at 0.25–0.75 edge (+11.0%) and degrade
at larger edges. This suggests the model is less calibrated on
the OVER side — large OVER projections overshoot.

## Monotonicity Assessment

**UNDER: Non-monotonic.** Edge size does not reliably predict win rate.
The signal works well at both small and large edges but has a dead
zone at 1.25–1.75.

**OVER: Non-monotonic.** Best at moderate edges (0.25–0.75), degrades
at both extremes.

**Combined: Weakly positive trend** but the 1.25–1.75 dip breaks
clean monotonicity.
