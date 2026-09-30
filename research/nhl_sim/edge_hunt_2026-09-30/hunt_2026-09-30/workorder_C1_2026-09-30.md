NHL SIM EDGE HUNT — WORK ORDER C-WO1: fix the swapped goalie ratings, prove it with a test that fails on the old
code, re-price 2022-24, re-run the prediction report and the regime family, commit the S46-S48 generators
(Cowork, 2026-09-30). Worktree ~/mlb-model-nhlsim4b, branch nhl/sim-s4b (continues; do NOT merge).

WHY: nhl/sim/game_inputs.py (S40) sets `h_mult.goalie_save = 1 - a_gsax / q` and `a_mult.goalie_save = 1 - h_gsax / q`.
The engine applies `opp.goalie_save` when the OTHER team attacks (engine.py, `gpa = gpa * opp.goalie_save *
me.finishing`), so `home.goalie_save` must be the HOME goalie's factor. As committed, each team's scoring is scaled
by its OWN goalie. Cowork confirmed on the committed prices: corr(engine ML logit, home−away goalie rating) −0.090 /
−0.052 (2022-23 / 2023-24) vs Pinnacle +0.370 / +0.332. Every S41-S48 number and the CLV test came from this
object. Cowork's fixed re-price (same seeds, same sims) gives: 2023-24 ML log-loss 0.6646 (was 0.6647; Pinnacle 0.6567), A1 −0.052 [−0.637, 0.534], goalie-diff t −1.76; 2022-23 (fit) 0.6594 (was 0.6669), goalie t −0.47, A1 0.448 [−0.066, 0.963]. So the fix is real, and it does not make the pre-game engine beat Pinnacle.
Ledger: project doc claude/nhl_sim_edge_hunt_ledger.md, entry C-01.

Read first: CLAUDE.md (WORK ORDERS), S40-S48 in research/nhl_sim/NHL_SIM_DECISION_v1.md, the S4d verification note,
research/nhl_sim/cowork_checks/s48_complete/s48_complete.py.

FOUR items. Commit AND push each. HARD RULE: no "deferred"; STOP and say so in chat instead. Cost 0 credits.
Decisions S49-S52 in the decision doc in the same commit as the code.

ITEM 1 (S49) — the fix and a test that catches it
- Test FIRST, in nhl/sim/tests/test_game_inputs.py: build league-average inputs, give the HOME goalie a rating of
  +0.02 gsax/att (i.e. a better goalie) through the same code path the real ratings use (a two-row goalie_ratings
  frame), simulate 20,000 sims, and assert mean AWAY goals fall by at least 10% vs all-ones while mean HOME goals
  change by less than 2%. Run it on the committed code: it must FAIL (paste the failing numbers). Then swap the two
  assignments in game_inputs.py and run again: must PASS. Both outputs go in the log.
- Null control: all-ones multipliers still reproduce league_average_inputs exactly (existing test).

ITEM 2 (S50) — re-price 2022-23 + 2023-24 with the fix
- python3 nhl/sim/price_games.py (2,000 sims, seed = game_id; ~50 min measured in S41). Before running, print the
  runtime estimate. Keep the old parquets as nhl/data/sim/prices/season={2022,2023}_swapped.parquet (gitignored,
  sha in the manifest) so the two objects stay comparable.
- Null control: with the swap put back (git stash the fix), the first 20 games of 2022-23 must reproduce the OLD
  parquet to max diff 0 (Cowork's re-pricer did: 0.0 on every column).
- Cowork's pre-registration for this fix (ledger C-01) was: 2023-24 ML log-loss improves by ≥ 0.002 from 0.6647;
  goalie-diff |t| < 1.64; A1 rises above 0.376. RESULT on Cowork's run: 2022-23 held on all three; 2023-24 held on
  NONE (0.6646, t −1.76, A1 −0.05). Report it that way. Your numbers must match Cowork's parquet
  (research/nhl_sim/edge_hunt_2026-09-30/prices_fixed_goalie_2022_2023_cowork.parquet, sha256 3bbf36f5…) to 4
  decimals on p_home_win for every game (same seeds) — if they do not, STOP: something else differs.

ITEM 3 (S51) — the reports on the fixed engine, and the generators that never got committed
- nhl/sim/prediction_report.py on the new prices (ML + totals, A1, reliability, |diff| buckets, A2 at real median
  prices with edge = engine − 1/median decimal ≥ 0.04, by side and month).
- Commit as code: the S46 variance measurement (research/nhl_sim/edge_hunt_2026-09-30/ or nhl/sim/, name it
  `measure_total_variance.py`), the S47 Poisson fit with the PER-TEAM offset from mean_home_goals /
  mean_away_goals (now in the prices), and cowork_checks/s48_complete/s48_complete.py (unchanged, plus a
  --prices argument). Each must reproduce the number in its decision entry when run on the swapped prices, and
  print its number on the fixed prices.
- S47 A1.3 rule stays pre-registered: a B2B modifier is kept only if 2023-24 ML log-loss improves with it. Report
  the coefficients on the fixed engine; do NOT apply them in this order (that is a separate re-price).

ITEM 4 (S52) — the 16-regime family on the fixed engine, one run
- s48_complete.py --prices <fixed 2023-24>, plus R7 (both teams' 5v5 attempt rate > 1.02 × league) and R8 (both
  teams' penalties taken > 1.05 × league) × ML / totals = 16 tests, BH 10% within the family; the 2022-23 view
  descriptive only. Cowork ran the same family on its fixed prices (hunt_2026-09-30/a02_regimes_fixed.csv): NO SURVIVORS within the
  family (min p 0.0064, ML R6, threshold 0.0063). Your table must match it to 3 decimals.
- Survivors, if any, are candidates for the hunt ledger; nothing is carried to 2024-25 by this order.

CLOSING
- Append "C-WO1" to logs/_log_nhl_sim_s4b.txt (git add -f): RETURNED vs MEANS per command, every null with its
  numbers, every pre-registration HELD / NOT HELD, NOT DONE, UNVERIFIED. Push. Stop. Do not merge.
