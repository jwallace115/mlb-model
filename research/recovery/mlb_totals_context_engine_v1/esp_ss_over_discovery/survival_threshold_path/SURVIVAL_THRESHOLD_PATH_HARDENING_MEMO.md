# SURVIVAL_THRESHOLD_PATH — Mechanism Hardening Memo

**Frozen:** 2026-04-13  
**Type:** Candidate mechanism hardening — no testing, no implementation

---

## 1. PURPOSE

This memo hardens SURVIVAL_THRESHOLD_PATH into a precise, falsifiable research candidate. It is not a betting memo and not a test result. It exists to make the idea sharp enough that a future test can either confirm or kill it cleanly.

## 2. MECHANISM CLAIM

Within the ESP=HIGH × SS=FRAGILE universe, full-game scoring may follow a path-bifurcation structure rather than a smooth mean shift:

- **Survival path:** The fragile starter absorbs early pressure and survives the first 1–2 innings intact. The game settles into a more normal scoring trajectory. Full-game total lands closer to or below the posted line.
- **Break path:** The fragile starter cracks under early pressure. The game shifts into a broken-game regime — early bullpen exposure, extended at-bats against relievers, and cascading scoring. Full-game total lands materially above the posted line.

The claim is that these two paths produce a **mixture distribution** for full-game totals in this universe, not a single shifted distribution. The market prices a blended expectation. If the break path is sufficiently heavy-tailed, the blended price may systematically underweight the break-path contribution.

## 3. WHAT MAKES THIS IDEA SPECIFIC

This is not "fragile starters give up runs." That is a mean-level claim. This is a distributional-shape claim about conditional paths:

- It requires ESP=HIGH (repeated early stress, not just one bad inning)
- It requires SS=FRAGILE (starter who may or may not absorb that stress)
- The interaction of repeated early tests × uncertain absorption is what creates the bifurcation hypothesis
- A stable starter facing high ESP does not bifurcate — they either hold (likely) or don't (rare). A fragile starter facing high ESP is where the survival/break split is most balanced and most consequential.

## 4. KEY EMPIRICAL PREDICTION

If the mechanism is true, the following pattern should be observable:

1. Within ESP=HIGH × SS=FRAGILE games, split on whether the starting pitcher exits before completing 3 innings (break) vs completes 3+ innings (survival)
2. The full-game total distribution for break-path games should be materially higher-mean and wider than for survival-path games
3. This gap should be larger than the equivalent gap in other ESP × SS cells (e.g., ESP=HIGH × SS=STABLE, where breaks are rarer and less consequential)
4. The combined distribution should look bimodal or heavy-right-tailed, not normally shifted

The prediction is about distributional shape, not just mean difference.

## 5. WHAT WOULD DISPROVE IT

- **No meaningful separation** between early-survival and early-break full-game scoring distributions within the ESP=HIGH × SS=FRAGILE universe
- **Generic effect:** The same survival/break split exists with similar magnitude across the entire board, not specific to this universe
- **Bullpen explains it all:** The full-game scoring difference is fully accounted for by bullpen innings pitched, with no residual path-specific effect
- **No bimodality:** The full-game total distribution in this universe is unimodal and approximately normal — just shifted upward, not bifurcated
- **Definitional fragility:** The result depends heavily on the exact inning cutoff for "survival" (e.g., works at 3 innings but not 2, or only at 4) — suggesting the threshold is an artifact, not a structural feature
- **Seasonal concentration:** The pattern appears in only 1–2 of 4 seasons, or is dominated by a single month

## 6. DATA / FEATURE REQUIREMENTS FOR A FUTURE TEST

Minimum requirements before any test can be designed:

- **Early-window definition:** A pre-registered innings threshold for survival vs break (likely 2 or 3 complete innings by the starter)
- **Starter exit inning:** From pitcher game logs or boxscore data — when the starting pitcher was removed
- **Inning-level scoring:** Runs scored by inning (available from MLB Stats API linescore)
- **Full-game total:** Already available in game_table
- **Bullpen innings pitched:** For controls — already partially available in pitcher_game_logs
- **Conditional distributions:** Full-game total distributions split by survival/break within the ESP × SS universe vs other universes

Critical constraints:
- All features must be constructed PIT-safe when test design begins
- Starter survival/break indicators are **in-game events**, not pregame inputs
- The later test design must clarify whether the hypothesis targets:
  - **Pregame predictors** of survival probability (a pregame object)
  - **Retrospective confirmation** of which path materialized (a distributional-shape finding)
- These are not the same research object and must not be blurred
- Any future test must pre-register the early-window definition and survival/break threshold before examining outcome data

## 7. DISTINCTIVENESS VS OTHER SURVIVORS

**vs FRONT_LOADED_DISTRIBUTION_SHAPE:** Front-loaded shape is a continuous claim — early innings carry disproportionate scoring weight, shifting the mean upward smoothly. Survival-threshold is a branching claim — the game takes one of two qualitatively different paths depending on a discrete early event. Front-loaded is about where runs concentrate. Survival-threshold is about whether the game regime changes.

**vs LINEUP_AMPLIFIER_UNDERPRICING:** Lineup amplifier is a pricing-of-interaction claim — the market underweights how strong lineups exploit fragile starters. Survival-threshold is a scoring-path-state claim — the market underweights the heavy tail of the break path regardless of lineup quality. Lineup amplifier is about who hits. Survival-threshold is about what happens after the starter cracks.

**vs generic bullpen-forced-exposure:** Bullpen exposure is a consequence, not the mechanism. Every early starter exit forces bullpen exposure. The distinctive claim here is that in ESP=HIGH × SS=FRAGILE games specifically, the break path produces cascading scoring that exceeds what simple bullpen-innings-replacement would predict — because the break disrupts game state, not just pitcher quality.

## 8. FALSE-POSITIVE RISKS

- The idea may be a reworded early-run effect with no genuine bifurcation structure
- The path split may be a bullpen-exposure story with extra narrative attached
- The bifurcation may not be unique to ESP=HIGH × SS=FRAGILE — it may exist board-wide
- "Survival threshold" can be defined too flexibly (2 innings? 3? 4?) and become a tuning trap
- The pattern may be concentrated in 1–2 seasons or specific months (e.g., April when starters are building up)
- Any future test must report results by season and by month before the bifurcation claim is credible

## 9. GO / NO-GO STANDARD FOR MOVING TO TEST DESIGN

This idea moves to test design only if:

1. The mechanism can be stated precisely (done in this memo)
2. The empirical prediction is distinct from generic mean-shift logic (defined above)
3. Disproof conditions are clear and pre-registered (defined above)
4. Data requirements are realistic with current infrastructure (they are)
5. The idea remains clearly distinct from the other two survivors (established above)
6. The early-window definition and survival/break threshold are pre-registered before any outcome data is examined

Post-hoc tuning of the early window would invalidate the test.

If any of these cannot be met: **NO-GO — close before testing.**

## 10. STATUS

SURVIVAL_THRESHOLD_PATH is preserved as a hardened candidate mechanism only. It is not a signal, not a betting object, and not evidence of edge. No live or shadow object behavior has been changed.

Any future test would require a separate approved prompt. This memo does not authorize testing by itself.
