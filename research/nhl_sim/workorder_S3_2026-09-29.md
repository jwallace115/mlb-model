NHL SIM — WORK ORDER S3: point-in-time team and goalie ratings, reliability, and a ratings-only sanity check
(written 2026-09-29 by Cowork after verifying S-WO2). Repo ~/mlb-model.

Read first: CLAUDE.md; research/nhl_sim/NHL_SIM_DECISION_v1.md (S1-S9 — S2 fixes the seasons and the holdout
lock); research/nhl_sim/nhl_sim_s2_verification_2026-09-29.md.

SETUP
- After Jeff merges nhl/sim-s1: new worktree `git worktree add ~/mlb-model-nhlsim3 -b nhl/sim-s3 origin/main`.
  Rebuild the gitignored event tables there with the committed generators (nhl/sim/build_events.py on
  nhl/cache/pbp — copy or symlink the cache from ~/mlb-model-nhlsim1/nhl/cache/pbp) and report their sha256 vs the
  S-WO2 tables (must be identical; that is the reproducibility check).
- Touch only nhl/sim/, nhl/sim/tests/, nhl/data/sim/, research/nhl_sim/. Commit AND push each item before the next.
  Each item appends its `### S<n>` entry (expected S10, S11, S12) in the same commit.
- HOLDOUT: 2024-25 and 2025-26 may be RATED (ratings roll forward through them) but NOTHING in this order compares
  anything to 2024-25 or 2025-26 outcomes or prices. Evaluation uses 2022-23 (fit) and 2023-24 (validate) only.
- Tests import production code on real fixtures; each must FAIL on a stated mutation that you run. Pre-registered
  bands are written before the numbers; HELD / NOT HELD; tune nothing to rescue one. A red is reported red.
- Runtime: local compute over ~560k attempts and 6,560 games — minutes. Credits 0.

ITEM 1 (S10) — team ratings (nhl/sim/ratings.py -> nhl/data/sim/ratings/team_ratings.parquet, one row per team per
game, using ONLY games strictly before that game's date).
- Stats, each FOR and AGAINST, per 60 of the relevant state: 5v5 unblocked attempts; 5v5 xG v2 per attempt; PP
  attempts and xG per attempt (per 60 of own PP time); PK attempts and xG against (per 60 of own PK time); penalties
  taken and drawn per 60; 5v5 attempts and xG per attempt score-adjusted with the constants_v2 multipliers (so a
  team that led a lot is not rated as a poor shooting team).
- Stabilisation measured, not assumed: on 2021-22 + 2022-23 only, split-half reliability (odd vs even games) of each
  stat as a function of games played; the regression-to-mean constant K = n(1-r)/r at the measured r. Rating =
  (team total + K x league mean) / (team n + K). Season carry-over: the prior season's final rating regressed to
  the mean with a weight measured on the fit seasons (report it); the first game of 2021-22 starts at league mean.
- PRE-REGISTER: split-half r of 5v5 attempt share at 40 games per half > 0.60; of 5v5 xG per attempt FOR at 40
  games < attempt share's r; of PP xG per attempt at a full season < 0.40.
- NULL CONTROL (the leakage test): recompute the ratings for 2023-24 games after deleting every game on or after
  each game's date — identical to the stored value to 1e-12 for 100% of rows. Test must fail if the "strictly
  before" filter becomes "on or before".

ITEM 2 (S11) — goalie ratings and the league finishing term (same file set; nhl/data/sim/ratings/goalie_ratings.parquet).
- Goalie: goals saved above xG v2 per unblocked non-empty-net attempt faced (all strengths), point-in-time, shrunk
  with a K measured by split-half reliability on the fit seasons; career carry-over across seasons with a measured
  regression weight; a goalie with no history starts at the mean of goalies with < 10 prior starts (measured).
- The starter for each game = the goalie on the ice for the game's first shot against (from the event table);
  report agreement with the box-score starter flag.
- League finishing term: league goals / xG v2 over the previous 30 days of games, strictly before the date
  (2025-26 ran 6.8% above 1.0 — the engine needs this), reported by month for all five seasons.
- PRE-REGISTER: goalie GSAx/attempt split-half r at 20 starts per half < 0.30 (goaltending is noisy); starter
  agreement with the box score > 99%.
- NULL CONTROL: the same truncation test as item 1, on 2023-24 goalies.

ITEM 3 (S12) — ratings-only sanity check, fit + validate seasons only (no engine yet).
- For each game compute the ratings' implied expected goals per team: 5v5 attempts per 60 (team FOR x opponent
  AGAINST / league) x xG per attempt (same form) x average 5v5 minutes, plus PP/PK the same way with average PP time,
  times the goalie factor and the league finishing term. Report, for 2022-23 and 2023-24 separately:
  corr(implied goal diff, actual goal diff); corr(implied goal diff, logit of Pinnacle's de-vigged home probability);
  corr(implied total, Pinnacle's total line); mean implied goals vs actual.
- PRE-REGISTER: corr with Pinnacle's logit > 0.60 and corr of totals > 0.30 in 2023-24; mean implied total within
  +/- 3% of actual in 2023-24. If these fail, say so — the engine is not built on ratings that do not track the
  market.
- NULL CONTROL: shuffle the team labels within each date and recompute — correlations near 0.

CLOSING
- logs/_log_nhl_sim_s3.txt (`git add -f`): RETURNED vs MEANS; every null control with counts; every pre-registration
  HELD / NOT HELD with its number; the measured K and carry-over weights; NOT DONE; UNVERIFIED; commit shas; ONE
  merge command. Stop — Cowork verifies before S-WO4 (the engine).
