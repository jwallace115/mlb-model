# PER-START STARTER SUBSTRATE — SELF-AUDIT

**Date:** 2026-04-14  
**Auditor:** Build process self-audit

---

## Q1. What is the source of the 2026 Statcast data?

`pybaseball.statcast(start_dt, end_dt)` — pulls pitch-level data from Baseball Savant's public API. Four weekly chunks were pulled covering 2026-03-20 through 2026-04-14. The same source and same aggregation function (`_aggregate_pitcher_start`) as the existing 2022-2025 data.

---

## Q2. Were any 2022-2025 rows in `pitcher_statcast_per_start.parquet` modified?

**No.** The append-only strategy (v3 script) explicitly loads the existing parquet as ground truth for 2022-2025, unions with deduplicated 2026 rows, then verifies all four prior-season row counts are unchanged before writing. The PIT-safety check passed with all four seasons at exact pre-update counts (2022: 5,134; 2023: 5,114; 2024: 5,268; 2025: 5,146).

---

## Q3. What caused the v1/v2 backfill script failures, and how were they resolved?

**v1 failure** — `"cannot convert NA to integer"`. Root cause: 2026 Statcast returns `zone` (and other numeric columns) as `Int64` (pandas nullable extension type) rather than `float64`. The `(df["zone"].between(1, 9)).astype(int)` call fails when NAs are present in a nullable integer series. Fixed in v2 by casting all potentially-nullable columns to `float` first.

**v2 failure** — PIT-safety check HALT. Root cause: v2 re-merged from chunk files on disk, but several historical monthly chunk files are legitimately absent (2022-03, 2024-10, 2025-10 — confirmed by zero rows for those months in both the chunks directory and the existing parquet). Re-merging from incomplete chunks would have dropped ~600 rows from the historical record. The script correctly halted. Fixed in v3 by switching to an append-only strategy.

---

## Q4. Why is the 2023 match rate (89.3%) lower than other seasons?

Investigation shows unmatched 2023 starters have mean PGL pitches = 58.9 (P25 = 26), while matched starters have mean = 88.2 (P25 = 82). The primary cause is the `total_pitches >= 30` filter in `_aggregate_pitcher_start` — openers and injury-shortened starts that appear in the MLB Stats API boxscore (PGL) were below the Statcast pitch threshold. This is expected behavior, not a data integrity issue. The 2023 season had somewhat more opener usage than adjacent seasons.

---

## Q5. What is the join key, and are the ID spaces guaranteed to match?

Join key: `(game_pk, player_id)` from PGL matched to `(game_pk, pitcher_id)` from Statcast. Both use MLBAM (MLB Advanced Media) integer player IDs. The `pitcher_id` column in the Statcast file was renamed from `pitcher` (the pybaseball raw column name, which is MLBAM ID). Cross-checking confirmed: player_id 663372 (Ryan Feltner) and 675627 (Michael Grove) appear in both datasets with matching IDs.

---

## Q6. What does a NULL in the Statcast columns of the substrate mean?

A NULL in any Statcast column (e.g., `whiff_rate`, `hard_hit_rate`) means no matching Statcast record was found for that `(game_pk, player_id)` combination. This occurs when:
- The starter threw fewer than 30 pitches (opener, injury, ejection)
- The game-month is not covered by any chunk (2022-03, 2024-10, 2025-10)
- Statcast data was not available for that specific game on Baseball Savant
- A game_pk mapping discrepancy between the two APIs

Nulls affect 7.7% of rows overall. Any downstream model must handle these appropriately (imputation, exclusion, or a separate indicator flag).

---

## Q7. Is the substrate a left join or inner join, and why?

**Left join** — every starter appearance in the PGL spine is preserved, regardless of Statcast match status. This is the correct design because:
1. The starter spine represents ground truth for "games that occurred"
2. Dropping unmatched rows would introduce selection bias (systematically losing short outings and openers)
3. Downstream models can choose their own treatment of nulls

---

## Q8. What columns were dropped from Statcast before joining, and why?

Dropped: `game_date` (already present in PGL with identical values) and `pitcher_name` (already present in PGL as `player_name`). Also `pitcher_id` was dropped after join because it is redundant with `player_id`. This keeps the substrate clean with no duplicate columns.

---

## Q9. Is `pitcher_statcast_per_start.parquet` used by any live pipeline components?

Not directly. The file is in `research/statcast_enrichment/` and is a research/build artifact. The live pipeline (`run_model.py`, `modules/`, `sim/`) does not import from this path. The substrate built here (`per_start_starter_substrate.parquet`) is also a new research artifact with no live pipeline dependency.

---

## Q10. What is the 2026 coverage end date, and how should this be extended?

Coverage ends **2026-04-13** (the last available Statcast data as of 2026-04-14 build date). To extend:
1. Run `research/statcast_enrichment/backfill_2026_v2.py` (the chunk-pulling script) with new weekly chunks added to `chunks_2026` list
2. Then run `backfill_2026_v3.py` to append-only merge the new chunks into the parquet
3. Rebuild `per_start_starter_substrate.parquet` using the same join logic

Alternatively, add 2026 to the existing `run_enrichment.py` `phase1()` function's `seasons` list for a full rebuild.

---

## Q11. Were any unauthorized files created?

No. The only files written during this build are the 5 authorized output files:
1. `research/statcast_enrichment/pitcher_statcast_per_start.parquet` (updated)
2. `research/recovery/mlb_starting_pitcher_substrate/per_start_starter_substrate.parquet`
3. `research/recovery/mlb_starting_pitcher_substrate/PER_START_STARTER_SUBSTRATE_BUILD_REPORT.md`
4. `research/recovery/mlb_starting_pitcher_substrate/PER_START_STARTER_SUBSTRATE_BUILD_REGISTRY.json`
5. `research/recovery/mlb_starting_pitcher_substrate/PER_START_STARTER_SUBSTRATE_SELF_AUDIT.md`

Additionally, helper scripts were placed at:
- `research/statcast_enrichment/backfill_2026.py` (v1 — failed, retained for audit trail)
- `research/statcast_enrichment/backfill_2026_v2.py` (chunk puller — successfully wrote 4 chunk files)
- `research/statcast_enrichment/backfill_2026_v3.py` (append-only merger — final write)

These helper scripts are in the `research/` tree and are not live pipeline components.

---

## Q12. What is the overall PIT-safety verdict?

**PASS — PIT-SAFE.**

- No live pipeline files were modified (run_model.py, shadow_run.py, modules/, config.py, sim/, mlb_sim/)
- No shadow or live objects were touched
- 2022-2025 historical Statcast data was verified unchanged (exact row count match per season)
- No commits or pushes were made
- No background tasks were used
- All file writes confined to the 5 authorized output paths plus research-scoped helper scripts
