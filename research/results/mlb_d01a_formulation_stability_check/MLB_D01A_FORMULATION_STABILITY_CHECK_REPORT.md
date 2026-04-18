# MLB D01A — FORMULATION STABILITY CHECK REPORT

**Test Date:** 2026-04-17
**Branch Name:** MLB_D01A_FORMULATION_STABILITY_CHECK
**Parent Branch:** MLB_D01_MANUAL_HISTORICAL_TEST
**Candidate ID:** MLB_D01
**Advancement Type:** MANUAL_CHILD_CHECK

---

## 1. PURPOSE

This child branch tests whether the D01 signal requires its full frozen 2-field gap formulation, or whether the result is mostly explained by one field carrying the signal while the other acts as a weak filter.

D01 advanced with a documented validation-attenuation caveat (+0.426 → +0.028 → +0.565). This check asks whether the current formulation is trustworthy enough to justify continuing. It does not modify D01 in any way.

---

## 2. SOURCE / GOVERNANCE STATUS

| Item | Status |
|---|---|
| Advancement type | Manual child check of provisional parent |
| Full orchestration governance present | **NO** — all orchestration files remain absent |
| Parent used fallback data object | **YES** — matchup_table_base |
| This child matches parent data object | **YES** — exact same object, no drift |
| Manual split enforcement | **YES** — discovery 2022–2023 / validation 2024 / OOS 2025 |
| Part of manually advanced provisional candidate path | **YES** |

---

## 3. DATA OBJECT USED

| Field | Value |
|---|---|
| Object | `research/recovery/mlb_matchup_table_base/mlb_matchup_table_base.parquet` |
| Outcome source | `sim/data/game_table.parquet` (`actual_total`) |
| Rows with both fields + outcome non-null | 13,566 |
| Seasons usable | 2022, 2023, 2024, 2025 |

Exact same object and join as parent D01. No source drift.

---

## 4. PARENT D01 INHERITANCE CONFIRMATION

Parent D01 frozen formulation inherited exactly:

| Element | Inherited Value |
|---|---|
| Field 1 | `opp_sp_workload_ip_last_3` |
| Field 2 | `opp_sp_workload_ip_last_10` |
| Rule | `collapse_flag = 1` when `opp_sp_workload_ip_last_10 - opp_sp_workload_ip_last_3 >= 1.0` |
| Threshold | 1.0 (IP gap) |
| Direction | Flagged games expected to have higher totals |

No modification to fields, thresholds, or rule definition.

Parent D01 staged results (for reference):

| Stage | Gap |
|---|---|
| Discovery | +0.426 |
| Validation | +0.028 |
| OOS | +0.565 |

---

## 5. FROZEN COMPARISON DEFINITIONS

### Structural Ambiguity — Critical Context

**D01 is a gap rule, not a conjunction of two independent level-threshold flags.** The parent threshold of 1.0 was designed as a minimum gap between two rolling windows (last_10 minus last_3), not as a level threshold applicable to either field independently.

Per instructions, the parent threshold value of 1.0 was applied literally to each field as a standalone level threshold. This produces structurally degenerate component groups because:

- **Component A** (`last_3 <= 1.0`): Flags rows where the opposing starter averaged 1.0 innings or less over their last 3 starts. Almost no MLB starters average this low — only extreme opener/bullpen-game edge cases.
- **Component B** (`last_10 >= 1.0`): Flags rows where the opposing starter averaged 1.0 innings or more over their last 10 starts. Virtually all MLB starters average well above 1.0 IP.

This degeneracy is not an error — it is the honest result of applying a gap threshold to individual field levels. The parent threshold (1.0) was meaningful as a gap; it is not meaningful as an absolute IP level for either field.

### Frozen Groups

| Group | Definition | Expected Behavior |
|---|---|---|
| COMPONENT_A_ONLY | `opp_sp_workload_ip_last_3 <= 1.0` | Degenerate — flags ~0% of rows |
| COMPONENT_B_ONLY | `opp_sp_workload_ip_last_10 >= 1.0` | Degenerate — flags ~100% of rows |
| D01_FULL_FORMULATION | `opp_sp_workload_ip_last_10 - opp_sp_workload_ip_last_3 >= 1.0` | Valid — exact parent rule |

---

## 6. SPLIT POLICY USED

| Stage | Seasons | Purpose |
|---|---|---|
| Discovery | 2022–2023 | Initial comparison |
| Validation | 2024 | Out-of-sample check |
| OOS | 2025 | Final confirmatory |

Manual enforcement. Identical to parent D01.

---

## 7. DISCOVERY RESULTS (2022–2023)

| Group | N Flagged | Flag % | Mean Flagged | Mean Unflagged | Gap | Note |
|---|---|---|---|---|---|---|
| COMPONENT_A (last_3 <= 1.0) | 13 | 0.2% | 7.769 | 8.938 | -1.169 | **BELOW 30 FLOOR** |
| COMPONENT_B (last_10 >= 1.0) | 6,778 | 99.9% | 8.937 | 7.000 | +1.937 | **UNFLAGGED BELOW 30** (only 4 unflagged) |
| D01_FULL_FORMULATION (gap >= 1.0) | 300 | 4.4% | 9.343 | 8.917 | +0.426 | Valid comparison |

**Assessment:** Both component groups are degenerate. Component A flags only 13 rows (below 30 floor). Component B flags 99.9% of rows (unflagged group has only 4 observations). Neither can serve as a meaningful comparison. Only the full formulation produces a valid flagged-vs-unflagged comparison.

---

## 8. VALIDATION RESULTS (2024)

| Group | N Flagged | Flag % | Mean Flagged | Mean Unflagged | Gap | Note |
|---|---|---|---|---|---|---|
| COMPONENT_A (last_3 <= 1.0) | 6 | 0.2% | 10.333 | 8.744 | +1.590 | **BELOW 30 FLOOR** |
| COMPONENT_B (last_10 >= 1.0) | 3,381 | 100.0% | 8.747 | 6.000 | +2.747 | **UNFLAGGED BELOW 30** (only 1 unflagged) |
| D01_FULL_FORMULATION (gap >= 1.0) | 159 | 4.7% | 8.774 | 8.745 | +0.028 | Valid comparison; severe attenuation |

---

## 9. OOS RESULTS (2025)

| Group | N Flagged | Flag % | Mean Flagged | Mean Unflagged | Gap | Note |
|---|---|---|---|---|---|---|
| COMPONENT_A (last_3 <= 1.0) | 0 | 0.0% | N/A | 8.907 | N/A | **ZERO FLAGGED** |
| COMPONENT_B (last_10 >= 1.0) | 3,402 | 100.0% | 8.907 | N/A | N/A | **ZERO UNFLAGGED** |
| D01_FULL_FORMULATION (gap >= 1.0) | 157 | 4.6% | 9.446 | 8.880 | +0.565 | Valid comparison |

---

## 10. FORMULATION INTERPRETATION

### Does the full D01 formulation add structure beyond either component alone?

**This question cannot be answered by this decomposition.** The component-dominance test format was designed for conjunction rules (e.g., H03's bullpen stress × short-outing risk, where each component has a meaningful standalone flag). D01 is a gap rule — the threshold (1.0) defines a minimum difference between two windows, not a level for either window independently. When the gap threshold is applied literally to individual fields, both component groups degenerate (near-zero or near-all flagged), making comparison impossible.

**What this DOES tell us:** D01's signal is inherently a trajectory signal. It cannot be reduced to "low recent IP" alone (Component A) or "high historical IP" alone (Component B), because neither field-level threshold captures the trajectory concept. The gap IS the formulation — it is not a conjunction of two separable components.

### Is the validation collapse still a concern?

**YES.** This child check does not resolve the validation attenuation. The full formulation reproduces the parent's results exactly (as expected — same data, same rule). The validation gap remains +0.028 (93% shrinkage from discovery). The component comparison was unable to provide diagnostic evidence about whether the validation collapse reflects a structural formulation weakness or normal sampling variability, because the components themselves are not evaluable.

### Is D01 worth further follow-up work?

**Conditional YES.** D01 cannot be dismissed by this check — neither component alone provides a credible alternative explanation for the signal. However, this check also cannot positively confirm that the gap formulation is structurally stable, because the decomposition format does not apply cleanly to gap rules. The validation attenuation remains an open concern.

Further follow-up, if pursued, should take a different form than component decomposition — for example, an economic reality check (does the market already price the trajectory?) or a sample-stability analysis (is the validation dip consistent with expected sampling noise given the flagged N of ~160?).

---

## 11. MECHANISM / ANTI-DUPLICATION CHECK

### Is D01 still genuine workload trajectory collapse, or generic recent-form starter weakness?

**Still genuinely trajectory-based.** The degenerate component results confirm this: "low recent IP" alone (last_3 <= 1.0) captures almost no rows, demonstrating that D01 does not flag on absolute IP levels. The signal requires the RELATIVE decline (gap between windows). A starter averaging 4.5 IP last-3 is only flagged if their last-10 average is ≥ 5.5 — the trajectory matters, not the level.

Conversely, a starter averaging 4.0 IP at both windows (consistently short) would NOT be flagged by D01. This is not generic "bad starter" or "recent form" logic — it is specifically workload trajectory instability.

### Is D01_FULL_FORMULATION structurally distinct, or just one component doing the work?

**Structurally distinct from either component.** Neither component alone, with parent thresholds, produces a meaningful comparison group. The full formulation is the only group that creates a valid flagged-vs-unflagged split with adequate sample sizes. The gap construct is not reducible to either field alone — it is genuinely a 2-field trajectory measure.

However, "structurally distinct from degenerate components" is a weak positive — it follows necessarily from the gap-rule structure rather than from empirical evidence of the signal's robustness.

---

## 12. CAVEATS

1. **Parent D01 governance limitation.** D01 was a provisional discovery candidate, manually advanced, tested with fallback data object and manual split enforcement. This child check inherits all parent governance limitations.

2. **Parent D01 validation attenuation.** The +0.028 validation gap (93% shrinkage) remains unresolved. This child check could not diagnose it because the decomposition format does not apply cleanly to gap rules.

3. **Degenerate component groups.** Both component-alone groups produced degenerate results (flagged N < 30 or unflagged N < 30). This means the component-dominance test could not be executed as intended. The finding is structural (gap rules don't decompose this way), not an indictment of D01 specifically.

4. **Sample-size imbalance.** Component A flags 0–13 rows per stage. Component B flags 99.9–100% of rows. Only the full formulation (4.4–4.7% flag rate) creates a balanced comparison. This imbalance is inherent to the decomposition of a gap rule using a gap-derived threshold.

5. **This check does not confirm D01 is production-ready.** It only finds that D01 cannot be dismissed as single-component-dominated. The formulation structure is not challenged by this test, but neither is the validation-attenuation concern resolved.

---

## 13. FINAL VERDICT

**MIXED_INCONCLUSIVE**

The component-dominance decomposition cannot be meaningfully executed for D01 because the parent formulation is a gap rule, not a conjunction of level-threshold flags. Applying the parent threshold (1.0) to individual fields produces degenerate component groups that fall below evidence floors. Neither component alone provides a credible alternative explanation for the signal, but neither does the decomposition positively confirm the full formulation's structural stability.

The validation-attenuation caveat from the parent D01 test is preserved and unresolved.

D01 is not dismissed by this check. It is not confirmed as structurally stable by this check. Further diagnostic work (if pursued) should use a different format — economic reality check or sample-stability analysis rather than component decomposition.

---

*Report generated: 2026-04-17*
*Advancement type: MANUAL_CHILD_CHECK*
*Governance: Manual split enforcement, parent fallback data object reused*
