# NHL edge hunt — open search from scratch (Cowork, 2026-09-29)

Jeff: find any repeatable NHL edge he can take at Hard Rock. Search every market and condition the data allows,
with a fixed discovery / validation / holdout protocol. **Result: nothing survives.** The detail is below, so
the null can be checked rather than taken on trust.

Pre-registration: `PREREGISTRATION.md` (sha256 `37ba3a17…`), written at 03:38Z before any outcome was looked
at. Scripts in run order: `build_features.py` -> `scan.py` -> `holdout.py` (opened once) -> `shape.py`,
`era_table.py`. Results: `scan_results.csv` (every tested cell), `survivors_DV.csv`, `holdout_results.csv`,
`shape_report.md`, `era_table.md`.

## 1. Data inventory (step 0)

| What | Seasons | Source | Price? |
|---|---|---|---|
| Scores, OT/SO flag, schedule | 1990-91 .. 2025-26 | NHL Stats API via public panel `github.com/ethanbell528-cmd/fda-project-1` `data/nhl.csv` | — |
| Closing moneyline, both sides | 2007-08 .. 2021-22 + 342 games of 2022-23 | SportsbookReviewsOnline (SBRO) closing odds, same panel | **yes** (real closing price) |
| Closing total LINE | same | SBRO | **no** (the panel dropped the over/under juice) |
| Puck-line side (+/-1.5) | 2014-15 .. 2022-23p | SBRO | **no** |
| Starting goalies | 1990-91 .. 2025-26 | NHL Stats API goalie logs, same panel `data/nhl_goalie_starts.csv` | — |
| Team xG, shots, goals by game | 2008-09 .. 2025-26 (to ~31 Mar 2026) | MoneyPuck, repo `nhl/cache/moneypuck_all_teams.csv` | — |
| Closing totals WITH prices | 2021-22 .. 2025-26 | repo `nhl/nhl_games_canonical.csv` (DraftKings/FanDuel) | **yes** |
| 11-book game lines | 2025-10-07 .. 2026-03-27 | repo `data/odds_archive/nhl/game_markets/` | totals only usable (see defects) |
| 7-book player props | Oct 2025 .. Mar 2026 | repo `data/odds_archive/nhl/props/` | yes, one season only |
| 30-min multi-book tape | from 2026-09-27 | repo `data/odds_archive/nhl/line_history/` | yes (Pinnacle; Hard Rock absent) |

**Checked, and it matters:** the DraftKings "closing" totals were pulled from an Odds API historical snapshot at
04:00Z the next day, which could have caught in-play lines. On the 1,311 games of 2021-22 where both exist, DK and
SBRO lines differ by 0.5 on 24% of games, but the difference does not track the final total
(corr(DK - SBRO, goals) = -0.04). If DK had caught in-play lines, that correlation would be clearly positive.
The raw `nhl/cache/odds_nhl_*.json` files DO contain non-pregame lines (totals of 1.5 .. 51.5) and were not used;
only the cleaned canonical table was (both prices in [-200, +180], overround 1.00-1.12).

**Defects found in repo data:**
- `data/odds_archive/nhl/game_markets/` (the 2025-26 backfill) lost team identity on every team-sided market. h2h
  keeps ONE price per book with no team name. Spreads keep +1.5 and -1.5 prices with no team name, and team totals
  keep two lines with no team name. The writer keyed outcomes by (description, point), which is blank for team
  markets, so the outcomes overwrote each other. Only its totals (over/under at one line) are usable.
- `odds_nhl_*.json` cache: one book, no timestamp, includes in-play/alternate lines (above).

**Missing, and what it would cost:**
- Moneyline and puck-line PRICES for 2022-23 .. 2025-26, and puck-line prices for every season. Source: Odds API
  historical (not reachable from Cowork; Claude Code on the Mac can call it). Featured markets h2h+spreads+totals
  cost 10 x 3 x 1 = 30 credits per snapshot. One snapshot per game day (~23:00Z) over ~630 game days (3.5
  seasons) = ~18,900 credits, or ~37,800 with a second 02:00Z snapshot for western games. Puck line + h2h only:
  12,600 / 25,200.
- SBRO over/under juice, puck-line prices and opening lines, 2007-08 .. 2021-22. Free in the original SBRO xlsx
  files (Internet Archive copies), but web.archive.org is blocked from this sandbox. Worth one try from the Mac.
- Period scores, empty-net goals, start times, officials. Free from the NHL API (api-web.nhle.com
  play-by-play / gamecenter), which is blocked here but reachable from the Mac/VM.
- 60-minute (3-way), OT yes/no and period-line prices: no historical source in hand.
- Starting-goalie confirmation times: no historical source. The starter used here is the actual starter.
- Hard Rock NHL prices: not in the Odds API feed at all (0/33 games, 2026-09-27). Anything Hard-Rock-specific is
  checked by Jeff in the app.

## 2. Search space (step 1)

**123 single conditions**, each known before puck drop:
- **Price:** home no-vig probability in 8 bands; favourite probability in 5 bands; hold terciles; puck line
  disagreeing with the moneyline.
- **Total line:** <=5.5, 6, 6.5, >=7.
- **Schedule (home and away versions):** back-to-back (opponent not), any back-to-back, 3+ days rest, rest
  advantage 2+, 3rd game in 4 nights, 4+ games in 7 days, travel > 1,500 mi since the last game, moved 2+ time
  zones east or west, playing 2+ zones from home, road trip game 4+, first home game after a 3+ game trip,
  homestand game 5+.
- **Goalie:** backup starting (not the team's season-to-date primary), backup vs primary, goalie on a
  back-to-back, season-to-date save % top or bottom quartile, new goalie (<=2 starts after 10 games).
- **Form (season to date, prior games only):** points % top or bottom quartile, points-% gap >= .15, last-10
  >= .7 or <= .3, 4+ win or loss streak, lost or won the last game by 3+, lost the last game in OT/SO, xG% top or
  bottom quartile (season and last 10), PDO >= 1.02 or <= .98, goal difference vs xG difference >= +/-0.3 a
  game, better xG but worse points than the opponent, lost the previous meeting, tank (60+ GP, points % < .45),
  first 10 games.
- **Game:** both teams on back-to-backs, both backups, both primaries, divisional (4+ meetings), scoring pace
  and xG pace high or low, pace vs the total line.
- **Calendar:** month, day of week.

Quantile thresholds come from discovery seasons only. Pairwise combinations (same team where both are team
conditions) were kept when discovery n >= 200.

**Outcomes:**
- Moneyline: side won, vs the no-vig closing probability. ROI is at the real SBRO closing price.
- Totals: over among non-pushes vs 50%. This is triage, because the line has no price before 2021-22.

**4,115 cells tested** (moneyline 2,128, totals 1,987).

Puck line, 60-minute, OT, period and team-total markets could not be scanned: there are no historical prices,
or no team identity. They are covered as outcome SHAPE in section 5.

## 3. Method (step 2) — each check

- **1a/1b provenance.** Form, goalie and xG features use only games strictly before the game date in the same
  regular season (cumulative sums shifted by one game). Schedule facts are known when the schedule is
  published. No end-of-season aggregate is used anywhere.
- **2 leakage.** The splits were fixed before running: moneyline D 2007-14 / V 2014-19 / H 2019-23; totals
  D 2007-14 / V 2014-23 / H 2023-26 at DK prices. Quantiles came from D only. The holdout was opened once, for
  the one D->V survivor.
- **3 identity.** One scan object. Any survivor would be re-implemented from the cell definition in `scan.py`.
- **4 economics.** Moneyline ROI is at real closing prices. Totals are triage (-110) until the holdout, which uses
  DK's real prices.
- **5 aggregates.** Survivors are broken out by season and era (section 4). Eras: 4-on-4 OT to 2014-15, 3-on-3
  from 2015-16, and the pulled-goalie era (see 5E).
- **Independence.** One row per game; nothing is double-counted inside a cell.

## 4. Results

| | observed | expected by chance |
|---|---|---|
| p < 0.05 (all 4,115) | 365 | 206 |
| p < 0.01 | 104 | 41 |
| p < 0.001 | 19 | 4 |
| **moneyline only, p < 0.01** | **21** | **21** |
| BH 10% FDR passes | 5 (all totals, all "under") | — |

- **Moneyline:**
  - Exactly as many p < 0.01 cells as chance predicts, and 0 pass BH.
  - Validation agrees in sign with discovery on 52.9% of all cells, and on 57% of the 21 p < 0.01 cells (n=21).
  - That is a coin flip. The closing moneyline shows no pattern this scan can find.
- **Totals — all the "significance" is the baseline:**
  - Over-rate against the SBRO line was 48.2% in discovery, not 50%. The book shades the juice instead of moving
    the line, and the line had no price.
  - So "under" cells look significant by default. Re-testing against the discovery-wide base rate (a
    sensitivity check added AFTER the results, reported, not used to select anything):
    - 0 BH passes;
    - p < 0.01: 52 vs 41 expected (overlapping pair cells are correlated);
    - discovery -> validation sign agreement 51.6%.
- **The one pre-registered D->V survivor**, under when the away team lost its last game by 3+ in a divisional
  game:

  | split | n | under rate | break-even |
  |---|---|---|---|
  | discovery | 790 | 57.5% | — |
  | validation | 671 | 52.6% | 52.4% at -110 (triage) |
  | **holdout (DK prices)** | 167 | **50.9%** | **51.7% at DK's real prices** |

  In the holdout, ROI **-1.2%**, and 2025-26 was 47.9%. **Fails.**
- **Survivors: 0.**

**Market baselines at real closing prices** (`era_table.md`):
- Backing the home team, the favourite or the underdog blind loses roughly the hold in every era (-2% to -9%).
  The bands are noisy season to season.
- The book's hold on these closing lines fell from 3.8% to about 2.3% from 2018-19.
- Big underdogs (+200 or longer) are not consistently mispriced: -6.8%, +5.7% and -4.6% by era, swinging from
  -22% to +25% by season.
- There is no stable favourite-longshot pattern like the NFL's.

## 5. Shape of outcomes vs prices (`shape_report.md`) — descriptive only

- **A/B. Games tied after 60 minutes:** 20.7%-25.0% per season since 2005-06 (2023-26: 20.7%, 20.7%, 24.8%).
  Close moneylines with totals <= 5.5 run about 24-25%. No historical 3-way prices exist, so this cannot be
  tested.
- **C/E. Two-goal wins rose:**
  - Games won by 2+ went from ~52-54% (2005-16) to ~60-62% (2021-25; 2025-26 57%). Regulation one-goal games
    fell from ~23% to ~17.5%.
  - This fits teams pulling the goalie earlier and more empty-net goals.
- **D. Favourite -1.5 cover rate** at the same moneyline is ~4 points higher in 2020-23 than in 2007-20. At a
  0.60-0.65 favourite, the fair -1.5 price moved from +187 to +140.
  - Whether puck-line prices kept up is **untested**: there are no puck-line prices.
  - I formed this hypothesis after seeing margins through 2025-26. The only clean test is forward: Pinnacle
    -1.5/+1.5 prices on the 30-min tape from 2026-27, graded against results.
- **G. Final totals are lumpy.** The shootout/OT winner's +1 turns every tied game into an odd total. P(6 goals)
  = 10.9% vs 16.1% under a Poisson with the same mean; P(5) = 22.8%, P(7) = 19.7%. A 6.0 line pushes only ~11%
  of the time.
- **F. DK totals by line x juice (2021-26):**
  - Out of ~17 cells, one looked large: 5.5 with the under slightly favoured went over 55% (n=200, +8.8% ROI at
    DK prices).
  - It is carried by 2021-22 (n=107) and 2024-25 (n=61). 2025-26 went 45.5%, and 2022-23 and 2023-24 have 3 and
    7 games.
  - It was found by looking and fails Check 5. **Not a result, not a bet.**
  - Note: section F shows 2023-26 outcomes, so any NEW totals idea drawn from it can only be tested forward.

## 6. Deviations from the pre-registration

1. A totals base-rate sensitivity check was added after results (§4). It removes rather than adds signal, and
   it changed nothing about which cell went to the holdout.
2. The shape tables (§5) show outcomes from the totals holdout seasons. No cell was chosen from them for the
   holdout. Any idea they suggest is forward-test only.

## 7. For Jeff

Nothing found here is a bet. Across 4,115 pre-game conditions over 15 seasons (rest, travel, goalies, form, xG,
luck, prices, totals, calendar and their combinations), the closing moneyline behaves like a fair coin weighted
by its own price. The one totals pattern that got through discovery and validation lost in the holdout at real
DraftKings prices: 50.9% against the 51.7% it needed. So there is no win rate to target and nothing to check in
the Hard Rock app yet.

The one structural change worth watching is that NHL games now end by 2+ goals far more often than they used to
(empty-net goals). That affects the puck line. We can't tell whether books price it correctly without puck-line
prices. The tape now records Pinnacle's puck line every 30 minutes. After a few hundred 2026-27 games we can
grade it forward, or we can buy ~12-25k Odds API credits of 2023-26 history if you want the answer sooner.

## 8. Reproduce

```
# public panel (scores, SBRO closing ML/total/puck-line side, goalie starts)
mkdir -p raw && cd raw
curl -sO https://raw.githubusercontent.com/ethanbell528-cmd/fda-project-1/HEAD/data/nhl.csv
curl -sO https://raw.githubusercontent.com/ethanbell528-cmd/fda-project-1/HEAD/data/nhl_goalie_starts.csv
cd ..
python3 build_features.py raw nhl/cache/moneypuck_all_teams.csv nhl/nhl_games_canonical.csv   # -> games.parquet (not committed, 3.7 MB)
python3 scan.py && python3 holdout.py && python3 shape.py && python3 era_table.py
```
Checks run before writing this: the season-to-date points % for BOS 2016-17 was rebuilt by hand from the raw
scores and matches all 41 home games exactly (max difference 0.0). The holdout row was recounted independently
(n=167, under 50.9%, ROI -1.24%).
