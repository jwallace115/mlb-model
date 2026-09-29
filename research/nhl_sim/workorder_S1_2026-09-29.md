NHL SIM — WORK ORDER S1: play-by-play, event tables, own xG, measured league constants (written 2026-09-29 by Cowork,
NHL chat). Repo ~/mlb-model.

Read first: CLAUDE.md (all of it — WORK ORDERS, ENVIRONMENT TRAPS, VM-default rule), research/nhl_sim/NHL_SIM_PLAN_2026-09-29.md,
research/nhl_sim/NHL_SIM_DECISION_v1.md (S1, S2). If anything here disagrees with S2, S2 wins — say so in the log.

SETUP
- `git fetch`; STOP unless `git show origin/main:research/nhl_sim/NHL_SIM_DECISION_v1.md | grep -c "^### S2"` prints 1.
- Worktree: `git worktree add ~/mlb-model-nhlsim1 -b nhl/sim-s1 origin/main`. Never work in or switch ~/mlb-model.
- You may create/change ONLY: nhl/sim/ (new package; add __init__.py), nhl/sim/tests/, nhl/data/sim/ (small committed
  outputs), .gitignore (add `nhl/data/sim/events/`), research/nhl_sim/. Nothing in nfl/, shared/, data/odds_archive/.
- Each item appends its `### S<n> — title (date)` entry at the END of research/nhl_sim/NHL_SIM_DECISION_v1.md in the SAME
  commit as its code (expected S3..S6). Commit AND push each item before the next (`git pull --rebase --autostash &&
  git push` on the branch). No committed file > 2 MB: raw play-by-play goes to nhl/cache/pbp/ (already gitignored via
  nhl/cache/), event tables to nhl/data/sim/events/ (gitignore it); both are rebuilt from committed generators.
- Tests import production code, run on fixtures cut from REAL responses/tables, and each new test must FAIL on a stated
  mutation that you run and report. Pre-registered predictions go in the report BEFORE the numbers; say plainly whether
  each held; tune nothing to rescue one. A red is reported red.
- Measure, do not assume: every constant in this order comes from the data, with its n and derivation printed.

PRE-CHECK (Cowork's numbers — measure them)
- Games: regular season 2021-22 .. 2025-26 = 5 x 1,312 = 6,560 (the boxscore cache nhl/cache/boxscore_20{21..25}02*.json
  lists them; 2025-26 has 1,220 cached — take the full list from api-web.nhle.com schedule and report the difference).
- Credits: 0 (NHL API and nothing else).
- Runtime: 6,560 calls x (0.25 s sleep + ~0.35 s response) ~= 66 min, resumable (existing file = skip). Items 2-4 are
  local compute on ~700k shot rows: minutes.
- Host: apply the VM-default test (SSH root@142.93.242.4, one play-by-play call). This is a one-off backfill, not a cron
  pipeline: run it on whichever host passes and say which; no cron in this order.

ITEM 1 (S3) — play-by-play pull.
- nhl/sim/pull_pbp.py: GET https://api-web.nhle.com/v1/gamecenter/{gameId}/play-by-play for every regular-season game
  2021-22..2025-26; save gzipped raw JSON to nhl/cache/pbp/{gameId}.json.gz; only games with gameState OFF/FINAL.
- PRE-REGISTER: 100% of the schedule's completed regular-season games return 200; every play carries a situationCode.
- Report: games requested / saved / failed per season, and the play typeDescKey vocabulary with counts (one season).

ITEM 2 (S4) — event and strength-state tables (nhl/sim/build_events.py -> nhl/data/sim/events/season=<S>/*.parquet).
- shots.parquet: every unblocked attempt (shot-on-goal, missed-shot, goal; blocked shots in a separate table), with
  game, period, seconds elapsed in game, x/y (normalised so the attacking net is always at +x), distance, angle,
  shot type, shooting team home/away, shooter id, goalie id (or empty net), strength state from situationCode from the
  SHOOTING team's view (e.g. 5v5, 5v4, 4v5, 4v4, 3v3, 6v5 = own goalie pulled, 5v6 = opponent's net empty), score
  difference BEFORE the event from the shooting team's view, rebound (previous attempt by the same team <= 3 s
  earlier), rush (previous event in the other half of the ice <= 4 s earlier), is_goal. Shootout events EXCLUDED
  (periodType SO) into their own table.
- penalties.parquet (type, minutes, team, time, score state); state_time.parquet: seconds per game spent in every
  (home skaters, away skaters, home goalie in/out, away goalie in/out) combination, split by score difference.
- NULL CONTROLS (asserted in tests and reported for all 6,560 games):
  (a) goals by team from the table == box-score score minus the shootout +1 — 100% of games;
  (b) shots on goal by team == box-score SOG — report the match rate; if < 100%, list the categories of mismatch;
  (c) state seconds per game == regulation 3,600 + OT seconds actually played, within 5 s — 100%;
  (d) empty-net goals counted from situationCode vs the play's own emptyNet flag where present.

ITEM 3 (S5) — our own expected-goals model, frozen (nhl/sim/fit_xg.py -> nhl/data/sim/xg_v1.json).
- Logistic regression on non-empty-net unblocked attempts from 2021-22 + 2022-23 ONLY: distance, angle, shot type,
  rebound, rush, strength-state group (even / PP / PK / 3v3). Coefficients + feature definitions + the sha256 of the
  training table written to the JSON; the generator is committed code.
- PRE-REGISTER before scoring 2023-24: calibration slope 0.9-1.1 and sum(xG)/goals within +/-5% on 2023-24; AUC above
  0.72. NULL CONTROL: the same fit on shuffled labels gives AUC 0.50 +/- 0.01.
- Report calibration by decile (fit seasons and 2023-24), and sum(xG)/goals by season 2021-22..2025-26 (2024-25 and
  2025-26 are REPORTED only — nothing is refitted on them).

ITEM 4 (S6) — measured league constants (nhl/sim/build_constants.py -> nhl/data/sim/constants_v1.json).
- Fitted on 2021-22 + 2022-23 ONLY. Each constant has n and a one-line derivation in the JSON:
  attempt rate per 60 and goals per xG by strength state; penalties per 60 per team, minor/double-minor/major shares,
  share of minors ended early by a PP goal; score-effect multipliers on attempt rate and xG/attempt by score
  difference (-3..+3) x period; pulled-goalie hazard by score difference (-1, -2, -3) x seconds remaining (30-s bins,
  last 5 min of the 3rd); empty-net attempt and goal rates for and against; OT 3-on-3 attempt rate, goals per xG, share
  of OT games ending in OT; shootout per-attempt conversion and share of shootouts past round 3; home-ice multipliers
  on attempt rate and xG/attempt.
- The same constants computed on 2023-24 are written beside them as `validate_drift` (reported, never used).
- PRE-REGISTER: PP goals per 60 of PP time 6-8; home share of unblocked attempts 50.5-52.0%; shootout conversion
  28-35%; the pull hazard at -1 is concentrated in the last 3:00 (> 80% of pulls). State held / not held for each.
- The JSON records its own sha256 in research/nhl_sim/constants_v1_manifest.md (content stamp, never git HEAD).

CLOSING
- logs/_log_nhl_sim_s1.txt (`git add -f`): what each command RETURNED kept apart from what it MEANS; the null-control
  results with counts; each pre-registration HELD / NOT HELD; NOT DONE; UNVERIFIED; commit shas; ONE merge command for
  Jeff. Push. Stop — Cowork verifies from the files before S-WO2 is written.
