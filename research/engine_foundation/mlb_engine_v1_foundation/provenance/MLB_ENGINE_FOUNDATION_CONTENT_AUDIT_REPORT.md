# MLB ENGINE FOUNDATION CONTENT AUDIT REPORT

**Date:** 2026-04-18
**Operator:** Claude (automated research assistant)
**Scope:** All MLB engine-building foundation data objects and PIT-safe substrate stack
**Both locations inspected:** Local Mac (`/Users/jw115/mlb-model`) and remote server (`root@142.93.242.4:/root/mlb-model`)

---

## 1. REAL CURRENT FOUNDATION OBJECT

**The real current MLB historical research base object is `mlb_matchup_table_base`.**

| Property | Value |
|---|---|
| Path | `research/recovery/mlb_matchup_table_base/mlb_matchup_table_base.parquet` |
| Rows | 19,804 (2 team-sides per game from 9,902 games) |
| Columns | 107 (9 identity + 7 carried-only + 91 approved features) |
| Seasons | 2022, 2023, 2024, 2025, 2026 (2026 partial) |
| Grain | One row per (game_pk, team) — team-side view |
| Documentation | Report + Registry + Self-Audit all present and consistent |
| PIT-safe | Report PIT verdict: no existing files modified, no background tasks, no commits |
| Local/Remote | Present in both, identical shape (19804x107) |

This object was built from 5 accepted substrates (lineup state, bullpen, per-start starter, rolling starter profile, hitter statcast) plus the game_table spine, with team-code normalization applied during the join. It is the single authoritative research base for all downstream hypothesis testing.

A "canonical historical research matchup object" (`research/recovery/mlb_canonical_historical_research_matchup_object/`) was referenced in multiple prompts but **does not exist and never has**. `mlb_matchup_table_base` is the real object. The naming gap should be formally resolved.

---

## 2. AUTHORITATIVE FOUNDATION FAMILIES

These families are fully present with data object + report + registry + self-audit, content matches expected role, PIT-safe claims are supported, and local/remote copies match:

| # | Family | Data Shape | Grain | Status |
|---|---|---|---|---|
| 1 | **mlb_matchup_table_base** | 19,804 x 107 | team-side per game | AUTHORITATIVE |
| 2 | **mlb_lineup_state_substrate** | 19,712 x 54 | team-side per game | AUTHORITATIVE |
| 3 | **mlb_starter_profile_substrate** | 19,914 x 55 | pitcher-start | AUTHORITATIVE |
| 4 | **mlb_starting_pitcher_substrate** | 19,914 x 46 | pitcher-start | AUTHORITATIVE |
| 5 | **mlb_hitter_statcast_substrate** | 197,497 x 17 | batter-game | AUTHORITATIVE |
| 6 | **mlb_umpire_substrate** | 9,902 x 8 | game | AUTHORITATIVE |
| 7 | **mlb_umpire_historical_layer** | 453 x 10 | umpire-season | AUTHORITATIVE |
| 8 | **mlb_weather_substrate** | 9,902 x 9 | game | AUTHORITATIVE |
| 9 | **mlb_park_context_substrate** | 9,902 x 17 | game | AUTHORITATIVE |
| 10 | **mlb_team_code_normalization** | JSON (6 mappings) | reference | AUTHORITATIVE |
| 11 | **game_table (spine)** | 9,902 x 30 | game | AUTHORITATIVE |
| 12 | **bullpen_features (production)** | 19,804 x 10 | team-side per game | AUTHORITATIVE |

All 12 are present on both machines with matching shapes.

---

## 3. AUTHORITATIVE WITH CAVEATS

| Family | Caveat |
|---|---|
| **mlb_bullpen_substrate** | Builder self-audit falsely claimed "no background tasks used." Background tasks WERE used during build. Substantive PIT-safety was independently verified and accepted per the Stack Acceptance Memo, but process attestation from the original builder cannot be fully trusted. |
| **mlb_umpire_ratings_repair** | Documentation-only package (3 doc files, no parquet). The repair was applied directly to `config.py`. The docs are authoritative as a record of what was changed, but there is no standalone data artifact to verify. |
| **mlb_substrate_stack_acceptance** | Memo only (no registry, no self-audit). This is the master acceptance document for the 5-substrate stack. It documents 3 frozen caveats: (1) team-code normalization mandatory before joins, (2) rolling starter SC fields use available-only averaging, (3) bullpen process history. The memo itself is authoritative but has no formal registry companion. |

---

## 4. SUBSTITUTE OBJECTS CURRENTLY IN USE

| Expected Object | Substitute In Use | Relationship |
|---|---|---|
| `mlb_canonical_historical_research_matchup_object` | `mlb_matchup_table_base` | Functional equivalent. All session work (discovery pass, D01, D01A, D02) used matchup_table_base as a documented fallback. The "canonical historical" name was never instantiated as a separate artifact. |

**Resolution needed:** Either formally designate matchup_table_base as the canonical object, or stop referencing the canonical historical name in future prompts.

---

## 5. PARTIAL OR CONCEPTUAL ARTIFACTS

| Artifact | Status | Notes |
|---|---|---|
| **Orchestration layer** | CONCEPTUAL_ONLY | Referenced in multiple prompts as if it existed. 7 files (orchestrator.py, config, router, templates, schema, report, registry) were never created. The `research/orchestration/` directory contains only a `__pycache__` locally and does not exist on remote. |
| **Approved objects manifest** | CONCEPTUAL_ONLY | Referenced but never created. The Stack Acceptance Memo serves as an informal equivalent for the 5 base substrates. |
| **Banned objects manifest** | CONCEPTUAL_ONLY | Referenced but never created. No formal list of banned sources exists. |

---

## 6. TRULY MISSING FOUNDATIONAL ARTIFACTS

| Artifact | Why Missing | Impact |
|---|---|---|
| Canonical historical research matchup object (by that name) | Never created as a distinct artifact | Low — matchup_table_base serves the role; only the naming is unresolved |
| Orchestration layer (7 files) | Never designed or built | HIGH — prevents autonomous discovery governance |
| Approved objects manifest | Never created | MEDIUM — no formal boundary enforcement |
| Banned objects manifest | Never created | MEDIUM — no formal exclusion enforcement |

---

## 7. GOVERNANCE LAYER STATUS

The intended governance layer (orchestration, manifests, canonical router) **does not exist and never has**. It is entirely conceptual — referenced in prompts as if available, but no files were ever created.

What DOES exist as informal governance:
- The Stack Acceptance Memo (defines accepted substrates with caveats)
- The matchup table base registry (documents field classifications)
- The team-code normalization map (enables cross-substrate joins)
- The H03 closeout memo (anti-duplication reference for closed families)

These informal artifacts have been sufficient for the manual research conducted so far, but they do not constitute a formal governance system capable of supporting autonomous discovery.

---

## 8. FINAL FOUNDATION VERDICT

**FOUNDATION_VALID_WITH_GAPS**

The MLB engine foundation is substantively valid:
- 12 authoritative data families are present on both machines with matching shapes
- All 5 accepted substrates pass content verification
- The matchup table base (19,804 x 107) is a real, documented, PIT-safe research object
- PIT-safe claims are supported by contents and independent forensic verification
- The game_table spine provides the outcome variable (actual_total) for all downstream testing
- Team-code normalization was applied during the matchup table build

The gaps are governance-layer, not data-layer:
- The canonical historical object naming is unresolved (cosmetic)
- The orchestration layer does not exist (prevents autonomous discovery)
- Manifests do not exist (prevents formal boundary enforcement)

**The foundation is solid enough to support honest manual research.** It is not yet equipped to support autonomous or self-governing research without the governance layer being built.

---

### Core Questions Answered

1. **What is the real current MLB historical research base object?**
   `mlb_matchup_table_base` — 19,804 x 107, 2022–2026, team-side grain.

2. **Does a true canonical historical research matchup object actually exist?**
   NO. `mlb_matchup_table_base` is the real substitute-in-use. The canonical name was never instantiated.

3. **Which substrate families are genuinely present and authoritative?**
   All 12 listed in Section 2 — every substrate referenced by the Stack Acceptance Memo plus the game-level context families (umpire, weather, park).

4. **Which substrate families are only partial / conceptual / missing?**
   The orchestration layer and manifests are conceptual only. The umpire ratings repair is documentation-only (no data artifact). Everything else is fully present.

5. **Are the PIT-safe foundation claims supported?**
   YES — with one documented exception (bullpen substrate builder self-audit was false about background tasks; substantive PIT verified independently).

6. **Is the engine foundation substantively valid even with incomplete governance?**
   YES. The data layer is solid. The governance layer has gaps but these affect autonomous process control, not data integrity.

7. **What exact gaps remain?**
   (a) Canonical object naming resolution, (b) orchestration layer creation, (c) manifest creation. All are governance/naming gaps, not data gaps.

---

*Report generated: 2026-04-18*
