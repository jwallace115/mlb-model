# Phase 4 — F5 Settlement Divergence Analysis

**Date:** 2026-04-09
**Scope:** Do F5 and full-game line settlements create exploitable structural residuals conditional on observed F5 game state?
**Data:** 4,853 games (2024-2025) with closing totals from market_snapshots + actual F5/full-game totals from game_table.
**Limitation:** No historical F5 closing lines exist for 2022-2025. F5 proxy = closing_total x 0.5647 (empirical ratio). All results using APPROXIMATE F5 expectation.

---

## Phase 1 — Data Audit

| Item | Value |
|------|-------|
| game_table rows (2022-2025) | 9,715 |
| actual_f5_total coverage | 9,713 / 9,715 (99.98%) |
| market_snapshots (closing totals) | 4,855 (2024-2025 only) |
| Merged analysis set | 4,853 games |
| F5 closing lines available | **None** for 2022-2025 |
| 2026 F5 lines (mlb_sim_f5) | 373 rows, too few for analysis |

Empirical F5/Total ratio:
- Mean: 0.5647 (2024: 0.5630, 2025: 0.5664)
- Median: 0.5714
- Stable across seasons (+0.003 drift, negligible)
- Used as constant proxy: F5_expected = closing_total x 0.5647

---

## Phase 2 — Late-Runs Residual

Definitions:
- actual_late_runs = actual_total - actual_f5_total
- late_proxy = closing_total x 0.4353 (complement of F5 ratio)
- late_residual = actual_late_runs - late_proxy

| Metric | Value |
|--------|-------|
| Mean actual_late_runs | 3.870 |
| Mean late_proxy | 3.656 |
| Mean late_residual | +0.214 |
| Median late_residual | -0.264 |
| Std late_residual | 2.972 |
| Skewness | +1.102 (right tail) |

Season splits:
- 2024: mean_resid = +0.222, std = 2.878, n = 2,425
- 2025: mean_resid = +0.207, std = 3.064, n = 2,428

The +0.214 mean residual indicates late innings produce slightly more runs than a constant-ratio proxy predicts. The positive skew (+1.10) reflects blowout late innings pulling the mean above the median.

---

## Phase 3 — Conditional on Observed F5 State

F5 deviation = actual_f5_total - (closing_total x 0.5647).

### Categorical buckets

| F5 State | N | Mean Late Runs | Late Proxy | Residual | Over% |
|----------|---|----------------|------------|----------|-------|
| F5_VERY_LOW (dev <= -3) | 744 | 4.152 | 3.711 | +0.441 | 48.0% |
| F5_LOW (dev -3 to -2) | 564 | 3.938 | 3.630 | +0.308 | 44.7% |
| F5_NORMAL (dev -2 to +2) | 2,281 | 3.751 | 3.639 | +0.112 | 45.1% |
| F5_HIGH (dev +2 to +3) | 357 | 3.720 | 3.645 | +0.074 | 42.9% |
| F5_VERY_HIGH (dev >= +3) | 907 | 3.955 | 3.673 | +0.282 | 48.5% |

### Fine-grained 1-run bins

| F5 Dev Bin | N | Residual |
|------------|---|----------|
| -5 | 158 | +0.837 |
| -4 | 368 | +0.354 |
| -3 | 544 | +0.263 |
| -2 | 595 | +0.203 |
| -1 | 662 | +0.094 |
| 0 | 589 | +0.094 |
| +1 | 482 | +0.262 |
| +2 | 399 | +0.046 |
| +3 | 326 | +0.119 |
| +4 | 224 | +0.123 |
| +5 | 506 | +0.368 |

Key observation: **U-shaped residual pattern.** Both F5 extremes (way under and way over expected) produce higher late-run residuals than F5-normal games. The U-shape is confirmed by:

| |F5 deviation| threshold | N | Mean Residual |
|--------------------------|---|---------------|
| >= 0 (all) | 4,853 | +0.214 |
| >= 1 | 3,684 | +0.254 |
| >= 2 | 2,572 | +0.305 |
| >= 3 | 1,651 | +0.353 |
| >= 4 | 898 | +0.463 |
| >= 5 | 474 | +0.470 |

### Season stability

F5_VERY_LOW: 2024 +0.520 (n=365), 2025 +0.365 (n=379) -- stable positive
F5_LOW: 2024 +0.355 (n=271), 2025 +0.265 (n=293) -- stable positive
F5_NORMAL: 2024 +0.117 (n=1161), 2025 +0.108 (n=1120) -- stable near zero
F5_HIGH: 2024 +0.102 (n=183), 2025 +0.045 (n=174) -- stable near zero
F5_VERY_HIGH: 2024 +0.221 (n=445), 2025 +0.340 (n=462) -- stable positive

All states show the same sign in both seasons. The effect does not flip.

---

## Phase 4 — Team-Level

Home/away F5 splits are **not available** in game_table. Only aggregate actual_f5_total exists. Full-game margin used as proxy for game flow.

| Margin Bucket | N | Late Runs | Proxy | Residual |
|---------------|---|-----------|-------|----------|
| Blowout away (margin < -6) | 502 | 5.64 | 3.75 | +1.886 |
| Solid away (-6 to -3) | 816 | 4.07 | 3.66 | +0.415 |
| Close away (-3 to -1) | 951 | 3.56 | 3.66 | -0.107 |
| Close (-1 to +2) | 1,285 | 3.22 | 3.62 | -0.394 |
| Solid home (+2 to +4) | 596 | 3.31 | 3.65 | -0.334 |
| Blow home (+4 to +7) | 497 | 3.98 | 3.64 | +0.339 |
| Crush home (+7 to +99) | 206 | 5.58 | 3.68 | +1.902 |

Blowouts in either direction produce ~+1.9 run late residuals. Close games produce negative residuals (-0.3 to -0.4). This is consistent with: blowout managers empty benches, position players pitch, late-inning garbage runs inflate totals.

---

## Phase 5 — Seam Test (OLS with Controls)

### Model A: Categorical F5 state dummies

actual_late_runs ~ intercept + late_proxy + closing_total + f5_state dummies + park_factor_runs

| Feature | Coef | SE | t | p |
|---------|------|----|---|---|
| intercept | 1.535 | 0.885 | 1.74 | 0.083 |
| is_very_low | +0.345 | 0.126 | 2.74 | 0.006 ** |
| is_low | +0.195 | 0.140 | 1.40 | 0.163 |
| is_high | -0.035 | 0.169 | -0.21 | 0.837 |
| is_very_high | +0.175 | 0.117 | 1.50 | 0.134 |
| park_factor_runs | -0.008 | 0.010 | -0.85 | 0.396 |

R-squared = 0.0136

Only F5_VERY_LOW is significant at p < 0.01. F5_VERY_HIGH trends positive but does not clear p < 0.05.

### Model B: Continuous f5_deviation

| Feature | Coef | t | p |
|---------|------|---|---|
| f5_deviation (linear) | -0.008 | -0.58 | 0.560 |

Linear f5_deviation is **not significant**. This is expected given the U-shape (positive residual at both extremes cancels in a linear model).

### Model C: Quadratic f5_deviation

| Feature | Coef | SE | t | p |
|---------|------|----|---|---|
| f5_deviation | -0.038 | 0.016 | -2.38 | 0.017 * |
| f5_deviation^2 | +0.009 | 0.003 | 3.38 | 0.001 *** |

R-squared = 0.0140

The **quadratic term is highly significant** (p = 0.0007). This confirms the U-shape: extreme F5 deviations in either direction predict higher late-inning scoring after controlling for closing total and park factor. The negative linear term means slightly more late scoring when F5 goes low (mean-reversion effect).

---

## Phase 6 — Actionability

### OVER bets on late-inning runs (at -110)

| F5 State | W-L | Win% | ROI |
|----------|-----|------|-----|
| F5_VERY_LOW | 357-387 | 48.0% | -8.4% |
| F5_LOW | 252-312 | 44.7% | -14.7% |
| F5_NORMAL | 1029-1252 | 45.1% | -13.9% |
| F5_HIGH | 153-204 | 42.9% | -18.2% |
| F5_VERY_HIGH | 440-467 | 48.5% | -7.4% |

### UNDER bets on late-inning runs (at -110)

| F5 State | W-L | Win% | ROI |
|----------|-----|------|-----|
| F5_VERY_LOW | 387-357 | 52.0% | -0.7% |
| F5_LOW | 312-252 | 55.3% | +5.6% |
| F5_NORMAL | 1252-1029 | 54.9% | +4.8% |
| F5_HIGH | 204-153 | 57.1% | +9.1% |
| F5_VERY_HIGH | 467-440 | 51.5% | -1.7% |

**Critical note:** The universal UNDER bias (all states show UNDER win% > 50%) is an artifact of the proxy construction. The late_proxy uses a constant ratio (0.4353), while actual late scoring has a positively skewed distribution. The median residual is -0.264 (negative), meaning most games have fewer late runs than average, but the right tail (blowouts) pulls the mean positive. This is a distributional artifact, NOT an exploitable edge against actual live markets.

The relative differences between states are meaningful (F5_HIGH under-rate 57.1% vs F5_VERY_HIGH 51.5%), but the absolute levels cannot be used for ROI estimation without actual live market F5 totals and live full-game lines.

---

## Phase 7 — Connection to Path-Tree

### Path-tree reference finding
Blowout branches in the Phase 3 path-tree analysis produced +2.95 run over-bias on full-game totals.

### This analysis

| Condition | N | Late Residual |
|-----------|---|---------------|
| F5 extreme (|dev| >= 3) | 1,651 | +0.353 |
| Full-game blowout (|margin| >= 6) | 988 | +1.500 |
| F5 extreme AND blowout | 414 | +1.133 |
| F5 extreme AND NOT blowout | 1,237 | +0.092 |

### Overlap analysis
- 25.1% of F5 extremes end as full-game blowouts
- 41.9% of full-game blowouts had F5 extremes
- The two conditions are correlated but far from identical

### Full-game total residual by F5 state

| F5 State | N | Total Residual | = F5 Residual + Late Residual |
|----------|---|----------------|-------------------------------|
| F5 very low | 744 | -3.450 | -3.891 + 0.441 |
| F5 low | 564 | -2.197 | -2.505 + 0.308 |
| F5 normal | 2,281 | -0.046 | -0.158 + 0.112 |
| F5 high | 357 | +2.546 | +2.472 + 0.074 |
| F5 very high | 907 | +5.683 | +5.401 + 0.282 |

### Interpretation

The F5 settlement divergence finding and the path-tree finding are **related but not the same signal:**

1. **Path-tree blowout effect** is about full-game totals. A game that becomes a blowout goes over by ~3 runs, mostly because the F5 deviation itself accounts for most of it (+5.4 runs of full-game residual is mostly F5 scoring, not late scoring).

2. **F5 settlement divergence** isolates the late-inning component. The late-run residual conditional on F5 state is much smaller (+0.35 runs at extremes vs +1.5 for blowout margins). When you condition on F5 extreme AND non-blowout final margin, the late residual drops to +0.09 -- essentially zero.

3. **The U-shape is real but small.** The quadratic f5_deviation^2 term is significant (p = 0.0007), confirming that extreme F5 outcomes predict slightly elevated late scoring in either direction. But the effect is ~0.35 runs at the extremes, which is within the noise band of a single game (std = 3.0).

4. **The convergence diagnosis:** The path-tree blowout finding is primarily a F5 scoring effect that persists into late innings only when the game remains a blowout through the finish. The F5 settlement divergence adds a small independent U-shape effect but does not substantially amplify the path-tree finding.

---

## Decision

**NEAR MISS.**

Evidence:
- The U-shaped quadratic relationship between F5 deviation and late-inning scoring is **statistically significant** (p < 0.001) and **stable across seasons** (same sign in 2024 and 2025).
- The effect is **real but small**: +0.35 runs at F5 extremes, representing ~0.12 standard deviations of late-run variance.
- The finding is **structurally meaningful**: it confirms that extreme F5 states (both high and low) predict slightly elevated late-inning scoring, likely due to bullpen quality differentials (early scoring depletes relief pitchers) and manager decisions (position player pitching in blowouts).
- R-squared of the F5-state model is 0.014 -- the signal explains ~1.4% of late-run variance. This is informative but not actionable at -110 vig.

Blocking factors:
1. **No historical F5 closing lines.** The entire analysis uses a constant-ratio proxy. Actual F5 lines vary by game (pitcher matchup, park), so the true F5 deviation distribution may differ.
2. **No live market data.** The actionability analysis assumes a bet against the pre-game proxy, not against an actual live line. Live lines adjust rapidly after F5 scoring.
3. **Effect size too small for standalone edge.** +0.35 runs at extremes translates to ~1% win-rate shift against a properly set line, well below the ~2.5% required to overcome -110 vig.
4. **Confounded with blowout path.** When controlling for non-blowout outcomes (removing games where the blowout persists), the F5 extreme late residual drops to +0.09 (noise).

Recommendation:
- **Do not advance** as a standalone signal for live betting.
- **Retain** the quadratic f5_deviation^2 finding as a candidate feature for the path-tree engine, where it can interact with bullpen availability and margin to refine late-game projections.
- **Collect F5 closing lines** in the 2026 season (already started via mlb_sim_f5) to enable a proper retest with actual market expectations rather than constant-ratio proxies.
- **Revisit** once 500+ games of F5 closing line data accumulate (approximately July 2026).
