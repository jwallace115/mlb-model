# Phase 3 — Top-of-Card vs Starter Matchup Model

**Date:** 2026-04-06
**Design:** Train 2024, test 2025 (pure year holdout). Logistic regression.

---

## Verdict: THIS BRANCH DID NOT PRODUCE A MEANINGFUL FIRST-INNING INTERACTION EDGE.

The interaction model does not materially improve over the prior baselines.
All models tested — broad, micro, card-only, interaction, top-5 — produce
AUCs between 0.50 and 0.55 and negative Brier improvements OOS. The interaction
features have interpretable coefficients but do not translate to better predictions.

---

## Card Construction

**Top-3 weighted card:** positions 1/2/3 weighted 40%/35%/25%.
**Top-5 weighted card:** positions 1-5 weighted 30%/25%/20%/15%/10%.
**Leadoff component:** position-1 OBP and BB rate extracted separately.
**2/3 damage component:** positions 2+3 average ISO and SLG.

Coverage: 98.4% of games have non-null rolling stats for top-3 and top-5 cards.

---

## Interaction Features Constructed

| Feature | Formula | Hypothesis |
|---------|---------|------------|
| reach × control | card OBP × pitcher BB rate | Both prone to free bases |
| damage × HR | card ISO × pitcher HR rate | Power hitters vs HR-prone pitcher |
| damage × barrel | card ISO × pitcher barrel rate | Power vs hard contact allowed |
| contact matchup | (1 - card K%) × (1 - pitcher whiff%) | Low-K hitters vs low-whiff pitcher |
| K mismatch | card K% - pitcher K% | Strikeout gap |
| lead reach × 2/3 damage | leadoff OBP × cleanup ISO | Baserunner + damage sequencing |
| platoon × TTO1 | platoon advantage × TTO1 vulnerability | Handedness pressure on vulnerable arm |

---

## Side-Level Results

### TOP1 (away scores in top of 1st)

| Model | N test | AUC | Brier % | LL % | TD lift | TQ lift |
|-------|--------|-----|---------|------|---------|---------|
| A) Broad | 1186 | 0.5132 | -0.34% | -0.28% | 1.01x | 1.10x |
| B) Micro | 1136 | **0.5311** | -0.21% | -0.25% | 1.16x | 1.16x |
| C) Card-only | 1093 | 0.4968 | -1.36% | -1.18% | 1.04x | 1.01x |
| D) Interaction | 1093 | 0.5017 | -1.71% | -1.56% | 0.97x | 1.01x |
| E) Card5-only | 1093 | 0.5018 | -0.90% | -0.78% | 1.11x | 1.15x |

The interaction model (D) is **worse** than the prior micro baseline (B) on every
metric. Card-only (C) is also worse. Adding more features hurts — classic overfitting
on 2024 that doesn't generalize to 2025.

### BOT1 (home scores in bottom of 1st)

| Model | N test | AUC | Brier % | LL % | TD lift | TQ lift |
|-------|--------|-----|---------|------|---------|---------|
| A) Broad | 1184 | **0.5354** | -0.03% | -0.05% | 1.17x | 1.09x |
| B) Micro | 1146 | 0.5113 | -0.88% | -0.73% | 1.04x | 1.07x |
| C) Card-only | 1096 | 0.5260 | -0.78% | -0.62% | 1.02x | 0.99x |
| D) Interaction | 1096 | 0.5311 | -0.82% | -0.65% | 1.08x | 1.02x |
| E) Card5-only | 1096 | 0.5274 | -0.67% | -0.55% | 0.99x | 1.00x |

Broad (A) wins BOT1 on AUC — the simplest model is best. Interaction (D) is
slightly better than card-only (C) but still below broad.

---

## YRFI Combination

| Model | N | AUC | Brier % | TD lift | NRFI bottom-decile |
|-------|---|-----|---------|---------|-------------------|
| A) Broad | 1131 | 0.5204 | -0.48% | 1.05x | 0.500 |
| B) Micro | 1048 | 0.5180 | -0.79% | 1.04x | 0.505 |
| C) Card-only | 1012 | 0.5089 | -1.07% | 1.06x | 0.500 |
| D) Interaction | 1012 | **0.5276** | -0.74% | 1.06x | 0.510 |

The interaction model has the best combined YRFI AUC (0.5276) but all models are
within 0.02 of each other. No model achieves positive Brier improvement — all are
worse than predicting the base rate.

---

## Leakage Check

After residualizing the interaction model's YRFI probability against obvious controls
(park factor, temperature, broad team offense, pitcher K rate):

| Group | YRFI rate | NRFI rate | Delta vs base |
|-------|-----------|-----------|---------------|
| Residual bottom 10% | 0.431 | **0.569** | **+0.048** |
| Residual top 10% | 0.510 | 0.490 | +0.031 |
| Spread | | | 0.078 |

R² of controls on p_yrfi: 0.365

**This is the one positive finding:** after removing obvious context, the interaction
model's extreme tails show a 7.8pp spread in YRFI rates. The bottom-10% residual
achieves 56.9% NRFI vs 52.1% base — a +4.8pp delta that survives obvious controls.

However:
- This residual spread is on N=~100 per tail. Noisy.
- The raw model Brier is negative (model miscalibrated OOS).
- The AUC is 0.5276 — barely above chance.
- The residual finding does not translate to useful raw predictions because the
  model's calibration is wrong in the first place.

---

## Top-3 vs Top-5 Card

Top-5 (E) shows no improvement over Top-3 (C) on either side:

| Model | TOP1 AUC | BOT1 AUC |
|-------|----------|----------|
| Top-3 card | 0.4968 | 0.5260 |
| Top-5 card | 0.5018 | 0.5274 |

Negligible difference. Top-3 is sufficient — adding positions 4-5 adds noise.

---

## Weighting

Simple average (equal weight) top-3 was used in the prior micro baseline (B).
Weighted top-3 (40/35/25) was used in card-only (C) and interaction (D).

The weighted card did NOT outperform the simple average micro baseline on either
side. Weighting did not help.

---

## Coefficient Interpretation

The interaction model's top coefficients are interpretable but contradictory:

**TOP1:**
- `dmg_iso` (+0.68) — more power in top-3 = more scoring. Expected.
- `lead_reach_x_dmg` (-0.54) — leadoff reach × cleanup damage NEGATIVE. Counter-expected.
- `reach_x_control` (+0.53) — card OBP × pitcher walk rate positive. Expected.
- `sp_bb_rate` (-0.41) — pitcher walk rate alone is NEGATIVE. Contradicts the interaction.

The leadoff×damage interaction has the **wrong sign**. This is a hallmark of
multicollinearity: when raw features and their interaction are both in the model,
the coefficients become unstable and swap signs.

---

## Why This Branch Failed

1. **First-inning scoring is low-signal.** ~27% (top) and ~30% (bottom) base rates
   mean most innings are scoreless regardless of matchup quality. The single-inning
   outcome is too binary and too noisy for feature-rich models to gain traction.

2. **Interaction features add noise, not signal.** Products of two noisy rolling
   averages produce even noisier inputs. Logistic regression can't reliably estimate
   interaction coefficients from ~900 training games.

3. **The market context already captures matchup quality.** YRFI/NRFI lines implicitly
   price starter quality, lineup strength, and park factor. The micro features are
   redundant with market information.

4. **SLG/ISO collinearity persists.** All card models show the same sign conflict
   between SLG and ISO. The feature space needs orthogonalization, not more features.

---

## Conclusion

The top-of-card vs starter interaction model does not produce a meaningful
first-inning edge. It does not materially improve over the prior baselines from
Phase 1, and all baselines are themselves barely above chance.

The residualized tail finding (+4.8pp NRFI in bottom-10% after controls) is the only
thing that survived any version of this analysis. It is consistent across Phase 2 and
Phase 3. But it is too small, too noisy, and too dependent on correct calibration to
be a deployable filter.

**Recommended disposition:** Close the first-inning research branch. The data
foundation is sound (targets available, hitter cards constructable, pitcher profiles
rich), but first-inning outcomes are too noisy for the available feature set to
predict meaningfully. If this branch is revisited, it should be with pitch-level
Statcast data (actual first-inning pitch sequences) rather than game-level rolling
averages — and even then, the base-rate problem limits the ceiling.
