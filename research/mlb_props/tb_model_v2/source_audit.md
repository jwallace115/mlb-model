# TB Model v2 — Source Audit

**Date:** 2026-03-27

| Source | Path | Rows | Seasons | Join Keys | Coverage | Pregame Safe |
|:-------|:-----|-----:|:--------|:----------|:---------|:-------------|
| Hitter game logs | `mlb/data/hitter_game_logs.parquet` | 201,605 | 2022-2025 | player_id, game_pk | 100% | Yes (rolling with shift) |
| Pitcher game logs | `mlb/data/pitcher_game_logs.parquet` | 83,042 | 2022-2025 | player_id, game_pk, starter_flag | 100% | Yes |
| Pitcher statcast | `research/statcast_enrichment/pitcher_statcast_per_start.parquet` | 20,662 | 2022-2025 | pitcher_id, game_pk | ~56% of batter-games | Yes (rolling with shift) |
| Protection | `research/lineup_protection_study/followup_iso_mechanism/iso_mechanism_dataset.parquet` | 174,870 | 2022-2025 | game_pk, player_id | ~83% | Yes |
| Team defense | `research/statcast_enrichment/team_defense.parquet` | 120 | 2022-2025 | season, team_name | ~77% | Yes (seasonal) |
| TB props | `research/mlb_props/tb_props/tb_props_dataset.parquet` | 32,756 | 2025 | player_id, game_pk | 2025 only | N/A (market data) |
| Park factors | `config.py` STADIUMS dict | 30 teams | Static | home_team | 100% | Yes |
