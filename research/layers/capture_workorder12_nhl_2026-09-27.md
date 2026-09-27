# Capture work order 12 — NHL on the line tape, multi-book event markets (props + every game market), NFL props multi-book (2026-09-27)

Written by Cowork for Jeff's instruction (2026-09-27): "add NHL line pulls ... pull from multi-books on all sports for
data, Hard Rock is what we pick off ... player props, totals, spread, moneyline, everything we can." Plan:
`research/layers/LAYERS_GAMEPLAN_2026-09-27.md`. NHL opens Tue 2026-09-29 (first puck 21:00Z).

## What Cowork verified in the repo before writing this
- The 30-min tape is `shared/pipeline/multi_book_open_capture.py`: 10 named books via `bookmakers=` (includes
  `hardrockbet_fl` and `pinnacle`; <= 10 books costs 1 region-equivalent), markets h2h/spreads/totals, **3 credits per
  sport per call**. Default sports: MLB, NFL, NCAAF. It runs on the **VM** by cron (CLAUDE.md "VM-default rule";
  Mac LaunchAgents disabled 2026-09-14). The VM crontab has never been read by Cowork.
- Three defects that bite the moment a hockey/basketball sport is added: (1) the output folder is
  `sport.replace("americanfootball_", "")`, so NHL would land in `data/odds_archive/icehockey_nhl/`, not the existing
  `data/odds_archive/nhl/`; (2) the season label is `year if month >= 3 else year - 1`, which splits an NHL/NBA
  season at March 1; (3) any HTTP error on one sport calls `sys.exit(1)` and kills every sport after it in the run.
- `nfl/pipeline/pull_hardrock_props.py` requests `bookmakers=hardrockbet_fl` only, 10 markets, 15 credits per
  event; it is the VM's canonical props writer and rewrites one monthly parquet.
- Existing `data/odds_archive/nhl/props/` and `game_markets/` are the historical backfill, partitioned by CALENDAR
  year. New live data goes in NEW folders (`line_history/`, `event_markets/`), so the two are never mixed.

## Pre-check (Cowork)
- Runtime: seconds per call; event pulls sleep 1 s between events (~15 events -> ~15 s). No long jobs.
- Credits (100,000/month plan): tape +3 per NHL call x ~32 calls/day ≈ **96/day**. Event markets: cost = markets
  returned x 1 region-equivalent per event — MEASURE it (print `x-requests-last` per event); estimate ~15 per event x
  ~12-15 events x 2 slots ≈ **~400/day**. NFL props to 10 books: expected **unchanged** at 15/event — MEASURE it.
  Live tests in this order: tape dry-run (3), event-markets discovery on 2 events (~2), one real event pull (~15).
- Paths: `data/odds_archive/nhl/line_history/season=2026/snap_<ts>.parquet` (new),
  `data/odds_archive/nhl/event_markets/season=2026/snap_<ts>.parquet` (new), `research/layers/LAYERS_DECISION_v1.md`
  (new, entries L1-L4), `shared/pipeline/pull_event_markets.py` (new), tests under `shared/pipeline/tests/`.

```
Capture work order 12 (research/layers/capture_workorder12_nhl_2026-09-27.md). Branch eng/cap12 from origin/main in
a worktree (eng/5y is running in another session: do not touch nfl/sim/). Commit AND push each item before the next.
Each decision (L1-L4) goes into research/layers/LAYERS_DECISION_v1.md (create it; append at the end) in the same
commit as its code. Session log goes into logs/_log_cap12.txt (NOT logs/agent_sessions.md — two branches are open;
Cowork appends it at merge). Never print the API key. Commit no file larger than 2 MB. Never weaken a test.

Item 0 (L1) — the tape takes any sport safely. shared/pipeline/multi_book_open_capture.py.
  (a) Folder map: americanfootball_nfl -> nfl, americanfootball_ncaaf -> ncaaf, icehockey_nhl -> nhl,
      basketball_nba -> nba, baseball_mlb -> baseball_mlb (UNCHANGED — the MLB tape already lives there).
  (b) Season label: NHL and NBA use the season's START year (month >= 7 -> year, else year - 1): every 2026-27
      snapshot is season=2026. Football and MLB keep their current rule (no existing file moves).
  (c) Per-sport isolation: an HTTP/network error on one sport logs HARD STOP for that sport, writes nothing for it,
      continues with the others, and the process exits 1 at the end if any sport failed.
  Tests (new, network-free, mock requests): the four folder/season cases incl. 2027-03-15 NHL -> season=2026; a
  failing sport does not stop the next one and the exit code is 1. Each test must FAIL on the current file.
  Live check from the Mac: `--sports icehockey_nhl --dry-run` (3 credits). Print games returned, books returned,
  whether hardrockbet_fl is PRESENT and on how many games, x-requests-last.

Item 1 (L2) — multi-book event markets: every market the API has for a game. NEW shared/pipeline/pull_event_markets.py.
  Generalise the NFL props puller to any sport: --sport, --window-hours, --tag, --floor (default 3000), --dry-run,
  --markets (default: DISCOVERED). Same 10-book list as the tape (Hard Rock + Pinnacle + 8). Discovery: for each
  event in the window call GET /v4/sports/{sport}/events/{id}/markets with the 10 books and print, per book, the
  market keys offered (this is how we learn what Hard Rock offers for NHL — props, alternate lines, team totals,
  period markets). Default market set for icehockey_nhl = the union of keys Hard Rock OR Pinnacle offers, minus the
  three featured markets the tape already has. Pull GET /events/{id}/odds for those markets and books; cost
  pre-check before any paid call (events x markets, printed) and HALT below --floor; print x-requests-last per event.
  Append-only per-pull files: data/odds_archive/<folder>/event_markets/season=<S>/snap_<UTC ts>.parquet with columns
  snapshot_utc, sport, event_id, commence_time, home_team, away_team, bookmaker, book_last_update, market,
  outcome_name, description (player), point, price, tag. Only events not yet started.
  Tests (mocked): cost pre-check halts below the floor; started events excluded; rows carry the player name.
  Live: discovery on 2 NHL events (print the per-book market table in the report — Cowork needs it), then ONE real
  pull of ONE event with the discovered set; print rows by book x market and the credits it cost.

Item 2 (L3) — NFL props from 10 books, same cost. nfl/pipeline/pull_hardrock_props.py: request the tape's 10-book
  list instead of hardrockbet_fl only. Nothing else changes (markets, file, schema — the bookmaker column already
  exists). Live: one event with --window-hours small enough to pick one game; print rows per book and x-requests-last.
  PRE-REGISTER: cost per event unchanged (15). If it rises, report it and REVERT this item; do not keep it.

STOP after item 2 and report. Cowork verifies and Jeff merges eng/cap12 before item 3.

Item 3 (L4) — VM deploy. ONLY when Jeff says "deploy" after the merge. SSH root@142.93.242.4. Print the current
  crontab FIRST (it has never been read by Cowork) and the lines that run multi_book_open_capture.py and
  pull_hardrock_props.py. Then: git pull in /root/mlb-model; add icehockey_nhl to the tape's --sports on the SAME
  cadence as football (do not change football or MLB lines); add two NHL event-market slots, 16:00Z and 22:30Z,
  `--sport icehockey_nhl --window-hours 24 --tag open|close`. Do NOT add NBA yet (the NBA chat does that for
  preseason). Canonical-writer rule: nothing new on the Mac. Verify from FILES: after the next slot, the new
  snapshot files exist on origin with NHL rows and Hard Rock present; print the crontab diff.

Every item's report separates what the command RETURNED from what it MEANS and ends with NOT DONE and UNVERIFIED.
```
