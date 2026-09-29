NHL SIM WORK ORDER S-WO3e — constants_v4 (goals vs xG named apart, pooled PP) + PP/PK/penalty ratings
(Cowork, 2026-09-29 16:30Z). Repo ~/mlb-model.

WHY: research/nhl_sim/nhl_sim_s3d_verification_2026-09-29.md.
- The S-WO3d content has been squashed onto main.
- Still open:
  - constants call goals-per-attempt "xg_per_attempt";
  - the PP split uses home power plays only;
  - goalie ratings are not in the truncation test;
  - the mutant is a re-implementation rather than a patch of the real file;
  - PP/PK/penalty ratings and the score adjustment were never built.

TWO items. Both must be done. "Deferred" is not an allowed outcome; if an item cannot be done, STOP and say why.
Decisions S23-S24 go in research/nhl_sim/NHL_SIM_DECISION_v1.md, in the SAME commit as their code.

SETUP
- `git fetch origin && git worktree add ~/mlb-model-nhlsim3e -b nhl/sim-s3e origin/main`
- Copy the gitignored inputs from ~/mlb-model-nhlsim3r (cp -R):
  - nhl/data/sim/events/
  - nhl/data/sim/ratings/team_game_stats.parquet, team_ratings.parquet, goalie_ratings.parquet
  - nhl/cache/
  - data/odds_archive/nhl/history/
- Check the copied parquets' sha256 against nhl/data/sim/ratings/manifest.json on main. Paste the result. If any
  differ, STOP.
- Paste `git diff --stat origin/main...HEAD` before each push. It must list only:
  - nhl/sim/**
  - nhl/data/sim/constants_v4.json
  - nhl/data/sim/ratings/{carryover_w,manifest}.json
  - the decision doc
  - logs/_log_nhl_sim_s3.txt
- Commit and push each item (`git pull --rebase --autostash && git push`). Do NOT merge to main.
- Cost: 0 credits.
- Runtime: a ratings rebuild takes ~1.4 s; xG-scoring all shots once is about a minute. Measure and report.

ITEM 1 (S23) — constants_v4 and the test fixes
- New nhl/data/sim/constants_v4.json, fit seasons [2021, 2022]. constants_v3 stays on disk and is marked superseded
  in S23.
- For EVERY state (5v5, 4v4, 3v3, and both sides of 5v4, 5v3, 4v3, 6v5, 6v4), give:
  - attempts per 60;
  - `goals_per_attempt`;
  - `xg_per_attempt` = the xg_v2 probability summed over attempts / attempts;
  - their ratio, goals / xG;
  - derivation strings.
- Uneven states: POOL both orientations. Power-play side = home in home-5v4 + away in home-4v5; the same for every
  uneven state.
- Minutes per team-game per state, both orientations pooled.
- NULL CONTROLS (paste each):
  (a) Restricted to home-5v4 only, the new code reproduces v3's 5v4 numerators and denominators exactly.
  (b) Every pooled numerator = home part + away part (integers, exact).
  (c) The 5v5 attempt rate equals v3 exactly.
- PRE-REGISTER (in the log before running): goals / xG is between 0.95 and 1.05 for 5v5 and for the pooled 5v4 power
  play in the fit seasons. xg_v2 was fit on 2021-23, so this is an in-sample calibration check. If it fails, the xG
  scoring in the constants code is wrong: STOP.
- TESTS (nhl/sim/tests/test_ratings_s18.py):
  - Add goalie ratings to the truncation test. Same 20 dates; drop the rows after D and corrupt D's shots; goalie
    ratings on D must equal the full run to 1e-12.
  - Replace the hand-written mutant with a patch of the REAL ratings.py source. Read the file, move the exact
    six-line `tc[...] +=` block above `if tc["n"] == 0:`, exec it as a temp module, and assert the diff is > 1e-6.
  - If the six-line block is not found, the test must FAIL, not skip. Cowork did exactly this edit in S-WO3c.
- Run `pytest nhl/sim/tests -q -rs` and paste the output. It should show 0 skipped on the Mac.

ITEM 2 (S24) — PP/PK/penalty ratings and the score-adjusted 5v5
- Point-in-time team ratings, per season, with the S16 structure (the carried-over prior is the season-long shrink
  target; w measured 2021→2022 only and written to carryover_w.json), for:
  - PP xG for per 60 of own PP time;
  - PK xG against per 60 of PK time;
  - penalties taken per 60;
  - penalties drawn per 60.
  Use the pooled-orientation definitions from Item 1.
- Split-half r and K for each, on 2021-23 only. Report them; no threshold.
- 5v5 score adjustment: weight each 5v5 attempt and its xG by 1 / constants_v2 score_effect_*_mult for its score diff
  (clipped ±3) and period. Keep the unadjusted columns alongside.
- PRE-REGISTER: the score-adjusted 5v5 attempt-share split-half r >= the unadjusted r (0.907).
  - If it holds, the adjusted version becomes the rated one.
  - If it does not, say so plainly and keep the unadjusted one. Tune nothing.
- Add every new rating to the truncation test (it must still pass at 1e-12).
- Rebuild team_ratings.parquet and update manifest.json.
- Do NOT run sanity_check.py; the formula run is S-WO3f.

CLOSING
- Append "S-WO3e" to logs/_log_nhl_sim_s3.txt (git add -f):
  - each command: what it RETURNED vs what it MEANS;
  - the sha check;
  - the diff --stat outputs;
  - the null controls;
  - the pytest output;
  - the pre-registrations with HELD / NOT HELD;
  - NOT DONE (it must be accurate);
  - UNVERIFIED.
- Push. Stop. Do not merge.
