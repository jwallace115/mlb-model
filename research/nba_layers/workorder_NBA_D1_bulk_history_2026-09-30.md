NBA — WORK ORDER NBA-D1: BULK ODDS-API HISTORY PULL, spend-today (written by Cowork's NHL edge-hunt chat for the NBA
chat, 2026-09-30). Plan is now 5M credits/month; today's balance does not roll over at 00:00 UTC 2026-10-01. The NBA
chat owns the decision entries (B-doc research/nba_layers/NBA_LAYERS_DECISION_v1.md); this order is DATA ACQUISITION
ONLY — no analysis, no model. Runs CONCURRENTLY with the NHL order E-WO2 (same account, shared balance).

Read first: CLAUDE.md (ODDS API COST MODEL, WORK ORDERS, ENVIRONMENT TRAPS); nhl/pipeline/pull_nhl_inplay.py and
nhl/pipeline/pull_nhl_history.py (reuse their request / parquet / resume code — write a sport-parameterised copy
under nba/pipeline/, do not fork a third puller style); claude/nba_layers_handoff.md (the NBA archive has NO
Pinnacle history and no live tape — this order is the first Pinnacle NBA history the repo will hold).

Worktree ~/mlb-model-nbaD, branch nba/data-d1 from origin/main. Data under data/odds_archive/nba/history/** is
GITIGNORED (add the .gitignore line in Item 0 if absent). Path rule: `nba`, NOT `basketball_nba` (the capture
script's path rule strips only `americanfootball_` — the NBA handoff flags this; use the NHL layout exactly).

BOOKS (binding): `bookmakers=pinnacle,draftkings,fanduel,betmgm,williamhill_us,betrivers,bovada,pointsbetus,
unibet_us,betonlineag` — exactly 10 keys = ONE region-equivalent; an 11th doubles every call. Never mybookieag or
barstool. Verify on the first call that x-requests-last == 10 × markets; if not, STOP.

BUDGET (binding): print x-requests-remaining before the first call and after every call. SPEND CAP for this order
= 2,400,000 credits (header deltas). GLOBAL FLOOR = 5,000 remaining: stop the moment remaining < 5,000 or the cap
is reached; commit; report. 4 concurrent workers, exponential backoff on 429/5xx (2 s → 60 s), measure calls/s in
the first 200 calls and print the projected finish per item. Resume-safe: existing files are never re-requested.
Sport key: basketball_nba. Seasons: start year (2022 = 2022-23, …). Regular season only (playoffs excluded by
date range from the schedule).

ITEM 0 — schedule + event ids (free): NBA regular-season dates and game list per season 2022-23..2025-26 from the
repo's games.parquet / box_stats.parquet where present (they end 2025-04-13 per the NBA handoff) and the NBA
schedule endpoint for the rest; commit the date lists. The first sport-level historical call per season (Item 1)
yields event ids for the day; collect them into data/odds_archive/nba/history/events_<season>.parquet as you go.

ITEM 1 (B-D1) — DENSE PRE-MATCH + CLOSE: hourly sport-level snapshots (h2h, spreads, totals; 30 credits per call),
every regular-season day, 00:00Z-23:00Z, seasons in PRIORITY ORDER 2024-25 → 2025-26 → 2023-24 → 2022-23.
≈ 170 days × 24 × 30 ≈ 122k per season; four ≈ 490k. Output data/odds_archive/nba/history/lines_hourly/
season=<yr>/snap_<requested>.parquet + .json.gz (NHL schema + `book_last_update`). This is the item that gives the
NBA chat Pinnacle closes and CLV for the first time.

ITEM 2 (B-D2) — PROPS at two pre-match snapshots (T−24 h, T−1 h) per event, seasons 2024-25 → 2025-26 → 2023-24
(historical event odds from 2023-05-03). Markets: player_points,player_rebounds,player_assists,player_threes,
player_points_rebounds_assists,player_double_double,player_blocks,player_steals (8 → 80 credits per
event-snapshot; ≈ 1,230 × 2 × 80 ≈ 197k per season; three ≈ 590k). Output data/odds_archive/nba/history/props/
season=<yr>/<event_id>_<T-24h|T-1h>.parquet. Absent markets are still charged — record empty, never retry.

ITEM 3 (B-D3) — IN-PLAY, 5-minute cadence, every game night, seasons 2024-25 → 2025-26 → 2023-24: sport-level
h2h+spreads+totals (30 credits) from (earliest tip − 5 min) to (latest tip + 3 h), ≈ 170 nights × ~60 × 30 ≈ 306k
per season; three ≈ 920k. Output data/odds_archive/nba/history/inplay/season=<yr>/snap_<requested>.parquet
(+ json.gz, + `book_last_update`).

ITEM 4 (B-D4) — DERIVATIVE MARKETS at T−24 h and T−1 h, seasons 2024-25 → 2025-26 → 2023-24: markets
h2h_h1,spreads_h1,totals_h1,h2h_q1,spreads_q1,totals_q1,team_totals,alternate_spreads (8 → 80 per event-snapshot;
≈ 197k per season; three ≈ 590k). Output data/odds_archive/nba/history/event_markets/season=<yr>/
<event_id>_<T-24h|T-1h>.parquet. Lowest priority.

NULL CONTROLS: (a) Item 1: for 20 random events, the T−1 h hourly snapshot's DraftKings h2h price must equal the
existing March-2026 backfill's price where both exist (data/odds_archive/nba/, per the NBA handoff) within the
snapshot gap — paste the max difference; (b) every parquet re-read must give the same row count as its json.gz's
outcomes (spot-check 50 files).

CLOSING (after every item AND on any stop): append "NBA-D1" to logs/agent_sessions.md (git add -f): per item —
calls, credits spent (header delta), remaining, files saved, achieved calls/s, wall time; null controls with
numbers; NOT DONE; UNVERIFIED. Decision entries are the NBA chat's (B-numbers) — write ONE data-facts entry per
item in research/nba_layers/NBA_LAYERS_DECISION_v1.md in the same commit (what was pulled, cost, granularity, gaps),
no interpretation. Push. Do not merge. Disk ≈ 8-10 GB; print `du -sh` at the end.
