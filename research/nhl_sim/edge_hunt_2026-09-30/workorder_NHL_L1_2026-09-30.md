NHL WORK ORDER NHL-L1 — Hard Rock + Pinnacle NHL tape and a shadow price layer (Cowork, 2026-09-30 02:40Z).
Repo ~/mlb-model.

WHY: research/nhl_sim/edge_hunt_2026-09-30/edge_hunt_2026-09-30.md.
- The engine is not an opinion edge on NHL game lines. Four pre-registered tests say so.
- The early soft-book price rule held out of sample: +2.7% CLV vs Pinnacle's close on 2024-26.
- The engine's game structure prices the puck line at Pinnacle quality (log-loss 0.6605 vs 0.6606).
- Hard Rock, the only book Jeff can bet, is in no history pull (CHECK 3 open). Opening night is days away, so the tape
  must start now.

HARD RULE: if you are about to write "NOT TESTED", "deferred" or "requires a pipeline change" for anything in this
order, STOP and explain in chat why the given code cannot work. Do not push a partial item.

SETUP
- `git fetch origin && git worktree add ~/mlb-model-nhlL1 -b nhl/price-layer-l1 origin/main`
- Cowork left the research record in ~/mlb-model/research/nhl_sim/edge_hunt_2026-09-30/ (untracked). Copy that
  folder into the worktree at the same path.
- Do NOT commit these (they are data): lines_all.parquet, games_lines.parquet, market_grid_v1_cowork.npz. Keep them
  as local inputs only.
- Commit and push each item (`git pull --rebase --autostash && git push`). Paste `git diff --stat origin/main...HEAD`
  before each push. Do NOT merge.
- No `.get(..., default)` fallbacks on constants or odds fields. Secrets: .env only, log the key fingerprint
  sha256[:8], never print the key.

ITEM 1 (L1a) — research record and the engine grid, committed and reproduced
- `git add` the .md / .py / .txt / .csv files in research/nhl_sim/edge_hunt_2026-09-30/ (no parquet, no npz).
- Move edge_hunt_2026-09-30/grid.py to nhl/sim/market_grid.py with these changes and no others:
  - ROOT-relative imports;
  - output nhl/data/sim/market_grid_v1.npz;
  - Pool(os.cpu_count()).
- Runtime: 63 cells x 20,000 sims = 1.26M sims. Cowork measured ~770 sims/s per core, so ~27 min of one core
  (~4 min on 8). Measure and report.
- IDENTITY TEST (new nhl/sim/tests/test_market_grid.py):
  - np.array_equal of J, S, M and reg_tie between the new npz and market_grid_v1_cowork.npz.
  - The seeds are fixed (cell seed = i*100 + j, PCG64), so the arrays must be equal. If not, report the max abs diff
    and STOP.
  - Note: Cowork ran with the S4b worktree's constants_v8, which differs from main's only by
    q_league_xg_per_non_en_attempt. league_average_inputs() does not read that field, so main must reproduce the grid.
- Commit nhl/data/sim/market_grid_v1.npz (130 KB) with its sha256 in the log.

ITEM 2 (L1b) — NHL on the multi-book tape (Hard Rock + Pinnacle)
- Find where shared/pipeline/multi_book_open_capture.py is scheduled: Mac crontab, launchd, and the VM crontab
  (`ssh root@142.93.242.4 crontab -l`). Paste every line that runs it.
- On THAT host, add a separate NHL line (keep the existing lines unchanged): hourly at :07 from 10:07 to 23:07
  America/New_York, running
  `python3 shared/pipeline/multi_book_open_capture.py --sports icehockey_nhl && python3 nhl/pricing/price_layer_shadow.py`
  (the second command is added once Item 3 exists).
- First run `--sports icehockey_nhl --dry-run`, then one real run.
  - Paste which books returned NHL rows. hardrockbet_fl and pinnacle must both be present. If Hard Rock is absent,
    STOP and report; do not substitute a book.
  - Paste the output path (expected data/odds_archive/nhl/game_markets/season=2026/…).
- COST:
  - 3 credits per call (10 named books = 1 region-equivalent x 3 markets);
  - 14 calls a day = 42 credits a day, ~190 days = ~8,000 credits a season.
  - Paste x-requests-remaining from the real run. If it is below 20,000, STOP and report before scheduling.

ITEM 3 (L1c) — shadow price layer, logging only (no bets)
- New nhl/pricing/price_layer_shadow.py. It reads the NHL tape. For every (event, snapshot) before puck where Pinnacle
  has a moneyline and a single-point total:
  - (a) Rule EV2, for EVERY book including hardrockbet_fl:
    - p_fair = Pinnacle two-way multiplicative de-vig at the same snapshot, same market and same point;
    - markets: moneyline, total at Pinnacle's point, puck line +/-1.5 at Pinnacle's orientation;
    - EV = p_fair x dec - 1;
    - flag EV >= 0.02.
  - (b) Rule ENGINE_ALT (exploratory: its pre-registered H3 failed; logged only for CLV):
    - solve (s, m) with alt_test.py's joint() / solve() copied UNCHANGED, reading nhl/data/sim/market_grid_v1.npz;
    - price every hardrockbet_fl totals and spreads quote at a point Pinnacle does not hang;
    - EV = p_win x (dec - 1) - p_lose;
    - flag EV >= 0.02.
- Append (dedupe on snapshot_utc, event_id, book, market, side, point) to nhl/data/price_layer/flags.parquet.
  Columns:
  - snapshot_utc, event_id, commence_time, lead_h;
  - book, market, side, point, dec;
  - p_fair, ev, rule;
  - solve_s, solve_m, solve_resid.
- New nhl/pricing/price_layer_grade.py, run nightly. For each flag whose game is final:
  - p_close = Pinnacle's fair at the last snapshot before puck, same market and point;
    - engine-converted when the point differs (same solve code);
  - CLV = p_close x dec - 1, push-aware for totals;
  - result from the NHL API final score (the source pull_pbp.py uses).
  - Write nhl/data/price_layer/graded.parquet.
- TESTS (nhl/pricing/tests/):
  - (1) De-vig/EV unit test on hand-computed fixture prices.
  - (2) PARITY: apply the shadow's EV2 function to research/nhl_sim/edge_hunt_2026-09-30/lines_all.parquet for
    2023-24 with ev_test.py's EARLY selection (best of the 8 non-Pinnacle books, earliest snapshot >= 12 h with
    Pinnacle, one bet per game x market). It must give EXACTLY 48 bets and mean CLV 0.0139 (4 dp, over the 46 with a close price), matching
    ev_test.py's log. This is CHECK 3 for the live object.
  - (3) ENGINE_ALT parity: for 2022-24 EARLY, the shadow's solve gives the same 1,592 solved games and 35 bets as
    alt_run_log.txt.
  - Paste `pytest nhl/pricing/tests nhl/sim/tests/test_market_grid.py -q -rs`, 0 skipped.
- Chain the shadow onto the Item 2 cron line; add the grader as a nightly line at 04:17 ET on the same host.

ITEM 4 (L1d) — report and the pre-registered go-live bar (write this into the decision doc now, before any data)
- nhl/pricing/price_layer_report.py prints:
  - flags and graded counts by rule, book and market;
  - mean CLV with a game-clustered SE and the 90% lower bound;
  - ROI;
  - Hard Rock alone as its own block.
- GO-LIVE BAR (pre-registered; shadow only until met): rule EV2, book hardrockbet_fl, one flag per game x market
  (the earliest snapshot at which it first qualifies), n >= 150 graded, mean CLV > 0 AND 90% lower bound > 0.
  - Until then, nothing is bet.
  - Not met by n = 400: rule EV2 at Hard Rock is dead, and is not re-thresholded.

CLOSING
- Append "NHL-L1" to logs/_log_nhl_sim_s4.txt (git add -f):
  - each command: what it RETURNED vs what it MEANS;
  - the cron lines before and after;
  - the credit numbers;
  - the identity and parity test outputs;
  - NOT DONE (should be empty);
  - UNVERIFIED.
- Push. Stop. Do not merge.
