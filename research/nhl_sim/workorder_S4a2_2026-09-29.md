NHL SIM WORK ORDER S-WO4a2 — fix the power-play expiry artifact at the root, rebuild the chain, investigate ties
(Cowork, 2026-09-29 19:37Z). Repo ~/mlb-model. Worktree ~/mlb-model-nhlsim4, branch nhl/sim-s4.

Read first: CLAUDE.md, research/nhl_sim/nhl_sim_s4a_verification_2026-09-29.md, decisions S34 and S35.

THREE items. HARD RULE: if you are about to write "deferred", "NOT TESTED" or "requires a pipeline change", STOP and
explain in chat instead. Do not push a partial item.
- Decisions S36-S38 go in the decision doc, in the same commit as their code.
- Commit and push each item (`git pull --rebase --autostash && git push`). Paste `git diff --stat origin/main...HEAD`
  before each push. Do NOT merge.
- Cost: 0 credits.
- Runtime: the events rebuild — measure one season first and report; the full rebuild of 5 seasons must be
  estimated before it runs. Ratings rebuild ~75 s. realism_report.py 100k sims ~70 s.
- Every new or changed output must come from committed code. After each item, grep that each written file has a
  generator, and paste it.

ITEM 1 (S36) — state_time: power plays end when the penalty expires, not at the next play
- In nhl/sim/build_events.py, when a span has a skater imbalance and the next play's situationCode shows fewer
  imbalanced skaters, the change happens at the EXPIRY time of the pending penalty, if that falls inside the span.
  - Expiry = penalty time + nominal length (2 / 4 / 5 min, from penalties.parquet). An earlier power-play goal ends
    a minor (and one half of a double minor). The goal is a play, so it is already exact.
  - Split the span there. The part after the expiry takes the next play's skater counts. Goalie flags and score are
    unchanged.
- NULL CONTROLS (paste each):
  (a) shots.parquet and penalties.parquet are byte-identical to before for every season: only state_time changes;
  (b) total seconds per game are unchanged, for every game;
  (c) no power-play span created by a single minor with no PP goal lasts more than 121 s. Paste the span-length
      distribution before and after; before, the median was 124 s and 46% were > 125 s;
  (d) the share of shots whose own strength label matches state_time at the shot's second must not fall. Report
      before and after.
- Rebuild the 15 event tables (5 seasons x 3), then team_game_stats / ratings / goalie_games / finishing term
  (`python3 nhl/sim/ratings.py --measure-hyper` — hyperparameters are re-measured because pp/pk seconds change),
  build_constants_v5.py, and build_constants_v7.py.
- Paste every r, K and w old → new, and the manifest.json sha values. Run all tests; paste the output.

ITEM 2 (S37) — realism re-run, same bands
- `python3 nhl/sim/realism_report.py --n-sims 100000`, unchanged. The engine is unchanged; only the inputs change
  because of Item 1.
- PRE-REGISTER (in the log before running): PP goals per team-game moves inside ±8%, and simulated PP minutes are
  within ±5% of the (corrected) actual.
- Report all 9 bands, HELD / NOT HELD. Tune nothing.

ITEM 3 (S38) — where do the missing regulation ties go? (descriptive, 2022-23 fit season only; no model change)
- Using the same 100k sims (save their per-sim score at every minute of the 3rd period: extend simulate() with an
  optional `trace_minutes=True` that returns the score difference at the end of each 3rd-period minute), and the
  actual 2022-23 state_time:
  - the share of games tied, up 1, and up 2+ at the start of the 3rd period and at 15:00, 10:00, 5:00, 2:00 and
    0:00 remaining, sim vs actual;
  - the share of 1-goal games at 5:00 remaining that end tied, sim vs actual.
- Report the table. State plainly where the gap opens. Do NOT change the engine in this order.

CLOSING
- Append "S-WO4a2" to logs/_log_nhl_sim_s4.txt (git add -f):
  - each command: what it RETURNED vs what it MEANS;
  - the null controls;
  - the generator grep;
  - the tests;
  - the pre-registrations with HELD / NOT HELD;
  - an accurate NOT DONE list;
  - UNVERIFIED.
- Push. Stop. Do not merge.
