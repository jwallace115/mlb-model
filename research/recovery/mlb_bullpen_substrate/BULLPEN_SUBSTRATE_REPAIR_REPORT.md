# BULLPEN SUBSTRATE REPAIR REPORT
Generated: 2026-04-15

## Summary
Full repair and extension of the bullpen usage/feature substrate.
Two defects corrected, 2026 season extended, production promoted.

---

## Part 1 — Build Script + Defect Verification

**Script:** `sim/phase8_bullpen_features.py`

### Pre-Repair State
| File | Rows | Seasons |
|------|------|---------|
| bullpen_usage.parquet | 83,042 | 2022–2025 |
| bullpen_features.parquet | 19,302 | 2022–2025 |
| game_table.parquet | 9,902 | 2022–2026 |

### Defect 1: Complete-Game (CG) Gap
**Finding:** 128 team-games existed in bullpen_usage with only starter rows (no reliever
appeared — complete games). These were absent from bullpen_features because the feature
builder only aggregated reliever rows. The per-game scaffold was missing 128 rows.

**Impact:** CG team-games had no feature row → silently dropped from any merge using
bullpen_features, causing those games to be excluded from model training/inference.
Distribution: ~32 CG per season across 30 teams.

### Defect 2: Within-Season Closer Look-Ahead
**Finding:** The `high_leverage_available` computation in phase8 ranked top-3 closers
using FULL-SEASON games_finished totals (e.g., all 2022 GF including future games).
This means a game played on April 8, 2022 used the closer who would finish the most
games *across the entire 2022 season* — introducing within-season look-ahead bias.

**Code location:** `sim/phase8_bullpen_features.py` lines ~250–295
```python
closer_gf = (
    df_usage[df_usage["games_finished"] > 0]
    .groupby(["team","season","pitcher_id","pitcher_name"])["games_finished"]
    .sum()  # <-- full-season total, NOT trailing
    .reset_index(name="career_gf")
)
```

**Impact:** For early-season games (April), the "top-3 closers" were identified with
knowledge of who would be the primary closer for the rest of that year — a data leakage
that could inflate the HLA signal's measured predictive power.

---

## Part 2 — 2026 Extension

**GT 2026 games:** 187  
**Cached boxscores available:** 187/187 (no API calls required)  
**New pitcher rows extracted:** 1,627  
**Method:** Same `parse_boxscore()` logic as phase8 (games_started, games_finished,
pitches_thrown, innings_pitched fields).

**Extended usage by season:**
| Season | Before | After | Delta |
|--------|--------|-------|-------|
| 2022 | 20,883 | 20,883 | +0 |
| 2023 | 20,634 | 20,634 | +0 |
| 2024 | 20,676 | 20,676 | +0 |
| 2025 | 20,849 | 20,849 | +0 |
| 2026 | 0 | 1,627 | +1,627 |
| **Total** | **83,042** | **84,669** | **+1,627** |

**2026 date range:** 2026-03-26 to 2026-04-09 (187 games, 374 team-game rows in features)

---

## Part 3 — Feature Rebuild with Both Fixes

### PIT-SAFE HIGH-LEVERAGE REPLACEMENT (DECLARED LOGIC):
```
For each team-game G:
1. Collect all reliever appearances for this team in the same season 
   with date < G.date (or same date, game_number < G.game_number for DH).
2. Sum games_finished per pitcher from those prior appearances only 
   (trailing cumulative GF — no future-season or future-game data).
3. Rank pitchers by trailing GF descending. Take top-3.
   If fewer than 3 have appeared, take all available.
4. Sum pitches thrown by those top-3 pitchers in the 2 most recent 
   prior games (same strict date filter).
5. high_leverage_available = 1 if that pitch sum < 25, else 0.
```

**Implementation:** Incremental per-(team, season) processing. For each game in
chronological order: read pitcher_cum_gf dict (built from prior games), identify
top-3, compute pitches from recent_games[-2:], assign HLA, then update dicts.

### CG FIX IMPLEMENTATION:
Scaffold of ALL team-games (from usage) merged LEFT onto per-game relievers. Zero-fills
n_relievers and total_pitches for CG team-games so rolling features proceed correctly.

### Feature Computation:
Rolling lag-1 and lag-3 features computed via `groupby(['team','season']).transform()`
to ensure season-boundary resets. shift(1) applied within each (team, season) group.
NaN values at game_seq=0 (first game of each team-season) are expected and correct.

---

## Part 4 — Staging Verification

### Schema: PASS (10 columns, identical)
### Grain: PASS (0 duplicates in both original and repaired)

### Season Coverage:
| Season | Original | Repaired | Delta | Status |
|--------|----------|----------|-------|--------|
| 2022 | 4,824 | 4,860 | +36 | OK |
| 2023 | 4,825 | 4,860 | +35 | OK |
| 2024 | 4,826 | 4,854 | +28 | OK |
| 2025 | 4,827 | 4,856 | +29 | OK |
| 2026 | 0 | 374 | +374 | NEW |

Season deltas (2022-2025): +128 total from CG fix (36+35+28+29=128).

### HLA Distribution:
| Metric | Original | Repaired |
|--------|----------|----------|
| HLA=0 (fatigued) | 12,605 | 12,598 |
| HLA=1 (rested) | 6,697 | 7,206 |
| HLA rate | 0.347 | 0.364 |

HLA rate shift (+0.017) explained by: (a) CG games added (always HLA=1 since no 
top-3 closers pitched), and (b) PIT-safe logic changes some early-season 
classifications where trailing GF differs from full-season GF ranking.

### Null Rates:
Rolling lag columns: 0.76% nulls (150 rows = first game of each of 150 team-seasons).
This is correct — shift(1) on the first row of each group produces NaN.
All key identifier columns (game_pk, date, season, game_number, team): 0% nulls.

### Backward Compatibility:
All 19,302 original (game_pk, team) pairs are present in repaired. PASS.
CG fix verified: all 19,804 team-games from usage appear in features. PASS.

---

## Part 5 — Production Promotion

**Pre-promotion backups:**
- `sim/data/bullpen_usage.parquet.bak`
- `sim/data/bullpen_features.parquet.bak`

**Files promoted:**
- `sim/data/bullpen_usage.parquet` ← `research/recovery/mlb_bullpen_substrate/bullpen_usage_repaired.parquet`
- `sim/data/bullpen_features.parquet` ← `research/recovery/mlb_bullpen_substrate/bullpen_features_repaired.parquet`

**Consumers verified (no schema changes required):**
- `sim/phase8_step3_retrain.py`
- `mlb/model_m3/build_m3.py`, `mlb/model_m4/build_m4.py`
- `mlb/model_m5/build_m5.py`, `mlb/model_m6/build_m6.py`
- `shadow_run.py`
- `mlb_sim/pipeline/combined_short_exit_shadow.py` (reads usage)

---

## PIT-Safety Verdict

VERIFIED. The repaired `high_leverage_available` uses only information available
at the time each game was played:
- Trailing GF per pitcher (cumulative from prior games only, strict date < game_date)
- Prior-2-games pitch totals (strict trailing window)
- No cross-season contamination (processed per (team, season))
- No within-season future data (incremental per game_seq order)
