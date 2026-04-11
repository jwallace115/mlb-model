# NRFI Phase 3B -- Executive Summary

**Date:** 2026-04-11
**Scope:** Non-pitcher residuals (park/weather/umpire/day-night) within F5/total line gates
**Data:** 9,900 games (2022-2025), all with park/weather/umpire variables

---

## Safety Provenance

| Variable Class | Provenance | Method |
|---------------|------------|--------|
| park_factor_runs | **PIT-SAFE** | Static per-park constants from config.py (15 unique values, 1 per venue) |
| venue_name / park identity | **PIT-SAFE** | Known pre-game |
| umpire_over_rate | **PIT-SAFE** | Static career-level constant (1 unique value per umpire, 111 umpires) |
| temperature, wind_speed | **PIT-SAFE** | Game-time forecast from Open-Meteo hourly API |
| is_day_game (local_start_hour) | **PIT-SAFE** | Known pre-game from schedule |
| roof_status (dome/retractable/open) | **PIT-SAFE** | Known pre-game from venue |
| wind_direction | **UNVERIFIED** | Available but not used (no CF bearing to make directional) |

---

## Bottom Line

**Day vs. night is the strongest and most stable non-pitcher overlay for NRFI selection.**
Inside Gate A (F5 <= 4.0), day games hit 69.7% NRFI (+6.4pp over gate baseline) with
3/3 seasons same-sign and only 1.3pp drift. Night games are a reliable disqualifier at
58.8% NRFI (-4.5pp), also 3/3 seasons consistent.

Strong wind (>=15 mph) and cold+pitcher_park show large deltas but with smaller samples.
The ump_under+windy interaction in Gate C is the most stable multi-year overlay found (4/4 yrs consistent, 0.7pp drift).

Park factors, umpire tendencies, and temperature **individually** are non-factors -- they are
already embedded in the market line. They only add signal in specific interactions.

---

## Key Findings

### Tier 1: WIDENERS (positive delta, consistent multi-year stability)

| Overlay | Gate | N | NRFI% | Delta | Stability | Note |
|---------|------|---|-------|-------|-----------|------|
| day_game | A (F5<=4.0) | 515 | 69.7% | +6.4pp | 3/3 yrs, drift=1.3pp | **Best single overlay** |
| day+hitter_park | A (F5<=4.0) | 165 | 72.1% | +8.8pp | 3/3 yrs, drift=5.3pp | Counter-intuitive: hitter park + day + low line = elite SP matchup |
| day_game | B (F5<=4.5) | 1,342 | 58.3% | +3.8pp | 3/3 yrs, drift=1.8pp | High volume |
| day+hitter_park | B (F5<=4.5) | 365 | 60.5% | +6.0pp | 3/3 yrs, drift=2.8pp | Stable |
| ump_under+windy | C (total<=8) | 268 | 60.1% | +4.5pp | **4/4 yrs**, drift=0.7pp | Most stable overlay |
| strong_wind>=15 | A (F5<=4.0) | 71 | 71.8% | +8.6pp | 2/2 yrs | Small N |
| cold+pitcher_park | B (F5<=4.5) | 71 | 70.4% | +15.9pp | 2/2 yrs | Largest delta, early-season only |

### Tier 2: SELECTORS (moderate delta, less stable)

| Overlay | Gate | N | NRFI% | Delta | Stability | Note |
|---------|------|---|-------|-------|-----------|------|
| pf=94 (Oakland) | B (F5<=4.5) | 402 | 61.2% | +6.7pp | 3/3 yrs, drift=5.1pp | Venue-specific |
| strong_wind>=15 | C (total<=8) | 248 | 60.9% | +5.3pp | 3/4 yrs | 2025 flipped (N=11) |
| strong_wind>=15 | D (total<=9) | 411 | 57.2% | +4.4pp | 3/4 yrs | 2023 negative |

### Tier 3: DISQUALIFIERS (negative delta, consistent)

| Overlay | Gate | N | NRFI% | Delta | Stability | Note |
|---------|------|---|-------|-------|-----------|------|
| night_game | A (F5<=4.0) | 735 | 58.8% | **-4.5pp** | 3/3 yrs, drift=0.7pp | Very stable penalty |
| day+cold | C (total<=8) | 179 | 48.6% | **-7.0pp** | 4/4 yrs | Cold hurts pitcher grip in low-total context |
| indoor | D (total<=9) | 316 | 50.0% | -2.8pp | 3/4 yrs | Removes weather edge |

### NON-FACTORS (already priced into line)

| Variable | Why non-factor |
|----------|---------------|
| park_factor_runs (pitcher/neutral/hitter buckets) | Already embedded in line. Direction flips by gate (selection effect). |
| umpire_over_rate alone | Full-game tendency doesn't predict 1st inning. Only works in interaction. |
| temperature alone | Cold helps ball die but also hurts pitcher grip. Net effect ~zero. |

---

## Counter-Intuitive Finding: Hitter Parks Help NRFI in Low-Line Gates

In Gates A and B (low F5 lines), hitter-friendly parks (pf >= 103) show **higher** NRFI rates
than pitcher-friendly parks. This is a selection effect: when the market sets a very low line
despite a hitter-friendly park, it implies elite SP matchup quality that overwhelms the park effect.
The market has already discounted the park; the residual is elite pitching.

---

## Practical Decision Rules for Daily Card

### PLAY signals (additive to existing gates):
1. **Gate A + day game** -> upgrade confidence (+6.4pp)
2. **Gate A + day + hitter park** -> strongest combo (+8.8pp)
3. **Gate B + day game** -> widen to include (+3.8pp, high volume)
4. **Gate C + ump_under + windy** -> most stable interaction (+4.5pp)
5. **Any gate + strong wind >=15** -> boost (+5-9pp)

### SKIP signals:
1. **Gate A + night game** -> downgrade (-4.5pp, very stable)
2. **Gate C + day + cold** -> skip (-7.0pp, counter-intuitive but 4yr consistent)
3. **Gate D + indoor** -> skip (-2.8pp)

---

## Weather Provenance Note

Temperature and wind_speed in game_table come from Open-Meteo hourly API forecasts
(game-time resolution), confirmed in `modules/weather.py`. This satisfies the PIT-safety
requirement for game-time conditions. Wind direction is available but not used directionally
(no CF bearing transformation was applied for this analysis).

---

## Files Produced

| File | Description |
|------|-------------|
| `nrfi_phase3b_research_table.parquet` | Full research table with derived variables |
| `univariate_all_games.csv` | Univariate screen across all 9,900 games |
| `univariate_within_gates.csv` | Univariate screen within each gate |
| `interactions_within_gates.csv` | Interaction tests within each gate |
| `stability_split_half.csv` | Train/test split-half stability |
| `year_by_year.csv` | Year-by-year breakdown for key combos |
| `NRFI_PHASE3B_FINAL_TABLE.csv` | Classification table (widener/selector/disqualifier/non-factor) |
| `NRFI_PHASE3B_EXEC_SUMMARY.md` | This file |
