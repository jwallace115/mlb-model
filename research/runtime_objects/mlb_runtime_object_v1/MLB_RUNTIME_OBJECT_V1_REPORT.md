# MLB RUNTIME OBJECT V1 — BUILD REPORT

**Build Date:** 2026-04-19 (rebuilt after session-loss event)
**Shape:** 19,430 rows x 130 columns
**Grain:** one row per (game_pk, team)
**Scope:** 2022-2025 historical only

## Merged Families
| Family | Join Key | Columns Added | Match Rate |
|---|---|---|---|
| mlb_matchup_table_base | N/A (base) | 107 | N/A |
| game_table_spine | game_pk | 22 (minus umpire ratings) | 100% |
| mlb_umpire_substrate | game_pk | 1 (umpire_matched) | 100% |

## Umpire Field Correction
`umpire_over_rate` and `umpire_k_rate` excluded from build. These derive from static seasonal constants, not historically safe for default runtime use. Historical umpire ratings must be joined separately from `mlb_umpire_historical_layer` when needed.

## Grain Integrity
- Duplicates at (game_pk, team): **0**
- Row count: **19,430** (2022-2025 only; 2026 excluded)

## Final Status
**RUNTIME_OBJECT_READY_HISTORICAL_CLEAN**
