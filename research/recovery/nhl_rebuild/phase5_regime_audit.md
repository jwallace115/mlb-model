======================================================================
PHASE 5: REGIME AUDIT
======================================================================

--- LEAGUE SCORING TRENDS ---
  2021: avg total=6.29  std=2.34  n=1312
  2022: avg total=6.36  std=2.28  n=1312
  2023: avg total=6.23  std=2.31  n=1312
  2024: avg total=6.08  std=2.32  n=1312
  2025: avg total=6.27  std=2.30  n=1258

--- MODEL A BIAS BY SEASON ---
  2021: bias=+0.022  MAE=1.844
  2022: bias=-0.022  MAE=1.814
  2023: bias=-0.019  MAE=1.864
  2024: bias=-0.163  MAE=1.871
  2025: bias=-0.288  MAE=1.865

--- FEATURE STABILITY (mean of key features by season) ---

  home_goals_scored_rolling_10:
    2021: mean=3.1274  std=0.6572
    2022: mean=3.1611  std=0.6027
    2023: mean=3.1115  std=0.6004
    2024: mean=3.0284  std=0.5637
    2025: mean=3.1154  std=0.5566

  home_shots_for_rolling_20:
    2021: mean=31.5898  std=2.7092
    2022: mean=31.2890  std=2.6769
    2023: mean=30.3243  std=2.4168
    2024: mean=28.3115  std=2.0493
    2025: mean=27.9596  std=2.1526

  home_pp_pct_rolling_20:
    2021: mean=0.2019  std=0.0626
    2022: mean=0.2144  std=0.0598
    2023: mean=0.2049  std=0.0636
    2024: mean=0.2104  std=0.0659
    2025: mean=0.2029  std=0.0592

  home_goalie_sv_pct_rolling_10:
    2021: mean=0.9019  std=0.0220
    2022: mean=0.8984  std=0.0207
    2023: mean=0.8966  std=0.0220
    2024: mean=0.8949  std=0.0214
    2025: mean=0.8890  std=0.0231

--- EDGE SIGNAL QUALITY ---
  corr(model_edge, market_error): 0.1552
  (>0.05 = genuine signal, >0.10 = strong signal)

--- QUINTILE CALIBRATION (Model A calibrated, OOS) ---
  Q1: pred=5.47  actual=5.86  n=263  delta=-0.39
  Q2: pred=5.75  actual=5.99  n=262  delta=-0.24
  Q3: pred=5.93  actual=6.00  n=262  delta=-0.07
  Q4: pred=6.11  actual=6.29  n=262  delta=-0.18
  Q5: pred=6.43  actual=6.27  n=263  delta=+0.16

--- B2B EFFECT (OOS) ---
  home B2B: avg_total=5.98 (n=121)  vs no B2B: 6.09 (n=1191)
  away B2B: avg_total=5.99 (n=277)  vs no B2B: 6.11 (n=1035)