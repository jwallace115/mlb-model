# LINEUP_AMPLIFIER_UNDERPRICING — Mechanism Hardening Memo

**Frozen:** 2026-04-13  
**Type:** Candidate mechanism hardening — no testing, no implementation

---

## 1. PURPOSE

This memo hardens LINEUP_AMPLIFIER_UNDERPRICING into a precise, falsifiable research candidate. It is not a betting memo and not a test result. It exists to make the idea sharp enough that a future test can either confirm or kill it cleanly.

## 2. MECHANISM CLAIM

Within the ESP=HIGH × SS=FRAGILE universe, the market moves the total upward for the obvious reason: fragile starter under early pressure. But it may still underprice how specific lineup traits amplify damage inside this exact structural state.

The claim is not that good lineups score more (obvious). The claim is that certain lineup characteristics interact with the fragile-starter / high-pressure combination in ways that produce more damage than the market's blended adjustment accounts for. The market prices the pitcher weakness. It may not fully price the lineup-side magnifier on top of it.

## 3. WHAT MAKES THIS IDEA SPECIFIC

This is not "good lineups score more." That is a main effect. This is an interaction claim requiring all three elements:

- **ESP=HIGH:** Repeated early stress creating multiple high-leverage plate appearances
- **SS=FRAGILE:** A starter who may not absorb that stress cleanly
- **Specific lineup traits** that exploit the fragile starter's particular vulnerability pattern

A patient, high-walk-rate lineup facing a fragile starter under early pressure is a different threat than a free-swinging, high-power lineup in the same spot. The market may adjust for "bad pitcher vs good lineup" generically but miss the trait-specific amplification.

**Candidate lineup-trait families** (not yet frozen — named for future test design only):
- **Patience / walk pressure:** OBP-driven lineups that extend at-bats and accelerate pitch counts
- **Contact quality / hard-contact shape:** Lineups with high barrel rates or hard-hit tendencies
- **Handedness mix / platoon structure:** Lineups with platoon advantage against the fragile starter's throwing hand *(lineup-confirmation-dependent)*
- **Sequencing pressure / lineup depth:** Deep lineups where the 6-9 hitters still pose threats, preventing the starter from cruising through soft spots

These are candidates only. Final trait selection must happen before any outcome data is examined.

Lineup card availability varies. Handedness mix and platoon structure require confirmed lineup announcement. Any trait family that depends on confirmed lineups must be flagged as **lineup-confirmation-dependent** in any future test design.

## 4. KEY EMPIRICAL PREDICTION

If the mechanism is true:

1. Within the ESP=HIGH × SS=FRAGILE universe, games where the opposing lineup has stronger amplifier traits should show materially higher full-game totals or overward market-path behavior than games with weaker amplifier traits
2. This difference should persist after controlling for generic lineup quality (e.g., team wRC+ or OPS)
3. The interaction effect should be larger in this universe than board-wide — amplifier traits should matter more here than in ESP=LOW or SS=STABLE territory
4. The pattern should look like a residual interaction, not just a restatement of "better lineup = more runs"

## 5. WHAT WOULD DISPROVE IT

- **No residual interaction:** Once generic lineup quality is controlled, the amplifier-trait effect disappears
- **Main-effect only:** The same lineup traits predict scoring equally well across the entire board, with no special interaction in the ESP=HIGH × SS=FRAGILE universe
- **Absorbed by pitcher quality:** The effect is fully explained by starter weakness metrics (FIP, xFIP, walk rate) without needing lineup-side information
- **Feature fragility:** The result depends on which specific trait family is chosen, and no single family survives cleanly — suggesting the interaction is a feature-selection artifact
- **Seasonal collapse:** The pattern appears in only 1–2 of 4 seasons or is concentrated in a single month

## 6. DATA / FEATURE REQUIREMENTS FOR A FUTURE TEST

Minimum requirements before any test can be designed:

- **Frozen ESP=HIGH × SS=FRAGILE universe definition** (already available from CE V1)
- **Lineup trait families chosen before testing** — selected by structural/theoretical reasoning, not outcome correlation
- **Pregame lineup-level descriptors available PIT-safe** — team-level rolling stats using strict date < game_date
- **Starter fragility descriptors** — already frozen in CE V1 (SS output)
- **Generic lineup quality controls** — team wRC+ or OPS as baseline to isolate interaction residual
- **Full-game total or market-path outcome** for retrospective analysis

Critical constraints:
- All feature construction must be PIT-safe
- Lineup trait selection must be frozen before validation/OOS work
- "Frozen cleanly" means trait families are defined using structural/theoretical reasoning only, without examining any outcome data or validation/OOS splits. If any trait family was selected because it appeared to correlate with runs, totals, or line movement in exploratory analysis, it is not frozen cleanly and must be excluded.
- Line-movement decomposition or feature search creates major leakage risk if done loosely
- Must distinguish pregame lineup amplifiers (known before first pitch) from retrospective realized lineup performance — these are not the same object
- Pregame lineup amplifiers must also be available at the frozen wager decision time, not just before first pitch. If the system wagers earlier than lineup confirmation, lineup-confirmation-dependent trait families may be unusable for that object.

## 7. DISTINCTIVENESS VS OTHER SURVIVORS

**vs SURVIVAL_THRESHOLD_PATH:** Survival-threshold is a scoring-path bifurcation claim — does the starter survive or break? Lineup amplifier is an interaction-pricing claim — given the same structural state, which matchups produce more damage? Survival-threshold is about what happens after the starter cracks. Lineup amplifier is about which pregame matchup structures make cracking more likely and more damaging.

**vs FRONT_LOADED_DISTRIBUTION_SHAPE:** Front-loaded shape is about when run mass appears (early innings vs late). Lineup amplifier is about why some pregame matchup structures produce more total scoring than the market adjusts for. Front-loaded is a temporal claim. Lineup amplifier is a cross-sectional claim.

**vs generic lineup strength:** Generic lineup strength is a main effect that the market already prices. This idea requires the interaction with the specific ESP=HIGH × SS=FRAGILE universe to be underpriced — the lineup traits must matter more here than elsewhere.

**vs generic fragile-starter pricing:** The market already moves the total for obvious fragile-starter risk. This idea claims the lineup-side magnifier on top of that adjustment is still underpriced.

## 8. FALSE-POSITIVE RISKS

- Risk that this is just generic lineup quality in disguise — the "interaction" may collapse once team wRC+ is controlled
- Risk that the effect is fully explained by obvious pitcher weakness metrics
- Risk that trait-family selection becomes a tuning trap — too many candidate traits, too easy to find one that fits
- Risk that line-movement decomposition invites discovery-validation leakage
- Risk that the effect exists broadly and is not specific to this universe
- Risk that the idea becomes too feature-hungry to remain interpretable
- Any future test must report results by season, and by month if the interaction appears concentrated, before the underpricing claim is credible

## 9. GO / NO-GO STANDARD FOR MOVING TO TEST DESIGN

This idea moves to test design only if:

1. The mechanism can be stated precisely (done in this memo)
2. Candidate lineup-trait families can be frozen cleanly — defined by structural/theoretical reasoning only, without examining outcome data
3. The empirical prediction is distinct from main-effect lineup strength
4. Disproof conditions are clear and pre-registered
5. Data requirements are realistic with current infrastructure
6. The idea remains clearly distinct from the other two survivors
7. The future test design pre-registers trait families and interaction definition before examining validation/OOS outcomes

Post-hoc trait selection would invalidate the test.

If any of these cannot be met: **NO-GO — close before testing.**

## 10. STATUS

LINEUP_AMPLIFIER_UNDERPRICING is preserved as a hardened candidate mechanism only. It is not a signal, not a betting object, and not evidence of edge. No live or shadow object behavior has been changed.

Any future test would require a separate approved prompt. This memo does not authorize testing by itself.
