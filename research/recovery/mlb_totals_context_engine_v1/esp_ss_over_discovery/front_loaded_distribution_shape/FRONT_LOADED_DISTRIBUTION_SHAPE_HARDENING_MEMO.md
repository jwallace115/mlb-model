# FRONT_LOADED_DISTRIBUTION_SHAPE — Mechanism Hardening Memo

**Frozen:** 2026-04-14  
**Type:** Candidate mechanism hardening — no testing, no implementation

---

## 1. PURPOSE

This memo hardens FRONT_LOADED_DISTRIBUTION_SHAPE into a precise, falsifiable research candidate. It is not a betting memo and not a test result. It exists to make the idea sharp enough that a future test can either confirm or kill it cleanly.

## 2. MECHANISM CLAIM

Within the ESP=HIGH × SS=FRAGILE universe, run mass may be disproportionately concentrated in the earliest innings (1–3) compared to the broader MLB board. This is a distribution-shape claim, not a higher-mean claim.

The market may recognize that this universe trends higher and move the total accordingly. But it may price the total as if runs are distributed across innings in a roughly normal way. If scoring is actually front-loaded — with innings 1–3 carrying an outsized share of total run mass — the realized scoring shape differs from what a standard total implies, even if the mean is correctly priced. Front-loading changes the variance structure, the path of the game, and possibly the relationship between F5 and full-game totals.

## 3. WHAT MAKES THIS IDEA SPECIFIC

This is not "high early pressure means early runs." That restates ESP. This is a claim about the shape of the inning-by-inning run distribution being structurally different in this universe:

- **ESP=HIGH** creates repeated early stress — not a single bad inning, but sustained pressure across the first few innings
- **SS=FRAGILE** means the starter absorbs that pressure unevenly — some innings leak, some don't, but the fragility concentrates damage in the period before removal
- The combination should produce a run distribution where innings 1–3 carry a larger share of total runs than in normal environments

This is distinct from saying "more runs happen." It says runs happen at a different time, and that timing structure may matter for how totals and F5 markets relate.

## 4. KEY EMPIRICAL PREDICTION

If the mechanism is true:

1. Within ESP=HIGH × SS=FRAGILE games, the share of total runs scored in innings 1–3 should be meaningfully higher than the MLB board-wide baseline
2. This concentration should be continuous — a shift in the distribution shape, not necessarily a branching into two paths
3. The front-loading should remain visible even without imposing a survival/break split (distinguishing this from SURVIVAL_THRESHOLD_PATH)
4. The F5-to-full-game run ratio should behave differently in this universe than board-wide — more of the action should be resolved by the F5 mark
5. The pattern should be present across all 4 seasons, not concentrated in 1–2

## 5. WHAT WOULD DISPROVE IT

- **No front-loading:** The inning 1–3 run share in this universe is not meaningfully higher than the board baseline
- **Generic effect:** The same front-loading exists in all ESP=HIGH environments regardless of SS, or board-wide — not specific to this universe
- **Absorbed by bifurcation:** The apparent front-loading disappears once SURVIVAL_THRESHOLD_PATH's break/survival split is controlled for — front-loading is just a blurred view of the break path, not a separate phenomenon
- **Arbitrary windows:** The result depends on whether you use innings 1–2, 1–3, or 1–4 — no window produces a robust finding
- **Seasonal concentration:** The pattern appears in only 1–2 of 4 seasons or a single month
- **Day/evening confound:** The pattern is driven by the day/evening game mix within the universe rather than the structural state itself

## 6. DATA / FEATURE REQUIREMENTS FOR A FUTURE TEST

Minimum requirements before any test can be designed:

- **Frozen ESP=HIGH × SS=FRAGILE universe definition** (already available from CE V1)
- **Inning-level scoring data:** Runs scored per inning per game (available from MLB Stats API linescore)
- **Board-wide baseline:** Inning-level run share distribution for all MLB games as comparison
- **F5 vs full-game run ratios** for this universe vs board
- **Controls:** Generic ESP-HIGH games without SS=FRAGILE, to isolate the interaction

Critical constraints:
- All feature construction must be PIT-safe
- Inning-level scoring distributions are **retrospective outcome descriptors**, not pregame inputs
- Later test design must distinguish:
  - **Retrospective descriptive confirmation** of front-loading (this is a distributional finding)
  - **Pregame predictors** that would be usable in a live object (requires a PIT-safe proxy)
- These are not the same research object and must not be blurred
- If early-window or inning buckets are used, they must be **frozen before validation/OOS testing**
- Post-hoc choice of inning windows would invalidate the test
- At minimum, a future live object would need a PIT-safe pregame predictor of front-loaded scoring shape, such as expected innings pitched, first-inning run expectation, or lineup ordering depth
- If no credible pregame proxy exists, the idea may remain descriptively valid but operationally unusable as a live object

## 7. DISTINCTIVENESS VS OTHER SURVIVORS

**vs SURVIVAL_THRESHOLD_PATH:** Survival-threshold is a branching claim — the game takes one of two qualitatively different paths depending on a discrete early event. Front-loaded shape is a continuous concentration claim — run mass shifts toward early innings across the entire universe, even before any branching logic is imposed. If front-loading only appears inside the break subpath, then this idea collapses into survival-threshold and should be closed.

**vs LINEUP_AMPLIFIER_UNDERPRICING:** Lineup amplifier is a cross-sectional claim about which pregame matchup structures produce more damage. Front-loaded shape is a temporal claim about when damage occurs within the game. Lineup amplifier asks "which games are most dangerous?" Front-loaded shape asks "when in the game does the danger concentrate?"

**vs generic early-scoring logic:** Generic early scoring says early runs happen. This idea claims the ESP=HIGH × SS=FRAGILE universe has an unusually high share of total run mass in innings 1–3 relative to normal environments — a structural shape difference, not just a level difference.

**vs generic fragile-starter logic:** Fragile-starter logic is a broad weakness claim. This idea is specifically about timing and concentration — not just that fragile starters leak runs, but that they leak them disproportionately early, creating a non-standard scoring shape.

## 8. FALSE-POSITIVE RISKS

- Risk that this is just a reworded ESP main effect with no genuine shape distinction
- Risk that it is fully absorbed by SURVIVAL_THRESHOLD_PATH — front-loading may just be the break path viewed without the split
- Risk that generic early-scoring environments show the same front-loading, making this universe unremarkable
- Risk that inning-window selection becomes a tuning trap (1–2 vs 1–3 vs 1–4)
- Risk that the pattern appears only in 1–2 seasons or specific months
- Risk that retrospective front-loading has no live pregame usefulness — descriptively real but operationally dead
- Risk that the front-loading is driven by the day/evening game mix within the universe rather than the structural state
- Any future test must report results by season, by month if concentration appears uneven, and by day/evening split before the front-loaded-shape claim is credible

## 9. GO / NO-GO STANDARD FOR MOVING TO TEST DESIGN

This idea moves to test design only if:

1. The mechanism can be stated precisely (done in this memo)
2. The empirical prediction is distinct from a simple higher-mean claim
3. The idea remains clearly distinct from SURVIVAL_THRESHOLD_PATH — front-loading must be visible without imposing a survival/break split
4. Disproof conditions are clear and pre-registered
5. Data requirements are realistic with current infrastructure
6. Inning-window definitions can be frozen cleanly — defined by structural reasoning only, without examining validation/OOS outcomes

"Frozen cleanly" means inning windows or early-run buckets are defined using structural/theoretical reasoning only. If the chosen windows were selected because they looked best in exploratory outcome analysis, the hypothesis is not frozen cleanly and should not advance.

If any of these cannot be met: **NO-GO — close before testing.**

## 10. STATUS

FRONT_LOADED_DISTRIBUTION_SHAPE is preserved as a hardened candidate mechanism only. It is not a signal, not a betting object, and not evidence of edge. No live or shadow object behavior has been changed.

Any future test would require a separate approved prompt. This memo does not authorize testing by itself.
