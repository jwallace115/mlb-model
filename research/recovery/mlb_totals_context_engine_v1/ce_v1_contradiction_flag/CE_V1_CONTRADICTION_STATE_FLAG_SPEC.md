# CE V1 Contradiction-State Flag — Design Spec

**Object:** CE-V1-CONTRADICTION-FLAG-V1  
**Frozen:** 2026-04-13  
**Type:** Design spec only — no implementation

---

## 1. PURPOSE

This spec defines a lightweight annotation framework for labeling future candidate objects or fired signals as structurally aligned, contradicted, or mixed relative to known CE V1 market-response tendencies. It is meant for object review and characterization, not direct betting.

## 2. WHAT THE FLAG IS

An interpretive label attached during review of future candidate objects or shadow signals. It summarizes whether the object's directional claim (OVER or UNDER) is aligned with or contradicted by the dominant market-response patterns established in Context × MPS Crosswalk V1.

## 3. WHAT THE FLAG IS NOT

- Not a signal
- Not a gate or suppression rule
- Not an activation rule
- Not evidence of edge (alignment does not mean profitable)
- Not evidence an object is invalid (contradiction does not mean wrong)
- Not an auto-execution or auto-kill mechanism

## 4. FROZEN FINDINGS USED

From Context × MPS Crosswalk V1 findings memo:

- **SS** is the strongest differentiator: STABLE → -17pp underward number asymmetry; FRAGILE → near-zero
- **ESP** shows the clearest directional gradient: LOW → -10pp/-6pp underward; HIGH → -3pp/+2pp near-neutral
- **WPL** is the strongest mechanism variable: LOW → 52% number moves; HIGH → 47% juice-only
- **ESP × SS** is the most differentiated interaction: ESP=HIGH × SS=FRAGILE is the only overward-number-leading cell (25%)
- **Baseline underward bias:** 51.4% underward vs 41.8% overward — this is the structural reference, not 50/50
- **FRAGILE states are noisy** — dominant family rotates across seasons
- **BRE and BS** have weak standalone gradients and should not drive strong labels alone

## 5. FLAG STATES

| State | Meaning | Confidence | Does NOT Mean |
|-------|---------|-----------|---------------|
| STRUCTURALLY_ALIGNED | Object's direction matches dominant CE V1 response tendency | Moderate descriptive support | The object has edge |
| STRUCTURALLY_CONTRADICTED | Object's direction opposes dominant CE V1 response tendency | Moderate descriptive concern | The object is wrong |
| STRUCTURALLY_MIXED | CE V1 outputs point in conflicting directions or effects are weak | Low confidence either way | The object is uncertain |
| NO_STRONG_LABEL | CE V1 state is too weak, noisy, or data-thin to justify annotation | No label forced | Anything about the object |

**Default is NO_STRONG_LABEL.** A label is only assigned when CE V1 states are strong enough to justify it. When in doubt, do not label.

## 6. DIRECTIONAL LOGIC — OVER-SIDE

An OVER-side object is **STRUCTURALLY_ALIGNED** when:
- ESP = HIGH **and** SS = FRAGILE (the only overward-number-leading cell)
- Or: ESP = HIGH **and** WPL = HIGH (near-neutral asymmetry, juice-only resolution favoring over-side)

An OVER-side object is **STRUCTURALLY_CONTRADICTED** when:
- SS = STABLE (dominant response is -17pp underward — strong structural headwind)
- Or: ESP = LOW **and** SS = STABLE (strongest underward cell at 32%)
- Or: WPL = LOW **and** SS = STABLE (underward number dominance compounding)

An OVER-side object is **STRUCTURALLY_MIXED** when:
- SS = MODERATE with conflicting ESP or WPL signals
- Or: ESP = HIGH but SS = STABLE (gradient pulling opposite directions)

**NO_STRONG_LABEL** applies when:
- SS = FRAGILE without ESP = HIGH (FRAGILE alone is too noisy across seasons)
- BRE or BS standalone without SS or ESP support
- Any state where the crosswalk gradient was < 5pp asymmetry shift

## 7. DIRECTIONAL LOGIC — UNDER-SIDE

An UNDER-side object is **STRUCTURALLY_ALIGNED** when:
- SS = STABLE (strongest underward state: -17pp number asymmetry)
- Or: ESP = LOW **and** SS = STABLE (32% underward number dominance)
- Or: WPL = LOW (strongest underward bias at -11pp, highest number-move propensity)

An UNDER-side object is **STRUCTURALLY_CONTRADICTED** when:
- ESP = HIGH **and** SS = FRAGILE (only overward-number-leading cell)
- Or: ESP = HIGH **and** WPL = HIGH (near-neutral, slight overward juice tendency)

An UNDER-side object is **STRUCTURALLY_MIXED** when:
- SS = MODERATE with ambiguous ESP/WPL
- Or: WPL = HIGH but SS = STABLE (mechanism favors juice-only, but direction still underward)

**NO_STRONG_LABEL** applies under the same rules as OVER-side.

## 8. MIXED / NO-LABEL STATES

The framework should refuse to force a label when:
- The relevant CE V1 state sits in FRAGILE territory without ESP = HIGH confirmation (FRAGILE dominant family rotates across seasons — unreliable anchor)
- Only BRE or BS supports the label without SS or ESP reinforcement (standalone gradients too weak: BRE max swing 4pp, BS max swing 4pp)
- The crosswalk asymmetry in the relevant cell is < 5pp (below descriptive significance)
- Multiple CE V1 outputs point in genuinely opposing directions with similar strength

NO_STRONG_LABEL is the correct default. Forced labeling is worse than no label.

## 9. HOW TO USE THE FLAG LATER

Correct uses:
- Annotate shadow objects during periodic review
- Characterize new candidate objects before validation
- Flag potential false positives (e.g., over signal in SS=STABLE territory)
- Compare object behavior against the 51.4/41.8 structural baseline, not 50/50

Critical implementation requirements (not yet resolved):
- CE V1 outputs used to compute the flag must come from data available at the wager decision time, not from full-pregame state
- The appropriate decision-time snapshot for CE V1 inputs has not yet been frozen
- This must be resolved before the flag is implemented in any live or shadow pipeline

## 10. MISUSE RISKS

- Treating ALIGNED as bullish proof that a signal has edge
- Treating CONTRADICTED as kill criteria that auto-suppresses a signal
- Comparing against 50/50 instead of the 51.4/41.8 structural baseline
- Overusing FRAGILE-state labels as if they are stable (they rotate across seasons)
- Using BRE or BS standalone to drive strong labels (their gradients are too weak)
- Building auto-gating logic from this framework without separate validation

## 11. IDENTITY LOCK

Any change to the following creates **CE V1 Contradiction-State Flag V2**:
- Flag state names or definitions
- Directional logic rules (which states → which labels)
- Which frozen findings are used
- Treatment of FRAGILE states
- Default behavior (NO_STRONG_LABEL as default)

## 12. STATUS

CE V1 contradiction-state labels are design annotations only. They do not constitute signals, gates, or evidence of edge. No live or shadow object behavior has been changed.

This spec is frozen for future object-review use. Implementation, if ever approved, must be separate and must preserve the non-gating role.
