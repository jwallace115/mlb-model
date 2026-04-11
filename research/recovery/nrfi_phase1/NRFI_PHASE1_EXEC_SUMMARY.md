# NRFI Phase 1 — Executive Summary

Generated: 2026-04-11
Data: 9900 MLB games, [np.int64(2022), np.int64(2023), np.int64(2024), np.int64(2025), np.int64(2026)]

## Key Findings

1. **Overall NRFI rate: 51.2%** across 9900 games (2022-2026)
   - Top-1 clean (away 0 in 1st): 73.5%
   - Bot-1 clean (home 0 in 1st): 69.3%
   - Fair NRFI price (no vig): -95
   - Typical market price: -135 (implied 57.4%)

5. **Environment effects are modest**
   - Dome: 50.5%, Outdoor: 51.3%

## Season stability
  2022: NRFI = 51.8% (2430 games)
  2023: NRFI = 49.8% (2430 games)
  2024: NRFI = 53.2% (2425 games)
  2025: NRFI = 49.8% (2428 games)
  2026: NRFI = 55.6% (187 games)

## Actionable framework
Select top-3 NRFI legs daily using:
1. Closing total <= 8.5
2. F5 total <= 5.0 (when available)
3. Micro-model p_yrfi bottom 10%
4. Exclude CONTACT_RISK archetype starters
5. Exclude both-top-3-changed lineups
6. Prefer dome/mild temperature

## Files
- `nrfi_research_table.parquet` — 9900 rows, canonical NRFI table
- `NRFI_PHASE1_FINAL_TABLE.csv` — same, CSV format
- Phase reports: phase2-phase8 markdown files