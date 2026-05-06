# MLB CLV Reverse Engineering V1

**Runtime:** 29.0s

**IMPORTANT:** Noon snapshot is a BENCHMARK, not true pregame close.

## Movement Statistics (discovery)
- Significant moves (>=0.5): 40.5%
- Up moves: 19.7%
- Down moves: 20.8%
- Mean line_move: -0.000

## Results
- Three-stage survivors: 1224
- FRONT_RUNNABLE: 9
- CLV_ONLY: 21
- NULL: 1194

## Verdict: **FRONT_RUNNABLE**


## Targeted Permutation Audit — Added May 6, 2026

**Limitation:** This is survivor-level permutation, not full search-level max-z permutation.

- Original FRONT_RUNNABLE survivors: 9
- Permutation pass (90th pctl): 6
- Permutation fail: 3
- Independent mechanism families: 5

### Per-Survivor Results

| Signal | z | p90 | Pctl | OOS N | Revised Tier |
|---|---|---|---|---|---|
| opp_sp_batmiss_whiff_rate_last_5_H × high_lev_hr_r | -2.69 | +0.72 | 0% | 133 | NEEDS_PERMUTATION_RETEST |
| plate_k_rate_last_10_L × high_lev_k_rate_baseline_ | -2.24 | +1.28 | 0% | 45 | NEEDS_PERMUTATION_RETEST |
| opp_sp_workload_pitches_last_5_H × top_order_xwoba | +2.77 | +1.14 | 100% | 88 | FRONT_RUNNABLE_CONFIRMED |
| opp_sp_workload_ppbf_last_10_L × high_lev_hr_rate_ | -2.13 | +1.34 | 1% | 162 | NEEDS_PERMUTATION_RETEST |
| opp_pl_sl_pct_last_3_L × opp_pl_velo_ff_mean_last_ | +2.59 | +1.23 | 99% | 135 | FRONT_RUNNABLE_CONFIRMED |
| opp_pl_sl_pct_last_3_L × opp_pl_velo_ff_mean_last_ | +2.72 | +1.32 | 100% | 131 | FRONT_RUNNABLE_CONFIRMED |
| opp_pl_sl_pct_last_3_L × opp_pl_velo_ff_mean_seaso | +2.59 | +1.25 | 99% | 144 | FRONT_RUNNABLE_CONFIRMED |
| opp_pl_sl_pct_last_5_L × opp_pl_velo_ff_mean_last_ | +2.61 | +1.20 | 99% | 130 | FRONT_RUNNABLE_CONFIRMED |
| opp_pl_sl_pct_last_5_L × opp_pl_velo_ff_mean_last_ | +2.78 | +1.38 | 100% | 131 | FRONT_RUNNABLE_CONFIRMED |

### Revised Verdict
**6 FRONT_RUNNABLE signals confirmed** after permutation.
