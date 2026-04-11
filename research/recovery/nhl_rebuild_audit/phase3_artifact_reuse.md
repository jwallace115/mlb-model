# Phase 3: Artifact Reuse Check

## Contaminated Artifact References
Checked the rebuild script for references to 10 known contaminated artifacts:

| Artifact                    | Referenced? |
|----------------------------|-------------|
| nhl_feature_table          | NO          |
| ridge_home                 | NO          |
| ridge_away                 | NO          |
| phase3_build               | NO          |
| phase45                    | NO          |
| nhl_model_outputs          | NO          |
| nhl_decisions              | NO          |
| phase1_build_canonical     | NO          |
| phase4_sim                 | NO          |
| phase45_calibration        | NO          |

## Pickle Usage
- The script WRITES pickle files (model_{k}.pkl) but never LOADS any pre-existing pickles
- No joblib.load calls found
- All models are trained from scratch within the script

## Output Isolation
All outputs are written exclusively under research/recovery/nhl_rebuild/:
- phase0_feature_inventory.md
- phase1_feature_build.md
- nhl_rebuild_features.parquet
- phase2_model_training.md
- phase3_backtest.md
- phase4_identity_lock.md
- phase5_regime_audit.md
- NHL_REBUILD_FINAL_VERDICT.md
- model_A_home.pkl, model_A_away.pkl, model_B.pkl, model_C_home.pkl, model_C_away.pkl

## Data Flow
```
nhl_games_canonical.csv  -->  [rebuild script]  -->  nhl_rebuild_features.parquet
nhl_market_snapshots.parquet -->                -->  model_*.pkl
```
No old model artifacts or contaminated feature tables enter the pipeline.

VERDICT: CLEAN -- no artifact reuse. Full isolation from contaminated pipeline.
