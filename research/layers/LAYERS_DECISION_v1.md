# LAYERS DECISION LOG

Decisions are numbered L1, L2, ... and appended in commit order.
Each entry names the code it ships with.

---

### L1 — tape takes any sport safely (2026-09-27)

**What changed:** `shared/pipeline/multi_book_open_capture.py` — three fixes:

1. **Folder map.** Replaced `sport.replace("americanfootball_", "")` with an explicit
   `FOLDER_MAP` dict: `icehockey_nhl -> nhl`, `basketball_nba -> nba`,
   `baseball_mlb -> baseball_mlb` (unchanged). Unknown sports raise `KeyError`.

2. **Season label.** NHL and NBA use start-year rule (month >= 7 -> current year,
   else previous year). A snapshot at 2027-03-15 for `icehockey_nhl` -> `season=2026`.
   Football and MLB keep month >= 3 (unchanged; no existing files move).

3. **Per-sport isolation.** `pull()` returns `None` on failure instead of `sys.exit(1)`.
   `main()` collects failed sports, continues with the rest, and exits 1 at the end
   if any sport failed. A healthy sport always writes its data.

**Tests:** 19 new tests in `shared/pipeline/tests/test_multi_book_capture_l1.py` — all
network-free (mock `requests.get`). Cover folder map (5 sports + unknown), season label
(11 cases incl. NHL March -> prev year), and isolation (HTTP 404 + network error both
allow subsequent sports to write).

**Live check (Mac, dry-run, 3 credits):**
- `icehockey_nhl`: 33 games, 9 books returned, `hardrockbet_fl` ABSENT (preseason not
  posted yet — first puck 2026-09-29), `x-requests-last=3`.

---

### L2 — multi-book event markets for any sport (2026-09-27)

**New file:** `shared/pipeline/pull_event_markets.py`

Generalises event-level market capture to any sport. Uses the same 10-book list as the
tape. Flow: (1) get events in window (free), (2) discover available markets via
`GET /events/{id}/markets` (1 credit), (3) compute default set = union of Hard Rock +
Pinnacle minus tape markets (h2h/spreads/totals) minus `--exclude-prefix`, (4) cost
pre-check (events x markets), (5) pull odds per event.

**Output:** `data/odds_archive/<folder>/event_markets/season=<S>/snap_<ts>.parquet`
with columns: snapshot_utc, sport, event_id, commence_time, home_team, away_team,
bookmaker, book_last_update, market, outcome_name, description, point, price, tag.

**Tests:** 5 mocked tests in `shared/pipeline/tests/test_pull_event_markets_l2.py`:
cost pre-check halt, started-event exclusion, player description propagation,
exclude-prefix filtering, HR+Pinnacle union logic.

**Live discovery (Mac, 8 credits total):**

NHL (FLA@CAR, MTL@TOR) — Hard Rock: 0 markets (preseason). Pinnacle: 22 markets
(period spreads/totals, alternates, 3-way, OT). No player props for NHL preseason.

NFL (LAC@BUF, CAR@CLE) — Hard Rock: 76 markets. Pinnacle: 26 markets. DraftKings: 102.
Per-book table in session log. NFL has full player prop coverage across all 10 books.

**One real NHL pull (FLA@CAR, 19 discovered markets):**
- x-requests-last = 19 (confirms cost = 1 per market per event)
- 141 rows, 9 books returned. Pinnacle richest (70 rows across 19 markets).
  Hard Rock absent (preseason). Bovada 2nd (21 rows, 8 markets).

**Cost model confirmed:** discovery = 1 credit/event, pull = markets/event.
