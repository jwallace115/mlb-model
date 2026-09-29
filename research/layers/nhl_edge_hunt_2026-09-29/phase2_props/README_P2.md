# NHL edge hunt, phase 2: player props, and the pull that fills every other market (Cowork, 2026-09-29)

Jeff: "the pattern exists... if data from the odds api can help lets pull it... search all player props to
game lines and everything in between."

Pre-registration: `PREREGISTRATION_P2.md` (sha256 `3eb95b79…`), written at 03:52Z, before any prop outcome was
looked at.

## What was tested now (props already in the repo)

- **Data:**
  - 2025-26 props, 2025-10-07 .. 2026-03-27, 1,151 games, 7 books, about 5 minutes before puck.
  - Markets: points, assists, shots on goal, and goals (two-way at 0.5; one-way Over at 1.5 and 2.5).
  - Graded against the NHL's own boxscores. All 1,151 games matched; the unmatched player-games are players who
    did not dress (void) plus two same-name Vancouver players.
  - Power-play points are excluded: the boxscore has no power-play assists.
- **Rows:** 134,982 player-game-market-lines.
- **Splits:** discovery = Oct-Dec, validation = Jan-Mar.
- **Reference:**
  - Two-way lines: the median de-vigged Over probability across books.
  - One-way lines: the median vig-inclusive price.
- **Statistic:** game-clustered z.
- **Conditions:**
  - line; price band;
  - player season-to-date average vs the line (four bands); hot/cold last 5; ice time up/down;
  - player's own prior hit rate at that line (high/low, and above/below the market);
  - position; home/away; back-to-back;
  - opponent shots allowed (top/bottom quartile); game total high/low;
  - early season; thin markets (<= 3 books); books disagreeing (>= 6 points);
  - plus pairs.
- **1,061 cells tested.**

**Results:**
- **Two-way props (points, assists, SOG, anytime goal):**
  - p < 0.01: 20 cells vs 8.8 expected. The pairs overlap heavily, which inflates this.
  - 0 pass BH inside the two-way family.
  - Under the pre-registered pooled BH, 8 assist-under cells passed discovery and validation. Every one LOSES at
    the median book's real price: -3.2% to -4.3% in discovery, -4.4% to -5.0% in validation.
  - Assist Overs at 0.5 hit 33.9% vs 35.2% fair. That is too small to beat the vig.
  - Survivors that could be bet: **0.**
- **One-way multi-goal Overs are a trap:**

  | line | hit rate | break-even at the median price | ROI |
  |---|---|---|---|
  | 1.5 goals | 1.8% | 3.7% | -64% |
  | 2.5 goals | 0.2% | 1.0% | -84% |

  This is the favourite-longshot bias at its strongest, and it held in both halves of the season. It is an
  AVOID, not a bet: no Under is offered on these.
- **Baselines at the median price** (`props_baselines.md`): every main line loses 1.6-12% on both sides. The
  closest to break-even is SOG 3.5 Under (-1.6%, n=1,323).

## Why pull the Odds API history — and what it can and cannot fix

Game-line markets were never priced in the repo with team identity:
- Moneyline prices exist only through 2022-23.
- Puck-line prices exist nowhere.
- 60-minute (3-way) prices exist nowhere.
- The 2025-26 backfill dropped team names.

The pull fills that gap. The puck line is the one place a real change in how games end (2-goal wins rose from
~53% to ~60-62%) could be mispriced. Props from 2024-25 give a second, independent season to re-run the props
scan with discovery on 2024-25 and validation on 2025-26. 2026-27 forward stays the clean holdout for anything
first noticed in data already seen.

Work order: `research/nhl_layers/workorder_2_odds_history_2026-09-29.md`.
