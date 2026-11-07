# CORRCAUSE registry — v3 ADDENDUM (2026-11-07 ~2:15 AM EST). v1 (ee85d564…) and v2 (f27d4760…) unchanged; this is the diff.
# Written BEFORE any 2024-25 look at NH8 and BEFORE its second predictions were computed on DEV.

## A. Close rule (CHECK 1a fix, applies to every NHL cell from CC-4 on, and to the forward object)
"Close" = the last tape snapshot with snapshot_utc ≤ the listed commence_time (never after). NHL puck drop is
~8 min after the listed time, so this is strictly pre-game. CC-3 found 44 % of NHL v1b/v2 closes were 5–30 min
after the listed start. Every NHL number in screen_v1b / screen_v2 is therefore "close-as-built", not
"pre-game close"; CC-4 re-runs the Tier 1 and Tier 2 NHL tables under this rule and reports both side by side.
Nothing is tuned; the rule is the registry's original intent made exact. NBA (lines_hourly) is unaffected unless
CC-4's check says otherwise.

## B. Totals null (CHECK 5 / null control)
Every one-sided totals cell reports its residual AND its excess over the population residual for the same side,
seasons and close rule (NHL DEV under base +0.022, n 2,454). The screen p stays vs 0 (the registered statistic);
the excess is reported beside it and is the number a CONFIRM must reproduce.

## C. NH8 — soft–Pinnacle moneyline disagreement at the close → UNDER (promoted from T2_NHL_f1_divergence_flag_yes_under)
- Condition (point-in-time): at the close snapshot (rule A), at least one of the 9 soft books (draftkings, fanduel,
  betmgm, williamhill_us, betrivers, bovada, pointsbetus, unibet_us, betonlineag) quoting h2h IN THAT SNAPSHOT with
  `book_last_update` age ≤ 10 min has |de-vigged home prob − Pinnacle's de-vigged home prob| ≥ 0.02 (multiplicative
  de-vig both). Side: UNDER at Pinnacle's closing total (pushes excluded). Fires on ~23 % of games.
- Screen evidence (exploratory family, DEV 2022-23 + 2023-24): r +0.068 (SE 0.021, n 558 synchronous), +0.087 /
  +0.055 by season, +0.046 over the population under base; strictly pre-listed-start rows +0.079 (n 288); ROI
  +10.6 % (SE 4.2 %) at the best same-snapshot soft under price. Survived: asynchrony, quote freshness (both sides),
  favourite size, fair over prob, book count, team, month (6/7), start hour, backup goalie, late ML move, divergence
  sign. No mechanism yet — that is this section.
- Mechanism (primary, M1 — Jeff's standing hypothesis, action balancing): a soft book that sits ≥ 2 pts off
  Pinnacle on the moneyline in fresh quotes is a book shading toward its own liability — these are games with
  lopsided public action. The same public money is on the OVER, and books (Pinnacle included, which also takes
  action) hold the total above fair rather than re-estimate. Why the book misses it: the total is balanced, not
  re-priced; the ML disagreement is the visible footprint of the action.
- Mechanism (secondary, M2 — pace): the disagreement marks games with unsettled inputs (lineups, goalie workload)
  that lower the realised pace more than the total allows for. Why missed: totals are less liquid and adjust less
  than the ML to the same information.
- Second predictions (pre-registered now; computed on DEV in CC-4 as FILTERS, not as evidence; each one-sided
  p < 0.10, game-clustered, same close rule):
  Q1 (M1, price footprint): in flagged games the soft books' de-vigged OVER probability at the close exceeds
  Pinnacle's by more than in unflagged games (mean soft − Pinnacle over prob, flagged minus unflagged ≥ +0.005).
  Q2 (M1, side footprint): in flagged games the driving book is HIGHER than Pinnacle on the FAVOURITE in > 55 % of
  cases (public shading is on the favourite, whichever side is home).
  Q3 (M2, pace): 5v5 attempts/60 (both teams, events table) in flagged games are ≥ 2 % below the two teams'
  prior-10-game average, vs no such gap in unflagged games.
  Q4 (luck check, must NOT be the whole story): all-situation shooting % in flagged games vs league prior-30-day
  — if the under excess is carried by sh % alone with Q1–Q3 all failing, the cell is finishing luck and is dropped.
  PASS rule for the filter: Q1 or Q2 holds (M1) OR Q3 holds (M2); fail = none of Q1–Q3 holds. The mechanism that
  passes is the one carried into CONFIRM and forward (recorded, not chosen after the fact — both are written here).
- CONFIRM: NHL 2024-25, one run, frozen rule above (close rule A, same books, same 0.02, same freshness), on the
  E-WO2 in-play tape season=2024 (10 books incl. Pinnacle, 5-min) + 2024-25 outcomes. Pass = r same sign with
  game-clustered 90 % lower bound > 0 AND excess over the 2024-25 population under base > 0 AND ROI at the best
  same-snapshot soft under price > 0 AND the passing Q holds again. Eligibility: market-behaviour variable absent
  from the 2026-09-29 grammar (OVERLAP_v1 certifies all NHL Tier 2 features NEW) → 2024-25 allowed. Expected n ≈
  280; MDE at p < 0.05 ≈ +0.049 — the look can see an effect of the screened size.
- The look is taken ONLY after Cowork has verified the CONFIRM script on a DEV dry-run (CC-4 Item 3) — a mis-built
  one-shot look cannot be re-taken. CC-5 runs it.
- Cowork priors (ledger CC-4a–4d): Q1 holds 40 %; Q2 holds 45 %; Q3 holds 35 %; at least one of Q1–Q3 65 %;
  CONFIRM pass given the filter passed 30 %; the cell survives a re-run under close rule A at ≥ +0.05 90 %.
- FORWARD (CHECK 3 caveat stated): the VM tape is 30-min, not 5-min; "close" = last 30-min snapshot ≤ listed
  start; divergence at 30-min cadence may fire differently — the forward object is registered as NH8-F with that
  cadence and its own counts; Hard Rock price-to-beat on the under, CLV vs Pinnacle close. ~300 fires a season →
  a one-season forward test is possible; shadow only until ≥ 60 fires with CLV 90 % lb > 0 and ROI > 0.

## D. NH7 note stands (post-break under; not a cell). NB10 DEAD (CC-2). April away-ML DEAD-ARTEFACT (CC-1b).
