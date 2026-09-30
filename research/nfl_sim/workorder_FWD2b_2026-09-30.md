# Work order FWD2b — make the live path actually run, on the bundle, and prove it on real data (2026-09-30)

Written by Cowork after verifying FWD2 (`fwd2_verification_2026-09-30.md`, D228). This continues on eng/fwd2 (not
merged). No physics change: every FREEZE_v1 file stays byte-identical. **Deadline:** Cowork verifies by
**Thu 10-01 20:00Z**, or TNF stays a pilot.

Pre-check (Cowork):
- **Runtime.**
  - Items 0-1 are code and tests. The fixture tests use a stubbed run_week, so they take seconds.
  - Item 2 runs on real data:
    - input refresh with the existing builders (`nfl/sim/pull_nflverse_inputs.py`, `nfl/sim/ratings.py`; runtime
      unknown: **measure it**);
    - one week-3 pilot at about 12 s × 14 games ≈ 3 min;
    - one week-4 dry run at about 12 s × 16 games ≈ 3-4 min;
    - scoring and re-grade in seconds.
  - Total well under an hour of compute.
- **Credits.** Zero. nflverse (snap counts, PBP) is free, the Odds API is not called, and tape reads are free.
- **Paths.** Existing: `nfl/sim/run_forward_v1.py`, `nfl/pipeline/log_ai_opinions.py`, `nfl/sim/run_week.py`,
  bundles under `nfl/data/board/week=2026_WW/sim_runs/<run_id>/`, and `research/nfl_sim/fwd1_runbook.md`. The snap
  counts come from nflreadpy `load_snap_counts` (the Mac has nflreadpy; cite the call).

```
Work order FWD2b (research/nfl_sim/workorder_FWD2b_2026-09-30.md). Continue on eng/fwd2 in /tmp/eng-fwd2 (git pull;
head must be fd0a2a5c6). Gate: `git show origin/main:research/nfl_sim/fwd2_verification_2026-09-30.md | grep -c
"^### D228"` prints 1. FIRST COMMIT: append D228 verbatim. Then items 0-3, ONE COMMIT PER ITEM, push each; D229-D232
in the same commit as their code. Session log appended to logs/_log_fwd2.txt. Keep context lean: grep for the
functions you change; do not read whole files.

HARD RULES: (1) FREEZE_v1 files byte-identical; test_freeze_v1 before every commit, paste the line.
(2) file:line for code claims. (3) NO test may inspect source text (no inspect.getsource, no string search of code) —
delete the existing ones and replace them with tests that EXECUTE the code. Every new test fails on fd0a2a5c6 for the
right reason; paste each failure. (4) An item whose required deliverable is missing is NOT DONE — do not start the
next item; say so and stop. (5) Every acceptance command in item 2 is actually run, and its output is pasted.

Item 0 (D229) — the harness runs in-process on the bundle, live and pilot.
  Refactor so main(argv=None, root=None, run_week_fn=None) is callable from a test: every path derives from root, and
  run_week_fn defaults to the real run_week.
  The sheet and the freeze are built IN-PROCESS from the bundle:
  - build_sheet(bundle props, bundle lines, T), restricted to the bundle's event_ids;
  - freeze(sheet, filled, ..., now=T, reader_model, pilot);
  - no subprocess to the logger CLI, so the CLI's "--as-of requires --pilot" rule no longer blocks a live run.
  T for a live run = wall clock at start. HALT if the wall clock at freeze >= the first kick of the window.
  validate() checks the filled sheet's price_first, price_second and source_utc against the sheet from the bundle,
  and HALTs on any difference.
  run_week gets the bundle's lines and the bundle's game list (add --lines-json and --games to run_week.py; it must
  not read the tape itself when given them) and simulates ONLY those games.
  Freshness HALTs (not warns) unless team ratings, tendencies and usage for season 2026 have max week >= W-1. Kickers
  with no 2026 rows are a declared fallback, recorded in the bundle.
  Tests, all through main() on a temp root: a 1-event fixture tape, a stub run_week writing picks_log.parquet and
  anchoring_log.parquet.
  - (a) LIVE (no --pilot, T=now, kick at T+2h): a frozen file exists, and its prices equal the bundle's.
  - (b) PILOT with --as-of completes.
  - (c) A bundle price altered after the sheet -> HALT.
  - (d) Stale ratings -> HALT.
  - (e) Zero matches -> HALT with nothing frozen.
  - (f) Usage-fingerprint mismatch (monkeypatched) -> HALT with nothing frozen.
  - (g) Wall clock past the first kick -> HALT.
  (a) must fail on fd0a2a5c6 with the --as-of HALT.

Item 1 (D230) — settlement and the experiment score, wired in.
  Participation for EVERY reader:
  - from nflverse snap counts (nflreadpy load_snap_counts, 2026) joined by player and game;
  - offense + special-teams snaps > 0 = played; not present = VOID; snap data unavailable for that game = unresolved;
  - replace the PBP player-id participants rule.
  Tests: a WR with snaps and 0 targets has his Under SETTLED as a win; a player absent from snaps is VOID; a game with
  no snap data is unresolved.
  Frozen rows gain run_id (new files only; existing files untouched).
  New CLI `log_ai_opinions.py score-experiment --experiment nfl_fwd_v1 [--include-pilot] [--file F]`:
  - pools ALL week directories for the canonical reader;
  - joins each row to ITS run's anchor sidecar (bundle, by run_id + event_id), and HALTs if any cohort row lacks one;
  - game key = event_id;
  - runs primary_cohort (the predicate printed verbatim, with the exclusion counts) and primary_statistic (Δ, 95% CI,
    verdict, n legs, n games);
  - P2: units at the frozen Hard Rock price, |p−q| > 0.08, settled only, with a game-bootstrap CI;
  - breakouts by family, week, gap bucket, and anchor status (the last reported only);
  - `--file` scores one file regardless of revision, for pilot diagnostics, labelled so.
  Tests run the CLI's main() on a fixture: another reader and an unanchored game stay out of the cohort; a missing
  sidecar HALTs.

Item 2 (D231) — acceptance on REAL data (run each command; paste the output).
  (a) Refresh inputs with the existing builders (cite the commands). Measure the runtime. Print the freshness table.
  (b) `run_forward_v1.py --week 3 --pilot --as-of 2026-09-27T16:30:00+00:00 --window-hours 9 --allow-stale-quotes`
      must COMPLETE a freeze. Paste the bundle manifest, freshness, coverage, sidecar and the frozen file name.
  (c) `score-experiment --experiment nfl_fwd_v1 --include-pilot --file <that file>`: paste the cohort, exclusions, Δ
      and CI, and P2.
  (d) `run_forward_v1.py --week 4 --dry-run --window-hours 60` (live mode): paste the whole output.
  (e) Re-grade the AI blind log for weeks 2-3 under the new settlement rule. For each file give old vs new units and
      Brier, and how many rows changed from settled to VOID or back. Reporting only; the frozen files are untouched.

Item 3 (D232) — the runbook and the stamp.
  Rewrite research/nfl_sim/fwd1_runbook.md for weeks 4-5:
  - weekday labels in UTC (TNF Fri 10-02 00:15Z; London Sun 10-04 13:30Z; SNF Mon 10-05 00:20Z; MNF Tue 10-06 00:15Z);
  - for each window: the input-refresh commands and their measured runtime, the run command, and the latest safe start
    time given the measured runtime (1-game run_week);
  - London: Jeff's exact manual props pull command writing to data/odds_archive/nfl/props/season=2026/manual/, and its
    credit cost.
  Re-stamp FWD_EXPERIMENT_v1.json LAST. Paste the full test list with pass counts.

Every item's report separates what the command RETURNED from what it MEANS and ends with NOT DONE and UNVERIFIED.
```
