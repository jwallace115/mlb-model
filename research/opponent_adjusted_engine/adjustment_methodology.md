# Adjustment Methodology — v1 Engine

## Core Formula
```
adj_metric = raw_metric - (opponent_rolling_20g - league_avg)
```

## Specific Definitions

**K rate:** adj_k_rate = raw_k_rate - (opp_k_rate_r20 - 0.2191)
**BB rate:** adj_bb_rate = raw_bb_rate - (opp_bb_rate_r20 - 0.0797)
**CSW (strike%):** adj_csw = raw_strike_pct - (opp_k_rate_r20 - 0.2191)

**Hard-hit allowed:** adj_hh = raw_hh + (league_avg_runs - opp_runs_r20) × 0.02
- Weaker offenses deflate HH allowed → adjust upward
- League avg runs/game: 4.435

**Barrel allowed:** adj_barrel = raw_barrel + (league_avg_runs - opp_runs_r20) × 0.005

## Opponent Features
- k_rate_r20: team K/AB, last 20 games (pregame only)
- bb_rate_r20: team BB/AB, last 20 games
- runs_r20: team runs/game, last 20 games

## Data Sources
- K, BB, BF, pitches, strikes: MLB Stats API boxscores
- Hard-hit, barrel: Statcast per-start (17,906 starters)
- Team batting: boxscore team batting lines
