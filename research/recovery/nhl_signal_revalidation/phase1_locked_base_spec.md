# Phase 1: Locked Base Specification

## Source
- Feature table: research/recovery/nhl_final_alignment/nhl_live_compatible_feature_table_v2.parquet
- Home model: research/recovery/nhl_final_alignment/model_A_home.pkl (29 features, alpha=100)
- Away model: research/recovery/nhl_final_alignment/model_A_away.pkl (29 features, alpha=500)
- OOS results: research/recovery/nhl_final_alignment/nhl_final_alignment_oos_results.csv

## Data Splits
- Train: 2021-2022 (2624 games)
- Validate: 2023 (1312 games)
- OOS: 2024 (1312 games)
- Live: 2025 (1258 games)

## Model Performance (raw, no drift)
- Train MAE: 1.8302
- OOS MAE: 1.8737

## Key Features (home model, top 10 by name)
[
  "home_goals_scored_rolling_10",
  "home_goals_allowed_rolling_10",
  "home_shots_for_rolling_20",
  "home_shots_against_rolling_20",
  "home_pp_pct_rolling_20",
  "home_pk_pct_rolling_20",
  "home_pp_opp_per_game_rolling_20",
  "home_goalie_sv_pct_rolling_10",
  "home_goalie_vs_team_baseline",
  "home_goalie_fatigue"
]
... (29 total per side)

## PK% Alignment
- Old rebuild PK% mean: ~0.966 (WRONG - used pk_goals_against)
- New aligned PK% mean: ~0.79 (CORRECT - uses opp_pp_goals)
- Live pipeline PK% prior: 0.7903

## Val-optimal drift: -0.1000
## Old VALIDATE_DRIFT: 0.4458
