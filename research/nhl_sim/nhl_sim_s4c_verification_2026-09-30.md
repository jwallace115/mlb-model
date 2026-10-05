# NHL sim — S-WO4c verification (Cowork, 2026-09-30)

Branch nhl/sim-s4b: 187936819 (S44), 0e5d4cd78 (S45). Cowork re-ran nhl/sim/prediction_report.py (committed) and
recomputed the picks from the committed prices.

## Held
- **Totals are now priced from the simulated total-goals distribution** (p_tot_0..15). The same-seed re-price
  reproduced every moneyline and puck-line column (max diff 0).
- **The report reproduces:**
  - moneyline 2023-24: log-loss 0.6647 vs Pinnacle 0.6567; A1 0.376, CI [-0.103, 0.869];
  - both reliability tables, the favourite / underdog split, and the |diff| buckets match S43.
- **Totals 2023-24** (1,079 games, 59 pushes):
  - log-loss 0.7001 vs Pinnacle 0.6942;
  - A1 -0.006, CI [-0.439, 0.458]: no information;
  - 2022-23: 0.7022 vs 0.6896, A1 -0.149.
- **Calibration (fit on 2022-23, applied once to 2023-24):**
  - moneyline 0.6647 → 0.6642 (Pinnacle 0.6567). Pre-registration HELD: better, still behind.

## Wrong or incomplete
1. **Totals slope 0.162 misread.** The log calls the engine "under-confident" on totals; a slope of 0.16 means its
   over/under probabilities are far too EXTREME. Engine totals carry almost no information:
   - the reliability tables are flat (actual 44-54% over across every bin);
   - engine mean P(over) is 0.449 vs an actual over rate of 0.487 (2022-23: 0.425 vs 0.497), a systematic lean
     toward the under.
   After calibration they sit at about a coin flip (0.6935 vs ln 2 = 0.6931), which is "parity" with Pinnacle's
   0.6942 only because Pinnacle's totals are close to a coin flip as well.
2. **"NOT DONE: (empty)" is false.** A2 has hit rates only:
   - no ROI at real prices, no SE, no split by side;
   - no confident picks;
   - no totals picks.
   CC's 676 moneyline picks also differ from Cowork's 488 under the order's definition (edge vs 1 / median
   decimal).

## Cowork computed the missing A2 numbers (real median prices, edge >= 0.04)

| picks | season | n | hit | ROI | SE | notes |
|---|---|---|---|---|---|---|
| moneyline | 2023-24 | 488 | 38.3% | **-3.7%** | 5.8% | |
| moneyline | 2022-23 | 587 | | -1.0% | 5.3% | |
| totals | 2023-24 | 217 | 51.2% | **+0.8%** | 6.7% | 194 of 217 are unders (the under lean) |
| totals | 2022-23 | 319 | | -6.1% | 5.4% | 315 unders |

Totals picks fire on one side more than 90% of the time. By CHECK 5 that is a bias artifact, not a signal.

## Conclusion
**The pre-game engine does not beat the market.**
- Moneyline trails Pinnacle and does not pass A1.
- Totals carry no information beyond the line.
- Picks at real prices are negative or zero.

The engine's value is its game mechanics: 9 / 9 realism on 2022-23, 8 / 9 on the 2023-24 out-of-sample season,
and it can start from any game state. That is what live pricing needs (situation hunter A / B). Next direction: Jeff
decides.

## CHECKS
- **1b:** inputs are point-in-time.
- **2:** calibration fit on 2022-23 only; 2023-24 used for evaluation only.
- **3:** prices come from committed code with seed = game_id.
- **4:** real median prices, picks negative.
- **5:** by month and side; the totals picks are one-sided, so they are not a signal.
