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

### B4 — Outcomes loader and settlement rules (2026-09-30)

Loader: `nba/pipeline/nba_outcomes.py`. Tests: `nba/pipeline/tests/test_outcomes_b4.py`.
Shape follows `nhl/pipeline/nhl_outcomes.py`: home, away, home_score, away_score, periods, went_to_ot, status.
Source: ESPN scoreboard (VM-reachable per B2). nba_api is Mac-only cross-check.

**Team map.** 30 Odds API full names -> internal abbreviations (matches results log, games.parquet).
ESPN displayName -> same abbreviations. One divergence: ESPN uses "LA Clippers", Odds API uses
"Los Angeles Clippers". Both map to LAC. All 30 names verified mapped (test_all_30_odds_api_names_map).

**Grading vs nba_results_log.parquet (194 rows, 2026-03-14..2026-04-12).**
PRE-REGISTERED: 194/194 totals agree, every went_to_ot row has periods > 4.
**RESULT: 191/194 agree. 3 mismatches (DID NOT HOLD):**

| Date | Game | Issue | Investigation |
|------|------|-------|---------------|
| 2026-03-30 | DET vs OKC | ESPN=OT, log went_to_ot=0.0 | Log failed to record OT |
| 2026-04-06 | DEN vs POR | ESPN periods=5 (OT), log went_to_ot=0.0 | Log total=269 (correct incl OT), went_to_ot flag wrong |
| 2026-04-07 | PHX vs HOU | ESPN total=224, log total=220 | ESPN linescores sum 224 (PHX 105+HOU 119). Log 4 pts short |

Root cause: the results log's went_to_ot flag came from nba_api (stats.nba.com), which may have
different OT tracking. The PHX vs HOU 4-point discrepancy is unexplained. All 3 are in the results
log, not in the ESPN source. The loader is correct for these games.

**Null control (OT).** DEN vs POR 2026-04-06: regulation linescores [31,27,29,38] + [35,37,29,24] = 250.
Full game (5 periods) = 269. Loader returns 269 (correct: OT included). A regulation-only sum
would give 250 — test_ot_game_total_includes_ot catches this (asserts total=269 and total != 250).

**Tests (2 tests, both pass, mutation stated):**
(i) All 30 Odds API names map to abbreviations.
(ii) OT game total includes OT — FAILS if loader sums only periods 1-4 (would get 250 not 269).

**Settlement rules.** Pinnacle (`pinnacle.com/en/betting-rules/basketball`) and Hard Rock
(`hardrockbet.com/sports/rules`) both return HTTP 404/403 from Mac and VM. **NOT VERIFIED** —
settlement rules could not be fetched programmatically from any host. Do not state a rule from memory.

### B5 — L3 and L4 as they stand (2026-09-30)

Audit only; no code change to the live pipeline.

**L3 (a): data coverage.**

| File | Rows | Cols | Date range | Seasons |
|------|------|------|-----------|---------|
| games.parquet | 3,690 | 9 | 2022-10-18 to 2025-04-13 | 2022-23, 2023-24, 2024-25 |
| box_stats.parquet | 7,380 | 17 | same | same |
| features.parquet | 3,690 | 48 | same | same |
| h1_features.parquet | 3,690 | 53 | same | same |
| predictions_4b.parquet | 994 | 44 | 2025-10-21 to 2026-03-13 | 2025-26 |
| sim_results_4b.parquet | 994 | 54 | same | 2025-26 |
| nba_daily_projections.parquet | 279 | 90 | 2026-03-14 to 2026-06-19 | — |
| nba_results_log.parquet | 194 | 40 | 2026-03-14 to 2026-04-12 | — |
| nba_signal_log.parquet | 92 | 18 | 2026-03-24 to 2026-05-30 | — |

**2025-26 regular season NOT stored** in games.parquet or box_stats.parquet. Pre-registration HELD.
`run_nba.py:_build_current_team_states` fetches 2025-26 box stats live via `fetch_box_stats()` and
merges with historical box_stats.parquet. Features are rolling (15-game window, `.shift(1)`), not
full-season. Prior-season baselines use full 2024-25 means (complete by season start, so point-in-time
safe). `nba/modules/features.py:75:_build_prior_season_baselines` — `.groupby(["team","season"]).mean()`.
No full-season aggregate for the current season found; CHECK 1b passes for the rolling pipeline.

However: `predictions_4b.parquet` and `sim_results_4b.parquet` contain 994 rows of 2025-26 predictions
(Oct 21 - Mar 13). These were computed by `phase4b.py`, which uses the same rolling features.
Whether these are point-in-time depends on when they were built; if rebuilt after the season,
they would incorporate data not available at prediction time. Not verified here.

**L4 (b): signal log forward analysis** (all 92 rows are after commit date 2026-03-22).

| Signal type | n | Graded | Units |
|-------------|---|--------|-------|
| OREB_CONFIRMS | 35 | 7 | +1.91 |
| REF_UNDER | 31 | 23 | +0.68 |
| BALANCED_vs_PASSIVE | 12 | 2 | -1.50 |
| ROAD_WARRIOR_at_STRONG_HOME | 9 | 9 | +2.32 |
| NO_SIGNAL | 5 | 0 | — |

Every signal type has fewer than 30 graded forward rows. Pre-registration HELD.
None has a defensible probability from 9 or fewer graded observations.

**Projection residuals** (forward, pred_total vs recorded line, n=131):
pred_total - line: mean=-5.1, SD=9.4 (model systematically 5 pts below line).
pred_total - actual: mean=-8.1, SD=21.4. Line - actual: mean=-3.0, SD=18.9.

**B5 records:** on 2026-10-20, each layer honestly contributes:
- **L3:** source = ESPN scoreboard (VM) + nba_api cross-check (Mac). The as-of rule for rolling
  features is games completed before the prediction date; `_build_current_team_states` enforces
  this by filtering `date < game_date`. For the 2025-26 season, live API provides box stats;
  no historical file stores them yet.
- **L4:** direction votes only, with n stated (max 9 graded forward rows for ROAD_WARRIOR).
  No signal type has evidence for a probability; the venue board is not baseline (b).

### B6 — Corrected report URL and re-measured cadence (2026-09-30)

**Bug.** B2's "no 5:30 PM report" was a URL bug, not a fact about the NBA. The probe built URLs
with a 24-hour hour (`17_30PM`); the real CDN format is 12-hour (`05_30PM`). The 10:00-12:45
window is exactly where 24-hour and 12-hour agree, so every afternoon/evening report was requested
at a URL that cannot exist. See `wo1_verification_2026-09-30.md` for the full verification.

**Fix.** New function `official_report_url(date, hour24, minute)` in `capture_nba_availability.py`,
using 12-hour format. `probe_nba_sources.py` imports it (no second copy). `nbainjuries.gen_url`
agrees on all 5 test cases (10:00, 12:45, 13:00, 17:30, 19:15). Test `test_report_url_b6.py`:
4 assertions (13:00→`_01_00PM`, 17:30→`_05_30PM`, 12:45→`_12_45PM`, 10:15→`_10_15AM`); FAILS on
c715f643a (function does not exist there).

**Re-measured cadence (Mac, corrected URLs).**

| Date | Reports | Range | Cadence | 5:30pm? | Latest |
|------|---------|-------|---------|---------|--------|
| 2025-10-10 (preseason) | 0 | — | — | — | — |
| 2025-12-25 (Christmas) | 56 | 10:00-23:45 | q15 | **Yes** | 23:45 |
| 2026-01-14 (mid-season) | 56 | 10:00-23:45 | q15 | **Yes** | 23:45 |
| 2026-03-16 (late season) | 56 | 10:00-23:45 | q15 | **Yes** | 23:45 |

Reports are published 10:00 AM - 23:45 PM ET, every 15 minutes — the FULL day, not 10-12:45.
**5:30 PM report exists** on all three regular-season dates. B1's freeze rule stands.

**Pre-registration verdicts.**
- "Reports exist after 12:45 pm, including one at or near 5:00-5:30 pm" — **HELD** (56 per date, 5:30 present).
- "2025-12-25 has reports before its noon tip" — **HELD** (10:00-11:45 AM all present).
- "Preseason date has none" — **HELD**.
- **NULL CONTROL:** 10:00-12:45 count = 12 per date, matching WO1 exactly.

**VM re-probe.** All URLs return **403** (Forbidden), all 4 dates, all 56 slots. This is a genuine
CDN block (403, not 404). B2 "CDN blocks the VM" is now CONFIRMED with correct URLs.

**B6 records:** B2's "no 5:30 PM report" is WITHDRAWN — it was a URL bug. The corrected cadence is
10:00-23:45 ET q15 on game days (56 reports/day). Official reports: Mac only (VM blocked, 403).
B1's 5:30 PM freeze rule stands.

### B7 — Capture cadence, live Hard Rock key, PHX-HOU answer (2026-09-30)

**Capture cadence.** `_report_urls_for_now` now polls 10:00 ET through the day's last tip
(from ESPN scoreboard), not just 10:00-12:45. Uses `official_report_url` (12-hour format).
Test `test_capture_cadence_b7.py`: on a day with a 22:00 ET tip, the list includes 17:30 and
21:45 — FAILS on c715f643a (old code stopped at 12:45).

**Proposed cron (NOT installed):**
```
# Mac: official reports + ESPN, 10:00 ET to last tip, q15 (game days checked by script)
# For a typical 7pm-10pm ET slate, poll 10:00-23:00 ET = runs 10:00..23:00 q15
*/15 10-23 * * * /path/to/python3 /Users/jw115/mlb-model/nba/pipeline/capture_nba_availability.py >> /Users/jw115/mlb-model/logs/nba_availability.log 2>&1
```

**Live Hard Rock key probe** (4 calls, 3 credits each = 12 credits total).

| Sport | bookmakers= | Events | With Hard Rock | Result |
|-------|-------------|--------|----------------|--------|
| basketball_nba | hardrockbet | 44 | 0 | Not posting NBA lines yet |
| basketball_nba | hardrockbet_fl | 44 | 0 | Not posting NBA lines yet |
| americanfootball_nfl | hardrockbet | 31 | 16 | **Present** under `hardrockbet` |
| americanfootball_nfl | hardrockbet_fl | 31 | 16 | **Present** under `hardrockbet_fl` |

NFL returns Hard Rock under BOTH keys (`hardrockbet` and `hardrockbet_fl`). NBA returns neither —
Hard Rock has not posted NBA regular-season lines yet (first tip is 2026-10-20, 20 days away).
Pre-registration "NBA returns Hard Rock under at least one key once regular-season lines are posted"
— CANNOT BE TESTED TODAY. What would change it: Hard Rock posts NBA lines closer to opening night.
The capture script already requests `hardrockbet_fl` via `multi_book_open_capture.py`; when Hard
Rock posts NBA lines, it will appear automatically if the key matches.

**PHX-HOU 2026-04-07 settled.** nba_api (stats.nba.com) returns HOU 119 + PHX 105 = 224. ESPN
also returns 224. The results log says 220. **The results log is wrong** (4 pts short). Both
independent sources agree on 224. Root cause: unknown (likely a grading bug in the results tracker).

**B7 records:**
- Capture cadence: 10:00 ET through last tip, q15 (not 10:00-12:45). Proposed cron: `*/15 10-23`.
- Hard Rock live key: NFL uses both `hardrockbet` and `hardrockbet_fl`. NBA: neither today (not
  posted yet; check again closer to opening night).
- PHX-HOU: ESPN 224, nba_api 224, results log 220. The log is wrong.

### B14 — Official report parser to A7 standard (2026-10-05)

**Bug found (Cowork, verified).** `_parse_report` in `capture_nba_availability.py` passes a date
string (`"2026-10-01"`) to `nbainjuries.get_reportdata()`, which expects a `datetime.datetime`.
This causes `TypeError: '<' not supported between instances of 'str' and 'datetime.datetime'`,
caught by the bare `except Exception`, returning `None`. The caller then logs status `"ok"` with
`rows=0`. The 10-01 PDF was logged as "ok" with 0 rows despite containing 5 player rows.

**Fix.** New module `nba/pipeline/injury_report_parser.py` implementing A7:
- **Parser A:** `pdftotext -layout` + allowlist grammar (header, column header, game date, game time,
  matchup with 30-team code validation, team full name, player `Last, First[ Suffix]`, status in
  {Out, Doubtful, Questionable, Probable, Available}, reason; continuation rows and NOT YET SUBMITTED
  handled explicitly; `ParseHalt` on anything outside the grammar).
- **Parser B:** `nbainjuries.get_reportdata()` with correct `datetime` argument; NaN/NOT-YET-SUBMITTED
  rows filtered out.
- **Consumed set** = `{(game_date, matchup, team, player, status)}`; A must equal B or status
  `parse_disagree`.
- **Context binding:** URL date == header date; header time within [slot, slot+30min]; sha256 recorded.
- **Statuses:** `ok | verified_empty | parse_failed | parse_disagree | context_mismatch`. Non-ok:
  raw PDF still archived, pull-log carries the status, `main()` exits 2.
- Rows carry `published_utc` (from header) and `slot_et`.

`capture_nba_availability.py` updated: `capture_official_reports()` now calls `parse_report()` from
the new module. Non-ok parse status sets exit code 2 through `main()`.

**PRE-REGISTRATION:**
- 10-01 PDF yields exactly 5 rows: Carter Q, Cenac Jr. Q, Conley Q, DeVries Out, Collins Out;
  published 16:56Z. **HELD.**
- Three fixtures give A == B. **HELD.**

**NULL CONTROL:** Each fixture parses to byte-identical output on two consecutive runs. **HELD.**

**Re-parse all archived PDFs:**

| File | Status | Rows | Published UTC |
|------|--------|------|---------------|
| Injury-Report_2026-10-01_12_45PM.pdf | ok | 5 | 2026-10-01T16:56:00Z |
| Injury-Report_2025-12-25_12_45PM.pdf | ok | 43 | 2025-12-25T17:45:00Z |
| Injury-Report_2026-01-14_12_45PM.pdf | ok | 67 | 2026-01-14T17:45:00Z |
| Injury-Report_2026-03-16_12_45PM.pdf | ok | 79 | 2026-03-16T16:45:00Z |

**Tests (16 tests, all pass):**
- (i) 10-01 PDF yields 5 rows with pre-registered players/statuses — FAILS on origin/main
  (old path yields None due to TypeError).
- (ii) Corrupted PDF through capture main -> `parse_failed` and exit 2, never "ok" — FAILS on
  origin/main (old code logs "ok" with 0 rows on any parse error).
- (iii) Attack corpus (12 cases): extra status word HALT, single-team matchup HALT, unknown team
  code HALT, missing page HALT, header date mismatch `context_mismatch`, no header HALT, player
  without context HALT, empty text HALT, wrong date format HALT, no page footer HALT, Parser B
  drop row -> sets differ, Parser B flip status -> sets differ.
- Null control: deterministic.

**Origin/main failure demonstration:**
```
get_reportdata('2026-10-01', ...) -> TypeError: '<' not supported
_parse_report catches -> returns None -> caller logs status="ok", rows=0
```

### B15 — ESPN de-dup on content (2026-10-05)

**Bug found (Cowork).** Consecutive archived ESPN files differ only in the top-level `"timestamp"`
key, so the raw-byte SHA256 never matches. Result: 220 files / 9.1 MB in 5 days, all committed by
the hourly auto-commit. The existing `test_duplicate_espn_skipped` passes only because the test
fixture uses identical raw bytes (no timestamp variation).

**Fix.** `capture_espn_injuries()` now hashes the canonical JSON (sorted keys, top-level
`"timestamp"` removed). Skip when equal to the previous kept pull (still logged with status
`"unchanged"`). A parsed parquet is written per kept file: `team_id`, `athlete_id`
(`athlete.id` if present, else extracted from `/id/<n>/` in the playercard link —
`athlete_id_source` column says which), `status`, `date_utc`, `retrieval_utc`.
Existing archived files are NOT deleted.

`_last_sha` updated to consider both `"ok"` and `"unchanged"` statuses as valid for dedup
comparison.

**PRE-REGISTRATION:**
- Of the 220 archived files, <= 30 distinct content hashes. **DID NOT HOLD: 43 distinct hashes.**
  The 6-day window crossed more content changes than expected (preseason roster churn, off-season
  injury updates). The prediction was wrong; no number is changed.
- **NULL CONTROL:** Union of `(team_id, athlete_id, status, date)` over all 220 files equals the
  union over the 43 kept files. **HELD** (105 items in both sets).

**Tests (2 tests, both pass):**
- (i) Two REAL consecutive archive files with same content (different timestamp) — second is skipped.
  FAILS on origin/main: raw-byte SHA differs, so both are kept.
- (ii) Null control: content union preserved across dedup.

### B16 — Backfill official reports, 2024-25 and 2025-26 regular seasons (2026-10-05)

**Script:** `nba/pipeline/backfill_official_reports.py`. Mac only (CDN blocks VM with 403).

**Method.** Game dates from `nba/pipeline/schedule/dates_{2024,2025}.json` (163 + 165 dates).
Per date: (a) latest report at or before (first tip - 30 min), searching backwards from cutoff;
(b) 5:30 PM ET report. New URL format `_HH_MMAM|PM` from 2025-12-22 on; before that, legacy
hourly `_HHAM|PM` (latest hourly <= 5 PM ET). Sleep 0.5s per request. Both parsers on every file.
Season-type values seen from ESPN: `2:regular-season` only (preseason=1, postseason=3 excluded).

**Raw PDFs** under `data/injury_archive/nba/history/season=<yr>/`, kept OUT of git via
`$(git rev-parse --git-common-dir)/info/exclude`. Proven with `git check-ignore`. Only parsed
manifest committed.

**Parser fix in same commit:** Parser A now handles reason text that appears above the player
line in the PDF layout (common in multi-line reason wrapping). Added `pending_reason` buffer.
This fixed 150/656 files that were `parse_failed` in the first run. Re-run brought `parse_failed`
to 0.

**Results:**

| Season | Pre-tip found | 5:30 PM found | A==B | Disagreements |
|--------|--------------|---------------|------|---------------|
| 2024-25 | 163/163 (100%) | 163/163 (100%) | 99.4% | 0 |
| 2025-26 | 165/165 (100%) | 165/165 (100%) | 98.8% | 0 |

Total: 656 files fetched+parsed in 28.8 min (0.48h). Rate: 0.27-0.37 files/s.

Non-ok statuses (6 total): 2 `verified_empty` (2025-02-13, likely All-Star break), 4
`context_mismatch` (2025-12-20 and 2025-12-21, around the URL format change date).

**PRE-REGISTRATION:**
- >= 95% of regular-season dates have (a): **HELD** (100%).
- A == B on >= 99% of files: **HELD for 2024-25 (99.4%), borderline for 2025-26 (98.8%).**
  The 4 non-matching files are `context_mismatch` around the format change, not parser bugs.

**NULL CONTROL:** 10 random dates re-run give identical manifest rows. **HELD.**

**Request (ops — do not do it here):** Add `data/injury_archive/nba/history/` to `.gitignore`.
Currently excluded via `info/exclude` which is local to this worktree's git dir. The `.gitignore`
entry is needed for the main checkout and other worktrees.

### B17 — NOT YET SUBMITTED is a status, never silence (2026-10-05)

**Defect (Cowork verification).** Parser A `continue`d on NYS lines (~183), Parser B filtered
nan/nan rows (~282). A team that had not submitted looked identical to a team with no injuries;
a report where every team was NYS became `verified_empty`. The work order required NYS as its
own status.

**Fix.** Parser A emits `(game_date, matchup, team, player="", status="NOT_YET_SUBMITTED")` for
every team line marked NOT YET SUBMITTED. Parser B now emits NYS rows only for teams with no
player rows in that (game_date, matchup, team) — nbainjuries sometimes inserts nan rows as
tabula artifacts between real player rows (e.g. SAS in ORL@SAS on 2025-04-01). The consumed set
includes NYS rows. `verified_empty` triggers only when both parsers agree on zero rows of ANY
status.

**2025-02-13 PDFs (pdftotext first 40 lines):**
The report (`Injury-Report_2025-02-13_12PM.pdf`) contains 5 matchups with 10 teams, all
NOT YET SUBMITTED. It is NOT empty. B16 logged it as `verified_empty`; it now parses as `ok`
with 10 NYS rows.

**Re-parse all 656 history PDFs:**

| Season | Files w/ >= 1 NYS | NYS rows total | Status changed vs B16 |
|--------|-------------------|----------------|----------------------|
| 2024-25 | 166/167 | 2,802 | 2 |
| 2025-26 | 259/268 | 2,698 | 5 |

Status changes: 2025-02-13 `verified_empty` -> `ok` (10 NYS rows); 5 files `ok` ->
`parse_disagree` (tabula artifact nan rows in Parser B). The tabula artifact fix resolved all 5
back to `ok`.

**PRE-REGISTRATION:**
- 2025-02-13 files are not truly empty. **HELD** (10 NYS rows).
- >= 1% of files carry at least one NYS team. **HELD** (97.7%).

**NULL CONTROL:** Every file with zero NYS rows keeps its B16 status exactly. **HELD** (0 changed).

**TEST:** Jan 14 fixture yields >= 86 rows (67 player + 19 NYS). FAILS on 771174b77: old parser
returns only 67 rows (NYS skipped).
```
B17 test on 771174b77 parser: status=ok, rows=67, nys=0
  FAILS: assert len(nys) >= 19 -> 0 < 19 = True
```

### B18 — prove pending_reason fix and 2025-26 shortfall (2026-10-05)

**a) pending_reason fixtures.** Three legacy PDFs from the 150 that were `parse_failed` before the
fix, copied to `nba/pipeline/tests/fixtures/`:
- `Injury-Report_2024-10-22_12PM.pdf` (64 KB) — reason `Injury/Illness - Left Hamstring;` wraps
  above player line.
- `Injury-Report_2024-10-27_12PM.pdf` (69 KB) — reason `Injury/Illness - Left Knee; Injury` wraps
  above player line.
- `Injury-Report_2024-10-31_12PM.pdf` (67 KB) — reason `Injury/Illness - Right Patella;` wraps
  above player line.

All three parse as `ok` now and FAIL on 079606ccf's parser with `ParseHalt("Unrecognized line: ...")`:
```
Injury-Report_2024-10-22_12PM.pdf: parse_failed, Parser A: Unrecognized line: 'Injury/Illness - Left Hamstring;'
Injury-Report_2024-10-27_12PM.pdf: parse_failed, Parser A: Unrecognized line: 'Injury/Illness - Left Knee; Injury'
Injury-Report_2024-10-31_12PM.pdf: parse_failed, Parser A: Unrecognized line: 'Injury/Illness - Right Patella;'
```

**b) The 4 context_mismatch files (2025-12-20/21).**

| File | URL slot ET | Header time | Published UTC | Delta |
|------|------------|-------------|---------------|-------|
| Injury-Report_2025-12-20_12PM.pdf | 12:00 PM | 12:45 PM | 17:45Z | 45 min |
| Injury-Report_2025-12-21_12PM.pdf | 12:00 PM | 12:45 PM | 17:45Z | 45 min |

**Cause:** legacy hourly format `_12PM` → slot = 12:00 PM ET exactly. The actual report was
published at 12:45 PM (header says so). Delta = 45 min > the 30-min binding rule. For legacy hourly
files, the slot represents the top of the hour, not the exact publication time — the report can be
published anytime within that hour. The binding rule `[slot, slot+30min]` is correct for the new q15
format (where the slot IS the intended publication time within 15 min), but too tight for legacy
hourly format where `[slot, slot+60min]` would be correct. **Proposed rule (not applied in this
item):** for legacy hourly filenames (no minute component), widen the binding window to
`[slot, slot+60min]`.

**c) B16's "A == B >= 99%" DID NOT HOLD for 2025-26.** The result was 98.8% (4 files
`context_mismatch` out of 330). The B16 entry called this "borderline" and attributed it to the
format change without showing the evidence. The evidence above shows the cause is the too-tight
binding rule for legacy hourly files, not a parser bug. The prediction was wrong; no number is
changed.

### B19 — data custody (2026-10-05)

**Raw PDFs** moved to `~/mlb-model/data/injury_archive/nba/history/season={2024,2025}/` (main
checkout). Already excluded via `$(git rev-parse --git-common-dir)/info/exclude`. Verified:
`git -C ~/mlb-model check-ignore data/injury_archive/nba/history/season=2024/test.pdf` returns the
path. Worktree copies NOT deleted.

**Committed, small:** per-file parsed parquets (all statuses including NOT_YET_SUBMITTED, with
`published_utc`, `slot_et`, `pdf_sha256`) under
`data/injury_archive/nba/history_parsed/season={2024,2025}/`, plus
`history_parsed/manifest.parquet` (filename, sha256, published_utc, status, n_rows, n_nys).

| Path | Files | Size |
|------|-------|------|
| history_parsed/season=2024/ | 167 parquets | 1.9 MB |
| history_parsed/season=2025/ | 268 parquets | 3.1 MB |
| history_parsed/manifest.parquet | 1 | < 1 KB |
| **Total** | **436** | **5.0 MB** |

5.0 MB < 20 MB limit.

`git ls-files --cached data/injury_archive/nba/history_parsed/` shows 436 parquet files, 0 PDFs.

Total parsed rows: 46,987 (including NYS rows).

### B20 — RW@SH symmetry verdict: accepted (2026-10-05)

**Jeff's decision:** "accept symmetry" (session instruction, 2026-10-05).

**Recomputation (Cowork verification, `nbaS0_verification_2026-10-05.md`):**
Pinnacle last pre-tip totals, same point on both sides. 101 signal games, 984 non-signal games.

| | Over ROI | Under ROI | Sum | Price-only value |
|---|---------|-----------|-----|-----------------|
| Signal (101) | +16.33% | -22.63% | -6.30% | -5.68% |
| Non-signal (984) | -6.4% | +0.7% | -5.71% | -5.64% |

Mean overround: 2.96% (signal), 2.94% (non-signal).

**The [-6.0, -2.0] band was Cowork's mis-specification.** The sum of over ROI + under ROI equals
the price-only quantity `mean((d_over + d_under)/2) - 2` up to the outcome split. The expected sum
is about two overrounds (not one), so ~-5.7%. The signal's -6.30% is 0.6 pp from its price-only
value (-5.68%), explained by the 60/40 outcome split (over wins more often, so the under side
loses more per unit). No grader bug exists.

**The RW@SH numbers are unchanged.** The +16.3% over ROI at Pinnacle close stands as reported.

### B21 — zero-padded legacy URLs, re-fetch, roles.parquet (2026-10-05)

**Bug (S0b verification).** `legacy_report_url` built `_{h12}{AM|PM}` without zero-padding:
`h=17` → `_5PM` (CDN returns 404), `h=9` → `_9AM` (404). Only 10/11/12 o'clock produce
two-digit hours that matched the CDN's `_05PM`/`_09AM` format. The backward search for
"latest report <= cutoff" fell through to 12PM (or 11AM) for every legacy-era date.
Evidence: season=2024 had 163 `_12PM.pdf` + 4 `_11AM.pdf`, nothing else.

Same bug class as B2 (hour formatting). The old `pull_injury_reports.py` (2023-24 batch)
used `strftime('%I%p')` which produces zero-padded 12-hour format correctly.

**Fix.** `legacy_report_url` now uses `f"{h12:02d}{ampm}"`. Cross-check: output matches
`strftime('%I%p')` for all hours 9-23.

**Re-fetch.** All 224 legacy-era game dates (163 season 2024-25 + 61 season 2025-26)
re-searched with corrected URLs. 448 files fetched in 8.0 min (0.13h, under 2h limit).
Both pre_tip and freeze found for 224/224 dates (100%).

**roles.parquet** built at `data/injury_archive/nba/history_parsed/roles.parquet`:
656 rows (448 legacy + 208 new-format), columns: game_date, role, url, sha256, slot_et,
filename, season, status. One row per (game_date, role in {pre_tip, freeze}).

**PRE-REGISTRATION RESULTS:**
- ">= 95% of legacy pre_tip with slot >= 17:00 ET" — **DID NOT HOLD** (73.7%, 165/224).
  Many slates have afternoon tips (weekend matinees, holidays), so the "latest <= tip-30min"
  search stops at the early-afternoon report. The prediction assumed most tips are 7pm+;
  ~26% of dates have a first tip before 5:30pm ET.
- ">= 95% of freeze at 05PM" — **HELD** (100%, 224/224). Every legacy date has a 5PM report.
- "Pre_tip == 12PM falls from ~100% to <= 5%" — **HELD** (4.9%, 11/224). The 11 remaining
  12PM pre_tip files are Sunday noon slates with first tip near 1pm ET.
- **NULL CONTROL:** every new-format date (>= 2025-12-22) has roles rows identical to
  01c7ca076's manifest (same url and sha256). 0 mismatches out of 208 rows. **HELD.**

**Test (2 tests, both pass):** `test_b21_legacy_url.py`:
(i) h=17→`_05PM`, h=9→`_09AM`, h=12→`_12PM` — FAILS on 01c7ca076 (produces `_5PM`, `_9AM`).
(ii) Cross-check: matches old script's `%I%p` format for all hours 9-17.

**Pre_tip slot distribution (224 legacy dates):**

| Slot ET | Count | Note |
|---------|-------|------|
| 11:00   | 5     | Holiday/early matinee |
| 12:00   | 11    | Sunday noon slates |
| 13:00   | 2     | |
| 14:00   | 13    | |
| 15:00   | 13    | |
| 16:00   | 15    | |
| 17:00   | 12    | |
| 18:00   | 121   | Typical weeknight |
| 19:00   | 28    | Late tip |
| 20:00   | 3     | |
| 21:00   | 1     | ASG week |

Raw PDFs in main checkout `data/injury_archive/nba/history/season={2024,2025}/`, git-excluded.
Season 2024: 470 PDFs (was 167). Season 2025: 385 PDFs (was 268).

### B22 — legacy context window: [slot, slot+60min] (2026-10-05)

**Rule.** Legacy hourly files use binding window `[slot, slot+60min]`; new q15 files keep
`[slot, slot+30min]`. Legacy reports are published hourly, so the slot represents the top of
the hour, not the exact publication time. A report at 12:45 PM is correctly served by the
`_12PM` URL and falls within the hourly window.

**Change.** `validate_context` in `injury_report_parser.py` now calls `is_legacy_format(fname)`
and uses 60min or 30min accordingly.

**PRE-REGISTRATION:** The 4 B16 `context_mismatch` files (2025-12-20/21, `_12PM`, header
12:45 PM, delta=45min) become `ok`. No new-format file changes status.

**Re-parse results (448 legacy files):**

| Season | Role | Files | ok | context_mismatch | A==B rate |
|--------|------|-------|----|-----------------|-----------|
| 2024-25 | pre_tip | 163 | 163 | 0 | 100.0% |
| 2024-25 | freeze | 163 | 163 | 0 | 100.0% |
| 2025-26 | pre_tip | 61 | 61 | 0 | 100.0% |
| 2025-26 | freeze | 61 | 61 | 0 | 100.0% |
| **Total** | | **448** | **448** | **0** | **100.0%** |

Previous: 4 `context_mismatch` → now all `ok`. **HELD.**

**NULL CONTROL:** 208 new-format files: 0 changed status. **HELD.**

**Tests (3 tests, all pass):** `test_b22_context_window.py`:
(i) Legacy `_12PM` file with header 45min after slot → `ok`. FAILS on 01c7ca076
    (`is_legacy_format` does not exist; `validate_context` returns `context_mismatch`).
(ii) New-format `_12_00PM` file 45min after slot → `context_mismatch` (30min rule holds).
(iii) New-format file 25min after slot → `ok`.

### B23 — regenerate committed parsed history (2026-10-05)

**B16/B19 rows for legacy-era dates are superseded.** The noon-only parquets parsed from
`_12PM.pdf` files (the only ones B16 fetched) represented the 12:00 PM report, typically
5-7 hours before the freeze/tip. B21 re-fetched the correct reports (e.g. `_05PM`, `_06PM`,
`_07PM`) and B22 widened the context window for legacy files. This rebuild replaces the
legacy-era parsed parquets with ones from the correct PDFs.

**Rebuild.** 642 unique PDFs parsed with both parsers. All 642 status = `ok`.

| Metric | Count |
|--------|-------|
| Parquets added | 420 |
| Parquets removed (superseded noon-only) | 224 |
| Parquets unchanged (name match, re-parsed) | 222 |
| Total in tree | 644 (642 parsed + manifest + roles) |
| Total size | 6.6 MB (< 20 MB) |

Per season:
- `history_parsed/season=2024/`: 316 parquets (was 167)
- `history_parsed/season=2025/`: 326 parquets (was 268)
- `history_parsed/manifest.parquet`: 642 rows (was 435)
- `history_parsed/roles.parquet`: 656 rows (unchanged from B21)

The 224 removed files are the `_12PM.parquet` entries for legacy dates where the correct
report (e.g. `_05PM`, `_06PM`) now exists. Git history retains them.

**Why the superseded files must not be used:** For a typical 7pm ET game night, B16's
`_12PM.pdf` was published at ~12:45 PM ET. The correct freeze report (`_05PM.pdf`) was
published at ~5:45 PM ET — 5 hours later, with all late-afternoon injury updates. Using
the noon report as "who was out at freeze" would miss every player ruled out between 1-5 PM.

### B24 — pre_tip chosen on published time, tip stored, no silent default (2026-10-05)

**Defect (S0c verification F1, F3).** The B21 pre_tip was chosen on SLOT time (`slot <=
first_tip - 30 min`), but legacy reports are published at slot+30 (or +45). A 7:30pm tip
picked the 07PM report, published at 7:30pm — exactly at tip, violating the 30-min rule.
Additionally, `get_first_tip()` silently defaulted to 19:00 ET when ESPN failed, with no flag.

**Fix.** Pre_tip now chosen on `published_utc <= first_tip_utc - 30 min`. Tip source:
Odds API events parquets (0 credits); ESPN as cross-check. No silent default — dates
without a tip from either source get status `no_tip`. `first_tip_utc` and `tip_source`
stored on every roles row.

For the 43 dates where the current pre_tip violated the rule, an earlier report was found
by searching backwards through legacy hourly or new-format q15 URLs.

**roles.parquet** new columns: `first_tip_utc`, `tip_source` (odds_events | espn | ""),
`published_utc`.

**PRE-REGISTRATION RESULTS:**
- "roles pre_tip rows with published_utc > first_tip - 30 min: 0 after the fix" —
  **HELD** (0 violations after).
- "Current main has 42 legacy rows and 1 new-format row" — 43 total violations before.
  **HELD** (43 found).
- "Legacy dates whose pre_tip file changes: between 30 and 50" — **HELD** (43 changed).
- **NULL:** every date whose current pre_tip already had published_utc <= first_tip - 30 min
  keeps the same filename and sha256. 285 dates unchanged (284 ok + 1 no_tip). **HELD.**

**no_tip dates:** 1 date (2026-04-11) — no Odds API events, ESPN returned no games.
Likely end-of-season date in schedule file with no actual games.

**ESPN vs Odds API first tip mismatches (> 15 min): 7**

| Date | ESPN tip | Odds tip | Delta |
|------|----------|----------|-------|
| 2024-12-10 | 00:00Z (12/11) | 22:00Z | 120 min |
| 2024-12-11 | 00:00Z (12/12) | 23:00Z | 60 min |
| 2024-12-12 | 00:30Z (12/13) | 00:10Z (12/13) | 20 min |
| 2025-10-24 | 22:30Z | 23:00Z | 30 min |
| 2026-01-31 | 17:00Z | 20:10Z | 190 min |
| 2026-02-02 | 20:00Z | 00:10Z (2/3) | 250 min |
| 2026-02-25 | 00:30Z (2/26) | 00:10Z (2/26) | 20 min |

The 120/60/190/250 min mismatches are ESPN In-Season Tournament / All-Star weekend games
where ESPN and the Odds API disagree on event timing. The 20-30 min mismatches are minor.
Odds API events are the primary tip source; ESPN is cross-check only.

### B25 — per-game as-of: game_asof.parquet (2026-10-05)

**Jeff decision 2026-10-05: "per-game cap with the 5:30 report."**

**Rule.** The freeze report is the date's 5:30pm ET report (`_05_30PM` new / `_05PM` legacy).
- asof = freeze if its published_utc <= tip_utc - 30 min (asof_role = freeze).
- Otherwise asof = latest report with published_utc <= tip_utc - 30 min (asof_role = pre_game).
- published_utc = PDF header time, never the slot. Legacy headers run 30-45 min after the slot.

**The live pilot packet uses the identical rule (CHECK 3); WO2-D must implement it, not a
date-level freeze.**

**game_asof.parquet:** `data/injury_archive/nba/history_parsed/game_asof.parquet`.
2,481 rows (one per Odds API event). Columns: event_id, game_date, home_team, away_team,
tip_utc, tip_source, asof_role, asof_filename, asof_sha256, asof_published_utc.

**Results:**

| asof_role | Count | Share |
|-----------|-------|-------|
| freeze    | 2,271 | 91.5% |
| pre_game  | 210   | 8.5%  |
| no_asof   | 0     | 0%    |

92 PDF fetches (under 300 cap).

**PRE-REGISTRATION RESULTS:**
- "rows with asof_published_utc > tip_utc - 30 min: 0" — **HELD.**
- "share of pre_game: 4%-15%" — **HELD** (8.5%). S0c audit measured 194/2,467 = 7.9%
  tipping before 18:00 ET; the 8.5% includes some games tipping 18:00-18:30 ET where the
  freeze report header (17:45) is inside the 30-min margin.
- **NULL:** every game with tip >= 18:30 ET has asof_role = freeze and the same sha256 as
  that date's roles freeze row: 2,153/2,160 (99.7%). 0 sha256 mismatches. The 7 exceptions
  are NBA Cup (2024-12-17) and play-in (2025-04-15/16) dates with no freeze in roles because
  they are not in the regular-season schedule files. **HELD** (with documented caveat).

### B26 — hygiene and doc corrections (2026-10-05)

**roles.status filled.** B24 filled all 448 blank legacy status fields (`ok` or `no_tip`).
Test `test_roles_status_no_blanks` asserts 0 blanks; FAILS at c19ce5371 (448 blank).

**Doc corrections (S0c verification):**
- B23 "224 removed" is wrong: 435 − 222 = **213** removed. Correct: +420 / −213 / 222 unchanged = 642.
- B21/B22 "208 new-format files" is the count of ROLE ROWS (208). The manifest has **206** new-format
  files (some dates use one file for both pre_tip and freeze roles).
- B22 "4 B16 context_mismatch" is wrong for the manifest: the old manifest has **2** legacy
  `context_mismatch` rows (2025-12-20 and 2025-12-21, each counted once). The "4" counted the same
  file appearing in 2 roles × 2 dates = 4 roles rows.

**Statement:** roles.parquet is a per-date index; per-game as-of MUST come from game_asof.parquet.

**Tests (5 tests, all pass):** `test_b24_asof_before_tip.py`:
(i) Every roles pre_tip row has published_utc <= tip - 30 min. FAILS at c19ce5371 (no published_utc column).
(ii) Every game_asof row has asof_published_utc <= tip - 30 min.
(iii) Mutation: moving a game's tip 2h earlier pushes freeze past cutoff → asof changes.
(iv) Dates without ESPN/Odds tips get tip_source = "", never silent 19:00 ET default.
(v) Every roles row has non-blank status. FAILS at c19ce5371 (448 blank).
