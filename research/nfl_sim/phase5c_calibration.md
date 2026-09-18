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

| Family       | N obs    | Monotone |
|-------------|----------|----------|
| margin_side | 61,851   | Yes      |
| total_side  | 22,827   | Yes      |
| team_total  | 127,022  | Yes      |

### Prop families (by position)

| Family            | N obs  | Monotone |
|-------------------|--------|----------|
| prop_rec_WR       | 17,958 | Yes      |
| prop_rec_TE       | 6,577  | Yes      |
| prop_rec_RB       | 4,320  | Yes      |
| prop_rec_yds_WR   | 29,698 | Yes      |
| prop_rec_yds_TE   | 10,765 | Yes      |
| prop_rec_yds_RB   | 7,178  | Yes      |
| prop_rush_yds_RB  | 6,218  | Yes      |
| prop_rush_yds_WR  | 886    | Yes      |
| prop_rush_att_RB  | 3,975  | Yes      |
| prop_atd_WR       | 6,590  | Yes      |
| prop_atd_TE       | 2,533  | Yes      |
| prop_atd_RB       | 1,746  | Yes      |
| prop_atd_QB       | 1,691  | Yes      |
| prop_pass_att_QB  | 6,568  | Yes      |
| prop_pass_cmp_QB  | 6,357  | Yes      |
| prop_pass_yds_QB  | 8,594  | Yes      |
| prop_pass_td_QB   | 6,521  | Yes      |
| prop_rush_att_QB  | 1,468  | Yes      |
| prop_rush_yds_QB  | 2,465  | Yes      |

All maps monotone, x-domain spans [0.01, 0.99]. Synthetic identity test
(50,000 perfectly-calibrated Bernoulli draws): max decile error 0.015 < 0.02.

### Reliability deciles (IN-SAMPLE FIT CHECK)

These deciles are an **in-sample fit check**: isotonic regression reproduces
its own training deciles by construction. They confirm the fitting procedure
ran correctly, not that the model is calibrated out-of-sample. All game
families show mean gap < 0.003 and max gap < 0.01; prop families max gap
<= 0.015. Saved to `fit_5c2b/reliability_deciles.parquet`.

## K4: Player-Level Edge at Real Closing Prices

72,850 legs graded against 6-book consensus closing (DK, FD, BetMGM,
BetRivers, Caesars, Unibet; 2023-24 only). Player names resolved via
names.py (74k exact_team, 1.7k exact_league, 700 fi_last).

Vig formula: expected_sum = 2/total_implied - 2 (where total_implied =
implied_over + implied_under, median ~1.07).

### Flat K4 (bet every line, no model filter)

| Family      | N      | Over ROI | Under ROI | Sum     | Expected | Sym err |
|-------------|--------|----------|-----------|---------|----------|---------|
| receptions  | 11,135 | -9.8%    | -2.6%     | -12.5%  | -12.8%   | 0.3pp   |
| rec_yds     | 32,475 | -7.5%    | -5.2%     | -12.7%  | -13.1%   | 0.4pp   |
| rush_yds    | 13,684 | -9.3%    | -2.7%     | -12.0%  | -13.2%   | 1.2pp   |
| rush_att    | 2,365  | -17.7%   | +4.5%     | -13.2%  | -12.7%   | 0.4pp   |
| pass_yds    | 8,212  | -5.1%    | -5.3%     | -10.4%  | -13.1%   | **2.7pp** |
| pass_att    | 1,431  | -11.2%   | -1.4%     | -12.6%  | -12.6%   | 0.0pp   |
| pass_cmp    | 1,710  | -5.0%    | -6.5%     | -11.5%  | -12.8%   | 1.3pp   |
| pass_td     | 1,838  | -8.0%    | -5.9%     | -13.9%  | -13.0%   | 0.9pp   |

**Symmetry check** (|sum - expected| < 2pp for n >= 500): 7/8 PASS.
pass_yds FAIL at 2.7pp — reported as a matching bug (PBP pass_yds vs
prop definition), not an edge claim.

**No family has positive flat-over ROI.** Consistent with D17 (receptions
-5.4pp at different N/engine; now -9.8% at real closing, same direction).

### Model-filtered K4 (bet when model sees edge vs devig)

| Family      | Over N | Over ROI | Under N | Under ROI |
|-------------|--------|----------|---------|-----------|
| receptions  | 3,605  | -6.9%    | 7,526   | -1.2%     |
| rec_yds     | 10,748 | -0.4%    | 21,727  | -2.2%     |
| rush_yds    | 5,077  | -5.1%    | 8,607   | +0.4%     |
| pass_yds    | 2,768  | -10.4%  | 5,444   | -8.2%     |
| pass_td     | 429    | +7.3%    | 1,409   | -2.9%     |

No family shows reliable positive ROI on both sides after model filtering.

### By season (flat, all families pooled)

| Season | N      | Over ROI | Under ROI | Sum    | Expected |
|--------|--------|----------|-----------|--------|----------|
| 2023   | 35,654 | -7.6%    | -4.7%     | -12.3% | -13.1%   |
| 2024   | 37,196 | -9.0%    | -3.4%     | -12.3% | -13.1%   |

K4 data saved at `fit_5c2b/k4_real_closing.parquet` (not tracked).

## A8: TD-Label Cause Breakdown

`td_player_id` (nflfastR canonical scorer) used since 5C-1 for anytime-TD
grading. Cases where `td_player_id != receiver/rusher` (2021-24):

| Unit          | Count | Explanation |
|---------------|-------|-------------|
| **TD plays**  | 205   | Distinct scoring plays where the canonical scorer differs from the receiver (pass) or rusher (run) |
| **Player-games** | 407 | (game_id, player_id) pairs whose ATD grade changes: each mismatch affects 2 players (gainer + loser) |

| Cause (TD plays)       | Count |
|------------------------|-------|
| receiver != td_player  | 152   |
| fumble-return          | 50    |
| lateral                | 3     |
| **Total**              | **205** |

Reconciliation: 5C-1 reported ~348 (player-games); the recount gives 407
player-games (205 plays x 2 - duplicates). The 5C-1 count was an undercount,
likely because it used a different filter (e.g., pass plays only, or
counted only the gainer, not the loser).

## What Remains Untrusted and Why

1. **No positive edge**: K4 at real closing prices shows no family with
   positive flat-over ROI. The model grades props at closing-price accuracy,
   not better. Live edge (if any) requires CLV, not K4.
2. **pass_yds symmetry**: 2.7pp gap — likely a PBP-vs-official stat mismatch.
   Treat pass_yds calibration as untrusted until reconciled.
3. **Prop families with <1000 obs** (prop_rush_yds_WR, prop_atd_QB,
   prop_rush_att_QB): isotonic fit is noisy.
4. **Three engine reds** (4th-down go rate 0.210 vs 0.198, penalties 6.20
   vs 5.51, tied-drive expiry 0.110 vs 0.050): pre-existing from 5A-3/4/9.
5. **OOS performance**: all metrics are IN-SAMPLE on 2021-24. The only
   true OOS is prospective 2026 grading (2025 is consumed per the
   2026-09-14 decision).
