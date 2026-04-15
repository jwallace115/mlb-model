# ROLLING STARTER PROFILE — SELF-AUDIT

**Generated:** 2026-04-15 09:28:44 UTC

---

## 12-QUESTION SELF-AUDIT

### Q01: Is there any same-game leakage in the rolling features?

NO. shift(1) is applied before every rolling window. Game N uses only games 1..N-1 within the player-season group. Verified: the shift is applied inside the groupby transform, not globally.

### Q02: Is there cross-season leakage?

NO. Grouping is by player_id × season. The rolling window resets at the start of each new season. A pitcher's final game in 2024 does NOT contribute to their first-game rolling value in 2025.

### Q03: Are doubleheader games handled correctly?

YES. game_number (1 or 2) is merged from game_table.parquet and used as a sort tiebreaker within game_date. 324 game-2 doubleheader starts identified. The sort order [player_id, season, game_date, game_number] ensures game-1 appears before game-2.

### Q04: Were any background tasks used?

NO. All steps were run synchronously in the foreground. No background tasks, threads, or async operations were used at any point in this build.

### Q05: Were any files created outside the 4 approved output files?

NO. The only permanent writes are: rolling_starter_profile.parquet, ROLLING_STARTER_PROFILE_BUILD_REPORT.md, ROLLING_STARTER_PROFILE_BUILD_REGISTRY.json, ROLLING_STARTER_PROFILE_SELF_AUDIT.md. Temporary files in /tmp were used for inter-step data passing but were not written to the project directory.

### Q06: Is the parquet round-trip verified?

YES. After saving, the file was reloaded and verified: 19,914 rows × 55 cols, row count and column list exact match confirmed.

### Q07: What is the null rate for rolling features and is it expected?

Overall null rates: last_3=16.1%, last_5=22.3%, last_10=32.6%. These are expected: last_3 requires 2 prior starts (few at season start), last_10 requires 5. The 2026 high null rate (86.9%) reflects an early-season dataset with <5 starts for most pitchers. No imputation was applied; NaN is the honest value.

### Q08: Are Statcast rolling features correctly conditioned on SC availability?

YES. Statcast columns (whiff_rate, hard_hit_rate, barrel_rate, etc.) have 7.7% null at the row level (SC-unenriched games). Rolling means over these columns will be NaN when the trailing window contains insufficient SC-enriched starts. The sc_enriched flag is carried in the output for downstream conditioning.

### Q09: Are derived rates (k_rate, bb_rate, etc.) present in the output?

NO — by design. Derived rates are intermediate computations used only as rolling inputs. Only their rolled versions (e.g. batmiss_k_rate_last_5) appear in the output. Exceptions: batters_faced and innings_pitched are carried raw as CARRIED_ONLY fields for downstream denominator use.

### Q10: Does the feature family taxonomy match the approved spec?

YES. Five families implemented: BATMISS (2 base metrics), COMMAND (2), CONTACT (4), WORKLOAD (4), DAMAGE (2). Total: 14 base metrics × 3 windows = 42 rolling columns. whip_game was computed but excluded from the output (redundant with hits_per_bf + bb_rate components). All families present in output with correct _last_3 / _last_5 / _last_10 suffixes.

### Q11: Is the output sorted correctly for downstream join operations?

YES. Output is sorted by [season, game_date, game_number, game_pk, player_id]. This enables clean merge operations on (game_pk, player_id) as a joint key.

### Q12: Are there any data quality warnings that downstream users must know?

Four warnings documented in BUILD_REPORT and REGISTRY: (1) 2026 null rates high — early season. (2) balls_in_zone / contacts_in_zone absent from source. (3) 2023 SC enrichment slightly lower (89.3%). (4) min_periods thresholds cause NaN in wider windows for early-season starters.

---

## SUMMARY VERDICT

| Check | Result |
|-------|--------|
| PIT-safety (shift applied) | PASS |
| Cross-season isolation | PASS |
| Doubleheader ordering | PASS |
| Background tasks used | NONE |
| Unauthorized files created | NONE |
| Round-trip verification | PASS |
| Null rates expected | PASS |
| SC conditioning | PASS |
| Output column set correct | PASS |
| Family taxonomy correct | PASS |
| Output sort order correct | PASS |
| Warnings documented | YES (4) |

**OVERALL: APPROVED — no issues found**
