# Integrity Report — MLB Odds Archive

## Deduplication
- Props: 2,720,897 → 2,577,628 (143,269 duplicates removed from incremental saves)
- Game markets: 233,744 → 199,108 (34,636 duplicates removed)
- Dedup key: event_id + bookmaker + market_key + player_name + line

## Coverage by Market — Props

| Market | Records | Events | Books |
|--------|---------|--------|-------|
| batter_total_bases | 655,825 | 2,413 | 9 |
| batter_hits | 532,390 | 2,413 | 8 |
| batter_home_runs | 424,154 | 2,413 | 8 |
| batter_rbis | 333,702 | 2,412 | 6 |
| batter_runs_scored | 249,475 | 2,412 | 6 |
| batter_hits_runs_rbis | 203,175 | 2,412 | 6 |
| batter_stolen_bases | 145,172 | 2,412 | 5 |
| pitcher_hits_allowed | 51,749 | 2,403 | 6 |
| pitcher_strikeouts | 50,405 | 2,411 | 9 |
| pitcher_earned_runs | 40,976 | 2,399 | 5 |
| pitcher_outs | 25,114 | 2,284 | 8 |
| pitcher_walks | 8,760 | 2,377 | 2 |

## Coverage by Market — Game Markets

| Market | Records | Events |
|--------|---------|--------|
| spreads | 55,532 | 2,413 |
| team_totals | 55,424 | 2,413 |
| spreads_1st_5_innings | 29,832 | 2,412 |
| h2h | 27,986 | 2,413 |
| totals | 27,940 | 2,413 |
| h2h_1st_5_innings | 22,092 | 2,413 |
| totals_1st_5_innings | 14,938 | 2,413 |

## Date Coverage
- First successful date: 2025-03-27
- Last successful date: 2026-03-28
- Expired events (404): 30 (all from late March 2025 pre-season)
- No gap dates within the successful range

## Books Coverage
FanDuel (671K), BetOnline (577K), BetRivers (360K), BetMGM (324K), DraftKings (271K), Fanatics (173K), Bovada (162K), WilliamHill (150K), MyBookie (32K)
