# Phase 1: Live-Compatible Feature Specification

## The PK% Discrepancy

### Canonical CSV definition (WRONG for our purposes):
```
pk_pct = 1 - pk_goals_against / opp_pp_opportunities
Mean: 0.9641
```
pk_goals_against counts SHORTHANDED goals against (very rare, ~0.08/game)

### Live pipeline definition (CORRECT, source of truth):
```python
# From nhl_daily_pipeline.py lines 531-535:
# PK% — 1 - (opp_pp_goals / opp_pp_opportunities)
opp_ppg = r.get(f'{opp_pfx}_pp_goals')
opp_ppo = r.get(f'{opp_pfx}_pp_opportunities')
pk_pct = 1.0 - opp_ppg / opp_ppo if opp_ppo > 0 else 1.0
```
Live PK% mean (home): 0.7960
Live PK% mean (away): 0.7823

### Delta between definitions:
Canonical mean: ~0.965
Live mean: ~0.789
Gap: ~0.176

This gap means the old rebuild model learned PK% coefficients on a scale
that was 0.17 higher than what the live pipeline feeds it. Any model
trained on the old definition will systematically mispredict when given
live PK% values.

## PP% definition (CONSISTENT)
Both canonical and live use: pp_goals / pp_opportunities
Canonical mean: 0.2177
No fix needed.

## All feature definitions (source of truth for retrain):

- **goals_scored_rolling_10**: rolling 10-game mean of goals scored (ROLLING_SHORT=10)
- **goals_allowed_rolling_10**: rolling 10-game mean of goals allowed
- **shots_for_rolling_20**: rolling 20-game mean of shots on goal
- **shots_against_rolling_20**: rolling 20-game mean of shots against
- **pp_pct_rolling_20**: rolling 20-game mean of pp_goals/pp_opportunities
- **pk_pct_rolling_20**: rolling 20-game mean of 1 - opp_pp_goals/opp_pp_opportunities  ** CORRECTED **
- **pp_opp_per_game_rolling_20**: rolling 20-game mean of pp_opportunities
- **goalie_sv_pct_rolling_10**: rolling 10-game mean of 1 - GA/SA for starting goalie
- **goalie_vs_team_baseline**: goalie sv% minus team average sv% (needs >=3 starts)
- **goalie_fatigue**: goalie starts in last 3 days
- **goalie_b2b**: is back-to-back game
- **backup_flag**: is not the most frequent starter (needs >=5 games)
- **days_rest**: rest days since last game
- **b2b**: is back-to-back
- **games_last_7**: games in last 7 days
- **shot_pressure**: team shots_for_rolling - opp shots_against_rolling