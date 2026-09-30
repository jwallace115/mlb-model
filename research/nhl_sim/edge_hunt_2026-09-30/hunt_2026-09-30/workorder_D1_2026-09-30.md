NHL SIM EDGE HUNT — WORK ORDER D-WO1: 2010-11..2020-21 play-by-play + boxscores + event tables (Cowork, 2026-09-30)

WHY: every pre-game engine test so far has two seasons of engine prices. Real SBRO closing moneylines and totals
exist 2007-2023 in research/nhl_sim/edge_hunt_2026-09-30/inputs/games.parquet, and the NHL API serves play-by-play
back to 2010-11 for free. This order gets the raw data and the event tables for 11 more seasons. D-WO2 (separate,
after Cowork verifies this one) builds the walk-forward chain and prices the games. Ledger entry D-01 in project
doc claude/nhl_sim_edge_hunt_ledger.md.

Read first: CLAUDE.md (WORK ORDERS section), research/nhl_sim/NHL_SIM_DECISION_v1.md S1-S2, S36 (PP expiry), S39.

Worktree: ~/mlb-model-nhlD, branch nhl/sim-d1 from origin/main. The pbp cache from S-WO1 is gitignored and lives
in the worktree where S-WO1 ran (~/mlb-model-nhlsim1/nhl/cache/pbp/); state which cache directory you use, and
put the new seasons beside the existing ones (symlink or a shared absolute path — say which). Boxscores are read
by build_events.py / ratings.py from nhl/cache/boxscore_{gid}.json (same layout as the 2021-25 files).

FOUR items. Commit AND push each (`git pull --rebase --autostash && git push`) before the next. Do NOT merge.
HARD RULE: if you are about to write "deferred", "NOT TESTED" or "NOT DONE" for a required output, STOP and say so
in chat instead. Cost: 0 credits (NHL API is free). Decisions D1-D4 go in research/nhl_sim/NHL_SIM_DECISION_v1.md
in the same commit as the code.

ITEM 1 (D1) — PROBE before pulling anything
- Fetch play-by-play AND boxscore for exactly these 6 games with the existing scripts' URL patterns:
  2010020001, 2012020001 (lockout season), 2013020001, 2016020001, 2019020001, 2020020001.
- For each, report: gameState; number of plays; whether every play has typeDescKey, situationCode,
  periodDescriptor.number, timeInPeriod; share of shot-type plays (shot-on-goal, missed-shot, blocked-shot, goal)
  with x/y coordinates; whether details.shootingPlayerId / goalieInNetId exist; boxscore has homeTeam/awayTeam
  abbrev, gameDate, playerByGameStats with goalies and their toi/starter flag (ratings.py reads the `starter` flag
  for goalie identity — say whether it exists in 2010).
- Also count regular-season games per season from the schedule endpoint (api-web.nhle.com/v1/schedule or
  club-schedule-season; state which) for 2010..2020 — MEASURED counts, not assumed (30 teams = 1,230; 31 teams from
  2017-18 = 1,271; 2012-13 lockout 720; 2019-20 stopped at ~1,082; 2020-21 = 868).
- STOP if situationCode or shot coordinates are absent for any probed season: say which season, and propose
  what the event tables would lose. Do not pull 12,000 games onto fields that are not there.
- Write the probe table into research/nhl_sim/edge_hunt_2026-09-30/d1_probe_2026-09-30.md and decision D1.

ITEM 2 (D2) — Pull play-by-play + boxscores, 2010-11 .. 2020-21
- Generalise nhl/sim/pull_pbp.py: --seasons takes any start year; games per season come from Item 1's measured
  counts (a `--max-games` per season map or the schedule), not GAMES_PER_SEASON = 1312. Add a `--boxscore` mode
  (same resume-safe pattern, nhl/cache/boxscore_{gid}.json, plain JSON like the existing files). Keep the 0.25 s
  sleep; requests that return 404 for game ids past the season's last game must stop that season, not loop.
- Runtime pre-check to print BEFORE starting: n_games x (measured request time + 0.25 s) for pbp, and again for
  boxscores. Cowork's estimate: ~11,900 games x ~0.55 s ≈ 1.8 h each; run pbp first, then boxscores. If the
  measured per-request time makes either run exceed 2.5 h, say so and reduce the sleep only if the API's
  rate-limit headers show headroom (report them).
- Null control: re-running the puller on 2021 must download nothing (all files exist) and change no byte in the
  existing cache (compare a sha256 listing of nhl/cache/pbp/2021*.json.gz before and after).
- Report per season: files pulled, files skipped as non-FINAL, 404 count, elapsed, bytes on disk.

ITEM 3 (D3) — Event tables for the new seasons
- Run nhl/sim/build_events.py --seasons 2010,...,2020. Fix only what the old format breaks, and list every
  branch you add with the season it was needed for. The 2021-25 event tables must be byte-identical after your
  changes (null control: sha256 of nhl/data/sim/events/season=2021..2025/*.parquet before and after).
- Sanity per season, printed as a table (as S-WO1/S-WO2 did): goals from events vs boxscore totals (must match to
  within 5 games per season — state the exact count); 5v5 seconds per game; PP seconds per game; penalties per
  team-game; empty-net goals per game; shootout games. Pre-register the bands BEFORE running: goals match >= 99.5%;
  5v5 minutes/game within 45-52; penalties per team-game 2.5-4.5 (older seasons were higher; report, don't clip).
  If a band fails, report it — do not relax it.
- Known structural breaks to record in D3 (from the data, with the season the number moves): 3v3 overtime starts
  2015-16 (4v4 before); the shootout exists throughout; 2012-13 has 48 games/team; 2019-20 ends in March;
  2020-21 is 56 games, divisional. Each of these must be visible in the sanity table (OT length, games per team).

ITEM 4 (D4) — xG v2 applied point-in-time, and a walk-forward plan for constants
- Do NOT refit xG on the new seasons in this order. Apply the frozen xg_v2.json to the new seasons' shots and report
  calibration by decile per season (as fit_xg.py's report does), so D-WO2 knows whether one xG model can serve
  2010-2020 or the walk-forward must refit it per window.
- Write research/nhl_sim/edge_hunt_2026-09-30/d_walkforward_plan.md: for each target season T in 2012..2020,
  fit window = T-2, T-1 (constants v8 fields, ratings K/w, finishing term, xG if Item 4 says so), and the exact
  commands. Do not run it. Decision D4 records the plan and the xG calibration verdict.

CLOSING
- Append a "D-WO1" section to logs/agent_sessions.md (git add -f): each command — what it RETURNED vs what it MEANS;
  every null control with its numbers; every pre-registered band HELD / NOT HELD; NOT DONE; UNVERIFIED.
- Push. Stop. Cowork verifies from origin before D-WO2 is written.
