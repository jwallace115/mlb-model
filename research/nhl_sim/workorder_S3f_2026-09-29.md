NHL SIM WORK ORDER S-WO3f — fix the xG double-count, constants from a committed generator, PP/PK/penalty ratings
done properly (Cowork, 2026-09-29 17:12Z). Repo ~/mlb-model.

WHY: research/nhl_sim/nhl_sim_s3e_verification_2026-09-29.md.
- The xG merge double-counts shots that share (game, period, second, team): 2023-24 5v5 attempts are 89,944 vs 89,391
  in the event table.
- constants_v3 and v4 have no committed generator.
- S24's PP/PK/penalty ratings are unshrunk running totals.
- The score adjustment and the goalie truncation test are still missing.

TWO items. The code for each hard part is given below. Use it as written.

HARD RULE: if you are about to write "NOT TESTED", "deferred" or "requires a pipeline change" for anything in this
order, STOP instead and explain in chat why the given code cannot work. Do not push a partial item.

Decisions S25-S26 go in research/nhl_sim/NHL_SIM_DECISION_v1.md, in the SAME commit as their code.

SETUP
- Continue in worktree ~/mlb-model-nhlsim3e on branch nhl/sim-s3e. Run `git pull --rebase origin main` first.
- Commit and push each item (`git pull --rebase --autostash && git push`). Paste `git diff --stat origin/main...HEAD`
  before each push. Do NOT merge.
- Cost: 0 credits.
- Runtime: the stats rebuild takes ~52 s; ratings ~2 s. Goalie ratings are rebuilt from the per-game goalie table
  (see Item 2), so the truncation test takes seconds. Measure and report.

ITEM 1 (S25) — xG attached by row, not by merge; constants_v5 from a committed generator
- In build_game_stats_vectorised, replace the merge with:
    en = shots_all["empty_net"].astype(bool)
    shots_all = shots_all.copy()
    shots_all["xg"] = 0.0
    shots_all.loc[~en, "xg"] = score_xg(shots_all.loc[~en], model)
- Apply the same fix anywhere else a merge on (game_id, period, seconds, shooting_team) is used (grep, and paste the
  grep).
- NULL CONTROL (new test in test_ratings_s18.py, run for each of the 5 seasons, EXACT equality):
  - sum(ev_att_for) == number of event-table shots with strength == "5v5";
  - sum(ev_goals_for) == those shots' goals;
  - sum(pp_att_for) == number of shots with strength in PP_STATES.
  It must FAIL on the current code. Run it before the fix and paste the failure: Cowork measured 2023-24 at 89,944 vs
  89,391. It must pass after the fix.
- Rebuild team_game_stats.parquet and team_ratings.parquet; update manifest.json.
- New committed generator nhl/sim/build_constants_v5.py writes nhl/data/sim/constants_v5.json. It computes the same
  fields as constants_v4, from the event tables with the row-wise xG, fit seasons [2021, 2022], with derivation
  strings.
- Mark v3 and v4 SUPERSEDED in S25 (no generator; v4 double-counted). Do not delete them.
- NULL CONTROLS for v5 (paste each):
  (a) the 5v5 numerator == 178,012, v2's count from its committed generator build_constants.py;
  (b) every pooled numerator = home part + away part;
  (c) running build_constants_v5.py twice gives byte-identical JSON.

ITEM 2 (S26) — PP/PK/penalty ratings with shrinkage and carry-over; score-adjusted 5v5; goalie truncation test
(a) Add total_seconds to team_game_stats (the sum of state_time duration per game).
    Penalty rates = penalties / total_seconds × 3600. Not ev_seconds.
(b) Score-adjusted 5v5. In build_game_stats_vectorised, for 5v5 shots:
      c2 = constants_v2 constants
      sd = shots.score_diff.clip(-3, 3).astype(int); p = shots.period.clip(upper=3).astype(int)
      w_att = 1 / c2[f"score_effect_attempt_mult_sd{sd}_p{p}"]["value"]   (vectorise with a dict lookup)
      w_xg  = 1 / c2[f"score_effect_xg_mult_sd{sd}_p{p}"]["value"]
    score_diff is from the SHOOTER's view (as in build_constants.py).
    New columns:
      ev_att_for_adj = sum(w_att)
      ev_xg_for_adj  = sum(w_att × w_xg × xg)
    and the same for "against". Keep the unadjusted columns.
(c) PRE-REGISTER (in the log before computing): split-half r of the ADJUSTED 5v5 attempt share >= r of the UNADJUSTED
    share. Both are computed after the Item 1 fix, the same way, on 2021-23.
    - If it holds, the ratings use the adjusted columns.
    - If not, keep the unadjusted columns and say so plainly. Tune nothing.
(d) Add pp_xg_for_per60, pk_xg_against_per60, penalties_taken_per60 and penalties_drawn_per60 to build_pit_ratings,
    with EXACTLY the 5v5 structure:
    - K = compute_K(split-half r on 2021-23 per-game rates, 82);
    - carry-over w measured 2021 → 2022 with the same slope method, written to carryover_w.json;
    - target = w × last season's final + (1 - w) × league mean strictly before D in-season (previous season's league
      mean until 20 team-games), and 2021 warm-up as the 5v5 code does;
    - rating = shrink(raw × n, n, target, K).
    - Delete the literal 7.0 / 3.8 defaults. Report every r, K and w.
(e) TESTS:
    - Add the four new columns and the adjusted 5v5 columns to the truncation test COLS.
    - GOALIE truncation test: split build_goalie_ratings into _build_goalie_games (exists) + a new
      goalie_ratings_from_games(gdf). The test builds gdf once. For each of the 20 dates:
      - keep gdf rows with date <= D;
      - set that date's gsax to gsax × 7 + 3;
      - rebuild; goalie ratings on D must equal the full run to 1e-12.
      - Also a goalie mutant (move the `gs[...] +=` lines above the rating): it must give diff > 1e-6.
    - Paste the full `pytest nhl/sim/tests -q -rs` output. 0 skipped.
- Rebuild ratings; update manifest.json. Do NOT run sanity_check.py; the formula run is the next order.

CLOSING
- Append "S-WO3f" to logs/_log_nhl_sim_s3.txt (git add -f):
  - each command: what it RETURNED vs what it MEANS;
  - the failing-then-passing null control;
  - the grep;
  - the diff --stat outputs;
  - every r, K and w;
  - the pre-registration with HELD / NOT HELD;
  - an accurate NOT DONE list (should be empty);
  - UNVERIFIED.
- Push. Stop. Do not merge.
