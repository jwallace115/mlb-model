# ST02 Deep Analysis — road_trip_game_6plus_away

Signal: `road_trip_game_num_away >= 6`
Direction: UNDER (away team fatigue on extended road trips)
Coverage: 4855 games (2024-2025), 4666 non-push
Prevalence: 1208 games (24.9%)
Baseline: error=+0.442, under_rate=0.509

## Test 1 — Tail Structure

| Bucket | N (non-push) | Under Rate | Mean Error | Resid vs Non-ST02 | ROI @-110 |
|--------|-------------|-----------|-----------|-------------------|-----------|
| Non-ST02 | 3513 | 0.501 | +0.534 | — | -4.4% |
| Game 6 | 609 | 0.534 | +0.027 | -0.507 | +1.9% |
| Game 7 | 249 | 0.502 | +0.665 | +0.131 | -4.2% |
| Game 8 | 124 | 0.556 | +0.338 | -0.195 | +6.2% |
| Game 9+ | 171 | 0.567 | -0.185 | -0.719 | +8.3% |
| **All ST02** | **1153** | **0.534** | **+0.166** | **-0.367** | **+2.0%** |

Effect strengthens monotonically as trip lengthens: **NO** (non-monotonic)

## Test 2 — Season Stability

| Year | Coefficient | p-value | R² |
|------|-----------|---------|-----|
| 2024 | -0.2720 | 0.1709 | 0.000773 |
| 2025 | -0.4645 | 0.0285 | 0.001975 |

Verdict: **STABLE** — coefficient negative both years

## Test 3 — Robustness Controls

OLS: market_error ~ st02 + closing_total + home_sp_xfip + away_sp_xfip + park_run_factor + temperature

- ST02 coefficient: -0.3579
- ST02 p-value: 0.0135
- N (with all controls): 4855

Verdict: **ROBUST**

## Test 4 — Market Awareness

- corr(ST02, closing_total): r=0.0388, p=0.0068
- Avg closing total — ST02: 8.46, non-ST02: 8.38, diff=+0.081

Market does NOT lower totals for long road trips. Signal is **mostly unpriced**.

## Test 5 — Travel Geography

| Subset | N (non-push) | Under Rate | Mean Error | ROI @-110 |
|--------|-------------|-----------|-----------|-----------|
| West Coast away | 249 | 0.510 | +0.184 | -2.6% |
| Cross-country (tz≥2) | 21 | 0.571 | +0.500 | +9.1% |
| Same-region (tz=0) | 1106 | 0.539 | +0.088 | +2.9% |

## Test 6 — Interaction with P09

P09 coverage within dataset: 4855/4855 (100.0%)

| Cohort | N (non-push) | Under Rate | Mean Error | ROI @-110 |
|--------|-------------|-----------|-----------|-----------|
| Neither | 3395 | 0.500 | +0.540 | -4.6% |
| ST02 only | 1110 | 0.538 | +0.160 | +2.7% |
| P09 only | 118 | 0.534 | +0.341 | +1.9% |
| ST02 + P09 | 43 | 0.442 | +0.312 | -15.6% |

## Test 7 — Permutation (2025 only)

- 2025 ST02: N=597, under_rate=0.556, ROI@-110=+6.1%
- Permutation (200 shuffles): median=-1.8%, p5=-6.4%, p95=+4.1%
- Observed ROI percentile: 99.5%
- Under rate percentile: 98.5%

## Test 8 — Practical Deployment Profile

| Season | ST02 Games | Total Games | Prevalence | Per Week |
|--------|-----------|-------------|-----------|----------|
| 2024 | 611 | 2427 | 25.2% | 23.5 |
| 2025 | 597 | 2428 | 24.6% | 23.0 |

Average: ~23.2 games/week during regular season

## Final Verdict

### Scorecard

| Test | Result | Notes |
|------|--------|-------|
| T1 Tail structure | MIXED | Game 7 breaks monotonicity; effect concentrates at game 6 and 9+ |
| T2 Season stability | PASS | Negative both years; 2025 coefficient 1.7× larger than 2024 |
| T3 Robustness | PASS | p=0.013 after controlling for closing_total, SP xFIP, park, temp |
| T4 Market awareness | PASS | Market does NOT adjust — ST02 games have *higher* closing totals (+0.08) |
| T5 Geography | INFORMATIVE | Effect is in same-region trips (N=1106, +2.9% ROI), NOT cross-country |
| T6 P09 interaction | FAIL | ST02+P09 cohort (N=43) shows -15.6% ROI — signals are NOT additive |
| T7 Permutation 2025 | PASS | 99.5th percentile; under rate at 98.5th percentile |
| T8 Deployment | PASS | ~23 games/week, high prevalence |

### Key Findings

1. **Signal is real.** OLS survives controls (p=0.013), permutation at 99.5th pctile, stable across years.

2. **Signal is unpriced.** Market actually sets *higher* totals for ST02 games (+0.08 vs baseline), leaving full edge on the table.

3. **Non-monotonic tail.** Game 7 (N=249) shows no effect (under_rate=0.502, ROI=-4.2%). The signal is driven by game 6 (N=609) and games 8+ (N=295). This is a yellow flag — a clean fatigue effect should monotonically increase.

4. **Geography is surprising.** The effect concentrates in same-region trips (tz_change=0), NOT cross-country travel. West Coast away teams show no effect (-2.6% ROI). This suggests the mechanism is *cumulative road fatigue* rather than jet lag.

5. **P09 interaction is negative.** The ST02+P09 overlap (N=43) has 44.2% under rate and -15.6% ROI. These signals are redundant or interfere. Do NOT stack with P09.

6. **ROI is modest.** All-ST02 pooled: +2.0% ROI at -110 (53.4% under rate). 2025 alone is +6.1%, but 2024 was weaker. This is a thin edge — vig-sensitive.

### Verdict: **INVESTIGATE**

Not ADVANCE, not SHELVE. Reasons:

- **For:** Robust after controls, unpriced, stable direction, strong permutation
- **Against:** Non-monotonic tail, modest pooled ROI (+2.0%), P09 interference, game-7 hole

### Deployment Recommendation

- **Role:** Standalone signal, NOT overlay (fails P09 interaction test)
- **Best form if advanced:** Binary flag for V1 UNDER amplifier, similar to S12/P09 pattern
- **Threshold:** Keep >= 6 (game 6 carries half the signal volume)
- **Required next step:** Monitor in 2026 shadow mode. If 2026 under_rate ≥ 53% at N≥150, promote to overlay. If game-7 hole persists, consider restricting to game 6 + game 8+ only.
- **Do NOT stack with P09.** Deploy independently or as mutually exclusive overlay tier.

