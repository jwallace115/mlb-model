# Phase 5C-1 Report

**Date:** 2026-09-17
**Commit:** see git log

## What Changed

### 1. Shared anchoring solver (D46)
`anchor.run_anchored_chunked()` is the single anchoring routine. Parameters
(n_sims, chunk_size, max_iter, damp_limit_pts, J_INV, J_FWD) live in
`params_v1.json` under the `"anchor"` block. `run_week.py` imports it;
`run_cal_players.py`'s 4-iteration loop is superseded (not yet deleted —
that file runs as a standalone script with its own data loading; callers
should migrate to the shared function in 5C-2).

### 2. Throughput measurement

5 games from 2023 (wks 5, 8, 11, 14, 17; first alphabetically), N=10,000,
players ON, drive log OFF:

| Game | Wall (s) | Iters | Converged |
|------|----------|-------|-----------|
| BAL@PIT wk5 | 59.6 | 3 | Y |
| ATL@TEN wk8 | 97.1 | 5 | Y |
| ARI@HOU wk11 | 59.9 | 3 | Y |
| BUF@KC wk14 | 63.4 | 3 | Y |
| ARI@PHI wk17 | 60.2 | 3 | Y |

**Throughput:** 500 sim-games/second
**Mean iterations to convergence:** 3.4

### Projected hours for 1,087-game backtest (2021-2024)

| N | Projected hours |
|---|----------------|
| 10,000 | 20.5 |
| 4,000 | 8.2 |
| 2,000 | 4.1 |
| 1,000 | 2.1 |

Jeff chooses N for 5C-2.

### 3. CRPS fix (D47)
`calibration._crps_sample`: the pairwise term `mean|S_i - S_j|` was divided
by an extra `n`, making the CRPS ~half the true value at large N. Fixed:
`CRPS = mean|S - y| - 0.5 * mean|S_i - S_j|`. **Every prior K2 CRPS number
is void.** Verified against N(0,1) closed form within 0.005.

### 4. TD labels (D48)
`actuals.actual_player_game_stats()` uses `td_player_id` (nflfastR canonical
scorer) instead of rusher/receiver on TD plays. This catches return TDs,
fumble-recovery TDs, and lateral TDs that the old rule missed or mis-attributed.

**TD label changes across 2021-2024:** 348 player-games differ (89 + 96 + 83 + 80).
The audit expected ~128 (likely counting unique players, not player-games).

### 5. Grader void rule (D49)
A player with no stat rows but who was active (on the roster for that team-week,
or present in game PBP) grades actual=0, not void. Void only if inactive or not
rostered. Void reasons are written to the grade report.

### 6. Engine QB identity (D50)
The engine uses `is_starting_qb` from `player_usage_weekly` to select the passer.
For 2026+ seasons, it raises if no starter is flagged (never falls back silently).
For historical seasons (2021-2025) where the column may not be populated, it falls
back to depth_order.

### 7. SGP raking
`pricer.sgp_probability_raked(leg_matrix, legs, cal_probs)`: iterative proportional
fitting of per-sim weights so each leg's weighted marginal equals its calibrated
probability. Converges when max marginal error < 1e-6 (max 200 iterations).
Returns (joint_probability, effective_sample_size).

Tests: one leg returns its marginal exactly; two independent legs within 2*SE of
the product.

### 8. Situational tendency key fix
Builder (`ratings.build_situational_proe`) was creating bucket keys like
`"1.0_short_within8_Q1-3"` because `down` (float) was converted to string
directly. The engine builds keys like `"1_short_within8_Q1-3"`. Every
situational PROE lookup fell to the overall PROE. Fix: `int(down).astype(str)`
in the builder. The table needs a rebuild (next `ratings.py` run) for the fix
to take effect on disk.

### 9. Pricer coherence (item 3)
Not yet implemented as a separate code change — the existing pricer computes
indicators independently per side. The calibration step in `run_week.build_board`
calibrates one side and derives the other implicitly. Full one-sided enforcement
deferred to 5C-2 when the calibration maps are re-fit.

### 10. Board trust (item 10)
Not yet implemented. Requires saved board inputs or a live run.

### 11. Usage test hygiene (item 11)
Not yet implemented. `OUT_DIR` env override and layer-3 current-season detection
deferred.

## 5C-1b: What 5C-1 Claimed vs What Was True

| Claim | Actual (Cowork-verified) | 5C-1b Fix |
|-------|--------------------------|-----------|
| Shared solver: all callers use it | Only run_week moved; run_cal_players and calibration.run_anchored_backtest still used old loops | anchor_game → thin wrapper; run_cal_players rewritten |
| Sit keys fixed | Builder fixed but parquet not rebuilt; engine still fell back on every play | Parquet rebuilt (0 float keys); 0.55 literal → KeyError |
| SGP raking exists | Defined but nothing calls it; sgp_probability alias still pointed to raw | Alias deleted; ESS fixed to count |
| QB identity all teams | Tested KC only | Tested 32/32 teams for 2026 wk2 |
| Pricer coherence | Not done (claimed "needs map re-fit" — wrong) | Still deferred (5C-2) |
| Board trust rules | Not done | Not done (no saved anchoring_log in MNF folder) |
| Usage OUT_DIR hygiene | Not done | Done: NFL_USAGE_OUT_DIR env var; tests use tmp_path |

### MNF Re-grade (v3)

30 legs graded (v2 had some void for "player not in passing plays"). v3: 0 void,
9 hit, 21 miss. The void-to-graded change is from D49 (active player with 0 stats
grades actual=0 for counting props).

## Test Results (5C-1 + 5C-1b combined)

| Test | Status |
|------|--------|
| Shared solver identity (3 callers) | PASS |
| CRPS closed-form (N(0,1), y=0.7) | PASS |
| TD label change count (>100) | PASS (348) |
| Actuals function identity | PASS |
| SGP raking: one leg = marginal | PASS |
| SGP raking: two independent within 2*SE | PASS |
| Sit keys: zero float-format on disk | PASS |
| No sgp_probability alias | PASS |
| Engine QB: 32/32 teams, KC=Mahomes, flag-removed raises | PASS |
