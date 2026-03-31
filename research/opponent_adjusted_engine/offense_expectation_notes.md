# Offense Expectation Layer — Notes

## Method
- Source: MLB Stats API boxscores (team batting lines)
- Rolling window: last 20 completed games per team
- Shift(1): excludes current game (strict pregame lookback)
- Min periods: 10 games

## Features
- `k_rate_r20`: team K/AB rolling 20g (high = strikeout-prone)
- `bb_rate_r20`: team BB/AB rolling 20g (high = patient)
- `runs_r20`: team runs/game rolling 20g

## Limitations
- No team-level hard-hit or barrel from boxscores
- No handedness split (would require pitch-level data per game)
- Early-season gap (~first 10 games per team per year)
