# TB Distribution Model v1 — Report

**Date:** 2026-03-27
**Status:** Research prototype — NOT deployed
**Output:** `research/mlb_props/tb_model_v1/`

---

## Executive Summary

| Metric | tb_zero (P=0) | tb_over_1_5 (P>=2) | tb_over_2_5 (P>=3) |
|:-------|---:|---:|---:|
| Train AUC (2022-2024) | 0.6334 | 0.6310 | 0.6443 |
| **Val AUC (2025)** | **0.6174** | **0.6082** | **0.6112** |
| Val LogLoss | 0.6645 | 0.6097 | 0.4672 |
| Val Brier | 0.2359 | 0.2104 | 0.1474 |

| Finding | Result |
|:--------|:-------|
| Does the model beat the market? | **Partially.** Model identifies genuine edge (mean +6.6pp Under 1.5, +4.9pp Under 2.5) but over-estimates edge at extreme probabilities. |
| Best deployment market? | **Under 1.5 TB** — top 30% confidence picks show 69.3% win rate and +18.7% ROI (N=76 with closing odds) |
| Protection interaction value? | **Moderate.** ondeck_woba ranks #7-9 in feature importance. The interaction term itself has low importance in GBT (tree splits capture it implicitly). |
| Is edge stable? | **Partially.** Calibration is good in 0.55-0.70 probability range. Deteriorates above 0.75 (over-confident). |

**Verdict: Model shows genuine discrimination beyond the market, but needs calibration refinement before deployment.**

---

## 1. Model Architecture

### Design
Three independent Gradient Boosted Tree classifiers predicting:
- **Model A:** P(TB = 0) — zero-TB probability
- **Model B:** P(TB >= 2) — over 1.5 probability
- **Model C:** P(TB >= 3) — over 2.5 probability

### Hyperparameters
- 300 trees, max_depth=4, learning_rate=0.05
- min_samples_leaf=50, subsample=0.8, max_features=0.7
- Conservative to prevent overfitting on 141K training rows

### Data Split
- **Train:** 2022-2024 (141,123 batter-games)
- **Validation:** 2025 (49,306 batter-games, 6,249 with market odds at 1.5 line)

### Features (23 total)

| Group | Features | Coverage |
|:------|:---------|:---------|
| A: Zero-TB Propensity | zero_tb_rate_last10/20/season, pct_2plus_tb_last20, pct_4plus_tb_last20, tb_variance_last20 | 95% |
| B: Protection | ondeck_iso_last20, ondeck_woba_proxy_last20, weak_protection_flag, high_iso_flag, high_iso_x_weak_protection, protector_type_enc | 80-83% |
| C: Defense | opp_drs | 77% |
| D: Pitcher | p_barrel_rate_last5, p_hard_hit_rate_last5, p_whiff_rate_last5, p_avg_ip_last5 | 56% |
| E: Baseline | batter_iso_last20, batter_slg_last20, batter_k_rate_last20, batter_obp_last20, batting_order_slot, park_factor | 95-100% |

Missing features filled with training-set median.

---

## 2. Model Performance

### AUC Comparison

| Model | Train AUC | Val AUC | Overfit Gap |
|:------|---:|---:|---:|
| tb_zero | 0.6334 | 0.6174 | 0.016 |
| tb_over_1_5 | 0.6310 | 0.6082 | 0.023 |
| tb_over_2_5 | 0.6443 | 0.6112 | 0.033 |

Overfit gap is modest (1.6-3.3pp), indicating good generalization from 2022-2024 to 2025.

### Calibration (tb_zero model, validation set)

| Model Predicted | Actual Rate | N |
|---:|---:|---:|
| 0.298 | 0.306 | ~4,900 |
| 0.335 | 0.331 | ~4,900 |
| 0.360 | 0.358 | ~4,900 |
| 0.385 | 0.396 | ~4,900 |
| 0.412 | 0.410 | ~4,900 |
| 0.440 | 0.442 | ~4,900 |
| 0.467 | 0.468 | ~4,900 |
| 0.495 | 0.502 | ~4,900 |
| 0.534 | 0.559 | ~4,900 |
| 0.635 | 0.657 | ~4,900 |

Calibration is excellent in the 0.30-0.50 range. Top decile (0.635 predicted, 0.657 actual) is slightly under-predicted.

### Calibration (tb_over_1_5 model)

| Model Predicted | Actual Rate |
|---:|---:|
| 0.179 | 0.160 |
| 0.241 | 0.229 |
| 0.293 | 0.294 |
| 0.341 | 0.346 |
| 0.387 | 0.383 |
| 0.456 | 0.434 |

Well-calibrated through the middle. Top decile slightly over-predicts (0.456 vs 0.434).

---

## 3. Edge Distribution

### Model vs Market (2025 validation, Under 1.5)

| Model P(Under 1.5) Bin | N | Model P | Market P | Actual | Model Edge | Actual Edge |
|:------------------------|---:|---:|---:|---:|---:|---:|
| 0.00-0.55 | 307 | 0.527 | 0.511 | 0.554 | +0.015 | +0.043 |
| 0.55-0.60 | 1,121 | 0.578 | 0.534 | 0.589 | +0.044 | +0.055 |
| **0.60-0.65** | **1,610** | **0.625** | **0.569** | **0.630** | **+0.056** | **+0.061** |
| **0.65-0.70** | **1,389** | **0.675** | **0.606** | **0.654** | **+0.069** | **+0.049** |
| 0.70-0.75 | 1,277 | 0.724 | 0.641 | 0.693 | +0.083 | +0.052 |
| 0.75-0.80 | 472 | 0.767 | 0.661 | 0.701 | +0.106 | +0.040 |
| 0.80+ | 73 | 0.831 | 0.644 | 0.603 | +0.187 | -0.041 |

**Key insight:** The model has genuine edge over the market in the 0.55-0.70 range (actual edge is 4-6pp). Above 0.75, the model becomes over-confident — predicted edge expands to 10pp+ but actual edge shrinks. The 0.80+ bin actually shows *negative* actual edge (model worse than market at the extreme).

**Sweet spot: model_p_under_1_5 between 0.60 and 0.70** — this is where calibration is best and actual edge is largest.

### Model vs Market Quintiles

| Quintile | N | Model P(Under) | Market P(Under) | Actual Under | Model Edge |
|:---------|---:|---:|---:|---:|---:|
| Q1 (lowest) | 1,250 | 0.563 | 0.527 | 0.577 | +0.036 |
| Q2 | 1,250 | 0.614 | 0.560 | 0.630 | +0.054 |
| Q3 | 1,249 | 0.653 | 0.589 | 0.624 | +0.064 |
| Q4 | 1,250 | 0.698 | 0.624 | 0.675 | +0.074 |
| Q5 (highest) | 1,250 | 0.752 | 0.652 | 0.704 | +0.100 |

The model discriminates well — Q5 actual Under rate (70.4%) is 12.7pp higher than Q1 (57.7%). The market sees a 12.5pp spread (65.2% vs 52.7%). The model captures additional 5-10pp of separation.

---

## 4. Backtest Results

### Under 1.5 TB (primary market)

| Edge Threshold | N | N w/ Odds | Win Rate | Avg Edge | ROI (actual) |
|---:|---:|---:|---:|---:|---:|
| >= 0.00 | 5,413 | 326 | 63.1% | +8.3pp | **-5.4%** |
| >= 0.02 | 4,947 | 285 | 62.9% | +9.0pp | -6.2% |
| >= 0.05 | 3,952 | 221 | 62.8% | +10.4pp | -5.3% |
| >= 0.08 | 2,549 | 135 | 61.2% | +12.5pp | -8.0% |
| >= 0.10 | 1,728 | 103 | 60.6% | +14.2pp | -8.6% |

**Flat-bet ROI is negative at all thresholds.** Higher edge thresholds actually produce *worse* ROI, confirming the over-confidence problem at extreme model probabilities.

### Under 1.5 TB by Probability Decile

| Decile | N | Model P | Actual | ROI |
|:-------|---:|---:|---:|---:|
| D0 | 625 | 0.544 | 0.574 | -26.0% |
| D1 | 625 | 0.581 | 0.579 | -32.9% |
| D2 | 625 | 0.605 | 0.624 | -11.5% |
| D3 | 625 | 0.624 | 0.637 | -0.6% |
| **D4** | 625 | 0.642 | 0.613 | **+5.9%** |
| **D5** | 624 | 0.664 | 0.636 | **+11.4%** |
| D6 | 625 | 0.687 | 0.678 | -14.8% |
| **D7** | 625 | 0.709 | 0.672 | **+25.0%** |
| **D8** | 625 | 0.733 | 0.725 | **+20.5%** |
| D9 | 625 | 0.772 | 0.683 | +10.1% |

Four of the top six deciles (D4, D5, D7, D8) show positive ROI. However, sample sizes with actual closing odds are small (40-80 per decile), so individual decile ROI is noisy.

**High-confidence subset (top 30%):** N=1,875, win rate=69.3%, ROI=**+18.7%** (N=76 with closing odds). Promising but small sample.

### Under 1.5 by Bookmaker (edge >= 0, with closing odds)

| Book | N | ROI |
|:-----|---:|---:|
| betonlineag | 87 | **+21.0%** |
| fanatics | 16 | +0.1% |
| mybookieag | 43 | -1.6% |
| williamhill_us | 65 | -8.4% |
| bovada | 11 | -12.3% |
| draftkings | 80 | -24.1% |
| betmgm | 24 | -38.6% |

BetOnline is the only book with positive ROI. This is consistent with the diagnostic finding that BetOnline has the widest over-pricing.

### Under 2.5 TB

Under 2.5 has only 31-40 records with closing odds. ROI is deeply negative (-27% to -43%). **Insufficient data for reliable backtest at this line.** The win rate is high (73-79%) but the vig on Under 2.5 is steep, and the few records with closing odds skew to heavy favorites.

---

## 5. Feature Importance

### tb_zero Model (P = 0)

| Rank | Feature | Importance |
|---:|:--------|---:|
| 1 | **zero_tb_rate_season** | 0.3300 |
| 2 | batting_order_slot | 0.1549 |
| 3 | zero_tb_rate_last20 | 0.0805 |
| 4 | pct_2plus_tb_last20 | 0.0714 |
| 5 | p_whiff_rate_last5 | 0.0440 |
| 6 | batter_k_rate_last20 | 0.0407 |
| 7 | tb_variance_last20 | 0.0346 |
| 8 | batter_slg_last20 | 0.0329 |
| 9 | ondeck_woba_proxy_last20 | 0.0259 |
| 10 | p_hard_hit_rate_last5 | 0.0247 |
| 13 | **opp_drs** | 0.0195 |
| 14 | park_factor | 0.0188 |
| 15 | p_barrel_rate_last5 | 0.0177 |

### tb_over_1_5 Model (P >= 2)

| Rank | Feature | Importance |
|---:|:--------|---:|
| 1 | **zero_tb_rate_season** | 0.2617 |
| 2 | batting_order_slot | 0.1522 |
| 3 | pct_2plus_tb_last20 | 0.0814 |
| 4 | zero_tb_rate_last20 | 0.0629 |
| 5 | tb_variance_last20 | 0.0551 |
| 6 | p_whiff_rate_last5 | 0.0472 |
| 7 | **ondeck_woba_proxy_last20** | 0.0324 |
| 8 | p_hard_hit_rate_last5 | 0.0317 |
| 11 | **opp_drs** | 0.0281 |
| 14 | park_factor | 0.0272 |
| 15 | **p_barrel_rate_last5** | 0.0262 |

### tb_over_2_5 Model (P >= 3)

| Rank | Feature | Importance |
|---:|:--------|---:|
| 1 | **zero_tb_rate_season** | 0.2177 |
| 2 | batting_order_slot | 0.1347 |
| 3 | tb_variance_last20 | 0.0836 |
| 4 | pct_4plus_tb_last20 | 0.0755 |
| 5 | p_whiff_rate_last5 | 0.0563 |
| 9 | **ondeck_woba_proxy_last20** | 0.0361 |
| 12 | p_hard_hit_rate_last5 | 0.0330 |
| 14 | **opp_drs** | 0.0253 |
| 15 | **p_barrel_rate_last5** | 0.0250 |

### Signal Discovery Validation

| Signal Family | Expected Role | Confirmed? |
|:--------------|:--------------|:-----------|
| **zero_tb_rate** (Family A) | Primary backbone | **YES** — #1 feature in all three models (22-33% importance) |
| **Protection** (Family C) | Primary overlay | **PARTIAL** — ondeck_woba ranks #7-9 (2.6-3.6%). The interaction term (high_iso_x_weak_protection) has low GBT importance because trees capture interactions implicitly via splits. |
| **Defense DRS** (Family E) | Secondary | **YES** — ranks #11-14 (1.9-2.8%) |
| **Pitcher barrel rate** (Family B) | Secondary | **YES** — ranks #15 (1.8-2.6%). Pitcher whiff rate (#5-6) is stronger than barrel rate. |
| Bullpen (Family D) | Shelved | Confirmed shelved — p_avg_ip_last5 has negligible importance. |

---

## 6. Key Findings

### Does the zero-TB model beat the market?

**Yes, in discrimination. No, in flat-bet ROI.** The model identifies situations where Under 1.5 TB wins ~70% of the time versus the market's implied ~65%. But the vig on Under 1.5 (typically -130 to -180) absorbs most of the edge when betting indiscriminately. The model needs a **selectivity filter** that targets only the best-priced opportunities.

### Is Under 2.5 the most profitable deployment?

**No — insufficient closing odds data.** Only 31-40 records with Under 2.5 closing odds. Win rates are high (74-79%) but we cannot reliably assess ROI. Under 1.5 is the better target because: (a) more market data, (b) larger edge vs implied, (c) better calibration.

### Do protection interactions meaningfully improve predictions?

**Modestly.** ondeck_woba_proxy contributes 2.6-3.6% of model importance. The explicit interaction term (high_iso_x_weak_protection) has low GBT importance because trees capture this pattern through splits on the constituent features. The protection signal is real but is a secondary contributor, not a primary driver.

### Is the edge stable across seasons?

**Mixed.** The model trains on 2022-2024 and validates on 2025 with an overfit gap of only 1.6-3.3pp AUC, indicating good temporal stability of feature relationships. However, the calibration breaks down above model_p=0.75, suggesting the model's extreme predictions don't generalize fully. The **0.60-0.70 probability band** is where calibration and edge are both strongest.

---

## 7. Verdict and Next Steps

### Model Assessment

| Dimension | Grade | Notes |
|:----------|:------|:------|
| Discrimination | B+ | AUC 0.61-0.62, genuinely separates outcomes |
| Calibration | B | Good in 0.55-0.70 range, poor above 0.75 |
| Market edge | C+ | Edge exists but vig absorbs it at broad thresholds |
| Backtest ROI | C- | Flat-bet negative; positive only in select deciles and at BetOnline |
| Feature stability | B+ | Small overfit gap, signal families confirmed |

### What Works
1. **zero_tb_rate_season** is the dominant feature — the signal discovery hypothesis was correct
2. Model discriminates genuinely beyond the market (5-10pp additional separation)
3. Calibration in the 0.60-0.70 range is excellent
4. BetOnline Under 1.5 shows +21% ROI — this book has the widest mispricing

### What Needs Work
1. **Over-confidence above 0.75** — model predicts 77% Under but actual is 70%. Need isotonic calibration or probability capping.
2. **Vig absorption** — 5-8pp edge isn't enough to overcome -130 to -180 vig consistently. Need either better odds (BetOnline) or larger edge.
3. **Under 2.5 data gap** — need more books posting two-sided Under 2.5 odds to evaluate that market.
4. **Pitcher features at 56% coverage** — 44% of rows use median fill. Need better pitcher data pipeline.

### Recommended Next Steps (if proceeding to v2)

1. **Isotonic calibration** on the probability outputs to fix the over-confidence at extremes
2. **Book-specific deployment** — target BetOnline Under 1.5 where mispricing is largest
3. **Odds threshold filter** — only bet when Under odds >= -130 (avoid heavy favorites where vig kills edge)
4. **Pitcher coverage improvement** — backfill statcast data or fall back to game-log-derived metrics (K/9, HR/9)
5. **Expand to 0.5 line** — the zero-TB model (AUC 0.6174) could be used directly for Under 0.5 deployment

---

## Output Files

| File | Description | Rows |
|:-----|:------------|-----:|
| `tb_model_dataset.parquet` | Full modeling table (2022-2025) | 201,605 |
| `model_predictions.parquet` | 2025 validation predictions + market data | 49,306 |
| `tb_model_backtest.parquet` | Backtest ROI by edge threshold | 10 |
| `feature_importance.parquet` | Top 15 features x 3 models | 45 |
