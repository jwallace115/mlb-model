# MLB W02 — MANUAL HISTORICAL HYPOTHESIS TEST — SELF-AUDIT

**Audit Date:** 2026-04-19
**Branch:** MLB_W02_MANUAL_HISTORICAL_TEST

---

## Self-Audit Questions

### 1. Was MLB_W02 manually advanced rather than autonomous promotion?
**YES.** W02 was manually advanced from provisional candidate in Bounded Discovery Pass 03. This is explicitly documented as a manual bounded hypothesis test.

### 2. Were foundation, orchestration, and runtime object all confirmed?
**YES.** All three confirmed before proceeding:
- Foundation: `research/engine_foundation/mlb_engine_v1_foundation/`
- Orchestration: `research/orchestration/` (default_deny=true)
- Runtime object: `mlb_runtime_object_v1.parquet` (19,430 x 130, HISTORICAL_CLEAN)

### 3. Were outside-package inputs excluded?
**YES.** Only the runtime object (built from frozen foundation) was used. The self-join for opponent bullpen data uses existing fields within the runtime object. No outside-package files.

### 4. Were field list, interaction form, and thresholds frozen before results?
**YES.** All frozen before any staged results were computed:
- Fields: `opp_sp_command_bb_rate_last_3`, `relievers_used_last_3_games` (opponent via self-join)
- Form: AND rule
- Thresholds: BB rate >= 0.10, relievers used >= 12
- Direction: flagged > unflagged
- All from discovery pass 03 definition, no modifications.

### 5. Did any post-discovery tuning occur?
**NO.** Thresholds were frozen from the discovery pass 03 definition. No adjustment was made after seeing any results.

### 6. Was validation kept out of discovery construction?
**YES.** Discovery used 2022-2023 only. Validation (2024) and OOS (2025) were strictly separated.

### 7. Was OOS used only as confirmatory?
**YES.** OOS (2025) was used only to evaluate the pre-frozen rule. No re-tuning based on OOS results.

### 8. Was the vacuous threshold check run before staging?
**YES.** Vacuous check completed before reporting staged results:
- Component A: 26.6% — not vacuous
- Component B: 19.6% — not vacuous
- Full formulation: 5.0% — at floor but not below

### 9. Was the anti-duplication check against W01 and H03 applied?
**YES.** Explicit checks against:
- W01 (different fields: BB rate vs IP, relievers vs pitches; different mechanism angle: leading vs lagging)
- H03 (different side of matchup: opposing vs own; different fields)
- D01 (different mechanism: level threshold + bullpen conjunction vs trajectory collapse)
- Generic starter weakness (requires conjunction, not standalone)
- Generic bullpen fatigue (requires conjunction, not standalone)

### 10. Were only authorized files written to the correct directory?
**YES.** Exactly 5 files written to `research/results/mlb_w02_manual_historical_test/`:
1. MLB_W02_MANUAL_HISTORICAL_TEST_REPORT.md
2. MLB_W02_MANUAL_HISTORICAL_TEST_REGISTRY.json
3. MLB_W02_MANUAL_HISTORICAL_TEST_STAGE_TABLES.csv
4. MLB_W02_MANUAL_HISTORICAL_TEST_SELF_AUDIT.md
5. MLB_W02_MANUAL_HISTORICAL_TEST_BRANCH_STATUS.json

### 11. Were any VM writes used?
**NO.** All writes to local Mac filesystem only.

### 12. Is the final verdict honestly supported by the staged evidence?
**YES.** SHELVE is the correct verdict. The OOS material reversal (-0.464 vs discovery +0.450) is decisive. The sign flips with comparable magnitude. This is not a marginal call — the minimum evidence standard explicitly requires OOS to not materially reverse, and a complete sign flip with magnitude exceeding discovery is an unambiguous material reversal.

---

## Self-Audit Verdict

**PASS**

All 12 questions answered affirmatively. No process violations. No post-discovery tuning. No outside-package inputs. No VM writes. The SHELVE verdict is honestly supported by the evidence.
