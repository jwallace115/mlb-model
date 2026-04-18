# MLB ARTIFACT CANONICALIZATION PLAN

**Date:** 2026-04-18

---

## BUCKET 1 — SAFE TO CANONICALIZE NOW

**Empty.** No safe canonicalizations can be executed without human decisions.

The local-only session files do not need local canonicalization — they are already in their correct canonical paths. They need a git commit+push to sync to remote, which is a human decision, not a file-copy operation.

The recovery substrates already match across both locations. No copies needed.

---

## BUCKET 2 — NEEDS MANUAL DECISION

### 2.1 Sync Session Work to Remote (35 files)

**Conflicting state:** 35 files exist locally, 0 exist on remote.

**What differs:** The remote server has empty `research/results/` and no `research/discovery/` directory. The local Mac has all session work from the H03 closeout, bounded discovery pass, D01/D01A/D02 tests, and D-family status memo.

**Decision needed:** Whether to commit and push these files to the shared git repo, making them available on the remote server. All prompts specified "DO NOT COMMIT" — an explicit human decision to commit is required.

**Files involved:**
- `research/results/mlb_h03_family_closeout/` (4 files)
- `research/discovery/mlb_bounded_discovery_pass_01/` (6 files)
- `research/results/mlb_d01_manual_historical_test/` (5 files)
- `research/results/mlb_d01a_formulation_stability_check/` (5 files)
- `research/results/mlb_d02_manual_historical_test/` (5 files)
- `research/results/mlb_d_family_status/` (4 files)
- `research/recovery/mlb_artifact_reconciliation/` (5 files — this package)

### 2.2 Canonical Object Naming Resolution

**Conflicting state:** All session prompts referenced `mlb_canonical_historical_research_matchup_object` as the expected canonical object. It does not exist. `mlb_matchup_table_base` was used as a documented fallback everywhere.

**Decision needed:** Either:
- **(A)** Create `research/recovery/mlb_canonical_historical_research_matchup_object/` as a formal alias (copy or symlink from matchup_table_base) with its own registry documenting the equivalence
- **(B)** Update all future prompts to reference `mlb_matchup_table_base` directly and stop referencing the canonical historical object name
- **(C)** Create a genuinely separate canonical object that builds on matchup_table_base with additional fields or structure

Option A is the simplest. Option B avoids artifact duplication. Option C is the most work but may be warranted if the canonical object should differ from the matchup table base.

---

## BUCKET 3 — TRULY MISSING (DO NOT FABRICATE)

### 3.1 Orchestration Layer (7 files)

| Artifact | Why Missing | What Would Recreate It |
|---|---|---|
| `mlb_research_orchestrator.py` | Never designed or built | New software engineering work — routing logic, workflow dispatch |
| `mlb_research_orchestration_config.json` | Never designed | New design work — define configuration schema |
| `mlb_research_object_router.json` | Never designed | New design work — map objects to workflows |
| `mlb_research_workflow_templates.json` | Never designed | New design work — define standard workflow shapes |
| `mlb_research_branch_status_schema.json` | Never designed | New schema design — formalize branch status fields |
| `MLB_RESEARCH_ORCHESTRATION_REPORT.md` | Never written | Documentation — describe the orchestration system |
| `MLB_RESEARCH_ORCHESTRATION_REGISTRY.json` | Never written | Registry — track all passes and branches |

**Assessment:** The orchestration layer is the largest governance gap. It was referenced as if it existed but was never built. Creating it requires deliberate design decisions about how research passes are structured, validated, and tracked. It cannot be fabricated from the session work alone.

### 3.2 Manifests (2 files)

| Artifact | Why Missing | What Would Recreate It |
|---|---|---|
| `MLB_STACK_APPROVED_OBJECTS_MANIFEST.json` | Never created | Enumerate all approved data objects with their paths, versions, and usage rules |
| `MLB_STACK_BANNED_OBJECTS_MANIFEST.json` | Never created | Enumerate all banned/deprecated objects that must not be used in research |

**Assessment:** These require explicit decisions about which objects are approved and banned. The substrate stack acceptance memo provides a starting point (5 substrates accepted, matchup table base built from them) but a formal manifest was never created.

### 3.3 Original H-Family Branch Artifacts (7 branch directories)

| Artifact | Why Missing | What Would Recreate It |
|---|---|---|
| H01 original branch files | Never persisted to disk | Would require original test scripts, data, and results — not recoverable |
| H02 original branch files | Never persisted to disk | Same |
| H03 parent original files | Never persisted to disk | Same |
| H03A–D original files | Never persisted to disk | Same |

**Assessment:** The H01/H02/H03/H03A-D branch research was conducted in prior conversations but artifacts were never written to disk. The H03 family closeout was reconstructed from verified user-confirmed summaries. The original branch artifacts (reports, registries, stage tables) cannot be honestly recreated because the original test scripts and exact numerical results are not recoverable. The provisional closeout is the best available record.

---

*Plan generated: 2026-04-18*
