# MPS Historical Snapshot Acquisition Build

> **BUILD ONLY — MPS REMAINS BLOCKED**
> Generated: 2026-04-13 07:53 UTC

## 1. Build Scope
Historical open/close totals snapshot acquisition for MLB Totals Context Engine V1.
This is a **data acquisition build only**. MPS is NOT activated, NOT computed,
and NOT in any path state.

## 2. Source Game Universe
- Source: `context_engine_raw_table.parquet`
- Total games: **9715**
- Seasons: 2022–2025

| Season | N Games |
|--------|---------|
| 2022 | 2430 |
| 2023 | 2430 |
| 2024 | 2427 |
| 2025 | 2428 |

## 3. Frozen Protocol
| Parameter | Rule |
|-----------|------|
| OPEN probe | `game_date 04:01:00 UTC` (= 00:01 ET) |
| CLOSE probe — day games (start < 17:00 local / UTC 14-21) | `commence_time_utc − 60 minutes` |
| CLOSE probe — evening games | `game_date 22:00:00 UTC` (= 18:00 ET) |
| CLOSE fallback | `game_date 22:00:00 UTC`, flagged `CLOSE_RULE_UNRESOLVED` |
| Book selection | FanDuel primary, DraftKings fallback |
| Sleep between calls | 0.4 seconds |
| Checkpoint | Every 100 games |

## 4. Acquisition Results

| Season | N | Open OK | Close OK | Both OK | Both% |
|--------|---|---------|----------|---------|-------|
| 2022 | 2430 | 1979 (81%) | 2427 (100%) | 1979 (81%) | 81% |
| 2023 | 2430 | 2059 (85%) | 2426 (100%) | 2058 (85%) | 85% |
| 2024 | 2427 | 2192 (90%) | 2425 (100%) | 2190 (90%) | 90% |
| 2025 | 2428 | 2355 (97%) | 2428 (100%) | 2355 (97%) | 97% |
| **TOTAL** | **9715** | **8585** (88%) | **9706** (100%) | **8582** (88%) | **88%** |

## 5. Failure / Missingness Analysis

**Open probe quality flags:**
- OK: 8585 (88.4%)
- MISSING: 1130 (11.6%)

**Close probe quality flags:**
- OK: 9706 (99.9%)
- MISSING: 9 (0.1%)

## 6. Final Table Spec
- File: `mps_historical_snapshots_2022_2025.parquet`
- Rows: 9715
- Column groups: IDENTITY (6), OPEN (18), CLOSE (19), PAIR (3)

## 7. Book Selection

| Probe | FanDuel | DraftKings | Missing |
|-------|---------|------------|---------|
| Open  | 8397 (86%) | 188 (2%) | 1130 (12%) |
| Close | 9673 (100%) | 33 (0%) | 9 (0%) |

## 8. Pair Quality

| Pair Flag | Count | % |
|-----------|-------|---|
| SAME_FANDUEL | 8366 | 86.1% |
| INCOMPLETE | 1127 | 11.6% |
| CROSS_BOOK | 215 | 2.2% |
| BOTH_MISSING | 6 | 0.1% |
| SAME_DRAFTKINGS | 1 | 0.0% |

## 9. Timestamp Quality
- OPEN  — median: 0.4 min | P90: 6.0 min
- CLOSE — median: 4.4 min | P90: 5.0 min

## 10. Readiness: SNAPSHOT SUBSTRATE BUILT CLEANLY

## 11. MPS Status

> **MPS remains RESERVED / DATA-BLOCKED.**
> The snapshot substrate has been acquired. MPS computation, path states,
> and activation are NOT part of this build and remain blocked pending
> explicit future authorization.