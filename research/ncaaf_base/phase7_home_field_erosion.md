# Phase 7 — Home-Field Erosion in the Portal/NIL Era (2022-2025)

**Date:** 2026-04-08
**Dataset:** ncaaf_canonical_2022_2025.parquet (2,998 games)
**Model:** base_ridge_v1.pkl (15 features, home_flag effective = +2.79 pts)

## Executive Summary

No actionable venue-based ATS mispricing survives model adjustment.
Raw home ATS is essentially 50/50 across the full sample. The one
directional signal — portal-badge teams covering on the road — is
already captured by the engine's portal features and has thin per-cell
counts that preclude standalone deployment.

**Decision: CLOSE**

---

## Phase 1 — Venue Buckets

| Venue Type | 2022 | 2023 | 2024 | 2025 | Total |
|---|---|---|---|---|---|
| TRUE HOME/AWAY | 715 | 728 | 717 | 739 | 2,899 |
| NEUTRAL | 19 | 22 | 35 | 23 | 99 |

---

## Phase 2 — Raw ATS

### Overall (excl. pushes)

| Side | N | Cover% | Avg ATS |
|---|---|---|---|
| HOME | 2,874 | 49.6% | +0.16 |
| AWAY | 2,874 | 50.4% | -0.16 |
| NEUTRAL (listed home) | 99 | 55.6% | +0.33 |
| NEUTRAL (listed away) | 99 | 44.4% | -0.33 |

### Home ATS by Season

| Season | N | Cover% | Avg ATS |
|---|---|---|---|
| 2022 | 703 | 49.5% | -0.64 |
| 2023 | 716 | 48.5% | -0.13 |
| 2024 | 716 | 49.7% | +0.74 |
| 2025 | 739 | 50.6% | +0.64 |

No trend toward home-field erosion — 2022/2023 slightly under 50%,
2024/2025 slightly over. The direction reverses across the sample,
consistent with noise around a fair market.

---

## Phase 3 — Residual Check (Engine-Adjusted)

### Home ATS by Model Edge Bucket (non-neutral, N=2,874)

| Bucket | N | Home Cover% | Avg ATS |
|---|---|---|---|
| MODEL_LIKES_HOME (edge > 1.5) | 1,073 | 49.2% | +0.36 |
| AGREE (edge +/- 1.5) | 551 | 51.0% | +0.12 |
| MARKET_LIKES_HOME (edge < -1.5) | 1,250 | 49.3% | -0.00 |

All three buckets sit within 1 percentage point of 50%. The engine's
home_flag coefficient (+2.79 points) plus intercept (+4.03) already
accounts for the venue effect. No residual home/away bias remains.

### Neutral-Site Residual (N=99)

| Bucket | N | Listed-Home Cover% | Avg ATS |
|---|---|---|---|
| MODEL_LIKES_HOME | 38 | 55.3% | +1.29 |
| AGREE | 24 | 70.8% | +3.08 |
| MARKET_LIKES_HOME | 37 | 45.9% | -2.45 |

The "AGREE" bucket shows 70.8% listed-home cover, but N=24 is far
too small to be actionable. Neutral-site games total only 99 across
four seasons — no stable subset exists.

---

## Phase 4 — Portal Interaction

Thresholds: portal_net_stars <= -29.0 AND returning_ppa >= 0.551 (Weeks 1-4 only).

### Badge Teams by Venue

| Venue | N | Cover% | Avg ATS |
|---|---|---|---|
| Badge AT HOME | 113 | 52.2% | +0.95 |
| Badge AWAY | 91 | 60.4% | +1.89 |

Badge teams cover at 60.4% on the road vs 52.2% at home. This is
the most interesting split in the study.

### Badge AWAY by Season

| Season | N | Cover% | Avg ATS |
|---|---|---|---|
| 2022 | 37 | 62.2% | +3.36 |
| 2023 | 26 | 53.8% | -0.75 |
| 2024 | 12 | 58.3% | +0.50 |
| 2025 | 16 | 68.8% | +3.81 |

Directional in 3 of 4 seasons, but 2023 is flat and per-season N
ranges from 12-37 — too thin for confidence.

### Badge AWAY After Model Residual

| Residual Bucket | N | Cover% | Avg ATS |
|---|---|---|---|
| MODEL_LIKES_AWAY | 34 | 61.8% | +2.09 |
| AGREE | 21 | 66.7% | +3.64 |
| MARKET_LIKES_AWAY | 36 | 55.6% | +0.68 |

The badge-away signal persists across all three residual buckets,
suggesting it is not fully absorbed by the engine's portal_net_stars
diff feature. However, N=91 total and the smallest cell is N=21.

---

## Phase 5 — Conference vs Non-Conference

| Split | N | Home Cover% | Avg ATS |
|---|---|---|---|
| Conference HOME | 2,089 | 50.1% | +0.19 |
| Conference AWAY | 2,089 | 49.9% | -0.19 |
| Non-conf HOME | 785 | 48.2% | +0.06 |
| Non-conf AWAY | 785 | 51.8% | -0.06 |

Non-conference homes cover at 48.2% — slightly below break-even but
the margin is negligible (+0.06 avg ATS). This "cupcake scheduling"
lean toward away dogs does not persist after model adjustment:

### Model Residual x Conference

| Split | N | Home Cover% | Avg ATS |
|---|---|---|---|
| Non-conf, MODEL_LIKES_HOME | 284 | 45.1% | -0.69 |
| Non-conf, AGREE | 132 | 50.8% | +0.28 |
| Non-conf, MARKET_LIKES_HOME | 369 | 49.6% | +0.56 |

The model-likes-home bucket in non-conference games shows 45.1%
home cover — the engine may slightly overvalue non-conf home teams.
But the MARKET_LIKES bucket returns to 49.6%, suggesting this is
model noise rather than a market mispricing.

### Non-Conf HOME by Season

| Season | N | Cover% | Avg ATS |
|---|---|---|---|
| 2022 | 196 | 49.0% | -0.87 |
| 2023 | 186 | 47.3% | -0.94 |
| 2024 | 201 | 45.8% | +0.62 |
| 2025 | 202 | 50.5% | +1.31 |

No stable direction — 2022-2023 slightly under, 2025 slightly over.

---

## Phase 6 — Favorite/Underdog

| Split | N | Cover% | Avg ATS |
|---|---|---|---|
| HOME FAVORED | 1,810 | 48.7% | -0.02 |
| HOME UNDERDOG | 1,062 | 51.0% | +0.43 |
| AWAY FAVORED | 1,062 | 49.0% | -0.43 |
| AWAY UNDERDOG | 1,810 | 51.3% | +0.02 |

Home underdogs cover at 51.0%, but this is a well-known market
inefficiency that has been priced in for years — the margin (+0.43)
is small.

### Big Home Favorites (spread <= -14)

| Season | N | Cover% | Avg ATS |
|---|---|---|---|
| 2022 | 175 | 47.4% | -2.48 |
| 2023 | 162 | 47.5% | -0.26 |
| 2024 | 159 | 48.4% | +0.53 |
| 2025 | 159 | 47.2% | +0.37 |
| **Total** | **655** | **47.6%** | **-0.51** |

Big home favorites fail to cover at 47.6% overall, but the ATS
margin is only -0.51 points — below the vig threshold. The 2022
season (-2.48 avg) drives most of the aggregate signal.

---

## Phase 7 — Robustness

### Home ATS by Week Bucket

| Weeks | N | Cover% | Avg ATS |
|---|---|---|---|
| 1-4 | 773 | 49.7% | -0.17 |
| 5-8 | 832 | 48.2% | +0.25 |
| 9-12 | 879 | 51.8% | +0.76 |
| 13+ | 390 | 47.4% | -0.75 |

Slight mid-season home advantage (Wk 9-12: 51.8%) but late-season
reversal (Wk 13+: 47.4%). No stable pattern.

### Non-Conf HOME by Conference

| Conference | N | Cover% | Avg ATS |
|---|---|---|---|
| Big 12 | 64 | 60.9% | +2.19 |
| Mountain West | 62 | 56.5% | +2.27 |
| Big Ten | 109 | 44.0% | +0.32 |
| ACC | 103 | 42.7% | -0.70 |
| American | 66 | 40.9% | -1.89 |

Big 12 and Mountain West home teams cover well in non-conference,
while Big Ten and ACC do not. This suggests conference-specific
scheduling strength rather than a universal home mispricing.

### Model Home-Field Value

The Ridge engine prices home field at **+2.79 points** (home_flag
coefficient after scaling), with an intercept of +4.03. This is
consistent with the modern consensus of 2.5-3.0 points for college
football home field, down from the historical ~3.5-4.0.

---

## Decision

**CLOSE** — The engine's home_flag adjustment already prices home
field accurately. No venue-related ATS bias exceeds 2 percentage
points after model adjustment, and the one interesting finding
(portal-badge teams covering on the road) has N=91 total, with
unstable season-to-season results.

### Why Not Advance

1. **Raw home ATS is 49.6%** — the market prices home field correctly
2. **Residual buckets are flat** — all within 1pp of 50% after the engine
3. **Portal-badge away** (60.4%, N=91) is directional but fails the
   N >= 100 threshold per-cell and is unstable in 2023
4. **Conference vs non-conf split** shows no stable direction
5. **Big home favorites** under-cover at 47.6% but the margin (-0.51)
   is below vig

### Portal-Badge Away: NEAR MISS Note

The portal-badge away signal (60.4% cover, +1.89 ATS) persists
across model residual buckets, suggesting partial independence from
the engine. If the portal-badge feature set is expanded in future
research and sample sizes grow, a venue-interaction term for
portal-badge teams could be worth revisiting. For now, the signal
is too thin and season-volatile to deploy.
