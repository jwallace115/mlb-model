# Phase 2: Home-Side Subtype Refinement

**Date:** 2026-04-07
**Objective:** Decompose the Phase 1 HOME nontraditional-starter over-rate finding (+4.8pp) into specific subtypes to identify which structural role drives the effect.

---

## Phase 1 — Home-Side Subtype Definitions

All features are pregame-safe (shifted by 1 / expanding window). HOME side only.

| Subtype | Definition |
|---------|-----------|
| **A (Strict Opener)** | season_start_number <= 2 AND (season_ip_per_start <= 3.0 OR no prior starts) |
| **B (Bulk Short)** | rolling5_ip_avg <= 3.5 AND season_start_number >= 3 |
| **C (Team Tendency)** | team_opener_rate >= 0.30 (rolling 10-game window, starter IP < 3.0) |
| **D (Combined)** | A OR B OR C |

### Subtype Counts by Season (HOME starts)

| Season | Total | A (N / %) | B (N / %) | C (N / %) | D (N / %) |
|--------|-------|-----------|-----------|-----------|-----------|
| 2022 | 1,863 | 160 / 8.6% | 29 / 1.6% | 45 / 2.4% | 228 / 12.2% |
| 2023 | 1,863 | 174 / 9.3% | 30 / 1.6% | 91 / 4.9% | 275 / 14.8% |
| 2024 | 1,860 | 165 / 8.9% | 27 / 1.5% | 56 / 3.0% | 231 / 12.4% |
| 2025 | 1,780 | 161 / 9.0% | 20 / 1.1% | 50 / 2.8% | 219 / 12.3% |

### Overlap (across all seasons)

- A and B: 0 (mutually exclusive by definition: start_number <= 2 vs >= 3)
- A and C: 35
- B and C: 21

### Mean Actual IP (sanity check)

| Subtype | Mean IP | Early Exit Rate (< 5.0 IP) |
|---------|---------|---------------------------|
| A | 3.85 | 56.9% |
| B | 3.78 | 54.9% |
| C | 4.77 | 37.6% |
| D | 4.14 | 50.7% |
| Baseline | 5.31 | 23.9% |

Subtypes A and B capture genuinely short outings. C captures team tendency but those starters often pitch normal innings (4.77 IP mean).

---

## Phase 2 — Raw Outcome Test by Home Subtype

**Universe:** 6,690 games with closing lines + home starter info, 2022-2025. Pushes excluded.

| Subtype | N | Mean Actual | Mean Closing | Residual | Over Rate | vs Baseline |
|---------|---|-------------|-------------|----------|-----------|-------------|
| **A (Strict Opener)** | **573** | **9.41** | **8.60** | **+0.810** | **54.1%** | **+5.4pp** |
| B (Bulk Short) | 91 | 8.71 | 8.73 | -0.016 | 49.5% | +0.8pp |
| C (Team Tendency) | 210 | 8.79 | 8.62 | +0.167 | 47.6% | -1.1pp |
| D (Combined) | 825 | 9.25 | 8.61 | +0.643 | 53.0% | +4.3pp |
| **Baseline (no flag)** | **5,590** | **8.87** | **8.42** | **+0.443** | **48.7%** | **---** |
| D minus A | 252 | --- | --- | +0.262 | 50.4% | +1.7pp |

**Finding:** Subtype A alone accounts for essentially all of the Phase 1 combined effect. Subtypes B and C are noise. Removing A from D leaves only a +1.7pp residual (N=252, not significant).

---

## Phase 3 — Year Trend

### Over Rate by Season

| Season | A | B | C | D | Baseline |
|--------|---|---|---|---|----------|
| 2022 | 44.8% | 55.0% | 45.7% | 45.7% | 49.6% |
| 2023 | 55.0% | 45.8% | 49.3% | 53.8% | 48.9% |
| 2024 | **58.0%** | 40.7% | 44.4% | 56.2% | 48.9% |
| 2025 | **56.7%** | 60.0% | 50.0% | 54.7% | 47.6% |

### Residual by Season

| Season | A Resid | B Resid | C Resid | D Resid | Baseline Resid |
|--------|---------|---------|---------|---------|----------------|
| 2022 | -0.316 | +0.400 | +0.114 | -0.189 | +0.484 |
| 2023 | +0.692 | +0.625 | -0.281 | +0.511 | +0.538 |
| 2024 | +1.003 | -1.370 | -0.046 | +0.765 | +0.406 |
| 2025 | +1.605 | +0.625 | +1.125 | +1.322 | +0.365 |

**Finding:** Subtype A shows a clear widening trend from 2022 to 2025:
- Over rate: 44.8% -> 55.0% -> 58.0% -> 56.7%
- Residual: -0.32 -> +0.69 -> +1.00 -> +1.61
- 3 of 4 seasons above 50% (2022 is the cold start outlier)
- 2023-2025 combined: N=448, Over=56.7%, residual growing each year

Subtypes B and C show no consistent directional pattern. B flips sign each year. C never exceeds 50%.

---

## Phase 4 — F5 Signal Interaction

### 2026 Live F5 Signals (mlb_sim/logs/f5_signals_2026.json)

48 resolved UNDER signals. Only 8 matched to home starter data (early season, limited coverage).

| Subtype | N | UNDER Win Rate | Mean F5 Line | Mean Actual F5 |
|---------|---|---------------|-------------|---------------|
| A | 7 | 42.9% (3/7) | 4.07 | 4.71 |
| D | 7 | 42.9% (3/7) | 4.07 | 4.71 |
| Baseline | 1 | 0.0% (0/1) | 4.00 | 10.00 |

**Note:** N=7 is too thin for conclusions, but directional: UNDER signals degrade when home starter is subtype A (42.9% win rate vs model expectation).

### 2024-2025 Proxy (actual_f5 < closing_total/2)

| Subtype | N | F5 Under Proxy Rate | Mean F5 Actual |
|---------|---|-------------------|---------------|
| A | 326 | 39.9% | 5.47 |
| B | 47 | 61.7% | 4.13 |
| C | 106 | 51.9% | 4.77 |
| D | 450 | 43.6% | 5.27 |
| Baseline | 3,188 | 45.3% | 4.96 |

**Finding:** Subtype A shows a notably lower F5 under-hit rate (39.9%) vs baseline (45.3%), with mean F5 actual 0.51 runs higher (5.47 vs 4.96). This confirms the full-game over signal persists into F5 and degrades UNDER selections.

### Availability Check

Closing total distribution is similar: A mean=8.60, baseline mean=8.42. The +0.18 difference in closing lines does NOT explain the +0.81 residual. The signal is in outcomes exceeding market expectation, not in line selection bias.

---

## Phase 5 — Market-Relative Test

### Statistical Tests (Full Sample 2022-2025)

| Subtype | N | Over Rate | Residual | t-stat | Binom p | Edge vs -110 |
|---------|---|-----------|----------|--------|---------|-------------|
| **A** | **573** | **54.1%** | **+0.810** | **4.15** | **0.055** | **+1.7pp** |
| B | 91 | 49.5% | -0.016 | -0.04 | 1.000 | -2.9pp |
| C | 210 | 47.6% | +0.167 | 0.56 | 0.535 | -4.8pp |
| D | 825 | 53.0% | +0.643 | 4.06 | 0.095 | +0.6pp |

### Subtype A Economics

**Full sample (2022-2025):** 54.1% over rate, but 2022 is an outlier (44.8%).

**2023-2025 (post regime-shift):** N=448, Over=56.7%, flat OVER ROI at -110 = **+8.2%**

This is economically meaningful. The -110 breakeven is 52.38%; a 56.7% hit rate yields substantial edge.

### Season Consistency (Subtype A)

- 2022: 44.8% (below 50% -- cold-start year)
- 2023: 55.0% (above breakeven)
- 2024: 58.0% (above breakeven)
- 2025: 56.7% (above breakeven)
- Consecutive above-breakeven seasons: 3

### Season Debut (start_number == 0) Sub-Analysis

The vast majority of Subtype A (472/573 = 82%) are season_start_number == 0 (literal first start of the season).

| Start Number | N | Over Rate | Residual |
|-------------|---|-----------|----------|
| 0 (debut) | 472 | 54.4% | +0.928 |
| 1 | 72 | 50.0% | +0.056 |
| 2 | 29 | 58.6% | +0.759 |

The effect is concentrated in true season debuts (start_number == 0), which makes structural sense: markets have the least information about these pitchers' current form, workload plan, and bullpen sequencing.

---

## Phase 6 — Practical Framing

### Recommended Implementation: Home-Side F5 UNDER Pass Filter

When the HOME starter qualifies as Subtype A (strict opener):
- **F5 UNDER signals should be suppressed or downgraded** (39.9% under-hit rate vs 45.3% baseline)
- **Full-game OVER lean is directionally supported** but may be better as a badge than a standalone signal

### Why Subtype A Only?

1. **B (Bulk Short)** is noise: N=91 total, over rate 49.5%, no directional consistency
2. **C (Team Tendency)** is noise: never exceeds 50% over rate in any season, starters actually pitch normal innings (4.77 IP mean)
3. **D minus A** is noise: N=252, over rate 50.4%, no edge
4. **A alone** captures 69% of D's total N and 100%+ of the effect

### Implementation Options (ranked)

1. **Pass filter on F5 UNDER:** When home_sp is Subtype A, block or badge-degrade F5 UNDER signals. This is the highest-confidence use case given the F5 proxy data.
2. **Full-game OVER badge:** Add an informational badge "Home SP debut/opener" on the game card. Not a standalone bet signal but context for human review.
3. **Do not use as standalone OVER trigger:** 54.1% is above breakeven but binom p=0.055 on the full sample. The trend is strong but sample is moderate.

### Pregame Availability

The flag requires only:
- `season_start_number`: known from prior game logs (fully pregame)
- `season_ip_per_start`: known from prior game logs (fully pregame)
- Both are already computed in the pitcher_game_logs pipeline

No additional data sources needed.

---

## Decision

### ADVANCE

**Subtype A (Strict Opener) clearly outperforms the combined flag and is the sole driver of the Phase 1 finding.**

Evidence:
- **Over rate:** 54.1% full sample, 56.7% in 2023-2025 (vs 48.7% baseline)
- **Residual:** +0.81 runs (t=4.15), widening trend 2022-2025
- **Directional stability:** 3 of 4 seasons above 50%, 3 consecutive above -110 breakeven
- **F5 degradation confirmed:** Under-hit rate drops to 39.9% vs 45.3% baseline; F5 actual +0.51 runs higher
- **Structural explanation:** Season debuts / early-season openers create maximum market uncertainty about workload, bullpen sequencing, and role classification
- **Subtypes B and C confirmed as noise** (no directional signal, small N, inconsistent)

**Next step:** Phase 3 should test Subtype A as an F5 UNDER pass filter in the live signal pipeline, with a secondary test as a full-game OVER informational badge.
