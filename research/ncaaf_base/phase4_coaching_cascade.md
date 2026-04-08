# NCAAF Coaching Cascade — Phase 4 Results

**Date:** 2026-04-08

**Hypothesis:** NEW HC + LARGE PORTAL INFLOW creates a market-mispriced state where the market has not yet calibrated to roster transformation.

**Definition:**
- `new_hc`: Head coach differs from prior season (CFBD coaches API, 2021-2025)
- `large_portal_inflow`: Portal incoming star total in top quartile for that season
- `cascade_flag`: new_hc AND large_portal_inflow

**Data:** CFBD coaches 2021-2025, CFBD portal 2022-2025, canonical games 2022-2025

---

## Phase 1: Cascade Flag Construction

| Season | Cascade Team-Seasons | Q75 Portal Stars Threshold |
|--------|---------------------|---------------------------|
| 2022 | 24 | 24.5 |
| 2023 | 16 | 32.0 |
| 2024 | 22 | 41.0 |
| 2025 | 26 | 50.8 |
| **Total** | **88** | |

Total new HC team-seasons across all FBS: 122.
Of those, 88 also had top-quartile portal inflow (72%).

Notable examples: 2022 USC (Lincoln Riley, 68 stars in), 2023 Colorado (Deion Sanders, 149 stars in), 2024 Indiana (Curt Cignetti, 85 stars in), 2025 Purdue (51 players, 147 stars in).

Total cascade team-game observations: 989 (985 excluding pushes).

---

## Phase 2: Raw ATS Test

| Split | N | Covers | Cover% | Mean ATS | p-value |
|-------|---|--------|--------|----------|---------|
| **All** | 985 | 485 | 49.2% | -0.44 | 0.6949 |
| Weeks 1-4 | 265 | 118 | 44.5% | -0.96 | 0.9674 |
| Weeks 5+ | 720 | 367 | 51.0% | -0.24 | 0.3140 |

### By Season — All Weeks

| Season | N | Cover% | Mean ATS |
|--------|---|--------|----------|
| 2022 | 268 | 50.7% | -0.45 |
| 2023 | 181 | 47.5% | -1.71 |
| 2024 | 245 | 46.5% | -0.10 |
| 2025 | 291 | 51.2% | +0.09 |

### By Season — Weeks 1-4

| Season | N | Cover% | Mean ATS |
|--------|---|--------|----------|
| 2022 | 75 | 37.3% | -4.67 |
| 2023 | 52 | 48.1% | +0.33 |
| 2024 | 63 | 44.4% | +0.47 |
| 2025 | 75 | 49.3% | +0.65 |

### By Season — Weeks 5+

| Season | N | Cover% | Mean ATS |
|--------|---|--------|----------|
| 2022 | 193 | 56.0% | +1.19 |
| 2023 | 129 | 47.3% | -2.53 |
| 2024 | 182 | 47.3% | -0.30 |
| 2025 | 216 | 51.9% | -0.10 |

No coherent ATS direction. Overall 49.2% cover rate is below 50%. Weeks 1-4 actually show *worse* performance (44.5%), opposite of the hypothesis that early-season uncertainty benefits cascade teams. Weeks 5+ marginally above 50% but driven entirely by 2022 (56.0%) with no consistency.

---

## Phase 3: Favored vs Underdog

| Split | N | Cover% | Mean ATS | p-value |
|-------|---|--------|----------|---------|
| Favored | 401 | 46.4% | -0.71 | 0.9330 |
| Underdog | 583 | 51.1% | -0.29 | 0.3096 |

Cascade teams are more often underdogs (59% of games). Neither split produces a meaningful edge.

### Favored by Season

| Season | N | Cover% | Mean ATS |
|--------|---|--------|----------|
| 2022 | 108 | 45.4% | -1.52 |
| 2023 | 79 | 39.2% | -3.16 |
| 2024 | 110 | 45.5% | -0.23 |
| 2025 | 104 | 53.8% | +1.47 |

When favored, cascade teams underperform ATS in 3 of 4 seasons. Only 2025 is above 50%.

### Underdog by Season

| Season | N | Cover% | Mean ATS |
|--------|---|--------|----------|
| 2022 | 159 | 54.1% | +0.12 |
| 2023 | 102 | 53.9% | -0.59 |
| 2024 | 135 | 47.4% | -0.00 |
| 2025 | 187 | 49.7% | -0.67 |

Underdog cascade teams show mild cover rates in 2022-2023 but fade in 2024-2025. Not stable.

---

## Phase 4: Portal Shock Interaction

Net star shock thresholds: Q25 = -29 (negative shock), cascade-specific Q75 = -2.0 (positive shock).

| Shock Bucket | N | Cover% | Mean ATS | p-value |
|-------------|---|--------|----------|---------|
| Negative (<= -29) | 155 | 48.4% | -1.14 | 0.6850 |
| Positive (>= -2) | 268 | 50.7% | +0.21 | 0.4273 |
| Middle | 562 | 48.8% | -0.55 | 0.7365 |

No shock bucket produces a meaningful signal. The negative shock group (heavy outgoing losses paired with new HC + big inflow) actually underperforms.

### Negative Shock by Season

| Season | N | Cover% | Mean ATS |
|--------|---|--------|----------|
| 2022 | 9 | 44.4% | -6.89 |
| 2023 | 47 | 40.4% | -2.10 |
| 2024 | 55 | 41.8% | -3.03 |
| 2025 | 44 | 65.9% | +3.43 |

2025 spike at 65.9% (p=0.024) but preceded by 3 consecutive losing seasons. Classic single-season outlier.

---

## Phase 5: Residual Check (Base Engine)

Model edge mean: +0.80 (model tends to like cascade teams slightly more than market).
Model edge median: +0.95.

| Model Split | N | Cover% | Mean ATS |
|------------|---|--------|----------|
| Model Likes (edge > 1) | 485 | 48.5% | -0.51 |
| Agree (-1 to 1) | 120 | 44.2% | -0.56 |
| Market Likes (edge < -1) | 380 | 51.8% | -0.30 |

The model slightly overvalues cascade teams (positive edge mean) but they still fail to cover. Residual mean = -1.24 points — cascade teams *underperform* model predictions by 1.24 points on average.

This is the opposite of the hypothesis. The model already slightly favors cascade teams, and they don't even cover that inflated expectation.

---

## Phase 6: Returning Production Split

Threshold: returning_ppa median = 0.551.

| Split | N | Cover% | Mean ATS | p-value |
|-------|---|--------|----------|---------|
| High Returning (>= 0.551) | 301 | 46.2% | -1.57 | 0.9168 |
| Low Returning (< 0.551) | 684 | 50.6% | +0.06 | 0.3945 |

High returning production *hurts* cascade teams ATS. Low returning is coin-flip. Neither is usable.

### Cross-Cuts

| Split | N | Cover% | Mean ATS |
|-------|---|--------|----------|
| NegShock + HighRet | 42 | 50.0% | -2.12 |
| NegShock + LowRet | 113 | 47.8% | -0.77 |
| PosShock + HighRet | 88 | 47.7% | -1.47 |

All cross-cuts at or below 50%. No actionable sub-bucket.

---

## Phase 7: Robustness

### By Conference

| Conference | N | Cover% | Mean ATS |
|-----------|---|--------|----------|
| ACC | 98 | 46.9% | -0.66 |
| American Athletic | 121 | 52.9% | +0.31 |
| Big 12 | 89 | 41.6% | -2.84 |
| Big Ten | 114 | 44.7% | -1.57 |
| Conference USA | 93 | 52.7% | +0.24 |
| FBS Independents | 22 | 54.5% | +2.25 |
| Mid-American | 44 | 45.5% | -2.82 |
| Mountain West | 136 | 53.7% | +1.47 |
| Pac-12 | 91 | 54.9% | +0.07 |
| SEC | 78 | 44.9% | -1.23 |
| Sun Belt | 99 | 48.5% | -0.27 |

Power conferences (Big 12, Big Ten, SEC) all under 50%. Mid-major conferences (AAC, C-USA, MW, Pac-12) slightly above but none with meaningful ATS margins or significance.

### Additional Splits

| Split | N | Cover% | Mean ATS |
|-------|---|--------|----------|
| Big Favorites (< -10) | 130 | 44.6% | -1.98 |
| Big Underdogs (> 10) | 284 | 52.8% | +1.04 |
| Home | 484 | 49.0% | -0.57 |
| Away | 501 | 49.5% | -0.31 |
| Weeks 1-2 | 126 | 45.2% | -0.63 |

### Season Stability

| Season | Cover% | Direction |
|--------|--------|-----------|
| 2022 | 50.7% | OVER |
| 2023 | 47.5% | UNDER |
| 2024 | 46.5% | UNDER |
| 2025 | 51.2% | OVER |

Only 2 of 4 seasons above 50%. Alternating direction. No stability.

---

## Summary

The coaching cascade hypothesis (new HC + large portal inflow = market mispricing) produces **no actionable signal**:

1. **Overall ATS: 49.2%** — below break-even, mean ATS = -0.44 points
2. **Early season (W1-4): 44.5%** — actively wrong direction, suggesting markets are *not* slow to adjust
3. **No stable sub-bucket** — favored/underdog, shock interaction, returning production, and conference splits all fail to produce consistent cover rates above 50%
4. **Model residual: -1.24** — cascade teams underperform even the base engine's expectations
5. **Season stability: 2/4** — no consistent direction year-over-year
6. **Total N = 985** — ample sample, result is not from thin data

The market appears to correctly price (or slightly overvalue) coaching overhauls with large portal inflow. This is consistent with the base engine's diff_new_coach coefficient being near-zero (-0.03).

---

## Verdict

**CLOSE**

No coherent direction, no stable sub-bucket, seasons alternate above/below 50%. The cascade flag adds no information beyond what the market already prices. Do not pursue as an overlay candidate.
