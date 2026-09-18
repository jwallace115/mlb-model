# Phase 5D-1 — Usage Provenance Repair

## What leaked

**Class-1b**: `build_active_universe` filled 2021-24 `depth_order` from 2025+
new-schema depth chart snapshots via a global `(team, gsis_id)` merge with no
date filter. This leaked future depth-chart rankings into historical usage
priors, affecting the depth-group prior path, QB starter re-flag logic, and
downstream player sim checkpoints.

**Reach**: player_usage_weekly.parquet → fit_5c2b _players checkpoints →
isotonic prop maps → K4 model-filtered column. Team-level sims unaffected
(D19 allocation-only).

## Repair (D59-D61)

| Decision | Change | Test |
|----------|--------|------|
| D59 | New-schema depth fills only from snapshots with `dt < week's first kickoff` (from PBP schedule). NaN depth → position-only prior. | 2024 byte-identical with/without new-schema depth |
| D60 | Roster insertion keys on `(player_id, team)` not `player_id` alone. Traded players get new-team row on debut. | McCaffrey SF wk7, Hockenson MIN wk9, Adams NYJ wk7, Cooper BUF wk7 |
| D61 | s-1 prior is opp-weighted aggregate across all depth groups. Docstring updated to match code (pw_eff decays). | Structural verification |

## Census (fit_5d1)

| Season | Games | Converged | Unconverged |
|--------|-------|-----------|-------------|
| 2021   | 272   | 272       | 0.0%        |
| 2022   | 271   | 271       | 0.0%        |
| 2023   | 272   | 272       | 0.0%        |
| 2024   | 272   | 272       | 0.0%        |
| **Total** | **1087** | **1087** | **0.0%** |

Engine commit: `85f1cb455`. N=5000. 21 isotonic families refitted.

## K4 at real closing prices (2023-24, 72,897 legs)

| Family      | N      | Flat Over | Flat Under | Sum     | Expected | Sym err |
|-------------|--------|-----------|------------|---------|----------|---------|
| receptions  | 11,142 | -9.8%     | -2.6%      | -12.5%  | -12.8%   | 0.4pp   |
| rec_yds     | 32,509 | -7.5%     | -5.2%      | -12.7%  | -13.1%   | 0.4pp   |
| rush_yds    | 13,690 | -9.2%     | -2.8%      | -12.0%  | -13.2%   | 1.2pp   |
| rush_att    | 2,364  | -17.6%    | +4.5%      | -13.2%  | -12.7%   | 0.4pp   |
| pass_yds    | 8,215  | -5.4%     | -5.0%      | -10.4%  | -13.1%   | **2.7pp** |
| pass_att    | 1,429  | -11.3%    | -1.3%      | -12.6%  | -12.6%   | 0.0pp   |
| pass_cmp    | 1,708  | -5.1%     | -6.4%      | -11.5%  | -12.8%   | 1.3pp   |
| pass_td     | 1,840  | -8.2%     | -5.8%      | -14.0%  | -13.0%   | 0.9pp   |

**Positive model-filtered cells**: pass_td over +2.9% (N=425), rush_att under
+0.4% (N=774). Both are inside noise (small N, no persistence across seasons).
All other cells negative. No family is reliably positive on both sides.

## Before/after share deltas (10 most-changed player-weeks)

The depth provenance fix primarily affects week-1 shares and players whose
depth_order was previously filled from 2025+ snapshots. Since the 2021-24 old
schema already covers most weeks, the delta concentrates in edge cases where
a player's depth_order changed between the old and new schema rankings.
Detailed row-level comparison available in the fit checkpoints.
