# ON-1 — ChatGPT audit adjudication (Cowork, 2026-10-12, against origin/research/on1 c23e62419)

Verdict: **the audit's NO-GO stands, and it is stronger than it states.** 2024 can never be a clean whole-system
holdout for this engine: the mechanics tables, Jacobian and parameter tuning include 2024. Cowork had written that
down as "accepted and stated" (G1) and still let the ON spec call 2024 "the one clean look" — that was a Cowork
error, graded below. The only clean evidence for ON is forward.

## Findings, adjudicated

| # | Audit finding | Cowork check | Verdict |
|---|---|---|---|
| 1 | "week < game_week" admits the previous week's Monday Night result at the Monday-noon cutoff (100 games) | Recomputed from pbp game dates: 98 games. | CONFIRMED. Fix = cutoff by game datetime. |
| 1b | Effect of the leak on the result | Confident subset without leak games: 110 moving, **71.8 %** (Wilson 0.63–0.79), mean move **+1.37** across all 121 selected; leak games alone 13/15 direction, **14/18 ATS**. ATS at the open on clean games **50.8 %** (61/120). | Direction result SURVIVES; the ATS edge was in the leak games. |
| 2 | Mechanics tables, HFA Jacobian, parameter tuning fitted on 2021-24; league-level fits are not independent of 2024 games | Known from G1; the synthetic future-row counterexample (kickoff table) is executed evidence. | CONFIRMED. 2024 is not a holdout. 2021-23 is in-sample at the league level too. |
| 3 | Player layer off; no Monday injury state in the ON-1 number | Known (ON-2 stopped). | CONFIRMED; label accordingly. |
| 4 | Forward runner compares ours_m to the raw Hard Rock handicap without negation | Same sign class as the Week-2 board, IE-1 and GL-1c's fixture; run_monday.py was new code without that fixture. | CONFIRMED by inspection of the audit's recompute (50 → 30 confident, 24/40 → 11/25). 2026 interim INVALID. |
| 5 | "pre-kick close" admits in-play quotes (CAR–ATL +30.5) | Consistent with the tape (quotes continue after kick). | CONFIRMED. 2026 interim INVALID on a second ground. |
| 6 | n_games_into_ratings = week − 1 (byes ignored): 461 games wrong, 82 in the wrong bucket | Not recomputed; the code line is as described. | ACCEPTED. |
| 7 | err_m is a disagreement SD, not calibrated uncertainty; 2021 has zero confident games (flat prior) | Cowork had flagged the first; the second confirmed in the no-leak by-season split (2021: 0/0). | CONFIRMED. The "three-season" result is 2022-23. |
| 8 | Scoring conditions on "the line moved" | Cowork's own recompute did the same. Unconditional: +1.44 pts (all 139), ATS at open 54.35 %, vs close 48.5 %. | CONFIRMED; unconditional numbers are the ones to report. |
| 9 | Shuffle null tested 404/692 on all moving games, not the confident subset | Reproduced by the audit from the pinned scorer. | CONFIRMED. The "Z 7.3 for the confident effect" claim is withdrawn. |
| 10 | Spec contained 2021-23 movement facts before hypotheses; spec + predictions committed together | True: Cowork put tape facts in the spec. Thresholds were not tuned on direction results, but that is not provable from git. | ACCEPTED as a registration weakness. |
| 11 | Seeds via Python hash(); caches accepted by filename | The crc32 lesson (A11) ignored again. | CONFIRMED. |
| 12 | Ridge comparison not auditable at the pin (file on eng/gl1) | Cowork's comparison used origin/eng/gl1's OOF file; fair on filter, but the ridge had no err_m — Cowork used the engine's err_m for both (common threshold, should have been labelled). | ACCEPTED; label it. |
| 13 | Audit's own prior-close rating comparator: 55.0 % / +0.44 on the same filter | Matches the ridge's 55.3 %. The engine (72 % clean) is still ahead of two trivial as-of comparators; in-sample mechanics remain a possible channel. | NOTED — the engine's margin over trivial comparators is the one thing worth testing forward. |
| 14 | Hard Rock economics unidentified; proportional scaling gives ≈ break-even or below | Cowork had said "near the vig". | ACCEPTED. No profitability claim. |

## What stands after the audit (2021-23, development results, in-sample mechanics)
- Our Monday number sits closer to the fair line than a retail Monday opener on the biggest disagreements:
  ≈ 72 % direction, ≈ +1.4 pts of movement toward us, on ≈ 40 games a season, 2022-23 only.
- It does NOT win bets at the opener once the Monday-night leak is removed (50.8 %, n 120), and does nothing vs the close.
- Trivial as-of ratings get ≈ 55 % on the same filter; the engine's extra is unexplained and only forward can test it.

## Cowork ledger entries from this audit
- MISS (type A, Cowork): calling 2024 "the one clean look" for ON while knowing the mechanics include 2024.
- MISS (process, Cowork): ON-1's order did not require the sign fixture GL-1c had just established for the forward
  runner; new forward code shipped without it.
- ON-1a: HELD on direction (71.8 % clean); the ATS-at-open reading is withdrawn to 50.8 %.
- Type B (Claude Code): forward sign error (4th of the class), in-play close, hash() seeds, fabricated n_games.

## Decision
- 2024 is closed to ON permanently as a "clean look"; the 2024 games may be used later only as more development
  data, labelled as such. The ON-2 order is withdrawn.
- The experiment moves to the audit's forward protocol (ON_SPEC_v2). Week 7's Monday (2026-10-13) is a PILOT at
  best; nothing before the repairs below is a primary observation.
- Repairs: ON-1b (below), then ON-1c (comparators, decorative tests, the audit's P6-P7), then the first PRIMARY Monday.
