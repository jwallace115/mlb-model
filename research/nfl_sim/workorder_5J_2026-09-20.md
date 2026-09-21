# Phase 5J work order — two point-in-time guards, book-line pricing on the board, a K1 generator

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
3. There is no committed script that prints the full K1 table (item 4 below). D99-D101's tables came from a
   gitignored parquet through uncommitted code (5I verification, item 5). `run_k1_5a5.py`
   prints non-offensive scoring and pts/team only; `k1_compare_5a4.py::report` has most of the
   lines but no tolerances and no single entry point.
4. The board prices RB rush attempts only at 4.5 / 9.5 / 14.5 / 19.5 and no QB family at all
   (`run_week.py` ~708-715). Measured on today's pre-kick board: a sim number exists at the book's
   line for 8 of 50 rush-attempt rows and 0 of 56 completions/attempts rows; 12 of Jeff's 34
   placed legs. The Week-3 comparison needs this before Thursday.
NOTHING in this order changes the engine fingerprint. The `Q4_mid` split + re-fit is work order
5K (`research/nfl_sim/workorder_5K_2026-09-20.md`), queued behind this one.

## HARD RULES

1. ALL work on branch `eng/5j` in worktree `~/mlb-model-5j`. `main` is not touched. Cowork
   verifies and merges. The Week 3 board (Thursday) runs on `main`.
2. No existing test, target, tolerance, threshold, `MIN_CELL` or sample filter is edited. New
   tests go in NEW files: `nfl/sim/tests/test_usage_pit_5j.py`, `nfl/sim/tests/test_run_week_5j.py`.
3. No constant is tuned to hit a test. `engine.py`, `anchor.py`, `params_v1.json` and
   `nfl/data/sim/tables/` are NOT edited: `engine_fingerprint()` must print `7f3d96900218c014`
   after every item. No re-fit in this order.
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
- Add `--as-of <UTC ISO>` to the CLI (default: now). It caps which line snapshots AND which props
  pulls may be read (`load_props`: only rows with `pull_timestamp <= as_of`; D69 tag precedence
  unchanged within that), so a past board is reproducible. (Amended 2026-09-21: by Sunday night the
  props archive held eight later `close` pulls; without the props cap a re-run "as of 15:30Z" would
  price Sunday-night lines and items 3's P4 could not be measured.) Record per game in `anchoring_log.parquet` / the board header:
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

## Item 3 — the board prices the line the book actually quotes

MEASURED 2026-09-20 on the pre-kick Week 2 board (main, `fit_5i`, board 15:50Z) against the
ticket candidate table `nfl/data/board/week=2026_02/nfl_prop_candidates_20260920T1424Z.parquet`
(two-way Hard Rock rows), join on (normalised player, family, line):

| market | two-way rows | player in sim | sim number AT the book's line |
|---|---|---|---|
| receptions | 153 | 139 | 138 |
| rush attempts | 50 (RB 38, QB 12) | 36 | **8** |
| pass completions | 28 | 0 | 0 |
| pass attempts | 28 | 0 | 0 |

Cause, read in `run_week.py` ~lines 708-715: rush attempts are priced only at the hardcoded
rungs `for k in [5, 10, 15, 20]` and only for RBs, so a book line of 13.5 / 15.5 / 18.5 never gets
a sim number. Of the 34 legs Jeff placed today, 12 have one. The Week-3+ sim-vs-ticket
comparison cannot run on a third of the legs.

Change (board layer only — `engine.py`, `anchor.py`, `params_v1.json`, tables untouched):
- For every RB, in addition to the four rungs, price P(carries >= floor(L)+1) for each distinct
  two-way rush-attempts line L Hard Rock quotes for that player in the pull `load_props` already
  selected (D69 rule unchanged). Same `_add_leg` call, same tier (`WATCH`, no calibration map —
  `cal_p == sim_p`; do not invent a map). Drop the 0.05-0.95 skip for book-quoted lines only, so a
  quoted line is never silently missing; keep it for the rungs.
- QB rush attempts, pass completions, pass attempts: if `stats` already carries the per-sim
  counts, log them the same way under new families with tier `UNCALIBRATED` and
  `rankable = False`; if it does not, DO NOT add engine counters in this order — report exactly
  which arrays are missing. Either way nothing new is rankable.
- New committed script `nfl/sim/run_board_coverage.py --week W`: prints the table above from the
  newest candidates parquet for the week and `picks_log.parquet`, plus a miss reason per row; takes `--candidates <file>` (default newest)
  (family not simulated / player not in sim universe / line not priced). Reads only; it may read
  `nfl/data/board/` but edits nothing there.

PRE-REGISTERED:
- P4. Re-running the board with `--week 2 --as-of 2026-09-20T15:30:00Z` (item 2's flag; that selects
  the 15:00:10Z props pull the 15:50Z board used), measured against
  `nfl_prop_candidates_20260920T1614Z.parquet` (built from that same pull; pass it explicitly to the
  coverage script): RB rush-attempt rows with a sim number at the book's line go from 8 of 36 to
  >= 34 of 36 (34 RBs are in the sim universe; a player not in it stays a miss, listed by name).
  Receptions stays 128 of 142. (Re-baselined 2026-09-21 by Cowork on the committed board; the table
  above is against the 1424Z candidates from the 14:07Z pull: 8 of 38 and 138 of 153.)
- NULL CONTROL. `engine_fingerprint()` unchanged (`7f3d96900218c014`), and every leg that exists
  on main's 15:50Z `picks_log.parquet` has the SAME `sim_p` to 4 dp when the run uses the same
  lines and seeds. If any differs, this item changed the simulation and that is a defect.
- Do NOT commit the worktree's `nfl/data/sim/outputs/week=2026_02/`; main's 15:50Z board is the
  pre-kick record. Write this item's run to `research/nfl_sim/phase5j_item3_board/` instead.

Tests (`test_run_week_5j.py`, added to item 2's file): a synthetic props frame with an RB line of
13.5 produces a `rush_attempts` leg at 13.5 with `sim_p == mean(carries >= 14)`; FAILS on main.

Decision entry: D106.

## Item 4 — `nfl/sim/run_k1_table.py`: one committed generator for the full K1 table

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

Run it on the branch (engine untouched by this order) -> `research/nfl_sim/phase5j_k1_before.txt`
(+ rows). It is the BEFORE table for work order 5K (the `Q4_mid` split).
CHECK: its pts/team, plays, drives, go rate, penalties must reproduce D100's "Item 2" column /
D102 to the printed precision. Any mismatch is a finding about D100-D102: report it, do not
reconcile it.

Decision entry: D107 (what the generator is, where each tolerance comes from, which lines have none).

---

## What this work order does NOT do

- It does not merge to `main`. Cowork verifies: recomputes K1 from the committed rows files,
  runs each new test against main's code to see it fail, checks nothing in `nfl/sim/tests`
  changed except the two new files.
- It does not change the engine, the tables or the fit: all four items can merge before
  Thursday's Week 3 board, which then runs on the same `fit_5i` object as today's dry run.
- It does not split `Q4_mid` (work order 5K, queued) or touch drives/game, the 0-40 s clock, first-down-by-penalty, half-the-distance,
  or untracking `nfl/data/pbp/depth_charts.parquet`. Measured and logged; next order.
- It does not close the calibration-transfer gate. The sim prices no ticket.

## Closing

Append to `logs/agent_sessions.md` (`git add -f`), timestamp from `date -u`. Separate what each
command RETURNED from what it MEANS. List what was NOT DONE and what is UNVERIFIED — including
anything you could not make fail on main.
