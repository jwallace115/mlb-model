# NRFI Phase 1B — Odds API Gap List

## Currently Available Data

| Data | Source | Games | Date Range | Status |
|------|--------|-------|-----------|--------|
| Full-game team totals | canonical odds | 4,893 (2024-25) | 2024-03 to 2025-09 | IN HAND |
| NRFI/YRFI O/U 0.5 prices | yrfi_lines_historical | 4,399 | 2024-03 to 2025-09 | IN HAND |
| YRFI actuals (1st inning runs) | yrfi_actuals | 4,399 | 2024-03 to 2025-09 | IN HAND |
| F5 game total | f5_lines_historical | 6,910 | 2023-05 to 2025-09 | IN HAND |

## Gaps (Data NOT Available)

| Data | Market Key | Available from API? | Notes |
|------|-----------|-------------------|-------|
| F5 team totals | N/A | NO — does not exist | Not a standard Odds API market |
| 1st-inning team totals | N/A | NO — does not exist | Not a standard Odds API market |
| 1st-inning O/U prices for 2022-2023 | totals_1st_1_innings | EXPIRED | Events >12 months old return 404 |
| Team totals for 2022 | team_totals | EXPIRED | 0% coverage in canonical; events expired |

## Recommended Pulls (Priority Order)

### 1. Team Totals for 2026 Season (ONGOING)
- **Market key:** `team_totals`
- **Status:** Already collecting via team_totals_2026.json (28 records so far)
- **Action:** Ensure daily collection captures team totals for every game
- **Cost:** ~0 incremental (already in pipeline)

### 2. NRFI/YRFI Prices for 2026 Season (ACTIVE)
- **Market key:** `totals_1st_1_innings`
- **Status:** nrfi_helper_daily.py computes model prices; need to also capture market prices
- **Action:** Add market price capture to daily NRFI pipeline
- **Cost:** ~10 credits/day (one API call for all games)

### 3. No Historical Backfill Needed
- 2024-2025 NRFI prices and team totals are already in hand (4,399 and 4,893 games)
- 2022-2023 events have expired from the Odds API historical endpoint
- The 2024-2025 sample (2 full seasons) is sufficient for model development

## Credit Budget

| Pull | Games | Credits/Game | Total Credits |
|------|-------|-------------|---------------|
| Team totals 2026 (ongoing) | ~2,400 | 0 (in pipeline) | 0 |
| NRFI market prices 2026 | ~2,400 | ~0.1 | ~240 |
| **Total incremental** | — | — | **~240** |

No expensive backfill is required. All data gaps are either permanently
unavailable (expired) or do not exist as markets.
