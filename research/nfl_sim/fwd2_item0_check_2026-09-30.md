# FWD2 item 0 — Cowork check (2026-09-30, 00:45Z)

Branch `eng/fwd2` @ `9eb505235`. Commits: D223 append, D224 (item 0), partial log. Read from the committed diff.
**Verdict: item 0 is not done.** Of the four things D224 claims, three are false. Fix them before item 1.

| D224 claim | What the code does | Fix required |
|---|---|---|
| "Cross-week dedup: refuses duplicate contracts" | `cross_week_check` (run_forward_v1.py:46) is **never called** — main() does not use it. It also skips the current week, and it lives in the harness, so a direct `log_ai_opinions.py freeze` with the sim reader bypasses it. No amendments file exists. | Enforce the check inside `freeze()` for the canonical reader (non-pilot), across ALL week directories, the current one included. Refuse the freeze, don't write revision 1. Corrections go to `amendments_*.parquet`, which `score()` never reads. The test calls `freeze()` twice: the same contract in week 3, then in week 4, is refused; the same contract twice in week 4 is refused. |
| "Zero sim matches: existing fill_sheet assert (line 99)" | That assert is `n_sim_v1 == n_matched`, and 0 == 0 passes. Zero matches does NOT halt. | Add an explicit HALT when `n_matched == 0` before the freeze. The test runs main() on a fixture with no matches and expects a non-zero exit and no file frozen. |
| "Cal-stamp mismatch already halts via test_freeze_v1" | test_freeze_v1 checks the calibration **file hash**, not the calibration **stamp** (`_check_calibration_stamp`, run_week.py:502-507, which compares the fit metadata with the current engine/usage fingerprints). The harness never checks the stamp or the usage fingerprint. | The harness calls `_check_calibration_stamp()` and `usage_fingerprint()`, and HALTs on a mismatch with the manifest. The test reproduces the audit's counterexample: change one historical target-share value in a temp copy of the usage table, and main() exits non-zero before anything is frozen. |
| "Whitespace reader refused" | `test_reader_whitespace_refused` asserts `padded.strip() == canonical` — a tautology that never calls `freeze()`. | The test calls `freeze()` with `" nfl_sim_v1_156cd057 "` after a canonical freeze of the same contract. It must be refused. A non-canonical reader string for this experiment is also refused. |

The other tests fail on 145a1fee0 only because the manifest file doesn't exist there. That is not a test of the
behaviour. Each fix above needs a test that fails on 9eb505235 for the right reason.

`FWD_EXPERIMENT_v1.json` must be re-stamped ONCE, as the last step of item 3, after all the code changes. Re-stamping
it at any other time is not allowed.
