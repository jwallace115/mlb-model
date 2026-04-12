# Signal B HOME -- Clean PIT-Safe Backtest: Executive Summary

**Date:** 2026-04-12
**Signal:** F5 Run Line HOME -0.5
**Trigger:** away_sp_FIP - home_sp_FIP >= 1.5 (PIT-safe expanding mean, min 3 prior starts)
**Sample:** 724 qualifying games, 2022-2025

---

## VERDICT: NOT PROFITABLE

Signal B HOME does not clear breakeven at any realistic F5 run line price.

| Metric | Value |
|---|---|
| Total bets | 724 |
| Record | 390W-334L |
| Hit rate | 53.9% |
| Breakeven @ -135 | 57.4% |
| Edge over BE | -3.6pp |
| ROI @ -135 | -6.2% |
| P/L @ -135 | -22.56u (0.5u flat) |

Even at the most generous realistic price (-120), the 53.9% hit rate falls short
of the 54.5% breakeven. The signal is unprofitable at every price point tested.

---

## Season Breakdown

| Season | N | W-L | Hit Rate | ROI @ -135 | P/L |
|---|---|---|---|---|---|
| 2022 | 199 | 119-80 | 59.8% | +4.1% | +4.07u |
| 2023 | 205 | 100-105 | 48.8% | -15.1% | -15.46u |
| 2024 | 147 | 78-69 | 53.1% | -7.6% | -5.61u |
| 2025 | 173 | 93-80 | 53.8% | -6.4% | -5.56u |

2022 was the only profitable season. 2023-2025 are all unprofitable.
The 2022 result (+59.8% hit rate) looks like noise against three losing seasons.

---

## Gap Bucket Breakdown

| Gap | N | W-L | Hit Rate | ROI |
|---|---|---|---|---|
| 1.5-2.0 | 300 | 166-134 | 55.3% | -3.7% |
| 2.0-2.5 | 173 | 93-80 | 53.8% | -6.4% |
| 2.5-3.0 | 111 | 61-50 | 55.0% | -4.3% |
| 3.0+ | 139 | 70-69 | 50.4% | -12.3% |

No gap bucket clears breakeven. Larger gaps do NOT improve hit rate --
the 3.0+ bucket is actually the worst (50.4%).

---

## Price Sensitivity

| Price | Breakeven | Edge | ROI | P/L |
|---|---|---|---|---|
| -120 | 54.5% | -0.7pp | -1.2% | -4.50u |
| -125 | 55.6% | -1.7pp | -3.0% | -11.00u |
| -130 | 56.5% | -2.7pp | -4.7% | -17.00u |
| -135 | 57.4% | -3.6pp | -6.2% | -22.56u |
| -140 | 58.3% | -4.5pp | -7.7% | -27.71u |
| -150 | 60.0% | -6.1pp | -10.2% | -37.00u |

Unprofitable at every price. The hit rate would need to reach ~55%+ even at -120.

---

## Methodology Notes

1. **PIT-safe construction:** Expanding mean FIP from pitcher_game_logs with shift(1),
   minimum 3 prior starts in the current season. Zero lookahead contamination.
2. **F5 scores:** Fetched from MLB Stats API linescore endpoint (innings 1-5, home/away).
   All 724 qualifying games resolved successfully.
3. **Price assumption:** -135 flat (no historical F5 RL prices available).
   Actual prices would vary; sensitivity table shows results across -120 to -150.
4. **No F5 RL historical prices exist** in the canonical odds archive. The -135 assumption
   is approximate. Actual juice could be worse (more negative) on niche F5 RL markets.

---

## Interpretation

The SP quality gap (away FIP - home FIP >= 1.5) correctly identifies a directional
advantage for the home team, but the 53.9% hit rate is insufficient to overcome
standard F5 run line juice. The signal captures real information about pitching
matchup asymmetry, but the F5 run line market prices this advantage accurately
(or slightly over-prices it from the bettor's perspective).

**Key insight:** The signal worked in 2022 (59.8%) but has degraded to ~53% in
2023-2025. This pattern is consistent with market efficiency improving or the
signal being a small-sample 2022 artifact.

---

## Recommendation

**Do not deploy Signal B HOME.** The clean PIT-safe backtest confirms the signal
is not profitable. The previously reported +27.9% ROI was contaminated by
lookahead bias in the xFIP construction, as established in the threshold proof audit.
