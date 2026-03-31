# MLB Yesterday Rollforward Check — Diagnostic Report

**Date:** 2026-03-27
**Yesterday:** 2026-03-26 (Opening Day — first full slate, 11 games)

---

## ANSWER: It depends on which feature you're asking about.

The MLB simulation pipeline uses a **hybrid architecture** where different features come from different sources with different update cadences. Some include yesterday's results, some don't, and some are frozen at prior-season levels.

---

## Feature-by-Feature Rollforward Status

| Feature | Source | Includes Yesterday? | Update Cadence |
|---------|--------|-------------------|----------------|
| **SP xFIP** | Savant 2025 xERA fallback | **NO** — using prior season stats | Season-level, FanGraphs 403 |
| **SP K%, BB%** | FanGraphs API | **NO** — returning None (403) | Season-level, currently broken |
| **SP avg IP** | FanGraphs API | **NO** — returning None (403) | Season-level, currently broken |
| **SP CSW%** | Per-start CSV + pybaseball | **YES** (if daily refresh ran) | Rolling 5-start |
| **Team wRC+** | FanGraphs API | **NO** — defaulting to 100.0 for all teams | Season-level, currently broken |
| **Bullpen fatigue** | **MLB Stats API (live)** | **YES** — fetches recent boxscores on each call | Rolling 3-day |
| **Weather** | Open-Meteo (live) | N/A — forecast, not rolling | Game-day |
| **Umpire** | Static UMPIRE_RATINGS dict | N/A — career stats | Static |
| **Park factor** | Static config.py | N/A | Static |
| **Wind factor** | Open-Meteo (live) | N/A — forecast | Game-day |

### Summary:
- **Bullpen fatigue**: YES, includes yesterday (live API)
- **SP CSW%**: YES, if daily refresh ran (per-start rolling)
- **SP xFIP/K%/BB%**: NO — using 2025 season-level data (FanGraphs 403)
- **Team offense (wRC+)**: NO — defaulting to league average 100.0 (FanGraphs 403)

---

## Step 1 — Yesterday's Games in Canonical Data

- **11 completed games** on 2026-03-26 with full scores in SQLite DB (mlb_model.db)
- **0 of these** appear in game_table.parquet, feature_table.parquet, or bullpen_usage.parquet
- These parquet files have max date **2025-09-28** and were last modified **2026-03-15**
- They are **training artifacts frozen after Phase 9 model build**, not runtime data stores

## Step 2 — Feature Table Rebuild

The feature_table.parquet is **NOT rebuilt during the season**. It was used only for model training.

At runtime, features are built fresh from **live API calls**:
- FanGraphs (currently returning 403)
- Baseball Savant (2025 data available, 2026 data not yet populated)
- MLB Stats API (live, working)
- Open-Meteo (live, working)

## Step 3 — Spot-Check on 3 Games

| Feature | LAA@HOU | CLE@SEA | ARI@LAD | Evidence |
|---------|---------|---------|---------|----------|
| wRC+ home | 100.0 | 100.0 | 100.0 | DEFAULT — FanGraphs 403, no 2026 data |
| wRC+ away | 100.0 | 100.0 | 100.0 | Same |
| SP K% | None | None | None | FanGraphs 403, Savant doesn't provide |
| SP BB% | None | None | None | Same |
| SP xFIP | Savant 2025 values | Same | Same | Prior-season, not current |
| BP fatigue home | 0.055 | 0.043 | 0.040 | **LIVE** — varies per team, includes yesterday |
| BP fatigue away | 0.031 | 0.044 | 0.044 | **LIVE** |
| Temperature | 78.0 | 47.4 | 64.3 | Live forecast |

**Bullpen fatigue is the ONLY rolling feature that reflects yesterday's games.** All other features are either static, prior-season, or defaulted.

## Step 4 — Pipeline Execution Path

The pipeline ran successfully:
1. Graded yesterday: 11 games written to DB with scores ✓
2. Season stats rebuilt ✓
3. Model ran for today: 8 projections stored ✓
4. V1 signals generated: 4 plays ✓
5. F5 signals generated ✓

**No step failed.** The pipeline executed correctly given its current design. The issue is not a failure — it's a design limitation: the pipeline was built to use season-level pitcher/offense data from FanGraphs, which (a) doesn't update game-by-game and (b) is currently returning 403 errors for 2026.

## Step 5 — Additional Concerns

### FanGraphs 403 is a critical problem
The FanGraphs API is returning 403 Forbidden for all 2026 queries. This means:
- **SP xFIP**: falling back to Savant 2025 xERA (prior season)
- **SP K%/BB%**: returning None (features missing from Ridge model input)
- **Team wRC+**: defaulting to 100.0 for every team (no offensive differentiation)

This effectively removes **3 of the 5 most important model features** (SP quality, lineup quality, bullpen quality — only bullpen works).

### The Phase 9 Ridge model is running with degraded inputs
The model was trained on 25 features with specific distributions. Currently:
- K%, BB% are None → the model receives zeros or NaN substitutions
- wRC+ is 100 for all teams → no offensive differentiation between NYY and OAK
- xFIP is 2025 season-level → doesn't reflect Opening Day starter quality for 2026

---

## Final Verdict

**The answer to "are yesterday's results rolling forward?" is:**

**PARTIALLY — only bullpen fatigue includes yesterday. All other rolling features are either broken (FanGraphs 403), frozen at prior-season levels, or defaulted to league average.**

**Confidence: HIGH** — verified by direct inspection of DB contents, projected feature values, and API response codes.

### Priority Issues (not in scope of this diagnostic, but flagged):
1. **FanGraphs 403**: blocks SP and offense features for 2026 season
2. **wRC+ = 100 for all teams**: eliminates offense differentiation
3. **SP K%/BB% = None**: Ridge model receiving incomplete feature vectors
4. **No game-by-game SP feature refresh**: xFIP/K%/BB% only update when FanGraphs season leaderboards change, not after each start
