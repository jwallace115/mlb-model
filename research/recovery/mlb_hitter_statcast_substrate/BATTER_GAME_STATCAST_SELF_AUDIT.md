# BATTER-GAME HITTER STATCAST SUBSTRATE — SELF-AUDIT

**Object ID:** mlb_batter_game_statcast_v1
**Build Date:** 2026-04-15
**Auditor:** build script (automated self-check)

---

## 12-QUESTION PIT-SAFETY AUDIT

**Q1. Canonical source exactly `statcast_chunk_*.parquet`?**
YES. All 33 chunk files sourced exclusively from `mlb/props/data/statcast_chunk_*.parquet`. `statcast_batters.parquet` was not used.

**Q2. Contaminated sources used?**
NO. `statcast_batters.parquet` (pre-aggregated, potentially rolling) was not loaded or referenced. `hitter_game_logs.parquet` was used only for the join to carry team/home_away/season/batting_order_position — it provides no Statcast contact metrics.

**Q3. Dedup on exact key first?**
YES. `drop_duplicates(subset=['game_pk', 'pitcher', 'at_bat_number', 'pitch_number'], keep='first')` was the first operation on each chunk, before any BIP filtering or aggregation.

**Q4. Fallback dedup keys invented?**
NO. The exact 4-field key specified in the build spec was used. No fallback or partial keys were used.

**Q5. Aggregation before dedup?**
NO. Within each chunk, dedup ran first. Aggregation (batter-game groupby) was performed only on the post-dedup chunk DataFrame.

**Q6. Rolling features built?**
NO. All aggregations are within a single (game_pk, batter, game_date) group. No multi-game windows, rolling means, lag features, or cumulative sums were computed.

**Q7. Unauthorized files written?**
NO. Exactly 4 files were written, all to `research/recovery/mlb_hitter_statcast_substrate/`:
  1. `batter_game_statcast.parquet`
  2. `BATTER_GAME_STATCAST_BUILD_REPORT.md`
  3. `BATTER_GAME_STATCAST_BUILD_REGISTRY.json`
  4. `BATTER_GAME_STATCAST_SELF_AUDIT.md`
No live objects, shadow objects, or other paths were modified.

**Q8. Background tasks spawned?**
NO. All computation ran in a single synchronous Python process with no subprocess, threading, or async calls.

**Q9. Join logic direct and documented?**
YES. Inner join on `(game_pk, batter == player_id)` to `hitter_game_logs.parquet`. Join type, fields carried, match rate, and unmatched count are documented in the build report and registry.

**Q10. Unmatched rows silently dropped?**
NO. Unmatched Statcast batter-game rows are explicitly counted and reported: 28,699 rows (12.7% of aggregated batter-games). The INNER join is intentional and documented.

**Q11. Safe for future shift(1) rolling?**
YES. The substrate is indexed by (game_pk, game_date, batter) with one row per batter per game. Any downstream rolling-feature build can sort by (batter, game_date), apply shift(1), and produce lag-1 features that are strictly prior to the target game. No within-game leakage is possible from this substrate.

**Q12. `batting_order_position` approved for pregame top/bottom feature?**
NO — EXPLICITLY NOT APPROVED. `batting_order_position` reflects the actual lineup position used in that game (a post-fact outcome from HGL). It cannot be used as a pregame feature without constructing it independently from pre-game confirmed lineup announcements with proper date-gating.

---

## SUMMARY VERDICT

All 12 audit questions pass. This substrate is **PIT-SAFE** for use as an input to downstream rolling-feature builders, subject to the warnings documented in the build report.

**BUILD COMPLETE — AUDIT PASSED**
2026-04-15 02:32 UTC
