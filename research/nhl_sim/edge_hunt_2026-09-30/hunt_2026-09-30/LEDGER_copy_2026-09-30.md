# NHL SIM EDGE HUNT — LEDGER

Standing mandate: Jeff, 2026-09-30 (chat "NHL SIM EDGE HUNT"). Keeper: Cowork. One entry per hypothesis. The
pre-registration text is written BEFORE the numbers are computed; results are appended after. Nothing is deleted.

## Rules of this ledger
- Seasons: DEV = 2022-23 + 2023-24 (or walk-forward seasons once branch D exists). CONFIRM = 2024-25, one run,
  rule frozen. FINAL = 2025-26, locked, opened once per candidate that passes CONFIRM. Then forward shadow 2026-27.
- FOUND = pre-registered + DEV pass + survives Benjamini-Hochberg 10% across EVERY test in this ledger + CONFIRM
  mean CLV vs Pinnacle de-vigged close with 90% lower bound > 0 + ≥ 60 qualifying games per season.
- Every result is at real prices (CHECK 4), broken down by season / month / market / fav-dog / sample depth
  (CHECK 5), point-in-time inputs (CHECK 1), and the tested object is the live object (CHECK 3).
- A confirmation failure is never re-thresholded. A new idea gets a new ID.
- **Season-role proposal for markets with no 2022-24 price history** (3-way exists only for 2024-25; team totals,
  periods, OT props only on the forward tape from 2026-09-29): DEV = the earliest season with prices, CONFIRM =
  the next season (pulled once, only for a rule that passed DEV), FINAL = forward tape. Needs Jeff's OK; until
  then such tests are labelled EXPLORATORY and cannot be FOUND.
- BH family: every p-value in this file, including the pre-mandate tests listed under L-00x.

## p-value family (for BH) — one line per test, appended as they run
| ID | test | p (one-sided unless noted) | status |
|---|---|---|---|
| L-001 | PREREG_CLV clean-set slope 2023-24 (engine predicts Pinnacle move) | 0.59 (slope −0.004, CI [−0.032, 0.024]) | FAILED |
| L-002 | PREREG_EV close H1 (best-of-8 ≥ 2% vs Pinnacle fair, ROI > 0) | ~0.94 (−16.6%, SE 10.8) | FAILED |
| L-003 | PREREG_EV early (secondary) CLV > 0, 2022-24 | 0.0004 (+1.28%, SE 0.38) | dev pass → L-004 |
| L-004 | PREREG_EV2 early rule CLV > 0, 2024-26 (confirmation) | 0.0002 (+2.70%, SE 0.76) | HELD (price rule, not sim; live via NHL-L1) |
| L-005 | PREREG_ALT early off-point totals CLV > 0 | 0.14 (+0.90%, SE 0.83) | FAILED |
| L-006..010 | S48 regimes ML: ALL 0.104; R1 0.908; R4 0.451; R5 0.428; totals ALL 0.527 | | no survivors (7 of 12 never computed → A-02) |

## Entries

### D-01 — Walk-forward 2010-2021 (branch D) — PLAN, not run
- Date 2026-09-30. Branch D. Status: PLANNED, needs a Claude Code work order (long pull) and Jeff's go.
- Why first: every pre-game test so far has two seasons of engine prices. Real SBRO closing ML + totals exist
  2007-2023 in `inputs/games.parquet` (22,842 games; `ml_h/ml_a/tl_sbr/pl_h` present from 2007). Free NHL API
  play-by-play exists from 2010-11 (coordinates + situation codes start there).
- Steps: (0) probe 5 old games (2010020001, 2013020001, 2016020001, 2019020001, 2020020001) for the fields
  build_events.py needs (typeDescKey, situationCode, x/y, periodDescriptor) — STOP if absent; (1) pull pbp +
  boxscore 2010-11..2020-21 with `nhl/sim/pull_pbp.py` (resume-safe); (2) build_events per season; (3) walk-forward
  chain: for target season T, xG model + constants + ratings hyperparameters fit on T-2..T-1 only (build_constants_v7
  --v8 takes a season list; ratings --measure-hyper likewise) — target season never touches its own fit; (4) price
  every game at 2,000 sims, seed = game_id; (5) evaluate vs SBRO close: log-loss, A1, A2 ROI at real close, the
  regime family, all by season. (6) Then every subset hypothesis in this ledger gets 11 more seasons.
- Runtime pre-check: games 2010-11..2020-21 ≈ 6×1,230 + 2×1,271 + 1,082 + 868 = 11,872 (2019-20 and 2020-21
  short). pull_pbp: ~0.3 s request + 0.25 s sleep ≈ 0.55 s/game → 1.8 h pbp, +1.8 h boxscores (two runs, resume-
  safe). Events + ratings: S-WO2/S27 took minutes per season → < 1 h. Pricing: 11,872 × 2,000 sims at ~770 sims/s/
  core = 8.6 core-hours; Mac 8 cores → ~1.1 h; VM 2 cores → 4.3 h. Total ≈ 5-6 h wall, in two work orders.
- Disk: nhl/cache is 264 MB for 6,468 games → ~500 MB more. Credits: 0 (NHL API is free).
- Risks stated up front: (a) old pbp may lack situationCode/coordinates (probe first); (b) rule changes (3v3 OT
  from 2015-16, trapezoid, 2019-20/2020-21 COVID formats) — constants must be fit per window, never pooled across
  the 2015 OT change; (c) SBRO close is a consensus, not Pinnacle — CLV vs Pinnacle is unavailable before 2022;
  the D metric is ROI at SBRO close + log-loss vs SBRO, labelled as such.

### C-01 — Goalie ratings are SWAPPED between teams in game_inputs.py (branch C, engine defect) — pre-registered
- Date 2026-09-30. Found by code reading, then confirmed on the committed prices before this entry was written
  (that confirmation is descriptive; the pre-registration below is for the fix):
  `game_inputs.py` sets `h_mult.goalie_save = 1 - a_gsax/q` and `a_mult.goalie_save = 1 - h_gsax/q`; the engine
  applies `opp.goalie_save` when the OTHER team attacks, so the home goalie's quality scales the home team's
  scoring. Evidence: corr(engine ML logit, home−away goalie rating) = −0.090 (2022-23) / −0.052 (2023-24) vs
  Pinnacle +0.370 / +0.332; logit(outcome) on engine logit + goalie diff gives goalie coef +4.2 (SE 1.05, p<0.001)
  in 2022-23, +2.3 (SE 1.56) in 2023-24; on Pinnacle logit + goalie diff: −0.1 / −3.3 (Pinnacle already prices it).
- Consequence: every engine-as-opinion result S41-S48 and L-001 was produced by an engine that was not the designed
  object (CHECK 3 failure). They are results about the swapped engine.
- PRE-REGISTERED (before the re-price):
  (a) Null control: my re-pricer with the swap left in reproduces S41 `p_home_win` and `mean_total` exactly on 20
      games (same seed = game_id, 2,000 sims). Must hold or the re-pricer is wrong.
  (b) With the fix, 2023-24 ML log-loss improves by ≥ 0.002 from 0.6647 (n = 1,138); 2022-23 likewise from 0.6669.
  (c) With the fix, the goalie-diff coefficient given the engine logit has |t| < 1.64 in both seasons.
  (d) A1 disagreement coefficient on 2023-24 rises above 0.376; whether its 90% CI clears 0 is NOT predicted.
  (e) Puck line / totals structure through the market grid is unaffected (the grid uses no goalie ratings).
- Seasons 2022-23 (fit) + 2023-24 (validate). 2024-26 untouched. Metric: log-loss, A1 coef, goalie-diff t.
- Cost 0. Runtime: 2,624 games × 2,000 sims / (770 sims/s × 2 cores) ≈ 57 min in the Cowork container.

### A-01 — Goalie news: the fixed engine (actual starter) predicts Pinnacle's early→close move when a non-primary goalie starts — pre-registered
- Branch A (goalie swaps / backup starts). Seasons DEV 2022-23 + 2023-24. Inputs: fixed engine prices (C-01),
  Pinnacle first snapshot ≥ 12 h before puck (early), Pinnacle last snapshot (close), `nhl_goalie_starts.csv`.
- Definitions: primary starter = goalie with the most starts for that team in that season BEFORE date D. A game is
  a BACKUP game if at least one team's starter is not its primary, the primary has ≥ 60% of the team's prior
  starts, and the team has ≥ 10 prior starts (strict; early-season churn excluded). Secondary, broad set: any
  non-primary starter with ≥ 1 prior start.
- H1 (information): in BACKUP games, OLS of [logit p_close − logit p_early] on [logit p_engine − logit p_early]
  has slope > 0 with 90% lower bound > 0, in EACH dev season. p = one-sided from HC1 t.
- Null control: the same regression on the CLEAN set (both primaries, no B2B) must stay ≈ 0 (L-001 measured
  −0.004 / −0.027 with the swapped engine; the fixed engine must not create a clean-set slope > 0.03).
- H2 (economics, UPPER BOUND — assumes the starter is known at the early snapshot, which is not achievable in
  practice): bet the engine side at the early median soft price when engine − break-even ≥ 0.03; mean CLV vs
  Pinnacle close > 0 with 90% lower bound > 0; ≥ 60 bets per season required.
- Expected n: strict backup set is a subset of 500 / 479 games with early + close + engine (2022-23 / 2023-24).
- What FOUND would mean here: the edge is in acting on the starter before the market, i.e. situation C (WO G1
  measures the lead time). The forward tape (30-min) then measures how many minutes the soft books lag.

### A-02 — Complete the S48 regime family on the fixed engine — pre-registered
- Branch A. DEV 2022-23 + 2023-24 (report both; 2023-24 is the validate season). 12 tests: R1 early season
  (either team ≤ 10 games played), R2 either team on B2B, R3 either team starting a non-primary goalie (strict
  A-01 definition), R4 |engine − Pinnacle| > 5 pts, R5 engine pick is the underdog, R6 both goalies rated above
  league average (totals) / below (ML) — each × ML and totals. Metric: A1 disagreement coefficient (outcome ~
  logit Pinnacle + (logit engine − logit Pinnacle)), one-sided p for coef > 0; A2 ROI at real median prices
  (edge ≥ 0.04) reported alongside with SE.
- Expected: no survivor at BH 10% across the family (prior tests found none). Survivors only go to CONFIRM.
- Count per season per regime is reported.

### A-03 — Totals: fixed engine mean total predicts Pinnacle's early→close TOTAL move — pre-registered
- Branch A. DEV 2022-23 + 2023-24. Games where Pinnacle's early and close total LINE are equal (share reported).
  y = logit(p_over_close) − logit(p_over_early) (Pinnacle de-vigged at that line);
  z = logit(p_over_engine at that line, from the sim pmf) − logit(p_over_early).
- H: slope > 0, 90% lower bound > 0, each season. Secondary: same in the A-01 strict backup set.
- Null control: the engine's mean-total bias (−4-5%) is a constant offset; the slope is invariant to it, but the
  intercept will be negative — reported, not interpreted.

### B-01 — 3-way (regulation) market: engine-conditioned 3-way vs the books, 2024-25 — EXPLORATORY (season-role rule pending)
- Branch B. Data: `data/odds_archive/nhl/history/threeway/season=2024` — measured before writing this: 1,228 events,
  ONE snapshot per event at ~12 min before puck (lead 0.2 h), Pinnacle on 1,226, soft books betmgm / betrivers /
  draftkings / fanduel / williamhill_us / bovada. Pinnacle's 3-way overround is 1.044 per snapshot (first count of
  1.149 was a double-count over the 800 events with two snapshots — corrected before running); soft books 1.05-1.12.
  No 2022-24 3-way prices exist (~13.7k credits per season, as WO2). No later snapshot → CLV is NOT measurable here;
  metrics are A1-style information tests against Pinnacle's own 3-way and ROI at the real quoted prices.
- Engine: market grid v2 (league-average engine, strength s × pace m, 20k sims per cell, seed as v1) storing the
  REGULATION joint score pmf, decided type, P1 and P1+P2 joint pmfs. Conditioning inputs: Pinnacle's 2-way ML +
  total from the LAST `lines_all` snapshot before the 3-way snapshot (median gap ~1 h; gap reported).
  → p_reg_home, p_draw, p_reg_away per event.
- Structure check (descriptive, pre-registered expectation): 3-class log-loss of engine vs Pinnacle 3-way
  (multiplicative de-vig, and power de-vig reported) on actual regulation results,
  engine within 0.01 of Pinnacle; engine mean p_draw within 1.5 pts of the actual draw rate (20.8% in 2024-25).
- H-B01a (information, draw): logistic of DRAW on logit(Pinnacle fair draw) + (logit engine draw − logit Pinnacle
  draw): coefficient > 0, 90% lower bound > 0 (one-sided p recorded in the family).
- H-B01b (information, regulation home win): same form on REG-HOME-WIN.
- H-B01c (economics): any book's 3-way quote with implied prob ≤ engine prob − 0.03 → bet at that price; ROI > 0
  with 90% lower bound > 0, by side (draw / home / away) and by book; ≥ 60 flags in the season required.
- Expected (Cowork's prior): a/b coefficients near 0 (Pinnacle's 3-way is derived from the same two numbers with
  a formula at least as good); c fails unless the engine's draw differs from the books' by more than their 5-12%
  margin, which it should not.
- Runtime: grid v2 = 63 cells × 20k sims ≈ 37 s each in the container ≈ 20 min on 2 cores. Cost 0.

### C-02 — Where does the engine's excess total-goals variance come from? — measurement, pre-registered
- Branch C (engine defect logged by Jeff 2026-09-30: engine within-game var 5.44-5.54 vs actual across-game 5.18-5.34).
- Pre-registered predictions (before measuring): (i) actual PENALTIES per game are under-dispersed vs Poisson
  (var/mean < 0.85 — referees even up calls and call less late in close games) while the engine's are ≈ Poisson
  (var/mean ≈ 1.0 ± 0.05); (ii) actual PP goals per game var/mean is below the engine's; (iii) the variance of
  regulation 5v5 goals per game is within 5% of the engine's (score effects are already measured in ev5_by_time_score).
  Data: 2022-23 + 2023-24 events tables (shots: is_goal, strength, empty_net, period_type; penalties) vs a 20k-sim
  league-average engine run (pp_opps, pp_goals, en_goals per sim). Descriptive, no p-value in the family.
- RESULT (2026-09-30): (i) NOT HELD — actual penalties per game are OVER-dispersed (var/mean 1.64 / 1.85 all
  penalties; 1.43 / 1.52 for 2-4-5 min) vs the engine's Poisson 0.99; but (ii) also NOT HELD in the expected
  direction: actual PP goals var/mean 0.97 / 1.04 vs engine 1.02 — penalty clustering does not propagate to PP-goal
  variance. Regulation goals: actual var 5.29 / 5.46 (var/mean 0.86 / 0.91) vs engine 5.73 (0.95); actual home-away
  goal correlation −0.116 / −0.117 vs engine −0.098; EN goals var/mean 0.83 / 0.84 vs 0.84 (matches). So the excess
  (~5-8% of variance) sits in 5v5 dispersion / the between-team negative correlation, not in PP or EN. Small; the
  market-conditioning pace knob absorbs the mean but not the shape → engine-priced FAR alt totals (±2 from the line)
  are slightly fat-tailed. Flagged for D-WO2 (measure 5v5 goal variance by score state on 11 seasons). No family p.
- A-02 addendum (before running): two more pre-registered regimes in the family, R7 both teams' 5v5 attempt rate
  > 1.02 × league (pace mismatch / high-event) and R8 both teams' penalties taken > 1.05 × league, each × ML and
  totals → the A-02 family is 16 tests, BH within-family at 10% on 2023-24 and then across the ledger.

### A-04 — Soft books lag Pinnacle's move (stale price after a sharp move), 2022-24 — pre-registered
- Branch A (timing / book mechanics; the price-rule family, not the sim). Distinct from PREREG_EV, which took every
  deviation from Pinnacle at one snapshot and FAILED at close (deviations at close are informed). This conditions on
  Pinnacle having JUST moved.
- Data: `lines_all.parquet`, consecutive snapshots per event (Pinnacle mean 2.7 snapshots/event; requested times are
  fixed daily slots). Rule: at snapshot k (not the first), Pinnacle's de-vigged home prob moved by ≥ 0.03 vs
  snapshot k−1 (either direction); side = the side Pinnacle moved TOWARD; for each soft book j quoting at k, the
  side's implied prob 1/dec_j ≤ Pinnacle-fair(k) − 0.02 → flag (book j is stale by ≥ 2 pts). Moneyline only.
  One flag per event-book-snapshot. Snapshot k must be ≥ 1 h before puck (the last snapshot is used as close).
- Metric: mean CLV = Pinnacle CLOSE fair prob of the side − 1/dec_j, 90% lower bound > 0, each dev season; ROI at
  dec_j with SE; breakdown by book, by move size, by lead time, by fav/dog. Trial p one-sided from CLV t.
- Null control: the same rule with the side = the side Pinnacle moved AWAY from must have CLV < 0 (if it is ≥ 0 the
  "CLV" is an artefact of Pinnacle's own reversion).
- Expected (prior): CLV > 0 by construction is NOT guaranteed — Pinnacle partially reverts after moves; prior belief
  is a small positive CLV (+0.5 to +1.5%) if books lag, and ≥ 60 flags/season is uncertain at this snapshot density.
- Confirmation (if dev passes and BH survives): 2024-25 one run, same script, season switch. Then NHL-L1's 30-min
  tape is the live object (denser snapshots → more flags; CHECK 3: the snapshot cadence differs, stated).
- RESULT (2026-09-30, dev): NOT TESTABLE at this snapshot cadence. Pinnacle moves ≥ 3 pts between consecutive
  snapshots: 144 (143 events) in 2022-24, two-thirds of them AT the last snapshot (so no later close exists). On the
  toward side, soft books were stale by ≥ 2 pts in 0 of 1,074 book-quotes (≥ 1 pt: 3; ≥ 0: 30); mean "staleness"
  −1.7% — i.e. hours after a Pinnacle move the soft books have already moved. No p-value; n = 0 per season.
  → the hypothesis lives only at minutes-scale cadence: candidate amendment to NHL-L1 (30-min tape: Pinnacle moved
  ≥ 3 pts in the last snapshot interval AND book j stale ≥ 2 pts → flag, CLV graded). Forward only.

### RESULTS 2026-09-30 ~04:40Z — C-01, A-01, A-02, A-03 on the fixed engine (one run each; log `work/a_tests_fixed_log.txt`)
- **C-01 (fix)**: null (a) HELD (exact reproduction). 2022-23 (fit): ML log-loss 0.6669 → **0.6594** (Pinnacle 0.6568),
  goalie-diff t −0.47 (HELD), A1 0.448 [−0.066, 0.963]. 2023-24 (validate): 0.6647 → **0.6646** (+0.0001; (b) NOT
  HELD), goalie-diff t −1.76, coef −2.93 ((c) NOT HELD — the fixed engine now OVER-weights the goalie in 2023-24;
  note the same negative sign appears given Pinnacle: −3.3, so the 2023-24 goalie ratings themselves were
  anti-predictive that season), A1 −0.052 [−0.637, 0.534] ((d) NOT HELD). Engine logit now correlates +0.42 / +0.35
  with the goalie diff (was −0.09 / −0.05). Logit SD 0.453 / 0.388 vs Pinnacle 0.560 / 0.514 — still too flat.
  Reading: the fix is right and matters a lot in the fit season (where the xG model is in-sample — CHECK 1b caveat
  on any 2022-23 goalie number), and does nothing out of sample. The engine as a pre-game opinion still trails
  Pinnacle by 0.008 log-loss.
- **A-01 H1 (information) HELD in both dev seasons**: strict backup games n = 214 / 212, slope +0.064 [+0.025, +0.103]
  p = 0.0035 and +0.066 [+0.028, +0.104] p = 0.0020. Null control HELD: clean set +0.022 / +0.020, CIs include 0,
  both < 0.03. Broad set: +0.018 (ns) / +0.032 (p 0.03). **A-01 H2 (economics, upper bound) NOT HELD**: 88 / 80 bets,
  CLV −0.92% / −0.89% (SE 0.2%) — the engine's goalie information (~0.6 pts of move per 10 pts of disagreement) is
  smaller than the soft-median vig (~1.5%). Ledger p: A-01a 0.0035, A-01b 0.0020 (information only).
- **A-03 HELD in both seasons** (totals move, same line, n = 577 / 596): slope +0.066 [+0.044, +0.089] p < 0.0001;
  +0.036 [+0.016, +0.056] p = 0.0017. Strict-backup subset +0.061 (p 0.0095) / +0.031 (p 0.14). No economics test
  was pre-registered → A-06 below. Ledger p: A-03a 0.0000, A-03b 0.0017.
- **A-02 (16 regimes × 2023-24, fixed engine): NO SURVIVORS** at BH 10% within the family (min p 0.0064 = ML R6
  again, coef 3.18, vs threshold 0.0063; in 2022-23 R6 is 0.20 — and its swapped twin already failed 2024-25).
  Descriptive lead, NOT a candidate: ML R8 (both teams take > 1.05 × league penalties) coef +3.37 (p 0.012, n 75)
  in 2022-23 and +2.94 (p 0.072, n 60) in 2023-24 — same sign both seasons, n at the measurability floor, A2 ROI
  +22% / +32% on 26 / 14 picks (noise). Goes to branch D (11 seasons) for power; not carried to 2024-25 now.
  16 p-values added to the family (2023-24 column of `work/a02_regimes_fixed.csv`).

### A-05 — Early best-of-8 price + fixed engine agreement (moneyline) — pre-registered
- Branch A × price layer. DEV 2022-24, early snapshot (Pinnacle first ≥ 12 h), the same 8 books as PREREG_EV.
  Rule: for each side, best available decimal across the 8 books; flag if 1/best ≤ p_engine(fixed, actual starter)
  − 0.03. Metric: mean CLV vs Pinnacle close fair, 90% lo > 0, each season; ROI at the best price; ≥ 60 / season.
- Null control: the same rule with the SWAPPED engine's probabilities must give lower CLV (its goalie information
  points the wrong way). Baseline reported on the same games: PREREG_EV early rule (best ≥ 2% vs Pinnacle fair).
- Expected: CLV positive but the question is whether it beats the EV2 baseline (+1.28% dev); prior: no.

### A-06 — Early best-of-8 totals price vs the fixed engine's total pmf — pre-registered
- Same snapshot and books. For every totals quote (any point) at the early snapshot: engine P(side | no push) from
  the fixed engine's total pmf at that point; flag if 1/dec ≤ engine − 0.03. Metric: CLV vs Pinnacle close fair for
  quotes AT Pinnacle's close line (90% lo > 0, each season); ROI at the quoted price for all flags; ≥ 60 / season.
  Caveat stated: the engine's mean total runs 1-4% low (S46), so UNDER flags will dominate — report by side; a
  one-sided family is a bias artefact (S44 lesson), so the pre-registered pass requires CLV > 0 on BOTH sides.
- Null control: swapped-engine pmf gives the same flags on totals? (goalie swap is nearly symmetric for totals) —
  report the flag overlap; CLV should be ≈ equal. Expected: fails the both-sides requirement.
- **A-05 FAILED** (dev): fixed-engine flags 393 / 348, CLV −0.52% / −0.59% (SE 0.1%), ROI +5.4% / −4.4% (noise);
  null HELD (swapped engine −0.81% / −0.83%, worse). Baseline column mis-specified (fair − 0.02 instead of EV ≥ 2%)
  → n = 0; irrelevant to the verdict. By book: all ≤ +0.4%. p (CLV one-sided) ≈ 1.
- **A-06 FAILED** (dev): 640 / 505 flags, 94% / 84% unders (the S46 under-lean, as predicted); CLV at Pinnacle's line
  −0.56% / −1.23%; Over side −0.11% / −0.70%; off-line ROI +1.5% / +2.6% (SE 7%) = noise. p ≈ 1.
- **Whole-ledger BH (44 p-values, `work/family.csv`)**: survivors = the EV/EV2 price rule (already confirmed and live),
  A-03a/b and A-01a/b (information only — their economics failed), S48 swapped R6 (failed confirmation), fixed ML R6
  (p 0.0064; 2022-23 coef 0.20 → does NOT pass the both-dev-seasons rule; Jeff may override as for its swapped twin
  — 2024-25 fixed prices cost ~7 min on the Mac), S48 swapped R5 (p 0.018; 2022-23 p 0.23; same status).
  **Nothing bettable has been found by the pre-game engine.** The engine's information about goalies and totals is
  real (A-01, A-03) but is worth < 1 pt of price, below the soft-book vig.
- **B-01 RESULT (one run, 2024-25, exploratory): DEAD.** 1,172 events conditioned (all converged; 2-way snapshot
  median 1.1 h before the 3-way one), 1,041 with outcomes. Structure check HELD: engine 3-class log-loss 1.0186 =
  Pinnacle multiplicative 1.0186 (power de-vig 1.0179); mean |engine − Pinnacle| 0.5 pts; engine mean draw 0.208
  vs actual 0.204 (Pinnacle mult 0.218 / power 0.213). H-B01a draw coef −1.13 [−5.79, +3.52] p 0.66; H-B01b reg-home
  coef −4.00 [−7.22, −0.79] p 0.98 (Pinnacle's 3-way is BETTER than the engine's on the home/away split).
  H-B01c: 2 flags in 20,820 quotes (both lost). Every soft book's 3-way is inside its margin of the engine's fair.
  Grid v2 null HELD: final joint pmf identical to grid v1 at every cell (max diff 0). Ledger p: B-01a 0.655,
  B-01b 0.980, B-01c n/a (n = 2).
  Meaning: the engine reproduces Pinnacle's 3-way exactly from Pinnacle's 2-way — a third demonstration that its
  structure is market-grade, and a third demonstration that structure alone is not an edge where Pinnacle hangs
  the market. Derivative markets Pinnacle hangs (3-way, PL) are closed; the open question is markets where only
  soft books hang a price (team totals / periods on the forward tape) — no history exists, ~13k credits per market
  per season to buy.

### C-03 — Are team-specific score-state responses persistent enough to model? — measurement, pre-registered
- Branch C (A1.3 "team modifiers": score-state response). For each team-season (2022-23, 2023-24), from shots +
  state_time: 5v5 attempt share when LEADING by 1 in the 3rd period minus attempt share when TIED in the 3rd
  ("lead-protection drop"), and the same for TRAILING by 1. Split-half (odd/even games) reliability r within season,
  and season-to-season r. Pre-registered bar to be worth building: split-half r ≥ 0.30 AND season-to-season r ≥ 0.25
  on the trailing-side measure (the one that moves totals late). Expected: r < 0.2 (score effects are mostly
  league-wide, as the ev5_by_time_score table assumes). No family p.
- RESULT: bar NOT MET — split-half r of the lead-protection drop 0.085 / −0.164 and of the trailing rise −0.070 /
  −0.008 (2022-23 / 2023-24); season-to-season r lead 0.30, trail −0.04. The tied-state attempt share (plain
  strength) IS reliable (split-half 0.38 / 0.26, season-to-season 0.59) — that is already the rating. League means:
  leading by 1 in P3 costs 5-6.5 pts of attempt share, trailing gains 4-6.5. Team-specific score-state modifiers
  are noise at 82 games; do not build them. Prediction HELD.

## STATUS AT END OF SESSION 2026-09-30 ~05:00Z — nothing found; what is alive; what is next
Alive: only the early soft-book price rule (L-003/L-004, +2.7% CLV confirmed; NHL-L1 puts it on the tape).
Dead today: S48-ML-R6 (confirmation), A-05, A-06, B-01, A-04 (untestable at this cadence).
Real but unmonetisable: A-01 and A-03 — the engine (fixed goalies, actual starter) knows a slice of what Pinnacle
learns between its opener and its close, worth < 1 pt of price; soft-book vig is ~1.5 pts.
Structure: the engine reproduces Pinnacle's puck line AND 3-way from Pinnacle's ML + total (log-loss identical). Any
market Pinnacle hangs is closed to a structure-only edge. Markets only soft books hang are the open door, and no
history exists for them.
Engine defects logged: C-01 (fixed here, to be committed by C-WO1); C-02 totals over-dispersion (5-8%, 5v5 /
between-team correlation); C-03 says team score-state modifiers are not worth building.
NEXT (pre-registered where testable):
1. D-WO1 → D-WO2 walk-forward 2010-2021: the only route to power for subset leads (R8 both-high-penalties, R6) and
   to a real test of the engine on 11 seasons at real closing prices.
2. Forward tape derivatives (branch B): NHL-L1 amendment — log grid-v2 engine fair vs every book for team totals,
   P1 totals / ML, OT yes-no, 3-way on the event_markets tape (2 slots/day, 10 books, WO12), graded nightly; dev =
   2026-27 first half, confirm = second half (needs Jeff's season-role OK). Zero credits.
3. Branch E (live): no historical in-play prices exist and NHL pbp has no wall-clock, so live is forward-only.
   Proposed probe: VM poller for games in the last 6 minutes of the 3rd period with a 1-goal margin — NHL live pbp
   (free) + Odds API event odds (h2h + totals, us region) every 30 s → ~24 credits/game, ~250/night, ~7.5k/month.
   Not before the credit cycle resets (balance ~20k, unverifiable from Cowork: the bridge gets 403 from the API).
