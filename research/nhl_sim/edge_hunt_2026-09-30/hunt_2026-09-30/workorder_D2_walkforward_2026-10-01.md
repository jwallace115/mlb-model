NHL SIM EDGE HUNT — WORK ORDER D-WO2: fix the pre-2019 play order, build the walk-forward chain 2012-13..2020-21,
price every game, evaluate at real closing prices (Cowork, 2026-10-01 01:00Z). Worktree ~/mlb-model-nhlD, branch
nhl/sim-d1 (continues D-WO1; `git pull --rebase --autostash` first). Ledger: claude/nhl_sim_edge_hunt_ledger.md D-01.

WHAT COWORK FOUND VERIFYING D-WO1 (read before Item 0):
- D1-D4 are on origin (2e7c718c5..94a74f349). Game counts, 100% goal agreement and the xG verdict reproduce.
- The "state time issue pre-2019" is NOT a period-transition encoding difference. The old play-by-play's play ORDER is
  not chronological: in 2015020001, 5 plays have an earlier timeInPeriod than the play before them (e.g. a
  shot-on-goal at 1:06 listed after a play at 2:45). build_events builds strength spans from consecutive plays, so
  an out-of-order play produces OVERLAPPING spans: that game's period 1 sums to 1,350 s of state time instead of
  1,200, and across 2015-16 the per-game state-time total has median 3,699 s and 90th percentile 4,292 s (should be
  3,600 / 3,900). 2019+ plays are time-ordered, which is why those seasons pass. Every per-60 rate, PP second, pull
  flag and shot score-state for 2010-2018 is contaminated until this is fixed. It is a one-line sort, with tests.
- D2's headline "12,592 games" disagrees with its own per-season table (sums to 12,502); say which is right.
- The 2021-2025 byte-identity null for build_events.py was NOT run (tables absent in the worktree). Item 0 runs it.

FOUR items. Commit AND push each. HARD RULE: STOP rather than write "deferred". Cost 0 credits. Decisions D5-D8 in
research/nhl_sim/NHL_SIM_DECISION_v1.md in the same commit as the code. Runtime pre-checks printed before each run.

ITEM 0 (D5) — chronological play order, tests first
- In build_events.py sort each game's plays by (period number, timeInPeriod seconds, sortOrder) before any span or
  score-state logic. Write the test FIRST: on 2015020001 the per-period state-time sum must equal 1,200 s per
  regulation period (and 300 s or less for OT) — show it FAILING on the committed code, then PASSING.
- Null controls (all must hold, paste numbers): (a) rebuild season=2021 and season=2023 → shots, penalties and
  state_time parquets byte-identical to the current files (sha256 before/after); (b) across 2010-2018 the share of
  games whose state-time total is within 2 s of 3,600 (+300 if OT, + shootout handling as the 2021+ code does) is
  ≥ 99% after the fix — print the per-season share before and after; (c) goals still match boxscores 100%.
- Rebuild events for all 11 old seasons. Report shots whose score_diff changed (count per season) — those are the
  shots that were mis-stated by the ordering bug.

ITEM 1 (D6) — walk-forward fit windows
- For each target season T in 2012..2020 (9 seasons), fit window = {T−2, T−1} (2012's window is 2010+2011).
  Generalise the fit-season lists in build_constants_v7.py (--v8), ratings.py (--measure-hyper, carry-over,
  finishing term) and anything else that hardcodes [2021, 2022] / ALL_SEASONS, as CLI arguments; keep the current
  defaults so the 2021+ outputs are unchanged (null control: re-running with defaults reproduces constants_v8.json
  and the current ratings parquets byte-for-byte or to 1e-12).
- Produce, per T: constants_v8_T.json, shrinkage_K_T.json, carryover_w_T.json, team_ratings/goalie_ratings/
  finishing_term for season T (point-in-time within T, prior from the window). Record the measured r/K/w per T in
  D6 as a table — these are the first cross-era measurements of the engine's own hyperparameters. xG stays xg_v2.
- Structural breaks to honour: 2015-16 OT changes to 3v3 — the 2017 window (2015+2016) is the first all-3v3 window;
  for T = 2015 and 2016 the OT constants must come from the 4v4 era and the engine's OT code takes a base-skater
  argument (currently 3); add it (default 3), test it. 2012-13 is 720 games: its window contributions are weighted
  by games, not seasons.

ITEM 2 (D7) — price every game, 2012-13..2020-21
- price_games.py generalised to --season T with the T-specific constants/ratings, 2,000 sims, seed = game_id.
  Runtime pre-check: ~10,850 games × 1.2 s (Mac, measured) / 4 processes ≈ 55 min; print it, then run.
- Output nhl/data/sim/prices/season=T.parquet (gitignored, sha in manifest), same columns as 2022-23 incl. the
  total-goals pmf and mean_home/away_goals. Null: the pricer on season=2023 with default inputs reproduces the
  committed 2023 parquet's p_home_win on 20 games to max diff 0.

ITEM 3 (D8) — evaluation at real closing prices, PRE-REGISTERED
- Inputs: research/nhl_sim/edge_hunt_2026-09-30/inputs/games.parquet (SBRO closing ML `ml_h/ml_a` → `p_h`, closing
  total `tl`, `tot`, `home_win`; 2007-2023). Join on game_id (or date+home+away; report unmatched per season).
- Per season 2012-2020 and pooled: ML log-loss engine vs SBRO close; A1 disagreement coefficient (outcome ~
  logit close + (logit engine − logit close)) with 90% CI; totals log-loss at the SBRO line and totals A1; A2 picks
  (engine − 1/decimal close ≥ 0.04) ROI at the SBRO close with SE, by season / month / fav-dog.
- PRE-REGISTER in the log BEFORE running: (i) engine ML log-loss within 0.012 of the close pooled; (ii) pooled A1
  coefficient 90% CI includes 0 (the engine as an opinion does not beat the close — the two-season result); (iii)
  THE ONE LEAD: regime R8 (both teams' penalties-taken rating > 1.05 × league at game time) — pooled over 9 seasons
  (~600 games), ML A1 coefficient > 0 with 90% lower bound > 0 is the pass; prior from 2022-24 was +3.4 / +2.9 on
  60-75 games a season. Also report R6 (both goalies below league average) the same way, and the full 16-regime
  family with BH 10% over the 9-season pool, as a family of 16 p-values for the ledger.
- If (iii) holds, the rule is frozen as written here and goes to the ledger as D-R8 for CONFIRM on 2022-23 +
  2023-24 at Pinnacle's close (already priced) — do NOT look at those seasons in this order. If it does not hold,
  say so; no re-thresholding.

CLOSING: append "D-WO2" to logs/agent_sessions.md (git add -f): RETURNED vs MEANS per command, every null control
with numbers, every pre-registration HELD / NOT HELD, NOT DONE, UNVERIFIED. Push. Stop. Do not merge.
