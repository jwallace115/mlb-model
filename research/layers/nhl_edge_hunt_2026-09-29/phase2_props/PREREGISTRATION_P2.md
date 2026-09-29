# NHL edge hunt, phase 2 (props + every market) — pre-registration

Written 2026-09-29 BEFORE any 2025-26 prop outcome was looked at. Jeff: "search all player props to game lines and
everything in between; if Odds API data can help, pull it."

## Data and splits (fixed now)
- Player props, 7 books (betrivers, betmgm, draftkings, betonlineag, williamhill_us, fanduel, bovada), ~5 min before
  puck, repo data/odds_archive/nhl/props/ (2025-10-07 .. 2026-03-27). Markets: points, assists, shots on goal,
  goals (mostly one-way Over), power-play points (NOT gradable from boxscores: needs PP assists -> excluded).
- Outcomes: NHL boxscores cached in the repo (player goals, assists, points, SOG).
- DISCOVERY: 2025-26 games 2025-10-07 .. 2025-12-31. VALIDATION: 2026-01-01 .. 2026-03-27.
- HOLDOUT: 2023-24 and 2024-25 props from the Odds API historical endpoint — NOT YET PULLED; nobody analyses them
  until the survivor list below is frozen in survivors_P2.csv with its sha256 posted in the README. Their boxscores
  were extracted with 2025-26 (same script) but are not analysed before then.
- FINAL CONFIRMATION: 2026-27 forward, from the live tape, at Hard Rock prices when Hard Rock appears.
- Game lines, 3-way, puck line, team totals, alt lines: tested on the pulled 2022-23..2025-26 history with the
  same rule (discovery 2022-23+2023-24, validation 2024-25, holdout 2025-26 regular season) — written now, before
  the pull.

## Statistic
- Unit = one player-game-market-line. Reference p = median across books of the de-vigged Over probability
  (two-way lines); one-way lines use the median vig-inclusive implied price (reported separately).
- Cell statistic: sum(y - p) with GAME-CLUSTERED variance (sum over games of the squared per-game residual sums).
- n >= 300 rows AND >= 100 games in discovery. BH 10% FDR over all discovery cells. Survivor: BH in discovery, same
  sign in validation with one-sided p < 0.10, then same sign AND positive ROI at the MEDIAN book's real price in the
  holdout seasons, each season separately non-negative. A cell must not depend on one book being off (book is a
  breakout, not a condition), because Jeff can only bet Hard Rock.
