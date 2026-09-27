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

---

### L3 — NFL props from 10 books (2026-09-27)

**Changed:** `nfl/pipeline/pull_hardrock_props.py`

1. **10-book list.** `bookmakers=` now uses the tape's 10-book list instead of
   `hardrockbet_fl` only. The `bookmaker` column already existed in the schema.

2. **Cost pre-check fix.** Was hardcoded `len(window) * 15 + 1`. Now computed from
   `len(MARKET_LIST)` (= 10 markets = 10 credits/event). Matches Jeff's measured
   `x-requests-last = 10` from 2026-09-27.

3. **--floor and --out-dir args.** `--floor` replaces hardcoded HALT_THRESHOLD in the
   check. `--out-dir` writes to a scratch path (canonical-writer rule: Mac must not
   write to the monthly file the VM also writes).

**PRE-REGISTRATION:** cost per event stays at 10 with 10 books.
**RESULT:** CONFIRMED. Every event returned `x-requests-last=10`. Cost is driven by
market count (10), not book count. Adding 9 books cost zero additional credits.

**Live test (Mac, 11 events, scratch path, 110 credits):**
- x-requests-last = 10 on all 11 events
- 6,391 rows across 9 books (lowvig absent — no props)
- hardrockbet_fl: 756 rows. bovada: 1,236. pinnacle: 557.
- Written to /tmp/nfl_props_scratch/ (not the monthly file).

---

### L2 amendment — conf, conf_rank, edge in freeze; conf bands in score (2026-09-27)

**Amended:** `nfl/pipeline/log_ai_opinions.py` per Jeff's reader_method_v1.md.

**Freeze changes:**
1. `conf` (0-100) and `conf_rank` (1 = best bet, unique per file, no gaps) are REQUIRED
   on every new freeze. Validation: conf in [0,100], conf_rank = 1..N with no duplicates
   or gaps.
2. `edge` computed by the tool: reader probability of its chosen side minus the book's
   de-vigged probability of that same side. For side "first": edge = p_first - book_p_first.
   For side "second": edge = (1 - p_first) - (1 - book_p_first). For side "none": edge = 0.
3. NHL added to SPORTS dict (book: pinnacle, require_side: True). NHL rows refuse
   side "none" — every line must have a side (no no_view tag allowed).
4. Football/NCAAF: `require_side: False` — old files without conf stay valid; new files
   carry conf/conf_rank/edge.

**Score changes:**
1. `conf_band` column: 1-10, 11-25, 26-50, 51+ — added to breakout tables.
2. `edge_rank`: rank by descending edge. Report compares conf_rank vs edge_rank on
   the same bands (pre-registered: band 1-10 should beat the rest on CLV/units).
3. `postfreeze_<UTC>.csv` read as reporting cut only: marks `postfreeze_affected` on
   rows whose `event_id` matches the CSV's `game` column. Never changes a grade or
   removes a row. Reported as "touched vs untouched" in the score report.

**Tests:** 12 new in `nfl/pipeline/tests/test_ai_opinions_conf_l2.py` + 10 existing
pass unchanged (conf/conf_rank added to test helper `_filled()`). Total: 22/22 green.
