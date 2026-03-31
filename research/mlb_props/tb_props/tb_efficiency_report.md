# TB Props Market Efficiency Report

Dataset: 32756 matched TB prop records
Raw pulled: 41303 records, join rate: 78.9%
Date range: 2025-03-27 to 2025-09-27
Credits used: ~9,153

## Overall Efficiency by Line

| Line | N | Actual Over% | Implied Over% | Edge | Over ROI | Under ROI |
|------|---|-------------|--------------|------|----------|-----------|
| 0.5 | 6275 | 0.599 | 0.639 | -0.040 ** | -5.9% | -8.6% |
| 1.5 | 6392 | 0.357 | 0.409 | -0.051 ** | -12.5% | -0.4% |
| 2.5 | 6153 | 0.213 | 0.250 | -0.037 ** | -13.4% | -0.2% |
| 3.5 | 5838 | 0.149 | 0.182 | -0.033 ** | -16.4% | -0.0% |
| 4.5 | 5859 | 0.074 | 0.100 | -0.026 | -20.2% | +0.0% |
| 5.5 | 2230 | 0.047 | 0.104 | -0.058 ** | -56.4% | -0.0% |

## TB Distribution

| TB | Actual | Poisson |
|----|--------|---------|
| 0 | 0.388 | 0.226 |
| 1 | 0.252 | 0.336 |
| 2 | 0.145 | 0.250 |
| 3 | 0.065 | 0.124 |
| 4 | 0.077 | 0.046 |
| 4+ | 0.151 | 0.064 |

Mean: 1.487, Variance: 3.246 (Poisson var would be 1.487)
Variance/Mean ratio: 2.18 (>1 = overdispersed)

## Verdict

**INVESTIGATE** — pricing inefficiencies detected at one or more line values.
Largest edge: line 5.5, edge=-0.058

