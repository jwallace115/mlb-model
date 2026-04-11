======================================================================
PHASE 4: IDENTITY LOCK — LIVE DEPLOYMENT CHECK
======================================================================

Model A (pure hockey) live feature requirements:
  LIVE  goals_scored_rolling_10
  LIVE  goals_allowed_rolling_10
  FIX   shots_for_rolling_20 — PARTIAL — available from NHL API boxscores but NOT in current live pipeline
  FIX   shots_against_rolling_20 — PARTIAL — available from NHL API boxscores but NOT in current live pipeline
  FIX   pp_pct_rolling_20 — PARTIAL — computable from pp_goals/pp_opportunities in NHL API
  FIX   pk_pct_rolling_20 — PARTIAL — computable from pk stats in NHL API
  FIX   pp_opp_per_game_rolling_20 — PARTIAL — available from NHL API boxscores
  LIVE  goalie_sv_pct_rolling_10
  LIVE  goalie_vs_team_baseline
  LIVE  goalie_fatigue
  LIVE  goalie_b2b
  LIVE  backup_flag
  LIVE  days_rest
  LIVE  b2b
  LIVE  games_last_7
  FIX   shot_pressure — PARTIAL — needs SOG from NHL API boxscores

Live-ready: NO — pipeline modifications needed

REQUIRED PIPELINE CHANGES:
  The current nhl_daily_pipeline.py fetches only goals from NHL API boxscores.
  To support the rebuilt model, extend load_or_refresh_live_season() to also fetch:
    - shots on goal (from boxscore)
    - PP goals and PP opportunities (from boxscore)
    - PK goals against (from boxscore)
  These are ALL available from the NHL API gamecenter/{id}/boxscore endpoint.
  The current pipeline already calls this endpoint for goalie info.
  Estimated effort: ~30 lines of code change in fetch_game_boxscore().

Model C (hybrid) additionally requires:
  LIVE  closing_total — from Odds API (already fetched in pipeline)