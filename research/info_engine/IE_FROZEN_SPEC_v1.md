# IE Frozen Spec v1 — 2026-10-12

## Feature list (21 features)

```
f1_inj_trajectory_diff
f2_pressure_diff
f3_home_motion_rate
f3_away_motion_rate
f3_home_pa_rate
f3_away_pa_rate
f4_ryoe_diff
f5_home_separation
f5_away_separation
f6_home_snap_shift
f6_away_snap_shift
f7_ref_avg_total
f7_ref_game_count
f8_home_dc_changes
f8_away_dc_changes
f9_wind_x_outdoor
f9_rest_diff
f9_temp
f9_outdoor
f9_grass
f10_line_move
```

## Alpha (frozen by LOSO on 2021-23)

- Margin/cover (LogReg C=1/alpha): alpha=100
- Totals (Ridge): alpha=1000

## As-of rules

- All features: week N-1 or earlier data only
- F1 (injuries): latest report with `date_modified < kickoff_utc`
- F3 (FTN): available 2022+ only
- F8: week N-1 depth chart only; week N is NEVER read
- F10: requires `nfl_line_movement.parquet` open-total data (67-74% coverage)

## Aggregation

- F2-F6: snap-weighted mean over players with >= 20 offensive snaps in that week,
  by position group (QB, OL, WR/TE, RB; DL, LB, DB), computed through week N-1

## Code hashes

```
build_feature_table.py SHA256: d5baa12e0555300548a6b12c2dc594f3e21094323bd4765bc1e98e3002793461
discovery_fit.py SHA256:       0e50f8f77f73861278de3de3a7926513bad11390eaa39693da83d24eaaa2f975
```

## Discovery results summary (2021-23 LOSO, NOT OOS)

- Margin ridge: LOSO log-loss 0.674 vs 0.693 baseline (+0.019 improvement)
- Totals ridge: LOSO MSE 155.8 vs 174.6 baseline (+18.8 improvement)
- Strongest families on margin: F2 (t=4.9), F4 (t=4.2), F5 (t=3.5), F3 (t=3.1)
- Strongest on totals: F8 (t=-2.5), F7 (t=2.0)
- All four pre-registrations FALSIFIED (stronger signal than expected)

## Status

FROZEN. Do not modify feature list, alpha, or as-of rules without a new decision entry.
2024 clean look is IE-2.
