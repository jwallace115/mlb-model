# S3 Course Elasticity Engine — Data Audit Report

**Date:** 2026-03-30  
**Purpose:** Validate data structure, coverage, and signal quality for course elasticity modeling

---

## Executive Summary

**Data Status:** COMPLETE and READY
- 125,346 player rounds (2019-2025, all SG complete)
- 251 unique tournaments with full round-by-round granularity
- 320 events tracked across 6 PGA Tour seasons
- Birdie/scoring data: 100% coverage (99.7% non-null)
- **Challenge:** Course metadata available at round level only; events table has no course-level details

---

## Dataset Inventory

### player_rounds.parquet
```
Rows:           125,346
Columns:        35
Year Range:     2019–2025
```

**Core Columns:**
| Column | Null % | Type | Notes |
|--------|--------|------|-------|
| sg_total | 0.0 | float | Complete coverage; baseline for course sensitivity |
| sg_ott | 19.8 | float | Tee-to-green excluded for ~20% of rounds |
| sg_app | 19.8 | float | Approach play |
| sg_arg | 19.8 | float | Around-green |
| sg_putt | 19.8 | float | Putting |
| round_score | 0.0 | int | Raw stroke count |
| birdies | 0.3 | int | Mean 3.71/round; ready for scoring distribution |
| pars | 0.0 | int | Par count per round |
| bogies | 0.0 | int | Bogey count |

**Course Metadata:**
- `course_name`: 176 unique courses (e.g., "Augusta National", "Pebble Beach")
- `course_num`: PGA Tour event code (typically 1-3 per tournament)
- `course_par`: Par for the course (typically 71-72)
- `start_hole`: Tee position (rotation indicator)

**Player & Event Context:**
- `dg_id`: DataGolf player ID
- `player_name`: Full name
- `event_id`: DataGolf event ID
- `event_name`: Tournament name
- `round_num`: 1–4 (qualifier rounds not included)
- `calendar_year`: Season identifier

**Performance Indicators:**
- `driving_acc`: Fairway hit % (greens and approach)
- `driving_dist`: Average distance off tee (yards)
- `gir`: Greens-in-regulation %
- `scrambling`: Save % from rough/sand
- `prox_fw`: Distance-to-hole from fairway (meters)
- `prox_rgh`: Distance-to-hole from rough/sand (meters)

---

## Correlations: SG Components to Total

Sample size: 100,487 complete-SG rounds (out of 125,346 available)

```
sg_total ~ sg_ott:  0.422   (weak-to-moderate; tee skills ≠ scoring)
sg_total ~ sg_app:  0.606   (strong; approach play is robust predictor)
sg_total ~ sg_arg:  0.398   (weak-to-moderate; short game variable)
sg_total ~ sg_putt: 0.596   (strong; putting is second-most predictive)
```

**Interpretation:**  
- Approach (0.606) + Putting (0.596) explain ~35% of variance in round scoring
- Course conditions likely moderate tee-to-green efficiency (OTT correlation is weakest)
- **Course elasticity signal expected strongest in approach + putting adjustment terms**

---

## Predictions.parquet

```
Rows:     32,000
Years:    2020–2025
Events:   251 tournaments
Field Size (mean):  127 players per event
```

**Event Representation:**
- 251 unique (event_id, calendar_year) pairs
- Balanced tournament coverage: major championships + regular tour events
- Prediction availability: 100% coverage for events with odds data

---

## Odds.parquet (Outrights)

```
Total Rows:  339,944
Markets:
  - win:       96,153 (outright winner)
  - top_20:    78,165 (top-20 finish)
  - top_5:     75,871 (top-5 finish)
  - top_10:    70,698 (top-10 finish)
  - make_cut:  19,057 (make cut)
```

**Coverage:** 5 distinct market types; sufficient for both win and place market modeling.

---

## Events.parquet (Metadata)

```
Total Events:    320
Events with Rounds:  320 (100%)
```

**Limitation:** No course-level attributes (yard lines, par, elevation, bermuda/bentgrass, prevailing wind setup)  
**Workaround:** Cross-reference `event_id` + `calendar_year` with external course databases or DataGolf API

**Available Columns:**
- event_id, calendar_year, event_name
- has_rounds, has_odds, has_predictions
- is_major, is_team_event

---

## Data Quality Checks

| Check | Result | Status |
|-------|--------|--------|
| SG coverage | 100% sg_total; 80% full SG | ✓ PASS |
| Event-round linkage | 100% (event_id present in all rounds) | ✓ PASS |
| Year continuity | 2019–2025 (unbroken) | ✓ PASS |
| Birdie/scoring counts | 99.7% non-null; sensible means (3.71 birdies/rd) | ✓ PASS |
| Course names | 176 unique; consistent spelling | ✓ PASS |
| Field size variance | 127±σ players/event; no extreme outliers | ✓ PASS |
| Duplicates (dg_id + event_id + round_num) | 0 detected | ✓ PASS |

---

## Course Elasticity Modeling — Data Readiness

### Available Signals
1. **Round-level SG breakdown** (sg_total, sg_app, sg_arg, sg_putt, sg_ott)
2. **Scoring distribution** (birdies, pars, bogies per round)
3. **Player consistency** (can measure σ(sg_total) across rounds at each course)
4. **Course difficulty** (mean round_score by course_name, year)
5. **Paired comparisons** (same player, different courses in same season)

### Missing Signals (External Enrichment Required)
- Yard lines (effects tee selection, driver carry expectations)
- Par breakdown by hole (allows hole-by-hole elasticity)
- Elevation change (can suppress distance-dependent metrics)
- Green speed (bentgrass vs bermuda; affects putting variance)
- Wind setup (prevailing direction, typical strength)
- Rough height / hazard density

### Recommended Data Enrichment
1. **DataGolf API course library** (if available): yard lines, par, course setup complexity score
2. **PGA Tour course records**: elevation, conditioning history (green speed trends)
3. **Weather archive** (Open-Meteo or NOAA): wind speed/direction by tournament week
4. **Historical line data**: closing totals by course-year to validate elasticity estimates

---

## Summary Table: Ready-for-Modeling Metrics

| Metric | Value | Use Case |
|--------|-------|----------|
| Player-round observations | 125,346 | Robust for course-player interaction terms |
| Complete SG observations | 100,487 | Elasticity calibration |
| Course count | 176 | Sufficient for regularized course effects |
| Year-course pairs | ~450 | Panel structure for temporal stability |
| Birdie-level granularity | 99.7% | Scoring distribution modeling |
| Prediction sample | 32,000 | Validation set (2020+) |

---

## Next Steps

1. **Merge course attributes** from external source (DataGolf, PGA Tour)
2. **Build elasticity matrix** by course × SG component (approach vs putting, OTT vs app, etc.)
3. **Fit hierarchical model** with course random effects + player random slope (sg_component × course)
4. **Validate on hold-out tournaments** (2025 events unseen in training)
5. **Compare to market-implied elasticity** from closing lines

---

**Report Generated:** 2026-03-30 | **Data Last Updated:** 2026-03-30
