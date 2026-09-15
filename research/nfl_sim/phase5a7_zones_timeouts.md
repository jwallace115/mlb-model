# Phase 5A-7: 10-yard-zone KM tables, timeouts and kneel policy, measured safety rates

**Executed by Cowork directly, 2026-09-15/16.** All numbers measured in the cloud workspace
on the same 2021–2024 pbp files staged from the Mac; K1 = 1,087 games × N=500 with
`seed_util` seeds (the D15 protocol).

## 1. Ten-yard zones with Kaplan–Meier (D27)

5A-6's KM fix used the v1 five field zones; a 40-yard "midfield" cell still averaged a real
compression gradient (a completion from the 25 is shorter than one from the 55 even when
the goal line does not bind), which showed up as +5% pass yards and a +0.84-yard mean at
the 21–30 bin. `tables.build_pass_table/build_rush_table` now take `zones="z10"` and write
`pass_outcomes_z10.parquet` / `rush_outcomes_z10.parquet` (98 and 82 populated cells of
120; min cell 20). KM tail borrowing chains zone-by-zone toward the goal line
(y10 ← y20 ← … ← y60; y70–y100 use open-field raw gains, yl > 60). The engine's outcome
arrays are (down, dist, 10 zones), filled from z10 with the z5 parent as the thin-cell
fallback (`engine._fill_zone_arrays`); `_zone_idx` is `ceil(yl/10) − 1`.

Per-play check (6 games × 500): completion mean yards from the 21–30 now 10.34 (was 10.82;
actual 9.98); TD rate per completion 0–5: 0.859 (actual 0.843), 5–10: 0.572 (0.527),
10–20: 0.236 (0.214); rushes 0–5: 0.500 (0.431), 5–10: 0.144 (0.126). The goal-line rush
overshoot persists (KM inside the y10 cell is dominated by censored snaps from the 1–3).

The 5A-4 hand scale on deep sack yardage (×0.687) is removed: the y90/y100 cells carry
their own measured sack-yardage quantiles.

## 2. Timeouts and the kneel decision (D28)

Measured (2021–2024 regular season): offensive timeouts after a snap in the last 3:00 of
Q2+Q4 1.78/game, defensive 2.08/game; P(offence timeout | last 30 s, clock running) 0.29–
0.36 in every score state; P(defence timeout | Q4, leading offence, 61–180 s, clock
running) 0.31–0.41. Kneel-downs 1.51/game; P(kneel | leading Q4, 81–120 s, 1st down) is
0.98 with the defence out of timeouts and 0.24–0.27 with any left — the "can I kneel it
out" rule emerges from the data with no arithmetic.

Two new empirical tables: `timeout_policy.parquet` (side × qtr × seconds bucket × offence
score state × clock running; min cell 80, pooled fallbacks) and `kneel_decision.parquet`
(qtr × seconds × defence timeouts remaining × down × situation; min cell 30). Engine:
`to_rem[2, N]` (3 per half, 2 in OT); after every scrimmage play in the last 3:00 of
Q2/Q4 the offence, then the defence, may call a timeout, which switches that play's runoff
to the stopped-clock kind (the clock table's `incomplete` outcome type); the 5A-1
`kneels_avail − 1.0` / 40-second heuristic is deleted — a kneel is a play drawn from the
kneel table, consuming the running-clock runoff for its score state, with the defence
able to stop it.

Result (K1): late-Q2 pass/run snaps 9.08 (actual 9.03; was 8.2), late-Q4 6.20 (5.61; was
4.5), offensive timeouts 1.85 (1.78), defensive 2.16 (2.08), kneels 1.29 (1.51).

## 3. Safety rates in the builder (D29)

The engine carried `0.0221 / 0.0090 / 0.0011` per-play safety rates typed by hand in 5A-4
and scaled by 1/1.84 "because the sim generated too many deep plays", plus two unused
constants in `constants.json`. Deep-play counts now match reality (snaps from the own 20:
7.6 vs 7.9 per game), so `tables.build_constants` measures the raw rates by zone
(98–100: 4.06% of 419 snaps; 95–97: 1.66% of 783; 90–94: 0.20% of 2,460) and the engine
reads them. 12-game sample: 0.063 safeties/game (actual 0.049). The K1 run below predates
this change (it shows 0.035 from the old scaled values).

## 4. K1 (team-level, 1,087 games, N=500; cloud 2,660 s)

| Metric | 5A-6 | 5A-7 | Actual | Note |
|---|---|---|---|---|
| Mean pts/team | 21.79 | **22.49** | 22.39 | by season 22.27/22.65/22.16/22.86 vs 22.98/21.88/21.77/22.91 — flatter than reality |
| Plays/game | 126.8 | 129.8 | 124.5 (+1.5 kneels) | FAIL: +3% volume |
| Drives/game | 22.1 | 22.8 | 21.9 | FAIL: +4% |
| SD margin (pooled) | 14.84 | 15.19 | 14.20 | FAIL |
| P(\|m\|=3) | 8.13% | 7.73% | 14.54% | FAIL — unchanged by any phase |
| P(\|m\|=6) | 5.18% | 5.15% | 7.54% | FAIL |
| P(\|m\|=7) | 7.14% | 6.81% | 7.27% | PASS |
| P(\|m\| ≤ 7) | — | 41.6% | 49.0% | the sim has too few close games |
| Completion yds/game (both teams) | — | 476.7 | 474.2 | PASS (see definition note) |
| Completions/game | — | 43.7 | 43.4 | PASS |
| Yards per completion | — | 10.90 | 10.93 | PASS |
| Rush plays/game | — | 55.5 | 52.5 | FAIL (+3) |
| Yards per rush | — | 4.45 | 4.50 | PASS |
| FG att/game | 3.32 | 3.56 | 3.92 | FAIL (improving) |
| non-4th FG att/game | 0.16 | 0.18 | 0.33 | short |
| 4th-down go rate | 20.7% | 21.0% | 19.8% | within 1.2pp |
| Off TDs/game | 4.80 | 4.90 | 4.73 | +3.6% |
| TDs from ≥ 20 out | 1.13 | 1.16 | 1.13 | PASS |
| Tie rate | 0.73% | 0.74% | 0.28% | 2.6× real |

**Definition correction.** The K1 line "pass yds/team 221" is nflverse pass yards
*including sack yardage*; the engine's `pass_yds` counters are completion yards only. The
two have been compared as if identical since Phase 2A; the earlier "PASS" (223.8 vs 221.0)
was a coincidence of fewer completions. On one definition the sim is right: 43.7
completions × 10.90 yds = 476.7 vs 43.4 × 10.93 = 474.2. The remaining volume excess is
plays (+3 rushes, +1 pass per game) and drives (+0.9), not yardage per play.

## 5. What remains (ordered)
1. **Key-number mass is structural and untouched by everything so far**: |m| ≤ 7 in 41.6%
   of sim games vs 49.0% real; mass at 3 is half. Points, drives, yards and late-half
   management are all now near reality, so the missing close-game mass is not a scoring
   deficit. Next diagnostic (5A-8): final-margin distribution conditional on the margin
   at 5:00 and 2:00 remaining, sim vs actual — is the deficit generated in the last five
   minutes (score-state strategy: trailing-by-3 FG to tie, leading-by-3 clock-killing,
   trailing-by-6 FG to get within 3, 2-pt decisions) or earlier?
2. Volume +3–4% (drives 22.8 vs 21.9): plays per drive match, so the clock is running ~4%
   slow per play overall. Candidate: the clock table's per-play runoff measured between
   scrimmage snaps ignores time consumed by special-teams sequences the sim charges
   differently (kickoffs, punts, FGs are "captured in the cross-play elapsed" — verify).
3. FG attempts 3.56 vs 3.92; non-4th FG 0.18 vs 0.33 — late possessions reach range 2.3
   times/game vs 3.3.
4. Goal-line rush TD overshoot; tie rate 2.6× real (OT rules by season were verified in
   5A; OT scoring behaviour not yet audited).
5. Timeouts outside the last 3:00 (injury/strategic) are not modelled.

## 6. Tests
`nfl/sim/tests/test_engine_5a7.py` (9 tests, spec tolerances): z10 tables populated and
used with fallback; no 0.687 constant; timeout and kneel tables live (perturbation);
late-half snaps within 0.7/0.8; timeouts within 0.4; kneels within 0.4; 21–30 completion
mean within 0.6. Full suite (5A…5A-7, 61 tests, 1,501 s cloud): **59 passed, 2 failed** —
`test_engine_5a3::test_t2_fg_attempts_per_game` (3.65 vs 3.92, spec 0.15) and
`test_engine_5a4::test_penalties_per_side` (offence 6.19 vs 5.51/game, spec 0.5; more plays,
more flags). The 5A-3 go-rate test, the 5A tie-rate test and the 5A offset-continuity test,
all red in 5A-5's run, now pass. Both failures are reported red, not widened.
