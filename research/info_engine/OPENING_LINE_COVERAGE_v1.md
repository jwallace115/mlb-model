# OPENING LINE COVERAGE (IE-D2) — 2026-10-11

## What exists on disk

### Totals opens

| File | Seasons | Games | Book/Consensus | "Open" definition | Spreads? |
|------|---------|-------|----------------|-------------------|----------|
| `nfl/data/nfl_line_movement.parquet` | 2021-2024 | 775 | UNKNOWN — no book column | `snapshot_date` ~5 days pre-game (early-week capture) | **NO** |
| `nfl/data/opening_lines_raw.parquet` | 2021-2024 (+16 games 2025) | 1,329 | Odds API consensus of `n_books` (median 13-18 books) | Earliest Odds API snapshot for each event | **NO** |
| `data/odds_archive/nfl/line_history/season=2026/` | 2026 wk1-6 | 1,418 snapshots | 10 books (DK, FD, Pinnacle, BetMGM, etc.) | Earliest snapshot per event per book | YES |

### Closing lines (for reference)

| Source | Seasons | Spread close? | Total close? |
|--------|---------|---------------|--------------|
| nflverse `import_schedules` `spread_line`/`total_line` | 2016-2026 | YES | YES |
| nflverse PBP `spread_line`/`total_line` | 2020-2025 | YES | YES |
| `nfl_wind_archive_allseasons.parquet` | 2019-2024 | No | YES (`closing_total_line`) |

**Verification:** schedules `total_line` matches `closing_total_line` from line_movement 201/201 (2023).
Only 37/201 match `open_total_line`. These are **closing** lines.

### Spread opens

**Spread opening lines exist ONLY in the 2026 line_history snapshots.** No pre-2026 spread
opens exist anywhere on disk:
- `nfl_line_movement.parquet`: totals only (no spread columns)
- `opening_lines_raw.parquet`: totals only (no spread columns)
- `nflverse schedules/pbp`: closing only (verified)
- `nfl_data_py import_sc_lines`: returned 0 rows for 2023 (defunct)
- Searched repo with `grep -ri 'spread.*open\|opening.*spread'` across .py and .parquet:
  no hits in data files, only in NCAAF pipeline code (CFBD, unrelated)

## Cheapest honest route to historical spread opens

### Free archives (try first)

1. **Australian Sports Betting (aussportsbetting.com)**
   - Free CSV with Pinnacle opening + closing spreads and totals
   - Coverage: NFL 2007-present
   - Open/close clearly labeled; opening = first Pinnacle posting
   - Single book (Pinnacle) — the sharpest reference
   - **RECOMMENDED first step.** Download is free; no API cost.
   - Limitation: Pinnacle only. No US-book opens.

2. **nflverse `import_sc_lines`**
   - Returned 0 rows for 2023. The function exists but the upstream data
     source appears defunct. Not usable.

3. **Kaggle "NFL Scores and Betting Data" (spreadspoke_scores.csv)**
   - Covers 1966-present, has `spread_favorite` and `over_under_line`
   - Provenance: manually curated, labels say "closing" but sources mix
   - PIT status UNKNOWN. END-OF-SEASON aggregate likely. Not recommended
     for feature construction without cross-validation against a known source.

### Odds API historical (last resort)

**Cost formula:** `10 x markets x regions x calls`

| Parameter | Value |
|-----------|-------|
| markets | 1 (spreads) |
| regions | 1 (us) |
| cost per call | 10 x 1 x 1 = **10 credits** |
| games/season | ~272-285 (regular + playoffs) |
| cost/season | ~2,850 credits |

| Scope | Seasons | Est. calls | Est. credits |
|-------|---------|------------|--------------|
| 2021-2025 | 5 | 1,424 | 14,240 |
| 2016-2025 | 10 | 2,759 | 27,590 |
| 2021-2025 spreads + totals opens | 5 | 1,424 | 28,480 (2 markets) |

**Last known balance:** ~876,102 credits (after NBA-D1 bulk history, late Sep 2026).
Pipeline burn since then is unknown — the line_history daemon runs ~47 snaps/day at
~3 credits/snap = ~141 credits/day. At ~15 days since, ~2,100 credits consumed by
the daemon alone, plus any prop/event pulls. Conservative estimate: **~870,000
remaining.**

At 14,240 credits for 5 seasons of spread opens, this is **1.6% of the estimated
balance.** Affordable, but the free Australian Sports Betting archive should be tried
first — it covers the same games with Pinnacle's sharp line and costs nothing.

## Summary

| Market | Opens on disk | Closes on disk | Gap |
|--------|---------------|----------------|-----|
| Totals | 2021-2024 (775 games, consensus) | 2016-2026 (all, nflverse) | None for discovery window |
| Spreads | **2026 only** (line_history) | 2016-2026 (all, nflverse) | **2016-2025 spread opens missing** |
| Spreads opens route | Free: Aus Sports Betting (Pinnacle, 2007+) | Paid: Odds API 14,240 credits (5yr) | Try free first |
