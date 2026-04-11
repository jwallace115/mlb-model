# Phase 2: Pipeline Gap Analysis

## Critical Finding: Model Mismatch

The production pipeline (`nhl/nhl_daily_pipeline.py`) currently loads the OLD models
(24 features each, including MoneyPuck-dependent xGF, xGA, HD shots, Corsi, Fenwick).

The rebuild Model A (`research/recovery/nhl_rebuild/model_A_home.pkl` / `model_A_away.pkl`)
uses 29 features each, with NO MoneyPuck features.

**These are different models.** The pipeline models include:
- `xgf_rolling_20` (MoneyPuck) -- DEAD
- `hd_shots_for_rolling_20` (MoneyPuck) -- DEAD
- `hd_shots_against_rolling_20` (MoneyPuck) -- DEAD
- `xga_rolling_20` (MoneyPuck) -- DEAD
- `penalties_taken_rolling_20` (MoneyPuck) -- DEAD
- `hd_pressure` (MoneyPuck-derived) -- DEAD

The rebuild Model A replaces all of these with live-available features:
- `shots_for_rolling_20` (NHL API SOG)
- `shots_against_rolling_20` (NHL API SOG)
- `pp_pct_rolling_20` (NHL API PP goals / PBP PP opp)
- `pk_pct_rolling_20` (derived from opponent PP data)
- `pp_opp_per_game_rolling_20` (PBP penalty count)
- `shot_pressure` (derived from SOG rolling)
- `goalie_sv_pct_rolling_10` (NHL API goalie SA/saves)
- `goalie_vs_team_baseline` (derived from goalie history)
- `goalie_fatigue` (schedule-derived)
- `backup_flag` (schedule-derived)

## Required Changes

### Step 1: Deploy Rebuild Model A Pickles
Copy `model_A_home.pkl` → `nhl/ridge_home_model.pkl`
Copy `model_A_away.pkl` → `nhl/ridge_away_model.pkl`

### Step 2: Extend `load_or_refresh_live_season()` to Fetch Boxscore Data
Currently fetches: game_id, game_date, home/away_team, home/away_score
Missing fields needed:

| Field | Source | Currently Extracted? |
|-------|--------|---------------------|
| home_sog / away_sog | boxscore top-level `homeTeam.sog` | NO |
| home_pp_goals / away_pp_goals | boxscore skater `powerPlayGoals` sum | NO |
| home_pp_opportunities / away_pp_opportunities | play-by-play penalty count | NO |
| home_goalie_id / away_goalie_id | boxscore `goalies[starter].playerId` | NO (only for today's game) |
| home_goalie_sa / away_goalie_sa | boxscore `goalies[starter].shotsAgainst` | NO (only for today's game) |
| home_goalie_ga / away_goalie_ga | boxscore `goalies[starter].goalsAgainst` | NO (only for today's game) |

### Step 3: Rewrite `build_live_team_features()` 
Replace MoneyPuck-prior fallback logic with actual rolling computations using live data.

### Step 4: Update `compute_league_priors()` 
Remove MoneyPuck-only priors, add priors for rebuild Model A features.

### Step 5: Update `compute_game_features()`
Remove MoneyPuck-derived features (hd_pressure), add shot_pressure from live data.

## MoneyPuck Fallback Status
Current code has extensive MoneyPuck fallback → league-average prior. After this change,
ALL features will be computed from live NHL API data. No MoneyPuck dependency remains.

## API Call Budget
- Current: 1 schedule call per day in season range
- New: 1 schedule call per day + 1 boxscore + 1 play-by-play per completed game
- For full season (~1,300 games): ~2,600 additional API calls on first cache build
- Subsequent runs: cached, 0 additional calls (within 6-hour window)
- NHL API has no rate limit / no key required
