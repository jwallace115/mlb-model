# MLB W-FAMILY — CLOSEOUT MEMO

**Family Name:** WORKLOAD / DEPTH / HANDOFF ASYMMETRY
**Closeout Date:** 2026-04-20
**Discovery Source:** MLB_BOUNDED_DISCOVERY_PASS_03
**Operator:** Claude (automated research assistant)
**Primary Source of Truth:** LOCAL_MAC

---

## 1. FAMILY STATUS

The W-family (WORKLOAD / DEPTH / HANDOFF ASYMMETRY) is **CLOSED** as an active edge-search family.

Both candidates advanced from Bounded Discovery Pass 03 have been fully tested. Neither produced a confirmed exploitable edge:
- W01: real structural mechanism, but market prices it efficiently (PRESERVE_AS_CONTEXT)
- W02: OOS material reversal, signal does not generalize (SHELVE)

Discovery Pass 03 is exhausted. No further W-family candidates are available.

---

## 2. BRANCH-BY-BRANCH SUMMARY

### W01 — Short-Outing Starter x Depleted Bullpen

| Field | Value |
|---|---|
| **Verdict** | PRESERVE_AS_CONTEXT |
| **Fields** | opp_sp_workload_ip_last_3, opp_bullpen_pitches_last_3 (self-join) |
| **Form** | AND rule: IP <= 4.67 AND bullpen_pitches >= 200 |
| **Flag rate** | 7-9% (selective) |

**Stage results:**
- Discovery: +0.323 gap, N=745 flagged (8.9%)
- Validation: +0.019 gap (94% attenuation)
- OOS: +0.363 gap

**Raw verdict:** ADVANCE with validation-attenuation caveat.

**Key finding:** Real structural mechanism. Market prices 75-94% of it. Residual after closing total adjustment is trivial (+0.080 disc, -0.204 val, +0.023 OOS). Not exploitable under current market conditions.

---

### W01A — Component Dominance Check

| Field | Value |
|---|---|
| **Verdict** | MIXED_INCONCLUSIVE |
| **Parent** | W01 |

**Stage results:**
- Component A (starter alone): +0.247 / +0.008 / +0.297
- Component B (bullpen alone): +0.011 / +0.198 / +0.015
- W01 full: +0.323 / +0.019 / +0.363

**Key finding:** Starter carries ~75% of signal. Bullpen adds ~25% amplification in disc/OOS but is unstable and near-zero in validation. Not cleanly interaction-real, not cleanly component-dominated.

---

### W01B — Economic Reality Check

| Field | Value |
|---|---|
| **Verdict** | PRESERVE_AS_CONTEXT |
| **Parent** | W01 |
| **Bridge** | mlb_w01_market_bridge_v1 (DraftKings closing total) |

**Stage results:**
- Component A residual: +0.017 / -0.188 / -0.009
- W01 full residual: +0.080 / -0.204 / +0.023

**Key finding:** Market already prices the mechanism through closing totals. Residual is small, reverses in validation, and trivial in OOS. W01 is a real mechanism, not a current exploitable edge.

---

### W02 — Command Instability x High Bullpen Usage

| Field | Value |
|---|---|
| **Verdict** | SHELVE |
| **Fields** | opp_sp_command_bb_rate_last_3, opp_relievers_used_last_3 (self-join) |
| **Form** | AND rule: BB rate >= 0.10 AND relievers_used >= 12 |
| **Flag rate** | 5.0% (selective) |

**Stage results:**
- Discovery: +0.450, N=406 (4.9% flag rate)
- Validation: +0.693 (amplified — warning sign)
- OOS: -0.464 (material reversal — decisive)

**Key finding:** Discovery/validation amplification followed by complete OOS sign flip. Validation stronger than discovery is characteristic of regime concentration, not generalizable mechanism. OOS reversal is decisive. No further branches warranted.

---

## 3. FINAL FAMILY CONCLUSIONS

### What is established:

1. The W-family mechanism (starter handoff stress x bullpen depth pressure) is real at the raw structural level
2. The starter fragility component (W01 Component A) showed the most consistent structure across the family (+0.247 / +0.008 / +0.297)
3. The market prices the primary W01 mechanism efficiently through closing totals (75-94% captured)
4. W02 did not survive OOS — regime concentration, not generalizable signal
5. No W-family branch produced a confirmed exploitable edge

### What is NOT established:

1. W01 is not an active deployable edge
2. W02 is not a viable mechanism under current data
3. The bullpen amplification effect is not confirmed stable
4. No W-family signal is approved for production or shadow

---

## 4. OPERATIONAL DISPOSITION

### Do NOT:
- Promote W01 to production
- Promote W01 to shadow edge candidate
- Treat W02 as a mechanism worth retesting without genuinely different theoretical basis
- Claim economic exploitability from current results
- Reopen W01B as if the residual result was inconclusive

### Do:
- Preserve W01 as a future layer / context candidate
- Preserve the carry-forward note on starter fragility Component A as a standalone worth future investigation
- Preserve W02 as a closed branch with known failure mode
- Move active research to a new mechanism family

---

## 5. CARRY-FORWARD NOTES FOR FUTURE USE

### W01 CARRY-FORWARD:

"W01 (short-outing starter risk x depleted bullpen) is a real structural mechanism but not a confirmed exploitable edge. The market prices most of the effect through closing totals. Residual is trivial in discovery, reverses in validation, and near-zero in OOS. Preserve as future layer/context candidate."

### W01 COMPONENT A CARRY-FORWARD:

"The starter fragility component alone (opp_sp_short_outing risk threshold) showed the most consistent structure across the W01 family — disc +0.247 / val +0.008 / OOS +0.297. Not exploitable as currently formulated, but worth revisiting as a standalone signal in a future bounded discovery pass with tighter threshold design."

### W02 CARRY-FORWARD:

"W02 (command instability x high bullpen usage) showed strong discovery and amplified validation but reversed materially in OOS (-0.464). Amplification pattern — validation stronger than discovery — was a warning sign of regime concentration. OOS sign flip is decisive. Shelved. Do not reopen without genuinely different theoretical basis."

---

## 6. HOW W-FAMILY FINDINGS MAY BE USED LATER

The W-family is closed as an active edge-search family, but its findings may inform future work in these ways:

1. **As a context layer in a multi-signal model:** W01's raw structural mechanism is real. If a future model architecture combines multiple confirmed mechanisms, W01's starter-handoff-stress signal could serve as a context feature (not a standalone edge). This would require the model to demonstrate value-add beyond what the market's closing total already captures.

2. **As anti-duplication reference:** Future discovery passes in the WORKLOAD / DEPTH / HANDOFF family must reference this closeout. The specific conjunction patterns tested here (IP x bullpen pitches, BB rate x relievers used) are exhausted. Future candidates must demonstrate genuinely different mechanism claims, not relabeled versions.

3. **As Component A standalone investigation:** The starter fragility component (opp_sp_workload_ip_last_3 <= threshold) showed the most consistent raw signal in the family. A future bounded discovery pass could investigate this as a standalone single-factor signal with tighter threshold design, provided it passes anti-duplication against W01 and acknowledges the market-pricing lesson.

4. **As a regime-sensitivity reference:** W02's amplification-then-reversal pattern (discovery +0.450, validation +0.693, OOS -0.464) is an important reference case for future signals that show validation stronger than discovery. This pattern should be treated as a warning sign in future work.

---

## 7. NEXT RESEARCH DIRECTION

The W-family (WORKLOAD / DEPTH / HANDOFF ASYMMETRY) is exhausted. Active research should move to a new mechanism family.

Options for next bounded discovery pass:
- A genuinely different mechanism family (not WORKLOAD/DEPTH/HANDOFF)
- If returning to starter-related mechanisms, must demonstrate differentiation from W01 Component A, D01, and all prior tested starter-fragility formulations

The orchestration layer remains active. The runtime object and frozen foundation are available for the next pass.

---

## 8. FINAL CLOSEOUT VERDICT

**W-FAMILY CLOSED**

Both candidates from Discovery Pass 03 tested. Both closed without confirmed exploitable edge. W01 preserved as structural context. W02 shelved. Family closed as active edge-search direction. Findings preserved for anti-duplication reference and potential future layer use.

---

*Closeout generated: 2026-04-20*
*Engine stack: MLB_ENGINE_V1_FOUNDATION + MLB_RESEARCH_ORCHESTRATION_V1 + MLB_RUNTIME_OBJECT_V1*
