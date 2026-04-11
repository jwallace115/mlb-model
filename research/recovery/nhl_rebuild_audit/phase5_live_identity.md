# Phase 5: Live Identity Lock

## Rebuild Feature Set (32 features)
All 32 rebuild features are a SUBSET of the live feature table (44 features).
- Overlap: 32/32 (100%)
- Rebuild-only features: 0
- Live-only features: 12 (all MoneyPuck-dependent, correctly excluded from rebuild)

Live-only features (not used by rebuild):
- home/away_xgf_rolling_20, home/away_xga_rolling_20 (MoneyPuck xG)
- home/away_hd_shots_for_rolling_20, home/away_hd_shots_against_rolling_20 (MoneyPuck HD)
- home/away_hd_pressure (derived from HD shots)
- home/away_penalties_taken_rolling_20

## Live Pipeline Data Availability

### Currently Available in Live Pipeline
The live pipeline (nhl_daily_pipeline.py) already fetches from NHL API boxscores:
- goals (home_score, away_score) -- AVAILABLE
- goalie SA and GA (goalie_sa, goalie_ga) -- AVAILABLE (line 196: starter.get("saves"))
- schedule features (B2B, rest_days, games_last_7) -- AVAILABLE

### Requires Pipeline Extension
The following are available from the NHL API boxscore endpoint (which the pipeline
already calls at line 179) but are NOT currently extracted:
- shots_on_goal -- needs parsing from boxscore response
- pp_goals, pp_opportunities -- needs parsing
- pk_goals_against -- needs parsing

The rebuild's phase4_identity_lock.md estimates ~30 lines of code change in
fetch_game_boxscore() to extract these fields.

### SOG Sourcing Gap
CRITICAL FINDING: The live pipeline currently fills shots_for_rolling_20 with
MoneyPuck OOS priors (line 120) when MoneyPuck data is unavailable. With MoneyPuck
down, this means live games get STALE prior values rather than actual rolling SOG.

The rebuild was trained on actual SOG values. To run live identically, the pipeline
must extract SOG from the NHL API boxscore response (the endpoint is already being
called; the data just needs to be parsed out).

## Model C Additional Requirement
- closing_total: Already fetched from Odds API in the live pipeline. AVAILABLE.

VERDICT: NOT LIVE-IDENTICAL TODAY -- pipeline needs ~30 lines of code to extract
SOG/PP/PK from the NHL API boxscore response it already fetches. The data is
available; the parsing is missing.
