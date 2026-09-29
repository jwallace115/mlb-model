NHL SIM WORK ORDER S-WO4a — the game engine, league-average mechanics only (Cowork, 2026-09-29 18:53Z).
Repo ~/mlb-model.

WHY: the ratings, constants and finishing term are verified and on main
(research/nhl_sim/nhl_sim_s3g_verification_2026-09-29.md).
- This order builds the engine and checks its MECHANICS with league-average teams on the fit season.
- Team ratings, pricing and 2023-24 validation are S-WO4b. The holdout is S-WO5.
- The engine must be able to start from any mid-game state (situation hunter: live pulled-goalie / power-play markets).

TWO items. HARD RULE: if you are about to write "deferred", "NOT TESTED" or "requires a pipeline change", STOP and
explain in chat instead. Do not push a partial item.
- Decisions S32-S33 go in research/nhl_sim/NHL_SIM_DECISION_v1.md, in the same commit as their code.

SETUP
- `git fetch origin && git worktree add ~/mlb-model-nhlsim4 -b nhl/sim-s4 origin/main`
- Copy the gitignored inputs from ~/mlb-model-nhlsim3e:
  - nhl/data/sim/events/
  - nhl/data/sim/ratings/*.parquet
  - nhl/cache/
  - data/odds_archive/nhl/history/
- Check them against nhl/data/sim/ratings/manifest.json and paste the result.
- Commit and push each item: `git push -u origin nhl/sim-s4` the first time, then
  `git pull --rebase --autostash && git push`. Paste `git diff --stat origin/main...HEAD` before each push. Do NOT merge.
- Cost: 0 credits.
- RUNTIME PRE-CHECK: time 20 league-average games at 10,000 sims each and report seconds per game.
  - If it's over 3 s per game, use 2,000 sims per game for Item 2 and say so.
  - Item 2 must finish in under 1 hour. Compute the estimate BEFORE running it.

ITEM 1 (S32) — nhl/sim/engine.py plus the pull-hazard measurement
(a) Pull hazard, measured properly. Add to nhl/sim/build_constants_v5.py a function writing constants_v6.json. v6 is
    v5 plus the new fields; v5 stays untouched. Null control: every v5 field is identical in v6.
    New field: pulled-goalie hazard per second by score diff (-1, -2, -3) and 30-second bin of 3rd-period time
    remaining, measured as pulls / seconds at risk (goalie in, trailing by k, 5v5 or while shorthanded) on fit
    seasons 2021-22 + 2022-23. v2's pull_hazard fields are histograms of pull times, not hazards; do not use them.
(b) engine.py, vectorised over N sims (numpy), stepping 1 second of game clock:
    - Strength state from the penalty clocks (minors 2 min; double minors 4 min; majors 5 min) and pulled goalies.
    - Per second and per team: attempt probability = rate(state, team view) / 3600; the goal probability per attempt
      comes from the inputs.
    - Score effects: 5v5 attempt and xG multipliers from constants_v2 score_effect_* by score diff (clip ±3) and
      period.
    - Home effect: constants_v2 home_attempt_share and home_xg_per_attempt_mult.
    - Penalties: per-team rate per 60 of total time. Type drawn from constants_v2 penalty_shares. A power-play goal
      ends a minor (and one half of a double minor), never a major.
    - Pulled goalie: v6 hazard. Empty-net and extra-attacker rates come from v5 6v5 advantaged/disadvantaged
      goals_per_attempt (empty-net shots are counted in goals, not xG).
    - Overtime: 5 minutes, 3v3 sudden death, with v5 3v3 rates. A penalty in overtime gives 4v3.
    - Shootout: 3 rounds, then sudden-death rounds, conversion from constants_v2. The winner gets +1 goal in the
      final score.
    - Output per sim (arrays):
      - final and regulation score for each team;
      - how it was decided (REG / OT / SO);
      - power-play opportunities and power-play goals per team;
      - empty-net goals per team;
      - attempts per team;
      - pull time.
    - `simulate(inputs, n_sims, seed, start_state=None)`. `start_state` sets period, second, score, the remaining
      penalty clocks per team, and pulled flags.
    - GameInputs is a dataclass holding every rate the engine uses. `league_average_inputs()` builds it from
      constants v5 / v6 / v2. There are NO literal rates in engine.py: grep for them and paste the result.
    - TESTS (nhl/sim/tests/test_engine.py):
      - same seed gives identical output;
      - start_state equal to puck drop gives exactly the same output as start_state=None (same seed);
      - no goals are scored after a sudden-death OT goal;
      - a game tied after 60:00 always gets an OT or SO result;
      - trailing by 1 with 0:30 left and the goalie pulled wins less often than tied at 0:30 (10k sims);
      - home ahead by 3 with 1:00 left wins > 99% of the time.

ITEM 2 (S33) — realism report: league-average teams vs the ACTUAL 2022-23 season (fit, in-sample)
- This checks mechanics, not predictive evidence: the constants were fit on these seasons.
- Simulate league-average home vs away games. Compare with the actual 2022-23 regular season (box scores + event
  tables).
- PRE-REGISTERED bands, fixed now:
  - goals per game (including the shootout goal): within ±3%;
  - share of games tied after regulation: within ±2.0 points;
  - shootout share of all games: within ±1.5 points;
  - power-play opportunities per team-game: within ±5%;
  - power-play goals per team-game: within ±8%;
  - empty-net goals per game: within ±15%;
  - total-goals distribution: max |P_sim(k) - P_actual(k)| <= 0.015 for k = 0..12;
  - share of regulation-decided games won by exactly 1 goal: within ±2.0 points;
  - home win %: within ±2.0 points.
- Report every band as HELD / NOT HELD, with sim value, actual value and the sims used.
- If a band fails, say so plainly. Change nothing in this order to make it pass; calibration belongs to S-WO4b, on
  2023-24 only.

CLOSING
- Write logs/_log_nhl_sim_s4.txt (git add -f):
  - each command: what it RETURNED vs what it MEANS;
  - runtime measured;
  - the grep;
  - the pytest output;
  - bands with HELD / NOT HELD;
  - an accurate NOT DONE list;
  - UNVERIFIED.
- Push. Stop. Do not merge.
