NHL SIM WORK ORDER S-WO3g — review Cowork's S27 code, point-in-time finishing term, ONE full-formula check run
(Cowork, 2026-09-29 17:58Z). Repo ~/mlb-model, worktree ~/mlb-model-nhlsim3e, branch nhl/sim-s3e.

Read first: CLAUDE.md, research/nhl_sim/nhl_sim_s3f_verification_2026-09-29.md, decision S27, amendments A1 / A2.

THREE items. HARD RULE: if you are about to write "deferred", "NOT TESTED" or "requires a pipeline change", STOP and
explain in chat instead. Do not push a partial item.
- Decisions S28-S30 go in the decision doc, in the same commit as their code.
- Commit and push each item (`git pull --rebase --autostash && git push`). Paste `git diff --stat origin/main...HEAD`
  before each push. Do NOT merge.
- Cost: 0 credits.
- Runtime: `python3 nhl/sim/ratings.py --from-cache` takes seconds; the full rebuild is ~75 s. Measure and report.

ITEM 1 — independent review of S27 (Cowork wrote this code; you check it)
- Run `pytest nhl/sim/tests -q -rs` on the Mac, including the e17ace021 old-code test, and paste the full output.
  test_build_events needs nhl/cache/pbp; if it's missing, copy it from ~/mlb-model-nhlsim1 or say it's absent.
- Re-run `python3 nhl/sim/ratings.py --from-cache`. The sha256 of team_ratings.parquet and goalie_ratings.parquet must
  equal manifest.json. Paste the result.
- Read build_pit_ratings, goalie_ratings_from_games, measure_hyper and measure_carryover. For each thing you think is
  wrong, write a test that demonstrates it and paste it failing. Only then fix it.
  A disagreement with no failing test goes in the log as an opinion, not a change.

ITEM 2 (S28) — point-in-time league finishing term
- New function in ratings.py. For each game date D:
  F(D) = sum(goals) / sum(xG) over non-empty-net attempts from all games with date in [D-30, D-1].
  - Before 300 games are in the window within the season, use the previous season's last 30 days of games.
  - 2021-22 dates before any window exist: NaN.
- Write nhl/data/sim/ratings/finishing_term.parquet (date, F, n_games, source = "in_season" / "prev_season"). Add its
  sha to manifest.json.
- TEST: add F to the truncation test. Drop rows after D and corrupt D's own goals/xG; F(D) must be unchanged to 1e-12.
  Also a mutant with window [D-30, D] must fail.
- Report F by month, 2021-26. This is descriptive only; the holdout seasons are shown as numbers, not used for any
  choice.

ITEM 3 (S29) — the ONE full-formula check run: new nhl/sim/sanity_check_v2.py (leave sanity_check.py as it is)
Per game, home team h vs away team a. Use the team_ratings rows (ratings going INTO the game), goalie_ratings,
constants_v5 (fit 2021-22) and F(D).
- League-relative terms use the stored `lg_*` columns, because the 5v5 ratings are on the score-adjusted scale:
    A_h = C5_att   × (h.ev_att_for_per60 / h.lg_ev_att_for_per60) × (a.ev_att_against_per60 / a.lg_ev_att_against_per60)
    Q_h = C5_xgpa  × (h.ev_xg_per_att_for / h.lg_ev_xg_per_att_for) × (a.ev_xg_per_att_against / a.lg_ev_xg_per_att_against)
    xG5_h = A_h × Q_h × M5 / 60
  where C5_att, C5_xgpa and M5 = constants_v5 attempt_rate_per_60_per_team_5v5, xg_per_attempt_5v5 and
  minutes_per_game_5v5.
- Power-play minutes:
    P_h = (minutes_per_team_game_5v4 + _5v3 + _4v3)
          × (h.penalties_drawn_per60 / h.lg_penalties_drawn_per60)
          × (a.penalties_taken_per60 / a.lg_penalties_taken_per60)
- Power-play and short-handed xG:
    PPxG_h = P_h / 60 × h.pp_xg_for_per60 × (a.pk_xg_against_per60 / a.lg_pk_xg_against_per60)
    SHxG_h = P_a / 60 × attempt_rate_per_60_disadvantaged_5v4 × xg_per_attempt_disadvantaged_5v4
- 4v4 and 3v3 xG per team: minutes_per_game_{4v4,3v3} / 60 × attempt_rate_per_60_per_team_{..} ×
  xg_per_attempt_{..}.
- Goalie of the other team:
    goals_h(non-EN) = F(D) × (xG5_h + PPxG_h + SHxG_h + xG4v4_h + xG3v3_h) × (1 - g_a.gsax_per_att_rating / q)
  with q = constants_v5 league xG per non-empty-net attempt, over all states. Derive it in the generator if it's not
  there, with a derivation string.
- Extra-attacker and empty-net goals per team = half of the league per-game goals in the 6v5 state (both sides:
  minutes × rate × goals_per_attempt from constants_v5).
- implied_total = goals_h + goals_a + extra-attacker/empty-net. implied_diff = goals_h - goals_a.
- ACTUAL total = regulation + OT goals (the shootout-winner goal removed). Report the box-score total with the
  shootout goal separately.
- Pinnacle join: import it from research/layers/nhl_edge_hunt_2026-09-29/phase3_lines/build_lines.py logic. Match
  counts must be 1,156 / 1,138.
- Run ONCE on 2022-23 and 2023-24. Report, in this order:
  (1) corr(implied_diff, actual goal diff) and corr(implied_total, actual total), next to Pinnacle's own corr on the
      same games;
  (2) the S12 bars: corr(implied_diff, Pinnacle logit) > 0.60; corr(implied_total, Pinnacle total) > 0.30; mean
      implied total within ±3%.
      The ±3% bar on 2023-24 is NOT blind (Cowork used 2023-24 totals to diagnose the power-play constant). Report it
      as a consistency check.
  (3) shuffled-within-date null;
  (4) CHECK 5 breakdown: the same corrs by month, and by n_prior_games bucket (0-10, 11-40, 41+).
- If a bar fails, say so plainly. No second run with changed inputs.

CLOSING
- Append "S-WO3g" to logs/_log_nhl_sim_s3.txt (git add -f):
  - each command: what it RETURNED vs what it MEANS;
  - the review findings (tests pasted);
  - the pre-registration results;
  - an accurate NOT DONE list;
  - UNVERIFIED.
- Push. Stop. Do not merge.
