# Phase 5J work order — two point-in-time guards, a K1 generator, the Q4_mid split

Date: 2026-09-20 (UTC). Repo: jwallace115/mlb-model. Scope: `nfl/sim/` and `research/nfl_sim/` only.
Read first: D59, D77, D81, D100, D102, D103 in `research/nfl_sim/NFL_SIM_DECISION_v1.md`, and
`research/nfl_sim/phase5i_verification_2026-09-20.md` (section "What did not hold").

## Why this order exists

Every item is a defect READ IN SOURCE on main (`7f3d96900218c014`, `fit_5i`), not guessed:

1. `nfl/sim/usage.py` layer 3 (the static depth-chart fallback for the starting QB, ~lines
   312-345) takes the NEWEST rank-1 QB per team (`sort_values("dt", ascending=False)`) and
   writes it into EVERY week 1-22 of the current season that layers 1-2 left unset. D59 put a
   `dt < week's first kickoff` rule on `depth_order` (lines ~396-430). Layer 3 never got it.
   A week already played can therefore be labelled from a depth chart published after it.
   Class 1b (historical feature construction). Raised by ChatGPT audit #5. The depth file
   spans 2025-08-03 .. today, 401 snapshot dates, so the cutoff is computable.
2. `nfl/sim/run_week.py::get_lines_from_history()` (lines 113-141) reads `files[-1]` — the
   newest line snapshot — with no check that `snapshot_utc < commence_time`, so a board built
   after a kickoff anchors to an in-play line. And when a game has no Hard Rock row it sets
   `hr = gdf` (ALL books) and takes `.iloc[0]`: an arbitrary book's spread and possibly a
   different book's total, labelled "consensus". It is not a consensus of anything.
3. There is no committed script that prints the full K1 table. D99-D101's tables came from a
   gitignored parquet through uncommitted code (5I verification, item 5). `run_k1_5a5.py`
   prints non-offensive scoring and pts/team only; `k1_compare_5a4.py::report` has most of the
   lines but no tolerances and no single entry point.
4. One `Q4_mid` clock cell covers 121-300 s. Measured by Cowork (2023, 272 games, N=200,
   offence tied or trailing 1-8): sim is +5.0 s/play slow on passes and +4.6 on runs in
   121-180 s, and -2.0 / -4.9 in 181-300 s. Right on average, wrong where a tied drive is
   racing the clock. Broad tied-drive expiry: 11-salt mean 0.099 (SD 0.012) vs matched 0.081.

## HARD RULES

1. ALL work on branch `eng/5j` in worktree `~/mlb-model-5j`. `main` is not touched. Cowork
   verifies and merges. The Week 3 board (Thursday) runs on `main`.
2. No existing test, target, tolerance, threshold, `MIN_CELL` or sample filter is edited. New
   tests go in NEW files: `nfl/sim/tests/test_usage_pit_5j.py`, `nfl/sim/tests/test_run_week_5j.py`,
   `nfl/sim/tests/test_engine_5j.py`.
3. No constant is tuned to hit a test. Table numbers are measured from PBP 2021-24 by committed
   builder code. `N=5,000` for the fit is D51 and does not change.
4. RUNTIME POLICY: never reduce N, subsample, shorten a sweep, skip a test or kill a run to
   finish sooner. Do not budget or narrate how long your own session will take.
5. Prefix EVERY git command with `GIT_OPTIONAL_LOCKS=0`. Push with `git push -u origin eng/5j`.
6. 4 items. Commit AND push each before the next. Each writes its `### DNN` entry (D104 onward —
   run `grep -n "^### D1" research/nfl_sim/NFL_SIM_DECISION_v1.md | tail -3` first and take the
   next free number) ON THE BRANCH in the same commit.
7. A diff is not evidence that code runs. Evidence is pasted execution output from the
   production entry point, and for every guard, a run where it changes an outcome.
8. Every number in a report comes from COMMITTED code. API credits: zero — nothing here pulls.
9. Do not touch `bets/`, `nfl/pipeline/`, `ncaaf/`, `shared/`.

## Setup

```
cd ~/mlb-model
GIT_OPTIONAL_LOCKS=0 git pull --rebase --autostash
GIT_OPTIONAL_LOCKS=0 git worktree add ~/mlb-model-5j -b eng/5j
cd ~/mlb-model-5j
for f in ~/mlb-model/nfl/data/pbp/*.parquet; do [ -e "nfl/data/pbp/$(basename $f)" ] || ln -s "$f" "nfl/data/pbp/$(basename $f)"; done
python3 -c "from nfl.sim.calibration import engine_fingerprint as f; print(f())"   # must print 7f3d96900218c014
```
If it prints anything else, STOP and report. If a run fails on another missing gitignored
input, link it the same way and say which.

---

## Item 1 — layer-3 starting-QB fallback gets the D59 date rule

Change: for each (season, week) layer 3 fills, use the latest rank-1 QB snapshot per team with
`dt` STRICTLY BEFORE that week's first kickoff. Reuse D59's kickoff lookup (PBP `game_date`);
for weeks with no PBP yet, take the first kickoff from the nflverse schedule the module already
loads elsewhere (`nflreadpy.load_schedules`) — state in D104 which source each 2026 week used.
A week with no eligible snapshot stays unset and is COUNTED and printed; it is not back-filled.

PRE-REGISTERED (write into the report before running):
- P1. Rebuilding usage changes `is_starting_qb` for ZERO team-weeks in 2026 weeks 1-2 as of
  today (Cowork checked the committed week-2 rows: 32/32 flagged starters equal the week-1
  leading passer). If any row changes, list every one with old/new player and source — that
  is the finding, do not explain it away.
- NULL CONTROL. The 2021-2024 block of `player_usage_weekly.parquet` is BIT-IDENTICAL before
  and after, and `engine_fingerprint()` and the D77/D81 ratings hashes are unchanged. Paste both.

Tests (`test_usage_pit_5j.py`), modelled on `test_d59_negative_control`:
- inject a synthetic rank-1 QB row for one team with `dt` AFTER week W's kickoff and a
  different `gsis_id`, on a (season, week, team) that layers 1-2 leave unset; assert the
  starter for week W is unchanged, and that the SAME row dated before kickoff DOES change it
  (so the test can go both ways). If no such team-week exists in real data, build the smallest
  synthetic input that reaches layer 3 and say so — do not write a test that cannot fire.
- confirm the test FAILS on main's `usage.py`. Paste that failure.

Decision entry: D104.

## Item 2 — `get_lines_from_history()`: pre-kick snapshot, one named book, no silent fallback

Change:
- For each game use the newest snapshot whose `snapshot_utc < commence_time` for THAT game
  (walk back through `snap_*.parquet`; do not assume `files[-1]`). A game with no pre-kick
  snapshot gets no line and is printed as skipped with the reason.
- Spread and total come from the SAME Hard Rock row set of that snapshot. If Hard Rock has no
  row for the game, there is NO fallback to `gdf.iloc[0]`: the game is skipped and printed.
  (If you believe a real consensus fallback is needed, write the case in D105 — do not build it.)
- Add `--as-of <UTC ISO>` to the CLI (default: now). It caps which snapshots may be read, so a
  past board is reproducible. Record per game in `anchoring_log.parquet` / the board header:
  `line_snapshot_utc`, `line_book`.

PRE-REGISTERED:
- P2. `run_week.py --week 2 --as-of 2026-09-20T15:30:00Z` yields the same spread/total for
  every game as the OLD function run on `snap_20260920T150009Z.parquet` alone (all games were
  un-kicked and Hard Rock-quoted then). Show the per-game diff; expected: empty.
- P3. With `--as-of 2026-09-20T18:30:00Z` (after the 17:00Z kickoffs) the old function returns
  in-play or missing lines for kicked games; the new one returns each game's last PRE-KICK
  line. Show at least 3 games where old != new, with both snapshot times.
- NULL CONTROL. `engine_fingerprint()` unchanged; the sim results for a game given the same
  (spread, total, seed) are identical — this item changes which line is read, nothing else.

Tests (`test_run_week_5j.py`), fixtures cut from the real 2026-09-20 tape (small, committed
under `nfl/sim/tests/fixtures/`): (a) in-play snapshot is never chosen; (b) a game with no
Hard Rock row is skipped, not priced from another book; (c) `--as-of` earlier than every
snapshot returns no lines. Confirm (a) and (b) FAIL on main. Paste the failures.

Decision entry: D105.

## Item 3 — `nfl/sim/run_k1_table.py`: one committed generator for the full K1 table

- One entry point: `python3 nfl/sim/run_k1_table.py --out research/nfl_sim/<name>.txt`
  (1,087 games x N=500, seasons 2021-24, week <= 18, seeds via `stable_seed` exactly as
  `run_k1_5a5.py`). 5H measured 1.08 s/game = ~20 min: confirm on the first 100 games and
  report the measured figure, do not rely on it.
- Prints EVERY line in D100's K1 table — pts/team, plays/game, drives/game, go rate, like-for-like
  go rate, off/def penalties per game, punts, FG attempts, 3rd-and-11+ share, non-offensive
  scoring, FD by penalty, broad AND strict tied-drive expiry — each with sim, actual, diff, the
  tolerance and PASS/FAIL. Every "actual" is computed from PBP in the same script; every
  tolerance is IMPORTED or read from where the suite already defines it
  (`nfl/sim/tests/`, `derive_engine_targets.py`). If a line has no tolerance defined anywhere,
  print `tolerance: none defined` — do NOT invent one.
- Also writes the per-game rows to `research/nfl_sim/<name>_rows.parquet` (committed; it must be
  small — per-game means, not per-sim) so Cowork can rebuild the table without re-simulating.
- Header: engine fingerprint, git describe, UTC time from `date -u`, N, game count.

Run it now on the untouched engine -> `research/nfl_sim/phase5j_k1_before.txt` (+ rows).
CHECK: its pts/team, plays, drives, go rate, penalties must reproduce D100's "Item 2" column /
D102 to the printed precision. Any mismatch is a finding about D100-D102: report it, do not
reconcile it.

Decision entry: D106 (what the generator is, where each tolerance comes from, which lines have none).

## Item 4 — split `Q4_mid` at 180 s, ONE re-fit, re-stamp

Step 0 — CELL SIZES FIRST, before any engine edit. From `build_clock_table`'s own `scrim`
frame, print n for every (outcome_type x score_state) cell in `Q4_mid_a` = 181-300 s and
`Q4_mid_b` = 121-180 s. `MIN_CELL` is 100 and stays 100. 5I found the tied cells already thin
(n = 117 / 138). Today a missing cell falls back to the ALL-GAME parent `p_<score_state>`
(~normal pace) — for a tied offence at 2:30 that is WORSE than the current unsplit cell.
So the fallback order becomes: split cell -> the existing unsplit `Q4_mid` cell (keep building
it) -> `p_<score_state>` -> legacy. Report which cells used which level. No pooling of score
states, no other new cells.

Change, in all THREE places that set the period — `tables.py::build_clock_table` (~531-538),
`engine.py` scalar path (~1576-1577), and both vectorised blocks (~2429-2444, ~2696-2705) — and
prove by a test that the scalar and vectorised paths label the same (qtr, clock) grid identically.

PRE-REGISTERED (write before running anything after Step 0):
- P4. Sim sec/play, offence tied or trailing 1-8, 2023, 272 games, N=200, measured with the
  late-snap instrumentation from `diag/5h` (commit 07fbed6) cherry-picked onto a scratch
  branch `diag/5j` that is pushed but NEVER merged: pass 121-180 within 2.0 s of real 12.63;
  run 121-180 within 2.0 s of 20.05; pass 181-300 within 2.0 s of 20.17; run 181-300 within
  2.0 s of 32.48. Extend `run_verify_5h.py::late_clock`'s buckets to [0,40,120,180,300] in a
  NEW committed script `nfl/sim/run_verify_5j.py`; do not edit the 5H one.
- P5. Broad tied-drive expiry, 11 salts (same harness as `run_metric_noise_5h.py`): mean falls
  from 0.099 to between 0.085 and 0.095. Cowork's LAST prediction on this metric
  (< 0.081) FAILED, so this one is deliberately modest. The 5A-9 test compares to 0.050 and
  will very likely STAY RED. That is the correct outcome. Do not relax it, do not tune toward it.
- NULL CONTROLS, from `run_k1_table.py` after vs `phase5j_k1_before.txt`, against the 5H seed
  SDs: go rate moves < 0.002 (SD 0.00052); off penalties/game < 0.06 (SD 0.018); def
  penalties < 0.03 (SD 0.007); pts/team < 0.15; Q1-Q3 plays per game < 0.2. Also report
  drives/game (23.8 vs real 21.9) and the 0-40 s bucket (+3.6 s): this item is NOT expected to
  fix either; say what they did.
If a prediction does not hold, say so in the first line of D107. Nothing is tuned to rescue it.

Then, in this order, pasting each trace:
1. Full suite. Summary + every failing assertion with its value. For each red, state whether it
   is red at the parent commit WITH THE SAME VALUE (run it there; do not recall it).
2. `python3 nfl/sim/run_week.py --week 2 --as-of 2026-09-20T15:30:00Z` BEFORE the re-fit: must
   show SIM PRICES SUPPRESSED and NO ranked leg (fingerprint mismatch vs `fit_5i`). If it ranks,
   STOP — bigger finding. Do NOT commit anything under `nfl/data/sim/outputs/week=2026_02/` from
   the worktree: main holds the pre-kick Week 2 board of record (`git checkout -- ` that dir after).
3. `python3 nfl/sim/run_fit.py --seasons 2021 2022 2023 2024 --out-dir fit_5j` (check the
   script's usage line first; 5C-2b measured ~90 min on 10 workers — measure and report).
   Paste `fit_meta.json`.
4. `run_cal_maps.py --fit-dir fit_5j`; show `save_calibration` read fingerprints from `fit_meta.json`.
5. Board again (same command): ranks, `sim_pricing_enabled` true. Paste the trace.
6. `run_k1_table.py` -> `phase5j_k1_after.txt` (+ rows). `run_k4.py` on `fit_5j`, rows committed
   this time. Report K4 as a measurement. **Do not interpret it as validation.**

Decision entry: D107 — cell sizes and fallback levels, P4/P5 held or not, null controls, the new
fingerprint, K1 before/after with every line that crossed a tolerance in EITHER direction.

---

## What this work order does NOT do

- It does not merge to `main`. Cowork verifies: recomputes K1 from the committed rows files,
  runs each new test against main's code to see it fail, checks nothing in `nfl/sim/tests`
  changed except the three new files.
- Items 1-2 do not change the engine fingerprint and may merge before Thursday's Week 3 board.
  Items 3-4 change it. The prospective sim-vs-ticket comparison starts Week 3 and every logged
  leg carries its fingerprint; a mid-season move from `fit_5i` to `fit_5j` is a fit on
  2021-24 only and tunes nothing on 2026, but the two are different objects and are reported
  separately, never pooled silently.
- It does not touch drives/game, the 0-40 s clock, first-down-by-penalty, half-the-distance,
  or untracking `nfl/data/pbp/depth_charts.parquet`. Measured and logged; next order.
- It does not close the calibration-transfer gate. The sim prices no ticket.

## Closing

Append to `logs/agent_sessions.md` (`git add -f`), timestamp from `date -u`. Separate what each
command RETURNED from what it MEANS. List what was NOT DONE and what is UNVERIFIED — including
anything you could not make fail on main.
