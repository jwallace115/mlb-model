# MLB CONTROL-PLANE RECOVERY AUDIT REPORT

**Audit Date:** 2026-04-19
**Search Root:** `/Users/jw115/mlb-model/`

---

## 1. PURPOSE

Determine whether the missing MLB orchestration layer and MLB_RUNTIME_OBJECT_V1 are recoverable from non-canonical local paths, or whether a full rebuild is required.

---

## 2. SEARCH ROOT CONFIRMATION

Search conducted under `/Users/jw115/mlb-model/` only. No VM paths. No external directories. Also checked: git stash (empty), git worktrees (one worktree at `.claude/worktrees/funny-noyce` — no target files found there either).

---

## 3. KNOWN SURVIVING ARTIFACTS

| Artifact | Status |
|---|---|
| `research/engine_foundation/mlb_engine_v1_foundation/` | PRESENT — 18 files including frozen base object parquet |
| `research/results/` | PRESENT — 11 subdirectories (D-family, E-family, W01, W01A, H03 closeout) |
| `research/discovery/` | PRESENT — pass 01 and pass 03 (pass 02 missing) |
| `research/recovery/` | PRESENT — all substrate families intact |
| `mlb_sim/data/mlb_odds_closing_canonical.parquet` | PRESENT |

---

## 4. ORCHESTRATION AUDIT

All 9 orchestration files searched by exact name under entire repo root.

**Result: ALL 9 FILES MISSING.**

No canonical copies. No non-canonical copies. No partial copies. No renamed variants. Not in git stash. Not in worktrees. The `research/orchestration/` directory does not exist.

These files were created during a prior conversation session, never committed, and have been lost when the session working state was not preserved.

---

## 5. RUNTIME OBJECT AUDIT

All 9 runtime object files (including backup parquet) searched by exact name under entire repo root.

**Result: ALL 9 FILES MISSING.**

The `research/runtime_objects/` directory does not exist. No runtime object parquet, no documentation, no field dictionary, no correction backup. Same cause as orchestration: created in session, never committed, lost.

---

## 6. PASS 02 AUDIT

All 3 Pass 02 discovery files searched by exact name under entire repo root.

**Result: ALL 3 FILES MISSING.**

The `research/discovery/mlb_bounded_discovery_pass_02/` directory does not exist. Pass 01 and Pass 03 survived (they were created in an earlier session or on the same filesystem state that persisted), but Pass 02 was lost.

---

## 7. RECOVERY CLASSIFICATION SUMMARY

| Category | Count |
|---|---|
| CANONICAL_PRESENT | 0 |
| NONCANONICAL_PRESENT | 0 |
| MISSING | 21 |
| DUPLICATED | 0 |
| AMBIGUOUS_MATCH | 0 |

**All 21 target files are definitively MISSING.** No local restore is possible.

---

## 8. SAFE RESTORE OPPORTUNITIES

**None.** There are zero files that can be restored by copying from a non-canonical local path. All 21 targets must be rebuilt.

---

## 9. REBUILD-REQUIRED OBJECTS

### Orchestration Layer (9 files)
Must be rebuilt from the surviving engine foundation package. The prior session's exact file contents are documented in conversation context but not on disk. A rebuild task can recreate them from the frozen foundation package + prior design specifications.

### Runtime Object (9 files including backup)
Must be rebuilt from the surviving engine foundation package base object + game_table + umpire substrate. The build logic is documented in conversation context and in the surviving engine foundation registry. The umpire-field correction (removing umpire_over_rate and umpire_k_rate) must be re-applied.

### Pass 02 Discovery (3 files)
Must be recreated from conversation context. The E01/E02 candidates and their outcomes are documented in the surviving E-family test results and closeout. The discovery pass itself was the source for those tests.

---

## 10. RECOMMENDED NEXT STEP

**FULL_REBUILD_REQUIRED**

All 21 missing files must be rebuilt. No partial restore is possible. The rebuild should be done in this order:

1. **Orchestration layer** (9 files) — from frozen foundation package
2. **Runtime object** (8 files + backup) — from frozen base object + approved joins + umpire correction
3. **Pass 02 discovery** (3 files) — from conversation context and surviving E-family results

The frozen engine foundation package (`research/engine_foundation/mlb_engine_v1_foundation/`) survived intact and provides the complete specification for rebuilding both the orchestration layer and runtime object. The rebuild is deterministic — all design decisions were documented in the foundation package registry and caveats.

---

## 11. FINAL STATUS

**AUDIT_COMPLETE**

All 21 target files audited. All confirmed MISSING with no local restore path. Full rebuild required from the surviving frozen engine foundation package.

---

*Audit completed: 2026-04-19*
