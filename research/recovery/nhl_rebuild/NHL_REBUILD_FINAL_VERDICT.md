======================================================================
NHL REBUILD — FINAL VERDICT
======================================================================

======================================================================
OOS (2024-25) COMPARISON TABLE
======================================================================

  Model                    MAE    RMSE     Bias  vs Market       Status
  -------------------- ------- ------- -------- ---------- ------------
  Market (baseline)     1.8956  2.3525  -0.1410      +0.0%     baseline
  Model A (pure)        1.8714  2.3258  -0.1444      -1.3%        BEATS
  Model B (residual)    1.8882  2.3508  -0.1727      -0.4%        BEATS
  Model C (hybrid)      1.8742  2.3329  -0.1935      -1.1%        BEATS

--- VS ORIGINAL MODEL (from phase3_model_audit.txt) ---
  Original model (MoneyPuck features): Total OOS MAE = 1.9159, bias = -0.7864
  Rebuild Model A (no MoneyPuck):       Total OOS MAE = 1.8714, bias = -0.1444
  Rebuild Model C (no MoneyPuck+mkt):   Total OOS MAE = 1.8742, bias = -0.1935

  Model A vs original: -2.3%
  Model C vs original: -2.2%

  corr(edge, market_error):
    Model A: 0.1552
    Model C: 0.1415

  R² scores:
    Market: -0.0280
    Model A: -0.0048  (delta=+0.0232)
    Model C: -0.0109  (delta=+0.0170)

======================================================================
VERDICT
======================================================================

  STATUS: DEPLOYABLE
  RATIONALE: Best rebuild model (Model A (pure)) beats market by 1.3% MAE with genuine edge signal (corr=0.1552).

  DEPLOYMENT NOTES:
  1. Model C (hybrid with market anchor) is recommended as the rebuild candidate
  2. Requires pipeline extension to fetch SOG/PP/PK from NHL API boxscores
  3. The original model's live pipeline already falls back to MoneyPuck priors,
     so this rebuild is actually MORE honest about what's available live
  4. If MoneyPuck data becomes available again, the original model is superior

  FEATURE COMPARISON:
  Original model: 24 features (includes xGF, xGA, HD shots from MoneyPuck)
  Rebuild model:  29 features (NHL API + schedule only)
  Dropped features: xgf_rolling_20, xga_rolling_20, hd_shots_for_rolling_20,
                    hd_shots_against_rolling_20, hd_pressure (4+2 features)