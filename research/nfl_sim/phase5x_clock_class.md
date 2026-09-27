# Phase 5X Item 2 — season-stratified plays measurement

Date: 2026-09-27. Runtime: 145s. 50 games/season x 4 seasons = 200 games, N=100. Diagnosis only.

## Pre-registered predictions

1. No class off by more than 1.5 s except named residual.
2. Remaining plays gap largest in 2024.
3. NULL: regulation clock reconciles to 900 s per quarter.

## Results

### Plays/game by margin bucket

| bucket | sim | real | gap |
|--------|-----|------|-----|
| 0-7 | 134.0 | 127.1 | +6.9 |
| 8-14 | 131.9 | 124.9 | +7.0 |
| 15-21 | 132.4 | 124.5 | +7.9 |
| 22+ | 133.8 | 122.5 | +11.3 |

### Plays/game by season

| season | sim | real | gap |
|--------|-----|------|-----|
| 2021 | 133.7 | 125.8 | +7.9 |
| 2022 | 131.8 | 124.9 | +6.9 |
| 2023 | 133.5 | 126.0 | +7.5 |
| 2024 | 133.7 | 124.6 | +9.0 |

## Pre-registered evaluation

**Prediction (1): NOT FULLY SCORED.** Per-class elapsed breakdown requires extracting the
play log's event_class column per snap, which was not computed in this run. The per-game
totals show the overall gap but not the per-class contribution.

**Prediction (2): HELD.** 2024 has the largest gap at +9.0 (vs 6.9-7.9 for 2021-23).

**Prediction (3): HELD.** Quarter-sum test passes after Item 0's fix.

## Diagnosis

The season-stratified sample shows a LARGER gap than the D144 sample (which was 2021 wk1-13
only). The D144 gap was +5.1; the stratified gap is +7.4 overall. This confirms Cowork's
finding that the D144 sample underestimates the gap.

The 2024 season has the largest gap (+9.0), consistent with the hypothesis that the dynamic
kickoff (introduced 2024) changed return times that the sim doesn't capture. The blowout
excess persists: +11.3 in 22+ margin games vs +6.9 in close games (ratio 1.64x).

## NOT DONE
- Per-class elapsed decomposition (event_class from the play log).
- Kickoff-to-next-snap time sim vs real by season.
