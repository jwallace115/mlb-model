# ChatGPT audit brief #10 (v9) — audit of FWD6b, Cowork's fix for your audit #9 (2026-10-01)

This is a read-only audit and a follow-up to your audit #9 on `e826a30ae`. Cowork implemented the fix itself, so you are
again the only independent check between this code and Thursday's live freeze. Posture: guilty until proven innocent.
Cowork's acceptance notes have been wrong four times (D238, D245, D254, D259's "131 passed").

**Your audit #9 reply was not saved verbatim** (it exists only in Jeff's chat). D260-D262 restate every item from it. If
your restatement differs from what you wrote, that difference is itself a finding.

**Repo:** `jwallace115/mlb-model` (public).

**Pin:** branch `eng/fwd6`, at the commit that adds this file (titled "Cowork: FWD6b acceptance part 2 (Mac) …"). Below
it, in order:
- `d9b4b272c` (kill-ledger docs only);
- the FWD6b code commit (D260-D262);
- the acceptance part 1 commit;
- `b7d482a57`, a test-only fix.

The code under test is identical at `b7d482a57` and at the pin. The pin adds only the acceptance record, the week-3 pilot
run directory, its frozen file and its receipt.

**Deadline.**
- The first live freeze of `nfl_fwd_v1` is **Thu 2026-10-01 23:30Z**: TNF PIT@CLE, kick 10-02 00:15Z, command
  `python3 nfl/sim/run_forward_v1.py --week 4 --window-hours 2`.
- Hashed code must be merged to main by about **Thu 15:00Z**; otherwise TNF runs as a pilot.
- A reply by about 14:00Z leaves time to merge.

## 1. What FWD6b claims — verify each (decisions D260-D262 in `research/nfl_sim/NFL_SIM_DECISION_v1.md`; evidence in `research/nfl_sim/fwd6b_acceptance_2026-10-01.md`)

1. **A1 — consumed hashes are preserved.** `run_forward_v1._finalize_bundle_manifest` only ADDS hashes for new files. A
   listed file whose hash changed, or which vanished, HALTs. The read set is re-classified against the final manifest.
   `verify_bundle` runs again immediately before the freeze.
2. **A2 — the worker's numbers come from the bundle.**
   - `run_week.py --bundle-dir` reads lines, games and the cutoff itself from `lines.parquet`, `events.parquet` and
     `freshness.json`, so they appear in its read set.
   - `--lines-json` and `--games` are refused in forward mode, and `--as-of` must equal the bundle cutoff.
   - The worker writes `outputs/invocation.json`.
   - `_validate_outputs` HALTs unless the invocation matches the bundle, every `anchor_returned` target equals the
     bundle's spread and total, and picks_log, anchor_returned and anchoring_log all carry exactly this run's identity.
3. **A3 — full-record recovery.**
   - Receipts carry `run_dir` and the ai_opinions manifest entry.
   - The frozen file, the receipt (`<archive>/receipts/<run_id>.json`) and the registry are archived.
   - `restore_run.py --run-id` bootstraps the manifest from the receipt's bundle_digest and restores the run directory,
     publication.json, the frozen file, the manifest entry and the registry line.
   - It passes only if `verify_bundle` is clean and `receipt_status` is 'complete'.
   - A pre-D262 receipt (no `run_dir`) HALTs.
4. **A4 — schedule mapping (S2).**
   - The schedule comes from `nfl/data/pbp/schedules_<season>.parquet` if present, otherwise nflreadpy. It is
     snapshotted to `inputs/schedule.parquet`.
   - Each event must match exactly one target-week game with the same home and away team, with the kickoff (US Eastern
     `gameday` + `gametime`) within 60 min of `commence_time`.
   - `events.parquet` carries `nflverse_game_id`.
5. **A5 — freshness on the row the engine selects** (week == W, else the latest week ≤ W). Team ratings are judged per
   unit, taking the worst unit; a missing unit is not fresh.
6. **A6 — committed fixtures.** `nfl/sim/tests/fixtures/rosters_weekly_fixture.parquet`; no test reads a gitignored file.
7. **C — read-set hardening** (`nfl/sim/read_set.py`):
   - `io.open` and `pyarrow.parquet.ParquetFile` are wrapped.
   - 'r+' modes are recorded.
   - An audit-hook `open` backstop records reads that bypass the wrappers (os.open, FileIO, captured aliases).
   - Installation directories are excluded by real path, and code (.py/.pyc) is excluded.
   - `/private/etc` (macOS) is excluded alongside `/etc`.
   - `engine._CACHE` is cleared and `usage` is imported before routing.
   - `outputs/` entries must match the bytes on disk and the manifest.
   - MUST_READ now includes QB ratings, plus the bundle's lines, events and props.
8. **Found after the first pass, by Cowork's mutation run.** The new `io.open` text wrapper raised `LookupError` on
   `Path.read_text` with Python's UTF-8 mode OFF, which is the Mac's normal condition. The cloud C locale had hidden it.
   It is fixed with `_text_like_open`, and the forward list now runs with UTF-8 mode on and off.
9. **Evidence claimed:**
   - Linux clean worktree, no gitignored data: 170/0 with UTF-8 mode on and off.
   - 32 of 39 new tests fail on e826a30ae code.
   - 28 mutations, all caught after one test was strengthened (table in the acceptance note).
   - Mac (macOS, Python 3.13): 170/0.
   - Mac real runs:
     - a week-4 dry run (45-file read set, 0 unproven);
     - a week-3 pilot freeze (sha `a05a81fa…`), then its refused re-run;
     - a restore by run_id (29 files restored; verify clean; receipt complete; frozen file byte-identical).
   - **Same inputs, same outputs:** e826a30ae's and FWD6b's week-3 pilots have identical input hashes and give
     bit-identical picks_log `cal_p` (1,218 legs) and frozen `p_first` (989 rows).

## 2. What we need from you

**R1 — Re-test.** Re-run every audit-#9 (A) counterexample, every (C) bypass and every (D) surviving mutation at the pin.
Mark each FIXED, PARTIAL or NOT FIXED with file:line.

**R2 — Attack the read-set proof again.** In particular:
- the audit-hook backstop hashes the file at open time, not the bytes later parsed (a TOCTOU window), and only
  `os.open` should ever reach it;
- C extensions or memory maps reading natively;
- reads in the harness process that flow into the worker's arguments or environment;
- `read_set.json` on disk does not persist the `via` field;
- the four tables the old recorder missed (`actual_*_2021_2024`, `fourth_down_meta.json`): are any of them prediction
  inputs, and should any be per-run rather than repo-hashed?

**R3 — The freeze gate runs `test_freeze_v1` in-process via `pytest.main(..., plugins=[])`.** That does not stop
entry-point plugin autoload, and on the Mac `seleniumbase` and `pytest_asyncio` load. Is that a correctness risk for the
gate or the freeze, and what is the minimal fix if so? Note that run_forward_v1.py is hashed, so any change re-stamps.

**R4 — Walk Thursday's live run end to end at the pin.** Find anything that would halt when it should not, or not halt
when it should. Cover:
- quote age without `--allow-stale-quotes` (the VM props pull at about 22:00Z, line snapshots every 30 min);
- the ET/UTC date handling in the schedule match for a Thursday-night kickoff (00:15Z Friday);
- per-team freshness on week-4 data;
- the pinned logger and receipt path.

**R5 — Restore.** From a clean clone plus the archive, what is still not recoverable?
- Note that three inputs over 2 MB (player_usage, depth_charts, rosters) are not committed. They exist only in the Mac's
  archive.

**R6 — Mutations.** Find one surviving mutation per changed function in read_set.py, run_week.py (forward mode),
run_forward_v1.py (finalise, validate, schedule, freshness, receipts, archive) and restore_run.py.

**R7 — Verdict.** Can TNF be the first primary window on this pin? If not, give the minimum ranked fixes with file:line
that can be verified before Thu 15:00Z.

## 3. Known limits (Cowork's list — confirm, size, or refute)

- Code files are covered by the manifest hash check at the start of the run, not by the read set.
- Depth charts, injuries and the schedule are copied as record only; the prediction does not read them.
- Scoring (FWD7: S1-S4 and the scoring-side survivors) is declared, not implemented. Nothing has been scored.
- The old FWD3 pilot run `week=2026_03/sim_runs/20260927T170000Z` has no `inputs/` and cannot be restored. Under S1 it
  is never scored.
- The week-3 pilots are plumbing evidence, not out-of-sample.

A reply is most useful as:
- **(A)** the must-fix list before Thu 15:00Z, ranked, with a counterexample for each;
- **(B)** the audit-#9 re-test table;
- **(C)** read-set bypasses found;
- **(D)** surviving mutations;
- **(E)** start Thursday or not.
