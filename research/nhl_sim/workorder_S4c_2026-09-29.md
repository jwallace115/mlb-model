NHL SIM WORK ORDER S-WO4c — totals from the simulations, finish S42, fit-season calibration (Cowork, 2026-09-29 23:53Z).
Worktree ~/mlb-model-nhlsim4b, branch nhl/sim-s4b. Repo ~/mlb-model.

Read first: CLAUDE.md, research/nhl_sim/nhl_sim_s4b_verification_2026-09-29.md, decision S43, amendments A1 / A2.

TWO items. HARD RULE: if you are about to write "deferred", "NOT TESTED", "NOT DONE" for a required output, or
"requires a pipeline change", STOP and explain in chat instead. Do not push a partial item.
- Every output comes from committed code. Grep for each generator and paste the result.
- Decisions S44-S45 go in the decision doc, in the same commit as their code.
- Commit and push each item (`git pull --rebase --autostash && git push`). Do NOT merge.
- Cost: 0 credits.
- Runtime: the re-price is the same as S41 (~50 min for 2,624 games at 2k sims). Report the estimate before running.

ITEM 1 (S44) — totals priced from the simulations + S42 completed
- price_games.py:
  - store the total-goals distribution per game: columns p_tot_0 .. p_tot_15, where p_tot_15 = P(total >= 15);
  - compute P(over), P(under) and P(push) at Pinnacle's line EXACTLY from that distribution;
  - delete the normal approximation.
- NULL CONTROL: re-price with the same seeds. p_home_win, p_reg_*, p_home_m15, p_away_p15 and mean_total must be
  identical to the S41 parquets for all 2,624 games. Paste the max diff (must be 0).
- Then add to the S42 report script (committed), for 2023-24 (validate) and 2022-23 (fit):
  (a) TOTALS at Pinnacle's line, pushes excluded:
      - log-loss and Brier, engine vs Pinnacle (de-vigged over/under);
      - A1 disagreement coefficient with 90% CI;
      - reliability table in 10 bins.
  (b) MONEYLINE:
      - reliability table in 10 bins (engine and Pinnacle);
      - the favourite / underdog breakdown;
      - the |engine - Pinnacle| buckets (< 2, 2-5, > 5 pts).
      Cowork's numbers are in S43; match them.
  (c) A2 PICKS, moneyline and totals: edge >= 0.04 vs the break-even of the median-of-books price.
      - n, hit %, ROI at the real median price with its SE;
      - by month and by side;
      - confident picks (engine >= 0.70).
      - Descriptive only.

ITEM 2 (S45) — calibration map fit on 2022-23 ONLY, applied ONCE to 2023-24
- PRE-REGISTER in the log BEFORE fitting:
  - map = logistic regression of outcome on logit(p_engine), fit on 2022-23 only (moneyline; and totals over/under
    separately);
  - applied unchanged to 2023-24;
  - prediction: the calibrated engine's 2023-24 moneyline log-loss improves on the raw engine's 0.6647, but still
    does not beat Pinnacle's 0.6567.
- Report for 2023-24 (moneyline and totals):
  - log-loss raw vs calibrated vs Pinnacle;
  - A1 with the calibrated engine.
- If the prediction does not hold, say so. Nothing is re-fit.

CLOSING
- Append "S-WO4c" to logs/_log_nhl_sim_s4b.txt (git add -f):
  - each command: what it RETURNED vs what it MEANS;
  - the null-control max diffs;
  - the generator grep;
  - the pre-registration with HELD / NOT HELD;
  - an accurate NOT DONE list (should be empty);
  - UNVERIFIED.
- Push. Stop. Do not merge.
