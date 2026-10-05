# FWD3 verification — Cowork, 2026-09-30 (15:10Z)

Branch `eng/fwd3` @ `735374bf1` (D240 append; D241-D244). Read from the committed code, in a clean worktree on Linux.
**79 tests pass here.** Cowork also re-ran audit #7's surviving mutations and counterexamples against this code.
**Verdict: the freeze side is accepted; the scoring side is not. Not merged yet. FWD4 (small) continues on eng/fwd3.**

## What stands
- **D241.**
  - A run directory cannot be reused. A real re-run was refused, and a test covers it.
  - The prediction inputs are copied into the run directory and hashed. Three inputs are over 2 MB and not committed.
  - Outputs are written only under the run directory.
  - Stale game lines HALT.
  - The sidecar lives in the run directory.
  - A write that completes after the kick is quarantined.
  - verify detects a tampered run file.
- **D242.** The sidecar reads the solver's returned state (`anchor_returned.parquet`). The auditor's controlled-batch
  counterexample is now a test and passes.
- **D243, partly:**
  - an unregistered experiment name HALTs;
  - a same-pair game from another week is unresolved;
  - a crosswalk miss is unresolved, not VOID;
  - one leg gives no verdict;
  - the bootstrap key is event_id;
  - actuals.py is hashed;
  - the seed description is fixed;
  - the CLI imports.
- **Real runs:**
  - the week-4 live dry run completed (23 files hashed);
  - a week-3 pilot froze, and the same run_id was refused;
  - `score-experiment` skipped the pilot-only weeks and gave "0 eligible — no verdict".
- **Mutations now caught:**
  - sidecar forced to anchored;
  - zero-match halt removed;
  - cross-week dedup removed;
  - cohort forced to all-anchored;
  - no snap participation.

## What does not
1. **The anchor join by (run_id, event_id) is still not implemented.** `primary_cohort` (log_ai_opinions.py:775-784)
   still builds a set of anchored **game names** from every sidecar pooled across runs, and skips the check entirely
   when there is no sidecar. D243(b) claims otherwise. Cowork ran both audit counterexamples on this code:
   - run A anchored and run B unanchored, scoring a run-B row: the row **stays in the cohort**;
   - an empty sidecar: the row **stays in the cohort**.
   `score_experiment` does not HALT on a missing sidecar either.
2. **Mutations that still survive the whole 79-test suite** (Cowork applied each, re-stamped the temporary manifest,
   and ran the suite):

   | Mutation | Why no test catches it |
   |---|---|
   | The game-line snapshot cutoff removed (`if snap_utc <= T` → `if True`) | No test checks it. |
   | The pre-write publication halt removed | `test_publication_past_kick_halts_live` exits at event selection first — the same flaw audit #7 named. |
   | `--lines-json`/`--games` dropped from the real run_week call | The harness tests stub run_week. |
   | The bootstrap made non-resampling | No test checks the interval. |

3. **The record is rewritten after the freeze.**
   - The harness re-writes the frozen parquet to add `publication_utc`, and re-hashes the manifest entry
     (run_forward_v1.py:~766-776).
   - It rewrites `bundle_manifest.json` after the freeze with an `experiment_digest`, and with a "bundle_digest" that is
     the hash of the manifest's previous version.
   - No digest is carried on the frozen rows, contrary to D241(f).
   The member files do not change, so this is hygiene rather than a wrong record. It is still not what was ordered.
4. **The committed week-3 pilot numbers:** 162 of 625 matched, 357 lines frozen, 57 settled legs from 5 games. With
   as-of 17:00Z, the 1 pm games had already kicked, so the pilot differs from the order's 16:30Z; the 16:30Z run
   directory was a stale partial run. Δ = +0.0118 (CI −0.019 to +0.051). This is a pilot and not evidence.

### D245 — Cowork verification of FWD3: freeze side accepted; the scoring anchor join is still unimplemented; four surviving mutations; not merged (2026-09-30)

FWD3 (eng/fwd3 @ 735374bf1) is not merged.

Accepted, freeze side:
- the run directory cannot be reused;
- inputs are copied and hashed into it, and outputs are confined to it;
- stale lines HALT;
- a write after the kick is quarantined;
- the sidecar reads the solver's returned state.

Accepted, scoring side:
- an unregistered experiment HALTs;
- grading uses the exact event;
- a crosswalk miss is unresolved;
- the checkpoint policy applies;
- actuals.py is hashed.

Not accepted:
- primary_cohort still pools anchored game names across runs and skips the check when no sidecar exists. Both audit
  counterexamples still pass, reproduced by Cowork.
- Four mutations survive the 79 tests: the line cutoff, the pre-write publication halt, the run_week --lines-json
  call, and bootstrap resampling.
- The frozen file and bundle manifest are rewritten after the freeze, and no digest is on the rows.

Next: FWD4. TNF is primary only if FWD4 is verified by Thu 15:00Z.
