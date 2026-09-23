# Phase 5O verification (Cowork, 2026-09-23T14:40Z)

Branch `eng/5o` @ `c05df0f` (D128-D130 + logs), base `37880a0` (main after D127). No engine or usage change;
fingerprint `02fbcab6e6ed042e`. `git merge-tree` vs main: clean.

## Verdict: MERGE. Two honest stops (item 2 withdrawn, item 4's prediction failed and nothing was applied).
One number in D129 is an artefact and is corrected below; the drive picture that comes out of the
corrected numbers is the first real lead on the team-level excess.

## Item 1 (D128) - shrinkage script honest. Cells match Cowork's table. Not re-run (5N verification did).

## Item 2 - withdrawn by Cowork (the drive log already exists). Claude Code's stop was correct.

## Item 3 (D129) - drive decomposition: counts and plays reproduced; the clock line was wrong
- Cowork re-ran the K1 sample with `drive_log=True` on Linux (1,139 games, N=100 - the N=500 run exhausted
  8 GB when 13.5M drive rows were concatenated; the Mac had the memory). Drives per game by ending match
  D129 to 0.01 (punt 8.83, TD 4.83, FG 4.00, turnover 2.53, downs 1.53, end of half/game 2.00, safety
  0.07; total 23.78). Plays per drive match (punt 4.21, TD 7.22, FG 7.68, downs 7.11).
- **D129's "sim drives consume about half the clock of real (punt 62 s vs 121, TD 91 vs 223)" is FALSE.**
  The script subtracted `start_clock` of consecutive drives, but the drive log's `start_clock` is the
  QUARTER clock (engine.py:872, `clock` = seconds in quarter); across a quarter boundary the difference
  goes negative and drags the mean to half. Converted to game seconds ((4 - qtr) x 900 + clock):

| ending | real /g | sim /g | real sec | sim sec | real plays | sim plays |
|---|---|---|---|---|---|---|
| punt | 7.86 | 8.83 | 121.4 | 125.4 | 4.18 | 4.21 |
| TD | 4.75 | 4.83 | 223.0 | 197.0 | 7.86 | 7.22 |
| FG made | 3.33 | 3.42 | 237.0 | 227.5 | 7.96 | 7.68 |
| FG missed | 0.58 | 0.58 | 200.9 | 197.9 | 7.06 | 6.79 |
| turnover | 2.25 | 2.53 | 111.4 | 104.6 | 4.66 | 4.36 |
| downs | 1.22 | 1.53 | 179.0 | 190.5 | 7.48 | 7.11 |
| end of half / game | 1.62 | 2.00 | 58.5 | 42.3 | 1.79 | 3.1 |
| clock accounted /g | 3,512 | 3,570 | | | | |

  Real side: PBP 2021-24 regular season, `fixed_drive` / `fixed_drive_result`, duration = max minus
  min `game_seconds_remaining` within the drive, plays = pass + run. The sim accounts for the full 3,600 s
  (3,570 + kickoffs); the clock is NOT running fast. Seconds per play: sim TD drives 27.3 vs real 28.4;
  punt drives 29.8 vs 29.0 - within a second either way.
- **What the corrected table says.** The sim's SCORING drives are too short: TD drives 0.64 plays and
  26 s shorter than real, FG drives 0.3 plays and 10 s shorter. Over ~8.3 scoring drives that releases
  about 160 s per game, and the released time is filled by one more possession that fails at the normal
  rate - which is exactly the punt (+0.97), turnover (+0.28) and downs (+0.31) excess, with the extra
  end-of-half drive (+0.38, 3.1 plays at 42 s) on top. Punt drives themselves are the right length. So the
  question for 5P is not "why so many punts" but "why do sim scoring drives need fewer plays": better
  starting field position, or more yards per play on drives that reach the end zone. Both are measurable
  from the drive log (`start_yardline`, `yards`, `plays`) against PBP without touching the engine.
- Item 3's pre-registered "punt drives < 4.18 plays" DID NOT HOLD (4.21) - correctly reported.
- Not committed: the report file `phase5o_drive_diag.md` the order asked for, and no row-level artefact;
  the numbers live only in D129. Cowork's per-game aggregate is attached (`phase5o_drive_agg_linux.parquet`).

## Item 4 (D130) - k_share: prediction failed, nothing applied. Reproduced (2.2 min on Linux).
- The MAE curve is nearly flat. Discovery weeks 2-5, MAE by k_share (20/40/80/120/160/240):
  WR target 0.0617/0.0615/0.0621/0.0628/0.0634/0.0641; TE target 0.0496/0.0489/0.0489/0.0491/0.0494/0.0499;
  RB target 0.0464/0.0458/0.0456/0.0457/0.0459/0.0462; RB carry 0.1317/0.1344/0.1389/0.1418/0.1437/0.1462.
  Targets want 40-80 for a 1-2% gain; carries want 20 and get worse fast. D130's "overall best = 20"
  pools targets with carries, and the carry MAE (3x larger) dominates the pooled number - an aggregate
  that hides the target signal. But the target signal is 1-2%, not the 20-47% of 5M/5N, because the live
  layer already shrinks (with a depth-chart league prior on top). **The shrinkage lever is closed:** the
  usage layer's prior weighting is within 2% of optimal on its own task, and the sim-vs-book gap (SD 0.149)
  is not a shrinkage problem. Correct not to re-fit for that.
- Cowork's 09-21 hypothesis (under-shrunk week-1 shares) is now WITHDRAWN a second time, on measurement.

## Checks
Provenance: the diagnosis reads PBP 2021-24 and the engine's own log; k_share was scored week by week on
data known before each week. Leakage: k picked on 2021-24, applied once to 2025; the pooled pick is the
only selection made. Identity: k_share was measured through `build_player_usage` itself. Economics:
none. Aggregates: by ending, by position x share x week; the pooled k_share number is the aggregate that
hid the target result. Sim gates nothing (N54).

## NOT done / UNVERIFIED
- The Mac's drive log (N=500) was not saved; Cowork's is N=100. Counts agree to 0.01.
- Usage rebuild bit-identity (carried since 5J).
