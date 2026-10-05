NHL SIM WORK ORDER S-WO4d — pre-game push: totals shape, team modifiers, and a pre-registered search for where the
engine adds information (Cowork, 2026-09-30 01:40Z). Worktree ~/mlb-model-nhlsim4b, branch nhl/sim-s4b.

WHY:
- The engine matches game mechanics, but pre-game it trails Pinnacle on the moneyline and carries no totals
  information (research/nhl_sim/nhl_sim_s4c_verification_2026-09-30.md).
- Jeff (2026-09-30): the engine is a LAYER. Find where it produces something meaningful.
- So this order does three things:
  1. fixes the one known structural gap (the total-goals spread);
  2. adds the information the engine lacks (rest / back-to-back, backup goalie);
  3. tests, pre-registered and FDR-controlled, WHERE the engine's disagreement with the market carries information.
- Anything that survives goes to the locked holdout (S-WO5) unchanged.

Read first: CLAUDE.md, the S4c verification note, decisions S43-S45, amendments A1 / A2.

THREE items. HARD RULE: if you are about to write "deferred", "NOT TESTED", "NOT DONE" for a required output, or
"requires a pipeline change", STOP and explain in chat instead. Do not push a partial item.
- Every output comes from committed code (grep for each generator and paste it).
- Decisions S46-S48 go in the decision doc, in the same commit as their code.
- Commit and push each item (`git pull --rebase --autostash && git push`). Do NOT merge.
- Cost: 0 credits.
- Runtime: re-pricing 2,624 games takes ~50 min (measured in S41 / S44). Report the estimate before each re-price.
  Everything else takes minutes.
- 2024-25 and 2025-26 stay closed.

ITEM 1 (S46) — total-goals spread: game-level pace factor, fit on fit seasons only
- MEASURE first (2021-22 + 2022-23 actual, league-average engine 100k sims, realism_report inputs):
  - variance of total goals per game;
  - P(total >= 7);
  - variance of the goal difference.
  Report actual vs simulated.
  - Cowork's prior (from the realism tables): the engine's upper tail is light. Simulated P(total >= 7) ≈ 0.46 vs
    ≈ 0.48 actual, and engine mean P(over) is 0.449 vs an actual over rate of 0.487 in 2023-24.
- Engine change:
  - one multiplier per simulated game, g ~ Gamma(shape k, scale 1/k) (mean 1), applied to BOTH teams' attempt
    rates in every state;
  - choose k by method of moments so the league-average simulated total-goals variance equals the 2021-23 actual
    variance;
  - write k to constants (build_constants_v7.py `--v8` → a new field, with derivation; every other field
    unchanged);
  - k = infinity (no pace factor) must reproduce the current engine exactly (test).
- PRE-REGISTER (in the log before running):
  - with k fitted, 2022-23 realism holds >= 8 / 9 bands;
  - simulated P(total >= 7) is within 1 point of actual on 2022-23.
- Then run 2023-24 realism ONCE and report it (out-of-sample). If the variance gap is NOT confirmed by the
  measurement, say so, set no k, and skip the engine change. That is an allowed outcome of this item.

ITEM 2 (S47) — team modifiers (amendment A1.3): rest, back-to-back, backup goalie
- Point-in-time features per team-game, from box-score dates and the goalie table:
  - rest days (0 = second of a back-to-back, 1, 2, 3+);
  - backup_start = the starting goalie is NOT the team's most-used starter in that season BEFORE the date.
- ESTIMATE on 2022-23 only:
  - Poisson regression of each team's actual goals (regulation + OT, no shootout goal) on
    log(engine expected goals for that team) as an offset, plus: own rest category, opponent rest category, own
    backup_start, opponent backup_start.
  - The engine's expected goals come from the 2022-23 prices. Add mean_home_goals / mean_away_goals to
    price_games.py; the same seeds must reproduce every existing column (max diff 0).
  - Paste coefficients with SEs.
- Apply as multipliers on the engine: own-rest and own-backup effects scale the team's attempt rates; the
  opponent-side effects scale the team's goal-per-attempt against.
- Re-price 2022-23 and 2023-24.
- A1.3 RULE (pre-registered): a modifier is KEPT only if 2023-24 moneyline log-loss improves with it vs without it.
  Report each modifier's contribution. Anything that fails is dropped before Item 3.

ITEM 3 (S48) — 2023-24 report + a pre-registered regime family
- Full S42 report on the final engine (moneyline and totals):
  - log-loss / Brier vs Pinnacle;
  - A1;
  - reliability;
  - A2 picks at real median prices: n, hit, ROI, SE, by side and month, confident picks, for moneyline AND totals.
    Use Cowork's pick definition: edge = engine prob - 1 / median decimal price >= 0.04.
- REGIME FAMILY, written in the log BEFORE computing:
  - 6 regimes × 2 markets = 12 tests. The 6 regimes:
    (R1) early season (0-10 games played by either team);
    (R2) either team on a back-to-back;
    (R3) either team starting a backup goalie;
    (R4) |engine - Pinnacle| > 5 pts;
    (R5) the engine's pick is the underdog;
    (R6) both starting goalies rated above league average (totals) or below average (moneyline).
  - For each: the A1 disagreement coefficient with 90% CI, and the A2 ROI at real prices.
  - Benjamini-Hochberg at 10% across the 12 p-values (one-sided, coefficient > 0).
  - SURVIVORS are the only candidates carried to the holdout, unchanged. No survivor is an allowed and informative
    outcome.
- The totals under-lean: report engine mean P(over) vs actual over rate after Items 1-2.

CLOSING
- Append "S-WO4d" to logs/_log_nhl_sim_s4b.txt (git add -f):
  - each command: what it RETURNED vs what it MEANS;
  - the null controls;
  - the generator grep;
  - every pre-registration with HELD / NOT HELD;
  - an accurate NOT DONE list;
  - UNVERIFIED.
- Push. Stop. Do not merge.
