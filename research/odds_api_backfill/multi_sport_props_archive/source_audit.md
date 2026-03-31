# Source Audit — Multi-Sport Props Archive

## Existing MLB Archive (reference pattern)
- Root: data/odds_archive/mlb/
- Props: partitioned by season/month, parquet
- Game markets: same partition strategy
- Manifests: event manifest + master index (parquet + CSV)
- Logs: pull_log.parquet
- Schema: sport, event_id, game_date, commence_time, home_team, away_team, bookmaker, market_key, last_update, player_name, line, over_price, under_price, implied_over, implied_under, pull_batch, pull_timestamp

## New Archive Locations
- data/odds_archive/nba/ (props/, game_markets/, manifests/, logs/)
- data/odds_archive/nfl/ (same structure)
- data/odds_archive/nhl/ (same structure)

## Credits Available
~3,468,000 remaining (after MLB backfill used ~519K)

## Estimated Cost
- NBA: ~1,500 events × 3 batches × ~70 credits = ~315,000
- NFL: ~300 events × 3 batches × ~70 credits = ~63,000
- NHL: ~1,300 events × 3 batches × ~70 credits = ~273,000
- Market inventory: ~200 per sport = ~600
- Total estimated: ~652,000 credits (~19% of remaining)
