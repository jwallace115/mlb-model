# NBA Layers — work order 2b: capture NBA player props, fix L3 history, correct the cron proposal (2026-10-01)

Written by Cowork after verifying WO2 (`research/nba_layers/wo2_verification_2026-10-01.md`). Same branch nba/wo2.

Pre-check:
- Runtime: tests seconds. Item 2's real packet build must drop from ~1,500 ESPN calls to one pass over the season's
  dates with a disk cache: first build of a March slate ~150 calls x ~0.3 s ~= 45-60 s; rebuilds ~0 calls.
- Credits: item 1 discovery (`/events/{id}/markets`) 1 credit per call x 2 events; ONE real pull of ONE event with
  the new market set = markets x 1 (expect ~10-20). Steady state is re-estimated from the measured number.
- Paths: unchanged from WO2; ESPN cache `nba/data/outcomes_cache/` (gitignored, created in B9).
- Shared file: `shared/pipeline/pull_event_markets.py` — default behavior for NHL/NFL/NCAAF must not change.

```
NBA WO2b. Fresh session in ~/mlb-model. Read CLAUDE.md (WORK ORDERS, ENVIRONMENT TRAPS, ODDS API COST MODEL), then
~/mlb-model/research/nba_layers/wo2_verification_2026-10-01.md and this file (both UNTRACKED in the main checkout —
copy both into the worktree's research/nba_layers/ in your first commit). Use the EXISTING branch nba/wo2 (worktree
~/mlb-model-nba2; recreate from origin/nba/wo2 if missing). Never switch the main checkout. Commit AND push each item
(`git pull --rebase --autostash && git push`); B11/B12 appended at the END of the decision doc in the same commit.
Every new test must FAIL on cbeb7a0d4 by running the OLD logic (not by ImportError) — paste the failure. Before each
push run `git log origin/main -1 -- shared/pipeline/pull_event_markets.py nfl/pipeline/log_ai_opinions.py`; if it
moved since your branch point, STOP. Install no cron. Do not merge.

Item 1 (B11) — NBA player props in the event-market capture.
  a) `compute_market_set` gains a per-sport policy, default unchanged (union of hardrockbet_fl + pinnacle). For
     basketball_nba and basketball_nba_preseason: union of markets offered by ANY of the 10 BOOKS, minus the tape
     markets, keeping `player_*` plus alternate_spreads, alternate_totals, team_totals; drop `*_alternate` player
     ladders unless Hard Rock or Pinnacle offers them. Print the per-book table and the final set.
     TEST: on a discovery fixture cut from a REAL /markets response (save it from the live call in b), NBA's set
     contains player_points/player_rebounds/player_assists when only FanDuel/DraftKings list them — must FAIL on
     cbeb7a0d4's HR+Pinnacle rule. NULL: NHL and NFL sets from the same function on their own real fixtures (or a
     synthetic one if none on disk — say which) are byte-identical to cbeb7a0d4's output.
  b) Live: discovery on 2 basketball_nba events (opening week), then ONE real pull of ONE event: rows by book x market,
     x-requests-last, remaining. PRE-REGISTER: cost = number of markets requested (1 per market per event, 10 books =
     1 region); at least player_points is offered by >= 2 books.
  c) B11 records the market set, measured cost/event, and the daily estimate: (tape) + (event markets: games x markets
     x 2 slots).

Item 2 (B12) — L3 history: one cached pass, regular season only, failures visible.
  a) nba_outcomes.fetch_scoreboard returns `season_type` (ESPN event season.type: 1 pre, 2 regular, 3 post, 5 play-in
     or as ESPN labels it — print the values seen) and reads/writes the B9 disk cache (finals only are cached; a date
     with any non-final game is not cached).
  b) build_packet_nba computes L3 ONCE per slate for all teams from season start (first regular-season date, not
     Oct 15) to slate_date - 1, regular-season finals only. A date whose fetch fails is listed in the layer as
     `"dates_failed": [...]` and the packet header gets `"l3_complete": false`; the builder exits non-zero if any date
     failed, unless `--allow-incomplete-history` (then the flag stays in the packet for the reader to see).
  c) TESTS (nba/layers/tests/test_packet_nba_b12.py): a preseason final on Oct 16 is NOT counted (must FAIL on
     cbeb7a0d4); a fetch error on one date surfaces in dates_failed and the exit code (must FAIL on cbeb7a0d4, which
     swallowed it); call count for a 10-game slate equals the number of dates, not games x dates (instrument the fetch).
  d) Rebuild the 2026-03-16 packet; paste call count and wall time for a cold and a warm (cached) build; the L3 for
     ATL and ORL must equal a count from nba/data/nba_results_log.parquet + predictions_4b actual scores where they
     overlap (print both; differences listed, not patched).

Item 3 (B13) — Corrected cron proposal (text only). SSH to the VM, print the CURRENT crontab lines that run
  multi_book_open_capture.py and pull_event_markets.py (read only). Propose: add basketball_nba and
  basketball_nba_preseason to the EXISTING tape line's --sports (same cadence as football — do not create a 24-hour
  line); event markets 16:00Z `--tag open` (noon ET) and 21:40Z `--tag close` (after the 5:30 pm ET report). Write the
  exact before/after lines into B13. Do not install.

Closing: session log (git add -f logs/agent_sessions.md): RETURNED vs MEANS, NOT DONE, UNVERIFIED. Push. STOP.
```
