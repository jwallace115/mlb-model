NHL SIM WORK ORDER S-WO3d — tests in the repo, goalie code restored, constants_v3 (Cowork, 2026-09-29 15:47Z).
Repo ~/mlb-model.

WHY: research/nhl_sim/nhl_sim_s3c_verification_2026-09-29.md.
- The S18 tests were never committed (Cowork ran them; they pass and can fail).
- The goalie rating code was deleted but its stale parquet is still used.
- constants_v2 averages both sides of uneven-strength states: the PP side is ~71 attempts/60, but the constant says
  41.3.

This order is deliberately SMALL: three items. Do all three. "Deferred" is not an allowed outcome for any of them;
if one truly cannot be done, STOP and say why, before starting the next.
Decisions S20-S22 go in research/nhl_sim/NHL_SIM_DECISION_v1.md, each in the SAME commit as its code.

SETUP
- Worktree ~/mlb-model-nhlsim3r, branch nhl/sim-s3r.
- Run `git fetch origin && git rebase origin/main`. The duplicate verification commit should drop out.
- Then `git diff --stat origin/main...HEAD` must list ONLY:
  - nhl/sim/**
  - nhl/data/sim/ratings/carryover_w.json
  - research/nhl_sim/NHL_SIM_DECISION_v1.md
  - logs/_log_nhl_sim_s3.txt
  Paste it. If anything else is listed, fix the history before continuing.
- Commit and push each item (`git pull --rebase --autostash && git push`). Do NOT merge to main.
- Cost: 0 credits.
- Runtime: a ratings rebuild from team_game_stats.parquet takes ~1.4 s (Cowork measured). The whole order is minutes.

ITEM 1 (S20) — the S18 tests, committed and run
- Port research/nhl_sim/cowork_checks/truncation_check_2026-09-29.py into nhl/sim/tests/test_ratings_s18.py, reading
  the cache. The check:
  - 20 dates in 2023-24, seed 20260929;
  - drop the rows after D;
  - corrupt D's own stats (×7 + 3);
  - ratings on D must equal the full run to 1e-12.
- Parametrise it over three versions of the code:
  (a) the current ratings.py — must PASS;
  (b) a MUTANT built inside the test by moving the six `tc[...] +=` lines above `if tc["n"] == 0:` — must FAIL
      (Cowork got 20/20 dates failing, max diff 3.30);
  (c) e17ace021's compute_pit_ratings, loaded from `git show e17ace021:nhl/sim/ratings.py` into a temp module —
      must FAIL (Cowork: 20/20, max 0.010).
  Mark (b) and (c) as expected failures by asserting that the difference is > 1e-6. They are NOT xfail/skip.
- STARTER test: the rated goalie must equal the box score's `playerByGameStats.goalies[].starter` in > 99% of
  team-games (Cowork: 99.94%).
- Run `pytest nhl/sim/tests -q`. Paste the full output and the exit code.

ITEM 2 (S21) — goalie ratings back in ratings.py; no literal weights
- Restore build_goalie_ratings, from 3fa82ecce, with the S16 structure:
  - per season;
  - the carried-over prior is the season-long shrink target;
  - K from split-half on 2021-23.
- Measure goalie w with measure_goalie_carryover() (2021 -> 2022 only). Write it to carryover_w.json with its
  derivation, replacing the literal 0.3.
- Remove every `.get(..., 0.5)` fallback. A missing weight must raise. Grep for literal weights and paste the result.
- Rebuild goalie_ratings.parquet and team_ratings.parquet. Add the goalie ratings to the Item 1 truncation test.
- CHECK 3: write nhl/data/sim/ratings/manifest.json (committed, small) with:
  - sha256 of ratings.py;
  - sha256 of carryover_w.json;
  - sha256 of each output parquet;
  - row counts.

ITEM 3 (S22) — constants_v3: each side of uneven-strength states measured separately
- New nhl/data/sim/constants_v3.json, same fit seasons as v2 ([2021, 2022]); v2 stays untouched.
- For 5v4, 5v3, 4v3, 6v5, 6v4 (and their mirrors): attempts per 60 and xG per attempt, SEPARATELY for:
  - the side with more skaters;
  - the side with fewer skaters.
- Minutes per team-game in each state, including 5v5 and 4v4.
- Keep the derivation strings (numerator, denominator, units).
- NULL CONTROLS (paste each):
  (a) advantaged-side rate + disadvantaged-side rate = 2 × the v2 value, to 1e-9, for every uneven state (this is
      arithmetic);
  (b) the 5v5, 4v4 and 3v3 values equal v2 to 1e-9.
- PRE-REGISTER, in the log before looking:
  - 5v4 PP-side attempts/60 between 65 and 80;
  - 5v4 short-handed side between 8 and 20;
  - PP-side xG per attempt > the v2 averaged 0.0945;
  - PP minutes per team-game between 4.5 and 6.0.
  If any does not hold, say so plainly. Change nothing to make it hold.
- Do NOT re-run sanity_check.py in this order. The 2023-24 mean-total bar is no longer blind (see the
  verification note). The next order uses v3.

CLOSING
- Append "S-WO3d" to logs/_log_nhl_sim_s3.txt (git add -f):
  - each command: what it RETURNED vs what it MEANS;
  - the pytest output and exit code;
  - the grep output;
  - the pre-registrations with HELD / NOT HELD;
  - NOT DONE (should be empty);
  - UNVERIFIED.
- Push. Stop. Do not merge.
