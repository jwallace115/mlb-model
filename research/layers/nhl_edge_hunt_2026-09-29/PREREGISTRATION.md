# NHL edge hunt — pre-registration (written BEFORE any outcome was looked at)

Written 2026-09-29 03:38Z by Cowork. Nothing below is changed after results are seen; any later change is
listed in the README as a deviation with its reason.

## Data used (inventory done first — see README §1)
- Games, scores, decided_in (REG/OT/SO), closing moneyline both sides, closing total LINE (no price),
  puck-line side (no price): public panel built from the NHL Stats API + SportsbookReviewsOnline (SBRO)
  closing odds (github ethanbell528-cmd/fda-project-1, data/nhl.csv). ML/total 2007-08..2021-22 + ~342 games
  of 2022-23; puck-line side 2014-15..2022-23p.
- Starting goalies: same source, data/nhl_goalie_starts.csv (NHL Stats API goalie game logs, 1990-2026).
- Team shot/xG by game: MoneyPuck all_teams gameByGame (repo nhl/cache, 2008-09..2025-26), situation 'all'.
- Totals with REAL prices: repo nhl/nhl_games_canonical.csv (DraftKings/FanDuel close, 2021-22..2025-26),
  cleaned: both prices in [-200,+180] and overround 1.00-1.12.

## Universe
Regular-season games only (playoffs excluded from the scan; reported once as context). One row = one game.

## Splits (fixed now)
- Moneyline: discovery 2007-08..2013-14 | validation 2014-15..2018-19 | holdout 2019-20..2022-23(partial).
- Totals: discovery 2007-08..2013-14 (SBRO line, H0 over = 50%, TRIAGE: no price)
          | validation 2014-15..2022-23 (SBRO line to 2021-22, canonical DK line 2022-23; triage)
          | holdout 2023-24..2025-26 (DK line AND real de-vigged prices).
- Holdout is opened ONCE, only for discovery->validation survivors.

## Tests
- Every condition is built point-in-time: schedule facts (rest, travel, back-to-backs, road-trip length) are
  known in advance; form, goalie and xG features use only games strictly BEFORE the game date of that season
  (regular season only). Starter identity is the actual starter (known at puck drop).
- Moneyline: for a cell, side = the team the condition describes. Statistic z = sum(y - p) / sqrt(sum p(1-p)),
  y = side won, p = no-vig closing probability of the side. Two-sided p-value.
- Totals: over rate among non-push games vs 50%, binomial z. Two-sided.
- Singles AND pairwise combinations; a cell is tested only with n >= 200 games in discovery.
- Benjamini-Hochberg at 10% FDR over ALL discovery tests (both markets pooled). Report the number of p<0.01
  and p<0.05 cells expected by chance vs observed.
- Survivor = BH-significant in discovery AND same sign in validation (and validation p < 0.10 one-sided)
  AND same sign in holdout AND positive ROI at the real closing price in holdout (moneyline: the side's SBRO
  closing price; totals: DK price). Flat -110 is triage only.
- Era/season breakdown for every survivor; if one season or one era (pre/post 3-on-3 OT, 2015-16) carries
  it, it is not a result.
- Prediction written now: the closing NHL moneyline and total are efficient to public pre-game information;
  expected BH survivors in discovery ~0, and none reaching holdout at a real price. Structural shape
  questions (60-minute tie rate, 2-goal margins, empty nets) cannot be priced from this data.
