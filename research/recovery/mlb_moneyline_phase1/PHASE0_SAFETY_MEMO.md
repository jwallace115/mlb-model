# MLB Moneyline Rediscovery — Safety Framework Memo

## Date: 2026-04-11

## Contaminated Legacy Objects (EXCLUDED)
- Any pitcher quality metric (xFIP, SIERA, xERA, K%, BB%)
- Any team offensive rating (wRC+, xwOBA, OPS)
- Any bullpen fatigue/availability metric
- Any umpire run-environment rating
- Any park factor beyond what is in game_table (structural)
- Any sim/model output from prior phases
- Any feature derived from end-of-season aggregates
- shadow_log.parquet, phase9_baseline_model.pkl, any .pkl model

## Allowed Data Sources
- mlb_odds_closing_canonical.parquet: ACTUAL closing prices from Odds API backfill
- game_table.parquet: outcomes + PIT-safe schedule context only
  - home_score, away_score (outcome)
  - home_rest_days, away_rest_days (PIT-safe, known pre-game)
  - local_start_hour (PIT-safe, schedule-derived)
  - home_team, away_team (structural)
  - temperature, wind_speed (PIT-safe if from forecast, but treating as context only)

## PIT-Safe Axes
- Home/away orientation (structural, always known)
- Favorite/dog orientation from closing ML price (market-derived, PIT at close)
- Rest differential (schedule-derived, always known pre-game)
- Day vs night (schedule-derived, always known pre-game)
- Divisional matchup (structural, always known — if derivable)

## Rules
1. No end-of-season aggregates — all features must be point-in-time
2. No discovery on validation/OOS data — discovery on 2022-2023 ONLY; 2024 validate; 2025 OOS
3. No contaminated V1-adjacent features
4. Actual closing prices required for all economics
5. Report by season — aggregate cannot hide failures
6. If a feature is not provably PIT-safe, EXCLUDE it
