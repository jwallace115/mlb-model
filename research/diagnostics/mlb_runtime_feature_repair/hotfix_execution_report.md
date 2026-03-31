# Hotfix Execution Report — 2026-03-27

## 1. Poisoned Cache Backup

Backed up to: `data/cache/offense_v2_2026-03-27_poisoned_backup.json`
Contents: 2 teams (NYY, SFG) — caused by early manual run accepting partial Savant 2026 data.

## 2. Restored Offense Cache

Restored from: `data/cache/offense_v2_2026-03-26.json` (yesterday's 30-team 2025 Savant data)
Team count in restored cache: **30 teams**

## 3. Cache Validation Fix

**File modified:** `modules/offense.py`

Changes:
- Added `_MIN_TEAMS = 25` constant
- `_load_cache()`: rejects cached data with fewer than 25 teams (logs warning, returns empty)
- `_save_cache()`: refuses to write cache with < 25 teams; refuses to overwrite larger cache with smaller one
- `build_offense_db()`: FanGraphs and Savant results now checked for `len(result) >= _MIN_TEAMS` before acceptance; partial results log team count and fall through to prior year

This prevents future cache poisoning from partial early-season data.

## 4. Overlay Signal Logging Fix

**File modified:** `mlb_sim/pipeline/daily_signal_generator.py`

Added to `SIGNAL_COLS`:
- `s12_overlay_active`
- `s12_value`
- `p09_overlay_active`
- `p09_value`
- `p09_data_available`
- `combined_overlay_tier`
- `base_stake`

These fields are now preserved in both parquet and JSON signal logs.

**Verified:** Today's regenerated signals show:
- KCR@ATL: s12=1, s12_value=14.93, p09=0, tier=S12_ONLY, base_stake=0.5 → final=0.625
- ARI@LAD: s12=1, s12_value=9.29, p09=0, tier=S12_ONLY, base_stake=1.0 → final=1.25

## 5. Before / After Signal Comparison

| Game | Proj Before | Proj After | Delta | wRC Home | wRC Away | Play | Stake | Overlay |
|------|-----------|-----------|-------|----------|----------|------|-------|---------|
| **ARI@LAD** | 7.95 | **8.21** | +0.26 | 105.1 | 101.4 | YES | 1.25u | S12_ONLY |
| **KCR@ATL** | 7.93 | **7.98** | +0.05 | 101.1 | 99.5 | YES | 0.625u | S12_ONLY |
| CLE@SEA | 7.69 | 7.48 | -0.21 | 102.6 | 91.7 | no | - | - |
| COL@MIA | 9.32 | 8.90 | -0.42 | 100.0 | 91.1 | no | - | - |
| DET@SDP | 7.96 | 8.05 | +0.09 | 101.6 | 100.8 | no | - | - |
| LAA@HOU | 9.11 | 8.93 | -0.18 | 98.7 | 96.7 | no | - | - |
| NYY@SFG | 8.29 | 8.75 | +0.46 | 98.9 | 108.2 | no | - | - |
| OAK@TOR | 8.24 | 8.30 | +0.06 | 103.4 | 98.0 | no | - | - |

### Key changes:
- **NYY@SFG** moved +0.46 runs (NYY wRC+ 108.2 vs generic 100.0 before — strong offense now reflected)
- **COL@MIA** moved -0.42 runs (COL wRC+ 91.1 and MIA 100.0 — weaker offenses now reflected)
- **CLE@SEA** moved -0.21 runs (CLE wRC+ 91.7 — weaker offense now reflected)
- Play games (KCR@ATL, ARI@LAD) moved minimally (+0.05, +0.26) — both teams near league average

### Play validity:
- **KCR@ATL**: projection barely changed (+0.05). Signal remains valid. S12 overlay active.
- **ARI@LAD**: projection increased +0.26 (LAD offense 105.1 now priced). Line is 8.5, model projects 8.21 → still UNDER but edge narrowed from ~0.55 to ~0.29. Signal remains but is weaker. S12 overlay active — the 1.25u sizing reflects the S12 boost (base was 1.0u).

## 6. Recommendation

| Play | Status | Note |
|------|--------|------|
| KCR@ATL 0.625u UNDER | **VALID** — minimal projection change | S12 overlay confirmed active |
| ARI@LAD 1.25u UNDER | **VALID but edge reduced** — projection moved toward the line | Edge narrowed from ~0.55 to ~0.29 after offense correction. Still within signal threshold but confidence is lower. |

Both plays remain within V1 signal thresholds. The S12 overlay is confirmed running correctly (both games have S12 active). No change to play decisions or sizing required.

## Files Modified
- `modules/offense.py` — cache validation logic
- `mlb_sim/pipeline/daily_signal_generator.py` — SIGNAL_COLS overlay fields
- `data/cache/offense_v2_2026-03-27.json` — restored from yesterday's 30-team cache
- `mlb_sim/logs/signals_2026.parquet` — regenerated with overlay fields
- `mlb_sim/logs/signals_2026.json` — regenerated with overlay fields
- `results.json` — rebuilt with corrected projections

## Git Push
Commit `4003944` pushed to main.
