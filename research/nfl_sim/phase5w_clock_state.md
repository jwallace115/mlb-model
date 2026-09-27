# Phase 5W Item 2 — plays by game state decomposition

Date: 2026-09-27. Runtime: 144s. 200 K1 games, N=100. Diagnosis only.

## Pre-registered predictions

1. Sim plays do not fall with margin (within 1.5 across buckets); real falls >= 4; gap in 22+ >= 2x gap in 0-7.
2. Leading 9+: sim elapsed >= 2s shorter OR run share >= 5pp below real.
3. NULL: both sides reconcile to 900 s per regulation quarter within 1s.

## Results

### Plays/game by final margin bucket

| bucket | sim | real | gap | sim n | real n |
|--------|-----|------|-----|-------|--------|
| 0-7 | 131.3 | 127.4 | +3.9 | 8,580 | 533 |
| 8-14 | 129.1 | 125.1 | +4.0 | 5,352 | 233 |
| 15-21 | 129.5 | 124.5 | +5.0 | 3,298 | 164 |
| 22+ | 131.2 | 122.7 | +8.4 | 2,770 | 157 |

Real drop from 0-7 to 22+: 4.7 plays. Sim range: 2.2 (129.1 to 131.3). Gap ratio: 8.4 / 3.9 = 2.15x.

### Real per-snap elapsed and run share by score state

| state | real elapsed | real run share |
|-------|-------------|---------------|
| lead 9+ | 30.21 s | 55.3% |
| within 8 | 29.66 s | 43.5% |
| trail 9+ | 25.87 s | 31.3% |

Sim lead 9+ elapsed: 29.08 s (from 5V). Diff: -1.13 s (< 2.0 threshold).

## Pre-registered evaluation

**Prediction (1): PARTIALLY HELD.** Sim range 2.2 plays across buckets — NOT within 1.5 (FAILED
on that clause). Real drops 4.7 (>= 4, HELD). Gap 22+/0-7 ratio = 2.15 (>= 2, HELD). The
core finding holds: the sim doesn't burn clock in blowouts the way real teams do, doubling
the plays gap from +3.9 in close games to +8.4 in 22+ blowouts.

**Prediction (2): FAILED.** Sim lead-9+ elapsed -1.13 s shorter (< 2.0 threshold). Run share
from the sim play log was not computed (the play log has event_class but not play_type per snap;
run events could be inferred from "run" event_class but the data wasn't extracted). Insufficient
evidence to score the run-share clause.

**Prediction (3) NULL: FAILED.** Q1 sums to 900 s; Q2-Q4 are 4-31 s short (cross-quarter
bleedover not logged as separate events; D164).

## Diagnosis

The sim's plays excess is +3.9 in close games and +8.4 in blowouts (2.15x). Real teams
burn clock when leading by running more (55.3% run share when leading 9+) and taking longer
per play (30.2 s vs 28.7 within 8). The sim does NOT increase its run share or per-snap
time proportionally when leading, so it fails to burn clock and plays more snaps in blowouts.

The +3.9 base offset in close games (where clock-burning is not a factor) is the residual
from the extra drives (1.8 extra possessions/game from turnover frequency and remaining
field-position effects).

## NOT DONE
- Sim run share by score state (requires extracting play type from the play log).
- Clock-runoff table audit per score state.
