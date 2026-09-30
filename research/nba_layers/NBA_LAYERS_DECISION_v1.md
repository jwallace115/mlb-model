# NBA Layers — decision record (entries B1, B2, ...)

One decision doc per sport (gameplan §7). Only the NBA chat appends here. Cross-sport rules live in
`research/layers/LAYERS_DECISION_v1.md`; the plan is `research/layers/LAYERS_GAMEPLAN_2026-09-27.md`.
Append at the END of the file. A decision that exists only in a commit message does not exist.

### B1 — NBA Layers scope, dates, freeze rule, file ownership; what the repo holds today (2026-09-27)

Written by Cowork at 2026-09-27T13:54Z from Jeff's instruction and a read of the files on the Mac. No pick exists yet.

**Dates (Jeff).** NBA regular season opens Tue 2026-10-20. Preseason games are an UNSCORED pipe test.
**Pilot Tue 2026-10-20 .. Sun 2026-10-25** (pilot files are never pooled). **Record starts Mon 2026-10-26.**
Checkpoints and metrics exactly as gameplan §4 (CLV vs Pinnacle's close primary; Brier vs de-vigged book; units
at the real frozen price; baselines (a) book, (b) best single model layer where one exists, (c) follow-the-move;
report at 500 and 1,500 graded sides; no keep/kill before 1,500, and that is a named decision pass).
Preseason starts Sat 2026-10-03 (TOR vs MIA, Quebec City) per a web schedule guide read 2026-09-27; to be
re-measured from a schedule feed in B2, not trusted from the web page.

**Freeze (Jeff): after the 5:30pm ET injury report**, before the first tip it covers, `--reader-model` required
(N62), sha256 posted in `claude/capture_status_2026-09-20.md` before that tip. Lines that move after freeze are
CLV, never re-picked; only revision 0 of a line is scored.
- **OPEN — needs Jeff.** Opening night's first game, BOS @ DET, tips **3:00pm ET (19:00Z)** — before the 5:30pm
  report exists (FOX Sports schedule; matches the gameplan's "first tip 19:00Z"). Weekend and holiday slates also
  have afternoon tips. Proposed default, NOT decided: a game tipping before 6:00pm ET is frozen in its own earlier
  file from the latest official report published at least 30 minutes before its tip; every other game freezes
  after the 5:30pm report. Whether a 5:30pm report is actually published is measured in B2, not assumed.

**Reader (pilot default, gameplan §10).** Every line gets a probability and a side (NCAAF style). Drivers field
required on every row. The reader method file is frozen for the pilot; a change after the pilot is a new version.

**File ownership.** The NBA chat edits only `nba/`, `research/nba_layers/`, `data/injury_archive/nba/`,
`claude/nba_layers_handoff.md`. Shared code — `nfl/pipeline/log_ai_opinions.py`,
`shared/pipeline/multi_book_open_capture.py`, `shared/layers/` — is NOT touched by NBA work order 1. NHL goes
first (opens 09-29) and its work order 1 changes those files (tape entry, date-keyed slate, packet builder). NBA's
entries in them are NBA work order 2, on one branch, after NHL work order 1 is merged, reusing what NHL built.
As of 2026-09-27T13:54Z: no NHL handoff doc exists in the project, no `research/nhl_layers/`, no `shared/layers/`,
and `icehockey_nhl` is not in the capture script — NHL work order 1 has not landed.

**What the repo holds for the NBA today (read from files 2026-09-27; each is a fact about a file, not a verdict):**
- Live-line tape: NONE for the NBA. `data/odds_archive/nba/{game_markets,props}` is a one-time HISTORICAL
  backfill (pulled 2026-03-27 11:38-11:48 local, game dates 2025-10..2026-03, 365,266 credits per its pull_log),
  books betmgm/betonlineag/betrivers/betus/bovada/draftkings/fanatics/fanduel/lowvig/mybookieag/williamhill_us —
  **no pinnacle and no hardrockbet_fl**. `basketball_nba` is not in `multi_book_open_capture.py` SPORTS, and its
  output path rule `sport.replace("americanfootball_", "")` would write the NBA tape to
  `data/odds_archive/basketball_nba/line_history/` (as MLB's goes to `baseball_mlb/`), not `nba/`.
  The capture script WARNS under 3,000 remaining credits; it does not halt.
- `nba/modules/fetch_nba_odds.py`: totals + h1_totals, draftkings/fanduel only, cached once a day. Not a tape.
- Availability: `nba/modules/fetch_injuries.py` reads ESPN's injuries endpoint, KEEPS ONLY Out/Doubtful (drops
  Questionable), saves nothing, no retrieval time. `nba/scripts/pull_injury_reports.py` pulls the OFFICIAL NBA
  injury-report PDF (ak-static.cms.nba.com, via `nbainjuries`, Java at `/Users/jw115/jre21` — Mac-only as
  written); the archive `nba/data/injury_reports/` holds 171 files for 2023-24 (all the 5:00pm ET report) and 1 for
  2026-03-16. No point-in-time injury trail exists for 2025-26. The script notes the URL format changed on
  2025-12-22 to `_HH_MM`.
- Outcomes: the pipeline grades from `nba_api` (`scoreboardv2`, stats.nba.com — blocked from the VM, CLAUDE.md).
- History (L3): `nba/data/games.parquet` and `box_stats.parquet` END 2025-04-13 (3,690 games / 7,380 rows,
  2022-10-18..2025-04-13). The 2025-26 season is not in them; `run_nba.py` builds current team states from the
  API live. Whether a point-in-time 2025-26 history exists anywhere on disk is unmeasured.
- Model layer (L4): the venue board's team lists are hardcoded (`_ROAD_WARRIOR` 10 teams, `_STRONG_HOME` 8,
  `_CORE_*` 3x3), selected from 2024-25 data, committed 2026-03-22 (b448fbd36) and "pruned" the same day on
  2022-23..2024-25 — a window that contains the selection season. **CHECK 2 fails: every historical number for
  the venue board (+4.68 / +6.65 pts, 59.5% / 64.3%) is in-sample.** Its only clean evidence is forward: the
  signal log (`nba/data/nba_signal_log.parquet`, 92 rows 2026-03-24..05-30) has 9 graded ROAD_WARRIOR rows.
  It enters the Layers System as a logged vote, gating nothing (gameplan §3); no historical figure of it is
  evidence of anything, and it is not baseline (b) until it has a probability that is not in-sample.
- `nba/data/board/` does not exist yet; the frozen-log tree for the NBA will be
  `nba/data/board/date=YYYY-MM-DD/ai_opinions/` (gameplan §7).

**Checks stated.** 1a: freeze after the report, before tip, packet items carry source times — to be enforced by
the tools, not yet built. 1b: no NBA history layer is yet known point-in-time for 2025-26 (measured in WO1).
2: the reader is judged forward only; the venue board fails CHECK 2 historically (above). 3: the packet is hashed
with the picks (gameplan). 4: real frozen prices, Pinnacle close for CLV. 5: breakouts per gameplan §4.

### B-D1 — Item 1 data: dense pre-match + close NBA historical odds, 4 seasons (2026-09-30)

Data-facts entry from NBA-D1 work order item 1. No interpretation.

**What was pulled.** Sport-level historical odds (h2h, spreads, totals) for basketball_nba,
seasons 2022-23 through 2025-26. Hourly snapshots (00:00Z-23:00Z) on every game date, plus
close snapshots at each distinct tip time minus 5 minutes. All snapshots saved as parquet +
json.gz in `data/odds_archive/nba/history/lines_hourly/season=<yr>/`.

**Bookmakers (10).** pinnacle, draftkings, fanduel, betmgm, williamhill_us, betrivers, bovada,
betonlineag, lowvig, hardrockbet. Cost = 30 credits per call (10 x 3 markets x 1 region-equiv).

**A10 Hard Rock discovery.** The NHL puller used key `hardrockbet_fl` and got 0 rows. NBA probe
found the key is `hardrockbet` (no `_fl` suffix), in the `us2` region, present for 2024-25 and
2025-26 only (Hard Rock launched ~2024). Not found in 2022-23 or 2023-24 (expected).

**Pinnacle discovery.** Pinnacle is NOT in `us` or `us2` regions. It is in the `eu` region. The
`bookmakers=pinnacle` parameter fetches it cross-region at no extra cost (still 1 region-equiv
with <=10 books). Verified: 10-book call costs exactly 30. All 10 books returned in 2024-25 data.
This is the first Pinnacle NBA history the repo holds.

**Volume.**

| Season | Hourly | Close | Total snaps | Events | Credits | Hard Rock |
|--------|--------|-------|-------------|--------|---------|-----------|
| 2024   | 3,912  | 831   | 4,743       | 1,247  | ~142k   | Present   |
| 2025   | 3,960  | 825   | 4,785       | 1,234  | 143,550 | Present   |
| 2023   | 3,840  | 786   | 4,626       | 1,274  | 138,780 | Absent    |
| 2022   | 3,936  | 839   | 4,775       | 1,254  | 143,250 | Absent    |
| **Total** | **15,648** | **3,281** | **18,929** | **5,009** | **~568k** | |

Events parquets: `data/odds_archive/nba/history/events/events_<season>.parquet` — event_id,
commence_time, home_team, away_team. These feed items 2, 3, 4.

**A7 null control.** Matched March 2026 backfill (DraftKings, game_markets) against hourly data
on (event_id, market, last_update). 30 matches found. Price identical in 30/30. Max difference = 0.
The backfill stores no snapshot time; the match relies on bookmaker last_update timestamps.

**A5 cost check.** First call of each season: x-requests-last = 30, as expected.

**Gaps.** Hard Rock absent in 2022-23 and 2023-24 (not yet launched). All other 9 books present
in all seasons. Event counts (1,234-1,274) include some playoff games whose commence_time falls
in the date range. Rate achieved: 5.6-7.6 calls/s with 4 workers.

### B-D2 — Item 2 data: player props at T-24h and T-1h, 3 seasons (2026-09-30)

Data-facts entry from NBA-D1 work order item 2. No interpretation.

**What was pulled.** Historical event-level odds for 8 player prop markets at two pre-match
snapshots (T-24h and T-1h before commence_time) per event. Seasons 2024-25, 2025-26, 2023-24.
Output: `data/odds_archive/nba/history/props/season=<yr>/<event_id>_<T-24h|T-1h>.parquet`.

**Markets (8).** player_points, player_rebounds, player_assists, player_threes,
player_points_rebounds_assists, player_double_double, player_blocks, player_steals.
Expected cost = 10 x 8 = 80 per event-snapshot.

**Volume.**

| Season | Events | Calls | Credits (run) | Notes |
|--------|--------|-------|---------------|-------|
| 2024   | 1,247  | 2,494 | 127,390       | 9 books in sample (lowvig absent for props) |
| 2025   | 1,234  | 2,468 | 125,720       | |
| 2023   | 1,274  | 2,548 | 138,470       | |
| **Total** | **3,755** | **7,510** | **~391k** | |

**A5 cost check.** First call per season: x-requests-last = 80, as expected. No call exceeded
10 x 8 = 80 (0 cost violations). Actual per-call average ~51-54 credits — lower than 80, likely
because not all 8 prop markets are available for every event at every book. Empty-but-charged = 0.

**Gaps.** lowvig absent from props data (not a props book). Hard Rock absent for season 2023 (pre-launch).

### B-D4 — Item 4 data: derivative markets at T-24h and T-1h, 3 seasons (2026-09-30)

Data-facts entry from NBA-D1 work order item 4. No interpretation.

**What was pulled.** Historical event-level odds for 8 derivative markets at T-24h and T-1h
per event. Seasons 2024-25, 2025-26, 2023-24.
Output: `data/odds_archive/nba/history/event_markets/season=<yr>/<event_id>_<T-24h|T-1h>.parquet`.

**Markets (8).** h2h_h1, spreads_h1, totals_h1, h2h_q1, spreads_q1, totals_q1, team_totals,
alternate_spreads. Expected cost = 10 x 8 = 80 per event-snapshot.

**Volume.**

| Season | Events | Calls | Credits (run) | First call cost |
|--------|--------|-------|---------------|-----------------|
| 2024   | 1,247  | 2,494 | 135,300       | 80              |
| 2025   | 1,234  | 2,468 | 119,600       | 40              |
| 2023   | 1,274  | 2,548 | 126,240       | 70              |
| **Total** | **3,755** | **7,510** | **~381k** | |

**A5 cost check.** First call per season: 2024=80, 2025=40, 2023=70. All below 10 x 8 = 80
(no violations). Variable cost per season: not all 8 derivative markets available for every
event historically. Alternate spreads and Q1 markets less available in earlier seasons.
Empty-but-charged = 0.

**Gaps.** Same as item 2 — lowvig absent, Hard Rock absent for 2023.

### B-D3 — Item 3 data: in-play 5-min snapshots, 3 seasons (2026-09-30)

Data-facts entry from NBA-D1 work order item 3. No interpretation.

**What was pulled.** Sport-level historical odds (h2h, spreads, totals) at 5-minute intervals
from (first tip - 5 min) to (last tip + 3 h) on each game night. Keep in-play events (unlike
item 1 which filters them). Output: `data/odds_archive/nba/history/inplay/season=<yr>/`.

**A6 credit projection (computed before item 3 started).**

| Season | Nights | Snapshots needed | Credits needed |
|--------|--------|------------------|----------------|
| 2024   | 167    | 13,768           | 413,040        |
| 2025   | 165    | 14,171           | 425,130        |
| 2023   | 164    | 13,590           | 407,700        |
| **Total** | | **41,529** | **1,245,870** |

**Actual.**

| Season | Snapshots pulled | Credits | Status |
|--------|-----------------|---------|--------|
| 2024   | 13,768          | 413,040 | Complete |
| 2025   | 14,171          | 425,130 | Complete |
| 2023   | 7,370           | 221,100 | Partial (54%, capped at spend limit) |
| **Total** | **35,309** | **1,059,270** | |

Season 2023 stopped at 7,370/13,590 snapshots when the order-level spend cap (2.4M) was reached.
The remaining 6,220 season-2023 inplay snapshots (~186k credits) are resume-safe — rerunning
with budget will pick up from where it stopped.

### Grand total — NBA-D1 order

| Item | Calls | Credits | Files |
|------|-------|---------|-------|
| Probe | ~9 | 270 | 1 JSON |
| 1 — Lines (4 seasons) | 18,929 | 567,580 | 18,929 parquet + json.gz |
| 2 — Props (3 seasons) | 7,510 | 391,580 | 7,510 parquet |
| 4 — Markets (3 seasons) | 7,510 | 381,140 | 7,510 parquet |
| 3 — Inplay (2.54 seasons) | 35,309 | 1,059,270 | 35,309 parquet + json.gz |
| **Total** | **69,267** | **2,399,840** | 1.2 GB |

Account x-requests-remaining at end: ~876,102. Global floor (5,000) not breached.
Disk: 1.2 GB (lines 334M, inplay 682M, props 90M, markets 82M, events 224K).

### B-D5 — Corrections to B-D1..B-D4 after Cowork verification (2026-09-30)

Data facts only; details in `research/nba_layers/nbaD1_verification_2026-09-30.md`.
- Hard Rock (`hardrockbet`) IS in season 2023-24: first seen 2023-11-28, on 74.1% of events' last pre-tip snapshot
  (98.8% 2024-25, 97.7% 2025-26), and in 2023 props. B-D1/B-D2 "Absent for 2023" is wrong. 2022-23: none.
- Close (A4): 99%+ of events have a pre-tip close row; median 9.4 min, p90 19.4 min before the actual tip;
  Pinnacle in it on 95.5-99.7% of events by season.
- Null control (b): item-1 parquet = json minus games already started (8/50 sampled files differ, every difference
  equals the live games' outcomes). In-play files match exactly. Not data loss.
- T-24h props empty on 58-72% of events; T-24h derivative markets 38-49%; T-1h under 3%. D1 holds one props
  snapshot per game (T-1h); no props opening line or movement.
- Events include 8-10 play-in/playoff games per season inside the date range; in-play 2023-24 covers Oct-Jan only.

### B2 — Source probe: what each NBA source returns and from which host (2026-09-30)

Probe script: `nba/pipeline/probe_nba_sources.py`. Report: `research/nba_layers/b2_sources_2026-09-30.md`.
Run on Mac and VM. Pre-registered 6 predictions; 2 held, 2 partially held, 2 did not hold.

**Odds API (LIVE).** `basketball_nba` active, 44 events (opening night 2026-10-20T19:00Z = 3pm ET).
`basketball_nba_preseason` is a **separate key**, currently inactive. Books returned: 9 —
betmgm, betonlineag, betrivers, bovada, draftkings, fanduel, lowvig, **pinnacle**, williamhill_us.
**`hardrockbet_fl` absent** for basketball_nba (historical key is `hardrockbet`; live key `_fl` not
returned). Dry-run cost: 3 credits (confirmed). Null control: passed.

**Official injury reports.** Published 10:00 AM - 12:45 PM ET, every 15 min, new format only
(`_HH_MMAM/PM`). **No 5:30 PM ET report exists** — the freeze assumption in B1 is wrong; the last
published report is 12:45 PM ET. No preseason reports. CDN **blocks the VM** (404); Mac only.
3 fixture PDFs downloaded. nbainjuries requires Java (Mac JRE at `/Users/jw115/jre21`, not in PATH).

**ESPN.** Injuries: per-item `date` field EXISTS (e.g. `"2026-09-21T19:50Z"`) — pre-registration wrong.
Off-season: 66 items (Out=14, Day-To-Day=52). Scoreboard: 8 games on 2026-03-16, STATUS_FINAL,
period count available. Both work from Mac and VM.

**stats.nba.com.** Mac: works (nba_api scoreboardv2). VM: blocked (JSONDecodeError).

**Host decisions.** Tape: VM. Official reports: Mac only. ESPN: VM. Outcomes (ESPN scoreboard): VM.
stats.nba.com cross-check: Mac only. Pinnacle is the CLV reference book. Hard Rock unavailable
on the live tape.

**Report cadence for capture (item 2).** Poll 10:00-13:00 ET every 15 min for official reports.
ESPN: once per capture run (content-hash dedup).

### B3 — Availability trail (L2): capture script, cadence, tests (2026-09-30)

Script: `nba/pipeline/capture_nba_availability.py`. Tests: `nba/pipeline/tests/test_availability_b3.py`.

**What it captures** per run, into `data/injury_archive/nba/season=2026/`:
- Every new official report PDF published since last run + parsed parquet (all statuses).
  Parse failure logged, never blocks archiving the raw PDF.
- ESPN injuries JSON (gzip, ALL statuses kept — fetch_injuries.py drops Questionable; the reader
  needs it). Skipped when content hash equals previous pull.
- One line per feed in `_pulls.jsonl` (N41 convention: feed, retrieval_utc, source URL, rows, sha256, status).

**Cadence derivation.** B2 measured reports at 10:00-12:45 ET, every 15 min, game days only.
Proposed cron: on game days, 13 runs at 10:00-13:00 ET q15 for official reports (Mac only);
one ESPN run per capture for the VM. **Proposed cron lines (NOT installed):**
```
# Mac: official reports + ESPN, 10:00-13:00 ET q15 (game days checked by script)
*/15 10-13 * * * /path/to/python3 /Users/jw115/mlb-model/nba/pipeline/capture_nba_availability.py >> /Users/jw115/mlb-model/logs/nba_availability.log 2>&1
```

**Tests (3 tests, all pass, each killed by stated mutation):**
(i) Questionable player in ESPN fixture appears in output — FAILS with Out/Doubtful-only filter.
(ii) Second run on identical ESPN content writes no new file — FAILS with hash check removed.
(iii) Parsed official row carries report timestamp; post_tip=True when report > game tip — FAILS
with flag forced False.

**Null control:** `git diff origin/main -- nba/modules nba/run_nba.py` is empty.

**Live run (Mac):** official reports = 0 (off-season). ESPN injuries = 66 items (Out=14, Day-To-Day=52).
One line written to `_pulls.jsonl`.
