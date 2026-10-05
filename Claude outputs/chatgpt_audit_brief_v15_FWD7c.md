# ChatGPT audit brief #16 (v15): FWD7c (D273), for a primary Sunday week 4 (2026-10-02)

Your audit #15 of `a7bd0c62a` (NO-GO for both primary Sunday windows) is at
`~/mlb-model/research/cross_ai/chatgpt_audit15_reply_2026-10-02.md`. Cowork accepted it in **D273**
(`research/nfl_sim/NFL_SIM_DECISION_v1.md`). Read D273 in full first. Cowork then implemented **FWD7c**. Posture:
guilty until proven innocent.

**Pin: `9c7bf9dfa` on branch `eng/fwd6`** ("FWD7c Mac run: …"). Below it, in order:
- `b8a7fe211`: the refreshed week-4 tables under 2 MB, plus the ratings report that ratings.py rewrites;
- `8803102d8`: FWD7c, D273 (code, tests, D273);
- `a7bd0c62a`: the pin of your audit #15.

The code at `8803102d8` is byte-identical to the tree Cowork tested (Cowork re-checked it from GitHub). The Mac run's
full output is in `research/nfl_sim/fwd7c_mac_run.md`. Put the full SHA you audit on line 2.

**The real constraint:** the first Sunday window, IND@WAS: manual props pull at 12:15Z and harness at 12:45Z on
2026-10-04. The main + SNF harness is at 16:15Z. Nothing else is a deadline.

## How to work

1. **Create the reply file first.** Write `research/cross_ai/chatgpt_audit16_reply_2026-10-02.md` in `~/mlb-model`
   with line 1 a title, line 2 the SHA, and INCOMPLETE. Rewrite it after every check.
2. **Each command must finish in under 10 minutes.** For long jobs, use `nohup … &` and poll the logs.
3. **If a tool is blocked, say which check it blocked and move on.**

## What FWD7c claims (verify each)

1. **Your A1 (invalid cutoff).**
   - `usage._week_cutoffs` counts only valid dates. A week with none has no key, never NaT.
   - For a season with an archived schedule snapshot (2026), the cutoff is the earliest valid date among the week's
     schedule gamedays and PBP game_dates. History without a snapshot uses the earliest valid PBP date, as before.
   - `_require_cutoffs` HALTs:
     - `build_active_universe`, for every week of the newest season being built;
     - layer 3, for regular-season weeks 1-18.
     A present but incomplete snapshot no longer counts.
   - `refresh_inputs.snapshot_schedule` refuses a download missing a valid gameday for any week 1-18, and writes
     nothing.
2. **Defense in depth.** The forward gate HALTs when a team's week-W active players have no depth ranks. Cowork found
   every historical team-week (2021-2025, 572 each; 2026 weeks 1-5) has them, on the Mac's inputs.
3. **On valid inputs nothing changes.** On the Mac's staged inputs, the D273 build of both tables is byte-identical to
   the D272 build, for every season and row.
4. **A stale test, found by Cowork.**
   - 5J-2's `test_board_5j2::test_schedule_kickoff_timezone_accepts_pre_kick_qb` asserted the pre-D272 live-week QB
     rule. It is outside the forward suite and nobody ran it after D272; it would have failed.
   - It is rewritten on week 4 (no PBP when written). It passes on D273 and fails on D271.
   - The Mac run now also runs the four usage test files (`--tune` deselected, because it rewrites params_v1.json while
     running).
5. **Your seven survivors** are each killed by a test in `test_fwd7c.py`. Cowork's mutations S1-S16:
   - all killed except S4 (the schedule NaT filter);
   - S4 is argued **equivalent**: groupby-min skips NaT, and an all-NaT week gives NaT, which `_require_cutoffs`
     rejects. Challenge this.
   - The R-mutations R5, R6, R10, R13, R14, R16 and R18 are re-killed.
6. **Input version `D273-v3`.** Clean output equals D272-v2's. The roster cutoff is unchanged.
7. **Refresh wording.** Restore covers the rebuild steps (0-6) only, as you noted.
8. **`fourth_down_go_rate`.** Declared not point-in-time and not consumed, to be quarantined later. It is NOT changed
   now, because it is in the fitted window.

**Cowork's own cloud evidence**, on the Mac's earlier staged inputs (PBP weeks 1-3, i.e. the shape you used):
- the null-date week-4 row is EQUIVALENT under D273 and DIFFERENT under D272 (24.6% of target shares, 35.3% of depth
  orders);
- the forward gate for the 28 Sunday teams, with tables built from each case:
  - clean tables PASS;
  - D272 null-date tables HALT for all 28 ("no depth ranks");
  - D273 null-date tables PASS.

**Results reported.** Claude Code ran these on the Mac at about 12:20-12:35Z on Friday; Cowork re-checked the
committed record.
- **Tests:** forward 291 passed per file, 0 skipped (also 291 on Linux 3.11 and standalone 3.13.7); usage tests 22
  passed, 1 deselected. Selftest: launcher hash ok, 1090 / 6395.
- **Refresh:**
  - backup `~/mlb-model-archive/nfl_ratings_backups/20261002T122158Z`;
  - schedule snapshot 272 games, weeks 1-18;
  - **pbp_2026 now holds weeks 1-4**, because TNF PIT@CLE was played;
  - fingerprint `3638769c89030de0`;
  - archived as `D273-v3`;
  - freshness PASS for all 32 teams, exit 0.
- **Null-date checks on these inputs:** base vs plus and base vs null are EQUIVALENT for both tables, and the installed
  rows equal the rebuild. Week-4 depth is 723/800 non-null, with 0 duplicates and no null flags.
- **The D272 null-date control was ALSO EQUIVALENT, and every gate case passed.** This is expected, not a contradiction
  (the note's explanation, "a different PBP shape", is imprecise). With TNF played, week 4 has valid PBP dates, so the
  null row never leaves week 4 without a valid date. The defect needs a target week with no valid PBP date, which is
  exactly the live shape before the week's first game. **The Mac control was therefore vacuous**, and P1.2 asks you
  to rerun it on the right shape.
- **Point-in-time** for W = 2 and 3: OK in both tables.
- **Spot-check:**
  - five players equal the PBP;
  - the week-4 injury report has 291 rows: 7 Out/Doubtful, 2 of them skill players, both inactive (a real positive
    exclusion this time).
- **Runbook** matches the generator.
- **Sunday smoke run:**
  - gate PASS;
  - all 28 teams' tables at week 4;
  - 14/14 converged;
  - read set 45 files, 0 unproven;
  - 66/257 matched;
  - injury_game_statuses 0 except WAS (2), because the run was before Friday's final reports.

## P1: decides GO or NO-GO for a primary Sunday

Your audit #15 condition was: a missing date must either leave the clean result unchanged or HALT before the worker.
Then rerun the affected checks, the full baseline, and the production-command smoke.

1. **Baseline, in bounded groups.** Run each forward file separately, plus the four usage files with `--tune`
   deselected:
   `nohup sh -c 'for f in $(ls nfl/sim/tests/test_fwd*.py) nfl/sim/tests/test_forward_v1.py nfl/sim/tests/test_freeze_v1.py; do python3 -m pytest -q -p no:cacheprovider "$f" > /private/tmp/a16-$(basename $f .py).txt 2>&1; echo "$f $?" >> /private/tmp/a16-index.txt; done' > /dev/null 2>&1 &`
2. **Your A1 counterexample on the pinned code, in the shape that exercises it.** Use your audit-15 setup: the
   archived D272-v2 refresh (`…/20261002T041239Z/refreshed`, PBP weeks 1-3) or the current inputs with pbp_2026
   truncated to weeks < 4.
   - With `game_date=None`, and with an unparseable date: usage and the active universe must equal the clean build,
     or the build must HALT. The layer-3 starting-QB map must also be unchanged.
   - Repeat your real bootstrap IND@WAS dry-run comparison: either 0 probability changes, or a HALT before the worker.
   - Confirm the D272 code still reproduces your 43-change result on the same shape, so the test discriminates.
3. **Incomplete inputs.** Check each case for a HALT or an unchanged result, never a silent skip:
   - a snapshot missing week 4;
   - a null gameday for week 4;
   - a snapshot whose weeks exist but whose dates disagree with the PBP (judge the earliest-date rule);
   - an all-null-date PBP week with no snapshot (history).
   Check that the depth-rank gate HALTs any week whose active players have no ranks.
4. **Identity (Check 3).** Is the earliest-of-schedule-and-PBP cutoff identical for a live week (schedule only) and
   the same week rebuilt later (schedule + PBP)? Construct the TNF case:
   - live at week 4 before TNF, with PBP weeks 1-3;
   - then with week-4 TNF PBP present.
   The Sunday teams' week-4 rows must be identical. Extend point-in-time to W = 4 on the current inputs (PBP through
   week 3 versus through week 4).
5. **Smoke and Sunday procedure.** Check the saved smoke artifact (`nfl/data/board/week=2026_04/sim_runs/20261002T123229Z`)
   and run one independent IND@WAS bootstrap dry run on the pinned code. Confirm the runbook, quote-age arithmetic and
   refresh deadlines are unchanged from audit #15. TNF PBP now in pbp_2026 changes PIT/CLE's last-played week to 4;
   confirm nothing in the Sunday windows depends on PIT/CLE rows.

## P2: if time remains

6. Re-run your audit-15 survivors and Cowork's S1-S16 (operators at the end of D273), each isolated and re-stamped.
   Try to break the S4 equivalence argument. Look for new survivors in `_week_cutoffs`, `_require_cutoffs`, the
   depth-rank gate and `snapshot_schedule`.
7. Look for any remaining way for a bad input to reach the worker past the gate, or for a value other than the
   worker's to reach a primary frozen file. The D269 L4 native-I/O boundary is out of scope.

## Reply format

Use:
- **(A)** must-fix before a primary Sunday (ranked, file:line);
- **(B)** the P1 table;
- **(C)** P2 and any bypasses;
- **(D)** survivors;
- **(E)** GO or NO-GO for a primary Sunday at this pin, per window (IND@WAS; main + SNF).

Distinguish what you executed from what you read in the source. Write nothing else to the repository.
