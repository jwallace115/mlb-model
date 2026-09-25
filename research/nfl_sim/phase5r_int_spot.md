# Phase 5R Item 4 — Where does an interception land? (DIAGNOSIS ONLY)

Date: 2026-09-25. Runtime: 214s (3.6 min), 200 K1 games, N=100.
No fix in this order.

## Pre-registered predictions

1. Sim interceptions have air yards >= 4 higher than real at the median, OR the engine spots
   the pick at the line of scrimmage rather than at the catch.
2. Sim INT rate per attempt is within 0.3 pts of real (the +0.41 turnovers/game is placement
   plus fumbles, not INT rate).

## Derivation

**Real:** PBP 2021-24 REG, `interception == 1` (1,675 events, 1,561 with complete data).
LOS = `yardline_100` (yards to offense's target EZ). Air yards = `air_yards` (distance of
throw downfield). Return yards = `return_yards` (yards defender ran after catch). Next drive
start = `yardline_100` of the following drive's first scrimmage play. Catch point =
LOS - air_yards.

**Sim:** 200 K1 games (seed 42), N=100, drive_log=True. 32,485 sim INT events. LOS =
`start_yardline` (drive start). End yardline = `end_yardline` (yardline at INT play). Next
drive start = next drive's `start_yardline` in same sim.

## Results

### Next drive start after INT

| metric | sim | real | diff |
|--------|----:|-----:|-----:|
| Mean | 39.9 | 56.0 | **-16.2** |
| Median | 36.8 | 59.0 | **-22.2** |

The sim gives the new offense 16.2 yards more field position than real after an INT.

### Real INT distributions

| metric | p10 | p25 | p50 | p75 | p90 | mean |
|--------|----:|----:|----:|----:|----:|-----:|
| LOS (yl100) | 17.0 | 37.0 | 57.0 | 72.0 | 79.0 | 52.8 |
| Air yards | 2.0 | 6.0 | 13.0 | 22.0 | 35.0 | 15.5 |
| Catch point | 0.0 | 16.0 | 38.0 | 57.0 | 69.0 | 37.3 |
| Return yards | 0.0 | 0.0 | 5.0 | 21.0 | 34.0 | 12.7 |
| Next drive start | 20.0 | 38.0 | 59.0 | 75.0 | 84.0 | 56.0 |

### INT rate

| metric | value |
|--------|------:|
| Real 2021 | 2.20% per attempt |
| Real 2022 | 2.16% |
| Real 2023 | 2.18% |
| Real 2024 | 2.02% |
| Sim | 1.62 INTs/game |
| Real | 1.54 INTs/game |
| Diff | +0.08 INTs/game (~+0.2pp per attempt) |

**Prediction (2): HELD.** INT rate difference is ~0.2pp (within 0.3 threshold). The +0.41
turnovers/game excess (D135) comes from both INT placement (+0.08/game frequency +
16-yard placement error) and fumbles, not an extreme INT rate.

## Mechanism

**Prediction (1): HELD (second clause).** The engine spots the INT at the LINE OF SCRIMMAGE,
not at the catch point. The engine's formula (engine.py:2331-2332):

```
ret = interp(uniform, int_return_yds_q)
yl_new = 100 - (yl_at_LOS + ret)
```

The correct formula accounting for air yards:

```
yl_new = 100 - (yl_at_LOS - air_yards + ret)
```

The engine treats the INT as occurring at the line of scrimmage and adds the return from there.
But in reality, the INT is caught `air_yards` downfield (median 13.0, mean 15.5), so the
catch point is LOS - air_yards. The return starts from the catch point, not the LOS.

This produces an error of exactly the air yards: **expected error = mean air_yards = 15.5 yards;
observed error = 16.2 yards** (close match; the 0.7-yard difference likely comes from the
slight INT frequency excess and the INT rate being non-uniform across field positions).

This is the mechanism behind D135's finding that sim INT drives start 13 yards closer than
real (39.9 vs 52.7). The engine doesn't model air yards on interceptions, so every INT gives
the defense ~15 free yards of field position. Over ~1.6 INTs/game, that's ~25 yards/game of
incorrect field position.

**The fix (not applied):** at the INT event, draw air_yards from a table (or from the pass
depth model if one exists), compute the catch point = yl - air_yards, then apply the return
from there: `yl_new = 100 - (yl - air_yards + ret)`. This would close the 16-yard gap in
post-INT drive starts.

No engine, usage, table, or parameter change.
