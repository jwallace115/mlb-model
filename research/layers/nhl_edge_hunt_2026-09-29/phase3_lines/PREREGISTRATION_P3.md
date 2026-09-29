# NHL edge hunt, phase 3 — game lines with real multi-book prices (Odds API history 2022-23..2025-26)

Written 2026-09-29 BEFORE any pulled price was compared with any outcome. Extends PREREGISTRATION_P2.md
("game lines ... discovery 2022-23+2023-24, validation 2024-25, holdout 2025-26 regular season").

## Price per game
Regular season only. For each game, the LAST historical snapshot before puck (Odds API `snapshot_utc` <
commence_time); games whose last snapshot is > 6 h before puck are dropped and counted.
- Reference probability = Pinnacle de-vigged (two-way) for that market and line.
- Bet price = MEDIAN across the books quoting that exact market/line, taken in decimal odds (a median of American
  odds breaks across +/-100). Hard Rock is absent from every snapshot, so the median US book stands in for it and
  a Hard Rock check in-app is still required before anything is called bettable.

## Markets and outcomes
- Moneyline (condition side won), puck line at -1.5/+1.5 (favourite covered), total at the Pinnacle line
  (over among non-push). Scores and OT/SO from the NHL panel; the shootout winner's +1 counts (as books settle).

## Conditions
The 123 phase-1 point-in-time conditions (thresholds re-used unchanged from phase 1's discovery quantiles) plus
new market conditions built only from pre-puck prices: Pinnacle vs median-US-book disagreement >= 3 points on the
side; book dispersion (max-min implied) high; puck-line price implying a 2+ goal win rate far from what the
moneyline implies (ratio P(fav -1.5)/P(fav win) top/bottom tercile of discovery); total juice direction.
Pairs as in phase 1. n >= 200 games in discovery.

## Rule (same as phase 1)
Game-clustered (one row per game) z vs the Pinnacle reference; BH 10% over all discovery cells; survivor =
BH in discovery, same sign and one-sided p < 0.10 in validation, same sign AND positive ROI at the median book price
in the 2025-26 holdout.

## One structural hypothesis, tested once, no multiplicity
H_PL: because 2-goal wins rose (phase 1 §5), the favourite -1.5 covers MORE often than Pinnacle's de-vigged price
says, and backing it at the median book price is profitable. Tested on all four seasons pooled and by season.
CAVEAT stated now: I saw 2022-26 margins (not prices) before writing this, so a pass here is a lead for 2026-27
forward confirmation, not a result on its own.

## Known contamination
2025-26 totals outcomes were seen in phase-1 shape table F (DraftKings line x juice) — a totals cell surviving to
the 2025-26 holdout is marked "holdout seen" and needs 2026-27 forward. 3-way (2024-25 only, partial) is
descriptive: tie rates for 2024-25 were seen in phase 1.

## ADDENDUM (written after the D/V scan, BEFORE opening 2025-26 for it) — H_XG, a declared deviation
The scan gave 0 BH passes and 0 D->V survivors, so by the rule above the holdout stays closed. One family stood
out anyway: 12 cells with p < 0.05 and the same sign in BOTH discovery and validation (chance ~1.7), all variants of
"a top-xG team is playing -> under". Because it was picked after looking, it gets ONE declared test on 2025-26:
- H_XG condition: either team's season-to-date xG% (MoneyPuck, all situations, prior games only, >= 5 games) >=
  0.5239 (phase-1 top-quartile threshold, unchanged).
- Bet: Under at Pinnacle's line, at the median book's price, last snapshot <= 6 h before puck.
- Seen so far (D 2022-24 / V 2024-25): Under 54.5% / 56.8% vs Pinnacle 49.6% / 49.9%; ROI at the median price
  +5.2% / +9.3%. Complement ("neither team top-xG") leaned Over.
- PASS on 2025-26 = Under rate above Pinnacle's de-vigged Under AND ROI at the median price > 0, reported with z and
  by month. Even a pass is a candidate for 2026-27 forward logging only (selected after multiple testing), never
  "validated", never a bet on its own.
- Known 1b caveat: MoneyPuck's historical xG comes from its current shot model, which was fit on data that
  includes these seasons (shot-quality mapping, not game results).
