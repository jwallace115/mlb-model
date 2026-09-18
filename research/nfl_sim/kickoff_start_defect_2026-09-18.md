# The kickoff table's start_yl100 is a hardcoded placeholder — 2024 is 5 yards wrong

Cowork, 2026-09-18, found while pre-checking 5D-2 item 2(c).

## Root cause

`nfl/sim/tables.py` 984-997 does not measure the post-kickoff starting yardline at
all. It writes a literal:

    ko_starts.append({"season": s, "touchback_rate": tb_rate,
                      "start_yl100": 75.0})  # Default; will be refined

The comment two lines above already flagged the risk and was never acted on:
`# Touchback = ball at 25 (since 2023: 30 for new rule? — use empirical)`.
It was never refined. `touchback_rate` IS computed correctly — and the engine
never reads it. `engine.py::_do_kickoff` uses `start_yl100` only, as a single
fixed value for every kickoff (`yl[m] = ko_start`, 6 call sites).

## Measured against PBP (play after each kickoff, same game)

| season | N | mean | median | mode | % at 75 | % at 70 | % at 65 | table | error |
|---|---|---|---|---|---|---|---|---|---|
| 2021 | 2,734 | 74.36 | 75 | 75 (60.5%) | 60.5% | 1.3% | 0.5% | 75.0 | correct |
| 2022 | 2,671 | 74.13 | 75 | 75 (61.8%) | 61.8% | 1.5% | 0.5% | 75.0 | correct |
| 2023 | 2,692 | 74.47 | 75 | 75 (78.0%) | 78.0% | 0.6% | 0.3% | 75.0 | correct |
| **2024** | **2,758** | **69.87** | **70** | **70 (64.8%)** | **2.6%** | **64.8%** | 1.4% | **75.0** | **5 yd too deep** |
| 2025 | 2,779 | 69.04 | 69 | 65 (19.9%) | 4.1% | 5.8% | 19.9% | *missing* | — |

The 2024 dynamic kickoff moved the touchback to the 30. The table still says the
25. Only **2.6%** of 2024 post-kickoff drives actually started where the engine
puts all of them.

## Two consequences

**1. fit_5d1 is affected.** 2024 is one of its four seasons. Every 2024 drive in
that fit started 5 yards deeper than reality — longer fields, fewer scores, more
punts. The isotonic maps in `calibration_v1.json` were fitted on that. This is a
new defect, not one of the ones 5D-1 or 5D-3 addressed, and it means a re-fit is
required on its own merits, independent of the open question about whether
calibration transfers across a rule regime.

Worth checking, not yet claimed: two of the four standing engine reds are
field-position sensitive — `test_t1_4th_down_go_rate` (0.210 vs 0.198, spec
<0.010) and `test_penalties_per_side` (6.20 vs 5.51, spec <0.50). A 5-yard error
in every 2024 drive start is a plausible contributor. Re-measure them after the
fix before assuming they are unrelated.

**2. A single scalar no longer describes 2025.** In 2021-24 the modal start
covered 60-78% of drives, so one number was a defensible approximation. In 2025
the mode covers **19.9%** (sd 9.1): touchbacks to the 35, more returns, wider
spread. Adding one scalar row for 2025 would encode a value that describes a
fifth of the cases.

## What NOT to do

Do not simply "add a 2025 row". The apparent 6-yard jump from 75 to ~69 is an
artifact of comparing 2025 reality against a 2024 table value that was already
wrong. The real 2024 -> 2025 move is 69.87 -> 69.04 — essentially nothing.
Reporting it as "the 25 to the 31" describes a change that did not happen.
