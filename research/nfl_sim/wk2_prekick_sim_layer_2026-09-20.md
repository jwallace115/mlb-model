# Week 2 pre-kick sim layer — UNSCORED dry run (2026-09-20)

Board: `nfl/data/sim/outputs/week=2026_02/` generated 2026-09-20T15:50:02Z on main, engine
`7f3d96900218c014` (`fit_5i`), 15 games, N=5,000, 15/15 converged, 9.7 min on the Mac. Lines: Hard
Rock, snapshot 15:00:09Z; props pull 15:00:10Z (tag close). All games un-kicked (first kick 17:00Z).
Provenance 1a: every input pre-kick. This is NOT a backtest, NOT validation, and gates nothing.
The scored comparison starts Week 3. Nothing here is tuned on.

## 1. Coverage — the sim cannot speak to most ticket legs (defect, ordered in 5J item 3)

Join: ticket candidates `nfl/data/board/week=2026_02/nfl_prop_candidates_20260920T1424Z.parquet`
(two-way rows) to `picks_log.parquet` on (normalised player, family, line).

| market | two-way rows | player in sim | sim number at the book's line |
|---|---|---|---|
| receptions | 153 | 139 | 138 |
| rush attempts | 50 (RB 38 / QB 12) | 36 | 8 |
| pass completions | 28 | 0 | 0 |
| pass attempts | 28 | 0 | 0 |

Cause (read in `run_week.py` ~708-715): RB rush attempts priced only at 4.5/9.5/14.5/19.5; no QB
family. Of the 34 legs placed today, 12 have a sim number
(`nfl/data/board/week=2026_02/placed_legs_sim_layer_20260920T1550Z.csv`).

## 2. Sim vs the book's de-vigged probability (what it RETURNED, not what it means)

146 joined rows, P(over): cal_p - q_over: receptions mean +0.012, SD 0.147 (n=138); rush attempts
mean +0.028, SD 0.289 (n=8). 30 rows differ by > 0.20, 8 by > 0.30. By game the mean runs from
-0.099 (CIN@HOU) to +0.104 (CAR@ATL). Largest: Kaelon Black SF O9.5 rush att sim 0.905 vs book
0.480 while McCaffrey O14.5 is 0.151 vs 0.510; Bijan Robinson O4.5 rec 0.932 vs 0.575 (10 targets
in week 1, share 0.346); DeMario Douglas O3.5 rec 0.893 vs 0.428.
On the 12 placed legs with a number: sim agrees with the picked side on 11; mean book q 0.584,
mean cal_p 0.609.

WHAT IT MEANS: unknown until graded. The book is not truth, but a 0.15 SD against a 7%-hold market
after ONE 2026 game says the sim's share layer moves a long way on one week of targets/carries
(`[PRIOR-ONLY SHARES]` is printed on many of these). Hypothesis to TEST, not a finding: week-1
shares are under-shrunk. Pre-registered check for tonight's grading: among the 30 rows with
|cal_p - q| > 0.20, the book's side wins more often than the sim's. n=30, one week — it can
embarrass the sim, it cannot vindicate either.

NOT DONE: outcomes; any look at the share shrinkage code. UNVERIFIED: that name-normalised joins
missed no player (14 reception players absent from the sim universe were not listed by name).
