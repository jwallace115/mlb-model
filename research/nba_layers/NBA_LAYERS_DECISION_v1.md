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
