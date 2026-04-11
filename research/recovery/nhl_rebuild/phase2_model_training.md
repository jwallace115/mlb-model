======================================================================
PHASE 2: MODEL TRAINING — 3 VARIANTS
======================================================================

Splits: train=2624, val=1312, oos=1312, live=1258

--- MODEL A: Pure Hockey (no market) ---

  HOME model (29 features):
    Best alpha: 100.0
    Train MAE=1.3985  bias=+0.0000
    Val   MAE=1.3829  bias=-0.0238
    OOS   MAE=1.4261  bias=-0.1896

  AWAY model (29 features):
    Best alpha: 500.0
    Train MAE=1.3435  bias=+0.0000
    Val   MAE=1.4067  bias=+0.0051
    OOS   MAE=1.3860  bias=+0.0266
  Model A Total train: MAE=1.8289  bias=+0.0000
  Model A Total val: MAE=1.8637  bias=-0.0186
  Model A Total oos: MAE=1.8708  bias=-0.1630

--- MODEL B: Residual (market anchor + hockey adjustment) ---
  Market-available: train=2622, val=1312, oos=1312
  Best alpha: 500.0
  Model B Total train: MAE=1.8284  bias=+0.0000  resid MAE=1.8284
  Model B Total val: MAE=1.8790  bias=+0.1706  resid MAE=1.8790
  Model B Total oos: MAE=1.8957  bias=-0.0021  resid MAE=1.8957

--- MODEL C: Hybrid (closing_total as additional feature) ---

  HOME model (30 features):
    Best alpha: 50.0
    Train MAE=1.3978  bias=-0.0000
    Val   MAE=1.3830  bias=-0.0128
    OOS   MAE=1.4274  bias=-0.1915
    closing_total coef (scaled): 0.0295

  AWAY model (30 features):
    Best alpha: 500.0
    Train MAE=1.3402  bias=+0.0000
    Val   MAE=1.4114  bias=+0.0565
    OOS   MAE=1.3896  bias=+0.0417
    closing_total coef (scaled): 0.1045
  Model C Total train: MAE=1.8250  bias=-0.0000
  Model C Total val: MAE=1.8657  bias=+0.0437
  Model C Total oos: MAE=1.8751  bias=-0.1498

======================================================================
MODEL COMPARISON (OOS = 2024-25 season)
======================================================================

  Model            MAE    RMSE     Bias  vs Market
  ------------ ------- ------- -------- ----------
  Market        1.8956  2.3525  -0.1410   baseline
  Model A       1.8708  2.3270  -0.1630      -1.3%
  Model B       1.8957  2.3444  -0.0021      +0.0%
  Model C       1.8751  2.3297  -0.1498      -1.1%