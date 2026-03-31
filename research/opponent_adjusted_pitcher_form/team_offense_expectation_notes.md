# Team Offense Expectation — Data Notes

## Method
- Source: MLB Stats API boxscores (9,715 cached JSON files)
- Extracted team batting: K, BB, AB, H, R, HR per game-side
- Rolling window: last 20 completed games per team (shift(1) to exclude current game)
- Min periods: 10 games

## Features
- `k_rate_r20`: team K/AB rolling 20 games (higher = more strikeout-prone offense)
- `bb_rate_r20`: team BB/AB rolling 20 games (higher = more patient offense)
- `runs_per_game_r20`: team runs/game rolling 20 games

## Coverage (2024-2025)
- k_rate_r20: 99.9%
- bb_rate_r20: 99.9%
- Gaps are early-season (first ~10 games per team per season)
