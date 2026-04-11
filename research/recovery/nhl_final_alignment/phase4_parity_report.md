Live pipeline priors (from canonical s24):
  pp_pct prior: 0.2097
  pk_pct prior: 0.7903

Rebuild feature table (2025 season) means:
  home_pk_pct_rolling_20: 0.7975
  home_pp_pct_rolling_20: 0.2029
  PK% range: [0.5617, 0.9400]

  ** PK% ALIGNED: rebuild mean within 0.05 of live prior (0.0072)

  Old rebuild PK% mean (2025): 0.9676
  Old vs live prior delta: 0.1773  ** THIS WAS THE BUG **
  New vs live prior delta: 0.0072  ** FIXED **

--- SAMPLE GAME FEATURE COMPARISON ---
Comparing canonical-rebuild features vs what live pipeline would compute
(Both should now use live-compatible PK% definition)

  Game 2025020056: ANA vs PIT
    home_pk_pct_rolling_20: 0.7915
    away_pk_pct_rolling_20: 0.8017
    home_pp_pct_rolling_20: 0.2085
    away_pp_pct_rolling_20: 0.1933

  Game 2025020070: ANA vs CAR
    home_pk_pct_rolling_20: 0.8017
    away_pk_pct_rolling_20: 0.8100
    home_pp_pct_rolling_20: 0.2150
    away_pp_pct_rolling_20: 0.1858

  Game 2025020180: ANA vs DET
    home_pk_pct_rolling_20: 0.7879
    away_pk_pct_rolling_20: 0.8566
    home_pp_pct_rolling_20: 0.1905
    away_pp_pct_rolling_20: 0.2309

  Game 2025020197: ANA vs NJD
    home_pk_pct_rolling_20: 0.7909
    away_pk_pct_rolling_20: 0.8601
    home_pp_pct_rolling_20: 0.1903
    away_pp_pct_rolling_20: 0.2616

  Game 2025020211: ANA vs FLA
    home_pk_pct_rolling_20: 0.8011
    away_pk_pct_rolling_20: 0.7634
    home_pp_pct_rolling_20: 0.1801
    away_pp_pct_rolling_20: 0.2066

--- PARITY VERDICT ---
PASS: PK% and PP% definitions are aligned between rebuild and live pipeline.
The retrained model is compatible with live feature computation.