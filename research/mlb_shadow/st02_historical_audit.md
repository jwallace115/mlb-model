# ST02 Historical Audit

**Date:** 2026-03-27
**Signal:** ST02 — road_trip_game_6plus (UNDER direction)
**Definition:** Away team on 6th or later consecutive road game
**Status:** SHADOW (not active for wagering)

---

## Dataset Coverage

| Season | Total Games | With Closing Total | ST02 Games (non-push) |
|:-------|---:|---:|---:|
| 2022 | 2,430 | 1,908 (78.5%) | 544 |
| 2023 | 2,430 | 2,003 (82.4%) | 511 |
| 2024 | 2,427 | 2,427 (100%) | 566 |
| 2025 | 2,428 | 2,428 (100%) | 551 |
| **Total** | **9,715** | **8,766 (90.2%)** | **2,172** |

Closing line sources: MLB historical closing lines (2022-2023), bet_results DraftKings/FanDuel (2024-2025).

---

## Signal Definition

```
ST02 = 1 if road_trip_game_num_away >= 6
```

Road trip game number = count of consecutive away games for the away team within the same season. Resets to 0 at season boundaries and after any home game.

**Hypothesis:** Away team fatigue on extended road trips causes late-game run suppression, biasing outcomes UNDER.

---

## Overall Results (2022-2025)

| Segment | N (non-push) | Under Rate | ROI at -110 | Mean Market Error |
|:--------|---:|---:|---:|---:|
| **ST02** | **2,172** | **52.21%** | **-0.3%** | +0.279 |
| Baseline | 6,239 | 50.38% | -3.8% | +0.508 |
| **Lift** | — | **+1.83pp** | **+3.5pp** | -0.229 |

**Statistical significance:**
- T-test (market error): t = -2.156, **p = 0.031**
- OLS with controls (closing_total, park_factor, temperature): coefficient = -0.235, t = -2.209, **p = 0.027**

The effect is statistically significant (p < 0.05) and survives controls.

---

## Season-by-Season Results

| Season | N | Under Rate | ROI | Baseline Under | Lift |
|:-------|---:|---:|---:|---:|---:|
| 2022 | 544 | 49.08% | -6.3% | 52.26% | **-3.2pp** |
| 2023 | 511 | 53.23% | +1.6% | 49.15% | **+4.1pp** |
| 2024 | 566 | 51.41% | -1.8% | 49.72% | **+1.7pp** |
| 2025 | 551 | 55.17% | +5.3% | 50.65% | **+4.5pp** |

**2022 is the outlier.** ST02 was *anti-directional* in 2022 (-3.2pp lift). The signal has been consistently positive in 2023-2025 (+1.7pp to +4.5pp lift).

### Excluding 2022 (3 seasons: 2023-2025)

| Metric | Value |
|:-------|:------|
| N | 1,628 |
| Under rate | **53.26%** |
| ROI at -110 | **+1.7%** |

---

## Road Trip Game-by-Game Breakdown

| Game # | N | Under Rate | ROI |
|---:|---:|---:|---:|
| 1 | 1,194 | 47.49% | -9.3% |
| 2 | 1,451 | 50.59% | -3.4% |
| 3 | 1,361 | 51.21% | -2.2% |
| 4 | 1,083 | 52.26% | -0.2% |
| 5 | 1,150 | 50.35% | -3.9% |
| **6** | **1,110** | **52.25%** | **-0.2%** |
| 7 | 479 | 52.19% | -0.4% |
| 8 | 248 | 51.21% | -2.2% |
| **9** | **224** | **53.57%** | **+2.3%** |
| 10 | 97 | 50.52% | -3.6% |

**Observations:**
- The effect is NOT monotonic. Game 7 and 8 show no signal despite longer trips.
- Game 6 is the most common (N=1,110) but barely above break-even.
- Game 9 shows the strongest single-game signal (53.6%, N=224).
- The prior deep analysis flagged the game-7 "hole" as a yellow flag — this remains in the full 4-season data.

---

## Interaction with P09 (2024-2025 only)

P09 = combined opponent-adjusted hard-hit suppression (both pitchers suppressing > league average).

| Segment | N | Under Rate | ROI |
|:--------|---:|---:|---:|
| Neither | 2,011 | 49.43% | -5.6% |
| **ST02 only** | **685** | **54.45%** | **+4.0%** |
| P09 only | 1,502 | 51.00% | -2.6% |
| ST02 + P09 | 468 | 51.92% | -0.9% |

**Key finding confirmed:** ST02 performs best *without* P09 overlap. When both signals fire, the under rate drops from 54.5% to 51.9%. The signals appear to interfere rather than stack.

**Recommendation:** If deployed, ST02 should be standalone — NOT stacked with P09/hard-hit-based UNDER overlays.

---

## Promotion Gate Evaluation

**Gate criteria:** under_rate >= 53% AND N >= 150

### Full dataset (2022-2025)

| Metric | Value | Gate |
|:-------|:------|:-----|
| N | 2,172 | **PASS** (>= 150) |
| Under rate | 52.21% | **FAIL** (< 53%) |

**Result: FAIL.** The 4-season pooled under rate is 0.79pp below the 53% threshold, dragged down by 2022.

### Excluding 2022 (2023-2025)

| Metric | Value | Gate |
|:-------|:------|:-----|
| N | 1,628 | **PASS** |
| Under rate | 53.26% | **PASS** |

**Result: PASS** — but only if 2022 is excluded.

### Recent 2 seasons (2024-2025)

| Metric | Value | Gate |
|:-------|:------|:-----|
| N | 1,117 | **PASS** |
| Under rate | 53.27% | **PASS** |

### 2025 only

| Metric | Value | Gate |
|:-------|:------|:-----|
| N | 551 | **PASS** |
| Under rate | 55.17% | **PASS** |

---

## Summary Table

| Test | Result |
|:-----|:-------|
| Statistical significance (OLS) | **p = 0.027** — significant |
| 4-season pooled under rate | 52.21% — below 53% gate |
| 3-season pooled (2023-2025) | 53.26% — passes 53% gate |
| Season stability | **3 of 4 seasons positive** (2022 was anti-directional) |
| ROI (4 seasons) | -0.3% — not profitable pooled |
| ROI (2023-2025) | +1.7% — marginally profitable |
| P09 interaction | **Negative** — signals interfere, do not stack |
| Monotonicity | **Non-monotonic** — game 7-8 show no effect |
| Market pricing | **Unpriced** — market sets higher totals for ST02 games |
| Mechanism | Road fatigue (same-region), not timezone/jet lag |

---

## Final Verdict

### B) Evidence inconclusive — remain SHADOW

**Rationale:**

1. **The 4-season pooled under rate (52.21%) fails the 53% promotion gate.** This is the binding constraint. The signal is real (p=0.027) but the edge is not large enough for profitable deployment after vig.

2. **The 2022 outlier raises a stability concern.** 2022 was anti-directional (-3.2pp). Excluding it produces a passing signal (53.26%), but cherry-picking which seasons to include undermines the backtest discipline.

3. **The non-monotonic game-by-game pattern is unresolved.** If road fatigue is the true mechanism, the effect should strengthen with longer trips. It doesn't — game 7-8 show no signal. This suggests the mechanism may not be pure fatigue.

4. **P09 interference limits deployment options.** If deployed, ST02 cannot stack with the primary UNDER overlay signals, restricting its use to "ST02 only" situations (N≈685/season in 2024-2025).

5. **2025 is the strongest single season (+5.3% ROI, 55.2% under rate).** If the 2026 shadow data confirms this level, the signal becomes promotable. If 2026 regresses toward the 4-season mean (~52%), it confirms the signal is too weak.

**Recommended action:** Continue 2026 shadow collection. Re-evaluate after 150+ graded ST02 games in 2026 (approximately early June). If 2026 under_rate >= 53%, promote. If < 51%, archive.
