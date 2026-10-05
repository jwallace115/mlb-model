# NHL sim — S-WO4b verification (Cowork, 2026-09-29 23:53Z)

Branch nhl/sim-s4b:
- b18872088 (S40), c11cf38b8 (S41), f607bad75 (S42), 90394c6fa (log).
- Clean diff: 8 files (game_inputs.py, price_games.py, tests, v8 + q, manifest, decisions, log).

## Held
- **Setup:** the manifest check passed. Runtime pre-check: 1.16 s per game at 2k sims, so 2,624 games ≈ 50 min.
- **S40 game_inputs.py:** follows the order's mappings; raises on a missing row or NaN; 3 tests pass.
  q = 0.068513 added to v8 by the generator.
- **S41:** 2,624 games priced; Pinnacle matched 1,156 / 1,138.
- **S42 moneyline:** reproduced exactly by Cowork (decision S43). The engine trails Pinnacle by 0.008 log-loss; A1
  coefficient 0.375, 90% CI [-0.105, 0.854]. **No layer weight.**

## Wrong or not done
- **Totals were priced from a normal approximation, not the simulations.** Every totals number in S42 is invalid
  (`p_push_total` ≈ 0.16 on half-goal lines).
- **Missing:** the totals A1 test, the reliability table, the favourite / underdog and |engine - Pinnacle|
  breakdowns, and the A2 picks. All listed as NOT DONE; the hard rule was broken again.
- **The pre-registration was an expectation, not a test.** It said "the CI will include 0", so "HELD" says nothing
  about the engine.

## What the data says (Cowork)
**The engine is under-confident.**
- Its moneyline logits have 30% less spread than Pinnacle's.
- Calibration slope 1.32 (2023-24) and 1.15 (2022-23, fit).
- The log-loss gap sits entirely in the games where the engine and Pinnacle disagree by more than 5 pts.
- It could be missing information Pinnacle has (rest / back-to-backs, confirmed goalies, injuries), over-shrinking,
  or both.

**Moneyline picks at real median prices:** -3.7% (2023-24), -1.0% (2022-23). No edge.

## Next
S-WO4c:
1. Price totals from the simulations (store the total-goals distribution per game; re-running with the same seeds
   must reproduce every moneyline and puck-line column exactly).
2. Finish S42's missing reports.
3. A calibration map fit on 2022-23 only, applied once to 2023-24.

After that: the A1.3 team modifiers (rest, back-to-back, travel, goalie workload), each kept only if it improves
2023-24 log-loss. Then the holdout (S-WO5).

## CHECKS
- **1b:** inputs are point-in-time (tested since S27).
- **2:** 2023-24 used for evaluation only; no calibration fit on it.
- **3:** prices come from committed code (price_games.py, seed = game_id).
- **4:** picks were checked at real median prices: no edge.
- **5:** by month, games played, and |disagreement| (Cowork); the favourite / underdog breakdown is still owed.
