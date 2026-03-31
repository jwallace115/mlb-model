# Source Audit — V3 Lineup Model Phase 1

## Files

| File | Rows | Purpose |
|------|------|---------|
| sim/data/game_table.parquet | 9715 | Canonical game table (2022-2025) |
| sim/data/cache/boxscores/ | 9715 JSON | Full boxscores with battingOrder + per-batter stats |
| sim/data/bet_results.parquet | 4855 | Closing lines (2024-2025) |
| sim/data/phase5_sim_results.parquet | 4855 | V1 p_under (2024-2025) |

## Key Findings
- battingOrder: present in 100% of boxscores (9 player IDs per side)
- Per-batter stats: AB, H, 2B, 3B, HR, K, BB, HBP, PA, totalBases all available
- batSide (handedness): NOT in boxscore player data — would need separate roster lookup
- Position: available per player (P, C, 1B, etc.)
- Historical lineup data: fully reconstructable from boxscores
