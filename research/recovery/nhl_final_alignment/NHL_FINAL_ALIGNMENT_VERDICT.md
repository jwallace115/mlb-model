# NHL FINAL ALIGNMENT VERDICT: READY FOR SHADOW

## Summary
- PK% definition corrected from pk_goals_against (0.966 mean) to opp_pp_goals (0.79 mean)
- Feature table rebuilt with live-compatible definitions
- Model A retrained on corrected features
- Live parity verified: rebuild features match live pipeline computation

## Action Items
1. Copy model_A_home.pkl and model_A_away.pkl to nhl/ or update REBUILD paths
2. Copy nhl_live_compatible_feature_table_v2.parquet as the new rebuild FT
3. Run shadow for 3+ game days to validate

## Files Produced
- research/recovery/nhl_final_alignment/model_A_home.pkl
- research/recovery/nhl_final_alignment/model_A_away.pkl
- research/recovery/nhl_final_alignment/nhl_live_compatible_feature_table_v2.parquet
- research/recovery/nhl_final_alignment/phase1_live_feature_spec.md
- research/recovery/nhl_final_alignment/phase2_feature_build.md
- research/recovery/nhl_final_alignment/phase3_retrain_report.md
- research/recovery/nhl_final_alignment/phase4_parity_report.md

OOS results CSV: nhl_final_alignment_oos_results.csv (1312 games)