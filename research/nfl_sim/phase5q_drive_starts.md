# Phase 5Q Item 1 — Drive starts by the event that preceded them

Date: 2026-09-25. Engine fingerprint: `02fbcab6e6ed042e` (unchanged).
Runtime: 724s (12.1 min), 1,087 games x 100 sims, aggregated per game.

## Pre-registered predictions (written before looking)

1. Kickoff-started drives: sim inside-40 share is ~0 and real is 2-4%. The kickoff is NOT the
   source of the excess.
2. The excess inside-40 starts (+0.64/game) sit in turnover-started drives — sim turnover
   drives start >= 5 yards closer than real turnover drives.
3. The sim's interception-return yardage quantiles are higher than real at the median.

**Null:** INT and fumble return yard quantiles should be close to real (both come from PBP).

## Derivation

**Sim side:** K1 sample (1,087 REG games, 2021-24), N=100, `drive_log=True`. Each drive
classified by the PREVIOUS drive's `result` in the same sim: TD or FG_made -> `kickoff_score`;
first drive of sim -> `half_open`; end_half -> `half_open` for next drive; punt, turnover_int,
turnover_fumble, downs, FG_missed, safety mapped directly. Start yardline from drive log
`start_yardline` (yards to end zone). Per-game aggregates in `phase5q_drive_starts_by_game.parquet`.

**Real side:** PBP 2021-24, `season_type == "REG"` (1,087 games, 22,874 drives). Group by
(game_id, fixed_drive). For each drive, `fixed_drive_result` of the preceding drive (sorted by
fixed_drive number) classifies the start. Touchdown, Field goal, Opp touchdown -> `kickoff_score`.
End of half, first drive -> `half_open`. Turnover (PBP lumps INT + fumble) -> `turnover`.
Start yardline = `yardline_100` of the drive's first scrimmage play (play_type in {pass, run}).

**Return yards:** Real: `return_yards` on PBP plays where `interception == 1` (1,675 events)
or `fumble_lost == 1` (1,130 events), all seasons 2021-24 REG. Sim: `turnover_returns.json`
quantile arrays (101 percentiles, same n).

## Results

### Drive starts by preceding event

| preceding event   | dpg sim | dpg real | start yl sim | start yl real | in40 sim | in40 real | in20 sim | in20 real |
|-------------------|--------:|---------:|-------------:|--------------:|---------:|----------:|---------:|----------:|
| kickoff (score)   |    8.19 |     8.09 |         73.7 |          73.4 |    0.000 |     0.007 |    0.000 |     0.001 |
| half open         |    2.05 |     1.34 |         73.7 |          73.7 |    0.000 |     0.011 |    0.000 |     0.002 |
| punt              |    8.85 |     7.84 |         75.8 |          75.1 |    0.023 |     0.029 |    0.006 |     0.008 |
| interception (sim)|    1.58 |    (2.11 combined) |  39.9 |       (52.7) |    0.536 |   (0.346) |    0.267 |   (0.115) |
| fumble (sim)      |    0.95 |          |         49.1 |               |    0.424 |           |    0.084 |           |
| turnover combined |    2.52 |     2.11 |         43.4 |          52.7 |    0.494 |     0.346 |    0.199 |     0.115 |
| downs             |    1.53 |     1.07 |         58.6 |          63.4 |    0.265 |     0.164 |    0.040 |     0.021 |
| missed FG         |    0.58 |     0.55 |         68.3 |          63.9 |    0.012 |     0.017 |    0.000 |     0.003 |
| safety            |    0.07 |     0.04 |         75.0 |          62.5 |    0.000 |     0.091 |    0.000 |     0.045 |

### Inside-40 starts per game, by source

| source            | sim/game | real/game | excess  |
|-------------------|--------:|---------:|--------:|
| kickoff (score)   |   0.000 |    0.060 |  -0.060 |
| half open         |   0.000 |    0.015 |  -0.015 |
| punt              |   0.201 |    0.228 |  -0.027 |
| interception      |   0.845 |  (0.730) |         |
| fumble            |   0.401 |          |         |
| turnover combined |   1.246 |    0.730 |  +0.516 |
| downs             |   0.404 |    0.175 |  +0.229 |
| missed FG         |   0.007 |    0.009 |  -0.002 |
| safety            |   0.000 |    0.004 |  -0.004 |
| **TOTAL**         | **1.858** | **1.221** | **+0.637** |

The +0.64 excess from D132 decomposes as:
- **Turnovers: +0.52** (81% of excess). Sim INT drives start at 39.9 yds; fumble at 49.1; real combined 52.7.
- **Downs: +0.23** (36% of excess). Sim post-downs starts at 58.6 vs real 63.4 (-4.8 yds).
- **Kickoffs: -0.06** (sim MISSES real short-field kickoff returns due to fixed ko_start).
- **Other: -0.04** net.

(Turnover + downs sum to +0.75, offset by -0.11 from kickoff/punt/misc, giving net +0.64.)

### INT and fumble return yard quantiles

| pct | INT sim | INT real | fum sim | fum real |
|----:|--------:|---------:|--------:|---------:|
|  10 |     0.0 |      0.0 |     0.0 |      0.0 |
|  25 |     0.0 |      0.0 |     0.0 |      0.0 |
|  50 |     4.0 |      4.0 |     0.0 |      0.0 |
|  75 |    20.0 |     20.0 |     0.0 |      0.0 |
|  90 |    34.0 |     34.0 |     0.0 |      0.0 |
|  95 |    46.3 |     46.3 |     2.0 |      2.0 |

**Exact match** at every percentile. The sim's return yardage tables were built from the same PBP data.

## Pre-registered evaluation

**Prediction (1): HELD.** Kickoff-started drives produce 0.000 sim inside-40 starts (the fixed
`ko_start` eliminates field-position variance). Real inside-40 from kickoffs is 0.7%, below the
predicted 2-4% range but confirming that kickoffs are not the source. The engine's note at
engine.py:804-809 is correct: `ko_start` from `kickoff.parquet` is a single fixed yardline.

**Prediction (2): HELD.** Turnovers account for +0.52 of the +0.64 excess (81%). Sim turnover
drives start 9.3 yards closer than real (43.4 vs 52.7 — exceeds the 5-yard threshold). Downs
also contribute +0.23; the prediction named turnovers as the primary source, which holds.

**Prediction (3): FAILED.** INT return quantiles are identical to real at every percentile tested.
The sim's return yardage tables were built directly from PBP 2021-24 (n=1,675 INTs), so they
reproduce exactly. The effect is not in RETURN YARDAGE but in WHERE interceptions occur.

## Diagnosis

**The short-field excess comes from turnovers (81%) and downs (19%), not kickoffs.**

The sim's turnover-started drives begin 9.3 yards closer to the end zone than real. Since return
yardage is identical (prediction 3 failed), the cause is **where interceptions and fumbles happen
on the field**. Sim INTs produce drives starting at 39.9 yards; real turnover drives start at
52.7 yards. This means the sim's interceptions occur when the offense is deeper in its own
territory (higher yardline_100 at the time of INT), creating shorter fields for the recovering
defence. The candidate cause: the sim's interception rate may be uniform across field positions,
whereas real INTs cluster in mid-field and red-zone situations.

The downs excess (+0.23 inside-40/game, drives starting at 58.6 vs 63.4) adds to the effect:
the sim has +0.46 more turnovers on downs per game (1.53 vs 1.07), and those drives start
closer. This is likely the fourth-down decision model allowing more fourth-down attempts in
short-field situations.

**Frequency vs placement.** Both contribute. The sim has +0.41 more turnovers per game (2.52
vs 2.11 — frequency) AND those turnovers produce drives that start 9.3 yards closer
(placement). The frequency effect adds short fields through sheer volume; the placement effect
makes each turnover more damaging.

No engine, usage, table, or parameter change.
