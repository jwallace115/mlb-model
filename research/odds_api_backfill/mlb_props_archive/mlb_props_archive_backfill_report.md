# MLB Props Archive Backfill Report

## Summary

| Metric | Value |
|--------|-------|
| Date range | 2025-03-27 to 2026-03-28 |
| Events archived | 2,413 (of 2,742 total; 30 expired) |
| Prop records | **2,577,628** (after dedup) |
| Game market records | **199,108** (after dedup) |
| Credits used | ~518,655 |
| Credits remaining | ~3,468,000 |
| Archive size | ~16 MB (props 14MB + game markets 1.7MB) |

## Market Coverage

### Player Props (12 markets, all archived)
- batter_total_bases: 655K records, 2,413 events, 9 books
- batter_hits: 532K records
- batter_home_runs: 424K records
- batter_rbis: 334K records
- batter_runs_scored: 249K records
- batter_hits_runs_rbis: 203K records
- batter_stolen_bases: 145K records
- pitcher_strikeouts: 50K records, 9 books
- pitcher_hits_allowed: 52K records
- pitcher_earned_runs: 41K records
- pitcher_outs: 25K records
- pitcher_walks: 9K records

### Core Game Markets (7 markets, all archived)
- totals, spreads, h2h: all 2,413 events
- team_totals: 2,413 events
- F5 totals, F5 spreads, F5 h2h: 2,412-2,413 events

## Book Coverage (by record count)
1. FanDuel: 672K
2. BetOnline: 577K
3. BetRivers: 360K
4. BetMGM: 324K
5. DraftKings: 271K
6. Fanatics: 173K
7. Bovada: 162K
8. WilliamHill US: 150K
9. MyBookie: 32K

## Missing / Expired Dates
- 30 events returned 404 (all pre-season March 2025)
- Zero gaps in the regular season (April - September 2025)
- Off-season dates (November-February) returned valid events from other leagues but no MLB props

## Output File Locations

```
data/odds_archive/mlb/
  props/
    season=2025/month=03/ through month=11/
    season=2026/month=03/
  game_markets/
    season=2025/month=03/ through month=11/
    season=2026/month=03/
  manifests/
    mlb_event_manifest_2025_2026.parquet
    mlb_event_manifest_2025_2026.csv
    mlb_odds_archive_index.parquet
  logs/
    pull_log.parquet
```

## Credit Usage

| Item | Credits |
|------|---------|
| Event discovery (366 dates) | ~366 |
| Batter prop batches (2,413 events) | ~168,910 |
| Pitcher prop batches (2,413 events) | ~168,910 |
| Game market batches (2,413 events) | ~168,910 |
| Diagnostic / overhead | ~11,559 |
| **Total** | **~518,655** |
| Average per event | ~215 (3 batches × ~70 each) |

## Next Recommended Steps

1. **Join props archive to batter outcomes** — match batter_total_bases and batter_hits records to actual boxscore outcomes for efficiency backtesting
2. **Run bookmaker split on TB market** — compare FanDuel vs DraftKings vs BetMGM pricing on Over/Under 1.5 TB to identify which book offers the best Under prices
3. **Run pitcher strikeout efficiency study** — 50K records across 9 books, high-liquidity market
4. **Build team_totals efficiency study** — 55K records, direct application to existing totals model
5. **Extend archive forward** — add daily collection to capture 2026 season as it plays out
