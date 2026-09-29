# NHL sim — S-WO4a2 verification + Cowork S39 (2026-09-29 21:25Z)

Branch nhl/sim-s4: ff53d6a5d (S36), 772586e09 (S37), 33cc37531 (S38), 2b33fc239 (log).
- The history carries duplicated main commits again (a 47-file diff, including NFL and odds files).
- The sim content is squashed onto main by path, not merged.

## Held
**S36 PP-expiry fix works.**
- Checked on merged power-play spans: median 120 s, about 5% over 125 s (was median 124 s, 46%).
- shots and penalties byte-identical; game seconds unchanged.
- Chain rebuilt: v5 5v5 numerator still 178,012; 41 tests pass.

**S37 PP-goal pre-registration HELD** (-5.0%). 8 / 9 bands.

## Wrong
- **S36 reported per-play span medians (12 s) as "PP span" medians.** The statistic was wrong; the fix is fine.
- **Null (d) not run.** It went under NOT DONE: the hard rule was broken again.
- **S38 never measured the simulated side.** Its "implied" 20.5% and its conclusion ("variance too low") had no
  data behind them.
- **r / K / w old → new not pasted,** despite the order asking for it.

## Cowork S39
- Measured the tie trajectory properly.
- Found the two real gaps: no period effect on 5v5, and no late-game slowdown when tied or ahead by 1.
- Replaced the engine's 5v5 "base × v2 multiplier" with measured rates by time bin × score (constants_v8,
  committed generator).

**Realism 2022-23: 9 / 9. 2023-24 (first out-of-sample): 8 / 9** (one-goal share +2.1 pts vs a 2.0 bar).

## Merge decision
**YES: squash the sim paths from nhl/sim-s4 to main.** The engine and constants are ready for team inputs
(S-WO4b). constants_v6.json stays off main (no generator; superseded by v7 / v8).

## CHECKS
- **1b:** point-in-time ratings (tested); engine constants from 2021-23.
- **2:** 2023-24 was used once for a realism check with nothing tuned. S-WO4b's calibration may use only 2022-23.
- **3:** every engine input has a committed generator (v5, v7, v8, ratings.py).
- **4 / 5:** start in S-WO4b.
