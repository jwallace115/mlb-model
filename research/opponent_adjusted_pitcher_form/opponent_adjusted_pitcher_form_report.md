# Opponent-Adjusted Pitcher Form — Research Report

## Overview
Tested whether opponent-adjusted recent pitcher form predicts MLB totals /
market residuals better than raw recent pitcher form.

Evaluation window: 2024 + 2025 (4855 games, 4666 non-push)

## Source Data
- Game table: sim/data/game_table.parquet (9,715 games)
- Boxscores: sim/data/cache/boxscores/ (9,715 JSON files)
- Statcast: research/statcast_enrichment/pitcher_statcast_per_start_starters_only.parquet
- Closing lines: sim/data/bet_results.parquet (4,855 games)

## Methodology
```
adj_metric_start = raw_metric_start - (opponent_rolling_20g - league_avg)
```
- Opponent rolling: team K/AB, BB/AB over last 20 games (excluding current)
- Rolling form: last 3 and last 5 prior starts per pitcher
- Combined: average of home SP + away SP rolling form
- Strike% used as CSW proxy (strikes/pitches from boxscores)

## Step 5A — Univariate Results

| Family | Version | N | Resid Coef | Resid p | Total Coef | Total p | Under z | Under p |
|--------|---------|---|-----------|---------|-----------|---------|---------|---------|
| K_rate_last3 | RAW | 4471 | +0.22735 | 0.1241 | -6.628 | 0.0000 | +1.694 | 0.0902 |
| K_rate_last3 | ADJ | 4468 | +0.33137 | 0.0252 | -7.357 | 0.0000 | +2.301 | 0.0214 |
| K_rate_last5 | RAW | 4185 | +0.06373 | 0.7219 | -8.312 | 0.0000 | +0.433 | 0.6649 |
| K_rate_last5 | ADJ | 4182 | +0.10397 | 0.5619 | -8.207 | 0.0000 | +0.536 | 0.5919 |
| BB_rate_last3 | RAW | 4471 | +0.20455 | 0.4423 | +0.484 | 0.8371 | +0.752 | 0.4523 |
| BB_rate_last3 | ADJ | 4468 | +0.10259 | 0.6974 | +1.406 | 0.5465 | +0.366 | 0.7142 |
| BB_rate_last5 | RAW | 4185 | +0.20032 | 0.5513 | +0.877 | 0.7682 | +0.540 | 0.5891 |
| BB_rate_last5 | ADJ | 4182 | -0.07802 | 0.8153 | +2.975 | 0.3144 | -0.281 | 0.7785 |
| StrikePct_last3 | RAW | 4471 | +0.02455 | 0.9353 | -7.290 | 0.0064 | +0.124 | 0.9010 |
| StrikePct_last3 | ADJ | 4468 | +0.29863 | 0.2507 | -7.121 | 0.0019 | +1.018 | 0.3088 |
| StrikePct_last5 | RAW | 4185 | -0.11890 | 0.7458 | -7.225 | 0.0260 | -0.299 | 0.7650 |
| StrikePct_last5 | ADJ | 4182 | +0.02677 | 0.9335 | -5.024 | 0.0771 | -0.111 | 0.9116 |

## Step 5B — Paired Comparison

| Family | Significance | Effect Size | Stability | Decile Spread | ADJ Wins |
|--------|-------------|-------------|-----------|---------------|----------|
| K_rate_last3 | ADJ | ADJ | TIE | RAW | 2/4 |
| K_rate_last5 | ADJ | ADJ | TIE | ADJ | 3/4 |
| BB_rate_last3 | RAW | RAW | RAW | RAW | 0/4 |
| BB_rate_last5 | RAW | RAW | TIE | RAW | 0/4 |
| StrikePct_last3 | ADJ | ADJ | ADJ | ADJ | 4/4 |
| StrikePct_last5 | RAW | RAW | TIE | RAW | 0/4 |

### Year-by-Year Stability Detail

| Family | Version | 2024 Coef | 2024 p | 2025 Coef | 2025 p | Stable? |
|--------|---------|-----------|--------|-----------|--------|---------|
| K_rate_last3 | RAW | +0.22731 | 0.2874 | +0.23694 | 0.2478 | YES |
| K_rate_last3 | ADJ | +0.33964 | 0.1162 | +0.32306 | 0.1117 | YES |
| K_rate_last5 | RAW | +0.14065 | 0.5891 | +0.00467 | 0.9849 | YES |
| K_rate_last5 | ADJ | +0.18012 | 0.4944 | +0.03905 | 0.8731 | YES |
| BB_rate_last3 | RAW | +0.28523 | 0.4356 | +0.10073 | 0.7954 | YES |
| BB_rate_last3 | ADJ | +0.22693 | 0.5338 | -0.02874 | 0.9401 | NO |
| BB_rate_last5 | RAW | +0.12265 | 0.7921 | +0.26604 | 0.5852 | YES |
| BB_rate_last5 | ADJ | -0.09740 | 0.8352 | -0.06062 | 0.8988 | YES |
| StrikePct_last3 | RAW | -0.21469 | 0.6051 | +0.33016 | 0.4551 | NO |
| StrikePct_last3 | ADJ | +0.11516 | 0.7454 | +0.50105 | 0.1901 | YES |
| StrikePct_last5 | RAW | -0.19305 | 0.7017 | +0.00255 | 0.9962 | NO |
| StrikePct_last5 | ADJ | -0.07840 | 0.8585 | +0.14135 | 0.7635 | NO |

## Step 5C — Combined Models

| Family | Raw R² | Adj R² | Both R² | Raw p (combined) | Adj p (combined) |
|--------|--------|--------|---------|-----------------|-----------------|
| K_rate_last3 | 0.000549 | 0.001122 | 0.002163 | 0.0310 | 0.0072 |
| K_rate_last5 | 0.000034 | 0.000080 | 0.000197 | 0.4854 | 0.4095 |
| StrikePct_last3 | 0.000001 | 0.000295 | 0.001157 | 0.0497 | 0.0230 |
| StrikePct_last5 | 0.000025 | 0.000002 | 0.000171 | 0.4004 | 0.4352 |

## Step 6 — Strongest Metric Decile Structure

Best adjusted metric: **K_rate_last3** (combined_adj_k_rate_last3)
Best raw metric: **K_rate_last3** (combined_raw_k_rate_last3)

### ADJ K_rate_last3

| Decile | N | Mean | Mkt Resid | Under% | ROI @-110 |
|--------|---|------|----------|--------|-----------|
| 0 | 429 | 0.1043 | -0.0391 | 0.478 | -8.8% |
| 1 | 429 | 0.1358 | -0.0324 | 0.492 | -6.1% |
| 2 | 429 | 0.1530 | -0.0168 | 0.515 | -1.7% |
| 3 | 429 | 0.1662 | +0.0022 | 0.522 | -0.3% |
| 4 | 429 | 0.1789 | -0.0056 | 0.510 | -2.5% |
| 5 | 429 | 0.1915 | -0.0034 | 0.510 | -2.5% |
| 6 | 429 | 0.2050 | +0.0157 | 0.527 | +0.6% |
| 7 | 429 | 0.2209 | -0.0190 | 0.503 | -3.9% |
| 8 | 429 | 0.2413 | -0.0145 | 0.506 | -3.4% |
| 9 | 429 | 0.2814 | +0.0391 | 0.566 | +8.1% |

Market correlation: r=-0.3313, p=0.0000

### RAW K_rate_last3

| Decile | N | Mean | Mkt Resid | Under% | ROI @-110 |
|--------|---|------|----------|--------|-----------|
| 0 | 430 | 0.1376 | -0.0201 | 0.498 | -5.0% |
| 1 | 429 | 0.1678 | -0.0481 | 0.471 | -10.1% |
| 2 | 429 | 0.1846 | -0.0257 | 0.499 | -4.8% |
| 3 | 429 | 0.1988 | +0.0145 | 0.534 | +1.9% |
| 4 | 430 | 0.2121 | +0.0235 | 0.547 | +4.3% |
| 5 | 429 | 0.2253 | -0.0101 | 0.501 | -4.3% |
| 6 | 429 | 0.2385 | -0.0324 | 0.492 | -6.1% |
| 7 | 429 | 0.2539 | -0.0078 | 0.515 | -1.7% |
| 8 | 429 | 0.2737 | +0.0056 | 0.522 | -0.3% |
| 9 | 430 | 0.3137 | +0.0257 | 0.551 | +5.2% |

Market correlation: r=-0.3402, p=0.0000

## Step 7 — Final Verdict

### Q1: Does opponent-adjusted recent form beat raw recent form?

- Families where ADJ wins ≥3/4 criteria: 2/6
- Families where ADJ ties (2/4): 1/6
- Combined models where adj adds sig. value (p<0.10): 2/4

**Answer: MIXED — adjusted form improves some families but not all**

### Q2: Strongest metric family

- K_rate_last3: p=0.0252
- StrikePct_last3: p=0.2507
- K_rate_last5: p=0.5619
- BB_rate_last3: p=0.6974
- BB_rate_last5: p=0.8153
- StrikePct_last5: p=0.9335

### Q3: Does adjusted metric add value beyond raw metric?

- K_rate_last3: adj p in combined = 0.0072 → YES
- K_rate_last5: adj p in combined = 0.4095 → NO
- StrikePct_last3: adj p in combined = 0.0230 → YES
- StrikePct_last5: adj p in combined = 0.4352 → NO

### Q4: Classification by metric family

| Family | Verdict | Reason |
|--------|---------|--------|
| K_rate_last3 | **INVESTIGATE** | Only ADJ metric sig at p<0.05 (p=0.025). Adds value beyond raw in combined model (p=0.007). But individual R²=0.001 — tiny effect. Decile D9 (highest adj K%) shows +8.1% ROI but D0-D8 is noisy. Year-stable (POS both years) but neither year individually sig. |
| K_rate_last5 | **SHELVE** | p=0.56, no signal at any window |
| BB_rate_last3 | **SHELVE** | p=0.70, ADJ wins 0/4 criteria |
| BB_rate_last5 | **SHELVE** | p=0.82, ADJ wins 0/4 criteria |
| StrikePct_last3 | **SHELVE** | p=0.25 individually. Adds value in combined (p=0.023) but raw strike% has zero signal (p=0.94) so the "increment" is just the ADJ metric doing all the work — and it's not sig on its own. |
| StrikePct_last5 | **SHELVE** | p=0.93, no signal |

### Critical Observations

1. **Market correlation is very high.** Both raw and adj K_rate rolling features correlate r≈−0.33 with closing_total. The market already prices recent pitcher K rate heavily. Any signal is residual to a well-priced factor.

2. **R² is minuscule.** Best model (adj K_rate_last3) explains 0.11% of market residual variance. Even the combined raw+adj model only reaches 0.22%. This is noise-level explanatory power.

3. **Decile monotonicity is weak.** Adj K_rate_last3 shows under-performance in bottom decile (47.8%) and over-performance in top decile (56.6%), but deciles 1-8 are flat and non-monotonic. This is a tail-only effect, not a gradient.

4. **The adjustment DOES help for K_rate_last3 specifically.** Raw K_rate_last3 is not significant (p=0.12) while adjusted version is (p=0.025). The combined model confirms both contribute independently (raw p=0.031, adj p=0.007). This is genuine — opponent K-rate inflation is a real confounder.

5. **But the effect is too small for deployment.** The adj coefficient of +0.33 means a 1-standard-deviation increase in adj K_rate_last3 shifts the under outcome by ~0.016 probability points. Not tradeable.

### Overall Recommendation

**INVESTIGATE adj_k_rate_last3 only. SHELVE all other families.**

The opponent adjustment genuinely improves K_rate rolling form, but the effect size is too small for standalone signal use. The best path forward:

- Add `adj_k_rate_last3` to the scanner signal catalog as a candidate interaction feature
- Test it as an interaction term with existing V1 sim model features (particularly combined with S12 pitcher score)
- Do NOT pursue as a standalone overlay — insufficient edge magnitude
- The adjustment concept is sound but the marginal gain over raw is incremental, not transformative

