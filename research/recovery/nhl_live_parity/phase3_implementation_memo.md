# Phase 3: Implementation Memo

## Changes Applied to `nhl/nhl_daily_pipeline.py`

### 1. Model Loading (`load_models()`)
- Now loads rebuild Model A pickles (`model_A_home.pkl`, `model_A_away.pkl`) 
  from `research/recovery/nhl_rebuild/` if they exist
- Falls back to old `ridge_home_model.pkl` / `ridge_away_model.pkl` if rebuild not found

### 2. League Priors (`compute_league_priors()`)
- Uses rebuild feature table (`nhl_rebuild_features.parquet`) for 2024 OOS averages
- Removed all MoneyPuck-only features (xGF, xGA, HD shots, penalties_taken)
- Removed `hd_pressure` from priors
- Only computes priors for Model A features

### 3. New Function: `fetch_game_boxscore_extended()`
- Fetches boxscore + play-by-play for a single completed game
- Extracts from boxscore (same endpoint, no new API):
  - `home_sog` / `away_sog` from `data['homeTeam']['sog']`
  - `home_pp_goals` / `away_pp_goals` from summing skater `powerPlayGoals`
  - Goalie: `playerId`, `name`, `shotsAgainst`, `saves` (GA = SA - saves)
- Extracts from play-by-play (one additional call per game):
  - PP opportunities = count of opponent's non-misconduct penalties (duration >= 2)
- Returns None for any field that fails to extract

### 4. Live Season Cache (`load_or_refresh_live_season()`)
- Extended column set: adds `home/away_sog`, `home/away_pp_goals`, 
  `home/away_pp_opportunities`, `home/away_goalie_id/name/sa/ga`
- Phase 1: collects game stubs from schedule (same as before)
- Phase 2: fetches extended boxscore for each game via `fetch_game_boxscore_extended()`
- Auto-detects old cache without extended columns and forces refresh
- 50ms sleep between boxscore fetches for rate limiting

### 5. Feature Builder (`build_live_team_features()`)
- Complete rewrite to compute ALL Model A features from live data
- For each team game, extracts team-perspective stats (goals, SOG, PP, PK, goalie)
- Rolling windows: 10-game (goals, goalie SV%), 20-game (shots, PP%, PK%, PP opp)
- Shrinkage: `w = min(n, window) / window` — identical to rebuild
- NaN handling: `shrink()` now returns prior when raw is NaN (matches rebuild)
- Goalie SV% fallback: 0.91 when SA=0
- Goalie vs team baseline: requires 3+ starts, else 0.0

### 6. Game Features (`compute_game_features()`)
- Removed `hd_pressure` computation
- Added goalie fatigue from live data (count games in last 3 days)
- Added `games_last_7` from live data (count team games in last 7 days)
- Shot pressure now computed from live SOG data

### No Other Files Modified
Only `nhl/nhl_daily_pipeline.py` was changed. No model pickles were copied.
The pipeline dynamically loads from the rebuild directory at runtime.

## Verification
- Python syntax validated via `ast.parse()` — OK
- No remaining MoneyPuck feature references in active computation paths
- Old xGF/xGA references in signal output dict return None (display-only, harmless)
