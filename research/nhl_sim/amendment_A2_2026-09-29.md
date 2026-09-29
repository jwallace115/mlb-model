# NHL sim — amendment A2: grading the engine on its best picks (written 2026-09-29, BEFORE any holdout is opened)

Jeff: "what does it take for us to build an engine that's right 70-80 percent of the time". Answer recorded in the
chat: a hit rate means nothing without the price (Pinnacle 72%+ favourites hit 79.1% in 2022-24 against a 78.3%
break-even). What matters is how far a pick's hit rate beats its own break-even. A2 adds a pre-registered grade for
exactly that, on top of A1.2's incremental-information test. It goes into the decision log beside A1 in S-WO3b.

## A2.1 — Definition, fixed now
- For each game and market (moneyline, puck line +/-1.5, total at Pinnacle's line), each side's break-even = 1 /
  (median book decimal price) from the last snapshot <= 6 h before puck.
- **A pick** = the side where engine probability - break-even >= 0.04. At most one side per market per game; if
  several markets in one game qualify, all are logged and clustered by game.
- **Confident A pick** = an A pick whose engine probability is >= 0.70.
- No other threshold may be introduced after the holdout is opened. A threshold chosen after looking is a new
  hypothesis, testable only on 2026-27 forward.

## A2.2 — What is reported (holdout 2024-25 + 2025-26, scored once under the lock)
Every cut below reports: count per season and per week; hit rate vs mean break-even; ROI at the median price; and
z of (hit - break-even) with game-clustered variance. Cuts:
- all A picks;
- confident A picks;
- by price band: favourites <= -150 / near-even -150..+130 / underdogs >= +130;
- by market;
- by season (each holdout season separately);
- by month;
- by gap size (0.04-0.06, 0.06-0.10, > 0.10).

## A2.3 — The bar
- Engine picks count as "real" only if ALL of these hold:
  - ROI > 0 on all A picks in the holdout, with z >= 1.64;
  - ROI >= 0 in EACH holdout season separately;
  - no single price band or month carries the result (Check 5).
- Passing sends the A-pick rule to 2026-27 forward logging at Hard Rock prices, checked in the app. It is never
  called validated or +EV before that.
- Pre-registered expectation: the A-pick hit rate is within noise of its break-even in the holdout (the edge hunt
  found no public-information edge at the close). The purpose of A2 is to measure that honestly, not to assume it.

## A2.4 — Why the bar is set in hit-rate-over-break-even, not raw hit rate
At -110 the break-even is 52.4%. The long-run hit rates of the best known sports bettors are about 55-57% at that
price. At +150 the break-even is 40%, and 43-45% is excellent. A hit rate of 80% at -110, or 60% on +150 underdogs,
would be 25-28 points above break-even. No betting market is mispriced like that repeatedly, and any account that
did it would be limited within weeks. The engine is therefore built and judged on beating break-even by a few
points, reliably, with low volume and a long proof window.
