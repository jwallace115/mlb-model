# MLB RESEARCH — START HERE

**Last Updated:** 2026-04-19 (rebuilt after session-loss event)

## 1. WHAT THIS DIRECTORY IS
`/Users/jw115/mlb-model/research/orchestration/` — MLB research orchestration layer. Controls which data objects are approved for MLB engine/research work. Enforces the frozen foundation package as the sole approved input source.

## 2. SESSION LOG
**Check first:** `/Users/jw115/mlb-model/research/SESSION_LOG.txt`
Every session must read this log before proceeding.

## 3. PRIMARY MLB ENGINE FOUNDATION PATH
```
/Users/jw115/mlb-model/research/engine_foundation/mlb_engine_v1_foundation/
```

## 4. PRIMARY ORCHESTRATION PATH
```
/Users/jw115/mlb-model/research/orchestration/
```

## 5. REAL CURRENT BASE OBJECT
```
research/engine_foundation/mlb_engine_v1_foundation/base_object/mlb_matchup_table_base.parquet
```
19,804 rows x 107 columns. Grain: one row per (game_pk, team). This IS the canonical historical research base object.

## 6. READ THESE FILES FIRST
- `MLB_ENGINE_V1_FOUNDATION_REGISTRY.json`
- `MLB_ENGINE_V1_FOUNDATION_INCLUDED_ARTIFACTS.csv`
- `MLB_ENGINE_V1_FOUNDATION_EXCLUDED_ARTIFACTS.csv`
- `MLB_ENGINE_V1_FOUNDATION_CAVEATS.json`
- `MLB_ENGINE_V1_FOUNDATION_PIT_SAFE_SIGNOFF_REPORT.md`
- `MLB_RESEARCH_ORCHESTRATION_REGISTRY.json`
- `mlb_research_object_router.json`
- `mlb_research_workflow_templates.json`

## 7. HARD RULES
1. Use only files listed in the frozen foundation package.
2. No repo-wide fallback.
3. No closest-equivalent substitution.
4. Carry forward all caveats.
5. Default deny — any path not in included manifest is rejected.
6. Check SESSION_LOG.txt at every session start.

## 8. IF A NEEDED INPUT IS MISSING
Hard stop. Report the missing artifact. Do not fabricate or substitute.
