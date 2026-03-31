# MLB Two-Pass Daily Workflow — Implementation Report

## Files Modified

| File | Change |
|------|--------|
| `mlb_sim/pipeline/mlb_two_pass.py` | **NEW** — two-pass orchestrator with prelim/confirm modes |
| `~/Library/LaunchAgents/com.mlbmodel.opening_lines.plist` | Updated: 2AM → `mlb_two_pass.py --mode prelim` |
| `~/Library/LaunchAgents/com.mlbmodel.daily.plist` | Updated: 7AM → `mlb_two_pass.py --mode confirm` |

## New Scheduler Configuration

| Time | Job | Script | Mode |
|------|-----|--------|------|
| **2:00 AM** | com.mlbmodel.opening_lines | mlb_two_pass.py | `--mode prelim` |
| **7:00 AM** | com.mlbmodel.daily | mlb_two_pass.py | `--mode confirm` |
| 11:00 AM | refresh.py | (unchanged) | — |
| 12:00 PM | refresh.py | (unchanged) | — |
| 5:00 PM | refresh_5pm.py | (unchanged) | — |
| 11:30 PM | results_tracker.py | (unchanged) | — |

Both plists loaded and verified via `launchctl list`.

## 2AM Preliminary Pass Behavior

1. **Grade yesterday** — attempts to grade all completed games; logs any missing (west coast late finishers)
2. **Invalidate stale caches** — removes today's offense/pitcher caches if they contain < 25 teams
3. **Capture opening lines** — stores OPEN + 2AM snapshots to line_snapshots_2026.json
4. **Refresh feature caches** — calls build_pitcher_db() and build_offense_db() (with 25-team minimum validation)
5. **Preliminary model run** — generates projections and signals using best available data
6. **Push opening lines** — commits line_snapshots_2026.json to GitHub

The 2AM pass is resilient: if any step fails, subsequent steps still execute. West coast games missing from grading are logged but don't block the pipeline.

## 7AM Confirmation Pass Behavior

1. **West coast finalization check** — re-grades yesterday, compares expected vs graded, logs any still-missing games
2. **Cache quality check** — inspects the 2AM-created caches for completeness
3. **Cache invalidation** — if offense cache has < 25 teams, removes it to force re-fetch
4. **Hands off to push_results.py** — runs the standard full pipeline (grade → model → all sports → push)

The 7AM pass is the official run. It benefits from 2AM cache pre-warming but can repair any cache issues independently.

## Cache Safety Rules

### Offense Cache (`offense_v2_YYYY-MM-DD.json`)

| Rule | Implementation |
|------|---------------|
| Minimum teams: 25 | `_save_cache()` refuses to write < 25 teams |
| No downgrade | `_save_cache()` refuses to overwrite N-team cache with < N teams |
| Partial rejection | `build_offense_db()` requires ≥ 25 teams from FanGraphs/Savant before accepting |
| Load validation | `_load_cache()` rejects cached data with < 25 teams |
| Stale invalidation | `invalidate_stale_cache()` renames poisoned cache to `*_invalidated.json` |

### Example Log Outputs

**Rejected partial offense refresh:**
```
[WARNING] Savant 2026: only 2 teams (need 25), trying next
[WARNING] Refusing to cache offense data with only 2 teams (need 25)
```

**Cache overwrite prevention:**
```
[WARNING] Existing cache has 30 teams, new data has 24 — not overwriting
```

**Fallback activation:**
```
[INFO] FanGraphs 2026: 403 Forbidden
[INFO] FanGraphs 2025: 403 Forbidden
[INFO] Savant 2026: only 8 teams (need 25), trying next
[INFO] Savant 2025: loaded 30 teams
[INFO] Cached offense data for 30 teams
```

**Stale cache invalidation:**
```
[INFO] Invalidated offense cache (2 teams < 25): data/cache/offense_v2_2026-03-27.json
```

## Grading Idempotency

Grading uses the existing `grade_yesterday()` function which:
- Writes to SQLite `results` table with `game_pk + game_date` as key
- Skips games already graded (will not re-grade or overwrite)
- Safe to call multiple times (2AM + 7AM + 11:30PM)

Verified: running `grade_yesterday_games()` twice produces the same result (11/11 graded, 0 missing).

## Overlay Logging

Overlay fields (S12, P09, tier, base_stake) are preserved in signal logs via SIGNAL_COLS update from the prior hotfix. This is unaffected by the two-pass change.

## Remaining Risks

1. **FanGraphs 403 persists** — the two-pass system correctly falls back to Savant, but SP K%/BB% remain NULL until FanGraphs recovers or a boxscore-derived alternative is built
2. **Savant 2026 early-season noise** — after the 25-team threshold is met (~10 games into the season), Savant 2026 wRC+ values will be noisy (small sample). The system correctly prefers the stable 2025 values until 2026 has enough data.
3. **11AM/5PM refreshes unchanged** — these still use the same cache-first logic, so they benefit from 2AM cache pre-warming but don't have their own invalidation logic. The 25-team minimum in `_save_cache()` protects against corruption at all times.
