# NRFI Phase 1B — Data Inventory

## 1. Canonical Odds (mlb_sim/data/mlb_odds_closing_canonical.parquet)

- **Shape:** 11,406 rows x 24 columns
- **Date range:** 2022-04-07 to 2025-09-29
- **Seasons:** 2022 (2,458), 2023 (3,956), 2024 (2,488), 2025 (2,504)
- **Team total columns:** home_total_line, away_total_line, home/away_total_over/under_price
- **Team total coverage by season:**
  - 2022: 0/2,458 (0.0%)
  - 2023: 650/3,956 (16.4%)
  - 2024: 2,441/2,488 (98.1%)
  - 2025: 2,452/2,504 (97.9%)
- **home_total_line distribution:** mean=4.08, std=0.65, range [2.5, 6.5]
- **Most common lines:** 4.5 (2,644), 3.5 (2,424), 5.5 (331)

## 2. F5 Lines (mlb_sim_f5/data/f5_lines_historical.parquet)

- **Shape:** 6,910 rows x 15 columns
- **Date range:** 2023-05-03 to 2025-09-29
- **Available:** f5_total (game-level), f5_moneyline_home/away
- **NOT available:** F5 team totals (no home/away F5 team total columns)

## 3. Alt Totals (mlb_sim/data/mlb_alt_totals_historical.parquet)

- **Shape:** 674,990 rows x 10 columns
- **Available:** line_value, over_price, under_price (game-level alt lines)
- **NOT available:** team-level alt totals

## 4. YRFI/NRFI Odds (research/yrfi/data/)

- **yrfi_lines_historical.parquet:** 4,399 rows, 2024-03-28 to 2025-09-28
  - Columns: yrfi_over_price, nrfi_under_price, yrfi_line (always 0.5)
  - These are game-level NRFI/YRFI O/U 0.5 prices
- **yrfi_actuals.parquet:** 4,399 rows, matching actuals
  - first_inning_runs_home, first_inning_runs_away, first_inning_total, yrfi_result

## 5. NRFI Research Table (research/recovery/nrfi_phase1/)

- **Shape:** 9,900 rows x 22 columns
- **Date range:** 2022-04-07 to 2026-04-09
- **Key columns:** game_pk, nrfi, yrfi, closing_total, closing_f5_total, SP metrics, park/weather

## 6. Team Totals 2026 (mlb_sim/data/team_totals_2026.json)

- **28 records** (current/recent games)
- **Structure:** home_total_line, away_total_line per game

## 7. Odds API Market Inventory (confirmed)

Per market inventory doc, the Odds API historical endpoint supports:
- **team_totals** — full-game team totals (confirmed working)
- **totals_1st_1_innings** — first inning O/U (confirmed working, used in YRFI backfill)
- **totals_1st_5_innings** — F5 game total (confirmed working)
- F5 team totals — NOT a standard market (does not exist)
