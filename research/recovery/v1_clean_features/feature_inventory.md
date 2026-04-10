# V1 Feature Inventory — Clean Rebuild Classification

## Phase 9 Baseline: 25 Features

Source: `sim/data/phase9_baseline_model.pkl` (alpha=50, sigma=4.361)

### Feature Classification

| # | Feature | Source | Classification | Justification |
|---|---------|--------|---------------|---------------|
| 1 | home_sp_xfip | FanGraphs season aggregate | REBUILD_PIT | End-of-season xFIP used for ALL games in that season. April games see September data. Classic lookahead. |
| 2 | away_sp_xfip | FanGraphs season aggregate | REBUILD_PIT | Same as above. |
| 3 | home_sp_k_pct | FanGraphs season aggregate | REBUILD_PIT | K% is end-of-season aggregate, not point-in-time. |
| 4 | away_sp_k_pct | FanGraphs season aggregate | REBUILD_PIT | Same as above. |
| 5 | home_sp_bb_pct | FanGraphs season aggregate | REBUILD_PIT | BB% is end-of-season aggregate. |
| 6 | away_sp_bb_pct | FanGraphs season aggregate | REBUILD_PIT | Same as above. |
| 7 | home_sp_avg_ip | FanGraphs season aggregate | REBUILD_PIT | IP/GS computed from full-season totals. |
| 8 | away_sp_avg_ip | FanGraphs season aggregate | REBUILD_PIT | Same as above. |
| 9 | home_wrc_plus | FanGraphs season aggregate | REBUILD_PIT | End-of-season wRC+ for team offense. Needs game-by-game rebuild. |
| 10 | away_wrc_plus | FanGraphs season aggregate | REBUILD_PIT | Same as above. |
| 11 | park_factor_runs | config.py static table | REUSE_AS_IS | Static park factors from config.STADIUMS — no temporal leakage. Computed once per venue, used consistently. Verified in sim/phase1_build_game_table.py enrich_park_and_umpire(). |
| 12 | park_factor_hr | config.py static table | REUSE_AS_IS | Same source as park_factor_runs (same static table). |
| 13 | temperature | Open-Meteo API (game-day) | REUSE_AS_IS | Weather at game time from game_table. No future leakage — weather is an exogenous variable known at game time. |
| 14 | wind_factor_effective | Computed in phase2 | REUSE_AS_IS | Directional wind factor: -cos(wind_dir - cf_bearing) * wind_speed. Uses game-day weather (no leakage) + static CF bearings from config. |
| 15 | umpire_over_rate | Static umpire table | REUSE_AS_IS | From modules/umpires.py UMPIRE_RATINGS — static lookup table, same value for all games with that umpire. No temporal leakage. Verified: umpire_over_rate == runs_factor. |
| 16 | home_rest_days | game_table computation | REUSE_AS_IS | Days since team's last game, computed chronologically in phase1 compute_rest_days(). Uses only past game dates. No leakage. |
| 17 | away_rest_days | game_table computation | REUSE_AS_IS | Same as above for away team. |
| 18 | doubleheader_flag | game_table metadata | REUSE_AS_IS | Binary flag from MLB schedule API (game_number > 1). Known pre-game. No leakage. |
| 19 | flyball_wind_interaction | FanGraphs FB% × wind_out_flag | REBUILD_PIT | FB% comes from end-of-season FanGraphs aggregate (same contamination as xFIP). wind_out_flag itself is clean. |
| 20 | home_high_leverage_avail | Boxscore-derived rolling | REUSE_AS_IS | Built in phase8_bullpen_features.py from boxscores of PRIOR games. Uses shift(1) / rolling with strict chronological ordering. Verified: no same-day data included. |
| 21 | away_high_leverage_avail | Boxscore-derived rolling | REUSE_AS_IS | Same as above for away team. |
| 22 | home_bullpen_delta | bp_xfip - sp_xfip | REBUILD_PIT | bp_xfip comes from FanGraphs season aggregate (contaminated). sp_xfip also contaminated. Delta inherits contamination from both. |
| 23 | away_bullpen_delta | bp_xfip - sp_xfip | REBUILD_PIT | Same as above. |
| 24 | home_bp_delta_exposure | bullpen_delta * proj_bullpen_inn | REBUILD_PIT | Derived from contaminated bullpen_delta × proj_inn (proj_inn uses contaminated avg_ip). |
| 25 | away_bp_delta_exposure | bullpen_delta * proj_bullpen_inn | REBUILD_PIT | Same as above. |

### Summary

- **REBUILD_PIT**: 16 features (1-10, 19, 22-25)
- **REUSE_AS_IS**: 9 features (11-18, 20-21)

### Contamination Mechanism

The V1 feature table uses `sim/modules/fg_historical.py` which calls FanGraphs API with `season=YYYY` — this returns the **full-season aggregate** for that year. The same xFIP/K%/BB%/IP values are used for every game in the season, meaning a game on April 5 uses stats that include September performance. This is lookahead contamination.

Evidence: Gerrit Cole's `home_sp_xfip` is exactly 3.626 for ALL 16 starts in 2022, confirming a single season-end value was applied uniformly.

### Clean Rebuild Strategy

Use `pitcher_game_logs.parquet` (84,669 rows, 2022-2026) to compute expanding-mean features with `shift(1)` to ensure strict date < game_date filtering. This creates point-in-time features that were knowable before each game.
