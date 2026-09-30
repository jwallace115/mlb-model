# FWD2 verification — Cowork, 2026-09-30 (01:20Z)

Branch `eng/fwd2` @ `fd0a2a5c6` (D223 append; D224; D224a; D225; D226; D227; logs). Read from the committed code, in a
clean worktree on Linux. 31 tests pass here too.
**Verdict: not merged. The live path does not run.** The tests that were supposed to prove it does only read the
source text. Several deliverables the session itself lists as NOT DONE are required before any primary window.

## What stands
- **D224a.** Cross-week refusal now sits inside `freeze()`. A zero-match HALT exists. The harness calls the calibration
  stamp and the usage fingerprint.
- **D225.** `build_bundle()` writes events, props (archive + manual/, Hard Rock, newest ≤ T), lines (newest snapshot
  ≤ T) and a freshness table. `fill_sheet` keys on game_id. `newest_inputs` caps lines at `now`.
- **D226.** The sidecar takes its targets from the lines actually used (CAR@ATL −3.0/43.5), and is written into the
  bundle before the freeze.
- **D227.** `primary_cohort()` and `primary_statistic()` exist. The formula is the Brier difference, with a
  50,000-resample whole-game bootstrap and seed 20261004.

## What does not
1. **A live run HALTs at its first logger call.**
   - `main()` always appends `--as-of T` to the sheet call (run_forward_v1.py:510-511) and to the freeze call (:595).
   - The logger still refuses `--as-of` without `--pilot` (log_ai_opinions.py:741-742). Run by Cowork:
     `log_ai_opinions.py sheet --week 4 --as-of 2026-10-01T23:30:00+00:00` → `HALT: --as-of requires --pilot`,
     exit 1.
   - Every non-pilot run, including Thursday's, stops here. Nothing ever exercised a live run.
2. **The freeze does not use the bundle.** The freeze call passes neither `--props-file`/`--lines-file` nor the
   window or event restriction, so `freeze()` rebuilds its sheet from the tape. It builds from every pre-kick game,
   and the archive only (not manual/). A window run would then fail on lines the fill never saw, or would freeze
   quotes that differ from the bundle. `validate()` still does not compare prices or source_utc with the bundle (the
   session's own NOT DONE).
3. **The main() tests only read the source code.** `test_zero_matches_halt` and `test_cal_stamp_check_in_harness`
   assert that strings like `"n_matched == 0"` and `"_check_calibration_stamp"` appear in `inspect.getsource(main)`.
   No test runs `main()`. This is how item 1 passed.
4. **The participation rule voids real Unders.** `_game_actuals` counts as participants only the players named in
   some play's `*_player_id` column. A receiver who played and was never targeted appears in none, so his Under is
   VOID when Hard Rock pays it as a win. The order required a named nflverse participation source (snap counts or
   game status).
5. **The scoring is not wired in.**
   - `primary_cohort` and `primary_statistic` are never called from `score()` or the CLI, so `score` still pools
     every reader.
   - `primary_cohort` treats every game as anchored when no sidecar is passed, instead of halting.
   - The game key is the team pair, not event_id.
   - There is no P2 and no breakouts.
6. **Freshness only warns.** It prints a WARNING when ratings are older than W−1 (run_forward_v1.py:193) and does not
   HALT. The builders are not run and their runtime is not measured.
7. **run_week is not restricted to the bundle's events.** It simulates the whole week, which matters for runtime in
   the MNF window.
8. **Not done at all:**
   - the AI blind-log re-grade;
   - the runbook rewrite and the London pull command;
   - the week-4 dry run on the new path.

   This is the third order in a row where the dry run, which would have caught item 1 in a minute, was skipped.

### D228 — Cowork verification of FWD2: not merged; the live path HALTs, the main() tests read source text, participation voids real Unders (2026-09-30)

FWD2 (eng/fwd2 @ fd0a2a5c6) is not merged.

What stands:
- cross-week refusal inside freeze();
- the zero-match and calibration-stamp/usage HALTs;
- the run bundle at T;
- game-keyed matching;
- sidecar targets from the lines used;
- the cohort and statistic functions.

Defects:
- A live run HALTs at the sheet step (`--as-of` without `--pilot`, reproduced).
- freeze() rebuilds its sheet from the tape instead of the bundle, with no window, and no price comparison.
- The main() tests are `inspect.getsource` string checks.
- Participation comes from the PBP player-id columns, so an active player with no touches is VOID.
- The cohort and statistic are not wired into scoring, and the anchor join passes silently without a sidecar.
- Freshness only warns.
- run_week is not event-restricted.
- The re-grade, the runbook and the dry run were not done.

Next: FWD2b. Acceptance is on real data: a completed week-3 pilot freeze through main(), and a completed week-4 live
dry run. The TNF start window holds only if FWD2b is verified by Thu 10-01 20:00Z.
