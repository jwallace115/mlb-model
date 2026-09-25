# Phase 5P Item 1 — Why are scoring drives short?

Date: 2026-09-25. Engine fingerprint: `02fbcab6e6ed042e` (unchanged).
Runtime: 713s (11.9 min), 1,087 games x 100 sims, aggregated per game inside the loop.

## Pre-registered predictions (written before looking)

1. Sim TD drives start >= 3 yards closer than real (yards to end zone).
2. Sim yards per play on TD drives is within 0.3 of real.
3. The 1-3-play TD-drive bucket is where the sim's excess sits (sim share higher by >= 3pp).

**Null control:** punt-drive plays per drive sim vs real within 0.1 (known: 4.21 vs 4.18).

If (1) holds and (2) holds, the cause is field position (kick returns / turnover starts), not offence.
If (2) fails upward, the cause is play yardage on scoring drives.

## Derivation

**Sim side:** K1 sample (1,087 REG games, 2021-24), N=100 sims/game, `drive_log=True`. Drive log's
`start_clock` is the quarter clock (engine.py:872). Converted to game seconds:
`(4 - min(qtr, 4)) * 900 + start_clock`. Duration = own game_seconds minus next drive's game_seconds
within the same sim. Start yardline = drive log `start_yardline` (yards to end zone). Plays = drive
log `plays` (scrimmage plays). Per-game aggregates stored in `phase5p_drives_by_game.parquet`.

**Real side:** PBP 2021-24, `season_type == "REG"` filter (1,087 games). `fixed_drive` groups plays
into drives; `fixed_drive_result` gives the ending. Start yardline = `yardline_100` of the drive's
first scrimmage play (`play_type` in {pass, run}). Plays = count of pass + run plays in the drive.
Seconds = max - min `game_seconds_remaining` across all plays in the drive. Yards = sum of
`yards_gained` on scrimmage plays. Explosive = count of scrimmage plays with `yards_gained >= 20`.

## Results

### Mean start yardline (yards to end zone)

| ending   |  real |   sim |  diff |
|----------|------:|------:|------:|
| TD       |  66.3 |  62.7 |  -3.6 |
| FG       |  65.7 |  64.1 |  -1.6 |
| punt     |  75.7 |  75.8 |  +0.1 |
| turnover |  73.3 |  72.7 |  -0.6 |
| downs    |  70.5 |  71.0 |  +0.5 |

**Prediction (1): HELD.** Sim TD drives start 3.6 yards closer (>= 3 threshold).

### Yards per play

| ending   |  real |   sim |  diff |
|----------|------:|------:|------:|
| TD       |  8.17 |  8.52 | +0.36 |
| FG       |  5.76 |  5.68 | -0.08 |
| punt     |  2.67 |  2.67 | +0.00 |
| turnover |  4.88 |  4.62 | -0.27 |
| downs    |  4.30 |  4.22 | -0.08 |

**Prediction (2): FAILED upward.** Sim YPP on TD drives is +0.36 (outside the 0.3 threshold).
The sim's offence is more efficient per play on drives that reach the end zone.

### TD drive play-count distribution (share)

| bucket    |  real |   sim |   diff |
|-----------|------:|------:|-------:|
| 1-3 plays | 0.118 | 0.180 | +0.062 |
| 4-6 plays | 0.243 | 0.253 | +0.010 |
| 7-9 plays | 0.314 | 0.296 | -0.018 |
| 10+ plays | 0.325 | 0.271 | -0.053 |

**Prediction (3): HELD.** The 1-3-play bucket is +6.2pp (>= 3pp threshold). The 10+ bucket
is -5.3pp — the sim has fewer marathon drives and more quick-strike drives.

### TD drives starting inside opponent's 40, per game

| metric | real | sim  | diff  |
|--------|------|------|-------|
| /game  | 0.54 | 0.84 | +0.30 |

The sim generates 56% more short-field TD opportunities per game.

### Explosive plays (20+ yards) per TD drive — real side only

Real: 0.811 per TD drive. Sim: not measurable from drive log (total yards only, no per-play breakdown).

### Seconds per drive

| ending   |  real |   sim |   diff |
|----------|------:|------:|-------:|
| TD       | 224.0 | 196.2 |  -27.8 |
| FG       | 237.5 | 226.2 |  -11.2 |
| punt     | 121.4 | 125.4 |   +4.0 |
| turnover | 111.6 | 104.5 |   -7.1 |
| downs    | 179.0 | 190.2 |  +11.2 |

Consistent with D131 verification table (which had TD 223 vs 197, punt 121.4 vs 125.4).

### Drives per game

| ending   |  real |   sim |  diff |
|----------|------:|------:|------:|
| TD       |  4.73 |  4.81 | +0.08 |
| FG       |  3.33 |  3.42 | +0.09 |
| punt     |  7.86 |  8.85 | +0.99 |
| turnover |  2.25 |  2.52 | +0.27 |
| downs    |  1.22 |  1.53 | +0.31 |

Consistent with D131 verification (punt 7.86 vs 8.83; small sim-side variation from N=100 stochastic noise).

### Null check

Punt drives plays/drive: sim 4.21 vs real 4.18 = diff 0.02. **NULL HOLDS** (within 0.1).

## Diagnosis

**Both causes contribute.** Prediction (1) held and (2) failed upward, meaning
field position AND offensive efficiency on scoring drives are both in play.

**Field position is the primary cause.** Sim TD drives start 3.6 yards closer to the end zone.
The sim generates 0.84 short-field (inside the 40) TD starts per game vs 0.54 real — a 56% excess.
These short fields create the 1-3-play TD drive excess (+6.2pp, prediction 3), which is the
single largest shift in the play-count distribution. A drive starting at the 35 instead of the
65 needs ~30 fewer yards, which at 8+ YPP is 3-4 fewer plays. The 0.30 extra short-field
TD starts per game accounts for roughly half the 0.64-play difference in mean TD drive length
(D131: 7.22 vs 7.86).

**Yards per play is the secondary cause.** The sim's YPP on TD drives is +0.36 above real.
This means sim offences gain more ground per snap on drives that score touchdowns. Over ~7 plays
per TD drive, that is ~2.5 extra yards per drive — a modest contribution. But note that YPP is
*conditioned on the drive ending in a TD*: a drive with one long play is more likely to score,
so the conditioning itself could inflate YPP. The YPP on punt drives is identical (2.67 vs 2.67),
confirming the issue is specific to scoring drives, not a general offensive efficiency bias.

**The short-field excess likely comes from kick returns and turnover field position.** Punt drives
start at the correct yardline (75.7 vs 75.8), so punt-return field position is not the issue.
The candidates are: (a) kickoff returns giving too much field position, and (b) turnovers
(interceptions/fumbles) creating too many short-field possessions. This is measurable from the
drive log's `start_yardline` on the first drive after a scoring play (kickoff return result)
and the start yardline of drives following turnovers, but that analysis requires linking
consecutive drives across possession changes, which is outside this item's scope.

**The freed time becomes extra failed possessions.** The 27.8 seconds released per TD drive
(196.2 vs 224.0) times ~4.8 TD drives = ~134 seconds per game. The ~11.2 seconds released per
FG drive times ~3.4 FG drives = ~38 seconds. Total ~172 seconds. At ~125 seconds per punt drive,
that fills roughly 1.4 extra drives — close to the observed punt excess of +0.99 plus the
turnover (+0.27) and downs (+0.31) excess, totalling +1.57 extra failed possessions.
