# NRFI Phase 1B Data Audit — Executive Summary

**Date:** 2026-04-11
**Scope:** Inventory team-level early-scoring variables for NRFI model enrichment

---

## Bottom Line

We have **sufficient data in hand** to build team-total-enriched NRFI features
for 2024-2025 (4,893 games with team totals, 4,399 with NRFI market prices).
No expensive Odds API backfill is required. F5 team totals and 1st-inning
team totals **do not exist as markets** and cannot be pulled.

## Data Assets Confirmed

| Asset | Games | Seasons | Key Variables |
|-------|-------|---------|---------------|
| Full-game team totals | 4,893 | 2024-25 | home_total_line, away_total_line |
| NRFI/YRFI market prices | 4,399 | 2024-25 | nrfi_under_price, yrfi_over_price |
| NRFI actuals | 9,900 | 2022-26 | nrfi, yrfi, away_1st_runs, home_1st_runs |
| F5 game total | 6,910 | 2023-25 | f5_total (game-level only) |

## Structural Preview Results (5,398 games)

1. **tt_max (stronger offense)** is the key NRFI discriminator:
   - tt_max=3.5 → 55.0% NRFI | tt_max=5.5 → 44.1% NRFI (10.9pp spread)

2. **both_below_4** is the strongest binary flag:
   - True → 55.0% NRFI | False → 50.0% NRFI (+5.0pp lift)

3. **TT sum** shows clean monotonic decline:
   - Sum <= 7.0 → 54.1% NRFI | Sum > 9.5 → 42.7% NRFI (11.4pp spread)

4. **NRFI market is systematically biased toward NRFI** by 1.4-4.1pp across
   all implied probability quintiles. YRFI appears to be the value side.

## Feasibility Classification

- **FEASIBLE NOW (8 variables):** home/away_total_line, tt_max, tt_min,
  tt_dispersion, both_below_4, nrfi_market_price, nrfi_implied_prob
- **NOT FEASIBLE (4 variables):** F5 team totals, 1st-inning team totals
  (markets do not exist); 2022 team totals (expired from API)

## Recommended Next Steps

1. **Merge team totals into Phase 1 research table** for 2024-2025 subset
   and test as features in the NRFI model alongside SP metrics.
2. **Add NRFI market price capture** to the daily pipeline for 2026
   (minimal credit cost, ~240 total for the season).
3. **Investigate YRFI value** — the systematic NRFI overpricing (1.4-4.1pp)
   suggests YRFI may be the actionable side, not NRFI.
4. **Do NOT attempt** to pull F5 team totals or 1st-inning team totals
   — these markets do not exist on any sportsbook via the Odds API.

## Files Produced

| File | Description |
|------|-------------|
| phase0_framing_memo.md | Research question and variable definitions |
| phase1_data_inventory.md | Complete inventory of all relevant data sources |
| phase3_feasibility_map.md | Per-variable FEASIBLE/NOT FEASIBLE classification |
| phase4_structural_preview.md | NRFI rate analysis by team total decomposition |
| phase5_odds_api_gap_list.md | What to pull and what is permanently unavailable |
| variable_feasibility.csv | Machine-readable feasibility table (12 variables) |
| team_total_nrfi_preview.csv | 5,398-row merged dataset for downstream analysis |
| run_preview.py | Reproducible analysis script |
