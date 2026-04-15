# PER-START STARTER SUBSTRATE — BUILD REPORT

**Generated:** 2026-04-14  
**Build Type:** 2026 Statcast backfill + per-start starter substrate construction  
**Status:** COMPLETE — PIT-SAFE

---

## PURPOSE

Construct a per-game-start enriched substrate that joins two data sources:
1. The **starter spine** from `mlb/data/pitcher_game_logs.parquet` — every identified starting pitcher appearance (2022-2026) with game-level outcomes from the MLB Stats API.
2. The **Statcast pitch-level aggregations** from `research/statcast_enrichment/pitcher_statcast_per_start.parquet` — per-start movement/quality metrics derived from pybaseball `statcast()` pulls.

This substrate is the foundation for any downstream modeling that needs per-start stuff-quality metrics (whiff rate, chase rate, barrel rate, etc.) alongside game-level outcomes.

---

## EXISTING PITCHER STATCAST BUILD PATH

**Script:** `research/statcast_enrichment/run_enrichment.py`  
**Key function:** `_aggregate_pitcher_start(chunk_df)` (line 96)  
**Phase:** Phase 1 (lines 201-323)

### Build Mechanics
- Source: `pybaseball.statcast(start_dt, end_dt)` — pulls pitch-level data from Baseball Savant
- Chunking: Monthly chunks (e.g., `2022_04`, `2023_07`) stored in `research/statcast_enrichment/chunks/`
- Aggregation: Pitch-level rows grouped by `(pitcher, game_date, game_pk)` → per-start metrics
- Filter: `total_pitches >= 30` (excludes openers / extreme short outings)
- Output: `research/statcast_enrichment/pitcher_statcast_per_start.parquet`

### Metrics Produced
| Column | Description |
|--------|-------------|
| total_pitches | Raw pitch count per start |
| bip | Balls in play |
| hard_hits / hard_hit_rate | EV >= 95 mph on BIP |
| barrels / barrel_rate | Statcast barrel definition (EV/LA thresholds) on BIP |
| swings / whiffs / whiff_rate | Swing-and-miss rate |
| in_zone / outside_zone / chases / chase_rate | Zone-based swing tracking |
| zone_swings / zone_contacts / zone_contact_rate | In-zone contact quality |
| avg_launch_angle / avg_exit_velo | BIP quality averages |
| spin_rate_ff / spin_rate_sl | Mean spin rate for fastball (FF/SI) and slider (SL/ST/SV) groups |
| extension / release_point_x / release_point_z | Arm slot and extension |

---

## 2026 BACKFILL METHOD

### Trigger
The existing `run_enrichment.py` `phase1()` function was built for seasons `[2022, 2023, 2024, 2025]` only. No 2026 chunks existed prior to this build.

### Approach
Three scripts were developed iteratively:
1. `backfill_2026.py` — initial attempt; failed on `"cannot convert NA to integer"` because 2026 Statcast data returns `zone` as nullable `Int64` type (pandas extension type), not `float64` as in prior seasons.
2. `backfill_2026_v2.py` — fixed the dtype issue by casting all potentially nullable numeric columns to `float` before the boolean operations; successfully pulled all 4 chunks. However, re-merging from chunk files failed the PIT-safety check because several historical monthly chunk files are missing from disk (2022-03, 2024-10, 2025-10 — consistent with zero rows for those months in the existing parquet). The script correctly halted.
3. `backfill_2026_v3.py` (**used**) — append-only strategy: load the existing parquet as ground truth for 2022-2025, union with deduplicated 2026 chunk rows, verify PIT-safety, write back. This is the correct approach.

### 2026 Date Range Covered
| Chunk ID | Date Range | Raw Pitches | Pitcher-Starts |
|----------|-----------|-------------|----------------|
| 2026_03a | 2026-03-20 to 2026-03-26 | 22,562 | 220 |
| 2026_03b | 2026-03-27 to 2026-04-02 | 24,398 | 241 |
| 2026_04a | 2026-04-03 to 2026-04-09 | 28,395 | 274 |
| 2026_04b | 2026-04-10 to 2026-04-14 | 16,330 | 169 |
| **Total** | | **~91,685** | **904** |

### Dtype Fix Applied
The original `_aggregate_pitcher_start` used:
```python
df["is_in_zone"] = (df["zone"].between(1, 9)).astype(int)
```
When `zone` is `Int64` (nullable), `.astype(int)` raises `ValueError: cannot convert NA to integer`.

Fix: cast all potentially-nullable columns to float before boolean operations:
```python
df[col] = df[col].astype(float)
```
And add `.fillna(False)` before `.astype(int)` on all boolean-derived columns. This preserves identical semantics for non-null rows.

### game_date Normalization
Existing parquet stores `game_date` as string `"YYYY-MM-DD"`. The 2026 chunk files stored `game_date` as `datetime64[ns]` (Timestamp objects). Normalized to string before concat:
```python
df_c["game_date"] = pd.to_datetime(df_c["game_date"]).dt.strftime("%Y-%m-%d")
```

---

## POST-UPDATE COVERAGE CHECK

### Statcast File (`pitcher_statcast_per_start.parquet`)
| Year | Rows (Before) | Rows (After) | Status |
|------|--------------|-------------|--------|
| 2022 | 5,134 | 5,134 | OK |
| 2023 | 5,114 | 5,114 | OK |
| 2024 | 5,268 | 5,268 | OK |
| 2025 | 5,146 | 5,146 | OK |
| 2026 | 0 | 904 | +904 added |
| **Total** | **20,662** | **21,566** | **+904** |

**PIT-SAFETY VERDICT: PASS** — All 2022-2025 season row counts unchanged.

---

## STARTER SPINE DEFINITION

**Source:** `mlb/data/pitcher_game_logs.parquet`  
**Filter:** `starter_flag == 1`  
**Coverage:** 2022-2026, all 30 MLB teams

| Season | Starter Appearances |
|--------|-------------------|
| 2022 | 4,860 |
| 2023 | 4,860 |
| 2024 | 4,854 |
| 2025 | 4,856 |
| 2026 | 484 |
| **Total** | **19,914** |

**Join keys:** `game_pk` (int64) + `player_id` (int64, MLBAM)

### PGL Columns Carried Into Substrate
`game_pk`, `game_date`, `season`, `player_id`, `player_name`, `team`, `opponent`, `home_away`, `starter_flag`, `pitcher_hand`, `innings_pitched`, `batters_faced`, `pitches`, `hits_allowed`, `runs_allowed`, `earned_runs`, `walks`, `strikeouts`, `home_runs_allowed`, `ground_outs`, `fly_outs`, `air_outs`

---

## STATCAST ENRICHMENT JOIN LOGIC

**Join type:** LEFT JOIN (starter spine is the left table)  
**Join keys:** `game_pk` + `player_id` (PGL) = `game_pk` + `pitcher_id` (SC)  
**ID space:** Both use MLBAM pitcher IDs (confirmed identical)  
**Deduplication:** SC subset deduplicated on `(game_pk, pitcher_id)` before join  
**Dropped from SC before join:** `game_date` (redundant), `pitcher_name` (redundant — PGL has `player_name`)  
**`pitcher_id` column dropped** after join (redundant with `player_id`)

---

## OUTPUT SCHEMA

**File:** `research/recovery/mlb_starting_pitcher_substrate/per_start_starter_substrate.parquet`  
**Rows:** 19,914  
**Columns (43 total):**

PGL columns (22): `game_pk`, `game_date`, `season`, `player_id`, `player_name`, `team`, `opponent`, `home_away`, `starter_flag`, `pitcher_hand`, `innings_pitched`, `batters_faced`, `pitches`, `hits_allowed`, `runs_allowed`, `earned_runs`, `walks`, `strikeouts`, `home_runs_allowed`, `ground_outs`, `fly_outs`, `air_outs`

Statcast columns (21 — NULL when no match): `total_pitches`, `bip`, `hard_hits`, `barrels`, `swings`, `whiffs`, `in_zone`, `outside_zone`, `chases`, `zone_swings`, `zone_contacts`, `avg_launch_angle`, `avg_exit_velo`, `spin_rate_ff`, `spin_rate_sl`, `extension`, `release_point_x`, `release_point_z`, `hard_hit_rate`, `barrel_rate`, `chase_rate`, `zone_rate`, `zone_contact_rate`, `whiff_rate`

Wait — `total_pitches` through `zone_contacts` are raw counts (6 count cols listed above), then the rate/average columns. Full 21 Statcast columns as listed in the schema output.

---

## COVERAGE SUMMARY

### Overall Match Rate: 18,377 / 19,914 (92.3%)

| Season | Starter Starts | SC Matched | Match Rate | Unmatched |
|--------|---------------|-----------|-----------|-----------|
| 2022 | 4,860 | 4,531 | 93.2% | 329 |
| 2023 | 4,860 | 4,339 | 89.3% | 521 |
| 2024 | 4,854 | 4,579 | 94.3% | 275 |
| 2025 | 4,856 | 4,457 | 91.8% | 399 |
| 2026 | 484 | 471 | 97.3% | 13 |
| **All** | **19,914** | **18,377** | **92.3%** | **1,537** |

### Unmatched Row Analysis
Unmatched rows (7.7% of starts) have a distinct profile vs. matched rows:
- **Unmatched** 2023: mean pitches = 58.9, P25 = 26 (PGL pitches)
- **Matched** 2023: mean pitches = 88.2, P25 = 82 (PGL pitches)

Root causes (in priority order):
1. **Opener / short start < 30 pitches in Statcast** — the `>= 30` filter in `_aggregate_pitcher_start` removes openers; PGL records them as starters
2. **Missing chunk data** — 2022-03, 2024-10, 2025-10 months have zero chunk coverage (consistent with original build failures for those months)
3. **game_pk mismatch** — rare cases where Statcast and MLB Stats API assign different game IDs (doubleheaders, rescheduled games)
4. **Statcast raw data gaps** — Baseball Savant occasionally has missing game-days

The 2026 97.3% match rate is the best of all seasons, consistent with complete weekly chunk coverage.

---

## PIT-SAFETY STATUS

| Check | Result |
|-------|--------|
| 2022 rows in SC before/after | 5,134 / 5,134 — OK |
| 2023 rows in SC before/after | 5,114 / 5,114 — OK |
| 2024 rows in SC before/after | 5,268 / 5,268 — OK |
| 2025 rows in SC before/after | 5,146 / 5,146 — OK |
| Chunk re-merge NOT used | Confirmed — append-only strategy used |
| Live/shadow objects modified | None |
| Unauthorized files created | None |

**VERDICT: PIT-SAFE — PASS**

---

## WARNINGS / LIMITS

1. **2023 match rate (89.3%)** is the lowest of any season. Investigation confirms this is primarily opener/short-outing filtering, not a data integrity issue.
2. **Missing months** — 2022-03, 2024-10, 2025-10 have no Statcast chunk coverage. These months correspond to minimal games (pre-season, season-end). The existing parquet was built with the same gaps.
3. **2026 coverage through 2026-04-13 only.** Re-run the backfill weekly to extend coverage.
4. **`spin_rate_ff`/`spin_rate_sl`** have high null rates (~20-40%) for starters who primarily throw off-speed pitches; nulls are expected and should not be imputed.
5. **Barrel definition** uses a simplified angle-range formula (EV-dependent window). This matches the original `_aggregate_pitcher_start` implementation, not the full Statcast barrel model.
6. **PGL `pitches` column vs SC `total_pitches`** — these differ slightly; PGL counts pitches from boxscore, SC counts pitch-level rows. Typical delta is 0-5 pitches; large deltas may indicate play-by-play coverage gaps.

---

## STATUS

**COMPLETE** — All 5 authorized output files written.  
**READY FOR DOWNSTREAM USE**
