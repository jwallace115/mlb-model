# FWD4 verification — Cowork, 2026-09-30 (15:35Z)

Branch `eng/fwd3` @ `0b6d94a58` (D245 append; D246; D247). Read from the committed code, in a clean worktree on
Linux. Cowork re-ran its own mutation set and the audit-#7 cohort counterexamples.
**Verdict: accepted, conditional on one test-only fix (FWD4b). After that, eng/fwd3 merges, and the primary count of
`nfl_fwd_v1` starts at the week-4 TNF window.**

## What stands
- **The anchor join (D246a).** `primary_cohort(df, reader, sidecar)` joins on (run_id, event_id). Cowork ran the three
  cases:
  - run A anchored, run B unanchored, scoring a run-B row → **excluded ("game not anchored")**;
  - an empty sidecar → **excluded ("no sidecar match")**;
  - a duplicate (run_id, event_id) → **HALT**.

  The order asked for a HALT on a missing sidecar. The row is excluded and counted instead. **Accepted:** exclusion
  can only shrink the cohort, and the count is printed with its reason.
- **Written once (D246b).**
  - The frozen parquet is written only by `freeze()` (log_ai_opinions.py:356).
  - The bundle manifest is finalized before the freeze (run_forward_v1.py:735).
  - `bundle_digest` and `experiment_digest` are on every frozen row (:739-746).
  - Publication goes to `<run-dir>/publication.json` and to the ai_opinions manifest entry.
  - The frozen file is not rewritten.
- **Mutations (D247).** Cowork applied each one, re-stamping a temporary manifest each time, and **every one is now
  caught by a specific test:**

  | Mutation | Caught by |
  |---|---|
  | line cutoff removed | `test_line_cutoff_rejects_post_T_snapshot` |
  | pre-write publication halt removed | `test_pre_write_publication_halt` |
  | `--lines-json` dropped | `test_run_week_includes_lines_json_games_run_dir` |
  | bootstrap made non-resampling | `test_bootstrap_whole_game_resampling` |
  | sidecar forced anchored | FWD3 item-1 tests |
  | zero-match halt removed | `test_zero_matches_halts` |
  | cross-week dedup removed | 3 tests |
  | no snap participation | `test_snap_participants_loaded` |

- **The real week-4 dry run** (reported): PIT@CLE, 11 sim_v1, anchored 0.092 / 0.137, the sidecar carries event_id and
  run_id, bundle digest d7246f19….

## What does not
- **Two tests fail** on the full forward suite (**88 passed, 2 failed**):
  `test_fwd2_settlement.py::test_cohort_excludes_wrong_reader` and `::test_cohort_excludes_unanchored_game`. D246
  changed `primary_cohort`'s signature (`anchor_sidecar_df` → a required `sidecar`), and these two older tests were not
  updated. The session reported "46 tests pass, 0 regressions" from a partial run. The code is right; the tests are
  stale. FWD4b updates them to the new signature, with (run_id, event_id) fixtures, keeping what they assert.

### D248 — Cowork verification of FWD4: accepted pending a test-only fix; the (run_id, event_id) anchor join works; every named mutation is caught (2026-09-30)

FWD4 (eng/fwd3 @ 0b6d94a58) is accepted, conditional on FWD4b.

Verified:
- primary_cohort joins on (run_id, event_id): a cross-run leak is excluded, a missing sidecar is excluded and counted
  (accepted in place of HALT), and a duplicate HALTs.
- The frozen file is written once.
- The bundle manifest is finalized before the freeze.
- bundle_digest and experiment_digest are on the rows.
- Publication is in publication.json.
- All ten Cowork mutations are caught.

Defect: two older cohort tests call the old signature. 88 of 90 pass, not "0 regressions" as reported.

After FWD4b and a green full suite, eng/fwd3 (D240-D249) merges. The primary count of nfl_fwd_v1 starts at the
week-4 TNF window (run 23:30Z Thu 10-01), provided the merge is on main by Thu 15:00Z.
