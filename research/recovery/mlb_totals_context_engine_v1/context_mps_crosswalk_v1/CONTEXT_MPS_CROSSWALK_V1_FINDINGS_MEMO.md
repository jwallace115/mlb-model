# Context × MPS Crosswalk V1 — Findings Memo

**Frozen:** 2026-04-13 | **Object:** CROSSWALK-MLBCE-V1-MPS-V1

---

## 1. PURPOSE

This memo preserves the major descriptive findings of Context × MPS Crosswalk V1 and serves as a guardrail for future downstream use. It is not a betting document. It describes how the market tends to respond to structural game states — not where the market is wrong.

## 2. FROZEN FINDINGS TO PRESERVE

- **SS (Starter Stability) is the strongest differentiator.** STABLE starters produce -17pp underward number asymmetry. FRAGILE starters produce near-zero. This 17pp swing is the largest effect in the crosswalk.
- **ESP (Early Scoring Pressure) shows the clearest directional gradient.** LOW ESP has -10pp/-6pp underward asymmetry (number/juice). HIGH ESP nearly neutralizes both. The total swing is ~7-8pp on each axis.
- **WPL (Weather/Park Lift) is the strongest mechanism-of-adjustment variable.** LOW WPL produces 51.8% number moves (highest) and 42.1% juice-only (lowest). The market moves the number in suppressed environments and adjusts juice in lifted ones.
- **ESP=HIGH × SS=FRAGILE is the only cell where overward number movement leads (25%).** This is the sole structural state that overcomes the baseline underward bias.
- **STATIC (~7%) is context-independent.** No context output meaningfully predicts static markets. STATIC appears to be a microstructure phenomenon, not a game-state phenomenon.
- **The board has a persistent underward bias: 51.4% underward vs 41.8% overward.** This is the structural baseline. It is present in every context bucket. Future characterization must compare against this baseline, not 50/50.

## 3. TRUSTWORTHY FINDINGS

- **SS as strongest differentiator:** Clean, monotonic, stable across all 4 seasons. The 17pp swing from FRAGILE to STABLE is large enough to be structurally meaningful and shows no single-season artifact.
- **WPL mechanism split:** Structurally coherent — suppressed environments force number movement because the market has less ambiguity about direction. Stable across seasons.
- **ESP directional gradient:** Real but smaller in absolute terms than SS. The LOW→HIGH swing is 7-8pp vs SS's 17pp. Still the cleanest directional gradient in the crosswalk.

## 4. FINDINGS THAT REQUIRE CAUTION

- **SS=FRAGILE is noisy.** Dominant family rotates across seasons (OW_NUM in 2022-23, UW_NUM in 2024, OW_JUICE in 2025). Do not treat FRAGILE as a clean anchor state.
- **ESP=HIGH × SS=FRAGILE** is descriptively important but sits inside the noisiest structural state. Hold it lightly.
- **BRE and BS are weak standalone** but may still contribute in interactions. Do not dismiss them entirely — their standalone gradients are small, not zero.

## 5. WHAT THE CROSSWALK DOES NOT IMPLY

- It does NOT show where the market is wrong.
- It does NOT imply betting edge.
- It does NOT imply that following the dominant market response is profitable.
- It does NOT turn structural states into betting objects.
- Describing how the market tends to move is not evidence that the market moves incorrectly.

## 6. CORRECT FUTURE USES

- **Object characterization:** describe what structural environment a candidate object fires in
- **False-positive control:** flag objects firing against dominant structural response (e.g., over signal in SS=STABLE territory)
- **Archetype work:** SS and ESP are the primary context inputs for future structural-state classification
- **Baseline comparison:** always compare against the 51.4/41.8 structural baseline, not 50/50

## 7. MISUSE RISKS TO AVOID

- Treating descriptive dominance as evidence of edge
- Comparing future objects to 50/50 instead of the structural baseline
- Overusing FRAGILE states as if they are stable anchors
- Dismissing BRE/BS entirely because standalone gradients are small
- Using the crosswalk to justify a bet without a separate candidate mechanism

## 8. STATUS

MPS remains RESERVED / DATA-BLOCKED. Context × MPS Crosswalk V1 is a descriptive market-behavior map only. No signals have been tested, no predictive value has been claimed, and no changes to the canonical spec have been made.

This memo is frozen as an interpretive guardrail alongside Crosswalk V1. Future downstream use should reference this memo before object-level characterization work begins.
