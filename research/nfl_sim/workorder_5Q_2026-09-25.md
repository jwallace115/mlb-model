# Phase 5Q work order — where the short fields come from; where the quoted players' extra receptions come from (DIAGNOSIS ONLY)

Date: 2026-09-25 (UTC). Repo: jwallace115/mlb-model. Scope: `nfl/sim/` and `research/nfl_sim/` only.
Read first: `research/nfl_sim/phase5p_verification_2026-09-25.md`, D132-D134.
Prerequisite on main: `grep -c "^### D134" research/nfl_sim/NFL_SIM_DECISION_v1.md` = 1. If 0, STOP and report.

## Why this order exists

5P found two facts and 5Q asks where each comes from. No fix yet; a fix without the source is a tune.
(a) The sim starts 1.86 drives per game inside the opponent's 40 against 1.22 real (+0.64). Punt-drive starts are
    correct (75.8 vs 75.7), so the excess comes from the OTHER ways a drive starts. Note before looking: every
    kickoff drive in the engine starts at ONE fixed yardline from `kickoff.parquet` (engine.py:804-809,
    `ko_start`), so kickoffs produce no short fields at all - the excess must come from turnovers (+0.27/game,
    return yardage from `int_return_yds_q` / `fum_return_yds_q`), downs, missed kicks, or half/game boundaries.
(b) The sim projects the players the book quotes at +0.25 receptions above the book's mean and +0.28 above
    what they caught in Week 2, uniformly, with team pass volume explaining ~11%. The candidate is the division
    of team receptions: the named players get too large a share; unquoted depth players too little.
Fingerprint `02fbcab6e6ed042e` unchanged at the end. No engine, usage, table or parameter change. No re-fit.

## HARD RULES (as 5P; binding)

1. Branch `eng/5q`, worktree `~/mlb-model-5q`, from origin/main after D134. `main` untouched. Cowork verifies.
2. No existing test, tolerance, threshold, table, parameter or filter is edited. No engine change.
3. Aggregate per game inside loops; never subsample below the stated N; measure runtimes.
4. `GIT_OPTIONAL_LOCKS=0` on every git command. Commit AND push each item before the next
   (`git push -u origin eng/5q`). Each commit carries its `### DNN` entry (D135+), the report file, AND the
   per-game / per-player parquet the report is built from.
5. Every real-side number states its derivation. Pre-registered predictions are written BEFORE looking; a
   failed one is reported as failed. Sim means are compared with the book's MEAN or with actuals, never with
   the book's line (D134).
6. Zero API credits. Do not touch `bets/`, `nfl/pipeline/`, `ncaaf/`, `shared/`.

## Setup

```
cd ~/mlb-model && GIT_OPTIONAL_LOCKS=0 git pull --no-rebase --no-edit --autostash
GIT_OPTIONAL_LOCKS=0 git worktree add ~/mlb-model-5q -b eng/5q
cd ~/mlb-model-5q
for f in ~/mlb-model/nfl/data/pbp/*.parquet; do [ -e "nfl/data/pbp/$(basename $f)" ] || ln -s "$f" "nfl/data/pbp/$(basename $f)"; done
python3 -c "from nfl.sim.calibration import engine_fingerprint as f; print(f())"   # must print 02fbcab6e6ed042e
```

---

## Item 1 — drive starts by the event that preceded them (`run_drive_starts_5q.py`)

K1 sample, N=100, `drive_log=True`, aggregated per game. For every drive, classify how it began from the PREVIOUS
drive's `result` in the same sim (kickoff after TD / after FG made / to open a half; punt; interception; fumble;
downs; missed FG; safety; other) and record its `start_yardline`. Real side from PBP 2021-24 REG: the previous
`fixed_drive_result` in the same game (kickoff after score / half-open from `kickoff` plays; punt; INT; fumble;
downs; missed FG; safety), start = `yardline_100` of the drive's first scrimmage play.
Save `research/nfl_sim/phase5q_drive_starts_by_game.parquet` (game x preceding-event: n, start sum, inside-40 n,
inside-20 n). Report, per preceding event: drives per game sim vs real, mean start yardline, share inside the
40, share inside the 20; and the distribution of INT-return and fumble-return yards (sim table quantiles vs
real PBP `return_yards` on interceptions and recovered fumbles, stated how).
PRE-REGISTERED, write before looking: (1) kickoff-started drives: sim inside-40 share is ~0 and real is
2-4% (the fixed start hides real short fields, i.e. the kickoff is NOT the source of the excess); (2) the
excess inside-40 starts (+0.64/game) sit in turnover-started drives - sim turnover drives start >= 5 yards
closer than real turnover drives; (3) the sim's interception-return yardage quantiles are higher than real
at the median. If (2) fails, name where the excess actually sits. One paragraph: the source, and whether
it is frequency (more turnovers) or placement (returns too long / spot wrong).

## Item 2 — the quoted players' share of team receptions (`run_reception_share_5q.py`)

Two samples, same method:
(A) 2026 Weeks 1-2: the pre-kick boards on the current engine (`phase5m_boards/picks_log_mac.parquet` for
    Week 2; run Week 1 the same way with `--as-of` before its first kickoff, saved beside it) and the
    per-player sim means behind them (the board's player output, stated where it comes from); real =
    `pbp_2026` receptions by player and team.
(B) 2024, 100 seeded games (seed 42, K1's list), N=500 with the player layer ON: the sim's per-player mean
    receptions vs real receptions in that game.
For each team-game: team receptions sim vs real; the share of team receptions to the top-6 players by
sim mean ("quoted-type" players - state the rule) sim vs real; the share to everyone else; and, for the
top-6, mean receptions per player sim vs real by position. Save the per-team-game parquet
`research/nfl_sim/phase5q_reception_share.parquet`.
PRE-REGISTERED: (1) team receptions per game sim vs real are within 0.5 (volume is not the problem);
(2) the top-6 share is >= 3 points higher in the sim than real in BOTH samples (the division is the problem);
(3) the gap is largest at WR. If (1) fails, volume is back on the table and the report says so. Then, read
only: does `_renormalize_measured` (engine.py:381) hand inactive players' shares to the listed players, and how
many players per team are in `active_uni` for a Week 2 game versus how many actually caught a pass? Report
those two numbers; do not change anything.

## Closing

`logs/agent_sessions.md` entry (`git add -f`): RETURNED vs MEANS; runtimes; NOT DONE; UNVERIFIED.
Reports: `research/nfl_sim/phase5q_drive_starts.md`, `research/nfl_sim/phase5q_reception_share.md`.
