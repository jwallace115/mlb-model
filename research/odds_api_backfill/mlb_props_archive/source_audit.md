# Source Audit — MLB Props Archive Backfill

## Existing Odds Files
- data/cache/odds_full_*.json — daily live odds cache (2026 only)
- sim/data/mlb_historical_closing_lines.parquet — 2022-2023 closing totals
- sim/data/market_snapshots.parquet — 2024-2025 market snapshot archive
- mlb_sim/data/line_snapshots_2026.json — 2026 opening/closing line tracker
- research/mlb_props/tb_props/tb_props_raw.parquet — partial 2025 TB props (from prior pull)

## New Archive Location
data/odds_archive/mlb/
  props/ — player prop odds by season/month
  game_markets/ — core game market odds by season/month
  manifests/ — event manifest + master index
  logs/ — pull log

## Endpoint
GET /v4/historical/sports/baseball_mlb/events/{eventId}/odds
  markets=comma,separated,list
  date=commence_time
  regions=us
  oddsFormat=american

## Estimated Cost
~2,500 available games × 3 batches × 10 credits = ~75,000 credits
Credits remaining: ~3,988,800
Post-backfill estimate: ~3,913,800
