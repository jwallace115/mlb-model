# MLB RUNTIME OBJECT V1 — START HERE

**Rebuilt:** 2026-04-19

## 1. WHAT THIS OBJECT IS
The clean historical default MLB research working table. 19,430 rows x 130 columns. One row per (game_pk, team). Covers 2022-2025 only (2026 excluded). Contains team-side matchup features (91 approved), game context (weather, park, rest), umpire identity fields, and outcome variables (actual_total, actual_f5_total, scores).

**This object does NOT contain default historical umpire rating features.** If a branch needs historical umpire ratings, join from `mlb_umpire_historical_layer` through the frozen foundation package.

## 2. WHERE IT LIVES
```
/Users/jw115/mlb-model/research/runtime_objects/mlb_runtime_object_v1/mlb_runtime_object_v1.parquet
```

## 3. SESSION LOG
Check `/Users/jw115/mlb-model/research/SESSION_LOG.txt` at every session start.

## 4. FAMILIES MERGED
1. `mlb_matchup_table_base` — 107 columns (base)
2. `game_table_spine` — 22 columns (outcome + context, minus umpire ratings)
3. `mlb_umpire_substrate` — 1 column (umpire_matched)

## 5. HARD RULES
1. Derived only from the frozen MLB engine foundation package.
2. Must be used with the orchestration layer.
3. No outside-package files allowed.
4. Historical umpire ratings must be joined separately when needed.
5. Check SESSION_LOG.txt at session start.
