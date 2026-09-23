# Phase 5P work order — why the sim's scoring drives are short; what the sim-vs-book gap is made of (DIAGNOSIS ONLY)

Date: 2026-09-23 (UTC). Repo: jwallace115/mlb-model. Scope: `nfl/sim/` and `research/nfl_sim/` only.
Read first: `research/nfl_sim/phase5o_verification_2026-09-23.md` (the corrected drive table), D129-D131.
Prerequisite on main: `grep -c "^### D131" research/nfl_sim/NFL_SIM_DECISION_v1.md` = 1. If 0, STOP and report.

## Why this order exists

Two measured facts, both without a cause yet:
(a) Team level: sim TD drives take 7.22 plays / 197 s against real 7.86 / 223; FG drives 7.68 / 227 vs
    7.96 / 237. Punt drives are the right length. The freed time becomes one extra failed possession per
    game (punts +0.97 etc.), which is the whole punts/drives excess. Two candidate causes, both readable
    from the drive log against PBP: sim scoring drives START closer, or GAIN more per play.
(b) Player level: sim-vs-book SD(raw) 0.149 on Week 2 receptions. Shrinkage is ruled out (D131). Nobody
    has yet split that gap into "the sim's mean is wrong" vs "the sim's spread is wrong", or by who the
    players are (no prior season; changed team; position), or how much comes from the TEAM pass-volume
    error the player layer inherits.
No engine, usage or parameter change in this order. Fingerprint `02fbcab6e6ed042e` must be unchanged at
the end. No re-fit. Two items.

## HARD RULES (as 5O; binding)

1. Branch `eng/5p`, worktree `~/mlb-model-5p`, from origin/main after D131. `main` untouched. Cowork verifies.
2. No existing test, tolerance, threshold, table, parameter or filter is edited. No engine change.
3. Never reduce N below what the item states, never subsample, never kill a run. If a run needs more memory
   than the Mac has, aggregate per game inside the loop (as Cowork did) instead of concatenating raw rows.
   Measure runtimes and report them.
4. `GIT_OPTIONAL_LOCKS=0` on every git command. Commit AND push each item before the next
   (`git push -u origin eng/5p`). Each item writes its `### DNN` entry (D132+) in the same commit, AND
   its report file, AND a per-game (or per-player) parquet the report is built from - Cowork rebuilds
   the tables from the parquet, not from the report.
5. Every real-side number states its derivation (file, filter, formula). Pre-registered predictions are
   written into the report BEFORE looking; if one fails, say so.
6. Zero API credits. Do not touch `bets/`, `nfl/pipeline/`, `ncaaf/`, `shared/`.

## Setup

```
cd ~/mlb-model && GIT_OPTIONAL_LOCKS=0 git pull --no-rebase --no-edit --autostash
GIT_OPTIONAL_LOCKS=0 git worktree add ~/mlb-model-5p -b eng/5p
cd ~/mlb-model-5p
for f in ~/mlb-model/nfl/data/pbp/*.parquet; do [ -e "nfl/data/pbp/$(basename $f)" ] || ln -s "$f" "nfl/data/pbp/$(basename $f)"; done
python3 -c "from nfl.sim.calibration import engine_fingerprint as f; print(f())"   # must print 02fbcab6e6ed042e
```

---

## Item 1 — why are scoring drives short? (`run_scoring_drives_5p.py`)

K1's sample, N=100, `drive_log=True`, aggregated PER GAME inside the loop. Convert `start_clock` to game
seconds as `(4 - min(qtr,4)) * 900 + start_clock` (the log's clock is the quarter clock - D131). Save
`research/nfl_sim/phase5p_drives_by_game.parquet` (one row per game x ending: n, plays, yards, seconds,
mean start_yardline, and the share of drives starting inside the opponent's 40).
Real side, same shape, from PBP 2021-24 REG (`fixed_drive`, `fixed_drive_result`; start = `yardline_100`
of the drive's first scrimmage play; plays = pass + run; seconds = max - min `game_seconds_remaining`).
Report, by ending (TD, FG, punt, turnover, downs, end of half):
  - mean start yardline (yards to the end zone) sim vs real;
  - yards per play sim vs real;
  - the distribution of plays per TD drive (1-3, 4-6, 7-9, 10+ plays) sim vs real;
  - TD drives that started inside the opponent's 40 (short fields after turnovers/returns), per game;
  - explosive-play share on TD drives (plays of 20+ yards per TD drive) sim vs real.
PRE-REGISTERED, write before looking: (1) sim TD drives start >= 3 yards closer than real; (2) sim yards
per play on TD drives is within 0.3 of real; (3) the 1-3-play TD-drive bucket is where the sim's excess
sits (sim share higher by >= 3 points). If (1) holds and (2) holds, the cause is field position (kick
returns / turnover starts), not offence. If (2) fails upward, the cause is play yardage on scoring drives.
Name the cause in one paragraph. NULL: punt-drive plays per drive sim vs real within 0.1 (already known
4.21 vs 4.18) - if the re-run says otherwise, something in the run is wrong.

## Item 2 — what is the sim-vs-book gap made of? (`run_gap_decomp_5p.py`)

Inputs: `research/nfl_sim/phase5m_boards/picks_log_mac.parquet` (the Week 2 board on the current
engine), `nfl/data/board/week=2026_02/nfl_prop_candidates_20260920T1614Z.parquet` (two-way receptions
and rush-attempt lines with de-vigged q), `nfl/data/pbp/pbp_2026.parquet` (Week 2 actuals),
`nfl/data/sim/ratings/player_usage_weekly.parquet` (which players had a 2025 season, and their team).
For each matched player-line (the 132-146 rows the scorer uses, plus rush attempts):
  - the sim's implied MEAN receptions (from its rung probabilities: the mean of the fitted count
    distribution, stated how) vs the book's line (the book's line is its median);
  - the sim's implied SD vs a book-implied SD (from the over/under price at the line under the same count
    family the sim uses - state the family);
  - the realised receptions.
Save one row per player-line to `research/nfl_sim/phase5p_gap_rows.parquet`. Report:
  - mean(sim mean - book line) and SD of it, overall and by: position; had-2025-season yes/no; same team
    as 2025 yes/no; team pass-attempt error (sim's team pass attempts vs the book's QB pass-attempt line
    where quoted) split into thirds;
  - which is closer to the realised value, the sim's mean or the book's line, per group (n and MAE);
  - the fraction of the 0.149 SD that is removed if the sim's mean is REPLACED by the book's line but the
    sim's dispersion is kept (i.e. is it a mean problem or a spread problem).
PRE-REGISTERED, write before looking: (1) the gap is mostly a MEAN problem - replacing the sim's mean with
the book's line removes more than half of the SD; (2) players with no 2025 season and players on a new
team carry a larger mean error than the rest (>= 0.5 receptions larger); (3) the sim's team pass-attempt
error explains less than a third of the player mean error. Name what the gap is made of in one paragraph.
No fix, no tuning, no parameter change.

## Closing

`logs/agent_sessions.md` entry (`git add -f`): RETURNED vs MEANS; runtimes; NOT DONE; UNVERIFIED.
The report files: `research/nfl_sim/phase5p_scoring_drives.md`, `research/nfl_sim/phase5p_gap_decomp.md`.
