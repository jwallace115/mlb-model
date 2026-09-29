# NHL edge hunt, phase 3 — game lines at real multi-book prices (Cowork, 2026-09-29)

Data: NHL WO2's Odds API history.
- h2h, spreads and totals, 9 books incl. Pinnacle, 2022-23 .. 2025-26.
- 3-way, 2024-25, partial.

Pre-registration: `PREREGISTRATION_P3.md`. It was written before any pulled price met an outcome. It also has an
addendum for the one declared follow-up test.

## Checking WO2 against its files (not its report)
- **Holds:**
  - 2,005 snapshot files (490 / 510 / 505 / 500 by season).
  - Team names kept on every outcome.
  - Pinnacle has a moneyline on all 4,529 matched games.
  - Hard Rock is absent from every snapshot.
  - The log reports 30 credits per snapshot call, 62,538 in total.
- **Coverage gap the report did not state:**
  - 771 of 5,608 events have no snapshot within 6 hours of puck (mostly afternoon starts), so they were dropped.
  - 4,529 regular-season games remain: 1,156 / 1,140 / 1,118 / 1,115 by season. The median snapshot is 1.3 h
    before puck.
- **Not verified:** the claim that the new tests fail on the old normalizer. The data itself shows the old defect
  is gone.

## Scan (130 conditions)
The 123 phase-1 point-in-time conditions, plus 7 market ones:
- Pinnacle vs the median book;
- moneyline dispersion;
- puck-line-vs-moneyline ratio;
- total juice.

Pairs were tested too. Markets: moneyline, puck line (the condition team's ±1.5), and total at Pinnacle's line.
Reference = Pinnacle de-vigged. D = 2022-24, V = 2024-25, H = 2025-26.

**1,335 cells:**

| | observed | expected by chance |
|---|---|---|
| p < 0.05 | 59 | 67 |
| p < 0.01 | 14 | 13 |
| p < 0.001 | 1 | 1 |
| BH passes | **0** | — |
| D->V survivors | **0** | — |

Sign agreement between D and V: moneyline 48%, puck line 43%, totals 61%.

## H_PL (pre-registered single test): is the favourite -1.5 underpriced now that 2-goal wins are more common?
**No.**
- Pooled 2022-26: the favourite covered 37.9% vs Pinnacle's 38.4%.
- ROI -5.4% on the favourite -1.5 and -2.7% on the underdog +1.5, at the median price.
- 2025-26: the favourite covered 32.8% vs 36.3%.
- The books priced the empty-net era. See `H_PL_result.md`.

## H_XG (declared deviation, one test on 2025-26): strong-xG teams -> under
- **Why it was tested:** the only family that agreed across D and V. 12 cells had p < 0.05 with the same sign in
  both, where ~1.7 would be expected by chance.
- **What it was before the test:** in games with a top-quartile xG% team, the under hit 54.5% (D) and 56.8% (V)
  vs ~49.7% at Pinnacle; +5.2% / +9.3% at the median price.
- **2025-26, opened once:**
  - under 44.3% vs 49.9% (n=255, z = -1.80), ROI **-15.0%**;
  - wrong way in 5 of 6 months. **Failed.**
- **Plain reason:** team xG% bunched up in 2025-26 (SD 0.032 vs 0.049 in 2022-23), so only the very top teams
  qualified — and their games went over.
- I did not re-threshold it to rescue it.

## 60-minute draw (descriptive, 2024-25 partial, 1,228 games)
- Games tied after 60 minutes: 20.1%. Pinnacle's de-vigged draw: 21.8%.
- The median draw price is ~+328. Backing every draw at the median price returns -12.5%.

## Bottom line
- Across three phases the search tested:
  - 4,115 cells on 15 seasons of closing moneylines and totals;
  - 1,061 prop cells;
  - 1,335 cells on 4 seasons of 9-book game lines;
  - 2 declared structural hypotheses.
- Nothing survives at a real price. Every lead that looked real in one period reversed in the next.
- Still open: props 2024-25 (~52,500 credits) to re-run the props scan on a second season, and 2026-27 forward
  logging (Pinnacle on the tape; Hard Rock when it appears).
