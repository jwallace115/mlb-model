# K4 (fit_5d1) is contaminated by the actuals defect — do not treat it as a clean gate

Cowork audit, 2026-09-18, against `research/nfl_sim/k4_rows_fit_5d1.parquet`
(72,897 legs, 2023-24) committed in `678cea69c`.

## What reproduces

The doc table in `phase5d1_usage_provenance.md` reproduces EXACTLY from the committed
row-level file under `raw_side = devig_side * (1 + 2*vig)`, i.e. `vig` is the per-side
half-margin and the two-way overround is ~1.069 (~ -115/-115). Realistic for props.
Every cell matches to 0.1pp. The row-level file is real evidence and the arithmetic is sound.
There are no pushes to mishandle here: 72,893 of 72,897 lines are half-point.

## What the write-up missed

`phase5d1_usage_provenance.md` concludes "No family is reliably positive on both sides" and
dismisses its positive cells as "inside noise (small N, no persistence across seasons)".
That reasoning was applied to the MODEL-FILTERED cells only. The flat table printed
directly above it contains a cell that was never tested:

**rush_att blind UNDER = +4.5%, N=2,364, t = +2.32, and it persists in both seasons
independently: 2023 +3.9% (N=1,103), 2024 +5.0% (N=1,261).**

It is the only family with a positive blind side. Every other family's blind under runs
-1.3% to -5.2%, t = -0.52 to -9.88.

## It is a grading artifact, not an edge

Split the rush_att under by position and by line:

| position | N | under ROI | under hit | mkt no-vig | edge |
|---|---|---|---|---|---|
| QB | 722 | **+18.2%** | 63.3% | 50.1% | **+13.2pp** |
| RB | 1,637 | -1.8% | 52.3% | 49.8% | +2.5pp |

| line | N | edge |
|---|---|---|
| <=5.5 | 671 | +12.0pp |
| 6-10.5 | 536 | +6.6pp |
| 11-15.5 | 818 | +2.7pp |
| 16-20.5 | 331 | -0.1pp |
| >20.5 | 8 | -1.1pp |

The edge is entirely in QBs, decays monotonically as the line rises, and is gone by the
line range where RB volume lives. That is the signature of **kneel-downs being excluded
from graded rushing attempts**. Kneels are official rushing attempts; dropping them
understates QB rush_att by 1-3 per game, and unders on a 3.5-5.5 line then hit far too
often. ChatGPT audit #2 already documented this exact defect ("actuals: kneels excluded,
2-pt runs included, spikes excluded") and 5D-3 is scheduled to fix it. K4 was computed with
the broken grader and reported as clean.

The same fingerprint appears across families — under-hit minus market no-vig implied:

    rush_att +5.84pp | pass_att +2.67 | receptions +1.74 | rush_yds +1.56
    rec_yds  +0.66   | pass_td  +0.44 | pass_yds   +0.15 | pass_cmp -0.34

Count markets skew under, continuous markets do not. pass_att at +2.67pp is consistent with
**spikes excluded from pass attempts** — the second defect named in the same audit line.

## Consequence

1. K4 from fit_5d1 is NOT a deployment gate (Checks 3 and 4: the graded object does not use
   official stat definitions, so the research object is not the live object).
2. Re-run K4 only after 5D-3 lands `actuals.py` on official definitions. Any conclusion about
   count families (rush_att, pass_att, receptions) from this run is provisional.
3. This is K4 working. It surfaced a grader defect. The wrong read is "the sim has a QB
   rush-att under edge"; the right read is "the grader is broken and K4 caught it."
4. Aggregate hiding (Check 5): the family aggregate and the symmetry check both look fine
   while the defect sits in one sub-regime. The symmetry check is near-vacuous here — betting
   both sides of one line sums to -(two-way margin) almost by construction, so 6/8 passing is
   not evidence of correct grading.

## Also open

- The 5D-1 PIT test was never written. `test_usage_5b.py::test_pit_byte_identity_2024_wk10`
  (mtime 09-17 21:12, predates 5D-1) passes `d["active"]` UNTRUNCATED to both builds, and says
  so: "Active universe and roster universe are NOT truncated". The active universe is where
  depth_order / active_flag / injury_status live — the exact data class D59 repaired. "13/14
  tests pass" is the 5B suite re-run; nothing tests D59/D60/D61.
- D59's recorded test ("2024 byte-identical with and without new-schema depth") proves the
  leak into history is closed and says nothing about whether 2025/2026 depth_order is correct.
- `phase5d1_usage_provenance.md` section "Before/after share deltas (10 most-changed
  player-weeks)" contains no deltas.
