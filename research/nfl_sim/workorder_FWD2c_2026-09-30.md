# Work order FWD2c — live mode proven, runbook from the tape, params safe, settlement right (2026-09-30)

Written by Cowork after verifying FWD2b (`fwd2b_verification_2026-09-30.md`, D233). This continues on eng/fwd2. No
FREEZE_v1 file changes. **Gate:** Cowork verifies by **Thu 10-01 20:00Z**, or TNF stays a pilot.

Pre-check (Cowork):
- **Runtime.**
  - Code and tests: minutes.
  - One real live dry run for week 4: 1-2 games at about 30 s each plus the bundle, about 2 min.
  - Re-grade of weeks 2-3: seconds.
  - No ratings rebuild is needed; ratings are already at week 3.
- **Credits.** Zero. The London pull is Jeff's, on Sunday: about 10 credits, one event.
- **Paths.**
  - Existing: `nfl/sim/run_forward_v1.py`, `nfl/pipeline/log_ai_opinions.py`, `nfl/sim/ratings.py`,
    `research/nfl_sim/fwd1_runbook.md`, and `nfl/pipeline/pull_hardrock_props.py` (with `--out-dir`, which writes
    `scratch_<ts>.parquet`).
  - The manual props folder is `data/odds_archive/nfl/props/season=2026/manual/`.

```
Work order FWD2c (research/nfl_sim/workorder_FWD2c_2026-09-30.md). Continue on eng/fwd2 in /tmp/eng-fwd2 (git pull;
head 3beed7970). Gate: `git show origin/main:research/nfl_sim/fwd2b_verification_2026-09-30.md | grep -c "^### D233"`
prints 1. FIRST COMMIT: append D233 verbatim. Then items 0-3 (D234-D237), one commit each, pushed before the next.
Keep context lean (grep for functions).

HARD RULES: (1) FREEZE_v1 files byte-identical; test_freeze_v1 before every commit. (2) file:line for code claims.
(3) Tests execute the code; each new test fails on 3beed7970 for the right reason (paste it). (4) Every real-data
command is run and its output pasted; a missing deliverable = NOT DONE, stop. (5) Dates and games come from the line
tape or the nflverse schedule by code — never typed from memory.

Item 0 (D234) — live mode, proven.
  (a) Rename the existing test_live_freeze_completes to test_pilot_fixture_freeze. Add a TRUE live test: main() with
      NO --pilot and NO --as-of on the fixture root, where the fixture's kick = now + 2 h and its props pull = now − 30
      min, with the stub run_week. It completes a freeze; the frozen rows have pilot == False and the canonical reader;
      the prices equal the bundle. Add a second live test where the fixture pull is 4 h old: it HALTs on quote age with
      nothing frozen.
  (b) Allow --allow-stale-quotes together with --dry-run (never with a freeze), recorded in the bundle, so the live
      code path can be exercised at any hour.
  (c) REAL: `run_forward_v1.py --week 4 --dry-run --window-hours 60 --allow-stale-quotes` (no --pilot) must COMPLETE.
      Paste: the bundle manifest, freshness, the event list, coverage by market, the sidecar, the tag counts.

Item 1 (D235) — params safety and the runbook, from the tape.
  (a) ratings.py writes params_v1.json ONLY with a new --write-params flag (ratings.py:936-938). The default run
      leaves it byte-identical. Test: run the params-writing function without the flag on a temp path -> not written.
  (b) Rewrite research/nfl_sim/fwd1_runbook.md from a small script, research/nfl_sim/make_runbook.py, that reads the
      Hard Rock line tape and the nflverse schedule and prints, for weeks 4 and 5, every kick window:
      - the UTC and ET kick times, the weekday, and the games;
      - the run command (run from ~/mlb-model on main, with --week W and --window-hours);
      - the latest safe start (measured runtime per game × games + 3 min margin);
      - the VM props slot that precedes it, and its expected age;
      - for any window whose newest VM slot is more than 3 h before the run, the exact manual pull command:
        `python3 nfl/pipeline/pull_hardrock_props.py --window-hours 2 --tag close --out-dir
        data/odds_archive/nfl/props/season=2026/manual`, with its credit cost.
      Input refresh is ONCE a week (Wednesday), not per window, with the exact commands and the freeze-test check
      after. The runbook is the script's output; paste it.
  (c) Confirm with a fixture that build_bundle reads `manual/scratch_*.parquet` (the puller's real output name), and
      takes it when it is the newest pull at or before T.

Item 2 (D236) — settlement, for every reader.
  (a) snap_played None (no snap data for that game) -> UNRESOLVED; no stat is scored.
  (b) Participation matched by player ID, not name: map the frozen row's resolved gsis id to the snap-count row via
      the nflverse roster/ids crosswalk (cite the source). A name match is used only if there is no id, and the report
      counts how often.
  (c) Completed-game check: the game's final is in PBP (a game-end row or schedule result); otherwise unresolved.
  (d) Find why the week-3 re-grade graded 0 of 2,070 rows when the FWD1b pilot graded week 3 from the same PBP. Fix it.
      Re-run: weeks 2 and 3, AI files and the sim pilot, old vs new units, Brier, and void/unresolved counts per file.
  (e) `score-experiment --file F` is a pure diagnostic: it ignores the pilot and revision filters (labelled
      DIAGNOSTIC — NOT THE RECORD) and prints Δ, the CI and P2 for the sim_v1 rows. Run it on the week-3 pilot file
      and paste it (Cowork's FWD1b pilot numbers for comparison: Δ +0.0157, n=174).
  Tests: an inactive player with no snap data -> unresolved; a suffix name ("Jr.", "III") settles by id; an incomplete
  game -> unresolved.

Item 3 (D237) — stamp and summary. Re-stamp FWD_EXPERIMENT_v1.json LAST, then paste the full test list with pass
  counts and `git diff --stat origin/main...HEAD`.

Every item's report separates what the command RETURNED from what it MEANS and ends with NOT DONE and UNVERIFIED.
```
