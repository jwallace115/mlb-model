# NHL "situation hunter" — working from "80% is possible" (Cowork, 2026-09-29)

Jeff: assume 80% on -110 lines is possible, on a subset of situations; build toward it. 3-5 points over break-even
is not a failure. 80% is the goal.

## What 80% at -110 requires
The side must truly win about 80% of the time while the price says about 52%. That is a ~28-point information gap.
Re-modelling public statistics does not open gaps like that. The edge hunt (4,115 + 1,061 + 1,335 cells) and today's
rink-bias test (below) both came back priced. Gaps that size exist only where:
1. **time** — we know something before the price updates (live game state, lineup/goalie news);
2. **mechanics** — a price is wrong because of how the book builds it (a stale line vs the sharp market, parlay /
   same-game correlation, derivative markets built by formula);
3. **structure** — settlement rules or market design that the price ignores.

## The engine requirement this creates
The game-state engine (S-WO4) must simulate from ANY mid-game state: period, clock, score, strength, penalty
clocks, goalie in or out. Then the same engine prices both pre-game and live. This goes into S-WO4's spec.

## Situations to hunt, ranked by the size of the gap they could plausibly hold
| # | Situation | Why a big gap could exist | Information needed | Status |
|---|---|---|---|---|
| A | Live: pulled goalie / empty net (late 3rd) | Live totals and moneylines are formula-driven; the empty-net goal rate is large and state-specific | live play-by-play (NHL API, free), live prices | engine + latency probe needed |
| B | Live: power plays, 5-on-3, just after a goal | Next-goal / period-total prices lag state changes | same | same |
| C | Pre-game goalie / star scratch news | The price lags confirmation for minutes to hours | fast starter/scratch sources | WO G1 written |
| D | Props after a line or power-play promotion | Books price props off season averages; a PP1 promotion changes shots and points at once | line combos, shift charts (NHL API, free), news | not started |
| E | Same-game parlays (Jeff's favourite product) | The book's correlation model vs the engine's joint simulation of the same game | engine joint outcomes, Hard Rock SGP prices (app) | after the engine |
| F | Hard Rock stale vs Pinnacle | Hard Rock lags the sharp line (seen in NFL) | Hard Rock prices — not in the API for NHL | manual in-app; a scraper is Jeff's call (terms risk) |
| — | Rink scorer bias on SOG props | Tested today: factors unstable (season-to-season r 0.40 / 0.17 / 0.02), 2025-26 props at those rinks -7% | — | DEAD |
| — | Rest, travel, back-to-backs, form, xG, schedule | Edge hunt: priced | — | DEAD as pre-game stats |

## Data still missing, and what it costs
- Live NHL play-by-play latency (seconds behind the ice?): free; needs a probe.
- Live prices:
  - Hard Rock — app only.
  - Odds API live odds — polled per game, about 3 credits a call. One game every 30 s for 2.5 h is about 900
    credits, so live data goes to targeted situations only.
  - Historical in-play snapshots — to be priced by a 1-call test.
- Line combinations / power-play units: NHL shift charts (free) for history. Pre-game lines are published by
  teams and sites; no structured free feed is known yet.
- Props history 2024-25: ~52,500 credits (next credit cycle).
- Faster goalie/scratch news: G1 measures the free sources first; paid feeds only if free ones are too slow.

## How each situation is judged
Each situation gets its own pre-registration: a definition fixed before looking, the hit rate vs the break-even
of the price we could actually take, game-clustered, and each season separately. It passes only on data it was
not found on, and goes forward at Hard Rock prices. 80% is the aspiration; success is a reliable margin over
break-even.
