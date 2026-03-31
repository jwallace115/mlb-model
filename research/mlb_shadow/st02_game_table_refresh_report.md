# ST02 Game Table Refresh Report

**Date:** 2026-03-27
**Purpose:** Enable 2026 shadow data collection for ST02 (road_trip_game_6plus)

---

## What Was Done

### 1. Script Used

`sim/phase1_build_game_table.py` — the existing Phase 1 game table builder.

### 2. Config Changes (2 lines in `sim/phase1_build_game_table.py`)

- Added `2026: ("2026-03-26", "2026-09-27")` to `SEASON_WINDOWS` (line 74)
- Added `2026: 2430` to `EXPECTED_GAME_COUNTS` (line 84)

### 3. Rebuild Command

```bash
python sim/phase1_build_game_table.py --seasons 2022 2023 2024 2025 2026
```

### 4. Bug Fix in `mlb_sim/pipeline/shadow_signals.py`

Fixed road-trip streak calculation to reset at season boundaries. Without this fix, a team ending 2025 on the road would incorrectly show road_trip_game=7+ on Opening Day 2026.

---

## Results

### Rows Added

| Season | Games | Status |
|:-------|------:|:-------|
| 2022 | 2,430 | Unchanged |
| 2023 | 2,430 | Unchanged |
| 2024 | 2,427 | Unchanged |
| 2025 | 2,428 | Unchanged |
| **2026** | **11** | **New** |
| **Total** | **9,726** | Was 9,715 |

The 11 games are from 2026-03-26 (Opening Day) — the only completed 2026 games at time of refresh. Future runs of the phase1 script will pick up additional completed games as the season progresses.

### 2026 Date Coverage

| Field | Value |
|:------|:------|
| Earliest 2026 game | 2026-03-26 |
| Latest 2026 game | 2026-03-26 |
| Games included | 11 (all Opening Day) |
| Games skipped | 2,418 (not yet played) |

The script only includes games with status "Final", "Game Over", or "Completed Early" — future games are automatically excluded.

### ST02 Verification

All 11 completed 2026 games now produce non-null ST02 values:

| Date | Away @ Home | Road Trip Game | Favorable Zone |
|:-----|:------------|---:|:---:|
| 2026-03-26 | PIT @ NYM | 1 | No |
| 2026-03-26 | CHW @ MIL | 1 | No |
| 2026-03-26 | WSN @ CHC | 1 | No |
| 2026-03-26 | MIN @ BAL | 1 | No |
| 2026-03-26 | BOS @ CIN | 1 | No |
| 2026-03-26 | LAA @ HOU | 1 | No |
| 2026-03-26 | DET @ SDP | 1 | No |
| 2026-03-26 | TBR @ STL | 1 | No |
| 2026-03-26 | TEX @ PHI | 1 | No |
| 2026-03-26 | ARI @ LAD | 1 | No |
| 2026-03-26 | CLE @ SEA | 1 | No |

All show road_trip_game=1 (first away game of the new season) — correct. Favorable zone (>=6) will trigger naturally once road trips develop during the regular season.

---

## What Was NOT Changed

- ST02 remains in SHADOW status — not promoted to live
- No thresholds, live picks, or overlays were modified
- No other signal logic was changed
- The shadow_signals.py module continues to be observation-only

---

## Ongoing Maintenance

To keep 2026 coverage current, re-run periodically:

```bash
python sim/phase1_build_game_table.py --seasons 2022 2023 2024 2025 2026
```

This will pick up any new completed 2026 games. Weather data is cached per-game, so re-runs are fast for previously processed games.
