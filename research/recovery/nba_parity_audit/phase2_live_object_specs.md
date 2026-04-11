# Phase 2: Live Object Specs

## Entry Point
- push_results.py calls nba.run_nba.run() then push_nba.write_nba_json()
- run_nba.py is the full pipeline: grade results, fetch schedule, compute features, predict, classify

## Live Feature Computation (run_nba.py _build_current_team_states)
1. Loads historical box_stats.parquet + fetches current season via fetch_box_stats()
2. Filters to CURRENT_SEASON games BEFORE game_date (date < cutoff)
3. Computes rolling 15-game mean of ortg/drtg/pace from tail(15)
4. Computes rolling 5-game mean for trend features from tail(5)
5. Computes fg3a_rate and ft_rate from rolling 15-game window
6. Applies prior-season blending via _blend() from features module
7. Does NOT compute location-specific rolling (home/away split)
8. Does NOT compute b2b_flag_home (only b2b_flag_away used)
9. Does NOT compute days_rest, games_l7 (not in FEATURE_COLS)

## Live Model Prediction
- Loads nba/data/ridge_model.pkl (model + scaler + feature list)
- Assembles 15-feature vector from team states
- StandardScaler.transform() then RidgeCV.predict()
- Playoff: subtracts 6.0 pts for Games 1-2 (early-series bias correction)
- Playoff: uses series_blend to mix reg-season with series-specific rolling

## Live Archetype Signals
- _flag_archetype_matchups(): ELITE_DEF2 @ ELITE_DEF -> UNDER
- _flag_shot_profile(): BALANCED_OFF vs PASSIVE_DEF -> OVER, THREE_HEAVY vs FOUL_PRONE -> UNDER
- _flag_venue_signal(): ROAD_WARRIOR @ STRONG_HOME -> OVER, with CORE and OREB sub-tiers
- _flag_playoff_boards(): P1/P2/P4 structural playoff signals
- All team sets are hardcoded frozen lists in run_nba.py

## Confidence Classification
- HIGH: |pred - line| >= 6.0 AND p(directional) >= 0.55, no injuries
- MEDIUM: one condition met, or HIGH + active injury
- LOW: neither met

## Output
- nba_daily_projections.parquet: saved for next-day grading
- nba_results_log.parquet: 164 graded games as of 2026-04-10
- nba_signal_log.parquet: 35 logged archetype signal bets
- nba_market_snapshots.parquet: market line snapshots
