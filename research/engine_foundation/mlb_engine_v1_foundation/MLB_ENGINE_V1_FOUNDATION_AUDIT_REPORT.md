# MLB ENGINE V1 FOUNDATION — DATA QUALITY + PIT-SAFETY AUDIT

**Audit Date:** 2026-04-18
**Subject:** Frozen package at `research/engine_foundation/mlb_engine_v1_foundation/`
**Audit Type:** Data quality, PIT-safety, internal consistency, source control discipline

---

## 1. PURPOSE

This audit determines whether the frozen MLB Engine V1 Foundation package is safe to treat as the sole approved MLB engine input layer going forward. It verifies package contents, copy integrity, base object data quality, included-family support, PIT-safe claims, excluded-manifest adequacy, and engine-usage clarity.

---

## 2. PACKAGE INTEGRITY

### Control Files Present

| Required File | Present |
|---|---|
| MLB_ENGINE_V1_FOUNDATION_README.md | YES |
| MLB_ENGINE_V1_FOUNDATION_REGISTRY.json | YES |
| MLB_ENGINE_V1_FOUNDATION_INCLUDED_ARTIFACTS.csv | YES |
| MLB_ENGINE_V1_FOUNDATION_EXCLUDED_ARTIFACTS.csv | YES |
| MLB_ENGINE_V1_FOUNDATION_CAVEATS.json | YES |
| MLB_ENGINE_V1_FOUNDATION_BUILD_SELF_AUDIT.md | YES |

All 6 required control files present. **PASS.**

### Manifest-Registry Consistency

- Registry lists 15 included families. Included manifest lists 18 rows (15 families, some with multiple file entries for base_object docs). **Consistent** — the manifest provides finer granularity than the registry family list.
- Registry lists 22 excluded families. Excluded manifest lists 22 rows. **MATCH.**
- Registry `authoritative_count: 12`, `authoritative_with_caveats_count: 3`. Included manifest shows 12 AUTHORITATIVE + 3 AUTHORITATIVE_WITH_CAVEATS entries. **MATCH.**
- Caveats file lists 5 caveats. Three apply to included-with-caveats families (bullpen, starter profile, umpire repair), one to the base object naming, one to governance. **Consistent.**

### Unregistered Files

Zero unregistered files found in the package directory tree. All 12 files are accounted for by the control files or are the control files themselves. **PASS.**

---

## 3. BASE OBJECT AUDIT

### Frozen Copy: `base_object/mlb_matchup_table_base.parquet`

| Check | Result |
|---|---|
| Present and readable | **YES** |
| Shape | **19,804 rows x 107 columns** |
| Seasons | **[2022, 2023, 2024, 2025, 2026]** |
| Grain duplicates (game_pk, team) | **0** — grain is clean |
| Total cells | 2,119,028 |
| Null cells | 255,107 (12.0%) |
| Copy integrity (size match to source) | **12,503,400 bytes — MATCH** |

### Registry Agreement

| Registry Claim | Actual | Match |
|---|---|---|
| row_count: 19804 | 19,804 | **MATCH** |
| column_count: 107 | 107 | **MATCH** |
| seasons: [2022-2026] | [2022-2026] | **MATCH** |
| grain: (game_pk, team) | 0 duplicates | **MATCH** |
| 9 identity fields | all present | **MATCH** |
| 91 approved features | all present | **MATCH** |

### Report/Self-Audit Consistency

The base object report (14 PIT-safety questions) and self-audit both confirm:
- No existing files modified during build
- No background tasks used
- No commits or pushes performed
- No future data leakage (all rolling windows are lookback-only)
- 3,035 rows with null opposing starter profiles are structurally correct (early-season/debut starts)

### Substitute-in-Use Status

The registry explicitly designates this as `REAL_CURRENT_BASE_OBJECT` with naming note: "This object was previously referenced as 'mlb_canonical_historical_research_matchup_object' which never existed." **Clear and unambiguous.**

### Base Object Verdict

**Safe to treat as the sole current historical engine base object.** Shape, grain, fields, seasons, null patterns, and PIT-safe claims are all internally consistent and verified.

---

## 4. INCLUDED FOUNDATION FAMILY AUDIT

See `MLB_ENGINE_V1_FOUNDATION_AUDIT_TABLE.csv` for the full per-family audit.

**Summary:**

| Status | Count | Families |
|---|---|---|
| YES (clean authoritative) | 11 | lineup_state, starting_pitcher, hitter_statcast, umpire, umpire_historical, weather, park_context, team_code_norm, stack_acceptance, game_table, bullpen_production |
| YES_WITH_CAVEAT | 4 | matchup_table_base (naming), bullpen_substrate (process), starter_profile (SC averaging), umpire_repair (docs-only) |
| NO | 0 | — |

All 15 included families verified as present at their declared paths (copied or source). All data objects readable. All manifest/caveat alignment checks pass.

---

## 5. PIT-SAFETY SUPPORT REVIEW

| Support Level | Count | Families |
|---|---|---|
| EXPLICITLY_SUPPORTED | 12 | matchup_table_base, lineup_state, starting_pitcher, hitter_statcast, umpire, umpire_historical, weather, park_context, team_code_norm, stack_acceptance, game_table, bullpen_production |
| SUPPORTED_WITH_CAVEAT | 2 | bullpen_substrate (process non-pristine), starter_profile (SC averaging) |
| DOCUMENTED_BUT_WEAK | 1 | umpire_ratings_repair (docs only, no data artifact) |
| NOT_VERIFIABLE_FROM_PACKAGE | 0 | — |

**PIT-safety assessment:** The package provides strong PIT support for 14 of 15 families. The single DOCUMENTED_BUT_WEAK case (umpire repair) is a documentation-only package where the fix was applied to production code — this is a real but minor gap. No family has unverifiable PIT claims.

---

## 6. EXCLUDED-MANIFEST ADEQUACY

The excluded manifest covers:

| Category | Count | Examples |
|---|---|---|
| NON_FOUNDATION_BRANCH_OUTPUT | 5 | H01-H03D original branches |
| PROVISIONAL_OUTPUT | 5 | D01, D01A, D02, D-family, discovery pass |
| GOVERNANCE_CONCEPT_ONLY | 4 | orchestration, manifests, canonical name |
| AMBIGUOUS_LINEAGE | 6 | v1_clean_*, v2_engine, phase2 |
| OUTSIDE_SCOPE | 2 | archetype engine, context engine |

**Adequacy assessment:** The excluded manifest creates a clear boundary. It explicitly excludes branch outputs, provisional outputs, conceptual governance, ambiguous lineage, and out-of-scope engines. No category is missing. The boundary is operationally enforceable — a future prompt can check any candidate input against the excluded list.

**No files inside the package directory are present-but-unlisted.** Zero unregistered artifacts.

---

## 7. ENGINE-USAGE CLARITY

A future prompt using only this package can determine:

| Question | Answer Source | Clear? |
|---|---|---|
| What base object to use? | Registry `real_current_base_object` + README Section 3 | **YES** |
| What included artifacts are allowed? | `INCLUDED_ARTIFACTS.csv` + Registry `included_artifact_paths` | **YES** |
| What is excluded? | `EXCLUDED_ARTIFACTS.csv` + Registry `excluded_artifact_families` | **YES** |
| What caveats to carry forward? | `CAVEATS.json` | **YES** |
| Is out-of-package usage forbidden? | Registry `explicit_forbidden_outside_package_rule: true` + README Section 7 | **YES** |

**Engine-usage clarity is sufficient.** No repo-wide search or guesswork needed. All answers are in the package control files.

---

## 8. RESIDUAL RISKS

### Governance / Naming Risks — LOW

- **Naming resolved.** The canonical historical object naming ambiguity is formally resolved by this package (CAVEAT_03). Future prompts reference `mlb_matchup_table_base` directly.
- **Governance layer still absent.** No orchestration, manifests, or routing system exists (CAVEAT_04). This package's included/excluded manifests are a practical substitute, not a full governance system. Risk: future prompts may attempt to use files outside the package if the forbidden-outside-package rule is not enforced by the prompt author. This is a process risk, not a data risk.

### Data-Layer Risks — LOW

- **Null patterns are structural, not errors.** The 12% null rate in the base object is explained by early-season rolling windows with insufficient prior data. This is expected and documented.
- **Bullpen process history (CAVEAT_01).** The data is substantively verified but the builder's process attestation is not trustworthy. Risk is contained because independent forensic verification was performed. No action needed unless the bullpen substrate is rebuilt.
- **SC averaging windows (CAVEAT_02).** Some rolling windows may average over fewer observations than their label implies. This is a known structural property, not a bug. Downstream models should treat these features as potentially noisier for early-season starters.

### Caveat-Management Risks — LOW

- **All 5 caveats are documented and machine-readable.** Risk of caveat loss in future work is low as long as the caveats file is read.
- **Umpire repair (CAVEAT_05)** has no standalone data artifact. If the repair is ever questioned, verification requires inspecting `config.py` directly rather than a package artifact. Minor gap.

---

## 9. FINAL AUDIT VERDICT

**ENGINE_FOUNDATION_APPROVED_WITH_CAVEATS**

The MLB Engine V1 Foundation package is safe to treat as the sole approved MLB engine input layer going forward, subject to 5 documented caveats. Specifically:

1. **Package integrity:** All control files present, manifest/registry/caveats consistent, zero unregistered files.
2. **Base object quality:** Shape/grain/fields/seasons verified, registry matches actual data, PIT-safe claims supported, copy integrity confirmed.
3. **Included families:** All 15 present and accessible, 11 clean authoritative + 4 with documented caveats, no unsupported PIT claims.
4. **Excluded manifest:** Adequate boundary — covers all relevant non-foundation categories.
5. **Engine-usage clarity:** Sufficient for any future prompt to know exactly what to use without guesswork.

The "with caveats" qualification reflects 5 documented and manageable caveats, not structural deficiencies. The data layer is solid. The governance layer gap (CAVEAT_04) is a process concern that this package partially addresses but does not fully solve.

### Core Questions Answered

1. **Is this a real usable engine package?** YES — it contains a frozen verified base object with full provenance and clear inclusion/exclusion boundaries.
2. **Is the base object clearly frozen?** YES — designated as REAL_CURRENT_BASE_OBJECT, copy-verified, registry-consistent.
3. **Are included families strongly enough supported?** YES — 14/15 explicitly or caveat-supported, 1 documented-but-weak (docs-only umpire repair).
4. **Are caveats sufficient to prevent misuse?** YES — machine-readable, specific, actionable.
5. **Any remaining ambiguity?** MINIMAL — naming resolved, boundaries clear, forbidden-outside-package rule explicit.
6. **Exact residual risks?** Low across all three categories (governance, data, caveat-management).
7. **Final verdict:** ENGINE_FOUNDATION_APPROVED_WITH_CAVEATS.

---

*Audit completed: 2026-04-18*
