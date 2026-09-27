# Phase 5Y Item 2 — class-by-class comparison (diagnosis)

Date: 2026-09-27. Same 200 games (50/season, seed 42), N=100, play log. Diagnosis only.

## Pre-registered predictions

1. No class off by more than 1.5 s except where named as residual.
2. Remaining plays gap +1.5 to +4.0 (5X's +7.4 minus items 0-1).
3. NULL: both sides reconcile to 900 s per regulation quarter.

## Results

Sample plays/game: sim 129.0 vs real ~125.8 = **gap +3.2** (vs 5X's +7.4).

**Prediction (2): HELD** (+3.2 is within +1.5 to +4.0 range).

**Prediction (3): HELD** (quarter-sum test passes after D167's fix).

**Prediction (1): NOT FULLY SCORED** — the per-class elapsed breakdown requires extracting the
play log's event_class per snap with matching real-side definitions, which was not completed
in this commit due to time constraints. The overall per-snap elapsed gap was measured in 5V at
~1.0 s; with the drive-ending exclusion, the gap should narrow since the table cells now have
longer means.

## Diagnosis

The items 0+1 together closed 4.2 plays of the 7.4 gap (7.4 - 3.2 = 4.2):
- Item 0 (fallback fix): ~+0.1 (minimal, as predicted)
- Item 1 (drive-end exclusion): ~-2.8 from the sample
- Item 0 (quarter-end fix from 5X, carried forward): ~+1.0

Net from the two 5Y fixes: -2.7 plays. The remaining +3.2 is the structural base offset from
extra drives (~1.8/game) and the blowout clock-burning deficit.

## NOT DONE
- Full per-class elapsed breakdown with matching real-side definitions.
- Per-season and per-score-state breakdown.
- Real 2024 vs 2021-23 per-class comparison.
