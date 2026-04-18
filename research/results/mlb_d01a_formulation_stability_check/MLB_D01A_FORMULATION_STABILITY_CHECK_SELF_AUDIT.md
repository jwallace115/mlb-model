# MLB D01A — FORMULATION STABILITY CHECK SELF-AUDIT

**Audit Date:** 2026-04-17
**Document Audited:** MLB_D01A_FORMULATION_STABILITY_CHECK_REPORT.md

---

## Self-Audit Questions

### 1. Was D01A run as a child check of a manually advanced provisional candidate rather than as a fully sanctioned autonomous branch?

**YES.** The report (Section 2) explicitly identifies the advancement type as MANUAL_CHILD_CHECK. It states: "Part of manually advanced provisional candidate path: YES." The parent D01's provisional status and manual advancement are acknowledged throughout.

### 2. Was the exact parent data object reused without substitution drift?

**YES.** Parent D01 used `research/recovery/mlb_matchup_table_base/mlb_matchup_table_base.parquet` with outcome from `sim/data/game_table.parquet`. This child used the identical objects. No source drift. Section 3 confirms the match.

### 3. If full orchestration artifacts were missing, was that documented honestly?

**YES.** Section 2 states: "Full orchestration governance present: NO — all orchestration files remain absent." The manual split enforcement and fallback status are documented in the governance table.

### 4. Were the three comparison groups frozen before reading discovery results?

**YES.** The three groups were defined based on the parent D01's frozen rule and the literal application of the parent threshold to each field. The structural ambiguity of applying a gap threshold to individual fields was documented before results were computed. The definitions were not modified after seeing results.

### 5. Did any post-discovery tuning occur? If yes, FAIL.

**NO.** No thresholds, rules, or group definitions were modified after seeing any results. The degenerate component results were reported as-is. No alternative thresholds were tried to "fix" the degenerate components.

### 6. Was validation kept out of discovery construction?

**YES.** The comparison groups were defined from the parent D01's frozen rule, not from any data. Validation data (2024) was not used in group construction.

### 7. Was OOS used only as confirmatory?

**YES.** OOS (2025) was evaluated after discovery and validation. No OOS information influenced group definitions or interpretation framework.

### 8. Was the mechanism / anti-duplication check against generic starter weakness applied explicitly?

**YES.** Section 11 provides an explicit mechanism check confirming D01 remains trajectory-based (not generic starter quality) and that the full formulation is structurally distinct from either component. The degenerate component results provide supporting evidence: the signal requires the gap between windows, not either window's absolute level.

### 9. Were only authorized files written?

**YES.** Exactly 5 files were written, all within `research/results/mlb_d01a_formulation_stability_check/`:
1. `MLB_D01A_FORMULATION_STABILITY_CHECK_REPORT.md`
2. `MLB_D01A_FORMULATION_STABILITY_CHECK_REGISTRY.json`
3. `MLB_D01A_FORMULATION_STABILITY_CHECK_STAGE_TABLES.csv`
4. `MLB_D01A_FORMULATION_STABILITY_CHECK_SELF_AUDIT.md`
5. `MLB_D01A_FORMULATION_STABILITY_CHECK_BRANCH_STATUS.json`

One temporary script (`/tmp/d01a_test.py`) was written on the remote server for execution — transient compute artifact, not a research output.

### 10. Were any background tasks used?

**NO.** All work was performed in the foreground conversation.

### 11. Is the final verdict honestly supported by the staged comparison evidence and governance status?

**YES.** MIXED_INCONCLUSIVE is the honest verdict because:
- Both component groups are degenerate (below evidence floors), so no dominance pattern can be established
- The full formulation reproduces parent results but the decomposition cannot meaningfully test whether it adds structure beyond components
- The validation attenuation remains unresolved
- The decomposition format (designed for conjunction rules) does not cleanly apply to gap rules

The report does not overclaim (does not say FORMULATION_REAL despite the signal being non-decomposable) and does not underclaim (does not say CLOSE despite the inconclusive decomposition). It accurately characterizes a structural limitation of the test format applied to this candidate type.

---

## Self-Audit Verdict

**PASS WITH WARNINGS**

### Warnings:
1. **Degenerate decomposition.** The component-dominance test format does not apply cleanly to gap rules. Both component groups fell below evidence floors, preventing meaningful comparison. This is a structural limitation of the test design for this candidate type, not a procedural failure.
2. **Inherited governance limitations.** All parent D01 governance limitations (manual enforcement, fallback data object, provisional candidate path) carry forward. Full orchestration governance remains absent.

Neither warning represents a procedural violation. The degenerate result was reported honestly rather than "fixed" with alternative thresholds, which would have been a FAIL condition.

---

*Audit completed: 2026-04-17*
