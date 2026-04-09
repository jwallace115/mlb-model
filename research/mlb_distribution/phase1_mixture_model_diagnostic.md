# Phase 1: Mixture Model Diagnostic for MLB Game Totals

**Date:** 2026-04-08
**Question:** Does MLB game scoring contain genuine latent mixture structure that a single distribution misses?
**Data:** `sim/data/game_table.parquet` -- 9,837 regular-season completed games (2022-2026), 9+ innings

---

## Phase 2: Empirical Distribution

| Statistic | Value |
|-----------|-------|
| N | 9,837 |
| Mean | 8.87 |
| Median | 8.00 |
| Std | 4.48 |
| Skewness | 0.764 |
| Excess Kurtosis | 0.752 |
| P(total <= 5) | 0.2512 |
| P(total <= 7) | 0.4358 |
| P(total >= 10) | 0.3898 |
| P(total >= 12) | 0.2484 |
| P(total >= 13) | 0.1999 |

The distribution is right-skewed with heavier tails than normal. Variance (20.1) exceeds the mean (8.87), confirming overdispersion relative to Poisson (variance/mean ratio = 2.26).

---

## Phase 3: Unimodality Test

**Hartigan dip test:** dip = 0.0502, p-value = 0.0000

The dip test rejects unimodality at any conventional significance level. However, this is a very large sample (N=9,837) and the dip statistic itself is small (0.05), meaning the departure from unimodality is statistically significant but not necessarily large in practical terms.

**KDE mode analysis:**
- Bandwidth 0.30: 1 mode at 7.2 (effectively unimodal)
- Bandwidth 0.15: 4 modes at 5.3, 7.0, 8.8, 29.0 (typical noise at fine bandwidth)

The KDE evidence points to a single broad mode near 7-8 runs, not a clearly bimodal shape.

---

## Phase 4: Model Fit Comparison

| Model | Params | LL | AIC | BIC |
|-------|--------|------|------|------|
| Single Poisson | 1 | -30,291 | 60,585 | 60,592 |
| Single Negative Binomial | 2 | -28,163 | 56,330 | 56,344 |
| 2-component Poisson mixture | 3 | -28,302 | 56,611 | 56,632 |
| 2-component NB mixture | 5 | -28,161 | 56,333 | 56,369 |
| 2-component Gaussian mixture | 5 | -28,303 | 56,615 | 56,651 |

**AIC improvements (positive = improvement):**

| Comparison | dAIC |
|------------|------|
| Single NB vs Single Poisson | +4,255 |
| 2-comp Poisson mix vs Single Poisson | +3,974 |
| 2-comp NB mix vs Single NB | **-3.1** |

### Key Finding

The single Negative Binomial dominates. It beats both the 2-component Poisson mixture (by AIC 281) and effectively ties the 2-component NB mixture (dAIC = -3.1, well within noise for 3 extra parameters). The massive Poisson-to-NB improvement (+4,255 AIC) reflects overdispersion, not mixture structure. Once overdispersion is handled by NB's extra parameter, adding mixture components provides zero incremental fit.

**2-component Poisson mixture parameters:** lambdas = [6.22, 12.58], weights = [0.583, 0.417]. This looks like two components, but it is simply the Poisson mixture's only way to approximate overdispersion -- it splits the mean into a low and high component to manufacture extra variance. The single NB achieves the same thing with r=6.99, which directly parameterizes the overdispersion.

**2-component NB mixture parameters:** mus = [6.54, 10.58], weights = [0.422, 0.578]. The two NB components partially overlap (means only 4 runs apart, both with substantial dispersion). The EM found a marginal split but AIC penalizes the 3 extra parameters -- net improvement is negative.

---

## Phase 5: Tail Calibration

### CDF Calibration (P(total <= t))

| t | Actual | Single Poisson | Single NB | 2-comp Poisson | 2-comp NB | |NB err| | |Mix2NB err| |
|---|--------|----------------|-----------|----------------|-----------|---------|------------|
| 3 | 0.1016 | 0.0232 | 0.0920 | 0.0781 | 0.0922 | 0.0095 | 0.0093 |
| 5 | 0.2512 | 0.1237 | 0.2404 | 0.2458 | 0.2427 | 0.0108 | 0.0085 |
| 7 | 0.4358 | 0.3392 | 0.4268 | 0.4440 | 0.4285 | 0.0090 | 0.0073 |
| 10 | 0.6772 | 0.7211 | 0.6836 | 0.6731 | 0.6818 | 0.0063 | 0.0046 |
| 13 | 0.8548 | 0.9324 | 0.8522 | 0.8382 | 0.8501 | 0.0026 | 0.0048 |
| 15 | 0.9184 | 0.9804 | 0.9174 | 0.9159 | 0.9163 | 0.0010 | 0.0020 |

### Upper Tail (P(total >= t))

| t | Actual | Single NB | 2-comp NB | |NB err| | |Mix2NB err| |
|---|--------|-----------|-----------|---------|------------|
| 12 | 0.2484 | 0.2496 | 0.2519 | 0.0012 | 0.0035 |
| 15 | 0.1125 | 0.1112 | 0.1129 | 0.0013 | 0.0003 |
| 18 | 0.0424 | 0.0440 | 0.0440 | 0.0016 | 0.0016 |
| 20 | 0.0232 | 0.0225 | 0.0219 | 0.0007 | 0.0013 |

**Tail calibration verdict:** The single NB and 2-component NB mixture are nearly identical in tail accuracy. Maximum absolute error for single NB is ~1.1pp (at total=5), and the mixture improves this by only 0.2pp. Nowhere does the mixture improve tail calibration by more than 2pp. Both models track the actual distribution well across the entire range.

---

## Phase 6: Conditional Mixture Analysis

### By Closing Total Band (8,747 games with closing lines)

| Band | N | Mean | Std | NB AIC | Mix2P AIC | dAIC |
|------|---|------|-----|--------|-----------|------|
| <7.5 | 678 | 7.38 | 3.80 | 3,645 | 3,648 | -3.4 |
| 7.5-8.5 | 3,050 | 8.30 | 4.24 | 17,095 | 17,164 | -69.1 |
| 8.5-9.5 | 3,696 | 9.09 | 4.49 | 21,243 | 21,373 | -129.4 |
| 9.5-10.5 | 922 | 9.99 | 4.45 | 5,296 | 5,312 | -16.2 |
| >=10.5 | 401 | 11.20 | 4.94 | 2,399 | 2,418 | -19.1 |

**Single NB wins in every closing-line band.** The dAIC is negative (favoring NB) across all segments, and substantially so in the larger bands.

### By Park Factor

| Segment | N | Mean | Std | NB AIC | Mix2P AIC | dAIC |
|---------|---|------|-----|--------|-----------|------|
| Low PF (<98) | 2,919 | 8.57 | 4.32 | 16,508 | 16,565 | -56.5 |
| Mid PF (98-102) | 3,879 | 8.81 | 4.41 | 22,113 | 22,209 | -95.8 |
| High PF (>102) | 2,908 | 9.27 | 4.69 | 16,915 | 17,036 | -120.8 |

**Single NB wins in every park factor segment.** The high-PF venues (including Coors) show even stronger NB dominance over the mixture.

### By Season

| Season | N | Mean | NB AIC | Mix2P AIC | dAIC |
|--------|---|------|--------|-----------|------|
| 2022 | 2,420 | 8.57 | 13,715 | 13,791 | -75.8 |
| 2023 | 2,427 | 9.24 | 14,074 | 14,144 | -69.5 |
| 2024 | 2,421 | 8.79 | 13,695 | 13,737 | -42.3 |
| 2025 | 2,427 | 8.90 | 13,992 | 14,083 | -91.4 |
| 2026 | 142 | 8.72 | 833 | 835 | -2.3 |

**Single NB wins in every season.** No evidence of mixture structure emerging in any particular year.

### Coors Field

N=325, mean=11.39, std=5.20. NB AIC=1,980, Mix2P AIC=1,988, dAIC=-8.0. Even the most extreme venue does not exhibit mixture structure.

---

## Phase 7: Covariate Check

**Can pregame features predict upper-tail membership (total >= 12)?**

Train: 2022-2024, Test: 2025+. Features: closing total, park factor.

| Model | AUC |
|-------|-----|
| Closing line only | 0.581 |
| Closing line + park factor | 0.583 |

AUC of 0.58 is weak but real -- the closing line provides modest separation of tail games. Adding park factor contributes essentially nothing beyond the line (lift = 0.002).

**Residual distribution (actual - closing):**
- Mean: +0.43 (slight under on closing lines)
- Std: 4.50
- Skewness: 0.782
- Excess kurtosis: 0.858
- D'Agostino normality test: p = 5.2e-52

The residuals are right-skewed and heavy-tailed, rejecting normality decisively. This is consistent with NB-style overdispersion around the closing line, not mixture structure. The positive skew means blowout games (high residuals) are more common than extreme pitcher duels.

---

## Decision

### CLOSE -- Single Negative Binomial is adequate.

**Reasoning:**

1. **AIC/BIC:** The 2-component NB mixture improves AIC by only 3.1 over single NB -- far below the >10 threshold for "material improvement." The BIC actually penalizes the mixture (worse by 25 points). The 2-component Poisson mixture is dominated by single NB everywhere.

2. **Tail calibration:** Maximum improvement from mixture is <0.3pp at any threshold. The single NB already calibrates within ~1pp across the entire range including deep tails (P(total >= 20) off by 0.07pp).

3. **Conditional analysis:** Single NB beats the mixture in every segment tested -- all 5 closing-line bands, all 3 park-factor segments, all 5 seasons, and even Coors Field in isolation. There is no hidden subpopulation where mixture structure emerges.

4. **What the data actually shows:** The overdispersion (variance/mean = 2.26) is the dominant feature, and it is fully captured by the NB's dispersion parameter (r=6.99). The Hartigan dip test rejects unimodality statistically (p<0.001), but this is a power artifact at N=9,837 -- the KDE shows a single broad mode near 7 runs. The "multimodality" is integer-valued data with a skewed shape, not latent subpopulations.

5. **Practical implication:** For the sim pipeline, modeling game totals as a single Negative Binomial (conditioned on pregame features via the Ridge model) is statistically sufficient. No mixture model extension is warranted. The residual analysis confirms that the spread around the closing line is overdispersed and right-skewed -- this is already handled by the NB error model with sigma=4.36 in the Phase 9 baseline.

**No follow-up work recommended.** This line of inquiry is closed.
