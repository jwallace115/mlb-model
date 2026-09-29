NHL SIM — WORK ORDER S3r: repair the ratings (no future data, season boundaries, the leakage test), then run the
sanity check as specified (written 2026-09-29 by Cowork after verifying S-WO3). Repo ~/mlb-model.

Read first: CLAUDE.md (WORK ORDERS: "A diff is not evidence that code runs", "Measure, do not assume"),
research/nhl_sim/NHL_SIM_DECISION_v1.md, research/nhl_sim/nhl_sim_s3_verification_2026-09-29.md (the seven defects,
with line numbers), research/nhl_sim/amendment_A1_2026-09-29.md (outcomes first; Pinnacle is a floor, never a target).

SETUP
- Do NOT merge or reuse branch nhl/sim-s3 (cut from pre-rebase history; see the verification note). New worktree:
  `git worktree add ~/mlb-model-nhlsim3r -b nhl/sim-s3r origin/main`, then
  `git cherry-pick 97ded6c11 2c6cad87a 99556de37`. Report that `git diff --stat origin/main` touches only nhl/sim/,
  research/nhl_sim/ and logs/_log_nhl_sim_s3.txt.
- Rebuild the gitignored event tables with the committed generators (copy nhl/cache/pbp from ~/mlb-model-nhlsim1) and
  confirm the 15 sha256 match S-WO2. Copy data/odds_archive/nhl/history/ from ~/mlb-model (gitignored) for item 3.
- Touch only nhl/sim/, nhl/sim/tests/, nhl/data/sim/, research/nhl_sim/. Commit AND push each item before the next,
  each with its S-entry appended at the END of the decision log (expected S13, S14, S15). S13 states which S10-S12
  claims were wrong. S10-S12 are not edited.
- Tests import production code on real fixtures; every new test must FAIL on 97ded6c11/2c6cad87a (run it and report).
  Pre-registrations are written before looking; HELD / NOT HELD; tune nothing to rescue one.
- HOLDOUT: 2024-25 and 2025-26 may be rated; nothing is compared to their outcomes or prices, and nothing
  computed from them may enter a rating of an earlier game.
- Runtime: minutes (local). Credits: 0.

ITEM 1 (S13) — ratings rebuilt point-in-time (nhl/sim/ratings.py).
- Shrinkage target for a game on date D = the league mean of the same stat over all games strictly before D in that
  season. Before 10 league games have been played, the previous season's final league mean. For 2021-22's opening
  games, the 2021-22 first-10-days mean, reported and flagged as the only warm-up exception.
- Per-season accumulation. Carry-over: each team starts a season at
  (prior-season final rating) x w + league mean x (1 - w). w is measured on the 2021-22 -> 2022-23 transition ONLY:
  the slope of 2022-23 full-season rate on 2021-22 full-season rate across teams, per stat. Report w per stat.
- Stats in the table (FOR and AGAINST): 5v5 attempts per 60 and xG per attempt, score-adjusted with constants_v2's
  multipliers; PP attempts and xG per attempt per 60 of own PP time; PK the same against; penalties taken and drawn
  per 60. K per stat from split-half reliability on 2021-22 + 2022-23 only (report r and K per stat).
- Goalies: the same fixes (prior = league mean strictly before D; career carry-over with a measured w). Starter =
  goalie on the ice for the first shot against; report agreement with the box-score starter flag (pre-registered
  > 99%).
- NULL CONTROLS (run, with counts):
  (a) truncation — for every 2023-24 game, recompute its team and goalie ratings from a table with every game on or
      after its date deleted; identical to 1e-12 on 100% of rows;
  (b) mutation — change "strictly before" to "on or before": (a) must fail; show the failure count;
  (c) a test that a 2022-23 rating does not change when every 2024-25 and 2025-26 row is deleted (catches the
      all-season prior of defect 1). It must fail on 97ded6c11.

ITEM 2 (S14) — league finishing term, point-in-time.
- goals / xG v2 on non-empty-net attempts over the 30 days strictly before D (all teams). Reported by month for all
  five seasons, as xG/goals AND goals/xG with the label stated.
- Fix the label: the S14 entry states that S9's "Goals/xG 2025=1.068" was xG/goals (2025-26 goals came in ~6.8%
  BELOW xG).

ITEM 3 (S15) — the S12 sanity check, as S-WO3 specified it (nhl/sim/sanity_check.py).
- Implied goals per team = 5v5 part (attempts per 60 from team FOR x opponent AGAINST / league, x xG per attempt the
  same way, x average 5v5 minutes) + PP part + PK part (same form, with average PP/PK minutes from constants_v2), x
  the opposing goalie factor, x the league finishing term. Empty-net and 3-on-3 goals are added as league averages
  per game from constants_v2 (stated).
- Pinnacle: import the join and de-vig from research/layers/nhl_edge_hunt_2026-09-29/phase3_lines/build_lines.py
  ((ET date, home, away); last snapshot strictly before puck, <= 6 h). Report the match count per season.
- Report for 2022-23 and 2023-24 separately:
  - corr(implied goal diff, actual goal diff) — FIRST, per A1.1;
  - corr(implied goal diff, logit Pinnacle home);
  - corr(implied total, Pinnacle total line);
  - mean implied total vs actual.
- The S12 bars STAND as written (Pinnacle logit > 0.60, totals > 0.30, mean total within +/-3% in 2023-24). This is
  the first run of the formula S-WO3 specified. The 5v5-only run is reported as a deviation. Whatever this run gives
  is final for S12: no reweighting, no second formula.
- NULL CONTROL: team labels shuffled within date -> correlations near 0.

CLOSING
- logs/_log_nhl_sim_s3.txt (append "S-WO3r", `git add -f`): RETURNED vs MEANS; every null control with counts; every
  pre-registration HELD / NOT HELD with its number; w and K per stat; NOT DONE; UNVERIFIED; commit shas; ONE merge
  command (a branch whose diff vs origin/main touches only the allowed paths). Stop — Cowork verifies before
  S-WO3b (A1/A2 decisions + team modifiers) and S-WO4 (the engine, built to start from any game state).
