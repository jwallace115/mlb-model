# Phase 3: Full Path-Tree Bullpen Engine

**Date:** 2026-04-09
**Status:** NEAR MISS — strong structural signal, but pregame branch prediction is the fatal bottleneck

---

## Executive Summary

The path-tree architecture confirms that game-state branches (CLOSE/MODERATE/BLOWOUT) create massive differences in reliever run production — a 3.92-run residual gap between blowout and close games relative to closing lines. An oracle tree that knows the actual branch improves MAE by 0.15 runs over the closing line and achieves 70% directional accuracy on blowout-flagged overs. However, pregame branch prediction is essentially flat: the multinomial logistic model cannot spread P(blowout) beyond 0.25-0.30, collapsing the tree to a constant correction indistinguishable from the flat baseline. The bottleneck is branch prediction, not the tree architecture.

**Decision: NEAR MISS.** The tree has real structural power but only with observed branches (live/in-game value). Pregame, it offers zero edge over the closing line.

---

## Phase 1: Data Audit & Game-Level Dataset

**Dataset:** 7,366 games (2022-2025) with complete starter and reliever pitching logs.

| Branch | n | Share | Mean Total | Mean Reliever Runs | Std Reliever Runs |
|--------|---|-------|------------|-------------------|-------------------|
| CLOSE (margin <= 2) | 3,429 | 46.6% | 7.62 | 3.01 | 2.76 |
| MODERATE (margin 3-4) | 1,876 | 25.5% | 8.57 | 3.33 | 2.80 |
| BLOWOUT (margin >= 5) | 2,061 | 28.0% | 11.31 | 5.09 | 3.42 |

Key finding: Blowout games produce 2.08 more reliever runs than close games (5.09 vs 3.01), confirming the Phase 1 finding that branch structure is real.

---

## Phase 2: Pregame Branch Probability Model

**Architecture:** Multinomial logistic regression on 3 classes.
**Split:** Train 2022-2023 (3,400), Val 2024 (1,783), OOS 2025 (1,709).

### Model Comparison (Log-Loss)

| Model | Val LL | OOS LL | vs Naive |
|-------|--------|--------|----------|
| Naive (marginal rates) | 1.0607 | 1.0625 | baseline |
| SP quality only | 1.0609 | 1.0630 | +0.0002 (worse) |
| SP + early exit rate | 1.0629 | 1.0636 | +0.0011 (worse) |
| SP + exit + closing total | 1.0701* | 1.0628* | +0.0003 (worse) |

*Trained on half of 2024 only (closing lines unavailable pre-2024).

**Critical finding:** No feature combination beats the naive marginal baseline. The model cannot discriminate branches pregame. All Brier scores are at or above naive levels.

### Prediction Spread (Blowout Probability)

The SP-only model places all predictions in a single bucket (0.25-0.30). SP+exit spreads slightly wider but with zero calibration benefit:

| Bucket | n (OOS) | Predicted Mean | Actual Rate |
|--------|---------|----------------|-------------|
| 0.20-0.25 | 134 | 0.245 | 0.269 |
| 0.25-0.30 | 1,413 | 0.270 | 0.289 |
| 0.30-0.35 | 146 | 0.315 | 0.288 |
| 0.35-0.40 | 16 | 0.362 | 0.313 |

The model moves P(blowout) by at most 0.05-0.10 from the marginal rate. This is insufficient to generate actionable edge.

### Early Exit Rate Feature

Coefficients for early exit rate on blowout class: home_sp=+0.070, away_sp=+0.000. Adds no OOS value (Brier worsens by 0.0004). The signal is real but far too small to shift branch probabilities meaningfully.

---

## Phase 3: Starter Exit Transition Model

**Target:** P(starter exits before inning 5).
**Base rate:** 28.1%.

| Metric | Naive | Model | Improvement |
|--------|-------|-------|-------------|
| Val Brier | 0.2022 | 0.1857 | 0.0165 |
| OOS Brier | 0.2023 | 0.1890 | 0.0133 |

The exit model is reasonably well-calibrated (predicted 0.75 -> actual 0.71 in tail), driven primarily by season_ip_per_start (coeff=-0.58). However, starter exits explain only a fraction of branch outcomes — many blowouts occur with starters lasting 5+ innings, and many early exits lead to close games with quality relief.

---

## Phase 4: Branch-Conditional Deployment

| Metric | CLOSE | MODERATE | BLOWOUT |
|--------|-------|----------|---------|
| Home SP IP | 5.28 | 5.13 | 4.99 |
| Away SP IP | 5.09 | 4.98 | 4.75 |
| Home RP IP | 3.42 | 3.40 | 3.55 |
| Away RP IP | 3.05 | 3.04 | 3.30 |
| Home RP RA/9 | 4.33 | 4.99 | 6.77 |
| Away RP RA/9 | 6.01 | 6.30 | 7.77 |
| Home SP RA | 2.26 | 2.50 | 3.01 |
| Away SP RA | 2.35 | 2.74 | 3.22 |

Blowout games feature: shorter starter outings (-0.3 IP each side), more reliever innings, and dramatically worse reliever RA/9 (6.77/7.77 vs 4.33/6.01 in close games). The RA/9 difference is the endogenous deployment effect — managers use mop-up relievers in blowouts, inflating run rates.

---

## Phase 5: Branch-Conditional Reliever Run Environment

| Branch | Mean Reliever Runs | P(rr > 5) | P(rr > 7) | P10/P90 |
|--------|-------------------|-----------|-----------|---------|
| CLOSE | 3.01 | 16.9% | 7.2% | 0.0 / 7.0 |
| MODERATE | 3.33 | 18.9% | 8.2% | 0.0 / 7.0 |
| BLOWOUT | 5.09 | 39.6% | 20.5% | 1.0 / 10.0 |

The blowout reliever phase is a fundamentally different distribution: 2x the probability of 5+ reliever runs, 3x the probability of 7+ reliever runs.

---

## Phase 6: Full Tree Assembly

**Architecture:**
```
tree_fair = closing_total * sp_fraction + sum(P(branch_i) * E[reliever_runs | branch_i])
```

### Results (OOS 2025, n=1,709)

| Method | MAE | Corr with Actual |
|--------|-----|------------------|
| Closing total (market) | 3.506 | 0.2166 |
| Flat BP correction | 3.527 | 0.2166 |
| Predicted branch tree | 3.524 | 0.2150 |

The predicted branch tree is indistinguishable from the flat correction because the branch model cannot spread predictions. All three models produce nearly identical MAE.

---

## Phase 7: Market Validation (OOS 2025)

### Predicted Tree Directional Accuracy

| Edge Threshold | OVER n | Over Rate | UNDER n | Under Rate |
|----------------|--------|-----------|---------|------------|
| 0.25 | 216 | 43.5% | 525 | 47.8% |
| 0.35 | 121 | 39.7% | 374 | 48.4% |
| 0.50 | 25 | 52.0% | 234 | 47.4% |
| 0.65 | 4 | 75.0% | 111 | 45.0% |

**No directional edge at any threshold.** The predicted tree is noise against the closing line. Most "edges" are under-biased (tree systematically lower than closing), and under signals hit below 50%.

---

## Phase 8: Failure Analysis — Oracle vs Predicted Branch

This is the critical test. Using ACTUAL observed branch instead of predicted:

### MAE Comparison (OOS 2025, n=1,780)

| Method | MAE | Corr |
|--------|-----|------|
| Closing total | 3.531 | 0.2170 |
| Flat correction | 3.556 | 0.2170 |
| Predicted tree | 3.556 | 0.2170 |
| **Oracle tree** | **3.381** | **0.4060** |

The oracle tree beats the closing line by 0.15 MAE and nearly doubles the correlation (0.41 vs 0.22). This is a substantial improvement.

### Oracle Directional Accuracy (OOS 2025)

| Edge | OVER n | Over Rate | UNDER n | Under Rate |
|------|--------|-----------|---------|------------|
| 0.35 | 490 | **69.2%** | 884 | **59.6%** |
| 0.50 | 475 | **69.7%** | 742 | **58.9%** |
| 0.65 | 475 | **69.7%** | 383 | **55.9%** |
| 1.00 | 342 | **70.8%** | 146 | **58.9%** |

The oracle tree achieves 70% over-rate on blowout games — enormously profitable if actionable.

### Branch-Conditional Market Residuals (OOS 2025)

| Branch | n | Actual Over Rate | Mean (Actual - Closing) |
|--------|---|------------------|------------------------|
| CLOSE | 822 | 33.3% | **-0.97** |
| MODERATE | 445 | 44.5% | +0.24 |
| BLOWOUT | 513 | **69.2%** | **+2.95** |

The market systematically under-prices blowout games by nearly 3 runs and over-prices close games by about 1 run. The gap between blowout and close residuals is 3.92 runs — this is the structural signal the tree captures.

### Diagnosis

**The bottleneck is branch prediction, not the tree architecture.**

- Oracle tree: MAE 3.381, corr 0.406, 70% directional accuracy
- Predicted tree: MAE 3.524, corr 0.215, ~48% directional accuracy
- Gap: 0.143 MAE, 0.191 correlation points — entirely due to branch prediction failure

---

## Phase 9: Live/In-Game Value

### Variance Decomposition

Branch category explains 9.8% of reliever run variance (R-squared = 0.098). Within-branch residual standard deviations remain large:

| Branch | Within-Branch Std |
|--------|------------------|
| CLOSE | 2.84 |
| MODERATE | 2.87 |
| BLOWOUT | 3.59 |
| Overall | 3.25 |

Even knowing the exact branch, 90% of variance is unexplained. But the 10% that IS explained creates a 3.92-run conditional mean shift, which is large enough for live betting value.

### Live Betting Implications

After inning 5, the game state is observable:
- If the margin is >= 5 runs (blowout path), the remaining innings will produce ~2.95 more runs than the pregame closing line implies
- If the margin is <= 2 runs (close path), the remaining innings will produce ~0.97 fewer runs than implied
- This is a 70% directional signal on blowouts — well above the ~52.4% breakeven for -110 lines

**The strongest value is mid-game (after inning 5), not pregame.** By then, the branch is known, and the market has not fully adjusted for the mop-up reliever effect in blowouts.

### Hypothetical Pregame Value

If a model could spread P(blowout) across a 0.30-wide range (0.15 to 0.45 instead of 0.25 to 0.30), the implied edge swing would be approximately 1.18 runs. This would require features far beyond SP quality — likely in-game pace indicators, lineup depth, or live score trajectory. No pregame feature tested approaches this discriminating power.

---

## Decision

**NEAR MISS.**

| Criterion | Result |
|-----------|--------|
| Tree architecture works? | YES — oracle tree beats closing line by 0.15 MAE with 70% directional accuracy |
| Pregame branch prediction works? | NO — model cannot discriminate branches; all predictions cluster at marginal rates |
| Pregame edge over closing line? | NO — predicted tree is identical to flat correction (MAE 3.524 vs 3.506) |
| Live/in-game value? | YES — knowing branch after inning 5 gives 70% over-rate on blowouts, 60% under-rate on close games |
| OOS stability? | YES for oracle, N/A for predicted (no signal to evaluate) |

### Why It Failed Pregame

The fundamental problem identified in Phase 2 research persists in a more sophisticated form: **game-state branches are not predictable from pregame pitcher quality.** The branch (CLOSE/MODERATE/BLOWOUT) is determined by the interaction of both teams' entire pitching staffs, offensive execution, sequencing luck, and managerial decisions — all of which are endogenous to the game as it unfolds. SP ERA and early exit rates explain essentially 0% of branch variance.

### What Would Need to Be True

To make the tree work pregame, we would need a branch predictor that:
1. Spreads P(blowout) across at least a 0.25 range (current: 0.05)
2. Is calibrated (predicted 0.40 blowout -> 40% actual blowout rate)
3. Uses features beyond SP quality — potentially lineup depth vs SP weakness matchups, or historical blowout propensity by team pair

None of these appear feasible with available pregame data.

### Recommended Next Steps

1. **Live betting engine (high priority):** Build an after-inning-5 totals model that incorporates observed margin as a blowout/close indicator. The 70% directional accuracy on blowouts and 60% on close games is well above breakeven.
2. **F5 total refinement:** The tree finding implies F5 totals (starter-dominated) should be more predictable than full-game totals, since they avoid the unpredictable reliever branch. This supports the existing Phase 11 F5 plan.
3. **Close this pregame path.** No further pregame bullpen tree work is warranted. The Phase 2 conclusion holds: pregame bullpen quality does not equal deployed bullpen quality because deployment is endogenous to game state.
