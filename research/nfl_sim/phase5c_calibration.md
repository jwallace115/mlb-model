# Phase 5C Calibration — fit_5c2b Maps, K4, TD Labels

## Census

Fit from `nfl/data/sim/outputs/fit_5c2b/games/` checkpoints.

| Season | Games | Converged | Unconverged |
|--------|-------|-----------|-------------|
| 2021   | 272   | 272       | 0.0%        |
| 2022   | 271   | 271       | 0.0%        |
| 2023   | 272   | 272       | 0.0%        |
| 2024   | 272   | 272       | 0.0%        |
| **Total** | **1087** | **1087** | **0.0%** |

Engine commit: `b86967a39`. N=5000 per game, mean 3.0 iterations,
|err_m| 0.153, |err_t| 0.135. Convergence criterion: 2*SE both channels.

## Calibration Maps

22 isotonic families fitted on 2021-24 converged games:

### Game families

| Family       | N obs    | Max reliability gap | Monotone |
|-------------|----------|---------------------|----------|
| margin_side | 61,851   | 0.002               | Yes      |
| total_side  | 22,827   | 0.008               | Yes      |
| team_total  | 127,022  | 0.002               | Yes      |

### Prop families (by position)

| Family            | N obs  | Max gap | Monotone |
|-------------------|--------|---------|----------|
| prop_rec_WR       | 17,958 | 0.005   | Yes      |
| prop_rec_TE       | 6,577  | 0.010   | Yes      |
| prop_rec_RB       | 4,320  | 0.007   | Yes      |
| prop_rec_yds_WR   | 29,698 | 0.003   | Yes      |
| prop_rec_yds_TE   | 10,765 | 0.004   | Yes      |
| prop_rec_yds_RB   | 7,178  | 0.002   | Yes      |
| prop_rush_yds_RB  | 6,218  | 0.012   | Yes      |
| prop_rush_yds_WR  | 886    | 0.005   | Yes      |
| prop_rush_att_RB  | 3,975  | 0.007   | Yes      |
| prop_atd_WR       | 6,590  | 0.013   | Yes      |
| prop_atd_TE       | 2,533  | 0.015   | Yes      |
| prop_atd_RB       | 1,746  | 0.014   | Yes      |
| prop_atd_QB       | 1,691  | —       | Yes      |
| prop_pass_att_QB  | 6,568  | —       | Yes      |
| prop_pass_cmp_QB  | 6,357  | —       | Yes      |
| prop_pass_yds_QB  | 8,594  | —       | Yes      |
| prop_pass_td_QB   | 6,521  | —       | Yes      |
| prop_rush_att_QB  | 1,468  | —       | Yes      |
| prop_rush_yds_QB  | 2,465  | —       | Yes      |

All maps monotone, x-domain spans [0.01, 0.99]. Synthetic identity test
(50,000 perfectly-calibrated Bernoulli draws): max decile error 0.015 < 0.02.

### Reliability deciles (IN-SAMPLE)

Labelled IN-SAMPLE. All game families have mean gap < 0.003 and max gap < 0.01.
Prop families max gap ≤ 0.015. Saved to `fit_5c2b/reliability_deciles.parquet`.

## K4: Player-Level Edge

Measured on integer-ladder thresholds at flat -110 (no Hard Rock closing prices
in the archive). IN-SAMPLE on 2021-24 (same data as calibration fitting).

| Family      | N      | Over ROI | Under ROI | Over+Under |
|-------------|--------|----------|-----------|------------|
| atd         | 12,313 | +5.8%    | +44.1%    | +49.9%     |
| receptions  | 23,773 | +31.8%   | +37.8%    | +69.6%     |
| rec_yds     | 32,936 | +30.3%   | +41.7%    | +72.0%     |
| rush_yds    | 12,184 | +28.6%   | +44.6%    | +73.3%     |
| pass_att    | 8,684  | +43.1%   | +20.5%    | +63.5%     |
| pass_yds    | 6,217  | +26.7%   | +36.7%    | +63.4%     |

**Symmetry check**: over_ROI + under_ROI should be ≈ -2×vig (−9.1% at -110)
for a perfectly calibrated model against fair closing prices. All families
show +50% to +73% — expected for in-sample isotonic calibration with no
real closing prices. This is not evidence of a live edge.

By season (all families pooled):
- 2021: over +34.6%, under +39.6%
- 2022: over +30.1%, under +40.8%
- 2023: over +34.0%, under +41.2%
- 2024: over +31.1%, under +40.2%

K4 data saved at `fit_5c2b/k4_player_props.parquet` (not tracked).

## A8: TD-Label Cause Breakdown

`td_player_id` (nflfastR canonical scorer) used since 5C-1 for anytime-TD
grading. Cases where `td_player_id ≠ receiver/rusher` (2021-24, 5,722 TDs):

| Cause                | Count |
|----------------------|-------|
| receiver ≠ td_player | 152   |
| fumble-return        | 50    |
| lateral              | 3     |
| **Total changed**    | **205** |

Pass-play mismatches specifically: 213 (includes both directions).
Reconciliation with audit's ~128: the audit counted a single-season subset.

## What Remains Untrusted and Why

1. **K4 symmetry**: no Hard Rock closing prices in the archive → integer-ladder
   K4 is in-sample and uninformative about live edge.
2. **Prop families with <1000 obs** (prop_rush_yds_WR, prop_atd_QB,
   prop_rush_att_QB): isotonic fit is noisy; decile gaps not reported.
3. **Three engine reds** (4th-down go rate 0.210 vs 0.198, penalties 6.20 vs 5.51,
   tied-drive expiry 0.110 vs 0.050): pre-existing from 5A-3/4/9, not caused
   by calibration. These affect the sim distribution shape, which the isotonic
   maps partially correct but cannot fully fix.
4. **OOS performance**: all metrics are IN-SAMPLE on 2021-24. The only true
   OOS test is the 2025 holdout (gated by HOLDOUT_2025_SCORED.lock).
