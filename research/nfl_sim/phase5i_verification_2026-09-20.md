# Phase 5I — Cowork verification (2026-09-20)

Branch `eng/5i` at 18f549d, verified from a fresh clone on Linux. This note becomes D103 in
`NFL_SIM_DECISION_v1.md` AFTER the merge (writing it there first would conflict with the
branch's D99-D102, which are appended at the same place).

## Verdict: merge. The engine is better on every line that was measured, and the merge is clean.

Trial merge of `origin/eng/5i` into `origin/main` (5d5c3a1): no conflicts. In the merged tree
`engine_fingerprint()` = `7f3d96900218c014` and `_check_calibration_stamp()` = `(True, [])`.

## What held up (reproduced, not read from the report)

- **Scope.** Branch touches `engine.py` (+25), `tables.py` (+12), `scalars.json`,
  `clock_runoff.parquet`, `calibration_v1.json`, `fit_5i/` meta+census, ONE new test file, the
  decision doc, four K1 text files, the session log. No existing test, target or tolerance
  edited. `main` was not touched during the session.
- **The three new tests fail on the old engine** (run here against main's engine): drives with
  end_dist > 15 = 0.0649 (needs > 0.10); like-for-like go rate 0.21385 (diff 0.0159);
  `ev_3rd_long` KeyError. All three pass on the branch.
- **Suite values reproduce exactly on Linux:** go-rate test PASS, penalties per side PASS,
  FD by penalty 1.41 (FAIL, diff 0.32), tied-drive expiry 0.119 (FAIL), all late
  trailing/leading/tied-offence tests PASS. 21 passed / 2 failed of the 23 run here.
- **Refuse-to-rank at board level** — owed since 5G — is now on record: 990 legs, none ranked,
  `cal=d929ad258504b275, live=7f3d96900218c014`; ranks again after re-fit + re-stamp.
- **The clock fix does what it was for.** Cowork ran the check 5I skipped (5H late-snap
  instrumentation cherry-picked onto the 5I engine in a scratch clone; 2023, 272 games, N=200,
  249,004 snaps; real side = D98 section 3's definition). Offence tied or trailing 1-8, Q4:

  | sec/play | real | before (D98) | after 5I |
  |---|---|---|---|
  | pass, 121-300 s | 16.85 | 25.41 | **18.01** |
  | run, 121-300 s | 28.12 | 33.64 | **26.49** |
  | pass, 41-120 s | 11.82 | 11.10 | 10.93 |
  | pass, 0-40 s | 6.70 | 10.26 | 10.35 (untouched, as designed) |

  Cowork's prediction (pass within 3 s of 16.9) HELD: 18.0.

## What did not hold, or was not done

1. **Cowork's prediction that broad tied-drive expiry would fall below 0.081: FAILED.** 11-salt
   mean 0.117 -> 0.099 (SD 0.012); 0 of 11 below 0.081; strict 0.068 vs real 0/57. The test's
   own seed went the other way (0.111 -> 0.119) — inside one salt's noise. WHY, measured: one
   Q4_mid cell averages a window where real pace changes sharply at 3:00.

   | sec/play | real 121-180 | sim | real 181-300 | sim |
   |---|---|---|---|---|
   | pass | 12.63 | 17.68 (+5.0) | 20.17 | 18.18 (-2.0) |
   | run | 20.05 | 24.66 (+4.6) | 32.48 | 27.59 (-4.9) |

   Right on average, 5 s/play slow exactly where a tied drive is racing the clock, and the 0-40 s
   bucket is still +3.6 s. Candidate next fix (measured, not yet ordered): split Q4_mid at 180 s.
   Tied cells are already thin (n = 117 / 138; two fell back), so check cell sizes first.
2. **"Closed 94% of the go-rate gap" is the 50-game test sample.** On all 1,087 games,
   like-for-like: 0.219 -> 0.202 after item 1, then 0.207 after item 2 (the faster late clock
   gives trailing teams more snaps, hence more go-for-its — realistic). Real 0.198. About half
   the gap is closed, not 94%. Still the first fix to move this number at all.
3. **Cowork's four item-1 predictions "held exactly" is not independent evidence.** Same 50
   games, same seeds, deterministic engine: it is a reproduction of Cowork's scratch run. The
   independent check is the 1,087-game K1 above (-1.7pp), which agrees.
4. **Drives per game moved further from real: 22.9 -> 23.8 (real 21.9).** Already outside
   tolerance before, so "no K1 line moved out of tolerance" is literally true and hides it.
   Plays/game 130.3 vs 124.5 unchanged. Punts (8.19 -> 8.84 vs 8.73), FG attempts (3.77 -> 4.01
   vs 3.92) and pts/team (22.9 -> 22.7 vs 22.4) all moved TOWARD real.
5. **The K1 tables in D99-D101 cannot be rebuilt from anything committed.** The four
   `phase5i_k1_*.txt` files hold non-offensive scoring and pts/team only; the other lines came
   from the gitignored, overwritten `k1_5a5.parquet` via uncommitted code (rule 8). Cowork's
   error too: the order named `run_k1_5a5.py` as "K1" without checking what it prints. There is
   still no committed script that prints the full K1 table with tolerances.
6. **D101 contradicts itself.** Its table says FD-by-penalty "passes on all 11 salts (< 1.430)".
   The test needs |x - 1.73| < 0.3, i.e. x ABOVE 1.430; a mean of 1.414 FAILS on all 11, as
   D102's own suite run shows. Known cause: the engine has no scrimmage-play penalty first
   downs (0.477/team of the real 1.73).
7. **K4 rows for `fit_5i` were not committed**, so 0.25356 cannot be recomputed. `fit_5i/games/`
   lives only in `~/mlb-model-5i` (gitignored) — do not delete that folder.

## K4 in context — this is the number that answers "how much weight does the sim carry"

Recomputed from `k4_rows_fit_5d2.parquet` (72,897 real prop legs, 2023-24, outcome = over hit):

| forecast | Brier |
|---|---|
| sportsbook closing price, de-vigged | **0.2316** |
| always 50% | 0.2500 |
| calibrated sim, fit_5d2 | 0.2534 |
| calibrated sim, fit_5i (reported, not reproducible) | 0.2536 |
| raw sim, fit_5d2 | 0.2642 |

The sim is worse than the book in all 8 families (receptions 0.2426 vs 0.2232; rush attempts
0.3034 vs 0.2466) and slightly worse than a coin flip overall — with calibration maps fitted on
seasons that INCLUDE these games (in-sample, in the sim's favour). Real closing prices, not
synthetic. The 5I engine fixes did not move it (0.2534 -> 0.2536), which is expected: a
4th-down go rate does not move a receptions leg. Prop accuracy lives in the usage/player layer,
not in the game engine.

## After the merge

- `main`'s engine becomes `7f3d96900218c014` on `fit_5i`. Week 2's board (2026-09-20) was on
  `d929ad258504b275` / `fit_5d2`; the scored ablation starts Week 3, so every scored week is on
  one engine.
- Then: untrack `nfl/data/pbp/depth_charts.parquet` once `run_week.py` refreshes its own inputs
  (~216 MB/month of git history, N36), and give `run_week.py::get_lines_from_history()` a
  kickoff filter. Both were blocked on this branch.
