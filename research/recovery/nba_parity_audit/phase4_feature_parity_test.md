# Phase 4: Feature Parity Test

## Data Availability on VM

| File | Size | Last Modified | Notes |
|------|------|---------------|-------|
| nba/data/box_stats.parquet | 211KB | Apr 1 | 7,380 team-games (3 seasons) |
| nba/data/features.parquet | 394KB | Apr 1 | 3,690 games, 48 columns |
| nba/data/predictions.parquet | 465KB | Apr 1 | Train+val predictions |
| nba/data/ridge_model.pkl | 1.9KB | Apr 1 | Live model (alpha=0.1) |
| nba/data/nba_results_log.parquet | 32KB | Apr 10 | 164 graded live results |
| nba/data/nba_signal_log.parquet | 11KB | Apr 10 | 35 archetype signal bets |

## VM Limitation
The NBA pipeline runs on MacBook only (nba_api blocked at datacenter IP). Feature tables on the VM are synced copies, not independently computed. This means:
- features.parquet contains TRAINING-ERA features only (2022-2025)
- Current 2025-26 features are computed live on the MacBook each morning
- We cannot independently recompute 2025-26 features on the VM

## Quantified Feature Distribution Gap

For 200 randomly sampled games where location_rolling was used in training:
- **Mean diff (location_roll - overall_roll) for ORtg:** +0.94 pts
- **Std diff:** 2.84 pts
- **Median |diff|:** 1.83 pts
- **P90 |diff|:** 5.21 pts
- **Max |diff|:** 9.02 pts

This means the live pipeline systematically feeds the model ORtg/DRtg/pace values that differ from what it was trained on. The difference is not random noise -- it is a structural shift due to home/away performance splits.

## Impact Assessment

The top 6 Ridge coefficients are the 3 efficiency features x 2 sides:
- home_pace: +4.17, away_pace: +3.93
- home_ortg: +1.99, away_ortg: +1.57
- home_drtg: +1.67, away_drtg: +1.38

With a median 1.8-pt ORtg feature gap and a coefficient of ~1.8, the expected prediction shift is ~3.2 pts for ORtg alone. Combined with DRtg and pace gaps, total prediction drift could be 5-10 pts for individual games.

However, because the gap is bidirectional (sometimes loc > overall, sometimes loc < overall, mean = +0.94), the average bias may be small. The VARIANCE of predictions is increased, which degrades calibration but may not create systematic directional bias.

## Independent Recomputability
UNVERIFIABLE on VM -- would require running the live pipeline on MacBook and comparing feature vectors against what training features.py would produce for the same games.
