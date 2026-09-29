NHL WORK ORDER 2 — pull NHL odds history from the Odds API (written 2026-09-29 by Cowork, NHL chat). Repo ~/mlb-model.

WHY: Jeff: "if data from the odds api can help lets pull it." The repo has no NHL puck-line prices, no moneyline
prices after 2022-23, no 60-minute (3-way) prices, and the 2025-26 game_markets backfill lost team names on every
team-sided market (its normalizer keyed outcomes by (description, point), blank for team markets). This order pulls
the history so Cowork can scan game lines, puck line, 3-way and a second props season. PULL AND STORE ONLY:
do not analyse outcomes, do not compute win rates or ROI on anything pulled (that is Cowork's pre-registered step).

Read first: CLAUDE.md (ENVIRONMENT TRAPS, ODDS API COST MODEL: historical cost = 10 x markets x regions;
bookmakers= <= 10 books = 1 region-equivalent), research/layers/nhl_edge_hunt_2026-09-29/phase2_props/README_P2.md.

SETUP
- Worktree off origin/main: `git worktree add ~/mlb-model-nhl2 -b nhl/wo2 origin/main`. Touch only the new files
  named below. Commit AND push each item before the next (`git pull --rebase --autostash && git push`).
- Books (<= 10, one region-equivalent): pinnacle, hardrockbet_fl, draftkings, fanduel, betmgm, williamhill_us,
  betrivers, bovada, betonlineag, lowvig. Use `bookmakers=`, never `regions=`.
- New script: nhl/pipeline/pull_nhl_history.py with subcommands `lines`, `threeway`, `props`, a `--season`, a
  `--dry-run` that prints the call plan and credit cost and spends nothing, a `--cap` credit cap for the run, and a
  resume rule: an output file that already exists is skipped (append-only; never overwrite).
- Every paid call logs x-requests-last and x-requests-remaining. HALT if remaining - (next call's estimated cost)
  < RESERVE, with RESERVE = 20,000 (keeps two weeks of the daily captures alive). Load .env with override=True and
  log the key fingerprint sha256[:8]. Never print the key.
- SCHEMA (the thing the old backfill got wrong): keep one row per OUTCOME with outcome_name (team / Over / Under /
  Draw), description (player, for props), point, price, bookmaker, market, event_id, commence_time, home_team,
  away_team, snapshot_utc (the historical snapshot's own timestamp from the response), requested_utc.
  TEST (nhl/pipeline/tests/test_pull_nhl_history.py, on a real saved response as fixture): an h2h market yields
  two rows with the two team names; a spreads market yields +1.5 and -1.5 rows each carrying its team; a props
  market keeps player and Over/Under; a fixture with an in-play snapshot (snapshot_utc >= commence_time) drops that
  event. Each test must FAIL on the old normalize() from
  research/odds_api_backfill/multi_sport_props_archive/run_multi_sport_backfill.py (run it and report).

PRE-CHECK (Cowork's numbers — measure, do not trust)
- Game days: regular season ~185-190 per season. Seasons (start year): 2022, 2023, 2024, 2025.
- Item 1 lines: GET /v4/historical/sports/icehockey_nhl/odds?markets=h2h,spreads,totals&bookmakers=...&date=T
  = 10 x 3 x 1 = 30 credits per snapshot. Snapshots per game day: T = 22:45Z (7-7:30pm ET games), plus 16:45Z on days
  with any game starting before 22:00Z, plus 01:45Z on days with any game starting at or after 01:30Z. Each game is
  assigned to the latest snapshot before its commence_time. ~2.3 snapshots/day x 187 x 4 seasons ~= 1,720 calls
  ~= 52,000 credits. If that is over the budget, do 22:45Z + the conditional 01:45Z only (~1.8/day ~= 40,000).
- Item 2 3-way: GET /v4/historical/sports/icehockey_nhl/events?date=T (1 credit) then per event
  /v4/historical/sports/icehockey_nhl/events/{id}/odds?markets=h2h_3_way&date=(commence - 10 min) = 10 credits/event.
  2024-25 only: ~1,312 x 10 + ~190 = ~13,300.
- Item 3 props 2024-25: per event markets=player_points,player_assists,player_shots_on_goal,player_goal_scorer_anytime
  (use the keys the /markets discovery or the first response actually shows for NHL; report them) at
  commence - 10 min = 10 x 4 = 40 credits/event, ~1,312 events ~= 52,500.
- Runtime: <= ~4,500 calls at ~1 s each (0.5 s sleep) ~= 75 min total; each season is its own resumable run.
- Balance: unknown (100,000 plan; ~99,800 on 2026-09-27 minus captures since). Items run in order 1 -> 2 -> 3 and
  each stops at the RESERVE; whatever does not fit waits for the next cycle and is listed under NOT DONE.

ITEM 1 — game lines 2022-23 .. 2025-26 (featured markets, team names kept).
- `--dry-run` first: print the snapshot plan per season and total credits. Then ONE live snapshot (30 credits):
  PRE-REGISTER "costs 30 credits; pinnacle present; h2h has 2 outcomes per game". Report x-requests-last. If the
  measured cost differs from 30 by more than 20%, STOP and report.
- Output: data/odds_archive/nhl/history/lines/season=<S>/snap_<snapshotUTC>.parquet (start-year season).
- Report per season: game days, snapshots, games covered (vs the NHL schedule count), share of games with a
  pinnacle h2h + spreads + totals, median minutes from snapshot to puck, books returned / never returned,
  hardrockbet_fl presence, credits used.

ITEM 2 — 60-minute 3-way, 2024-25 (event endpoint).
- One live event first (PRE-REGISTER cost 10 + the events list 1), then the season.
- Output: data/odds_archive/nhl/history/threeway/season=2024/date=YYYY-MM-DD.parquet.
- Report: events covered, books offering h2h_3_way, credits.

ITEM 3 — player props, 2024-25 (event endpoint), only if the balance allows after items 1-2.
- One live event first; report the market keys actually returned for NHL and the cost. Then the season, month
  by month (each month a resumable chunk).
- Output: data/odds_archive/nhl/history/props/season=2024/month=MM/date=YYYY-MM-DD.parquet.
- Report: events, player-lines per market, books, credits, and months NOT pulled.

CLOSING
- logs/_log_nhl_wo2.txt (`git add -f`): what each command RETURNED vs what it MEANS; credits per item and the
  balance before/after; NOT DONE (with credits needed); UNVERIFIED. No analysis of outcomes. Push. Stop — Cowork
  runs the pre-registered scans on the pulled data.
