NHL SIM WORK ORDER S-WO3c — finish the ratings (Cowork, 2026-09-29 14:43Z). Repo ~/mlb-model.

WHY: research/nhl_sim/nhl_sim_s3r_verification_2026-09-29.md. S-WO3r fixed the leakage but left these undone:
- carry-over (measured w unused; hardcoded 0.5; applied to game 1 only);
- the truncation and mutation tests;
- PP/PK/penalty ratings and score adjustment;
- a point-in-time finishing term;
- the full S15 formula.
Decisions S16-S19 go in research/nhl_sim/NHL_SIM_DECISION_v1.md, each IN THE SAME COMMIT as its code. Also add one
line under S13 and one under S14 pointing to this correction.

Read first: CLAUDE.md (ENVIRONMENT TRAPS, secrets), the verification note above, amendment_A1_2026-09-29.md.

SETUP
- Continue in worktree ~/mlb-model-nhlsim3r on branch nhl/sim-s3r. First run
  `git fetch origin && git rebase origin/main`.
- Do NOT merge to main.
- Commit and push each item before starting the next (`git pull --rebase --autostash && git push`).
- Holdout (2024-25, 2025-26) outcomes stay closed. The only use of those seasons is the deletion test, which drops
  them.
- Cost: 0 Odds API credits. Everything is local data.

RUNTIME (measure, do not assume)
- build_game_stats() re-filters every table per game with row-wise .apply. That is most of S-WO3r's ~30 minutes.
- ITEM 1 first vectorises it (groupby on game_id / strength) and caches the output to
  nhl/data/sim/ratings/team_game_stats.parquet (gitignored).
- Report the before/after wall time. Tests then read the cache.
- NULL CONTROL: the new table must equal the old function's output on every existing column (max abs diff < 1e-9,
  same row count 12,850). If not, STOP.

ITEM 1 (S16) — carry-over that is actually used
- Measure w on 2021->2022 only, per stat, for:
  - 5v5 att for / against per 60;
  - xG per attempt for / against;
  - goalie GSAx per attempt (same method).
  Write them to nhl/data/sim/ratings/carryover_w.json (committed, small) with the derivation.
  The code READS this file. No literal w anywhere (grep for it and report).
- Season-start prior for a team = w × last season's final shrunk rating + (1 - w) × league prior.
- This prior is the SHRINK TARGET for the whole season:
  rating(D) = (in-season total before D + K × prior) / (n + K).
  It is not a game-1 value. Same structure for goalies, with the career prior as target.
- PRE-REGISTER (write in the log before running):
  (a) In 2023-24, the SD across teams of the att_for rating at n_prior_games=1 is >= 0.9 × its SD at n_prior_games=0.
      Today it is 1.42 vs 2.05 (0.69).
  (b) corr(implied goal diff, actual goal diff) in 2022-23 fit rises from 0.308 by +0.005 to +0.03. Validate is
      reported, not predicted.
- TEST (nhl/sim/tests/test_ratings_s16.py): adding +5 to one team's previous-season final attempts-for must change
  that team's rating at n_prior_games = 1 and 10.
  - It must FAIL on 3fa82ecce's ratings.py. Run it against a copy of that file and paste the failing output.
  - It must pass on the new code.

ITEM 2 (S17) — PP/PK, penalties, score-adjusted 5v5
- Rate each of these, point-in-time, per season, with the ITEM 1 carry-over:
  - team PP xG per 60 of own PP time;
  - PK xG against per 60 of PK time;
  - penalties taken per 60;
  - penalties drawn per 60 (from events/penalties.parquet; drop the placeholder line).
- 5v5 score adjustment: weight each 5v5 attempt and xG by 1 / constants_v2 score_effect_*_mult for its
  (score diff clipped ±3, period).
- Split-half r and K for every stat, on 2021-23 only.
- PRE-REGISTER: the score-adjusted 5v5 attempt-share r >= the unadjusted r (0.907).
  If it does not hold, say so plainly and keep the unadjusted version. Do not tune anything to rescue it.

ITEM 3 (S18) — null-control tests that can fail (nhl/sim/tests/test_ratings_s18.py, reading the cache)
- (a) TRUNCATION:
  - pick 20 dates in 2023-24 with a fixed seed;
  - for each date D, rebuild ratings from team_game_stats rows with date < D only;
  - every rating on date D must equal the full-run rating to 1e-12 (teams and goalies).
- (b) MUTATION: patch the loop to update the running totals BEFORE recording the rating. Test (a) must then FAIL.
  Run it and paste the failing output.
- (c) Run the existing holdout-deletion test against e17ace021's ratings.py, loaded as a temp module, and paste the
  failure. "Verified by reading source" does not count.
- (d) STARTER: the rated goalie must match the box-score `playerByGameStats.goalies[].starter` flag in > 99% of
  team-games. Cowork measured 99.94%. Report the mismatches.
- Keep the season-reset test, but make it build from the code, not read the saved parquet.

ITEM 4 (S19) — point-in-time finishing term + S15 re-run with the full formula (ONE run)
- Per-game column: league goals / xG over the 30 days strictly before D (non-empty-net). Before 30 days of
  in-season data, use the previous season's last 30 days.
- Implied goals per team:
  - 5v5: rating-based attempts × xG per attempt, using score-adjusted ratings.
  - PP: expected PP opportunities = league opportunities × (team drawn / league) × (opponent taken / league).
    Multiply by the league mean seconds per opportunity, then by team PP xG/60 × opponent PK xGA/60 / league.
    All league values are measured strictly before D in-season, with the previous season's value in the first
    10 days.
  - Both teams' xG × the finishing term.
  - Goalie: × (1 - rating / league xG per non-empty-net attempt, strictly before D). Replaces the 30× factor.
  - Empty-net and 3v3 OT goals: league per-game averages measured strictly before D. Replaces the literal 0.35.
- The S12 bars stand as written and are not changed:
  - corr(implied goal diff, Pinnacle logit) > 0.60;
  - corr(implied total, Pinnacle total) > 0.30;
  - mean implied total within ±3% of actual in 2023-24.
- Report corr with ACTUAL goal diff and totals first. Put Pinnacle's own corr on the same games beside it
  (Cowork measured Pinnacle 0.333 / 0.287 for goal diff; engine 0.292 / 0.258).
- Shuffled null control (shuffle within date) as before.
- If a bar fails, say so plainly. Do not re-run with changed constants.
- Import the Pinnacle join from
  research/layers/nhl_edge_hunt_2026-09-29/phase3_lines/build_lines.py logic, or diff against it: match counts must
  be 1,156 / 1,138.

CLOSING
- Append an "S-WO3c" section to logs/_log_nhl_sim_s3.txt (git add -f):
  - each command: what it RETURNED vs what it MEANS;
  - the pre-registrations with HELD / NOT HELD;
  - the pasted failing outputs;
  - NOT DONE;
  - UNVERIFIED.
- Push. Stop. Do not merge. Cowork verifies from the files.
