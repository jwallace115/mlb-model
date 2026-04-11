# Phase 1: Locked Object Spec — Model A Live Parity

## Model Identity
- **Model**: Model A (pure hockey, no market features)
- **Architecture**: Two Ridge regressors (home_score, away_score), StandardScaler
- **Pickle files**: `nhl/ridge_home_model.pkl`, `nhl/ridge_away_model.pkl`
- **Training seasons**: 2021, 2022 | Validation: 2023 | OOS: 2024

## Feature List — Home Model (29 features)

| # | Feature | Rolling | Source |
|---|---------|---------|--------|
| 1 | home_goals_scored_rolling_10 | 10-game | NHL API boxscore (score) |
| 2 | home_goals_allowed_rolling_10 | 10-game | NHL API boxscore (score) |
| 3 | home_shots_for_rolling_20 | 20-game | NHL API boxscore (SOG) |
| 4 | home_shots_against_rolling_20 | 20-game | NHL API boxscore (SOG) |
| 5 | home_pp_pct_rolling_20 | 20-game | NHL API boxscore (PP goals) + PBP (PP opp) |
| 6 | home_pk_pct_rolling_20 | 20-game | Derived: 1 - (opp_pp_goals / opp_pp_opp) |
| 7 | home_pp_opp_per_game_rolling_20 | 20-game | NHL API PBP (penalty count) |
| 8 | home_goalie_sv_pct_rolling_10 | 10-game (goalie-specific) | NHL API boxscore (SA, GA) |
| 9 | home_goalie_vs_team_baseline | full-season | Goalie SV% - team avg SV% |
| 10 | home_goalie_fatigue | 3-day window | Games started in last 3 days |
| 11 | home_goalie_b2b | binary | Same as team B2B |
| 12 | home_backup_flag | binary | Not the mode starter |
| 13 | home_days_rest | scalar | Schedule-derived |
| 14 | home_b2b | binary | Schedule-derived |
| 15 | home_games_last_7 | count | Schedule-derived |
| 16 | home_shot_pressure | derived | home_shots_for_r20 - away_shots_against_r20 |
| 17 | away_goals_scored_rolling_10 | 10-game | Same as above, away side |
| 18 | away_goals_allowed_rolling_10 | 10-game | |
| 19 | away_shots_for_rolling_20 | 20-game | |
| 20 | away_shots_against_rolling_20 | 20-game | |
| 21 | away_pp_pct_rolling_20 | 20-game | |
| 22 | away_pk_pct_rolling_20 | 20-game | |
| 23 | away_goalie_sv_pct_rolling_10 | 10-game | |
| 24 | away_goalie_vs_team_baseline | full-season | |
| 25 | away_goalie_fatigue | 3-day window | |
| 26 | away_goalie_b2b | binary | |
| 27 | away_backup_flag | binary | |
| 28 | away_days_rest | scalar | |
| 29 | away_b2b | binary | |

## Away Model (29 features)
Same features with home/away swapped: away side gets games_last_7, shot_pressure, pp_opp_per_game.

## Rolling Window Parameters
- **Short window**: 10 games (goals, goalie SV%)
- **Long window**: 20 games (shots, PP%, PK%, PP opp)
- **Shrinkage**: `w = min(n, window) / window; result = w * raw + (1-w) * prior`
- **PIT safety**: strict shift — only use games BEFORE current game date (no same-day leakage)

## Raw Fields Needed Per Game
From NHL API boxscore (`/v1/gamecenter/{id}/boxscore`):
1. `homeTeam.sog` / `awayTeam.sog` — shots on goal
2. `homeTeam.score` / `awayTeam.score` — goals (already extracted)
3. `playerByGameStats.{side}.forwards[].powerPlayGoals` — sum for PP goals
4. `playerByGameStats.{side}.defense[].powerPlayGoals` — sum for PP goals
5. `playerByGameStats.{side}.goalies[].shotsAgainst` — goalie SA
6. `playerByGameStats.{side}.goalies[].saves` — goalie saves (GA = SA - saves)
7. `playerByGameStats.{side}.goalies[].starter` — starter flag
8. `playerByGameStats.{side}.goalies[].playerId` — goalie ID
9. `playerByGameStats.{side}.goalies[].name.default` — goalie name

From NHL API play-by-play (`/v1/gamecenter/{id}/play-by-play`):
10. Penalty plays (typeDescKey == "penalty") with details.eventOwnerTeamId + details.duration
    - Count minor/major penalties per team → PP opportunities for opponent
    - Exclude misconduct penalties (10-min, don't create PP)

## Derived Fields
- `goalie_sv_pct = 1 - (GA / SA)` where GA = shotsAgainst - saves
- `pp_pct = pp_goals / pp_opportunities` (0 when pp_opp = 0)
- `pk_pct = 1 - (opp_pp_goals / opp_pp_opp)` (1.0 when opp_pp_opp = 0)
- `pk_goals_against = opponent's pp_goals`
- `shot_pressure = team_shots_for_r20 - opp_shots_against_r20`

## Missing Data Handling
- NaN features filled with train-set column means (stored in model pickle as `col_means`)
- Goalie SV% with SA=0 → fallback 0.91 (league average)
- Goalie vs team baseline with <3 starts → 0.0
- Rest days NaN → 3.0

## Models Currently Loaded
The pipeline currently loads `ridge_home_model.pkl` and `ridge_away_model.pkl`.
These ARE the Model A pickles from the rebuild (confirmed by feature list match).
