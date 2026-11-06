# CORRELATION → CAUSATION → FORWARD — pre-registration v1 (NHL + NBA), 2026-11-06 3:30 PM EST

Owner: the "corrcause" chat (Cowork). Status file: `claude/status_corrcause.md`. Repo path (new, this lane's):
`research/corrcause/`. Priors graded in `claude/claude_prediction_ledger.md` (CC-* rows). Jeff, 2026-11-06:
"find games that are correlated then find the causation and see if we can find the causation moving forward ...
we're not looking to find an edge in every game ... do the NHL and NBA, can always narrow down after."

This file is FROZEN once committed (sha256 printed by CC-1 Item 0 and pasted into the status file). Changes get a v2
with a diff; nothing here is edited after the screen runs.

## 0. The method, in one paragraph

History is the SCREEN, never the proof. A condition (something observable before puck drop / tip) is screened for a
correlation with the book being wrong — realized outcome vs Pinnacle's de-vigged closing probability — on the DEV
seasons. A screened correlation is worth nothing until it has (a) a MECHANISM written down, (b) a SECOND PREDICTION
that the mechanism makes about something we did not screen on, which must also hold, and (c) a stated reason WHY THE
BOOK MISSES IT (otherwise it is already in the price). Only cells with all three go to one frozen CONFIRM look, and
only CONFIRM survivors go FORWARD on the 2026-27 tape at Hard Rock prices, graded on CLV vs the Pinnacle close and
on real-price ROI. Nothing is re-thresholded after a miss. Narrow by design: a cell that fires on < 60 games a
season is not measurable and is not registered.

## 1. Discipline checks, stated up front (project rule; they bind every item below)

- CHECK 1a (live cleanliness): every condition uses only data stamped before commence_time; the forward object
  reads the tape and the archives as-of the freeze time, nothing later.
- CHECK 1b (historical construction): every condition is built POINT-IN-TIME from rows dated strictly before the
  game date. No season aggregates, no end-of-season ratings, no "prior-season SP+"-style columns. CC-1 Item 1 ships a
  truncation test: deleting every row dated after D must not change any feature for games on D (must FAIL on a
  planted leak before it passes).
- CHECK 2 (discovery/validation): season roles in §3. Known contamination is written there, not assumed away. The
  NHL situational grammar was ALREADY scanned (4,115 cells on 2007-23 ML / totals; 1,335 cells on 2022-26 at real
  prices; 0 survivors) — a re-scan of the same cells on the same seasons is NOT discovery, it is a second look at
  data the first look already spent. NHL Tier 2 is therefore restricted to market-behaviour features the old scan
  could not see (§5), and CC-1 diffs every Tier 1 NHL cell against the old scan's README.
- CHECK 3 (identity): the forward object is the SAME code (`research/corrcause/cells.py`) that produced the screen,
  with the same thresholds, same missing-value rule (a game with a missing input for a cell is EXCLUDED from that
  cell, never imputed), same book list. Any difference is a new cell id.
- CHECK 4 (economics): residual vs Pinnacle fair is the information metric; the economic metric is ROI at the BEST
  real price among the archived soft books at the last pre-tip snapshot (history), and at Hard Rock's quoted price
  (forward). Flat −110 is never used.
- CHECK 5 (aggregate hiding): every reported cell carries breakdowns by season, by month, by fav/dog (or over/under),
  by line band, and by sample depth; a cell whose pooled effect is carried > 60 % by one season-month is NOT a pass.

## 2. Definitions

- **Pinnacle fair** p_fair: multiplicative de-vig of Pinnacle's last pre-tip quote (the "close"). Where the in-play
  tape exists (NHL 2022-26, NBA 2023-26 per NBA-D1 item 3) the close is the last snapshot with commence_time > snapshot
  time and no in-play flag; otherwise the last pre-match snapshot (NBA lines_hourly; NHL lines_all).
- **Opener** p_open: the first archived Pinnacle quote ≥ 12 h before commence_time (NHL lines_all "early"; NHL
  event_markets T−24h where present from 2023-24; NBA lines_hourly first snapshot). Cells needing an opener exclude
  games without one.
- **Residual** r = outcome(side) − p_fair(side) per game, for the side the cell names; totals use the over/under
  indicator at Pinnacle's closing point (pushes excluded). Cell statistic = mean r with game-clustered SE (and
  season-clustered where the cell is league-wide, §4 NB7).
- **Best soft price**: highest decimal among {draftkings, fanduel, betmgm, williamhill_us, betrivers, bovada,
  pointsbetus, unibet_us, betonlineag} at the same snapshot as the close (never mybookieag / barstool). ROI = mean
  (win·(dec−1) − loss) at that price.
- **Fires**: a cell fires on a game when its condition is true and every input is present. Floor: ≥ 60 fires per
  DEV season (Jeff's floor, 2026-09-30).
- **Second prediction**: a pre-named, measurable quantity Q (from the events / box tables), its direction, and the
  bar it must clear (one-sided p < 0.10 on the fired games, same clustering). It is a FILTER on the mechanism, not a
  claim of edge; a cell whose Q fails is dropped even if r passes.

## 3. Season roles (CHECK 2)

| | NHL | NBA |
|---|---|---|
| SCREEN (DEV) | 2022-23 + 2023-24 (Pinnacle close + 9 soft books) | 2022-23 + 2023-24 (NBA-D1 lines_hourly, Pinnacle + 9) |
| Power/stability only (no p-values vs Pinnacle) | SBRO close 2010-11..2021-22 for cells whose inputs exist that far back — sign consistency by season only | — (no pre-2022 Pinnacle history) |
| CONFIRM (one look, rule frozen) | 2024-25 ONLY for cells whose defining variable is a market-behaviour variable absent from the 2026-09-29 scan grammar (CC-1 Item 0 certifies each cell); every other NHL cell confirms FORWARD only | 2024-25 (one look; the legacy program touched it for totals-ridge and archetype lists, so cells defined by team LISTS are excluded from this family) |
| FINAL (locked) | 2025-26 (PARTIAL per the NHL ledger — EV2 confirmation consumed it; not opened here) | 2025-26 (PARTIAL — RW@SH's one look; not opened here) |
| FORWARD | 2026-27 on the VM tape (30-min, Pinnacle + Hard Rock) from the first registered forward date | same |

Rule: a cell is looked at on CONFIRM at most once; a cell that fails CONFIRM is dead with its id; a new definition is
a new id. The forward test is the only evidence that counts as "the causation held moving forward" (Jeff's words).

## 4. Tier 1 — mechanism-first cells (pre-registered now; screened in CC-1)

Each cell: condition (point-in-time), side, mechanism, why the book misses it, second prediction Q, Cowork prior
P(passes DEV screen incl. BH) / P(survives CONFIRM), overlap note. Thresholds are frozen here. Prior numbers are
Cowork's before any data and go to the ledger as CC-NH*/CC-NB* rows.

### NHL (market-behaviour first — the situational grammar is already spent)

- **NH1 — Total pushed DOWN a full key step.** Pinnacle total at close is ≤ opener − 0.5 (e.g. 6.5 → 6.0, 6.0 → 5.5).
  Side: OVER at the closing point. Mechanism: NHL totals sit on half-goal key numbers where each step is a large
  probability move; late flow (goalie/injury narrative, public under money on a "defensive" matchup) pushes the
  number through a step and the book balances rather than re-estimates (Jeff's standing hypothesis). Why missed: the
  close is flow-driven on the last step. Q: 5v5 attempt rate per 60 (both teams, events table) in fired games is NOT
  below the two teams' prior-10-game 5v5 attempt rate by ≥ 2 % (the game is not actually slower). Prior 20 % / 8 %.
  Overlap: the 2026-09-29 totals scan used closing lines only (no opener→close moves) — new variable.
- **NH2 — Total pushed UP a full key step.** Mirror of NH1; side UNDER. Prior 12 % / 5 % (the project's recorded
  pattern in MLB and NBA is over-suppression, not over-inflation).
- **NH3 — Soft-only moneyline move.** At the close, book j ∈ {draftkings, fanduel, betmgm} has moved its de-vigged
  home probability ≥ 3 pts from its own opener while Pinnacle moved < 1 pt in the same direction. Side: AGAINST the
  soft move, at book j's price. Mechanism: action balancing at the retail book with no sharp confirmation. Why
  missed: by construction the soft book is the one that is wrong; Pinnacle is not. Q: Pinnacle's opener→close
  change toward the soft move is < 0.5 pt (Pinnacle did not follow). Prior 25 % / 10 % (the LM-1b lesson: the shade
  is real in NFL but smaller than the vig at the paid price — the economics test is the hard one).
- **NH4 — Backup-goalie overshoot.** Confirmed non-primary starter by the strict A-01 definition (primary has ≥ 60 %
  of prior starts, team ≥ 10 prior starts) AND Pinnacle's ML moved ≥ 2 pts against that team from opener to close.
  Side: the backup's team at the close. Mechanism: the market applies a near-fixed "backup discount"; for average
  backups it overshoots. Why missed: starter quality is priced as a category, not a rating. Q: the residual is
  concentrated where the backup's prior-season GSAx/60 is within 0.10 of the primary's (quality-insensitive pricing)
  and ≈ 0 where the backup is ≥ 0.25 worse — report both halves; pass requires the "close-quality" half to carry the
  effect. Prior 15 % / 6 %. Overlap: A-01 tested the ENGINE's information in backup games, A-02 R3 the engine's
  coefficient; neither tested a market overshoot. 2024-25 was touched by R3 → NH4 confirms FORWARD only.
- **NH5 — Post-OT road back-to-back with travel.** Team playing game 2 of a B2B, on the road, whose game 1 went to OT
  or SO, with ≥ 1 time-zone change between the two venues. Side: opponent ML. Mechanism: compounded fatigue beyond
  the flat B2B discount. Why missed: the book prices B2B as one flag. Q: the fatigued team's first-period 5v5 attempt
  share < 47 %. Prior 10 % / 4 %. Overlap: B2B and pairs were in the 4,115 cells — CC-1 Item 0 checks whether this
  triple interaction was one of them; if yes, NH5 is dropped from Tier 1 and the old result is cited instead.
- **NH6 — Empty-net-inflated favourite.** Favourite (p_fair ≥ 0.58) whose goal differential over its prior 15 games
  includes ≥ +4 net empty-net goals. Side: the underdog ML at the close. Mechanism: public power ratings and
  perception count EN goals as strength; the market's rating-driven number is too high. Why missed: ratings vendors
  don't strip EN goals; the book shades toward the rated team. Q: the favourite's 5v5 xG share over the same 15
  games is ≥ 3 pts BELOW its goal share (the record is PDO/EN-flattered). Prior 15 % / 6 %. Overlap: "form" cells
  were scanned; EN-stripped differential probably was not — Item 0 checks.
- **NH7 — Both rested ≥ 4 days.** Both teams' previous game ≥ 4 days earlier (bye / All-Star return / schedule gap).
  Side: UNDER at the closing point. Mechanism: rust lowers finishing (sh %) before it lowers pace; the market prices
  rest as neutral-to-positive. Why missed: rest is priced as an ML factor, not a finishing factor. Q: all-situation
  shooting % in fired games < league prior-30-day sh % by ≥ 0.5 pt. Prior 10 % / 4 %. Overlap: rest was scanned (as
  ML/totals outcome rates); the both-rested-≥4 cell may have been — Item 0 checks.

### NBA

- **NB1 — Total suppressed ≥ 3 pts.** Pinnacle total close ≤ opener − 3.0. Side: OVER at the closing point.
  Mechanism: injury / "defensive matchup" narrative over-suppression (the pattern the project recorded in NBA and MLB
  totals: significant market errors pointed OVER). Why missed: the cut assumes lower efficiency; pace does not fall.
  Q: possessions (box: FGA − ORB + TOV + 0.44·FTA, both teams) in fired games ≥ the two teams' prior-10 average − 1.
  Prior 30 % / 12 %.
- **NB2 — Total raised ≥ 3 pts.** Mirror; side UNDER. Prior 18 % / 7 %.
- **NB3 — Soft-only spread move.** Book j ∈ {draftkings, fanduel, betmgm} moved its spread ≥ 1.5 pts from its own
  opener while Pinnacle moved < 0.5 in that direction. Side: against the move, at book j. Mechanism / why missed as
  NH3. Q: Pinnacle's opener→close spread change toward the move < 0.5. Prior 25 % / 10 %.
- **NB4 — Star out, total cut.** A player in the team's top-2 by prior-10-game usage (FGA + 0.44·FTA + TOV share) is
  OUT on the official report as-of ≥ 30 min before tip (game_asof rule, NBA S0d), AND the Pinnacle total dropped ≥ 2
  vs the opener. Side: OVER. Mechanism: replacement units play faster and usage redistributes to efficient secondary
  options; the market cuts points roughly linearly with lost usage. Why missed: the book models the loss, not the
  substitution. Q: possessions ≥ team's prior-10 average + 1. Prior 25 % / 10 %. Data note: the parsed official
  reports cover 2023-24 and part of 2024-25 (game_asof 2,481 games) — DEV may reduce to 2023-24 alone; Item 0
  states the covered seasons, and a one-DEV-season cell can only pass as EXPLORATORY (forward confirm only).
- **NB5 — Eastbound 3-in-4 road fatigue.** Third game in four nights, on the road, having crossed ≥ 2 time zones
  eastward since game 1 of the stretch. Side: opponent against the spread. Mechanism: circadian + travel, beyond the
  flat B2B/3-in-4 discount. Why missed: the book's schedule factor is a flag, not a direction-of-travel term. Q: the
  fatigued team's 4th-quarter net rating in fired games ≤ its prior-20-game 4Q net rating − 3. Prior 15 % / 6 %.
  Overlap: the legacy "schedule fatigue domain closed (0/7)" tested 7 proxies on totals with contaminated features
  and never opened its holdout (kill ledger: INCONCLUSIVE) — this cell is spread-side with a travel direction and
  counts as new.
- **NB6 — OT-fatigue back-to-back.** Second game of a B2B when game 1 went to overtime. Side: opponent ATS.
  Mechanism: starters' extra minutes + late finish. Why missed: B2B is one flag. Q: the team's top-5 by minutes play
  ≥ 2 fewer minutes each in game 2 than their prior-10 average (coaches rest them) OR 4Q net rating ≤ prior-20 − 3;
  pre-registered as either (report both). Prior 15 % / 6 %.
- **NB7 — Early-season pace anchor (league-wide cell).** Window: season tip-off through November 15. Direction set
  point-in-time: on each date D in the window, compare league pts/game over the season's games before D (≥ 40
  games required) with last season's full-season pts/game; if the gap ≥ +2.0 side OVER for games on D, ≤ −2.0 side
  UNDER, else no fire. Mechanism: books anchor October totals to last season's level; the league's pace/foul regime
  shifts year to year (rule points of emphasis). Why missed: the anchor updates slowly. Q: the residual's sign
  equals the gap's sign in EACH DEV season separately (season-clustered; with two seasons this is a direction check,
  not a p-value — the cell is EXPLORATORY until it has ≥ 3 seasons). Prior 25 % / 10 %.
- **NB8 — Rest-premium overshoot.** Home team on ≥ 3 days' rest vs an opponent on the second night of a B2B. Side:
  the B2B team ATS. Mechanism: the retail "schedule alert" pushes the rested home side; the market's rest premium
  overshoots. Why missed: public bias on a visible schedule fact. Q: the B2B team's 4Q net rating in fired games is
  NOT below its prior-20 by more than 1 (the fatigue the price assumes does not show up). Prior 15 % / 6 %.
- **NB9 — Late upgrade (questionable → active).** A top-3-usage player listed QUESTIONABLE/DOUBTFUL on the day's first
  report and ACTIVE/AVAILABLE on the as-of report (≥ 30 min pre-tip), with the team's spread having moved ≥ 1 pt
  against it between the two reports. Side: that team ATS at the close. Mechanism: timing — the price discounted him
  and has not fully recovered. Why missed: the recovery is partial by the close at soft books. Q: Pinnacle's spread
  recovers ≥ 0.5 of the move by its close (the sharp book moved back; the soft book did not). Prior 15 % / 6 %. Same
  data note as NB4.

### Dismissed at registration (Jeff may promote any of these; listed per the prediction-ledger rule)

- Blowout bounce-back (lost by ≥ 25 last game): no second prediction exists beyond the outcome → fails §0(b) by
  construction. Testable for free: yes, as Tier 2 only.
- Revenge / rivalry / national-TV / coach-change cells: narrative with infinite cells; no mechanism that names a Q.
- NHL derivative markets (puck line, 3-way): closed — the engine shows Pinnacle hangs them at market grade.
- Garbage-time-inflated ratings (NBA): needs play-by-play we have not pulled; parked.

## 5. Tier 2 — bounded open scan (the "find the correlations" step), DEV seasons only

Purpose: generate hypotheses Tier 1 did not think of. It is NOT evidence. Family size is declared here so BH is
honest; every cell's count is recorded; anything it surfaces must be written up as a Tier 1-style cell (mechanism,
why missed, Q, prior) BEFORE any CONFIRM look, and confirms FORWARD only if its variable was in the old NHL scan.

- Grammar: single feature × binned level × market × side. No pairs (pairs were the multiplicity sink in 2026-09-29).
- NBA features (18): rest days H / A (0,1,2,3+), B2B H / A, 3-in-4 H / A, time zones crossed (0,1,2+), days since
  last game H / A, win streak ≥ 3, loss streak ≥ 3, last-game margin band (≤ −15, −14..14, ≥ 15), opener spread
  band, opener total band (< 220, 220-230, > 230), Pinnacle spread move band (≤ −1.5, −1.4..1.4, ≥ 1.5), Pinnacle
  total move band (≤ −2, −1.9..1.9, ≥ 2), soft–Pinnacle divergence at close (≥ 2 pts implied, either direction),
  share of the move in the last 3 h (≥ 70 %), month, weekday, divisional, star-out flag (where reports exist).
  Markets × sides: ML (H/A), spread (H/A), total (O/U) → 6. Declared family ≈ 18 × 3 × 6 = 324 cells.
- NHL features (8, market-behaviour only): opener ML band, opener total band (5.5 / 6 / 6.5+), Pinnacle ML move band
  (≤ −3, −2.9..2.9, ≥ 3 pts), total move (down a step / flat / up a step), soft–Pinnacle divergence at close (≥ 2 pts),
  move timing (last 3 h share ≥ 70 %), book-consensus dispersion at close (SD of de-vigged home prob across 9 books,
  top tercile), in-play first-snapshot reset (Pinnacle ML at the first in-play snapshot differs from its pre-match
  close by ≥ 2 pts). Markets × sides: ML (H/A), total (O/U) → 4. Declared family ≈ 8 × 3 × 4 = 96 cells.
- Whole-family BH 10 % across Tier 1 (16) + Tier 2 (≈ 420) + every p-value the NHL ledger already holds (63), one
  family, as the NHL ledger requires. A Tier 2 cell that passes BH is a HYPOTHESIS, not a result.

## 6. Pass bars (frozen)

- SCREEN pass (Tier 1 or Tier 2): fires ≥ 60 games in EACH DEV season; mean r has the registered sign in each DEV
  season; pooled game-clustered one-sided p survives whole-family BH 10 %; ROI at the best soft price > 0 pooled;
  CHECK 5 breakdowns show no single season-month carrying > 60 % of the pooled effect; and (Tier 1) Q holds at
  p < 0.10 one-sided, or (Tier 2) a Q is then written and tested on the same DEV games before the cell is promoted.
- CONFIRM pass: one run, frozen code and thresholds; mean r same sign with game-clustered 90 % lower bound > 0; ROI
  at the best soft price > 0; Q holds. Fails → dead with its id.
- FORWARD (2026-27 tape, Hard Rock price-to-beat, CLV vs Pinnacle close): shadow only until ≥ 60 forward fires with
  CLV 90 % lower bound > 0 AND real-price ROI > 0; then Jeff decides stakes. The forward log is written by the same
  `cells.py` the screen used (CHECK 3), one row per fire, at the freeze time, never edited.

## 7. Cowork's priors for the ledger (Brier-scored; written before any data)

| id | prediction |
|---|---|
| CC-0a | At least one NHL Tier 1 cell passes the SCREEN bar — 30 % |
| CC-0b | At least one NBA Tier 1 cell passes the SCREEN bar — 45 % |
| CC-0c | Tier 2 produces ≥ 1 BH survivor in NBA — 55 %; in NHL — 25 % (chance alone gives ~0.1 × family at the BH level, so a survivor is expected noise; the point is whether any survivor then clears the Q filter — 20 % NBA, 10 % NHL) |
| CC-0d | At least one cell (either sport) survives CONFIRM — 15 % |
| CC-0e | At least one cell reaches the forward bar (≥ 60 fires, CLV 90 % lb > 0, ROI > 0) by 2027-04-15 — 8 % |
| CC-NH1..NH7, CC-NB1..NB9 | per-cell priors as written in §4 (screen / confirm) |
| CC-0f | The most likely survivor class is the totals-suppression pair (NB1 > NH1 > NB4) — 40 % that the first survivor, if any, is one of these three |

What these numbers say: Cowork expects this to come back mostly empty, and the ledger is how Jeff grades that
expectation. Ideas are killed by data, not by the prior.

## 8. What CC-1 does and does not do

Does: inventory the archives and STOP on anything missing; build the point-in-time condition tables with the
truncation test; run Tier 1 and Tier 2 on the DEV seasons at real prices; write one report with every number
reproducible from committed code; print the family table; commit this file with its sha256. Does NOT: open 2024-25
or 2025-26 for anything; tune any threshold; build a reader layer; place or suggest a bet. Credits: 0 (everything is
on disk). Runtime pre-check is in the work order.
