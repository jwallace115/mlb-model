# Phase 5: Rolling Sigma Layer — Pregame Dynamic Sigma from Pitcher Variance

**Date:** 2026-04-08
**Question:** Does replacing the Phase 9 fixed sigma=4.361 with a pregame dynamic sigma driven by rolling pitcher variance improve tail calibration?
**Verdict:** CLOSE — variable sigma adds little; the signal is real but too weak and noisy to improve calibration out of sample.

---

## 1. Rolling Pitcher Variance Metrics

**Dataset:** 19,430 starter appearances across 2022-2025 from `mlb/data/pitcher_game_logs.parquet`.

For each starter, computed pregame-safe (shifted by 1) rolling 5-start metrics:
- `rolling_sd_5`: standard deviation of runs allowed over last 5 starts
- `rolling_var_5`: variance of runs allowed over last 5 starts
- `rolling_tail_rate`: proportion of last 5 starts with 6+ runs allowed
- `rolling_dom_rate`: proportion of last 5 starts with 0-1 runs allowed

**Coverage by month (representative):**

| Season | Month | Total | Has SD5 | Coverage |
|--------|-------|-------|---------|----------|
| 2024   | Apr   | 794   | 102     | 12.8%    |
| 2024   | May   | 818   | 624     | 76.3%    |
| 2024   | Jun   | 802   | 669     | 83.4%    |
| 2024   | Jul+  | 700+  | 600+    | 83-87%   |
| 2025   | Apr   | 782   | 115     | 14.7%    |
| 2025   | May+  | 750+  | 630+    | 80-86%   |

**Summary:** 69.8% overall coverage (13,566/19,430). April is a severe gap (~13% coverage); June onward stabilizes at 80-87%.

**League mean rolling_sd_5:** 1.871 (median 1.817, IQR 1.342-2.302).

---

## 2. Empirical 3x3 Game-Sigma Grid

4,280 games matched with both home and away starter variance metrics.
2,103 games also matched to closing totals from `sim/data/market_snapshots.parquet` (2024-2025 only).

Tercile cuts for rolling_sd_5: LOW <= 1.517, MED 1.517-2.121, HIGH > 2.121.

| Home \ Away | LOW             | MED             | HIGH            |
|-------------|-----------------|-----------------|-----------------|
| **LOW**     | N=495 sigma=4.52 | N=492 sigma=4.16 | N=468 sigma=4.83 |
| **MED**     | N=468 sigma=4.17 | N=458 sigma=4.39 | N=480 sigma=4.10 |
| **HIGH**    | N=503 sigma=4.73 | N=442 sigma=4.81 | N=474 sigma=4.79 |

**Key observation:** The grid does NOT show a clean monotonic pattern. HIGH/HIGH (sigma=4.79) is not the highest cell; LOW/HIGH (4.83) and HIGH/LOW (4.73) are comparable. The MED row actually has the lowest sigmas. This lack of monotonicity is the first red flag.

---

## 3. Model Fitting and OOS Evaluation

Three variable-sigma models fit on 2024 (N=1,072), evaluated OOS on 2025 (N=1,031):

### Model A — Additive
`game_sigma = 4.361 + 0.200*(home_sd5 - 1.871) + (-0.055)*(away_sd5 - 1.871)`

Note: the away weight is *negative*, contradicting the hypothesis that higher SP variance should increase game-level variance.

### Model B — Cell-based
Assign sigma from empirical 3x3 grid computed on 2022-2024.

### Model C — Max-based
`game_sigma = 4.361 + 0.060*(max(home_sd5, away_sd5) - 1.871)`

### OOS Negative Log-Likelihood (lower is better)

| Model              | OOS NLL  | Per Game | vs Fixed  |
|--------------------|----------|----------|-----------|
| Fixed sigma=4.361  | 3012.28  | 2.92171  | baseline  |
| Model A (additive) | 3013.89  | 2.92327  | **+1.61 worse** |
| Model B (cell)     | 3010.96  | 2.92042  | -1.32 better |
| Model C (max)      | 3011.88  | 2.92132  | -0.40 better |

**Model A degrades OOS.** Model B improves by 1.32 NLL points over 1,031 games (0.001 per game) — negligible. Model C is essentially tied with fixed.

---

## 4. Tail Calibration

### Fixed vs Cell-Based (Model B) on OOS 2025

| Threshold  | Actual  | Fixed Implied | Fixed Err | Cell Implied | Cell Err | Improvement |
|------------|---------|---------------|-----------|--------------|----------|-------------|
| +2 over    | 0.3007  | 0.3233        | 0.0226    | 0.3272       | 0.0265   | **-0.4pp worse** |
| +3 over    | 0.2435  | 0.2458        | 0.0023    | 0.2511       | 0.0076   | **-0.5pp worse** |
| -2 under   | 0.3162  | 0.3233        | 0.0071    | 0.3272       | 0.0110   | **-0.4pp worse** |
| -3 under   | 0.2250  | 0.2458        | 0.0207    | 0.2511       | 0.0260   | **-0.5pp worse** |

The cell-based model makes tail calibration *worse*, not better. Fixed sigma is already well-calibrated at +3 over (error = 0.2pp) and reasonably close elsewhere.

### By Cell Breakdown (P(total > close+2))

The cell-level errors are noisy and show no systematic pattern of improvement. Some cells improve slightly (e.g., LOW/MED, MED/LOW) while others worsen by more (e.g., LOW/HIGH, HIGH/HIGH).

---

## 5. Tail-Dispersion Proxy

### Quartile Analysis on OOS 2025

| Quartile   | N   | Resid Std | P(\|r\|>2) | P(\|r\|>3) | Mean SD5 |
|------------|-----|-----------|-----------|-----------|----------|
| Q1 (low)   | 258 | 4.334     | 0.6473    | 0.4922    | 1.219    |
| Q2          | 258 | 4.308     | 0.5969    | 0.4651    | 1.677    |
| Q3          | 257 | 4.584     | 0.6148    | 0.4708    | 1.991    |
| Q4 (high)  | 258 | 4.682     | 0.6085    | 0.4457    | 2.521    |

**Optimal sigma by extreme quartile:**
- Q1 (low variance SPs): optimal sigma = 4.329
- Q4 (high variance SPs): optimal sigma = 4.682

The effect exists — Q4 games have ~0.35 runs higher residual std than Q1 (8.0% of fixed sigma). But the relationship is **non-monotonic**: Q1 actually has *higher* tail rates than Q4 on the P(|r|>2) and P(|r|>3) metrics, contradicting the hypothesis.

### Decile Analysis

Residual std by decile of avg_sd5 shows no monotonic trend:

| Decile | Resid Std | P(\|r\|>3) |
|--------|-----------|-----------|
| D0     | 4.930     | 0.552     |
| D1     | 3.970     | 0.480     |
| D2     | 3.586     | 0.379     |
| D3     | 4.509     | 0.485     |
| ...    | ...       | ...       |
| D8     | 5.136     | 0.505     |
| D9     | 4.509     | 0.427     |

The pattern is essentially random. D0 (lowest pitcher variance) has one of the *highest* residual stds.

**Spearman correlation (avg_sd5 vs |residual|):** r = -0.022, p = 0.49 — no significant relationship.

---

## 6. Early-Season Sensitivity

### min5 vs min8 Coverage

Moving from min_periods=5 to min_periods=8 costs heavily in May (76% -> 39% coverage) and adds ~6-8pp loss through summer. Given that the signal is already weak, reducing coverage further is not justified.

### Prior-Season Bridge

Using the prior season's final rolling_sd_5 for early-season games:
- Bridges 2,541 of 5,864 missing observations (43.3%)
- Dramatically improves April coverage: 13% -> 79%
- **But correlation between prior_sd5 and first current_sd5 is r = 0.036** — essentially zero predictive value
- MAE = 0.796 runs (against a metric with std ~0.7)

Prior-season bridge provides coverage but not information. Starter variance does not persist meaningfully across seasons.

---

## 7. Deployment Framing

### Why the Signal Fails

The core hypothesis — that starters with volatile recent performance produce games with more total variance — is mechanically plausible but empirically negligible because:

1. **Starting pitchers account for ~40% of the game.** Even a pitcher who swings between 0 and 8 runs has that variance diluted by bullpen, offense, and park effects that are uncorrelated with SP variance history.

2. **The market already adjusts.** Closing totals incorporate SP quality. A volatile SP who just had a blowup gets a higher total posted, so the *residual* (actual - closing) already filters out the mean effect. What's left is pure noise that SP variance history cannot predict.

3. **5-start rolling windows are extremely noisy.** Variance of variance estimated from 5 observations has massive sampling error. The "signal" is mostly noise in the predictor itself.

4. **Non-persistence across seasons.** Prior-season bridge correlation of 0.036 confirms that pitcher variance is not a stable trait — it's dominated by matchup, form, and randomness.

### Effect Size

The maximum plausible effect is a 0.35-run shift in game-level sigma between extreme quartiles (4.33 vs 4.68). Even if this were perfectly estimated:
- It changes P(over by 3+) by about 1pp
- The NLL improvement is <0.002 per game
- This is smaller than the estimation noise in the variable sigma models themselves

---

## Decision: CLOSE

Rolling pitcher variance as a dynamic sigma driver is **closed**. The hypothesis fails on multiple independent tests:

1. **OOS NLL:** Best model (cell-based) improves by 0.001 NLL per game — effectively zero. Additive model actually degrades.
2. **Tail calibration:** Fixed sigma is *already better calibrated* than any variable-sigma approach at all four tail thresholds. No threshold improves by even 1pp; most get 0.4-0.5pp worse.
3. **Dispersion proxy:** No significant correlation between pitcher variance and game-level residuals (Spearman r = -0.02, p = 0.49).
4. **Non-monotonic grid:** The 3x3 empirical grid shows no clean pattern, with LOW/LOW having higher sigma than MED/MED.
5. **Bridge failure:** Zero cross-season persistence (r = 0.036) eliminates the metric as a stable pitcher trait.

---

## Answers

### 1. Genuine architectural improvement or marginal refinement?
Neither. It is a null result. The fixed sigma of 4.361 is already well-calibrated, and rolling pitcher variance does not contain usable information about game-level dispersion once you condition on the market closing line. The effect size (0.35 runs across extreme quartiles) is real but too small and too noisy to improve any downstream metric.

### 2. Which market benefits most?
None. The signal does not reach the threshold for actionable calibration improvement in any segment — not overs, not unders, not high-total games, not low-total games. The Spearman correlation is flat across all subgroups tested.

### 3. Correct sequencing for integration?
Do not integrate. If future work revisits game-level sigma modulation, more promising directions would be:
- **Park-weather interaction sigma:** e.g., Coors + wind games may have structurally higher variance than domed stadiums. These are environmental factors that the market may underprice in the tails.
- **Bullpen availability sigma:** games where both teams have depleted bullpens may have higher late-game variance. This at least has a mechanical pathway (worse relievers = more variance in innings 6-9).
- **Lineup-confirmed volatility:** platoon-heavy lineups facing opposite-hand starters may have bimodal outcomes that inflate sigma.

All of these would need the same >2pp tail calibration improvement bar to advance.
