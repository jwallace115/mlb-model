# NCAAF Base Engine — Phase 3: Portal Residual Overlay Test

**Date:** 2026-04-08
**Objective:** Test whether the portal shock signal (Bucket B: NEG_SHOCK + HIGH_RETURNING) works better as a residual overlay on the base Ridge engine than as a standalone badge.

---

## Setup

- **Base model:** `ncaaf/models/base_ridge_v1.pkl` (Ridge, alpha=100, 15 features)
- **Canonical data:** `ncaaf/data/ncaaf_canonical_2022_2025.parquet` (2,998 games)
- **Portal thresholds (frozen from Phase 2):** NET_STAR <= -29.0, returning_ppa >= 0.551
- **Scope:** Weeks 1-4, pushes excluded

### Sign Convention

- `closing_spread` < 0 means home team is favored
- `actual_margin` = home_points - away_points (positive = home win)
- `model_edge` = how much MORE the model likes a team vs the market (positive = model sees value on this team)
- Home team: `model_edge = model_pred + closing_spread`
- Away team: `model_edge = -model_pred - closing_spread`

### Residual Classification

- **MODEL_LIKES:** model_edge > +1.5 (model sees more value on this team than market)
- **AGREE:** model_edge in [-1.5, +1.5]
- **MARKET_LIKES:** model_edge < -1.5 (market likes this team more than model does)

---

## Phase 1 — Residual Distribution (Bucket B, Weeks 1-4)

| Residual Bucket | N | Cover % | ATS Margin |
|:---------------:|:-:|:-------:|:----------:|
| MODEL_LIKES (>1.5) | 82 | **48.8%** | -0.23 |
| AGREE (-1.5 to 1.5) | 44 | **70.5%** | +3.77 |
| MARKET_LIKES (<-1.5) | 87 | **56.3%** | +2.32 |
| **All Bucket B** | **213** | **56.3%** | +1.64 |

**Key finding:** The model-likes direction (where model and portal signal agree) *hurts* performance (48.8%). The signal concentrates in AGREE (70.5%, small N) and MARKET_LIKES (56.3%). This is the opposite of what a confirmatory overlay would show.

### Interpretation

When the model already likes a portal-shocked team (MODEL_LIKES), the market has likely already priced in the factors the model sees (talent, SP ratings, returning PPA). The portal overcorrection has already been absorbed. When the market likes the team more than the model does (MARKET_LIKES), the portal overcorrection is still live -- the market spread reflects portal-departure headlines that the model partially agrees with, but the retained-core effect still provides residual cover value.

---

## Phase 2 — Season Stability by Residual Bucket

### MODEL_LIKES (edge > 1.5)

| Season | N | Cover % | ATS Margin |
|:------:|:-:|:-------:|:----------:|
| 2022 | 36 | 41.7% | -2.21 |
| 2023 | 21 | 52.4% | +1.98 |
| 2024 | 9 | 33.3% | -3.94 |
| 2025 | 16 | 68.8% | +3.44 |

Only 1 of 4 seasons above 52.4%. Unstable and often negative.

### AGREE (-1.5 to 1.5)

| Season | N | Cover % | ATS Margin |
|:------:|:-:|:-------:|:----------:|
| 2022 | 19 | 84.2% | +7.82 |
| 2023 | 14 | 50.0% | -2.29 |
| 2024 | 9 | 66.7% | +2.50 |
| 2025 | 2 | 100.0% | +13.50 |

Strong overall but tiny N (44 total, single-digit seasons). 2022 dominance is a red flag.

### MARKET_LIKES (edge < -1.5)

| Season | N | Cover % | ATS Margin |
|:------:|:-:|:-------:|:----------:|
| 2022 | 36 | 61.1% | +3.07 |
| 2023 | 26 | 57.7% | -0.40 |
| 2024 | 11 | 54.5% | +4.50 |
| 2025 | 14 | 42.9% | +3.71 |

3 of 4 seasons above 50%. More stable than MODEL_LIKES but 2025 dips.

---

## Phase 3 — Threshold Tests

### MODEL_LIKES direction (model agrees with portal fade)

| Threshold | N | Cover % | ATS Margin |
|:---------:|:-:|:-------:|:----------:|
| edge > 0 | 100 | 53.0% | +0.94 |
| edge > 1.5 | 82 | 48.8% | -0.23 |
| edge > 3.0 | 62 | 53.2% | +0.85 |
| edge > 5.0 | 47 | 51.1% | +1.16 |
| edge > 7.0 | 33 | 45.5% | -1.50 |

No threshold produces a usable signal. Higher model conviction actually worsens results.

### MARKET_LIKES direction (fade model, back portal team)

| Threshold | N | Cover % | ATS Margin |
|:---------:|:-:|:-------:|:----------:|
| edge < 0 | 113 | 59.3% | +2.26 |
| edge < -1.5 | 87 | 56.3% | +2.32 |
| edge < -3.0 | 63 | 55.6% | +1.95 |
| edge < -5.0 | 44 | 59.1% | +3.16 |

The edge < 0 bucket (model does NOT like this team) at 59.3% with N=113 is the strongest residual-filtered result. But this is effectively saying: "use the portal signal and ignore the model" -- which is the opposite of a useful overlay.

---

## Phase 4 — Favorite vs Underdog (MODEL_LIKES > 1.5)

| Role | N | Cover % | ATS Margin |
|:----:|:-:|:-------:|:----------:|
| Favorite (< -3) | 18 | 44.4% | -1.28 |
| Pick-em (-3 to 3) | 10 | 60.0% | +0.15 |
| Underdog (> 3) | 54 | 48.1% | +0.06 |

No usable subset. Compare to raw Bucket B favorites (no residual filter): 59.3% cover rate, N=108.

---

## Phase 5 — Fade Curve

### MODEL_LIKES > 1.5

| Window | N | Cover % | ATS Margin |
|:------:|:-:|:-------:|:----------:|
| Weeks 1-2 | 39 | 56.4% | +2.32 |
| Weeks 3-4 | 43 | 41.9% | -2.53 |
| Weeks 5-8 | 90 | 48.9% | +0.44 |
| Weeks 9+ | 130 | 47.7% | -0.63 |

### Raw Bucket B (no residual filter)

| Window | N | Cover % | ATS Margin |
|:------:|:-:|:-------:|:----------:|
| Weeks 1-2 | 104 | 58.7% | +2.42 |
| Weeks 3-4 | 109 | 54.1% | +0.89 |
| Weeks 5-8 | 218 | 49.1% | -0.55 |
| Weeks 9+ | 327 | 49.2% | -0.26 |

The raw signal is stronger at every time window. The residual filter destroys the Weeks 3-4 signal entirely (41.9% vs 54.1%).

---

## Phase 6 — Coaching Cascade (MODEL_LIKES > 1.5)

| Split | N | Cover % | ATS Margin |
|:-----:|:-:|:-------:|:----------:|
| Same coach | 51 | 51.0% | +1.04 |
| New coach | 31 | 45.2% | -2.31 |

No usable subset.

---

## Summary Comparison

| Filter | N | Cover % | p (binom) | Seasons >= 50% |
|:------:|:-:|:-------:|:---------:|:--------------:|
| **Raw Bucket B (baseline)** | **213** | **56.3%** | **0.037** | **3 of 4** |
| B + MODEL_LIKES (>1.5) | 82 | 48.8% | 0.630 | 1 of 4 |
| B + MODEL_LIKES (>3.0) | 62 | 53.2% | 0.380 | 2 of 4 |
| B + AGREE | 44 | 70.5% | 0.005 | 3 of 4* |
| B + MARKET_LIKES (<-1.5) | 87 | 56.3% | 0.142 | 3 of 4 |
| B + edge < -5.0 | 44 | 59.1% | 0.146 | -- |
| Raw B favorites (comparison) | 108 | 59.3% | 0.034 | -- |

*AGREE has only 44 obs with 2 seasons in single digits.

---

## Diagnosis: Why the Overlay Fails

The portal shock signal is **orthogonal** to the base Ridge engine, not complementary. The mechanism:

1. The base engine already includes `diff_portal_net_stars` and `diff_returning_ppa` as features (coefficients -0.15 and +1.96 respectively). These capture the first-order portal effect.

2. The Bucket B badge captures a **nonlinear interaction** (bottom-quartile shock intersected with above-median returning production) that Ridge cannot represent. This is genuine residual alpha.

3. When the model also likes the portal-shock team (MODEL_LIKES), it means the team's other fundamentals (SP rating, talent, rolling performance) are strong enough that the market has already priced them fairly. The portal overcorrection is absorbed.

4. When the model does NOT like the team (MARKET_LIKES direction), the portal overcorrection is still live because the team's other metrics look weak -- but the retained core provides hidden support the model misses.

5. Therefore: the residual overlay destroys signal because it filters FOR games where the market has already corrected. The portal badge works precisely in the gap between what the model sees and what the market prices.

---

## Decision: CLOSE

### Criteria Check

| Criterion | Threshold | Actual | Pass? |
|-----------|:---------:|:------:|:-----:|
| Best residual-filtered cover % | >= 57% | 48.8% (MODEL_LIKES) | **No** |
| Sample size | >= 50 | 82 | Yes |
| Stable 3+ seasons | 3 of 4 | 1 of 4 | **No** |
| Additive value over raw portal | Improvement | **Degradation** | **No** |

The residual overlay adds no value over the raw portal signal. The MODEL_LIKES direction actively hurts (48.8% vs 56.3% raw). No threshold, favorite/underdog split, or coaching cascade rescues it.

### What This Means for the Pipeline

1. **Do NOT condition the portal badge on model agreement.** The portal signal is strongest precisely when the model disagrees.
2. **The portal badge should remain a standalone badge**, not a model overlay. Apply it as a post-model adjustment or parallel signal in Weeks 1-4.
3. **The AGREE bucket (70.5%, N=44) is interesting but too thin.** If a future canonical expansion adds 2+ more seasons, revisit whether model-portal agreement on direction is a real micro-signal.
4. **The base engine's portal features (-0.15, +1.96) are correctly signed but underpowered** -- they cannot capture the nonlinear threshold effect that makes Bucket B work. This is expected from Ridge.

### Next Steps

- Proceed with raw Bucket B (56.3%, N=213) as the operationalized signal for 2026 shadow
- Do NOT add a residual filter gate
- Consider adding the portal badge as a flat adjustment (+1.5 to +2.0 points) on qualifying teams in Weeks 1-4, applied after the model prediction, rather than using model agreement as a filter
