======================================================================
PHASE 0: LIVE-COMPATIBLE FEATURE INVENTORY
======================================================================

Canonical dataset: 6506 games, 62 columns
Seasons: [np.int64(2021), np.int64(2022), np.int64(2023), np.int64(2024), np.int64(2025)]

--- LIVE-AVAILABLE (will use in rebuild) ---
  goals_scored                   NHL API boxscore — always available
  goals_allowed                  NHL API boxscore — always available
  shots_on_goal                  NHL API boxscore — available for MoneyPuck-covered games
  pp_goals                       NHL API boxscore — 5 NaN total
  pp_opportunities               NHL API boxscore — 5 NaN total
  pk_goals_against               NHL API boxscore — 5 NaN total
  goalie_sa                      NHL API boxscore — 0 NaN
  goalie_ga                      NHL API boxscore — 0 NaN
  is_b2b                         Schedule-derived — 0 NaN
  rest_days                      Schedule-derived — <2% NaN
  games_last_7                   Schedule-derived — 0 NaN

--- MONEYPUCK-DEPENDENT (EXCLUDED) ---
  xgoals                         MoneyPuck — NOT available in live pipeline
  xgoals_against                 MoneyPuck — NOT available in live pipeline
  hd_shots                       MoneyPuck — NOT available in live pipeline
  hd_shots_against               MoneyPuck — NOT available in live pipeline
  corsi_pct                      MoneyPuck — NOT available in live pipeline
  fenwick_pct                    MoneyPuck — NOT available in live pipeline

NOTE: shots_on_goal has 196 NaN (all in recent 2025 games)
  These are recent games where MoneyPuck hasn't updated.
  However, SOG IS available from NHL API boxscores — the canonical
  just happened to source it from MoneyPuck. For the rebuild,
  we use the available SOG data and skip games with NaN.

DERIVED FEATURES (computed from live data):
  goalie_sv_pct = 1 - (GA / SA)  — from NHL API boxscore
  pp_pct = PP_goals / PP_opportunities  — from NHL API boxscore
  pk_pct = 1 - (PK_GA / PK_faced)  — from NHL API boxscore
  shot_pressure = team_SOG_rolling - opp_SA_rolling  — derived

--- CURRENT MODEL FEATURES THAT WILL BE DROPPED ---
  home/away_xgf_rolling_20
  home/away_xga_rolling_20
  home/away_hd_shots_for_rolling_20
  home/away_hd_shots_against_rolling_20
  home/away_hd_pressure

Original model: 24 features per side model
Rebuild model: ~16 features per side model (no xG/HD)