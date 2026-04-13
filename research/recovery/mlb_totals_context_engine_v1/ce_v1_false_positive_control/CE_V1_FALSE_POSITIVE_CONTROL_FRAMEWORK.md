# CE V1 False-Positive Control Framework

**Frozen:** 2026-04-13  
**Type:** Review framework memo — no implementation

---

## 1. PURPOSE

This memo defines how CE V1 should be used as a false-positive control layer during future object review. It is not a betting memo. It is meant to reduce overtrust in apparently novel objects by providing a structured way to ask whether a candidate object is actually novel, structurally ordinary, structurally contradicted, or structurally noisy.

## 2. WHAT CE V1 FALSE-POSITIVE CONTROL IS

A structured review framework. CE V1 helps characterize the structural footprint of a candidate object relative to known market-response tendencies (from Crosswalk V1). The goal is understanding — not gating. When a new object claims directional edge, CE V1 helps answer: is this claim structurally unusual, or is it just inheriting what the board already does?

## 3. WHAT IT IS NOT

- Not a signal
- Not a gate or suppression rule
- Not a proof of edge
- Not a kill switch
- Not a substitute for out-of-sample testing
- Not a substitute for forward shadow evidence

## 4. FALSE-POSITIVE FAILURE MODES CE V1 CAN HELP DETECT

**BASELINE INHERITANCE** — Object looks directional but is just tracking the board's baseline underward bias. Detection: compare the object's fired-game directional outcome rate to the 51.4% underward structural baseline, not 50/50. An underward object needs materially more than 51.4%. An overward object needs to overcome the ~10pp structural headwind before its directional claim is credible.

**STRUCTURAL OBVIOUSNESS** — Object appears novel but lives in a state where the market already responds in the same direction. Example: an under object that fires exclusively in SS=STABLE territory, where the market already moves underward 32% of the time by number alone. The object may be rediscovering what the market already prices.

**STRUCTURAL CONTRADICTION** — Object consistently fires against a strong known structural current. Example: an over object that fires in SS=STABLE territory (-17pp underward asymmetry). Not proof the object is wrong — but a flag that it's swimming upstream.

**MECHANISM MISMATCH** — Object claims one mechanism but its CE V1 footprint suggests another. Example: an object claiming bullpen-driven late scoring that actually fires in ESP=HIGH territory (an early-pressure state, not a late-pressure state).

**NOISY-STATE DEPENDENCE** — Object mainly lives in FRAGILE or otherwise weakly stable structural states. SS=FRAGILE dominant family rotates across seasons. Objects concentrated there have weaker structural grounding.

**MODIFIER CONFUSION** — Weak standalone variables (BRE, BS) mistaken for lead drivers. Their crosswalk gradients are 4pp or less. They are context modifiers, not directional anchors.

## 5. CORE REVIEW QUESTIONS FOR ANY FUTURE OBJECT

1. What is the object's CE V1 footprint? (Which SS/ESP/WPL buckets do its fired games inhabit?)
2. Is it living in states with strong known tendencies, or in mixed/noisy territory?
3. What is its contradiction-state label? (ALIGNED / CONTRADICTED / MIXED / NO_STRONG_LABEL)
4. Is its directional claim stronger than the 51.4/41.8 structural baseline?
5. Does its claimed mechanism match the CE V1 states it inhabits?
6. Is it depending mainly on FRAGILE or otherwise noisy states?
7. Is it using BRE or BS as lead evidence when they may only be modifiers?

## 6. HOW TO INTERPRET CE V1 EVIDENCE

**Makes reviewers more cautious:**
- Object is STRUCTURALLY_CONTRADICTED on strong axes (SS, ESP)
- Object's directional rate does not meaningfully exceed the structural baseline
- Object is concentrated in FRAGILE states
- Object's claimed mechanism doesn't match its CE V1 footprint

**Should be noted but not overread:**
- Object is STRUCTURALLY_MIXED or NO_STRONG_LABEL (absence of strong contradiction is not confirmation)
- Object lives in moderate BRE/BS states (weak standalone gradients — note, don't overweight)

**CE V1 can strengthen:** understanding of footprint, whether a claim is ordinary or unusual, clarity about contradiction vs alignment.

**CE V1 cannot confirm:** profitability, durability, market inefficiency.

All interpretation must be relative to the 51.4/41.8 structural baseline, not 50/50.

## 7. WHAT CE V1 EVIDENCE CANNOT RESOLVE

- Whether an object has edge
- Whether a contradicted object is actually bad
- Whether an aligned object is actually good
- Whether an object will survive forward shadow
- Whether timing changes would improve it
- Whether CE V1 explains everything important about the object

CE V1 is one lens. It is not the only lens.

## 8. PRACTICAL REVIEW WORKFLOW

1. **Identify claim:** What side (OVER/UNDER) and what mechanism does the object claim?
2. **Profile footprint:** Pull the CE V1 bucket distribution for the object's fired games (SS, ESP, WPL primarily).
3. **Apply contradiction label:** Using the frozen flag spec, classify as ALIGNED / CONTRADICTED / MIXED / NO_STRONG_LABEL.
4. **Compare to baseline:** Does the object's directional rate exceed the 51.4/41.8 structural baseline by a meaningful margin?
5. **Check mechanism coherence:** Does the claimed mechanism match the CE V1 states where the object fires?
6. **Assess structural novelty:** Is the object ordinary (living in obvious structural territory), contradicted, noisy, or genuinely unusual?
7. **Decide follow-up:** What additional evidence (forward shadow, timing analysis, split stability) is still needed?

**Important:** CE V1 outputs used in review must reflect data available at the object's actual decision time. Full-pregame CE V1 state is appropriate for postmortem and descriptive review only. The appropriate decision-time snapshot has not yet been frozen. This must be resolved before any automated implementation.

## 9. MISUSE RISKS

- Treating contradiction as kill criteria
- Treating alignment as bullish proof
- Comparing to 50/50 instead of the 51.4/41.8 baseline
- Overtrusting FRAGILE-state findings
- Forcing CE V1 to explain more than it can
- Turning the framework into a hidden gate
- Using CE V1 to "win" arguments about an object before forward evidence exists

## 10. STATUS

CE V1 false-positive control is a review framework only. It does not constitute a signal, gate, or proof of edge. No live or shadow object behavior has been changed.

This memo is frozen for future object-review use. Any implementation or process change would need a separate approval step.
