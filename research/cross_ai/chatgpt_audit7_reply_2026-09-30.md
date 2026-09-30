# ChatGPT audit #7 — the reply's findings (as pasted by Jeff, 2026-09-30), for the FWD3 tests

Pin audited: `0792fd122`. Baseline: 53 passed, 2 skipped (the skips need external snap and roster data).

## (A) Must fix before Thu 15:00Z, ranked, with the executed counterexamples

1. **score-experiment** (log_ai_opinions.py:788, :876, :905).
   - An altered frozen probability was accepted even though verify() detected its hash mismatch.
   - A missing sidecar admitted the candidate row.
   - An old run marked anchored overrode the current run marked unanchored.
   - An unregistered experiment argument was accepted.
   - The documented CLI command fails the package import. Module invocation stops on the week-2 directory (78 rows,
     all pilots) and never reaches later weeks.
   - Its report issued "inferior" on one leg from one game.
2. **The bundle** (run_forward_v1.py:105, :207, :553; run_week.py:975).
   - It hashes only events, props, lines and freshness. It does not preserve the ratings, usage, active universe or
     roster inputs. The sidecar is not hashed. picks and anchoring logs go to a shared, overwritable weekly directory.
   - Rebuilding the same run_id succeeded and replaced the quote bundle. The frozen opinion kept −110 while the
     replacement bundle had −120.
3. **Grading identity** (FWD_EXPERIMENT_v1.json:6; log_ai_opinions.py:427).
   - nfl/sim/actuals.py is not hashed. Changing its reception aggregation (counting pass rows, so incomplete targets
     count as receptions) survived the whole suite, 53 passed / 2 skipped, with no manifest change.
   - The manifest describes the seed as `stable_seed((game_id, 42))`, but anchor.py:175 uses
     `(home, away, season, week, 42)`.
4. **Exact event and participation** (log_ai_opinions.py:424, :531, :548).
   - A week-4 opinion was settled from a completed week-3 game with the same home/away pairing.
   - With a valid GSIS→PFR mapping the Under settled. With the crosswalk removed it became VOID, even though the
     player was present in the snap counts.
5. **Anchor iteration** (run_forward_v1.py:413). With controlled simulation batches the real solver returned
   iteration 2, converged, −0.7 / 39.3 against targets 0 / 40. The sidecar chose iteration 1 (−1.1 / 40) and
   classified the game unanchored.
6. **Freshness and publication** (run_forward_v1.py:170, :614, :638).
   - A live fixture froze with fresh props and five-day-old game lines.
   - With a controlled clock the pre-write check ran at kick−1 s and publication was recorded at kick+1 s; the
     freeze succeeded.

## (B) A1-A7 at 0792fd122
A4 is FIXED for the original counterexamples. A1, A2, A3, A5, A6 and A7 are PARTIAL.
- A5: a same-pair game from an old season or week still matched once.
- A5: the props loader returned 958 PIT@CLE rows, from nine books and two pulls.

## (C) Other scoring problems
- Two event_ids with the same team pair were clustered as one game.
- The experiment argument is never checked.
- Directory traversal is not limited to the requested season.
- An empty or pilot-only week aborts the report.
- There is no checkpoint policy.

## (D) Mutations that survived, one per test file
| Test file | Mutation that survived |
|---|---|
| test_fwd2_anchor.py | every sidecar row forced to anchored=True |
| test_fwd2_bundle.py | the game-line cutoff condition removed ("creates manifest" checks a signature; "filters lines" asserts nothing) |
| test_fwd2_experiment.py | actuals.py counts incomplete targets as receptions (no restamp needed) |
| test_fwd2_item0_fixes.py | the zero-match halt removed from main() (the harness file does catch this) |
| test_fwd2_settlement.py | the whole-game bootstrap replaced by independent-leg sampling |
| test_fwd2b_harness.py | the publication-time halt removed (the past-kick fixture exits earlier, during event selection) |
| test_forward_v1.py | duplicate-pick rejection removed |
| test_freeze_v1.py | a historical target-share value changed (the harness catches it separately) |

Two more whole-suite survivors:
- the bundle line/game arguments removed from the real subprocess call;
- score() made to find no snap participation for any game.

## (E) Verdict
Not with 0792fd122. Implement the six repairs, stamp the manifest once, and re-run the counterexamples on the final
commit, with acceptance through the real entry points. Otherwise Thursday's output is diagnostic/pilot data and the
primary count stays at 0.
