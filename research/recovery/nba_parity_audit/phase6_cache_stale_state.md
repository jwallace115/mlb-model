# Phase 6: Cache/Stale State

## Data File Ages

| File | Last Modified | Staleness |
|------|---------------|-----------|
| nba/data/ridge_model.pkl | 2026-04-01 | Current (trained once, stable) |
| nba/data/features.parquet | 2026-04-01 | Training-era only, not stale |
| nba/data/box_stats.parquet | 2026-04-01 | Training-era only (7,380 rows) |
| nba/data/predictions.parquet | 2026-04-01 | Training-era only |
| nba/data/nba_results_log.parquet | 2026-04-10 | Current (updated daily) |
| nba/data/nba_signal_log.parquet | 2026-04-10 | Current (updated daily) |

## Frozen Team Lists
All archetype team sets are hardcoded in run_nba.py (lines 571-718):
- **_ELITE_DEF, _ELITE_DEF2:** Frozen, no dynamic update mechanism
- **_ROAD_WARRIOR, _STRONG_HOME:** Frozen, last pruned 2026-03-22
- **_CORE_AWAY, _CORE_HOME:** Frozen subset
- **_BALANCED_OFF, _PASSIVE_DEF:** Frozen
- **_THREE_HEAVY_OFF, _FOUL_PRONE_DEF:** Frozen
- **_ELITE_OREB_TEAMS, _WEAK_BOXOUT_TEAMS:** Frozen (defined inside function body)

These team sets are frozen snapshots from 2024-25 data analysis. They are not recomputed from current-season stats. This is intentional (avoid overfitting to small samples) but means teams that have meaningfully changed their identity (e.g., roster turnover, coaching changes) may be misclassified.

## Stale Archetype Games Cache
Line 559-569 in run_nba.py: _ARCHETYPE_GAMES_2026 is a hardcoded dict of specific game dates for ELITE_DEF2_at_ELITE_DEF. This is NOT dynamically computed -- it is a manually maintained list. Games past the last entry (2026-04-12) would not be flagged unless the list is extended.

However, the general archetype detection (_flag_archetype_matchups) checks team set membership dynamically, so new games are still caught. The _ARCHETYPE_GAMES_2026 dict appears to be for reference only (not used in detection logic).

## Orphan Files
- nba/models/totals_base_model.pkl (alpha=500, 20 features) -- NOT used by live pipeline
- nba/models/variance_model.pkl -- NOT used by live pipeline
- These are from an earlier model iteration and should be documented as deprecated

## No Stale Cache Issues Found
The NBA pipeline does not use day-level cache files (unlike MLB). Feature computation is done live from the NBA API each morning. The only cached state is:
- box_stats.parquet: appended each day with new games
- The model pkl: trained once, not retrained
