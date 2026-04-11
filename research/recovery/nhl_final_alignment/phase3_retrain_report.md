Splits: train=2624, val=1312, oos=1312, live=1258

--- HOME model (29 features) ---
  Best alpha: 100.0
  Train MAE=1.3992  RMSE=1.7198  bias=-0.0000
  Val   MAE=1.3819  RMSE=1.7322  bias=-0.0236
  OOS   MAE=1.4244  RMSE=1.7714  bias=-0.1925
  Top 5 features (by |coef|):
    away_shots_against_rolling_20: +0.1693
    home_shots_for_rolling_20: +0.1597
    away_shots_for_rolling_20: -0.1389
    home_games_last_7: -0.1233
    away_goals_scored_rolling_10: +0.0839
  Saved: model_A_home.pkl

--- AWAY model (29 features) ---
  Best alpha: 500.0
  Train MAE=1.3431  RMSE=1.6593  bias=+0.0000
  Val   MAE=1.4071  RMSE=1.7500  bias=+0.0133
  OOS   MAE=1.3866  RMSE=1.7057  bias=+0.0546
  Top 5 features (by |coef|):
    home_shots_against_rolling_20: +0.1440
    away_shots_for_rolling_20: +0.1181
    away_shots_against_rolling_20: -0.1023
    away_goalie_fatigue: +0.0985
    away_goals_scored_rolling_10: +0.0973
  Saved: model_A_away.pkl

--- TOTAL PREDICTIONS ---
  train : MAE=1.8302  RMSE=2.2779  bias=+0.0000  n=2624
  val   : MAE=1.8638  RMSE=2.3249  bias=-0.0103  n=1312
  oos   : MAE=1.8737  RMSE=2.3275  bias=-0.1379  n=1312
  live  : MAE=1.8647  RMSE=2.3310  bias=-0.2711  n=1258

--- MARKET COMPARISON (OOS, n=1312) ---
  Model A: MAE=1.8737  RMSE=2.3275
  Market:  MAE=1.8956  RMSE=2.3525
  Delta:   MAE=-0.0219  RMSE=-0.0250

--- EDGE THRESHOLD ANALYSIS (OOS) ---
  OVER  edge>=0.3: n=346, hit%=0.549
  UNDER edge<=-0.3: n=347, hit%=0.542
  OVER  edge>=0.5: n=180, hit%=0.550
  UNDER edge<=-0.5: n=191, hit%=0.534
  OVER  edge>=0.75: n=61, hit%=0.590
  UNDER edge<=-0.75: n=56, hit%=0.607
  OVER  edge>=1.0: n=19, hit%=0.632
  UNDER edge<=-1.0: n=15, hit%=0.667
  UNDER edge<=-1.5: n=1, hit%=1.000

--- CALIBRATION BY MODEL TOTAL QUINTILE (OOS) ---
  Q0: pred=5.47  actual=5.78  delta=-0.30  n=263
  Q1: pred=5.76  actual=6.16  delta=-0.40  n=262
  Q2: pred=5.94  actual=6.04  delta=-0.11  n=262
  Q3: pred=6.12  actual=6.17  delta=-0.05  n=262
  Q4: pred=6.43  actual=6.26  delta=+0.17  n=263

--- COMPARISON WITH OLD REBUILD (PK% ~0.966) ---
  Old rebuild Model A OOS: MAE=1.8708  RMSE=2.3270
  New aligned Model A OOS: MAE=1.8737  RMSE=2.3275
  Improvement: MAE=-0.0029  RMSE=-0.0004