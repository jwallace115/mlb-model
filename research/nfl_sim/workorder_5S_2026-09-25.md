# Phase 5S work order — the interception is spotted where it is caught; ONE re-fit; two test debts paid

Date: 2026-09-25 (UTC). Repo: jwallace115/mlb-model. Scope: `nfl/sim/` and `research/nfl_sim/` only.
Read first: `research/nfl_sim/phase5r_verification_2026-09-25.md`, D138-D142.
Prerequisite on main: `grep -c "^### D142" research/nfl_sim/NFL_SIM_DECISION_v1.md` = 1. If 0, STOP and report.

## Why this order exists

engine.py (~line 2331-2332): after an interception the defence takes over at `100 - (yl + ret)` with `yl` the
line of scrimmage. The ball was caught `air_yards` downfield. Real post-INT drives start 56.0 yards from the
end zone; the sim's start 39.9 (D141) - 16 free yards on ~1.6 picks a game. That is the bulk of the short
fields (D135: +0.52 of +0.64 per game inside the 40), the short TD drives (D132) and a good part of the extra
possessions, punts and drives (D129/D131). The engine draws no air yards on a pass, so the spot needs a
MEASURED table, not a constant. Two test debts ride along. Items 1-2 change the fingerprint; ONE re-fit.

## HARD RULES (as 5R; binding)

1. Branch `eng/5s`, worktree `~/mlb-model-5s`, from origin/main after D142. `main` untouched. Cowork verifies.
2. No existing test, tolerance, threshold, `MIN_CELL`, `N` or sample filter is edited, EXCEPT the two named in
   item 0, for the reasons stated there. New tests in NEW files `test_engine_5s.py`.
3. No constant is typed by hand: the INT-spot table is built from PBP 2021-24 by a committed builder in
   `tables.py`, with the derivation in the `### DNN` entry.
4. Never reduce N, subsample, skip a test or kill a run. Measure runtimes. `GIT_OPTIONAL_LOCKS=0` on every
   git command. Commit AND push each item before the next (`git push -u origin eng/5s`), `### DNN` (D143+)
   with report and parquet in the same commit.
5. A diff is not evidence: the new spot is shown in the drive log (post-INT start yardline) before and after.
   Pre-registered predictions are written before looking; a failed one is reported as failed.
6. Zero API credits. Do not touch `bets/`, `nfl/pipeline/`, `ncaaf/`, `shared/`.

## Setup

```
cd ~/mlb-model && GIT_OPTIONAL_LOCKS=0 git pull --no-rebase --no-edit --autostash
GIT_OPTIONAL_LOCKS=0 git worktree add ~/mlb-model-5s -b eng/5s
cd ~/mlb-model-5s
for f in ~/mlb-model/nfl/data/pbp/*.parquet; do [ -e "nfl/data/pbp/$(basename $f)" ] || ln -s "$f" "nfl/data/pbp/$(basename $f)"; done
python3 -c "from nfl.sim.calibration import engine_fingerprint as f, usage_fingerprint as u; print(f(), u())"   # must print 5ee4b1009301783d 3638769c89030de0
```
Anything else: STOP and report.

---

## Item 0 — two test debts (no engine change)

0a. `nfl/sim/tests/test_score_vs_book.py`: the two tests pin the universe at 146 rows / 138 receptions. That
    count moves with every re-fit (which legs the sim prices at the book's exact line). Rewrite them to assert
    STRUCTURE: no placed rows in the universe; every row has cal_p, q_over and a hit/miss grade; the count
    equals what `build_universe` returns for the pre-registered candidates file (computed, not typed); and
    the game-cluster bootstrap runs. Show each rewritten test failing on a deliberately broken input.
0b. `like_for_like_go` has been red since 5L (K1 0.0102 vs tol 0.0100; the suite's test name, if any, stated).
    Investigate it in this item: what the metric is, why it sits 0.0002 over, and whether it is the same
    go-rate that `go_rate` (0.2050 vs 0.1980, PASS) measures on a different denominator. Report; change no
    threshold. If it is a denominator mismatch, say which one is right and queue the fix.

## Item 1 — the interception spot (engine + table)

1a. `tables.py`: a builder for `int_spot.parquet` from PBP 2021-24 REG: on `interception == 1` plays, the
    distribution of `air_yards` (the catch point relative to the LOS) by LOS bucket (yardline_100 buckets
    1-20 / 21-40 / 41-60 / 61-80 / 81-99), as quantiles (101 points) with n per bucket; rows with missing
    air_yards counted and reported. Derivation in the report. NULL for the table: its overall median equals
    the real median air yards on interceptions that D141 reported (13.0) within 0.5.
1b. `engine.py` INT branch: draw the catch point from the LOS bucket's quantiles with a NEW uniform draw from
    the PLAYER-INDEPENDENT stream (the play-loop `rng`, drawn alongside `u_int_ret` at the same place, so the
    per-play draw order is stated), clip the catch point to the field, then the return, then
    `yl_new = 100 - (yl - air + ret)` clipped to [1, 99]. A pick in the end zone (yl - air <= 0) is a
    touchback: new drive at 80 (state the real touchback rate on end-zone picks from PBP and use it, or the
    return quantiles from the 0 line - say which). Nothing else in the INT branch changes. Record the new
    fingerprint. Test in `test_engine_5s.py`: on 3 games x 2 seeds, mean post-INT start yardline moves from
    ~40 to >= 52; INT count per game unchanged within 0.05 (same draws for the pick itself). Show the test
    failing on the 5R engine.
PRE-REGISTERED (from the drive log, 200 K1 games, N=100): post-INT start 39.9 -> within 3 of 56.0; drives
starting inside the 40 per game 1.86 -> <= 1.45; TD drives 1-3 plays share 0.180 -> <= 0.14; INT rate
unchanged (1.62 +- 0.05 per game).

## Item 2 — ONE re-fit `fit_5s`, re-stamp, K1, K4, suite, boards

As 5R item 3: `run_fit.py --seasons 2021 2022 2023 2024 --out-dir fit_5s`, cal maps, re-stamp, K1 ->
`phase5s_k1_after.txt` (+rows), K4 -> `phase5s_k4.parquet`, full suite (name every red; the two 5I reds are
expected; anything else is investigated here), Week 2 board `--as-of 2026-09-20T15:30:00Z` and Week 3 board
`--as-of 2026-09-24T21:30:00Z` saved under `research/nfl_sim/phase5s_boards/` with their `team_volume`.
PRE-REGISTERED, write before looking: K1 plays/game 131.1 -> <= 128.5; drives 23.9 -> <= 23.3; punts 8.89
-> <= 8.6; TD drives per game within 0.15 of 4.73 (real); pts/team within 0.5 of 22.90 (NULL); go_rate,
off_pen, def_pen, fg_att within their K1 tolerances of the 5R values (NULL); INT rate unchanged (NULL).
Board: report SD(raw sim_p - q_over) on the 1614Z receptions candidates and the pass-attempt gap vs the
book; PRE-REGISTERED: SD falls from 0.134 (no target below - the pace side effect of D142 means the
board's volume is not expected to move here). If a prediction fails, say so and tune nothing.

## Item 3 — the ratings tables become reproducible for Cowork (no behaviour change)

`ratings.py` gets a `--check` mode that prints `usage_fingerprint()` after a rebuild, and the `### DNN`
entry records the exact command and inputs (PBP files with their sha256[:8], rosters, depth snapshot date)
that reproduce `3638769c89030de0` / the item-2 value, so Cowork can rebuild the gitignored tables on Linux
and run the bit-identity check that 5R could not. Show the rebuild on the Mac reproducing the fingerprint.

## Closing

`logs/agent_sessions.md` entry (`git add -f`): RETURNED vs MEANS; runtimes; NOT DONE; UNVERIFIED (at minimum:
Cowork's Linux rebuild + bit-identity of the item-2 boards).
