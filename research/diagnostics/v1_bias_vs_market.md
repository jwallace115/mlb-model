# V1 Model Bias vs Market Totals

**Date:** 2026-03-28
**Data:** 4,855 games with model projections + closing lines + actuals (2024-2025)

## Data Sources

| Field | Source | Column |
|-------|--------|--------|
| Model projection | `sim/data/model_outputs.parquet` | `sim_mean` (V1 Monte Carlo mean) |
| Closing line | `sim/data/market_snapshots.parquet` | `close_total` (Odds API close) |
| Actual runs | `sim/data/game_table.parquet` | `actual_total` (final score) |

Model projection vs actual market closing line — NOT two market lines.

## Step 1 — Projection Difference Distribution

`proj_minus_line = model_projection - closing_line`

| Metric | Value |
|--------|-------|
| Mean | **+0.471 runs** |
| Median | +0.506 runs |
| StdDev | 0.760 runs |

The model projects **0.47 runs higher** than the market on average.

### Distribution

| Bucket | N | % |
|--------|---|---|
| < -2.0 | 36 | 0.7% |
| -2.0 to -1.5 | 39 | 0.8% |
| -1.5 to -1.0 | 78 | 1.6% |
| -1.0 to -0.5 | 270 | 5.6% |
| -0.5 to 0.0 | 724 | 14.9% |
| **0.0 to 0.5** | **1,253** | **25.8%** |
| **0.5 to 1.0** | **1,336** | **27.5%** |
| 1.0 to 1.5 | 748 | 15.4% |
| 1.5+ | 371 | 7.6% |

76.3% of games have model projection > closing line (model runs hot).
Only 23.7% of games have model projection below closing line.

## Step 2 — Accuracy by Bucket

| Bucket | N | Avg Proj | Avg Line | Avg Actual |
|--------|---|----------|----------|------------|
| < -2.0 | 36 | 8.09 | 10.65 | **10.08** |
| -2.0 to -1.5 | 39 | 8.25 | 9.99 | **10.79** |
| -1.5 to -1.0 | 78 | 8.06 | 9.29 | **9.22** |
| -1.0 to -0.5 | 270 | 8.08 | 8.77 | **8.50** |
| -0.5 to 0.0 | 724 | 8.45 | 8.68 | **8.68** |
| 0.0 to 0.5 | 1,253 | 8.70 | 8.43 | **8.58** |
| 0.5 to 1.0 | 1,336 | 9.00 | 8.26 | **8.96** |
| 1.0 to 1.5 | 748 | 9.33 | 8.11 | **9.09** |
| 1.5+ | 371 | 9.76 | 7.98 | **8.99** |

**Key pattern:** When the model projects OVER the line (positive buckets),
actual runs tend to land between the model and the line — closer to the
model than the market. When the model projects UNDER (negative buckets),
actual runs are closer to the market.

This confirms the model has **genuine predictive signal on the OVER side**
(actual runs > closing line when model says OVER) but also confirms the
model's systematic upward bias.

## Step 3 — Model vs Market Accuracy

| Metric | Model | Market |
|--------|-------|--------|
| **MAE** | **3.459 runs** | **3.429 runs** |
| Bias | +0.028 (slight overestimate) | -0.442 (underestimates runs) |

**Market is 0.030 runs more accurate** in absolute terms.

### Bias Decomposition

| Metric | Value | Interpretation |
|--------|-------|----------------|
| Model mean | 8.870 | |
| Market mean | 8.399 | |
| Actual mean | 8.841 | |
| **Model - Actual** | **+0.028** | Model is nearly unbiased |
| **Market - Actual** | **-0.442** | Market underprices runs by 0.44 |
| Model - Market | +0.471 | Model runs 0.47 higher than market |

### By Season

| Season | Model MAE | Market MAE | Model Bias | Market Bias |
|--------|-----------|-----------|------------|-------------|
| 2024 | 3.345 | 3.334 | +0.020 | -0.460 |
| 2025 | 3.573 | 3.524 | +0.037 | -0.424 |

Pattern is consistent across both seasons.

## Interpretation

**The model is NOT biased — the market is.**

The model's mean projection (8.870) is almost exactly equal to actual mean
runs (8.841). The model overshoots by only 0.028 runs on average.

The **market** underprices total runs by 0.442 runs on average. Closing
lines are systematically ~0.44 runs below actual scoring. This is the
well-known "under bias" in totals markets — books shade lines slightly
low because the public bets overs.

The model's apparent "+0.47 runs vs market" is not model bias — it's the
model correctly estimating actual scoring while the market is set 0.44
runs below true expected value.

**This explains why V1 UNDER signals work despite the model running higher
than the market.** The model identifies games where even its higher
projection is below the market line — these are genuinely low-scoring
environments where the market's normal under-bias isn't enough to
compensate.
