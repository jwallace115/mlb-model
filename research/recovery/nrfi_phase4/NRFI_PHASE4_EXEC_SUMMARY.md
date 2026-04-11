# NRFI Phase 4 -- Executive Summary

**Date:** 2026-04-11
**Scope:** Minimal selector build + historical top-3/top-4 card test using ONLY production-safe variables
**Data:** 9,900 games (2022-2026), 6,635 with F5 lines

---

## Verdict: **SELECTOR IS ENOUGH**

The simplest selector (V1: F5 ascending + disqualify night at F5=4.0) delivers the best
card hit rate: 34.9% on Top-3 (+9.7pp vs random) and 23.5% on Top-4 (+7.5pp vs random).
Adding complexity (V2, V3) **hurts** performance -- the additional disqualifiers and boosts
reduce the qualifying pool and introduce noise without improving accuracy.

**Recommended selector: V1 (F5 ascending, disqualify night at F5=4.0 exactly).**

---

## Production-Safe Variables Used

| Variable | Source | PIT-Safe |
|----------|--------|----------|
| F5 closing total | f5_lines_historical.parquet | Yes |
| Full-game closing total | mlb_odds_closing_canonical.parquet | Yes |
| Day/night flag | local_start_hour from game_table | Yes |
| Park factor | Static constants (config.py) | Yes |
| Temperature | Open-Meteo game-time forecast | Yes |
| Wind speed | Open-Meteo game-time forecast | Yes |
| Umpire over_rate | Static career ratings | Yes |
| SP first-inning NRFI rate | PIT-safe rolling from linescore cache | Yes |
| Team totals | Canonical odds | Yes |

**Excluded:** Top-3 lineup variables (RESEARCH-ONLY), season-level aggregates, any non-PIT-safe features.

---

## Selector Definitions

| Selector | Logic |
|----------|-------|
| **V1** | F5 ascending sort. Disqualify night games at F5=4.0. |
| **V2** | V1 + Gate C premium (total<=8.5 & F5<=4.0 boosted). SP 1st-inning NRFI>0.65 in Gate C gets extra boost. |
| **V3** | V2 + day game boost + cold/day/low-total disqualifier + night/mid-F5 penalty + wind boost + park factor tiebreak. |

---

## Top-3 Card Results

| Method | Slates | Leg% | Card% | vs Random |
|--------|--------|------|-------|-----------|
| Random F5<=4.0 | MC | 63.3% | 25.2% | -- |
| Pure F5-sort | 226 | 67.4% | 32.7% | +7.6pp |
| **V1** | **192** | **69.3%** | **34.9%** | **+9.7pp** |
| V2 | 192 | 68.2% | 33.9% | +8.7pp |
| V3 | 183 | 66.5% | 31.1% | +6.0pp |

## Top-4 Card Results

| Method | Slates | Leg% | Card% | vs Random |
|--------|--------|------|-------|-----------|
| Random F5<=4.0 | MC | 63.3% | 16.0% | -- |
| Pure F5-sort | 128 | 67.6% | 21.9% | +5.9pp |
| **V1** | **102** | **70.3%** | **23.5%** | **+7.5pp** |
| V2 | 102 | 69.1% | 23.5% | +7.5pp |
| V3 | 92 | 69.3% | 21.7% | +5.7pp |

---

## V1 Top-3 Season Stability

| Season | Slates | Leg% | Card% |
|--------|--------|------|-------|
| 2023 | 33 | 68.7% | 39.4% |
| 2024 | 88 | 69.3% | 34.1% |
| 2025 | 71 | 69.5% | 33.8% |

Drift: 5.6pp (2023 to 2025). All three seasons above 33%. Stable.

## V1 Top-4 Season Stability

| Season | Slates | Leg% | Card% |
|--------|--------|------|-------|
| 2023 | 8 | 71.9% | 25.0% |
| 2024 | 55 | 70.9% | 27.3% |
| 2025 | 39 | 69.2% | 17.9% |

2025 drops to 17.9% -- smaller sample (39 slates) but still above random (16.0%).

## V1 Top-3 Monthly Stability

| Month | Slates | Leg% | Card% |
|-------|--------|------|-------|
| March | 4 | 83.3% | 75.0% |
| April | 27 | 67.9% | 29.6% |
| May | 44 | 67.4% | 29.5% |
| June | 30 | 70.0% | 36.7% |
| July | 26 | 73.1% | 42.3% |
| August | 25 | 70.7% | 36.0% |
| Sept | 36 | 66.7% | 33.3% |

All months except March (N=4) cluster 29-42% card rate. No seasonal collapse.

---

## Head-to-Head: V3 vs V1

| Card Size | Common Dates | V3 Wins | V1 Wins | Ties |
|-----------|-------------|---------|---------|------|
| Top-3 | 183 | 12 | 22 | 149 |
| Top-4 | 92 | 4 | 8 | 80 |

V1 wins nearly 2:1 on dates where they differ. The extra complexity in V3 is counter-productive.

---

## Baselines

| Metric | Value |
|--------|-------|
| Blind NRFI rate (all 9,900 games) | 51.2% |
| Gate B (F5<=4.0) NRFI rate (1,250 games) | 63.3% |
| Gate A (F5<=3.5) NRFI rate (1,050 games) | 65.5% |
| Gate C (total<=8.5 & F5<=4.0) NRFI rate (844 games) | 62.9% |

---

## Economics (illustrative)

At -150 NRFI pricing (60% implied):
- Single leg decimal payout: 1.667
- 3-leg parlay payout: 4.63x
- 4-leg parlay payout: 7.72x

**V1 Top-3:** Card rate 34.9% x 4.63 = **1.62x** return per dollar (**+61.6% EV**)
**V1 Top-4:** Card rate 23.5% x 7.72 = **1.82x** return per dollar (**+81.6% EV**)

With 33% SGP boost:
V1 Top-3: 34.9% x 6.16 = 2.15x (+114.9% EV)
V1 Top-4: 23.5% x 10.26 = 2.41x (+141.5% EV)

At -140 pricing:
V1 Top-3: 34.9% x 5.19 = 1.81x (+81.3% EV)
V1 Top-4: 23.5% x 8.78 = 2.06x (+106.3% EV)

**Caveat:** These are parlay EVs assuming independent legs. Actual SGP pricing may differ.

---

## Key Findings

1. **F5 line is the dominant selector.** Pure F5-sort alone gets Leg% from 63.3% to 67.4%.
2. **V1 (simplest) is the best selector.** Adding one rule (disqualify night at F5=4.0) lifts Leg% to 69.3% and Card% to 34.9%.
3. **More complexity hurts.** V2 and V3 add rules that reduce the qualifying pool and introduce noise. V3 underperforms even pure F5-sort on card hit rate.
4. **Season stability is strong.** V1 Top-3 card rate: 39.4% (2023), 34.1% (2024), 33.8% (2025) -- 3/3 seasons above 33%.
5. **Top-3 is more practical than Top-4.** Top-4 has higher per-leg EV but lower card hit rate and 2025 showed more volatility (17.9% vs 33.8%).
6. **Qualifying pool of 3-4 games is the sweet spot.** Pool sizes 3-4 produce Leg% 68-69%, Card% 20-35%. Pools of 7+ collapse (N too small to assess).
7. **Summer months (June-August) are strongest.** Card rates 36-42% vs 29-33% in spring/fall, consistent with Phase 3B day-game findings.

---

## Recommended Production Selector

```
QUALIFY: F5 closing total <= 4.0
DISQUALIFY: night game AND F5 total == 4.0
RANK BY: F5 total ascending
CARD SIZE: Top 3 (preferred) or Top 4
```

This selector uses exactly two variables (F5 total, day/night flag) and one disqualifier rule.
It is fully PIT-safe and can be computed the moment F5 lines are posted.

---

## Files Produced

| File | Description |
|------|-------------|
| `nrfi_phase4_selector.py` | Full analysis script |
| `nrfi_phase4_selector_table.parquet` | Full selector table (9,900 games) |
| `NRFI_PHASE4_FINAL_TABLE.csv` | Comparison table: all methods x card sizes |
| `NRFI_PHASE4_EXEC_SUMMARY.md` | This file |
