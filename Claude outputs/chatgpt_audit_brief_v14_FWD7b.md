# ChatGPT audit brief #15 (v14): FWD7b (D272), for a primary Sunday week 4 (2026-10-02)

Your audit #14 of `7429e9dbf` (NO-GO for a primary Sunday) is at
`~/mlb-model/research/cross_ai/chatgpt_audit14_reply_2026-10-02.md`. Cowork accepted all of it in **D272**
(`research/nfl_sim/NFL_SIM_DECISION_v1.md`, read D272 in full first) and implemented **FWD7b**. Posture: guilty until
proven innocent.

**Pin: the HEAD of branch `eng/fwd6` whose message starts "FWD7b Mac run".** Below it, in order:
- "Refreshed week-4 inputs with the D272 builders": the refreshed tables under 2 MB;
- "FWD7b (D272)": the code, tests, D272, the regenerated runbook;
- `7429e9dbf`: the pin of your audit #14.

The FWD7b code is byte-identical to the tree Cowork tested (the patch applied on `7429e9dbf` gives the same files).
The Mac run's full output is in `research/nfl_sim/fwd7b_mac_run.md`. Put the full SHA you audit on line 2.

**The real constraint:** the first Sunday window: IND@WAS, manual props pull at 12:15Z and harness at 12:45Z on
2026-10-04. The main slate + SNF window has its harness at 16:15Z. Nothing else is a deadline.

## How to work

1. **Create the reply file first.** Write `research/cross_ai/chatgpt_audit15_reply_2026-10-02.md` in `~/mlb-model`
   with line 1 a title, line 2 the SHA, and INCOMPLETE. Rewrite it after every check.
2. **Each command must finish in under 10 minutes.** For long jobs, use `nohup … &` and poll the logs.
3. **If a tool is blocked, say which check it blocked and move on.**

## What FWD7b claims (verify each)

1. **Your A1.**
   - `usage._week_cutoffs` gives one information cutoff for every week, live or historical: midnight UTC of the
     week's first game date. It comes from PBP when the week has plays, else from the archived schedule snapshot
     `nfl/data/pbp/schedules_2026.parquet`.
   - The depth layer (`build_active_universe`) and the layer-3 QB assignment both use it.
   - The live nflverse schedule fetch inside `usage.py` is gone. `usage.py` HALTs if a week lacks PBP and there is no
     snapshot.
   - `refresh_inputs.py` writes the snapshot once per refresh, before `usage.py`, and archives it.
2. **Point-in-time identity (new, Check 3).** Build usage and the active universe as if live at week W: pbp_2026
   truncated to weeks < W, everything else equal. Then compare the week-W rows with a build on the full PBP, which is
   the row a backtest consumes.
   - Cowork measured, on the Mac's inputs: D272 is IDENTICAL for W = 2 and W = 3.
   - The D271 builder (negative control) differs on 100% of week-3 target shares and 91% of depth orders.
   - The Mac run repeats this on the refreshed inputs (`pit.py`). Note what it implies: every pilot before D272 ran on
     live rows constructed differently from their backtest counterparts.
3. **Your A2.** The forward gate HALTs on:
   - any duplicate `(season, week, team, player_id)` in the week-W active universe;
   - non-boolean active flags;
   - null active flags, including a nullable-boolean `<NA>`.
4. **Your A3 and the declarations.**
   - `make_runbook.py` splits Sunday games before 16:30Z into their own window. It uses per-weekday VM slots, so there
     is no Monday 22:00Z slot, and MNF gets a manual pull.
   - Every command uses the bootstrap and `refresh_inputs.py`.
   - `research/nfl_sim/fwd1_runbook.md` is regenerated, and the Mac run diffs it against the generator.
   - D272 declares input version **`D272-v2`**: every refresh archives its source and table bytes with
     `refresh_manifest.json`.
   - D272 also declares the **roster cutoff**: each window freezes on its last refresh. Game-day inactives after that
     are not applied, and this is a declared difference from the backtest's final rosters.
5. **Corrections to D271**, as you found:
   - QB ratings are not consumed;
   - the full-rebuild fingerprint `a59adeafe48f62e6` was measured on the older inputs.
6. **Smaller items:**
   - `dependency_drift` requires all three runtime keys and three baseline runtimes;
   - the baseline is selected by `dependency_fields`, which takes the first primary in the registry;
   - the refresh's exit 1 means "refreshed and INSTALLED, some teams not ready". This is documented and tested.
7. **Tests and mutations.**
   - 280 tests: per file on the Mac, and on Linux 3.11 and standalone 3.13.7.
   - Your eight audit-#14 survivors are claimed killed.
   - Cowork's FWD7b mutations R1-R18 are 18/18 killed. The operators are listed at the end of D272.

## P1: decides GO or NO-GO for a primary Sunday

Your audit #14 GO conditions were: the repaired pin rejects the duplicate fixture, preserves depth/usage under the
truncated-PBP equivalence check, passes its baseline, and passes a production-command smoke run with actual fresh
inputs.

1. **Baseline, in bounded groups.** Run each forward test file separately in the background with per-file logs:
   `nohup sh -c 'for f in $(ls nfl/sim/tests/test_fwd*.py) nfl/sim/tests/test_forward_v1.py nfl/sim/tests/test_freeze_v1.py; do python3 -m pytest -q -p no:cacheprovider "$f" > /private/tmp/a15-$(basename $f .py).txt 2>&1; echo "$f $?" >> /private/tmp/a15-index.txt; done' > /dev/null 2>&1 &`
   Report every file's final line and exit code, then the totals.
2. **A2 on real inputs.** Re-run your audit-#14 duplicate counterexample against the refreshed week-4 bundle inputs,
   with the duplicate active row both before and after the inactive one. Also try a nullable-boolean `<NA>` and an
   object column. Use an OUT/Doubtful skill player if the week-4 report has one; otherwise use a synthetic one, and
   say which. The gate must HALT on each. Then confirm that the engine's context builder and the gate see the same
   single row.
3. **A1 on real inputs, independently.**
   - Repeat your date-only week-4 PBP experiment with your own code. Usage and the active universe must be
     identical, and the week-4 depth ranks non-null.
   - Repeat the point-in-time check for W = 2, 3 and, if you can, extend it to the layer-3 QB table
     (`derive_starting_qbs`).
   - Confirm that the D271 negative controls differ.
   - Look for any remaining builder path whose live-week construction differs from the historical one: team ratings,
     tendencies, situational tendencies, kickers, league baselines (Check 1b and Check 3).
4. **The smoke run.** From the saved artifact of the Mac's Sunday dry run, check that:
   - every Sunday team's tables are at week 4;
   - `active_universe_current` holds;
   - the read set is all proven;
   - the converged count is correct;
   - the bundle's active universe has non-null week-4 depth.
   Re-run one game through the bootstrap if time allows.
5. **Sunday's procedure.** Check that the committed runbook's week-4 windows match the schedule. For each window,
   give the quote-age arithmetic and the refresh timing.
   - Judge whether the declared roster cutoff (D272 ii) is acceptable for a PRIMARY, or whether the main window must
     move after the inactives (about 90 min before each kick).
   - Judge whether input version `D272-v2` (D272 i) is acceptable.
   - Confirm that both declarations were committed before any week-4 Sunday outcome.

## P2: if time remains

6. Re-run your eight audit-#14 survivors and Cowork's R1-R18, each isolated and re-stamped. Look for new survivors
   in `_week_cutoffs`, the layer-3 block, `_active_universe_matches`, `dependency_fields`, `archive_refresh`/
   `snapshot_schedule` and `make_runbook.group_windows`.
7. Look for any remaining way for a value other than the worker's to reach a primary frozen file, or for a bad input
   to reach the worker past the gate. The D269 L4 boundary for native I/O in RECORD-matched dependencies is out of
   scope.

## Reply format

Use:
- **(A)** must-fix before a primary Sunday (ranked, file:line);
- **(B)** the P1 table;
- **(C)** P2 and any bypasses;
- **(D)** survivors;
- **(E)** GO or NO-GO for a primary Sunday at this pin, per window (IND@WAS; main + SNF).

Distinguish what you executed from what you read in the source. Write nothing else to the repository.
