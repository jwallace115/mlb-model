# MLB ENGINE V1 FOUNDATION

**Version:** 1.0
**Build Date:** 2026-04-18
**Primary Source of Truth:** Local Mac (`/Users/jw115/mlb-model`)
**Foundation Audit Basis:** `MLB_ENGINE_FOUNDATION_CONTENT_AUDIT_REPORT.md` (2026-04-18)

---

## 1. PURPOSE

This is the single approved MLB engine-foundation reference point. All future MLB engine work must reference this package rather than scattered repo paths. This package eliminates source drift and path ambiguity by freezing exactly what is approved, what is excluded, and where everything lives.

This package replaces ad-hoc references to `mlb_matchup_table_base`, `mlb_canonical_historical_research_matchup_object`, and individual substrate paths. All those objects are either included here or explicitly excluded.

---

## 2. PRIMARY SOURCE OF TRUTH

This package was built locally on the Mac. It is the primary canonical source. The remote server (`root@142.93.242.4`) was not modified by this build.

The package references source artifacts at their original locations within the local repo. The `base_object/` subfolder contains a frozen copy of the primary research base object for convenience. The `provenance/` subfolder contains copies of key acceptance and audit documentation.

Original source artifacts remain in place and are not modified.

---

## 3. REAL CURRENT MLB BASE OBJECT

**The real current MLB historical research base object is `mlb_matchup_table_base`.**

| Property | Value |
|---|---|
| Frozen copy | `base_object/mlb_matchup_table_base.parquet` |
| Original source | `research/recovery/mlb_matchup_table_base/mlb_matchup_table_base.parquet` |
| Rows | 19,804 (team-side, 2 per game) |
| Columns | 107 (9 identity + 7 carried-only + 91 approved features) |
| Seasons | 2022, 2023, 2024, 2025, 2026 (2026 partial) |
| Grain | One row per (game_pk, team) |

**Naming resolution:** A "canonical historical research matchup object" was referenced in multiple prior prompts but never existed as a separate artifact. `mlb_matchup_table_base` is and always has been the real object. Future prompts must stop guessing and use this package registry instead. The intended canonical name is formally resolved to `mlb_matchup_table_base`.

---

## 4. WHAT IS INCLUDED

**15 artifact families** are included in this foundation (12 AUTHORITATIVE, 3 AUTHORITATIVE_WITH_CAVEATS). See `MLB_ENGINE_V1_FOUNDATION_INCLUDED_ARTIFACTS.csv` for the full list with paths and roles.

Included families:
1. mlb_matchup_table_base (base object — frozen copy in package)
2. mlb_lineup_state_substrate
3. mlb_bullpen_substrate (with caveats)
4. mlb_starter_profile_substrate
5. mlb_starting_pitcher_substrate
6. mlb_hitter_statcast_substrate
7. mlb_umpire_substrate
8. mlb_umpire_historical_layer
9. mlb_umpire_ratings_repair (docs only, with caveats)
10. mlb_weather_substrate
11. mlb_park_context_substrate
12. mlb_team_code_normalization
13. mlb_substrate_stack_acceptance (provenance — frozen copy in package)
14. game_table spine
15. bullpen_features production

---

## 5. WHAT IS EXCLUDED

See `MLB_ENGINE_V1_FOUNDATION_EXCLUDED_ARTIFACTS.csv` for the full list.

Key exclusions:
- H01/H02/H03 family branch outputs (non-foundation research results)
- D01/D01A/D02/D-family outputs (provisional research results)
- Bounded discovery pass outputs (provisional discovery, not foundation)
- Orchestration layer (conceptual only — never created)
- Approved/banned manifests (never created)
- Old V1/phase2/ambiguous-lineage objects
- Any artifact classified as PARTIAL, CONCEPTUAL, or MISSING by the audit

---

## 6. CAVEATS

See `MLB_ENGINE_V1_FOUNDATION_CAVEATS.json` for machine-readable details.

Key caveats:
1. **Bullpen substrate process:** Builder self-audit falsely claimed no background tasks. Substantive PIT-safety verified independently. Data is accepted but process attestation is not trustworthy.
2. **Rolling starter SC averaging:** Available-only windowing means a `last_3` value may be computed from fewer than 3 observations. Indistinguishable from fully observed windows.
3. **Base object naming:** `mlb_matchup_table_base` is the real object standing in for the intended `mlb_canonical_historical_research_matchup_object`. Resolved by this package.
4. **Governance layer incomplete:** No orchestration, no manifests. This package provides approved/excluded lists as a practical substitute.

---

## 7. FUTURE USAGE RULE

**Future MLB engine work may use only files listed in `MLB_ENGINE_V1_FOUNDATION_REGISTRY.json` and `MLB_ENGINE_V1_FOUNDATION_INCLUDED_ARTIFACTS.csv`.**

**Anything outside this package is forbidden for engine use unless explicitly promoted in a future versioned foundation package (V2 or later).**

This rule applies to:
- Hypothesis test construction
- Feature selection
- Model training data
- Backtest evaluation data
- Any engine-building activity

This rule does NOT apply to:
- Reading branch result documentation for anti-duplication
- Session-level exploration that does not produce engine artifacts

---

## 8. HOW TO BUILD A V2 FOUNDATION LATER

To create a future MLB_ENGINE_V2_FOUNDATION:
1. Start with this V1 package as the baseline
2. Document what is being added, removed, or modified
3. Run a new foundation content audit against the proposed changes
4. Create the V2 package in `research/engine_foundation/mlb_engine_v2_foundation/`
5. Update the registry, included/excluded manifests, and caveats
6. Explicitly deprecate V1 in the V2 README
7. Do not modify V1 — it remains frozen as a historical reference

---

## 9. FINAL PACKAGE STATUS

**FOUNDATION_PACKAGE_CREATED**

This package freezes the MLB engine foundation as of 2026-04-18. It contains 15 included artifact families (12 authoritative, 3 with documented caveats), 4 documented caveats, and explicit exclusion of all non-foundation artifacts. The real current base object (`mlb_matchup_table_base`, 19,804 x 107) is frozen into the package with full provenance.

---

*Package built: 2026-04-18*
*Primary source of truth: Local Mac*
