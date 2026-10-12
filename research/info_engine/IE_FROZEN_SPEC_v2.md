# IE Frozen Spec v2 — 2026-10-12 (supersedes v1)

v1 was RETRACTED due to the margin_resid bug (r=0.69 with spread_line).

## Corrected formulas

- `margin_resid = margin - spread_line` (|r| = 0.015 with spread_line)
- `total_resid = total - total_line` (|r| = 0.044 with total_line)
- `home_cover = margin > spread_line` (|r| = 0.03 with spread_line, rate 47.4%)

## Feature list (21 primary + 10 _simple)

Primary (snap-weighted where applicable):
```
f1_inj_trajectory_diff
f2_pressure_diff
f3_home_motion_rate, f3_away_motion_rate
f3_home_pa_rate, f3_away_pa_rate
f4_ryoe_diff
f5_home_separation, f5_away_separation
f6_home_snap_shift, f6_away_snap_shift
f7_ref_avg_total, f7_ref_game_count
f8_home_dc_changes, f8_away_dc_changes
f9_wind_x_outdoor, f9_rest_diff, f9_temp, f9_outdoor, f9_grass
f10_line_move
```

## Alpha (frozen by LOSO on 2021-23)

- Margin/cover (LogReg C=1/alpha): alpha=1000
- Totals (Ridge): alpha=1000

## Code hashes

```
build_feature_table.py SHA256: 167391c0662bd073e5637636ebc3fc8eac9355e6bbc0856ce89e25e317044375
discovery_fit.py SHA256:       e8921859d92733b977c7e992b8be11bfffda4894a69677b9abf4644c5158e5af
```

## Discovery results summary (2021-23 LOSO, corrected)

- **Margin: NO SIGNAL.** All-family ridge log-loss 0.700 vs 0.693 baseline (-0.007, WORSE).
  No individual family exceeds |t| = 1.6 on margin except F9 (t=-3.04, unstable sign).
- **Totals: weak signal.** F8 t=-2.5, F7 t=2.0. Ridge MSE 155.4 vs 174.6 baseline (+19.2).
- **The old margin signal was entirely a spread proxy.**

## Status

FROZEN. 2024 clean look is IE-2.
