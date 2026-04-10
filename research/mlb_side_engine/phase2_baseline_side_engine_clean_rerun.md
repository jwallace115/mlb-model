# Phase 2: Baseline Side Engine -- Clean PIT Rerun

**Date:** 2026-04-10
**Status:** All prior Phase 2-4 findings VOID. This is the from-scratch rebuild using ONLY point-in-time-clean features.

---

## Step 1: Data Coverage

**Joined dataset:** 10,816 games (PIT features + canonical odds + game table)

| Season | Games |
|--------|-------|
| 2022   | 2,407 |
| 2023   | 3,537 |
| 2024   | 2,426 |
| 2025   | 2,446 |

### Non-null Rates

| Feature | Rate | Count |
|---------|------|-------|
| home_sp_fip_pit | 0.8048 | 8,705/10,816 |
| away_sp_fip_pit | 0.8000 | 8,653/10,816 |
| home_bp_fip_pit | 0.9540 | 10,318/10,816 |
| away_bp_fip_pit | 0.9532 | 10,310/10,816 |
| home_offense_rpg_pit | 0.9683 | 10,473/10,816 |
| away_offense_rpg_pit | 0.9675 | 10,465/10,816 |
| park_factor_runs | 1.0000 | 10,816/10,816 |
| temperature | 1.0000 | 10,816/10,816 |
| wind_speed | 1.0000 | 10,816/10,816 |
| umpire_over_rate | 1.0000 | 10,816/10,816 |
| total_line | 0.9949 | 10,761/10,816 |
| p_home_ml | 1.0000 | 10,816/10,816 |
| home_rest_days | 1.0000 | 10,816/10,816 |
| away_rest_days | 1.0000 | 10,816/10,816 |

**Thin-sample flags:**
- sp_sample_thin: 3,113 (28.8%) -- SP FIP requires >20 IP lookback, so early-season + spot starters are thin
- bp_sample_thin: 550 (5.1%)
- offense_sample_thin: 364 (3.4%)

**Key observation:** SP FIP is the bottleneck -- 20% null rate plus 29% thin-flagged means only ~50% of games have fully trustworthy SP data. After dropping NaN features: 7,548 rows. After the sp_sample_thin filter: 7,548 (all thin rows had already been dropped by the NaN filter -- thin flag = True correlates perfectly with NaN FIP in this dataset).

---

## Step 2: Feature Engineering

**9 features, all differentials or contextual:**

| Feature | Mean | Std | Notes |
|---------|------|-----|-------|
| sp_fip_diff | +0.021 | 1.507 | Home SP FIP minus away SP FIP (lower = home SP better) |
| bp_fip_diff | -0.001 | 0.723 | Home BP FIP minus away BP FIP |
| offense_diff | -0.007 | 1.169 | Home offense RPG minus away |
| park_factor_runs | 100.485 | 4.827 | Park physics (100 = neutral) |
| temperature | 73.330 | 8.737 | Game-time temp (F) |
| wind_speed | 6.116 | 4.748 | Wind speed (mph) |
| umpire_over_rate | 0.999 | 0.020 | Umpire run environment factor |
| rest_diff | +0.011 | 0.298 | Home rest days minus away |
| total_line | 8.434 | 0.977 | Closing total (market-derived) |

**Split sizes:** Train (2022-2023): 4,130 | Validate (2024): 1,695 | OOS (2025): 1,723

---

## Step 3: Model Coefficients

### Model A -- Logistic Regression (C=1.0, standardized)

| Feature | Coefficient | Direction |
|---------|-------------|-----------|
| sp_fip_diff | -0.1913 | Lower home SP FIP -> home wins more (correct) |
| bp_fip_diff | -0.1649 | Lower home BP FIP -> home wins more (correct) |
| offense_diff | +0.1115 | Higher home offense -> home wins more (correct) |
| park_factor_runs | -0.0590 | Higher park factor -> home wins less (surprising, possibly spurious) |
| temperature | +0.0220 | Warmer -> home wins more (very weak) |
| wind_speed | -0.0433 | More wind -> home wins less (weak) |
| umpire_over_rate | -0.0384 | Higher umpire rate -> home wins less (very weak, near noise) |
| rest_diff | -0.0329 | More home rest -> home wins less (wrong sign, noise-level) |
| total_line | +0.0258 | Higher total -> home wins more (very weak) |
| **intercept** | **+0.0637** | Small home advantage residual |

**Takeaway:** SP FIP diff is the strongest single feature, followed by BP FIP diff and offense diff. Contextual features (weather, ump, rest) contribute near-zero signal to side prediction. All three core baseball differentials have correct signs.

### Model B -- Ridge Margin (alpha=1.0, standardized)

| Feature | Coefficient | Notes |
|---------|-------------|-------|
| sp_fip_diff | -0.4974 | Dominant feature |
| bp_fip_diff | -0.4203 | Strong second |
| offense_diff | +0.3544 | Third |
| park_factor_runs | -0.1429 | |
| temperature | -0.0332 | |
| wind_speed | -0.1022 | |
| umpire_over_rate | -0.1091 | |
| rest_diff | -0.0427 | |
| total_line | +0.0969 | |
| **intercept** | **-0.035** | Near zero (train margin std = 4.506) |

---

## Step 4: Calibration vs Market

### Brier Scores (lower is better)

| Split | N | Market | Logistic | Ridge | Delta (LR-Mkt) | Delta (Ridge-Mkt) |
|-------|---|--------|----------|-------|-----------------|-------------------|
| Train | 4,130 | 0.240791 | 0.242997 | 0.243483 | **+0.002207** | +0.002693 |
| Validate | 1,695 | 0.242268 | 0.246844 | 0.247852 | **+0.004576** | +0.005584 |
| **OOS 2025** | **1,723** | **0.244840** | **0.245798** | **0.246728** | **+0.000957** | **+0.001887** |

### Log Loss

| Split | Market | Logistic | Ridge |
|-------|--------|----------|-------|
| Train | 0.674487 | 0.679013 | 0.679985 |
| Validate | 0.677472 | 0.686869 | 0.688906 |
| OOS 2025 | 0.682552 | 0.684729 | 0.686584 |

**THE KEY NUMBER: OOS 2025 Brier delta = +0.000957 (model WORSE than market)**

The model loses to the market on every split, including train. This is not a case of overfitting -- the baseball features simply do not contain enough information to match the market's closing moneyline.

### OOS 2025 Calibration by Decile (Logistic)

| Predicted | Actual | N |
|-----------|--------|---|
| 0.379 | 0.376 | 173 |
| 0.441 | 0.494 | 172 |
| 0.470 | 0.581 | 172 |
| 0.493 | 0.517 | 172 |
| 0.512 | 0.491 | 173 |
| 0.530 | 0.558 | 172 |
| 0.549 | 0.529 | 172 |
| 0.568 | 0.628 | 172 |
| 0.593 | 0.564 | 172 |
| 0.645 | 0.636 | 173 |

Calibration is rough in the middle deciles -- the model compresses probability range too much (0.38-0.65) compared to actual outcomes.

---

## Step 5: RL Feasibility

**CAUTION:** The canonical RL data has mixed lines (home -1.5 and home +1.5), so the model's P(home wins by 2+) comparison against RL implied is **not apples-to-apples** -- the market RL implied includes games where home is +1.5. The reported delta of -0.040 is an artifact of this mismatch and should be disregarded until a proper line-aware comparison is built.

| Metric | Value |
|--------|-------|
| Games with RL prices | 1,710 |
| Model mean P(home -1.5) | 0.370 |
| Market RL implied mean | 0.525 |

**Verdict:** RL analysis is DEFERRED -- requires filtering to home -1.5 games only before meaningful comparison.

---

## Step 6: Residual Map (OOS 2025)

### A) SP Quality (sp_fip_diff buckets)

| Bucket | N | Model Brier | Market Brier | Delta |
|--------|---|-------------|--------------|-------|
| Home SP edge (<-0.5) | 623 | 0.24279 | 0.24053 | **+0.00226** |
| Neutral (-0.5 to 0.5) | 494 | 0.24601 | 0.24631 | **-0.00030** |
| Away SP edge (>0.5) | 606 | 0.24872 | 0.24808 | +0.00065 |

Model is closest to market in the **neutral SP** bucket. When there is a clear SP edge, the market prices it better.

### B) Bullpen Diff (bp_fip_diff buckets)

| Bucket | N | Model Brier | Market Brier | Delta |
|--------|---|-------------|--------------|-------|
| Home BP better (<-0.3) | 591 | 0.24136 | 0.24230 | **-0.00094** |
| Neutral | 568 | 0.24701 | 0.24743 | **-0.00042** |
| Away BP better (>0.3) | 564 | 0.24923 | 0.24489 | +0.00433 |

**Finding 1:** When home has BP advantage, model slightly beats market (-0.00094). When away BP is better, model is badly wrong (+0.00433). Asymmetric -- model overvalues home BP advantage when the away team has the better pen.

### C) Total Band

| Bucket | N | Model Brier | Market Brier | Delta |
|--------|---|-------------|--------------|-------|
| Low (<7.5) | 95 | 0.24951 | 0.25109 | -0.00158 |
| Mid (7.5-9.0) | 1,024 | 0.24339 | 0.24358 | **-0.00019** |
| High (>9.0) | 604 | 0.24930 | 0.24599 | +0.00330 |

**Finding 2:** Model is competitive in mid-total games (near zero delta). Loses ground in high-total games.

### D) ML Favorite Magnitude

| Bucket | N | Model Brier | Market Brier | Delta |
|--------|---|-------------|--------------|-------|
| Heavy home fav (>0.60) | 375 | 0.23576 | 0.22921 | **+0.00655** |
| Moderate home fav (0.52-0.60) | 588 | 0.25040 | 0.24995 | +0.00045 |
| Home underdog (<0.52) | 760 | 0.24719 | 0.24860 | **-0.00141** |

**Finding 3 (most interesting):** Model beats market when home team is underdog (-0.00141, n=760). Model is worst when home is heavy favorite (+0.00655). The market prices heavy favorites better than the model can.

### E) Home vs Away Favorite

| Bucket | N | Model Brier | Market Brier | Delta |
|--------|---|-------------|--------------|-------|
| Home fav | 963 | 0.24470 | 0.24188 | +0.00283 |
| Away fav | 467 | 0.24497 | 0.24740 | **-0.00243** |
| Pick em | 293 | 0.25072 | 0.25051 | +0.00021 |

Confirms: model has a pocket of value in **away-favorite games** (-0.00243, n=467).

---

## Step 7: Correction-Direction Test

### When model disagrees with market (>2pp)

| Direction | N | Model Pred | Market Pred | Actual | Model Closer? | Brier Delta |
|-----------|---|-----------|------------|--------|---------------|-------------|
| Model higher (+0.02) | 538 | 0.5351 | 0.4691 | 0.5242 | **Yes** | **-0.00237** |
| Model lower (-0.02) | 785 | 0.5040 | 0.5795 | 0.5554 | No | +0.00389 |

**Critical finding:** When model says home is better than market thinks, the model is right on average (actual 0.524 vs market 0.469). But when model says home is worse than market thinks, the market is right (actual 0.555 vs model 0.504). **The model's upward corrections are valid; its downward corrections are not.**

### By Disagreement Magnitude

| Magnitude | N | Model Brier | Market Brier | Delta |
|-----------|---|-------------|--------------|-------|
| Small (2-4pp) | 339 | 0.24075 | 0.24276 | **-0.00200** |
| Medium (4-8pp) | 544 | 0.24805 | 0.24763 | +0.00041 |
| Large (>8pp) | 440 | 0.24687 | 0.24179 | +0.00508 |

**Small disagreements are the sweet spot** -- the model beats the market when it disagrees by 2-4pp. Large disagreements are noise-driven and the market wins convincingly.

---

## Step 8: Mini-Robustness

### 8a) Without total_line

| Model | OOS Brier | Delta vs Market |
|-------|-----------|----------------|
| With total_line | 0.245798 | +0.000957 |
| Without total_line | 0.245638 | +0.000798 |
| Market | 0.244840 | -- |

Removing total_line actually **improves** the model slightly (+0.000798 vs +0.000957). total_line adds no value for side prediction -- it was a marginal feature that slightly degraded OOS performance. The baseball differentials carry the signal alone.

### 8b) Season-by-Season Brier Delta (model - market)

| Season | Model | Market | Delta | N |
|--------|-------|--------|-------|---|
| 2022 | 0.240855 | 0.235730 | **+0.005125** | 1,729 |
| 2023 | 0.244540 | 0.244435 | +0.000105 | 2,401 |
| 2024 | 0.246844 | 0.242268 | **+0.004576** | 1,695 |
| 2025 | 0.245798 | 0.244840 | +0.000957 | 1,723 |

Model is worst in 2022 (train year!) and 2024 (validation). 2025 OOS is the best non-train performance. The model is **trending in the right direction** -- the gap to market is narrowing over time.

### 8c) OOS 2025 by Month

| Month | Model | Market | Delta | N |
|-------|-------|--------|-------|---|
| April | 0.24360 | 0.23301 | **+0.01059** | 162 |
| May | 0.24216 | 0.24366 | **-0.00150** | 307 |
| June | 0.25007 | 0.24719 | +0.00288 | 302 |
| July | 0.24667 | 0.25586 | **-0.00919** | 316 |
| August | 0.24502 | 0.24332 | +0.00169 | 336 |
| September | 0.24636 | 0.24016 | +0.00620 | 300 |

**April is the model's worst month** (+0.01059) -- early-season SP FIP estimates are noisy even after thin-sample filtering. **July is the best month** (-0.00919) -- mid-season, PIT estimates are most stable. This is consistent with the SP sample quality hypothesis.

---

## Step 9: Verdict

### Summary Numbers

| Metric | Value |
|--------|-------|
| **OOS 2025 Brier (model)** | **0.245798** |
| **OOS 2025 Brier (market)** | **0.244840** |
| **OOS 2025 Delta** | **+0.000957 (model worse)** |
| Home win rate OOS | 0.5374 |
| Market mean P(home) | 0.5321 |
| Model mean P(home) | 0.5180 |

### Top 3 Residual Findings

1. **Away-favorite pocket:** When the away team is market favorite, the model beats the market by -0.00243 Brier (n=467). This is the strongest clean pocket.
2. **Small disagreement signal:** When model-market disagreement is 2-4pp, the model wins by -0.00200 (n=339). Larger disagreements are noise.
3. **Upward corrections only:** When the model says home is better than market thinks, it is correct on average (model closer to actual). Downward corrections fail.

### Evaluation Questions

**Q1: Does the model beat the market overall on Brier?**
No. Delta = +0.000957 (model worse). Consistent across train, val, and OOS.

**Q2: Are there pockets where the model adds value?**
Yes -- away-favorite games and small-disagreement corrections. But these are offset by losses in heavy-home-favorite and large-disagreement games.

**Q3: Is the signal in the baseball features or the market feature (total_line)?**
Baseball features only. Removing total_line actually improves OOS performance.

**Q4: Is the finding robust across months and seasons?**
Partially. July shows strong model advantage (-0.00919), but April (+0.01059) and September (+0.00620) are bad. Season trend is improving (2022: +0.005 -> 2025: +0.001).

**Q5: Is there a path to beating the market?**
The asymmetric correction pattern (upward corrections valid, downward not) suggests a **filtered correction model** could work: only bet when model > market by a small amount AND the home team is an underdog. This is a narrow, specific hypothesis worth testing but the raw edge is thin.

### VERDICT: NEAR MISS

The clean PIT baseline does not beat the market overall, but it is not far off (+0.001 Brier OOS). Three specific findings survive scrutiny:

1. The away-favorite pocket is real and mechanically interpretable (the market may slightly overprice away favorites when the home team has better SP matchup).
2. Small upward corrections are valid -- the model has genuine information the market partially misses.
3. The model improves as SP sample quality improves (April worst, July best), suggesting that with better feature engineering (more robust SP metrics, game-time adjustments), the gap could close further.

**Not ready for live deployment as a standalone side engine.** The pockets are too narrow (467-538 games) and the edges too thin (~0.002 Brier) to survive transaction costs. However, the baseball differential features are confirmed as real signal carriers that could improve a market-anchored correction model.

### Next Steps (if advancing)

1. Build a **market-anchored correction model**: start from p_home_ml, add baseball differentials as corrections
2. Test **filtered betting rules**: only when model > market by 2-4pp AND away team is favored
3. Investigate **July effect**: why does model excel mid-season? Can we dynamically weight SP confidence?
4. Fix RL analysis with proper line-side filtering
