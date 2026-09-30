# Cowork verification of FWD4b, and a merge blocker found on main (2026-09-30, 16:41Z)

Branch `eng/fwd3` @ `ffc3e67dc` (5e2db479b D248 verbatim; ffc3e67dc D249). Cowork re-ran everything below on a clean
checkout on Linux.

## FWD4b — accepted

- **Diff** (65098f910 → ffc3e67dc): only `nfl/sim/tests/test_fwd2_settlement.py` and `NFL_SIM_DECISION_v1.md` changed.
  No production file changed. D248 and D249 are both in the decision doc.
- **The two tests**, read by Cowork:
  - The wrong-reader test gives the row a matching anchored sidecar row, so only the reader filter can exclude it. It
    asserts the "reader != canonical" reason.
  - The unanchored test puts run_B anchored=True first and run_A anchored=False second, for the same event_id.
- **Suite**: the full forward list (13 files) gives **88 passed, 0 failed**. Reproduced.
- **Cowork's own mutations** on `primary_cohort`:
  - Joining on event_id only, with the duplicate check disabled, fails:
    - `test_cohort_excludes_unanchored_game`;
    - `test_run_b_unanchored_excluded`;
    - `test_duplicate_sidecar_halts`;
    - plus the manifest-hash test.
  - Removing the reader filter fails `test_cohort_excludes_wrong_reader` (plus the hash test).
  - Both mutations reverted; the tree is clean.

**Cowork's error: the 92.** Cowork's order expected 92 tests; the 13 files define 88. At the parent 65098f910 the run
gives **86 passed, 2 failed** (reproduced), so D248's "88 passed, 2 failed" overstated the passes by 2. Claude Code's
88 is right.

## Merge blocker: main has changed the experiment's hashed logger

A trial merge of `ffc3e67dc` into `origin/main` @ `70fa1d44f` was done in a scratch checkout; nothing was pushed.

**Textual conflicts:** only `logs/_log_fwd1_cowork.txt` and `shared/last_updated.json`.

**The real problem: `nfl/pipeline/log_ai_opinions.py`.**
- It is experiment-hashed (`FWD_EXPERIMENT_v1.json:20`, `cf100675bd385ca5`), and it holds `freeze()`, `verify()`,
  `score()`, `primary_cohort()` and `score_experiment()`.
- Since the merge base 82c38aef8, the NHL layers sessions have changed it by +558/−67 on main, in four commits:
  - 1075895bb H3;
  - c609718d3 H4;
  - 8d37ad49f H4b;
  - 4bb1cf17f H5.
- The changes touch `set_sport`, `build_sheet`, `prior_revisions`, `freeze`, `verify`, `score`, `score_report` and
  `main()`.
- Git auto-merges the file (sha `bf8eec3453fe` on main alone). The merged file is new code that no FWD verification,
  audit or mutation run has seen.

**On the merged tree the forward list gives 84 passed, 4 failed:**
- `test_experiment_file_hashes` (the hash check working as designed; the harness would HALT);
- `test_cross_week_dedup_freeze_different_week`, `test_cross_week_dedup_freeze_same_week` and
  `test_whitespace_reader_refused_by_freeze`.
  - For the three freeze tests, the HALT still fires, but the message changed from "cross-week dedup" to
    "cross-dedup" (`log_ai_opinions.py:384` on main).

**Why re-stamping is not enough.**
- Re-stamping after the merge would make the NFL experiment's scoring code depend on NHL development.
- Any later NHL edit to the shared file would change the hash, and every later NFL window would HALT. That is
  fail-safe, but it loses windows.
- The alternative, a merged file that nobody audited, fails CHECK 3: the object that was tested would not be the
  object that runs.

### D250 — FWD4b accepted; merging eng/fwd3 is blocked until the experiment's logger is decoupled from the shared NHL/NFL logger (2026-09-30)

FWD4b is accepted:
- test-only;
- 88 passed, 0 failed, reproduced;
- the run_id and reader mutations are caught.

Cowork's "92" expectation and D248's "88 passed, 2 failed" were wrong. The parent was 86 passed, 2 failed.

eng/fwd3 is NOT merged as-is. Main's NHL work (H3-H5) changed the experiment-hashed `nfl/pipeline/log_ai_opinions.py`
by +558/−67. A merge would put unaudited code into the experiment's freeze and scoring path. It fails the hash test and
three freeze-message tests.

FWD5 pins the experiment's logger instead:
- `nfl/sim/fwd_v1_logger.py` becomes a byte-identical copy of the verified eng/fwd3 version (sha256 cf100675bd385ca5);
- the harness and the forward tests import it;
- the manifest hashes it in place of the shared file, which returns to the NHL/NFL-AI sessions unhashed.

The TNF gate is unchanged: FWD5 must be verified and merged by Thu 10-01 15:00Z, or TNF runs `--pilot`.
