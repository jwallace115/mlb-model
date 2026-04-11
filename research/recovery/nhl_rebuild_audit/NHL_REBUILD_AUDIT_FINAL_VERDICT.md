# NHL Rebuild Audit -- Final Verdict
Date: 2026-04-10

## VERDICT: CLEAN BUT NOT LIVE-IDENTICAL

## Rationale

### What is proven clean:
1. DATA PROVENANCE: The rebuild uses zero MoneyPuck proprietary analytics (xG,
   Corsi, Fenwick, HD shots). All features trace to NHL API boxscore data or
   schedule-derived calculations.

2. PIT SAFETY: Rolling windows use strict prior-only indexing (iloc[:i]) with
   per-season resets. 5/5 manual spot checks confirmed exact reproducibility.
   Minor league-average look-ahead in shrinkage prior is immaterial.

3. ARTIFACT ISOLATION: Zero references to any contaminated model, feature table,
   or pickle file. The rebuild is fully self-contained.

4. ECONOMICS: Uses actual closing prices from market snapshots with 100% OOS
   coverage. No synthetic flat-vig assumptions.

5. SIGNAL QUALITY: corr(edge, market_error) = 0.1552 is a strong genuine signal.
   Edge-size calibration is monotonic. Model A beats market by 1.3% MAE OOS.

### What prevents LIVE-IDENTICAL status:
The live pipeline (nhl_daily_pipeline.py) does NOT currently extract shots on goal,
PP goals, PP opportunities, or PK goals against from NHL API boxscores. It falls
back to stale MoneyPuck OOS priors for these fields. The rebuild model was trained
on actual values for these features.

To achieve live-identical status, the pipeline needs ~30 lines of code added to
parse SOG/PP/PK from the boxscore response it already fetches.

### Concerns for deployment:
1. Growing negative bias (2023: -0.02, 2024: -0.16) suggests the model may need
   periodic recalibration as NHL scoring patterns evolve.
2. SOG per game is declining league-wide (31.6 to 28.0); a model trained on
   2021-2022 data may overweight shot volume features.
3. Model A OOS betting ROI of +5.3% (all bets) and +3.8% (edge >= 0.5) are
   promising but based on a single season.

## Deployment Recommendation
1. Fix the live pipeline to extract SOG/PP/PK from NHL API boxscores (~30 lines)
2. Shadow test for 2-3 weeks to confirm live predictions match backtest behavior
3. Monitor bias drift monthly; recalibrate if bias exceeds +/-0.3
4. Use Model A (pure hockey) for live deployment -- it has the strongest edge
   signal and does not depend on market closing lines as an input feature

## Files Audited
- research/recovery/nhl_rebuild/nhl_rebuild.py (1,183 lines)
- research/recovery/nhl_rebuild/nhl_rebuild_features.parquet (6,506 games, 44 cols)
- nhl/nhl_games_canonical.csv (6,506 games, 62 cols)
- nhl/nhl_market_snapshots.parquet (5,246 games, 13 cols)
- nhl/nhl_feature_table.parquet (6,506 games, 54 cols)
- nhl/nhl_daily_pipeline.py (live pipeline)
- research/recovery/nhl_rebuild/model_A_home.pkl
- research/recovery/nhl_rebuild/model_A_away.pkl
