# Current Pipeline Audit — MLB Two-Pass Redesign

## Current Schedule

| Job | Time | Script | Purpose |
|-----|------|--------|---------|
| com.mlbmodel.opening_lines | 2:00 AM | mlb_sim/pipeline/pull_opening_lines.py | Opening line capture |
| com.mlbmodel.daily | 7:00 AM | push_results.py | Grade + model + signals + push |
| com.mlbmodel.refresh | 11:00 AM | refresh.py | Lineup/weather/umpire refresh |
| com.mlbmodel.refresh.noon | 12:00 PM | refresh.py | Second refresh |
| com.mlbmodel.refresh.5pm | 5:00 PM | refresh_5pm.py | Final refresh + closing lines |
| com.mlbmodel.clv.capture | 6:30 PM | closing_line_runner.py | CLV capture |
| com.mlbmodel.results | 11:30 PM | results_tracker.py | Grade final scores |

## Execution Flow (7AM)

push_results.py:
1. grade_yesterday() → SQLite results table
2. build_season_stats_json()
3. run_model() → build_pitcher_db() + build_offense_db() + per-game projection
4. V1 signal generator
5. F5 signal generator
6. F5 run line generator
7. Timing line capture
8. Parlay tracker
9. NBA/NHL/Soccer/NFL pipelines
10. git push

## Cache Behavior
- Pitcher DB: data/cache/pitchers_v2_YYYY-MM-DD.json (per-day, first-write wins)
- Offense DB: data/cache/offense_v2_YYYY-MM-DD.json (per-day, first-write wins with hotfix validation)
- Odds: data/cache/odds_full_YYYY-MM-DD.json (per-day)

## Problems Identified
1. No 2AM preliminary pass — manual early runs can poison caches
2. 2AM opening line script only captures lines, doesn't grade/refresh
3. No west coast finalization check at 7AM
4. Cache validation only added in hotfix — not tested at scale
