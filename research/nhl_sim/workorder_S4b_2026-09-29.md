NHL SIM WORK ORDER S-WO4b — team inputs, game prices, and the 2023-24 prediction test (Cowork, 2026-09-29 21:25Z).
Repo ~/mlb-model.

WHY:
- The engine's league-level mechanics check out: 9 / 9 on 2022-23, 8 / 9 on 2023-24
  (research/nhl_sim/nhl_sim_s4a2_verification_2026-09-29.md).
- Now: team strength in, prices out, and the first real test of whether the engine knows anything the market
  doesn't.
- This is VALIDATION on 2023-24. The holdout (2024-25, 2025-26) stays locked until S-WO5.

THREE items. HARD RULE: if you are about to write "deferred", "NOT TESTED" or "requires a pipeline change", STOP and
explain in chat instead. Do not push a partial item.
- Every output file comes from committed code. Grep for each generator and paste the result.
- Decisions S40-S42 go in the decision doc, in the same commit as their code.

SETUP
- `git fetch origin && git worktree add ~/mlb-model-nhlsim4b -b nhl/sim-s4b origin/main`, then
  `git push -u origin nhl/sim-s4b`.
- Copy the gitignored inputs from ~/mlb-model-nhlsim4:
  - nhl/data/sim/events/
  - nhl/data/sim/ratings/*.parquet
  - nhl/cache/
  - data/odds_archive/nhl/history/
- Check them against manifest.json and paste the result.
- Commit and push each item (`git pull --rebase --autostash && git push`). Paste `git diff --stat origin/main...HEAD`
  before each push. Do NOT merge.
- Cost: 0 credits.
- RUNTIME: time 20 games at 2,000 sims each first.
  - Estimate Item 2 = 2,624 games × that.
  - If the estimate is over 90 minutes, drop to 1,000 sims per game and say so.
  - Report the estimate before running.

ITEM 1 (S40) — nhl/sim/game_inputs.py: team_ratings + goalie_ratings + F(D) → engine TeamMultipliers
For team T against opponent O on date D, using the rows for that game (ratings going INTO the game):
- ev_att_for     = T.ev_att_for_per60 / T.lg_ev_att_for_per60
- ev_att_against = T.ev_att_against_per60 / T.lg_ev_att_against_per60
- ev_q_for       = T.ev_xg_per_att_for / T.lg_ev_xg_per_att_for
- ev_q_against   = T.ev_xg_per_att_against / T.lg_ev_xg_per_att_against
- pp_q_for       = T.pp_xg_for_per60 / T.lg_pp_xg_for_per60
- pk_q_against   = T.pk_xg_against_per60 / T.lg_pk_xg_against_per60
- pen_taken      = T.penalties_taken_per60 / T.lg_penalties_taken_per60
- pen_drawn      = T.penalties_drawn_per60 / T.lg_penalties_drawn_per60
- goalie_save    = 1 - g.gsax_per_att_rating / q
  - g = T's starting goalie (goalie_ratings row for this game and team).
  - q = league xG per non-empty-net attempt, all states, fit seasons. Add it to build_constants_v7.py `--v8` with
    a derivation (null: every other v8 field unchanged).
- finishing      = F(D) from finishing_term.parquet.

Rules:
- A missing row or NaN RAISES. No defaults, no clipping.
- Games whose ratings are NaN (2021-22 opening night only) are excluded and counted.

TESTS:
- (a) All multipliers = 1 gives output identical to league_average_inputs() (same seed).
- (b) A team whose ev_att_for is scaled ×1.1 wins more often (10k sims).
- (c) Ratings for date D are read from the row for that game, not a later one: assert the date matches.

ITEM 2 (S41) — nhl/sim/price_games.py: simulate every 2022-23 and 2023-24 regular-season game
- Per game, write:
  - P(home win, including OT/SO);
  - P(regulation home / tie / away);
  - P(total > line) and P(total = line) at Pinnacle's pre-game line (build_lines.py join; counts must be
    1,156 / 1,138);
  - P(home -1.5) and P(away +1.5);
  - mean total;
  - the sims used.
- Output: nhl/data/sim/prices/season=YYYY.parquet. Gitignore it; its sha goes into manifest.json.
- One fixed seed per game = int(game_id).

ITEM 3 (S42) — the 2023-24 prediction test (validation; the 2022-23 numbers are reported beside it as fit)
PRE-REGISTER in the log BEFORE computing anything:
- the A1 test;
- that no calibration is fit on 2023-24;
- that nothing in Items 1-2 changes after this item runs.

Report, in this order:
(1) Moneyline (home win incl. OT/SO), 2023-24:
    - log-loss and Brier for the engine and for Pinnacle (de-vigged), on the same games;
    - reliability table in 10 bins;
    - A1 incremental-information test: logistic regression
      outcome ~ logit(p_Pinnacle) + (logit(p_engine) - logit(p_Pinnacle)).
      Report the disagreement coefficient and its 90% CI.
      The engine "adds information" only if the lower bound is > 0.
(2) Totals over/under at Pinnacle's line (pushes excluded): the same four things.
(3) CHECK 5 breakdowns for (1) and (2):
    - by month;
    - by games played so far (0-10 / 11-40 / 41+);
    - by favourite / underdog;
    - by |engine - Pinnacle| bucket (< 2, 2-5, > 5 pts).
(4) A2 picks, descriptive only:
    - an A pick = engine prob minus the break-even of the median-of-books price >= 0.04;
    - count, hit rate and ROI at the real median price, by month;
    - also for "confident A picks" (engine >= 0.70).
    - This is validation evidence, not a bet list.
- If the engine does not add information, say so plainly. Tune nothing, and run no second version.

CLOSING
- Write logs/_log_nhl_sim_s4b.txt (git add -f):
  - each command: what it RETURNED vs what it MEANS;
  - runtime;
  - the generator grep;
  - tests;
  - every pre-registration with HELD / NOT HELD;
  - an accurate NOT DONE list;
  - UNVERIFIED.
- Push. Stop. Do not merge.
