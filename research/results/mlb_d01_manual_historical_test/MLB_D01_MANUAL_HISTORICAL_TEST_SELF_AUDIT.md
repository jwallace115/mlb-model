# MLB D01 — MANUAL HISTORICAL HYPOTHESIS TEST SELF-AUDIT

**Audit Date:** 2026-04-17
**Document Audited:** MLB_D01_MANUAL_HISTORICAL_TEST_REPORT.md

---

## Self-Audit Questions

### 1. Was MLB_D01 manually advanced rather than treated as formally approved autonomous discovery output?

**YES.** The report (Section 2) explicitly states: "D01 is being manually advanced by explicit human decision, not automatically promoted by the discovery engine." The advancement type is recorded as MANUAL_FROM_PROVISIONAL_DISCOVERY throughout all artifacts. The governance memo's provisional status is acknowledged.

### 2. Were only the allowed historical object and control artifacts used?

**YES.** The test used only:
- `research/recovery/mlb_matchup_table_base/mlb_matchup_table_base.parquet` (approved fallback data object)
- `sim/data/game_table.parquet` (outcome variable source — `actual_total`)

No raw substrate stitching, no new bridges, no new ingestion, no forward/frozen objects, no modules/umpires.py, no phase2/V1 tables.

### 3. If full orchestration artifacts were missing, was that documented honestly?

**YES.** Section 2 (SOURCE / GOVERNANCE STATUS) includes a table explicitly documenting: full orchestration governance NOT present, canonical historical object NOT present, fallback to matchup_table_base used, manifests NOT present, split policy manually enforced. The governance limitation is stated clearly.

### 4. Was the field list and threshold logic frozen before reading discovery results?

**YES.** The field list (2 fields) and threshold logic (IP gap >= 1.0) were declared in the D01 provisional candidate writeup (MLB Bounded Discovery Pass 01 Report, Section 5) before any test execution. The test script implemented exactly these pre-declared specifications. No modifications were made after seeing results.

### 5. Did any post-discovery tuning occur? If yes, FAIL.

**NO.** The rule was frozen before results. No thresholds were adjusted after seeing discovery, validation, or OOS results. No alternative windows or cutpoints were tried. The test was one candidate, one frozen rule, one pass through all three stages.

### 6. Was validation kept out of discovery construction?

**YES.** The split policy assigned 2022–2023 to discovery and 2024 to validation. The flag rule was defined before any data was examined. Validation data was not used to shape or tune the rule.

### 7. Was OOS used only as confirmatory?

**YES.** OOS (2025) was evaluated only after discovery and validation results were computed. No information from OOS was used to modify the rule, threshold, or interpretation framework.

### 8. Was the anti-duplication check against generic starter weakness / H03 / V1-lite applied explicitly?

**YES.** Section 11 (ANTI-DUPLICATION CHECK) provides five explicit checks: (1) not generic recent-form starter fade, (2) not generic weak-starter bucket, (3) not H03-family recycle, (4) not V1-lite restatement, (5) does not need new features. Each check includes a specific explanation of why D01 is distinct. All checks passed.

### 9. Were only authorized files written?

**YES.** Exactly 5 files were written, all within `research/results/mlb_d01_manual_historical_test/`:
1. `MLB_D01_MANUAL_HISTORICAL_TEST_REPORT.md`
2. `MLB_D01_MANUAL_HISTORICAL_TEST_REGISTRY.json`
3. `MLB_D01_MANUAL_HISTORICAL_TEST_STAGE_TABLES.csv`
4. `MLB_D01_MANUAL_HISTORICAL_TEST_SELF_AUDIT.md`
5. `MLB_D01_MANUAL_HISTORICAL_TEST_BRANCH_STATUS.json`

One temporary script (`/tmp/d01_test.py`) was written on the remote server for execution — this is a transient compute artifact, not a research output.

### 10. Were any background tasks used?

**NO.** All work was performed in the foreground conversation.

### 11. Is the final verdict honestly supported by the staged evidence and governance status?

**YES, with honest caveat documentation.** The ADVANCE verdict is technically supported: all five pre-declared gates passed (discovery N >= 30, discovery non-trivial, discovery correct direction, validation same sign, OOS no material reversal). However, the report honestly documents the severe validation attenuation (+0.426 → +0.028, 93% shrinkage) as a significant caveat. The interpretation section explicitly flags the non-monotonic staged profile as unusual and notes that the validation dip weakens confidence below what a clean profile would provide. The verdict does not claim deployment readiness — only that D01 survived its first staged test.

---

## Self-Audit Verdict

**PASS WITH WARNINGS**

### Warnings:
1. **Validation attenuation.** The severe validation shrinkage (93%) means D01's staged profile is technically passing but not clean. The ADVANCE verdict is honest but carries a documented caveat that must be evaluated in any future branch work.
2. **Governance incomplete.** The test was run under manual split enforcement with a fallback data object, not under full orchestration governance. This is documented but means the test cannot claim full governance compliance.

Neither warning represents a procedural violation or integrity failure. Both reflect honest limitations that are documented in the report and carried forward as caveats.

---

*Audit completed: 2026-04-17*
