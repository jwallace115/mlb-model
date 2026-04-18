# MLB D-FAMILY — STATUS MEMO

**Memo Date:** 2026-04-17
**Family Name:** MLB_D_FAMILY
**Mechanism Family:** FORCED-ROLE / ROLE-INSTABILITY / STATE-TRANSITION ASYMMETRY
**Family Status:** NOT ACTIONABLE
**Discovery Engine Readiness:** NOT PROVEN

---

## 1. FAMILY STATUS

| Branch | Status | Summary |
|---|---|---|
| MLB_D01 | **UNRESOLVED / CAUTION** | Technically passing staged test, but validation severely attenuated; structure not confirmed |
| MLB_D01A | **MIXED_INCONCLUSIVE** | Component-dominance check degenerate; did not confirm formulation stability |
| MLB_D02 | **SHELVED** | Discovery direction wrong; sign reversals every stage; closed |
| Discovery Engine | **NOT PROVEN** | Pass 01 produced ideas but governance was incomplete |

**The D-family is not actionable.** No branch in this family has produced a confirmed, structurally validated signal. The discovery pass that generated the candidates did not meet full governance standards. The D-family must not be treated as a successful autonomous discovery family.

---

## 2. SOURCE / GOVERNANCE CONTEXT

The D-family originated from MLB Bounded Discovery Pass 01 (2026-04-17), which operated outside full governance:

| Governance Element | Status |
|---|---|
| Orchestration layer (7 files) | **MISSING** — all files absent |
| Canonical historical research object | **MISSING** — matchup_table_base used as fallback |
| Approved/banned manifests | **MISSING** |
| Anti-duplication closeout references | **PROVISIONAL** — H03 closeout reconstructed from verified summaries |
| Discovery pass governance verdict | **INCOMPLETE** (per governance memo) |
| Candidate status from pass | **PROVISIONAL ONLY** |

Both D01 and D02 were manually advanced from provisional candidates by explicit human decision — not by autonomous discovery engine promotion. All tests used manual split enforcement with the fallback data object.

---

## 3. BRANCH-BY-BRANCH SUMMARY

### D01 — Opposing Starter Workload Trajectory Collapse

| Field | Value |
|---|---|
| Advancement type | Manual from provisional discovery |
| Fields | `opp_sp_workload_ip_last_3`, `opp_sp_workload_ip_last_10` |
| Rule | `last_10 - last_3 >= 1.0` (gap rule) |
| Discovery | +0.426 (N=300 flagged) |
| Validation | +0.028 (**93% attenuation**) |
| OOS | +0.565 |
| Verdict | ADVANCE with validation-attenuation caveat |
| Current status | **UNRESOLVED / CAUTIONARY** |

D01 technically passed all pre-declared staged gates (same sign in all stages, no material OOS reversal, discovery N above floor). However, the validation attenuation is severe — the gap collapses from +0.426 to +0.028, a 93% shrinkage. The non-monotonic staged profile (+0.426 → +0.028 → +0.565) is unusual and does not inspire confidence in signal stability. D01 is a technical pass, not a clean pass.

### D01A — Formulation Stability Check

| Field | Value |
|---|---|
| Parent branch | D01 |
| Check type | Component-dominance decomposition |
| Verdict | **MIXED_INCONCLUSIVE** |

D01A attempted to test whether D01's signal requires its full 2-field gap formulation or is mostly explained by one component alone. The check produced **degenerate component groups**: applying the parent gap threshold (1.0) to individual fields as standalone level thresholds flagged near-zero rows (Component A: last_3 <= 1.0) or near-all rows (Component B: last_10 >= 1.0). Neither component produced a meaningful comparison.

This degeneracy is structural — D01 is a gap rule, not a conjunction of two level-threshold flags. The component-dominance decomposition format does not cleanly apply to gap-rule formulations. D01A therefore **did not confirm** that D01's formulation is structurally stable. It also did not dismiss D01 — neither component alone provides a credible alternative explanation. The result is genuinely inconclusive.

The parent D01 validation attenuation remains **unresolved** after D01A.

### D02 — Opposing Starter Pitch Efficiency Deterioration

| Field | Value |
|---|---|
| Advancement type | Manual from provisional discovery |
| Fields | `opp_sp_workload_ppbf_last_3`, `opp_sp_workload_ppbf_last_10` |
| Rule | `ppbf_last_3 - ppbf_last_10 >= 0.3` |
| Discovery | -0.157 (**wrong direction**) |
| Validation | +0.239 (sign reversal) |
| OOS | -0.125 (sign reversal again) |
| Verdict | **SHELVE** |
| Current status | **CLOSED** |

D02 failed cleanly. The discovery gap was negative (-0.157) — flagged games had lower totals, the opposite of the mechanism prediction. The full staged profile (-0.157 → +0.239 → -0.125) shows sign reversals in every stage. The primary expected failure mode materialized: pitches per batter faced is a noisy proxy influenced as much by the opposing lineup's approach as by the pitcher's efficiency. D02 is closed with no ambiguity.

---

## 4. CURRENT FAMILY INTERPRETATION

The D-family produced one technically passing but unclean result (D01), one inconclusive structure check (D01A), and one clean failure (D02). Taken together:

1. **D01's signal may be real, but it is not confirmed.** The gap rule passed all staged gates technically, but the 93% validation attenuation and the failure of D01A to confirm structural stability leave D01 in an unresolved state. A signal that collapses to near-zero in validation and rebounds in OOS could be genuine (validation dip is sampling noise) or could be unstable (the OOS rebound is the lucky outlier). Neither interpretation is ruled out.

2. **D02's failure is informative.** It demonstrates that not all ideas from the FORCED-ROLE mechanism family produce signal. The ppbf trajectory — a theoretically plausible leading indicator — turned out to be noise. This is a normal and expected result of honest hypothesis testing.

3. **The D-family does not validate the discovery engine.** The candidates were provisional, the governance was incomplete, and the results are mixed. One clean failure and one unresolved pass do not constitute proof that autonomous bounded discovery works.

---

## 5. OPERATIONAL DISPOSITION

### Do NOT:
- Promote D01 to production
- Promote D01 to shadow edge candidate
- Treat D01 as structurally confirmed
- Reopen D02
- Cite the D-family as proof autonomous bounded discovery is operational
- Expand the D-family broadly based on D01's technical pass
- Weaken standards to rescue D01's validation attenuation

### Do:
- Preserve D01 as unresolved / cautionary
- Preserve D01A as a completed child check that failed to confirm structure
- Preserve D02 as shelved and closed
- Move active attention to other families unless one very specific, tightly bounded D01 follow-up is justified later by explicit human decision

---

## 6. WHAT IS CLOSED

1. **D02 branch.** Shelved. Discovery direction wrong, sign reversals every stage. No further work warranted.

2. **D01A as a completed child check.** The formulation stability check is done. It returned MIXED_INCONCLUSIVE because the decomposition format does not apply to gap rules. It will not be re-run.

3. **The claim that D-family demonstrates autonomous discovery readiness.** The discovery pass operated outside full governance (missing orchestration, canonical object, manifests). The family results are mixed. Autonomous bounded discovery readiness is not proven by this family.

---

## 7. WHAT REMAINS OPEN

1. **D01 may remain as an unresolved note.** The signal technically passed staged gates and the mechanism is interpretable. It is not dismissed — but it is not confirmed either.

2. **Any further D01 work would require explicit human decision and a tightly bounded prompt.** Possible follow-up formats include:
   - Economic reality check (does the market already price the trajectory?)
   - Sample-stability analysis (is the validation dip consistent with expected noise given flagged N ~160?)
   - Neither should be initiated automatically. Both require manual operator judgment.

3. **No broad D-family expansion should occur automatically.** The family does not have enough confirmed structure to justify spawning additional candidates or child branches without explicit human direction.

---

## 8. DISCOVERY-ENGINE STATUS

| Question | Answer |
|---|---|
| Did bounded discovery pass 01 produce ideas? | YES — 2 provisional candidates |
| Were those ideas tested? | YES — both manually advanced and tested |
| Did the tests produce actionable results? | **NO** — 1 shelved, 1 unresolved |
| Was discovery governance complete? | **NO** — orchestration, canonical object, and manifests missing |
| Is bounded discovery operationally ready? | **NOT PROVEN** |

The bounded discovery engine demonstrated that it can generate interpretable, non-duplicative candidate ideas within a single mechanism family. That is a useful proof-of-concept for idea generation. But it did not demonstrate:
- Full governance compliance (missing control layer)
- Reliable signal production (1 of 2 candidates failed, 1 unresolved)
- That autonomous discovery can replace manual hypothesis construction

Before autonomous bounded discovery can be considered operational, the governance infrastructure must be restored (orchestration layer, canonical object, manifests) and a future pass must demonstrate clean end-to-end execution without substitutions.

---

## 9. FINAL STATUS VERDICT

**D_FAMILY_NOT_ACTIONABLE**

The MLB D-family (FORCED-ROLE / ROLE-INSTABILITY / STATE-TRANSITION ASYMMETRY) contains no confirmed, structurally validated, deployment-ready signal. D01 is unresolved with a validation-attenuation concern. D01A did not confirm formulation stability. D02 is cleanly shelved. The bounded discovery engine that produced these candidates is not operationally proven.

The D-family is preserved as documentation of the first bounded discovery attempt. It is not an active edge family, not a production candidate, and not proof that autonomous discovery is ready.

---

*Memo generated: 2026-04-17*
*Status: D_FAMILY_NOT_ACTIONABLE*
