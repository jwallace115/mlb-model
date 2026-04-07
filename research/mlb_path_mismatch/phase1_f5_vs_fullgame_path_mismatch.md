# F5 vs Full-Game Path Mismatch Research

**Date:** 2026-04-07
**Objective:** Test whether inconsistent path assumptions between F5 and full-game totals markets create exploitable signal.

---

## Phase 1: Data Audit / Join Feasibility

### Data Sources

| Source | File | Records | Date Range | Key Fields |
|--------|------|---------|------------|------------|
| F5 historical lines | `research/team_totals/data/f5_lines_historical.parquet` | 5,871 games | 2023-05-03 to 2025-09-28 | game_id, f5_line |
| Full-game closing lines | `sim/data/market_snapshots.parquet` | 4,855 games | 2024-03-20 to 2025-09-28 | game_id, close_total |
| Game actuals | `sim/data/game_table.parquet` | 9,857 games | 2022-04-07 to 2026-04-06 | game_pk, actual_total, actual_f5_total |
| F5 2026 lines | `mlb_sim_f5/data/f5_lines_2026.parquet` | 119 games | 2026-03-25 to 2026-04-07 | game_id, f5_total |
| F5 signals 2026 | `mlb_sim/logs/f5_signals_2026.json` | 52 entries | 2026 only | f5_line, actual_f5_total |
| FG signals 2026 | `mlb_sim/logs/signals_2026.json` | 53 entries | 2026 only | line_at_signal_time |

### Join Result

- **Join key:** game_id (= game_pk from MLB Stats API)
- F5 + full-game closing line: **4,215 games**
- After adding actuals + filtering to 9+ innings + non-null: **3,880 games**
- Season 2024: 1,881 games
- Season 2025: 1,999 games
- 2026 signal overlap (F5 + FG): 48 games (too small for standalone analysis)

**No historical F5 lines before May 2023.** No open-to-close line movement data available (market_snapshots has no open_total populated).

---

## Phase 2: Path-Mismatch Feature Construction

### Feature Definitions

```
late_implied = full_game_line - f5_line
early_per_inning = f5_line / 5
late_per_inning = late_implied / 4
late_ratio = late_per_inning / early_per_inning
```

### late_ratio Distribution

| Statistic | Value |
|-----------|-------|
| Mean | 1.095 |
| Std | 0.184 |
| P5 | 0.833 |
| P25 | 0.972 |
| P50 (median) | 1.111 |
| P75 | 1.250 |
| P95 | 1.429 |

The median is above 1.0, meaning the market generally expects late innings to produce slightly more runs per inning than early innings (reflecting bullpen vs starter quality).

### Bucket Assignment

| Bucket | Criterion | N | Mean F5 Line | Mean FG Line | Mean late_ratio |
|--------|-----------|---|-------------|-------------|-----------------|
| HIGH_EARLY_INFLATION | late_ratio <= 0.972 | 1,447 | 4.74 | 8.17 | 0.906 |
| NORMAL | 0.972 < late_ratio < 1.250 | 1,295 | 4.56 | 8.59 | 1.105 |
| HIGH_LATE_INFLATION | late_ratio >= 1.250 | 1,138 | 4.07 | 8.35 | 1.323 |

HIGH_EARLY_INFLATION games have higher F5 lines relative to their FG total (market expects scoring frontloaded). HIGH_LATE_INFLATION games have lower F5 lines relative to FG total (market expects scoring backloaded).

---

## Phase 3: Raw Outcome Test

### By Mismatch Bucket

| Metric | HIGH_EARLY_INFLATION | NORMAL | HIGH_LATE_INFLATION |
|--------|---------------------|--------|---------------------|
| N | 1,447 | 1,295 | 1,138 |
| Mean actual F5 | 4.97 | 4.99 | 4.85 |
| Mean actual FG | 8.81 | 8.96 | 8.73 |
| Mean actual late runs | 3.84 | 3.97 | 3.89 |
| Implied late/inning | 0.857 | 1.008 | 1.071 |
| Actual late/inning | 0.959 | 0.993 | 0.972 |
| **Late error (actual - implied)** | **+0.407** | **-0.059** | **-0.395** |
| F5 error (actual - line) | +0.233 | +0.427 | +0.778 |
| FG error (actual - line) | +0.641 | +0.368 | +0.383 |
| F5 over rate | 0.463 | 0.497 | 0.534 |
| FG over rate | 0.494 | 0.501 | 0.487 |

### Primary Finding

**The market systematically misprices the F5-to-late-inning split:**

- **HIGH_LATE_INFLATION:** Market implies late scoring of 1.071 runs/inning, actual is 0.972. The market overestimates late scoring by 0.40 runs. Meanwhile, actual F5 runs 0.78 runs above the F5 line (F5 over rate: 53.4%).
- **HIGH_EARLY_INFLATION:** Market implies late scoring of 0.857 runs/inning, actual is 0.959. The market underestimates late scoring by 0.41 runs. F5 actual runs only 0.23 above line (F5 under rate: 53.7%).

The actual scoring pace across innings is much more uniform than the market implies. Games bucketed as "late-heavy" don't actually produce more late runs; they produce more F5 runs than the F5 line expects.

---

## Phase 4: Signal Interaction Test

### Full-Game UNDER Signals by Bucket (N=821)

| Bucket | N | Win Rate | Avg Error (actual - line) |
|--------|---|----------|---------------------------|
| HIGH_EARLY_INFLATION | 226 | 0.610 | -0.25 |
| NORMAL | 288 | 0.554 | -0.17 |
| HIGH_LATE_INFLATION | 307 | 0.575 | -0.16 |

Full-game UNDER signals perform best in HIGH_EARLY_INFLATION bucket (+5.6pp vs NORMAL). This is coherent: when the market sets a relatively high F5 line (early inflation), it also tends to misprice the full game.

### Full-Game OVER Signals by Bucket (N=3,059)

All buckets near 51% -- no meaningful differentiation.

### F5 Line Hit Rates by Bucket (All 3,880 Games)

| Bucket | F5 Under Rate | F5 Over Rate |
|--------|---------------|--------------|
| HIGH_EARLY_INFLATION | **0.537** | 0.463 |
| NORMAL | 0.503 | 0.497 |
| HIGH_LATE_INFLATION | 0.466 | **0.534** |

**Chi-square test (HLI vs HEI F5 over rate): chi2=12.53, p=0.0004.** The difference is statistically significant.

### 2026 Signal Interaction (Small Sample)

| Bucket | N | F5 UNDER Win Rate |
|--------|---|-------------------|
| HIGH_EARLY_INFLATION | 6 | 0.833 (5W-1L) |
| NORMAL | 21 | 0.400 |
| HIGH_LATE_INFLATION | 21 | 0.381 |

Directionally consistent but N is too small to draw conclusions.

---

## Phase 5: Market-Relative Test

### F5 Market Accuracy by Bucket

| Bucket | F5 Over Rate | FG Over Rate | Late Over Rate | Mean F5 Error | Mean Late Error |
|--------|-------------|-------------|----------------|---------------|-----------------|
| HIGH_EARLY_INFLATION | 0.463 | 0.494 | 0.491 | +0.233 | +0.407 |
| NORMAL | 0.497 | 0.501 | 0.418 | +0.427 | -0.059 |
| HIGH_LATE_INFLATION | 0.534 | 0.487 | 0.363 | +0.778 | -0.395 |

### Season Stability

| Season | HEI F5 Under WR | HLI F5 Over WR |
|--------|-----------------|-----------------|
| 2024 | 0.532 | 0.558 |
| 2025 | 0.541 | 0.513 |

HEI F5 under is stable across both seasons. HLI F5 over is strong in 2024 but fades in 2025.

No open-to-close data available to test mismatch narrowing.

---

## Phase 6: Artifact Check

### 1. F5 Line Granularity Problem

**This is the dominant driver of the mismatch signal.**

F5 line distribution:
- **71.1% of games have F5 = 4.5**
- 73.8% of games have F5 in {4.0, 4.5, 5.0}
- Only 9 unique F5 line values in the entire dataset

With F5 pinned at 4.5, late_ratio is purely a function of the full-game line:
- FG = 7.5 implies late_ratio = 0.833 (HIGH_EARLY_INFLATION)
- FG = 8.5 implies late_ratio = 1.111 (NORMAL)
- FG = 9.5 implies late_ratio = 1.389 (HIGH_LATE_INFLATION)

**The "mismatch" is not two independent market assessments disagreeing. It is the F5 market failing to differentiate game quality because 71% of F5 lines are set at exactly 4.5.**

### 2. Correlation Structure

| Pair | Correlation |
|------|------------|
| f5_line vs close_total | 0.796 |
| actual_f5 vs close_total | 0.142 |
| actual_f5 vs actual_total | 0.737 |
| f5_line vs actual_f5 | 0.128 |
| late_ratio vs f5_line | -0.558 |
| late_ratio vs close_total | 0.051 |

The F5 line tracks the FG line well (0.80 correlation), but the F5 line has essentially zero predictive power for actual F5 scoring (0.13 correlation). This is because the F5 line is clustered at 4.5 regardless of actual scoring conditions.

### 3. F5=4.5 Subset Confirms the Pattern

With F5 fixed at 4.5 (N=2,760):

| FG Line Range | N | Implied Late | Actual Late | Late Gap | Actual F5 | F5 Gap |
|---------------|---|-------------|-------------|----------|-----------|--------|
| [6.5, 8.0) | 430 | 2.98 | 3.70 | +0.72 | 4.74 | +0.24 |
| [8.0, 8.5) | 676 | 3.50 | 3.63 | +0.13 | 4.76 | +0.26 |
| [8.5, 9.0) | 1,087 | 4.00 | 3.95 | -0.05 | 5.00 | +0.50 |
| [9.0, 10.0) | 566 | 4.58 | 4.15 | -0.43 | 5.26 | +0.76 |

**When FG line is high (9+) but F5 stays at 4.5, the market puts all the extra runs in late innings. In reality, the extra runs are more evenly distributed.** Actual F5 is 5.26 in these games (0.76 above the 4.5 line), not the 4.5 the F5 market implies.

### 4. Round-Number Clustering

The F5 market is severely constrained by 0.5-run increments. A game with FG total = 9.0 "should" have F5 = ~5.0, but the market often stays at 4.5 rather than moving to 5.0. This half-run of resolution creates a 0.27 swing in late_ratio.

---

## Phase 7: Practical Framing

### Implied ROI at Standard -110 Juice

| Strategy | Bucket | Win Rate | ROI at -110 | N |
|----------|--------|----------|-------------|---|
| F5 UNDER | HIGH_EARLY_INFLATION | 53.7% | +2.5% | 1,446 |
| F5 OVER | HIGH_LATE_INFLATION | 53.4% | +2.0% | 1,138 |
| F5 UNDER | NORMAL | 50.3% | -4.0% | 1,289 |

### Season-Level ROI

| Year | HEI F5 Under | HLI F5 Over |
|------|-------------|-------------|
| 2024 | +1.6% | +6.6% |
| 2025 | +3.3% | -2.2% |

**HEI F5 Under is the more stable side** (positive both years). HLI F5 Over showed profit in 2024 but went negative in 2025.

### Deployment Channel

The signal has two possible uses:

1. **F5 pass filter:** When our F5 model generates an UNDER signal AND the game falls in the HIGH_EARLY_INFLATION bucket, confidence is higher. This is the cleanest application.

2. **Standalone F5 UNDER on HEI games:** 53.7% win rate on ~750 games/season at +2.5% ROI is marginal. After juice variance, this is not standalone-profitable with confidence.

3. **Full-game filter:** No meaningful differentiation. The mismatch does not help full-game totals decisions.

4. **Cross-market badge:** Could flag games where the F5 market "hasn't caught up" to the game quality implied by the FG total. But this is really just "F5 = 4.5 when it should be 5.0."

---

## Decision: NEAR MISS

### What's Real

1. **The F5 market underadjusts for game quality.** When the full-game total is 9+, the F5 line stays at 4.5 in most games. Actual F5 scoring in these games averages 5.26. This is a genuine market inefficiency.

2. **Statistically significant.** The F5 over rate difference between HIGH_LATE_INFLATION (53.4%) and HIGH_EARLY_INFLATION (46.3%) has p=0.0004 on 2,584 games.

3. **Directionally coherent.** The market overestimates late scoring in high-total games and underestimates it in low-total games. Actual pacing is more uniform than implied.

4. **Season-stable on the UNDER side.** HEI F5 Under was +1.6% in 2024 and +3.3% in 2025.

### Why NEAR MISS (Not Advance)

1. **Artifact-dominated.** The "mismatch" is 71% driven by F5 line granularity (clustering at 4.5). This is not two markets independently disagreeing about game structure; it is one market (F5) lacking resolution.

2. **Thin edge.** 53.7% win rate at -110 yields +2.5% ROI. After realistic juice (some lines at -115, -120), this is likely break-even or slightly negative.

3. **One-sided stability.** HLI F5 Over collapsed from +6.6% to -2.2% between seasons. Only the UNDER side holds.

4. **Redundant with simpler signal.** "Bet F5 under when the FG total is low (sub-8.0) and F5 line is 4.5+" captures the same effect without the mismatch framework. The mismatch feature adds complexity without adding independent information beyond "F5 line is too high for this game."

5. **No full-game application.** The mismatch has zero signal for full-game over/under decisions.

### Recommended Next Step

If pursued, the cleanest path is:
- Use as a **F5 UNDER confidence booster** when bucket = HIGH_EARLY_INFLATION AND our existing F5 model already generates an UNDER signal
- Do NOT deploy as standalone; the edge is too thin
- Monitor 2026 sample (currently N=6 in HEI, need 50+ before re-evaluating)
