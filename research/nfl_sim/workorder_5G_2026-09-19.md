# Phase 5G work order — three engine defects, one re-fit

Date: 2026-09-19
Repo: jwallace115/mlb-model, branch main
Scope: nfl/ only. Do not touch ncaaf/ or any MLB path.

## Verified baseline (Cowork, 2026-09-19 ~18:30Z, origin c3060d9)

Full suite re-run on a clean clone with the gitignored PBP files staged in:
187 collected — 183 passed, 3 failed, 1 not run.

The three failures, with the values they failed at:

- `test_engine_5a3.py::test_t1_4th_down_go_rate` — 0.210 vs 0.198 (diff 0.0123 > 0.010)
- `test_engine_5a4.py::test_penalties_per_side` — 6.20 vs 5.51 (diff 0.687 > 0.5)
- `test_engine_5a9.py::test_t3_tied_drives_that_reach_range_get_the_kick_off` — 0.111 > 0.050

Not run in that baseline: `test_5c1.py::test_crps_closed_form` (it needed
~6.4 GB). D92 has since replaced the n x n matrix in `_crps_sample` with the
sorted-sample identity and added `test_crps_sorted_identity`; both pass. So
expect 188 collected: 185 passed, 3 failed. D92 is already taken — this work
order's entries stay D88-D91. Do not touch `_crps_sample` here.

Any red other than those three at the start of item 1 is new. Stop and
report it before changing anything.

## Standing contract (from CLAUDE.md WORK ORDERS)

- 4 items. Commit AND push each item before starting the next.
- Any item that makes a decision writes its `### DNN` entry into
  `research/nfl_sim/NFL_SIM_DECISION_v1.md` **in that same commit**.
- **A diff is not evidence that code runs.** For any claim of the form
  "X is now fixed / wired / enforced", the evidence is an execution
  trace, not a diff and not a return value.
- Prefix EVERY git command with `GIT_OPTIONAL_LOCKS=0`.
- Push with `git pull --rebase --autostash && git push`.

## RUNTIME POLICY

No speed-driven changes. Never reduce N, subsample, shorten a sweep, skip
a test or kill a run to finish sooner. Vectorisation that gives identical
results is the only allowed speed-up. Do not budget or narrate how long
your own session will take.

## HARD PROHIBITION FOR THIS PHASE

The three failing assertions are targets derived from real play-by-play
by `nfl/sim/tests/derive_engine_targets.py`. D86 re-derived all three
and confirmed them:

- 4th-down go rate 0.198 from 3,085/15,579
- offense penalties/game 5.513 from 5,993/1,087
- tied drives expiring 0.000 from 0/329

**You may not change a target, a tolerance, a spec threshold, or a
test's sample filter to make a test pass.** If you believe a target is
wrong, stop and write the case in the decision doc; do not edit it.
The fix is an engine change. A widened tolerance is a deleted signal.

## SEQUENCING — read before starting

Items 1-3 change the engine. Changing the engine changes
`engine_fingerprint()` (it hashes engine.py, anchor.py, params_v1.json,
and every file in nfl/data/sim/tables/), which invalidates the existing
calibration `fit_5d2`. **Do NOT re-fit after each item.** Items 1-3 fix
the engine; item 4 does the single re-fit, re-stamp and K4 re-run.

Between item 1 and item 4 the board is expected to be UNRANKABLE. That
is the correct behaviour and item 1 must demonstrate it.

---

## Item 1 — 4th-down go rate (test_engine_5a3.py:67)

Target 0.198. Sim 0.210. Spec |delta| < 0.010. Current delta +0.012.

D86 traced the excess to table granularity: the 5A-2 diagnostic showed
the go/no-go decision table's cells are too coarse, so situations that
should split across a decision boundary all resolve to "go". D23 (GOE
fix, 5A-3) and D30 (table rebuild, 5A-9) took this from 23.2% to ~21%;
the residual 1.2pp is what coarse cells leave behind.

Do:
- Read the 5A-2 diagnostic output and identify which cells carry the
  excess. Report the per-cell contribution to the +1.2pp before
  changing anything.
- Fix by finer table cells OR a supplementary correction term.
  State which you chose and why in the decision entry.
- Rebuild the table from PBP point-in-time. Do not hand-tune a constant
  to hit 0.198 — that is fitting the test.

Evidence required:
- Execution trace: run the sim, print the realised go rate and the
  per-cell breakdown, paste the output.
- The delta must be under spec on the FULL sample, not a subset.
- **Then run the board and paste the output showing it refuses to rank**
  because the engine fingerprint no longer matches `fit_5d2`'s stamp.
  If the board still ranks, STOP — the gate is decorative and that is a
  bigger finding than this item. Write it up as its own DNN.

Decision entry: D88.

---

## Item 2 — offense penalties per game (test_engine_5a4.py:75)

Target 5.513. Sim 6.20. Spec |delta| < 0.5. Current delta +0.69 (+12.5%).

D86: the `penalty_detail` table drives penalty generation; either the
rate or the game-context conditioning is too aggressive.

Do:
- Break the 6.20 down by penalty type and by game context before
  changing anything. Paste that breakdown. The excess is unlikely to be
  uniform — find where it concentrates.
- Audit the penalty rate table against PBP: is the rate itself wrong, or
  is the draw frequency wrong (the table is right but it is consulted
  too often)? These are different bugs. Say which.
- Fix the one that is actually wrong.

Evidence required:
- Execution trace with the per-type breakdown before and after.
- Confirm defensive penalties did not move as a side effect — if the
  fix moved both, you changed a shared path and need to say so.

Decision entry: D89.

---

## Item 3 — tied drives expiring (test_engine_5a9.py:143)

Target 0.000 (0 of 329 real tied drives expired). Sim 0.111.
Tolerance <= 0.050.

D86 gives two candidate causes:
  (a) the clock advances past the kick window despite the kneel table
  (b) the FG-setup state does not trigger for all qualifying situations

D33 (5A-9) introduced the FG-setup state and cut this from ~14%.

Do:
- **Instrument the FG-setup state activation.** For every tied drive
  that expires, log: did FG-setup activate? at what clock/field
  position? what was the last play type? This separates (a) from (b).
  Paste the instrumentation output.
- Do not guess. Fix the cause the instrumentation names.
- Note: real football has 0/329 here because coaches never let a tied
  drive expire in field goal range. Any residual above ~1% means the
  engine still has a decision path a real coach does not have.

Evidence required:
- Instrumentation output identifying (a) or (b).
- Execution trace post-fix showing the expiry rate.
- The count of tied drives in the sim sample, so we can see the rate
  is not being computed off a handful of drives.

Decision entry: D90.

---

## Item 4 — single re-fit, re-stamp, K4 re-run

Only after items 1-3 are all committed and pushed and all three tests
are green in the same run.

Do:
1. Run the full suite. Paste the complete output. Every engine test
   must be green simultaneously — item 3's fix must not have broken
   item 1's.
2. Run `nfl/sim/run_fit.py`. Confirm it writes `fit_meta.json` with the
   NEW `engine_fingerprint`, the `fit_inputs_fingerprint`,
   `fit_seasons`, `engine_commit` and `n_games`. Paste the file.
3. Re-stamp via `save_calibration(..., fit_dir=...)`. It must read the
   fingerprints from `fit_meta.json`, not compute them live. Confirm
   from the trace that it did.
4. Run the board. Confirm it now ranks — the stamp matches again.
   Paste the trace showing `sim_pricing_enabled` true and the gate
   passing for the right reason.
5. Re-run K4 (real closing-price ROI). Paste the output.

**Do not interpret the K4 result as validation.** Report the number.
The calibration-transfer question is not settled by one K4 run and this
work order does not settle it.

Decision entry: D91, recording the new fingerprints and the K4 number
as a measurement, not a finding.

---

## What this work order does NOT do

- It does not close the calibration transfer red. Totals currently get
  WORSE under calibration (Brier 0.24190 -> 0.24560). That is the gate
  on whether the sim ever prices a ticket and it needs prospective,
  family-level evidence over weeks. A green suite is not evidence for it.
- It does not prove the props cron fires on schedule. That needs the
  Tuesday 10:00 UTC slot to arrive with nobody triggering it.
- D61 remains not directly tested.
