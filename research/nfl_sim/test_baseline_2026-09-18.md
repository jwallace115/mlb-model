# Test Baseline 2026-09-18

Mechanism: git worktree at cca3e933d (parent of 5D-3 item 1), with
gitignored data directories symlinked from the main working tree. Main
branch untouched throughout.

## Baseline (cca3e933d, pre-5D-3)

- Wall clock: 913.02s (15:13)
- Collected: 126, passed: 122, failed: 4, errored: 0
- pytest summary: `4 failed, 122 passed, 2284 warnings in 913.02s`

## HEAD (f868b7782, post-5D-3)

- Wall clock: 912.73s (15:12)
- Collected: 143, passed: 139, failed: 4, errored: 0
- pytest summary: `4 failed, 139 passed, 2284 warnings in 912.73s`

17 more tests collected (from test_actuals_5d3: 5, test_clv_5d3: 4,
test_raking_5d3: 8). All 17 new tests pass.

## Failing tests (both commits)

| Test node ID | Baseline value | HEAD value | Spec | Verdict |
|---|---|---|---|---|
| test_engine_5a3.py::test_t1_4th_down_go_rate | 0.210 vs 0.198 (diff 0.012) | 0.210 vs 0.198 (diff 0.012) | diff < 0.010 | **Pre-existing** |
| test_engine_5a4.py::test_penalties_per_side | 6.20 vs 5.51 (diff 0.69) | 6.20 vs 5.51 (diff 0.69) | diff < 0.50 | **Pre-existing** |
| test_engine_5a9.py::test_t3_tied_drives_reach_range | 0.110 vs <=0.050 | 0.110 vs <=0.050 | <=0.050 | **Pre-existing** |
| test_usage_5b.py::test_starting_qb_identity_2026 | wk3 ARI-WAS no starter | wk3 ARI-WAS no starter | every team-week has starter | **Pre-existing** (wk3 unplayed) |

## Verdict

All 4 reds are pre-existing: same test, same values, at both commits.
5D-3 introduced zero new failures.

## Note on exit codes

The pytest output shows "4 failed" alongside exit code 0 from the task
runner. Running a single failing test individually returns exit code 1
(correct). The exit code 0 for the full suite is from the task runner's
process wrapper, not from pytest directly. The 4 failures are genuine
AssertionErrors, not xfails — there are no xfail/skip markers in the suite.
