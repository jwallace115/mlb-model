# ChatGPT audit #7 — adjudication by Cowork (2026-09-30, 13:10Z)

The audit was run on `main` @ `0792fd122` (brief v6). Cowork spot-checked the auditor's findings against the code
before accepting them. **Every item checked holds.**

Checked in run_forward_v1.py:
- the bundle directory is created with `mkdir(..., exist_ok=True)`, so a run can be rebuilt over an old one (:108);
- the sidecar picks the minimum-error iteration from the log (:413), not the solver's returned one;
- the quote-age check applies to props only (:170-178);
- publication is checked BEFORE `freeze()` and then recorded AFTER it, with a new `datetime.now()` (:614-642);
- a weekly `anchor_sidecar_sim_v1.parquet` is overwritten by every run.

Checked elsewhere:
- `nfl/sim/actuals.py` is not in FWD_EXPERIMENT_v1.json (0 matches);
- the run_id join in `score_experiment` is `pass` (Cowork had flagged this in the brief).

The auditor's executed counterexamples (grading a same-pair game from week 3, a crosswalk miss becoming VOID, a
replaced bundle, an altered frozen file accepted, one leg producing "inferior") are accepted as evidence. Cowork did not
re-run them.

**D238 was wrong to accept A1-A7.** At 0792fd122:
- A4 is FIXED;
- A1, A2, A3, A5, A6 and A7 are PARTIAL.

The auditor also confirmed the numbers that can be reproduced from the pin:
- the week-4 anchor, −2.408 / 38.137 in 3 iterations;
- the sheet, 70 lines / 43 two-way;
- 53 passed and 2 skipped (they need external data).

It could not reproduce the re-grade or the new pilot, because those artifacts are not committed.

## Decision

**Freeze-side and scoring-side are separated.**

- **Freeze-side defects make a frozen record untrustworthy for good.** These are: a replaceable bundle, prediction
  inputs not preserved, the wrong anchor iteration, stale anchoring lines, and publication after the kick. They must be
  fixed **before the first primary freeze**.
- **Scoring-side defects are implementation bugs against rules that were already pre-registered.** These are: the
  experiment and hash check, the run_id + event_id anchor join, exact-event grading, a crosswalk miss treated as
  unresolved, the event_id cluster key, the checkpoint policy, and hashing actuals.py. They must be fixed before **any
  outcome is scored**; nothing has been scored yet.

FWD3 does both before the first primary freeze, so that the experiment manifest is stamped once.

**Start window.** The primary count starts at the first window after FWD3 is verified:
- if Cowork verifies FWD3 before Thu 10-01 15:00Z, that window is TNF;
- otherwise TNF runs `--pilot` and the count starts at the London / Sunday windows (after FWD2d);
- failing that, week 5.

v1's physics (FREEZE_v1) are unchanged throughout.

### D240 — ChatGPT audit #7 adjudicated: D238's acceptance of A1-A7 was wrong; FWD3 fixes the freeze-side and scoring-side defects before the first primary freeze (2026-09-30)

At 0792fd122, A4 is FIXED, and A1, A2, A3, A5, A6 and A7 are PARTIAL.

Confirmed defects:
- `score_experiment` accepts an altered frozen file and an unregistered experiment name, has a no-op run_id join, lets
  another run's anchor status leak in, aborts on pilot-only weeks, and gives a verdict on one leg;
- the bundle can be replaced, does not preserve the ratings, usage or roster inputs, and leaves the sidecar unhashed;
- run_week writes to a shared weekly directory;
- actuals.py, which grading uses, is not hashed;
- grading selects games by team pair;
- a crosswalk miss becomes VOID;
- the sidecar picks the minimum-error iteration instead of the solver's returned one;
- game-line freshness is not checked;
- the publication check runs before the write.

Tests: eight mutations survived, one per test file.

Cowork's D238 acceptance is withdrawn.

Freeze-side defects must be fixed before the first primary freeze, and scoring-side defects before the first scoring.
FWD3 does both. The primary count starts at the first window after FWD3 is verified: TNF only if that is by
Thu 15:00Z, otherwise Sunday or week 5.
