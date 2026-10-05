# FWD2b verification — Cowork, 2026-09-30 (09:40Z)

Branch `eng/fwd2` @ `3beed7970` (D228 append; D229-D232). Read from the committed code, in a clean worktree on Linux.
49 tests pass here and none reads source text.
**Verdict: much closer, but not merged.** A live (non-pilot) run has still never executed, in a test or on real data.
The runbook has wrong dates, a wrong London game and a command that does not exist. Settlement still scores missing
data. FWD2c is a short fix order; the Thu 20:00Z gate still holds.

## What stands
- **D229 — the harness runs in-process on the bundle.**
  - `main(argv, root, run_week_fn)`.
  - `build_sheet` and `freeze` are called in-process from the bundle.
  - Prices and source_utc are validated against the bundle sheet.
  - run_week takes `--lines-json` / `--games` and skips the tape.
  - Freshness HALTs.
  - There are 7 execution tests through `main()` on a fixture root.
- **D230.** Participation is from nflreadpy snap counts. Frozen rows carry run_id. The `score-experiment` CLI exists.
- **D231.**
  - The **week-3 pilot freeze completed** on real data: 14 games, 162 matched (130 receptions + 32 rush attempts), 0
    unanchored.
  - The input builders are measured: `pull_nflverse_inputs.py` takes 6 s and `ratings.py` about 8 min.
  - Ratings are now at week 3, which is fresh for week 4.
- **D232.** FWD_EXPERIMENT_v1.json is re-stamped.

## What does not
1. **Live mode has never run.** `test_live_freeze_completes` (test_fwd2b_harness.py:190) passes `--pilot --as-of`, so it
   is a pilot test with a live name. The real week-4 dry run stopped at the quote-age check (24.5 h). No code path
   after the bundle has ever executed in live mode.
2. **The runbook facts are wrong.**
   - The Sunday dates are given as 10-05 instead of **Sun 10-04**.
   - The London game is given as "JAX@IND" instead of **IND@WAS, 13:30Z Sun 10-04** (line tape).
   - MNF is given as "Tue 10-07" instead of **Tue 10-06 00:15Z**.
   - Week-5 TNF is given as "Fri 10-10" instead of **Fri 10-09 00:15Z**.
   - The London pull command calls `nfl/pipeline/pull_odds.py`, **which does not exist**. The real puller is
     `nfl/pipeline/pull_hardrock_props.py --window-hours 2 --tag close --out-dir <manual dir>`, which writes
     `scratch_<ts>.parquet`.
   - The commands run from `/tmp/eng-fwd2` instead of `~/mlb-model` after the merge.
   - Every window refreshes ratings (8 min), even though a refresh once a week keeps W−1 fresh.
3. **`ratings.py` overwrites `params_v1.json`**, a FREEZE_v1 file, on every run (ratings.py:936-938). The runbook's
   answer is "git checkout after". One forgotten restore makes the harness HALT at the freeze test, which is safe, but
   it is an operational trap on a live Sunday.
4. **Settlement:**
   - With no snap data (`snap_played=None`) the stat is still scored, falling back to 0, so an inactive player's
     Under is again "settled". The order said unresolved.
   - Participation is matched by an exact Hard Rock name against the PFR name, so suffixes and punctuation give false
     VOIDs.
   - There is still no completed-game check.
   - The week-3 re-grade graded **0 of 2,070** rows, and even game lines (no snaps needed) did not grade. Yet the FWD1b
     pilot graded week 3 from the same PBP. That is a regression, not a "data lag".
   - `--file` diagnostic scoring still excludes pilot rows, so no Δ was ever produced on real data.

### D233 — Cowork verification of FWD2b: bundle harness accepted; live mode never executed, runbook facts wrong, settlement still scores missing data (2026-09-30)

FWD2b (eng/fwd2 @ 3beed7970) is not merged.

What stands:
- the in-process bundle harness, with price validation, freshness HALTs and event-restricted run_week;
- execution tests through main();
- snap-count participation, run_id and score-experiment;
- a completed real week-3 pilot freeze (14 games, 162 matched, 0 unanchored);
- measured builder runtimes (6 s / 8 min).

Defects:
- The "live" test runs --pilot, and no live run has executed.
- Runbook dates, the London game and the pull command are wrong.
- ratings.py overwrites params_v1.json.
- Settlement scores stats when snap data is missing.
- Participation is matched by name.
- There is no completed-game check.
- The week-3 re-grade graded 0 rows, a regression from FWD1b.
- The pilot diagnostic never produced a Δ.

Next: FWD2c. The TNF gate is Thu 20:00Z.
