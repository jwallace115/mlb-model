# V1 Clean Retrain — Training Report

## Model Specification
- Algorithm: Ridge Regression (alpha=50.0)
- Features: 25 (same feature set as Phase 9 baseline)
- Scaler: StandardScaler fit on training data only
- Training: [2022, 2023] (4847 games)
- Validation: 2024 (2421 games)
- OOS: 2025 (2427 games)

## Performance Metrics

| Metric | Train | Validation | OOS |
|--------|-------|-----------|-----|
| RMSE   | 4.424 | 4.281 | 4.569 |
| MAE    | 3.492 | 3.399 | 3.608 |

## Residual Sigma
- Clean model: 4.424
- Contaminated V1: 4.361
- Delta: +0.062

## Comparison with Contaminated V1

| Model | RMSE Val | RMSE OOS |
|-------|----------|----------|
| Contaminated V1 | 4.240 | 4.514 |
| Clean V1 | 4.281 | 4.569 |
| Delta | +0.041 | +0.055 |

## Feature Coefficients (sorted by |coef|)

| Feature | Coefficient |
|---------|------------|
| away_bullpen_delta | -0.3524 |
| temperature | +0.3404 |
| home_sp_xfip | +0.3170 |
| away_bp_delta_exposure | +0.2975 |
| home_bp_delta_exposure | +0.2585 |
| home_bullpen_delta | -0.2571 |
| park_factor_hr | +0.2493 |
| park_factor_runs | +0.2493 |
| away_sp_k_pct | -0.1471 |
| away_wrc_plus | +0.1249 |
| flyball_wind_interaction | +0.1106 |
| away_sp_xfip | -0.1075 |
| away_rest_days | +0.0917 |
| away_high_leverage_avail | -0.0846 |
| home_sp_bb_pct | -0.0787 |
| home_sp_k_pct | -0.0741 |
| home_high_leverage_avail | +0.0693 |
| home_wrc_plus | +0.0646 |
| umpire_over_rate | -0.0554 |
| doubleheader_flag | -0.0452 |
| wind_factor_effective | +0.0393 |
| away_sp_bb_pct | +0.0170 |
| home_sp_avg_ip | -0.0150 |
| away_sp_avg_ip | +0.0097 |
| home_rest_days | +0.0066 |
