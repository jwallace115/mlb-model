# Phase 2: Pregame Bullpen Quality Correction Layer

**Date:** 2026-04-09
**Verdict:** CLOSE — pregame bullpen quality carries near-zero independent signal; branch weighting adds nothing over flat; neither beats the closing line baseline.

---

## Phase 1 — Pregame Bullpen Quality Metric

**Data:** 4,326 complete-case games (2022-2025), 60,813 reliever appearances with pregame-shifted stats.

Two bullpen quality metrics were constructed:

| Metric | Mean | Std | Corr(actual_total) |
|--------|------|-----|-------------------|
| Deployed BP K rate (IP-weighted, pregame-shifted) | 0.2560 | 0.0488 | **-0.2059** |
| Pregame team BP K rate (season-to-date, all relievers) | 0.2398 | 0.0203 | **-0.0228** |

The deployed metric looks useful (r = -0.21) but suffers from **survivor bias**: it uses who actually pitched, which is unknowable pregame. The pregame-estimable metric (team season-to-date K rate across all relievers) has essentially zero correlation with scoring.

Correlation between deployed and pregame metrics: **0.354** — only moderate overlap, confirming that who gets deployed matters far more than the roster average.

Per-season pregame BP vs actual_total correlations: -0.059 (2022), -0.022 (2023), -0.045 (2024), **-0.012 (2025)**. The signal is weak in every year and trending weaker.

## Phase 2 — Branch Probabilities

Branch definitions by absolute game margin:

| Branch | Rate | Relief Runs (mean) |
|--------|------|--------------------|
| CLOSE (margin 0-2) | 46.1% | 2.94 |
| MODERATE (margin 3-4) | 26.1% | 3.21 |
| BLOWOUT (margin 5+) | 27.8% | 5.06 |

Blowouts generate ~2 extra reliever-phase runs vs close games — a meaningful structural difference.

**Branch predictability (logistic regression on pregame features):**

| Split | Model Log Loss | Base Rate Log Loss | Delta |
|-------|---------------|-------------------|-------|
| Train (22-23) | 0.5863 | 0.5883 | +0.0020 |
| Val (2024) | 0.5934 | 0.5944 | +0.0010 |
| OOS (2025) | 0.6009 | 0.6002 | **-0.0007** |

Branches are **essentially unpredictable pregame**. The logistic model is worse than the base rate OOS. Features used: closing total, SP quality differential, SP average ERA, pregame BP average K rate, pregame BP K rate differential. None provide meaningful branch separation.

## Phase 3 — Correction Layer

Three variants evaluated on train (2022-2023) / validate (2024) / OOS (2025):

| Split | Variant | MAE | Correlation |
|-------|---------|-----|-------------|
| Val 2024 | Baseline (close_total) | **3.373** | 0.1899 |
| Val 2024 | Flat BP correction | 3.401 | 0.1904 |
| Val 2024 | Branch-weighted | 3.405 | 0.1883 |
| OOS 2025 | Baseline (close_total) | **3.490** | **0.1956** |
| OOS 2025 | Flat BP correction | 3.554 | 0.1956 |
| OOS 2025 | Branch-weighted | 3.556 | 0.1918 |

**Both correction variants are worse than the closing line baseline on MAE.** The flat Ridge model's close_total coefficient is 0.819 (not 1.0), meaning it is shrinking the closing line toward a constant — a sign the BP features are not adding useful information and the model is compensating by dampening the line signal.

Flat Ridge coefficients:
- close_total: 0.8191
- pregame_bp_avg_k: -0.0835
- pregame_bp_k_diff: -0.1972
- intercept: 2.089

The BP K rate coefficients are small and economically negligible.

**Directional accuracy (over/under hit rate):**

The correction model is almost always positive (predicts above closing line), producing heavily skewed OVER signals with no UNDER signals at any threshold:

| Split | Threshold | OVER n | OVER Hit Rate |
|-------|-----------|--------|---------------|
| Val 2024 | 0.50 | 914 | 0.490 |
| OOS 2025 | 0.50 | 785 | **0.459** |
| OOS 2025 | 0.65 | 283 | **0.466** |

All hit rates are below 0.50 — the correction is systematically wrong OOS, predicting overs that lose.

## Phase 4 — Team-Total Interaction (Redundancy Check)

| Metric | Value |
|--------|-------|
| bp_correction vs sp_quality_diff | 0.033 |
| bp_correction vs sp_avg_era | -0.069 |
| bp_correction vs close_total | **-0.999** |
| Partial corr(bp_correction, actual_total \| close_total, SP) | **0.040** |
| Partial corr(pregame_bp_avg_k, actual_total \| close_total, SP) | **0.035** |

The correction is almost perfectly anti-correlated with the closing line (r = -0.999) because the Ridge coefficient on close_total is less than 1.0. After controlling for closing total and SP quality, the partial correlation of the BP correction with actual scoring is **0.04** — essentially zero independent signal.

The BP correction is **not redundant with SP quality** (corr = 0.03), but this is irrelevant because it has no independent value in the first place.

## Phase 5 — Signal Validation

**Monotonicity check (OOS 2025, quintiles by correction edge):**

| Quintile | Edge Mean | Over Rate |
|----------|-----------|-----------|
| 1 (lowest) | 0.310 | 0.430 |
| 2 | 0.489 | 0.471 |
| 3 | 0.546 | 0.452 |
| 4 | 0.647 | 0.425 |
| 5 (highest) | 0.763 | 0.466 |

**No monotonicity.** Higher predicted edges do not correspond to higher over rates. The signal is pure noise OOS.

Branch-weighted monotonicity is equally flat (0.430-0.462 across quintiles, no trend).

## Phase 6 — Integration Assessment

### Diagnosis

The pregame bullpen quality correction layer fails at every level:

1. **Pregame signal is near-zero** (r = -0.023 with scoring). The deployed bullpen metric looks useful (r = -0.21) but is unknowable pregame — a classic lookahead trap.

2. **Branches are unpredictable** pregame. The logistic model is worse than base rate on OOS data. Game closeness is essentially random noise from a pregame perspective.

3. **Both correction variants degrade MAE** vs the closing line baseline. The flat correction adds +0.064 MAE; branch-weighted adds +0.066.

4. **Directional accuracy is below 50%** at all thresholds OOS. The correction systematically overestimates totals.

5. **No monotonicity** in edge-to-outcome mapping.

6. **Near-zero partial correlation** (0.04) after controlling for closing total and SP quality.

### Why deployed BP quality "works" but pregame does not

The deployed metric benefits from in-game selection: managers deploy better relievers in close games (lower scoring) and worse relievers in blowouts (higher scoring). This creates a mechanical negative correlation between deployed reliever quality and game total that is not pregame-predictable.

The pregame team average washes out the deployment selection effect because it averages across all relievers without knowing who will pitch or in what game state.

### Verdict: CLOSE

Neither flat nor branch-weighted bullpen correction beats the closing line baseline on any metric. The pregame bullpen quality signal is functionally zero after the market has priced in SP quality and team strength.

**Do not advance.** The correction layer is not viable as:
- Standalone signal (no edge)
- V1 overlay (degrades MAE)
- Team-total input (partial corr = 0.04)
- CS028 enhancer (no independent information)

The existing Phase 9 model features (home/away_high_leverage_avail, bullpen_delta, bp_delta_exposure) capture the useful bullpen signal through availability/fatigue channels rather than quality channels. Those features address a different question — "is the bullpen rested?" — which has genuine pregame information content that roster-average quality does not.
