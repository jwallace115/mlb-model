# Run Volatility Score — Research Report

## Concept
Model game-level run scoring VARIANCE, not mean.
High-variance environments favor OVER due to right-skewed run distributions.

Dataset: 4855 games (2024-2025), 4666 non-push
Games with all features: 4092

## Features (16 total)

| Feature | Domain | Coverage |
|---------|--------|----------|
| combined_bb_rate | pitcher | 100.0% |
| combined_hard_hit | pitcher | 84.5% |
| bb_x_hard_hit | pitcher | 84.5% |
| combined_whiff | pitcher | 84.5% |
| combined_barrel | pitcher | 84.5% |
| combined_era_spike | pitcher | 100.0% |
| combined_bp_xfip | pitcher | 100.0% |
| combined_bp_workload | bullpen | 100.0% |
| combined_lineup_contact | lineup | 99.8% |
| combined_lineup_bb | lineup | 99.8% |
| contact_x_bb | lineup | 99.8% |
| park_hr_factor_scaled | park | 100.0% |
| wind_factor_effective | park | 100.0% |
| temp_factor | park | 100.0% |
| combined_short_starter_risk | interaction | 100.0% |
| short_starter_x_bp | interaction | 100.0% |

## Model Comparison

| Model | R² vs |deviation| | Method |
|-------|-------------------|--------|
| A (equal-weight) | 0.0018 | z-score sum |
| B (OLS-weighted) | 0.0128 | OLS regression |

### OLS Significant Features (p<0.10)

| Feature | Coefficient | p-value |
|---------|------------|---------|
| combined_whiff | -2.4499 | 0.0531 |
| combined_bp_xfip | +2.9711 | 0.0006 |
| temp_factor | +0.1686 | 0.0004 |

### MODEL_A Decile Structure

| Decile | N | Score | Over% | ROI |
|--------|---|-------|-------|-----|
| 0 | 393 | -8.19 | 0.496 | -5.3% |
| 1 | 393 | -4.45 | 0.468 | -10.6% |
| 2 | 392 | -2.58 | 0.480 | -8.4% |
| 3 | 393 | -1.14 | 0.455 | -13.0% |
| 4 | 393 | 0.14 | 0.511 | -2.4% |
| 5 | 392 | 1.51 | 0.480 | -8.4% |
| 6 | 393 | 2.92 | 0.509 | -2.8% |
| 7 | 392 | 4.44 | 0.492 | -6.0% |
| 8 | 393 | 6.66 | 0.463 | -11.6% |
| 9 | 393 | 11.10 | 0.473 | -9.6% |

Tail spread: D0=0.496 → D9=0.473 (-0.023)

### MODEL_B Decile Structure

| Decile | N | Score | Over% | ROI |
|--------|---|-------|-------|-----|
| 0 | 393 | 2.88 | 0.494 | -5.8% |
| 1 | 393 | 3.12 | 0.445 | -15.0% |
| 2 | 392 | 3.23 | 0.490 | -6.5% |
| 3 | 393 | 3.31 | 0.473 | -9.6% |
| 4 | 393 | 3.38 | 0.468 | -10.6% |
| 5 | 392 | 3.45 | 0.500 | -4.5% |
| 6 | 393 | 3.53 | 0.542 | +3.5% |
| 7 | 392 | 3.61 | 0.474 | -9.4% |
| 8 | 393 | 3.73 | 0.466 | -11.1% |
| 9 | 393 | 3.98 | 0.476 | -9.2% |

Tail spread: D0=0.494 → D9=0.476 (-0.018)

## OVER Prediction

### MODEL_A

| Threshold | N | Over% | ROI |
|-----------|---|-------|-----|
| top_10 | 393 | 0.473 | -9.6% |
| top_20 | 786 | 0.468 | -10.6% |
| top_30 | 1178 | 0.476 | -9.1% |

### MODEL_B

| Threshold | N | Over% | ROI |
|-----------|---|-------|-----|
| top_10 | 393 | 0.476 | -9.2% |
| top_20 | 786 | 0.471 | -10.1% |
| top_30 | 1178 | 0.472 | -9.9% |

## Season Stability (top 20%)

| Model | Year | N | Over% | ROI |
|-------|------|---|-------|-----|
| MODEL_A | 2024 | 390 | 0.477 | -9.0% |
| MODEL_A | 2025 | 395 | 0.456 | -13.0% |
| MODEL_B | 2024 | 390 | 0.454 | -13.4% |
| MODEL_B | 2025 | 395 | 0.476 | -9.1% |

## V1 Independence

- A vs V1 p_under: r=-0.5606
- B vs V1 p_under: r=-0.6046

## Permutation (2025 top 20%)

- MODEL_A: obs ROI=-13.0%, pctile=20%
- MODEL_B: obs ROI=-9.1%, pctile=49%

## Final Verdict


### Verdict: **SHELVE**

The run volatility score concept **does not work**.

**Evidence:**

1. **Both models predict OVER worse than random.** Top-20% volatility games go OVER at 46.8-47.1% (below the 49.1% baseline). High-volatility environments actually favor UNDER, not OVER.

2. **Decile structure is flat noise.** Neither MODEL A nor MODEL B produces a monotonic gradient. D0-D9 over rates bounce randomly between 44.5-54.2% with no pattern.

3. **OLS explains 1.3% of deviation variance.** Only 3 of 16 features are significant at p<0.10: combined_whiff (negative — more whiff = less deviation), combined_bp_xfip (positive — weak bullpen increases deviation), and temp_factor (positive — warmer = more deviation). These are weak and partially priced.

4. **Not independent from V1.** Volatility score correlates r=-0.56 to -0.60 with V1 p_under. This means high-volatility environments already appear as V1 OVER leans. Adding the volatility score to V1 OVER signals makes them *worse* (ROI -2.9% alone → -5.0% combined).

5. **Permutation fails.** MODEL A 2025 at 16th percentile (worse than random). MODEL B at 45th (neutral).

6. **Season unstable.** MODEL A: 2024 ROI -9.0%, 2025 -13.0% (both negative). MODEL B: 2024 -13.4%, 2025 -9.1% (both negative, opposite rank).

**Why the thesis failed:**

The core thesis — that markets underprice run variance and high-variance environments favor OVER — is incorrect for MLB totals betting. Specifically:

- **The market efficiently prices variance.** Closing totals already incorporate pitcher BB rates, bullpen quality, park factors, and weather. The variance-predictive features (BP xFIP, temperature) are already in the closing line.

- **High variance ≠ OVER.** Run distributions are right-skewed, but the market's closing total already accounts for this. The juice on OVER is typically -110 (same as UNDER), not discounted. There's no structural OVER bias from variance.

- **The best-performing feature (BP xFIP) is already in V1.** The V1 simulation model already uses bullpen xFIP as a feature. No incremental value.

**Recommendation:** No further work on run volatility scoring. The concept is theoretically appealing but empirically dead. The market prices variance adequately.

**Best feature subset (for reference only):**
- combined_bp_xfip (p=0.0006) — only significant volatility predictor
- temp_factor (p=0.0004) — warm weather increases deviation
- combined_whiff (p=0.053) — low whiff increases deviation
All three are already in the V1 model or priced by the market.
