NHL — WORK ORDER E-WO2: BULK ODDS-API HISTORY PULL, spend-today (Cowork, 2026-09-30). Plan is now 5M credits/month;
today's balance does not roll over at 00:00 UTC 2026-10-01. Ledger entries E-01/E-03 in claude/nhl_sim_edge_hunt_ledger.md.

PURPOSE: buy every NHL price history the hunt has been unable to test on — in-play (branch E, E-03 confirmation),
derivative markets (branch B), props — for 2022-23..2025-26, in priority order, with a spend cap and a global floor,
so that whatever finishes before the reset is the most valuable part. DATA ACQUISITION ONLY. No analysis.

Read first: CLAUDE.md (ODDS API COST MODEL, WORK ORDERS, ENVIRONMENT TRAPS), nhl/pipeline/pull_nhl_inplay.py (E-WO1's
puller — reuse its request / parquet / resume code; its one defect was `regions=us`, which excludes Pinnacle),
nhl/pipeline/pull_nhl_history.py (WO2's puller for the event-level pattern).

Worktree ~/mlb-model-nhlE, branch nhl/inplay-e1 (exists; `git pull --rebase --autostash` first). Commit code, tests,
date lists and the log; DATA IS GITIGNORED (data/odds_archive/nhl/history/**). Runs on the Mac.

BOOKS (binding, replaces regions=us): `bookmakers=pinnacle,draftkings,fanduel,betmgm,williamhill_us,betrivers,bovada,
pointsbetus,unibet_us,betonlineag` — exactly 10 keys = ONE region-equivalent (CLAUDE.md: every 10 books = 1 region;
an 11th silently doubles every call). NEVER include mybookieag or barstool (broken live feeds, E-02). Verify on the
first call that x-requests-last == 10 × number of markets; if not, STOP.

BUDGET (binding):
- Print x-requests-remaining before the first call and after every call. SPEND CAP for this order = 2,400,000
  credits (tracked from the header deltas). GLOBAL FLOOR = 5,000 remaining (the NBA order runs concurrently and
  shares the balance): stop pulling the moment remaining < 5,000 or the cap is reached; commit; report.
- Cost per call: historical = 10 × markets × 1 region-equivalent. Sport-level snapshot with h2h+spreads+totals = 30.
  Event-level snapshot with M markets = 10 × M.
- Throughput: run 4 concurrent workers (threads) with exponential backoff on HTTP 429 / 5xx (start 2 s, cap 60 s);
  measure the achieved calls/second in the first 200 calls and print the projected finish time per item. If the
  projection for the whole order passes 2026-09-30T23:30Z, keep going in priority order — the floor and the reset
  decide what gets done; do not skip ahead.
- Resume-safe everywhere: a file that exists is never re-requested (this order may be re-run after an interruption).

ITEM 1 (E4) — IN-PLAY, 5-minute cadence, every game night, four seasons. PRIORITY ORDER: 2024-25 → 2025-26 → 2023-24
(the 80 E-WO1 nights already exist under season=2023; fill the rest, same schema) → 2022-23.
- Endpoint: GET /v4/historical/sports/icehockey_nhl/odds?bookmakers=<list>&markets=h2h,spreads,totals
  &oddsFormat=american&date=<ISO>. 30 credits per call.
- Nights: every regular-season date with ≥ 1 game (from the boxscore cache / schedule). Snapshots from
  (earliest commence that night − 5 min) to (latest commence + 3 h 15 min), every 5 minutes, UTC, e.g. a 7pm-ET-only
  night ≈ 40 snapshots; a 7pm + 10pm night ≈ 76. Estimate: ~180 nights × ~55 snapshots × 30 ≈ 300k per season;
  four seasons ≈ 1.2M. Print the exact count per season before pulling it.
- Output: data/odds_archive/nhl/history/inplay/season=<start year>/snap_<requested>.parquet + .json.gz (WO2/E-WO1
  schema: snapshot_utc, requested_utc, event_id, commence_time, home_team, away_team, bookmaker, market,
  outcome_name, description, point, price) PLUS a new column `book_last_update` (the bookmaker's market
  last_update — E-02 needed it and had to re-parse the raw JSON).
- Null control: for 20 random 2024-25 pre-match events, the Pinnacle h2h prices in the in-play snapshot nearest
  (≤ 30 min) to a WO2 lines snapshot must equal the WO2 parquet's prices — paste the max difference.
- Decision E4 in research/nhl_sim/NHL_SIM_DECISION_v1.md: nights, snapshots, credits per season, achieved rate.

ITEM 2 (E5) — DERIVATIVE MARKETS at two pre-match snapshots, per event, three seasons. PRIORITY: 2024-25 → 2025-26
→ 2023-24 (historical event odds exist from 2023-05-03; earlier seasons are not available).
- Endpoint: GET /v4/historical/sports/icehockey_nhl/events/<event_id>/odds?bookmakers=<list>&markets=
  h2h_3_way,totals_p1,h2h_p1,spreads_p1,team_totals,alternate_totals,alternate_spreads,h2h_ot&oddsFormat=american
  &date=<ISO>. 8 markets → 80 credits per event-snapshot. Event ids come from the existing lines pulls
  (data/odds_archive/nhl/history/lines/season=*) — every event with a Pinnacle h2h there.
- Two snapshots per event: T−24 h and T−1 h (T = commence). If a market is absent at a snapshot the API still
  charges — record the empty result and do not retry. ≈ 1,310 events × 2 × 80 ≈ 210k per season; three ≈ 630k.
- Output: data/odds_archive/nhl/history/event_markets/season=<start year>/<event_id>_<T-24h|T-1h>.parquet
  (+ .json.gz), same columns as Item 1 plus `market` values as returned.
- Null control: the h2h_3_way rows for 2024-25 at T−1 h must agree with the existing WO2 threeway pull
  (data/odds_archive/nhl/history/threeway/season=2024) for 20 random events within the snapshot gap — paste.
- Decision E5.

ITEM 3 (E6) — PROPS at two pre-match snapshots, three seasons, same priority. Markets: player_points,
player_assists, player_shots_on_goal, player_goal_scorer_anytime, player_total_saves, player_blocked_shots
(6 → 60 credits per event-snapshot; ≈ 157k per season; three ≈ 470k). Same endpoint pattern, output
data/odds_archive/nhl/history/props/season=<start year>/<event_id>_<T-24h|T-1h>.parquet. NOTE the existing
data/odds_archive/nhl/props/ is a different, calendar-year partitioned 7-book backfill — do not write into it.
Decision E6.

ITEM 4 (E7) — DENSE PRE-MATCH, hourly sport-level snapshots (h2h, spreads, totals, 30 credits), every day of
2022-23..2025-26 from 00:00Z to 23:00Z (24/day; ≈ 190 days × 24 × 30 ≈ 137k per season; four ≈ 550k). Output
data/odds_archive/nhl/history/lines_hourly/season=<start year>/snap_<requested>.parquet. Lowest priority: only after
Items 1-3 are complete or the cap/floor stops them. Decision E7.

CLOSING (after every item AND on any stop): append "E-WO2" to logs/_log_e_wo1.txt (git add -f): per item — calls made,
credits spent (header delta), remaining, nights/events/snapshots saved, achieved calls/s, wall time; every null
control with numbers; NOT DONE (which seasons/items did not finish and why); UNVERIFIED. Commit code + date lists +
log; push (`git pull --rebase --autostash && git push`). Do not merge.

DISK: ~100 KB per snapshot; the full order is roughly 90,000 files ≈ 8-10 GB under data/odds_archive/nhl/history/.
Print `du -sh` at the end. Jeff has a 5 TB external drive if the laptop fills; nothing in this order moves data.
