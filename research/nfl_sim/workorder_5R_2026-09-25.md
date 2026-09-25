# Phase 5R work order — team tendencies get a prior-season prior and measured shrinkage; ONE re-fit; the board logs its pass volume; the interception spot (diagnosis)

Date: 2026-09-25 (UTC). Repo: jwallace115/mlb-model. Scope: `nfl/sim/` and `research/nfl_sim/` only.
Read first: `research/nfl_sim/phase5q_verification_2026-09-25.md`, D135-D137.
Prerequisite on main: `grep -c "^### D137" research/nfl_sim/NFL_SIM_DECISION_v1.md` = 1. If 0, STOP and report.

## Why this order exists

`nfl/sim/ratings.py::build_tendencies` (lines ~439-461) gives a team-week with no prior week in the season
`proe = 0.0, pace_sec = 28.0, n_plays = 0` - hardcoded, no prior season - and from week 2 on uses the RAW
mean pace of the games played (PROE is shrunk toward 0 with `k_tendency = 200`; pace is not shrunk at all).
Real full-season pace is 34-35 s. The result: the raw sim runs ~140 plays a game in weeks 1-2 (K1 rows,
real ~125), 39-43 pass attempts per 2026 team-game (real 33.9), 26-28 completions (real 20.5), and every
2026 board so far has run on it. The 2021-24 fit absorbed it. This is `start_yl100 = 75.0` again.
Items 1-2 change the tendency tables (part of `usage_fingerprint()` via FIT_INPUT_FILES) and need ONE
re-fit (item 3). Item 4 is diagnosis only.

## HARD RULES (as 5Q; binding)

1. Branch `eng/5r`, worktree `~/mlb-model-5r`, from origin/main after D137. `main` untouched. Cowork verifies.
2. No existing test, tolerance, threshold, `MIN_CELL`, `N` or sample filter is edited. New tests in NEW files
   `nfl/sim/tests/test_ratings_5r.py`, `test_board_5r.py`. The ONLY constants that change are the ones item 2
   measures, and they change to the measured values, recorded with the table that picked them.
3. Nothing is tuned to hit a test. Never reduce N, subsample, skip a test or kill a run. Measure runtimes.
4. `GIT_OPTIONAL_LOCKS=0` on every git command. Commit AND push each item before the next
   (`git push -u origin eng/5r`). Each item writes its `### DNN` entry (D138+) in the same commit, with its
   report and the parquet the report is built from.
5. A diff is not evidence. Every claim of the form "the board now uses X" is shown by an execution trace.
   Pre-registered predictions are written before looking; a failed one is reported as failed.
6. Zero API credits. Do not touch `bets/`, `nfl/pipeline/`, `ncaaf/`, `shared/`.

## Setup

```
cd ~/mlb-model && GIT_OPTIONAL_LOCKS=0 git pull --no-rebase --no-edit --autostash
GIT_OPTIONAL_LOCKS=0 git worktree add ~/mlb-model-5r -b eng/5r
cd ~/mlb-model-5r
for f in ~/mlb-model/nfl/data/pbp/*.parquet; do [ -e "nfl/data/pbp/$(basename $f)" ] || ln -s "$f" "nfl/data/pbp/$(basename $f)"; done
python3 -c "from nfl.sim.calibration import engine_fingerprint as f, usage_fingerprint as u; print(f(), u())"   # engine must print 02fbcab6e6ed042e; record the usage value
```
Anything else: STOP and report.

---

## Item 1 — MEASURE the defect and the board's exposure to it (no change yet)

`run_tendency_audit_5r.py`: (a) from `tendencies_weekly.parquet` and `tendencies_situational_weekly.parquet`,
print by season x week the mean `pace_sec`, `proe`, `n_plays`, and how many team-weeks sit on the week-1
default (pace == 28.0 and n_plays == 0) - for every season 2021-2026; say whether the situational table has
the same default. (b) From `phase5l_k1_after_rows.parquet`: plays, drives, punts per game by week bucket
(1-2 / 3-4 / 5-8 / 9+) sim vs real (real from PBP, derivation stated). (c) Re-run the Week 2 2026 board
(`--week 2 --as-of 2026-09-20T15:30:00Z`) with ONE addition to `run_week.py`: it writes a per-game
`team_volume` table (sim mean pass attempts, completions, rushes, plays per team AFTER anchoring; the book's
QB pass-attempt line where quoted; and, for played weeks, the actual) to the outputs dir next to
`picks_log.parquet`. This is a LOG, not a behaviour change - NULL: the re-run's `sim_p`/`cal_p` are bit-
identical to `phase5m_boards/picks_log_mac.parquet` (1,353/1,353); if not, STOP.
PRE-REGISTERED: (1) every 2021-2026 week-1 team-week is on the default; (2) K1 plays/game in weeks 1-2 exceed
weeks 5+ by >= 8; (3) on the anchored Week 2 board the sim's team pass attempts exceed the book's QB
attempt lines by >= 5 per team on average. Report `phase5r_tendency_audit.md`.

## Item 2 — the tendency builder gets a prior-season prior and a MEASURED shrinkage for pace and PROE

In `build_tendencies`: the prior for (proe, pace_sec) is the team's own PRIOR-SEASON full-season value
(computed by the same function's season-end row; league mean when the team has none - state the fallback),
and both are shrunk as `(n * obs + k * prior) / (n + k)` with n = plays observed so far this season. Week 1
is therefore the prior itself, not 28.0 / 0.0. `k_tendency` stays the PROE constant unless item 2's
measurement says otherwise; pace gets its own `k_pace`.
MEASURE k_pace and k_tendency with the builder's own function (`run_tendency_k_5r.py`): for k in
{25, 50, 100, 200, 400, 800} build the weekly tables for 2021-25, and for every team-week 2..18 score the
projected pace / PROE against that week's realised pace / PROE (from the same PBP definitions); pick each k
on POOLED 2021-24, report the 2025 holdout at the pick vs k=200 (PROE) and vs the current unshrunk rule
(pace). PRE-REGISTERED: (1) k_pace >= 100 (pace is stable; a game is ~60 plays, so one game should carry
well under half the weight); (2) the holdout MAE for week-1 pace falls by more than 40% vs the 28.0 default;
(3) k_tendency's pick is within a factor of 2 of 200 (the existing PROE shrinkage is about right).
Apply the picks in `params_v1.json`; rebuild the tables; print the same season x week means as item 1(a)
after; test in `test_ratings_5r.py`: week-1 rows carry the prior-season value (not 28.0), a one-game week-2
pace lies between the game's raw pace and the prior. Record the new `usage_fingerprint()`. The board will
be SUPPRESSED until item 3.

## Item 3 — ONE re-fit `fit_5r`, re-stamp, K1, K4, suite, board

`run_fit.py --seasons 2021 2022 2023 2024 --out-dir fit_5r` (N per D51), `run_cal_maps.py --fit-dir fit_5r`,
re-stamp, `run_k1_table.py` -> `phase5r_k1_after.txt` (+rows), `run_k4.py --fit-dir fit_5r --output
phase5r_k4.parquet`, full suite (name every red), Week 2 board `--as-of 2026-09-20T15:30:00Z` saved to
`research/nfl_sim/phase5r_boards/picks_log_mac.parquet` with its `team_volume` table, and the Week 3 board
`--week 3 --as-of 2026-09-24T21:30:00Z` saved beside it.
PRE-REGISTERED, write before looking: (a) K1 plays/game falls from 130.3 to <= 127 and weeks 1-2 from
139.7 to <= 131; drives/game from 23.8 to <= 23.0; punts from 8.84 to <= 8.5; (b) K1 pts/team stays within
0.5 of 22.75 (the anchoring absorbs volume, so scoring should not move much) and go_rate / off_pen /
def_pen / fg_att stay within their K1 tolerances of the 5M values; (c) on the Week 2 board, the sim's team
pass attempts come within 2 of the book's QB lines on average, and SD(raw sim_p - q_over) on the 1614Z
receptions candidates falls from 0.149 to below 0.12 (this is the number 5J-5M could not move). If (c)
fails, say so; do not tune. The 5I reds (fd_pen, tied_drives) are expected to remain; any NEW red is
investigated in this item.

## Item 4 — where does an interception land? (DIAGNOSIS ONLY)

`run_int_spot_5r.py`: on 200 K1 games (seed 42, N=100, drive_log=True on the item-3 engine), for every
interception: the line of scrimmage, the air yards of the throw if the engine records them, the spot of the
pick, the return, and the yardline the next drive starts from; real from PBP 2021-24 (`interception == 1`:
`yardline_100`, `air_yards`, `return_yards`, next drive's start). Report the distributions side by side and
the same for turnover-on-downs starts. PRE-REGISTERED: (1) sim interceptions have air yards >= 4 higher
than real at the median, OR the engine spots the pick at the line of scrimmage rather than at the catch;
(2) sim INT rate per attempt is within 0.3 pts of real (the +0.41 turnovers/game is placement plus fumbles,
not INT rate). Name the mechanism. No fix in this order.

## Closing

`logs/agent_sessions.md` entry (`git add -f`): RETURNED vs MEANS; runtimes; NOT DONE; UNVERIFIED (at minimum:
Cowork's Linux bit-identity check of the item-3 boards).
