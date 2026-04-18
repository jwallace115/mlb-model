# MLB BOUNDED DISCOVERY PASS 01 — GOVERNANCE MEMO

**Memo Date:** 2026-04-17
**Operator:** Claude (automated research assistant)
**Subject:** Governance status of MLB Bounded Discovery Pass 01
**Governance Status:** INCOMPLETE
**Candidate Status:** PROVISIONAL ONLY

---

## 1. PURPOSE

This memo documents the governance status of MLB Bounded Discovery Pass 01. The pass produced two candidate ideas (MLB_D01 and MLB_D02) that may have research value, but it did NOT satisfy the full governance standard required for autonomous bounded discovery to be considered operational.

This memo exists to:
- Preserve D01 and D02 as provisional candidate ideas
- Prevent them from being treated as formally advanced autonomous-discovery outputs
- Record exactly what infrastructure was missing or substituted
- Define what must be restored before autonomous bounded discovery is considered operational

This memo does not alter, upgrade, or reinterpret the candidates. It adds governance context only.

---

## 2. WHAT THE PASS PRODUCED

The pass generated two candidates within the FORCED-ROLE / ROLE-INSTABILITY / STATE-TRANSITION ASYMMETRY mechanism family:

**MLB_D01 — Opposing Starter Workload Trajectory Collapse**
- Fields: `opp_sp_workload_ip_last_3`, `opp_sp_workload_ip_last_10`
- Threshold: `opp_sp_workload_ip_last_10 - opp_sp_workload_ip_last_3 >= 1.0`
- Mechanism: starter's recent IP sharply below longer-term norm signals forced bullpen role expansion

**MLB_D02 — Opposing Starter Pitch Efficiency Deterioration**
- Fields: `opp_sp_workload_ppbf_last_3`, `opp_sp_workload_ppbf_last_10`
- Threshold: `opp_sp_workload_ppbf_last_3 - opp_sp_workload_ppbf_last_10 >= 0.3`
- Mechanism: rising pitches per batter faced is a leading indicator of shortened outings and forced role transition

Both candidates use 2 fields each from the matchup table base, have domain-grounded frozen thresholds, and include anti-duplication explanations against H01/H02/H03/V1-lite. Both were recommended as ADVANCE_TO_TEST by the discovery pass.

The full candidate descriptions, mechanism claims, market-miss arguments, anti-duplication explanations, and expected failure modes are preserved unaltered in `MLB_BOUNDED_DISCOVERY_PASS_01_REPORT.md`.

---

## 3. WHY THE PASS WAS NOT FULLY GOVERNED

The discovery pass self-audit returned **PASS WITH WARNINGS**, citing four categories of missing governance infrastructure. These are not minor documentation gaps — they represent the absence of the control layer that was specified as required for the pass to operate under full governance.

### 3.1 Missing Orchestration Layer Files

All 7 specified orchestration files do not exist on disk (local or remote):

| Required File | Status |
|---|---|
| `research/orchestration/mlb_research_orchestrator.py` | NOT FOUND |
| `research/orchestration/mlb_research_orchestration_config.json` | NOT FOUND |
| `research/orchestration/mlb_research_object_router.json` | NOT FOUND |
| `research/orchestration/mlb_research_workflow_templates.json` | NOT FOUND |
| `research/orchestration/mlb_research_branch_status_schema.json` | NOT FOUND |
| `research/orchestration/MLB_RESEARCH_ORCHESTRATION_REPORT.md` | NOT FOUND |
| `research/orchestration/MLB_RESEARCH_ORCHESTRATION_REGISTRY.json` | NOT FOUND |

**Impact:** The pass could not be routed through the orchestration layer, validated against workflow templates, or registered in the orchestration registry. There is no formal mechanism to track this pass as part of the broader research program.

### 3.2 Missing Canonical Historical Research Object

The specified canonical historical research matchup object (`research/recovery/mlb_canonical_historical_research_matchup_object/`) does not exist. The matchup table base (`research/recovery/mlb_matchup_table_base/mlb_matchup_table_base.parquet`) was used as a substitute.

**Impact:** The matchup table base is the accepted research base layer and contains the same fields the candidates need. However, the substitution means:
- The pass did not operate against the formally designated canonical object
- Field classification was verified against the matchup table base registry, not against a canonical object registry
- Any differences between the intended canonical object and the matchup table base (if they were ever different) would be undetected

### 3.3 Missing Manifest Files

Neither the approved nor banned object manifests exist:

| Required File | Status |
|---|---|
| `research/recovery/mlb_stack_standardization/MLB_STACK_APPROVED_OBJECTS_MANIFEST.json` | NOT FOUND |
| `research/recovery/mlb_stack_standardization/MLB_STACK_BANNED_OBJECTS_MANIFEST.json` | NOT FOUND |

**Impact:** Formal banned-source checking could not be performed. The pass relied on the matchup table base registry's approved feature list as an informal substitute. No formally banned sources were knowingly used, but the absence of the manifest means this cannot be verified against the intended standard.

### 3.4 Why This Prevents Full Governance Approval

The orchestration layer, canonical object, and manifests together constitute the governance control layer for autonomous discovery. Without them:

- There is no formal routing or registration mechanism
- There is no formal object boundary enforcement
- There is no formal banned-source exclusion check
- There is no formal workflow template to validate the pass structure against

The pass was conducted in good faith using available substitutes and documented every gap. But "documented substitution" is not the same as "full governance compliance." The control layer exists to prevent drift, enforce boundaries, and provide auditability — and those guarantees cannot be claimed when the control layer itself is absent.

---

## 4. PROVISIONAL CANDIDATE STATUS

MLB_D01 and MLB_D02 are **provisional candidate ideas only**.

They are:
- Idea memos, not formally sanctioned autonomous-discovery outputs
- Products of a pass that operated outside the intended governance layer
- Potentially useful starting points for manual hypothesis construction

They are NOT:
- Formally advanced autonomous-discovery candidates
- Proof that the bounded discovery engine works as intended
- Pre-approved for testing without human review

They may be:
- Manually reviewed by the operator
- Manually promoted to bounded historical hypothesis test prompts with explicit human approval
- Rewritten into direct test prompts that acknowledge their origin as provisional discovery candidates

---

## 5. WHAT IS ALLOWED NOW

1. **Preserve D01 and D02 as provisional ideas.** The discovery pass report, registry, and self-audit remain as-is. This governance memo adds context; it does not delete or alter the candidates.

2. **Manually inspect the candidates.** The operator may read the full candidate descriptions, evaluate the mechanism claims, and judge whether either idea is worth testing.

3. **Convert a candidate into a bounded historical hypothesis test prompt.** If the operator judges a candidate worth testing, it may be manually converted into a test prompt. That test prompt must explicitly acknowledge that the candidate originated from a provisional discovery pass that did not meet full governance standards.

4. **Use the candidates as input for a future fully-governed discovery pass.** If the governance infrastructure is restored, D01 and D02 may be re-evaluated under full governance as part of a subsequent pass.

---

## 6. WHAT IS NOT ALLOWED NOW

1. **Do NOT treat D01 or D02 as fully approved autonomous candidates.** They were not produced under full governance and must not be cited as such.

2. **Do NOT cite this pass as proof the discovery engine is operational.** The pass demonstrated that useful ideas can be generated, but it did not demonstrate that the governance control layer works, because the governance control layer was absent.

3. **Do NOT open broad autonomous discovery based on this pass.** One provisional pass with documented substitutions does not justify expanding to broader or more frequent autonomous discovery. The governance infrastructure must be restored first.

4. **Do NOT skip governance restoration just because the ideas look good.** The quality of the candidates is independent of the governance status of the pass. Good ideas produced outside the control layer are still outside the control layer. The control layer exists to prevent the bad ideas that will inevitably appear alongside the good ones — and its value cannot be assessed by a single pass that happened to produce reasonable output.

---

## 7. REQUIREMENTS TO RESTORE FULL DISCOVERY GOVERNANCE

Before autonomous bounded discovery can be considered operational, the following must exist on disk and be readable:

### 7.1 Orchestration Layer Artifacts

All of the following must be created, populated, and verified:

- `research/orchestration/mlb_research_orchestrator.py` — routing and execution logic
- `research/orchestration/mlb_research_orchestration_config.json` — configuration parameters
- `research/orchestration/mlb_research_object_router.json` — object routing rules
- `research/orchestration/mlb_research_workflow_templates.json` — workflow structure templates
- `research/orchestration/mlb_research_branch_status_schema.json` — branch status validation schema
- `research/orchestration/MLB_RESEARCH_ORCHESTRATION_REPORT.md` — orchestration layer documentation
- `research/orchestration/MLB_RESEARCH_ORCHESTRATION_REGISTRY.json` — pass and branch registration

### 7.2 Canonical Historical Research Object Artifacts

The designated canonical object must exist with its registry and report:

- `research/recovery/mlb_canonical_historical_research_matchup_object/mlb_canonical_historical_research_matchup_object.parquet`
- `research/recovery/mlb_canonical_historical_research_matchup_object/MLB_CANONICAL_HISTORICAL_RESEARCH_MATCHUP_OBJECT_REGISTRY.json`
- `research/recovery/mlb_canonical_historical_research_matchup_object/MLB_CANONICAL_HISTORICAL_RESEARCH_MATCHUP_OBJECT_REPORT.md`

Alternatively, if the matchup table base IS the intended canonical object, this must be formally documented — the naming and location must be reconciled so that future passes do not require ad-hoc substitution.

### 7.3 Approved and Banned Manifests

Both manifests must exist and be populated:

- `research/recovery/mlb_stack_standardization/MLB_STACK_APPROVED_OBJECTS_MANIFEST.json`
- `research/recovery/mlb_stack_standardization/MLB_STACK_BANNED_OBJECTS_MANIFEST.json`

### 7.4 Anti-Duplication Closeout References

Closed family artifacts must be present on disk (not only as session-reconstructed provisionals):

- H03 family closeout files (currently provisional, reconstructed from verified summaries)
- Any future closed families

### 7.5 Verification Standard

Once the above artifacts exist, a verification pass should confirm:
- The orchestration layer can route a discovery pass without substitutions
- The canonical object is readable and its field list matches the registry
- The manifests are populated and enforceable
- Anti-duplication references are readable from disk, not from session context

Only after this verification should autonomous bounded discovery be considered operational.

---

## 8. FINAL MEMO VERDICT

**PROVISIONAL_ONLY**

MLB Bounded Discovery Pass 01 produced two provisional candidate ideas (MLB_D01, MLB_D02) that may have research value. However, the pass did not satisfy full governance requirements due to missing orchestration layer files, missing canonical historical object, and missing manifest files. The candidates are preserved as provisional ideas only. The bounded discovery engine is not operational until the governance infrastructure is restored and verified.

---

*Memo generated: 2026-04-17*
*Status: GOVERNANCE INCOMPLETE — PROVISIONAL CANDIDATES ONLY*
