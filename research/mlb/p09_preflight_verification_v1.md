# P09 Pre-Flight Verification V1

**Date:** 2026-05-12
**Inputs:** P09 spec v1, spec review, PIT verification, p09_overlay.py, Statcast aggregate, line snapshots, raw odds cache
**Purpose:** Verify all implementation gates before any P09 runner code is written

---

## A. Verdict

**READY FOR RUNNER IMPLEMENTATION**

All gates PASS. Gate 5b (DraftKings live capture mechanism) has a minor implementation note — the `line_snapshot_store.py` only stores one book per game+label (first in API response, usually FanDuel), but DraftKings totals are available in the raw odds cache (`data/cache/odds_full_YYYY-MM-DD.json`) with 14/15 game coverage. The P09 runner must read the raw cache and filter to DraftKings rather than relying on `line_snapshots_2026.json`.

---

## B. Gate Results Summary Table

| Gate | Result | Evidence | Notes |
|---|---|---|---|
| 1. P09 source of truth | PASS | `p09_overlay.py:33-40`, `p09_overlay_config.json`, PIT verification §G | Formula, cutoff 31.7305, direction LOW→UNDER, DraftKings canonical all confirmed |
| 2. Starter hard-hit runtime feasibility | PASS | `pitcher_statcast_per_start.parquet` (27,854 rows, 2022-04-07 to 2026-05-10), `modules/schedule.py:125-131` | Daily aggregate has pitcher_id + game_date + hard_hit_rate with zero nulls; schedule API provides probable pitcher ID pregame; shift(1).rolling(5,3) verified on 14 games |
| 3. Formula reconstruction | PASS | 14 games computed on 2026-05-10 | 1 signal fired (NYY@MIL p09=30.5013); see Section C |
| 4. p09_overlay.py match | PASS | All 14 games match compute_p09() at diff=0.000000 | Initial 4-decimal rounding artifact resolved; full-precision values match exactly |
| 5a. DraftKings schema feasibility | PASS | `line_snapshots_2026.json` (41 DK entries) + `data/cache/odds_full_*.json` | DK entries have total_line, over_price, under_price, snapshot_time, book="draftkings" |
| 5b. DraftKings live capture mechanism | PASS | `data/cache/odds_full_2026-05-10.json`: DK totals in 14/15 games; `config.py:317` ODDS_BOOKMAKERS includes "draftkings" | Raw cache written daily by run_model.py/refresh.py; P09 runner reads raw cache filtered to DK |
| 5 overall | PASS | 5a PASS + 5b PASS | |
| 6. Grading feasibility | PASS | MLB Stats API linescore: tested game_pk 822820 → total=15 | Same pattern as YRFI grader; actual_total from live feed; W/L/P against DK captured total |

---

## C. Sample Formula Verification Table (Gate 3, date=2026-05-10)

| away | home | away_starter | home_starter | away_hh_r5 | home_hh_r5 | park_rf | p09_score | cutoff | signal_fired | overlay_match |
|---|---|---|---|---|---|---|---|---|---|---|
| WSN | MIA | Cade Cavalli | Sandy Alcantara | 0.3658 | 0.4118 | 98 | 38.1057 | 31.7305 | false | EXACT |
| OAK | BAL | Luis Severino | Keegan Akin | 0.3461 | 0.5190 | 106 | 45.8536 | 31.7305 | false | EXACT |
| TBR | BOS | Nick Martinez | Payton Tolle | 0.3471 | 0.4157 | 104 | 39.6647 | 31.7305 | false | EXACT |
| COL | PHI | Tomoyuki Sugano | Cristopher Sanchez | 0.4055 | 0.5138 | 104 | 47.8027 | 31.7305 | false | EXACT |
| HOU | CIN | Kai-Wei Teng | Andrew Abbott | 0.3558 | 0.3687 | 107 | 38.7562 | 31.7305 | false | EXACT |
| MIN | CLE | Andrew Morris | Gavin Williams | 0.3327 | 0.4405 | 98 | 37.8883 | 31.7305 | false | EXACT |
| SEA | CHW | Logan Gilbert | Davis Martin | 0.5288 | 0.4571 | 100 | 49.2941 | 31.7305 | false | EXACT |
| NYY | MIL | Carlos Rodon | Logan Henderson | 0.3632 | 0.2348 | 102 | 30.5013 | 31.7305 | **true** | EXACT |
| CHC | TEX | Jameson Taillon | Jacob deGrom | 0.3286 | 0.5058 | 107 | 44.6392 | 31.7305 | false | EXACT |
| PIT | SFG | Bubba Chandler | Tyler Mahle | 0.3832 | 0.3289 | 96 | 34.1812 | 31.7305 | false | EXACT |
| NYM | ARI | Huascar Brazoban | Eduardo Rodriguez | 0.3417 | 0.3774 | 98 | 35.2329 | 31.7305 | false | EXACT |
| STL | SDP | Kyle Leahy | Walker Buehler | 0.5397 | 0.3979 | 95 | 44.5360 | 31.7305 | false | EXACT |
| ATL | LAD | Bryce Elder | Justin Wrobleski | 0.4035 | 0.4730 | 95 | 41.6333 | 31.7305 | false | EXACT |
| DET | KCR | Brenan Hanifee | Noah Cameron | 0.3267 | 0.4121 | 100 | 36.9360 | 31.7305 | false | EXACT |

1 game skipped (LAA@TOR): away starter Spencer Miles had only 2 prior starts (below min_periods=3).

14/14 computed games match `p09_overlay.py` `compute_p09()` at diff=0.000000.

---

## D. DraftKings Market Source Finding

**Gate 5a — DraftKings schema feasibility: PASS**

The `line_snapshots_2026.json` file contains 41 DraftKings entries with the required schema: `total_line` (float), `over_price` (int, American), `under_price` (int, American), `snapshot_time` (ISO timestamp), `book` ("draftkings"), `game_date`, `home_team`, `away_team`, `game_id`.

**Gate 5b — DraftKings live capture mechanism: PASS**

DraftKings data IS captured daily, but with a nuance:

1. **Raw odds cache** (`data/cache/odds_full_YYYY-MM-DD.json`): Written by `run_model.py` at 7am and `refresh.py` at 11am. Contains per-bookmaker data for all three requested books (pinnacle, draftkings, fanduel). DraftKings totals present in 14/15 games on 2026-05-10. This is the reliable DK source.

2. **Line snapshot store** (`mlb_sim/data/line_snapshots_2026.json`): Written by `store_snapshots_from_odds_response()` which picks the **first bookmaker with data** in the API response. Result: 1,335 FanDuel entries vs 41 DraftKings entries. The store deduplicates by `(game_id, snapshot_label)`, so only one book per game per label is stored.

**Implementation note:** The P09 runner must read the raw odds cache (`data/cache/odds_full_YYYY-MM-DD.json`) and filter to `bookmakers[].key == "draftkings"` to get DraftKings canonical totals. It should NOT rely on `line_snapshots_2026.json` for DraftKings prices, as that store is FanDuel-dominated.

Alternatively, FanDuel entries from `line_snapshots_2026.json` can serve as alt-book forensic data (same total_line in most cases, different vig).

**Gate 5 overall: PASS**

---

## E. Blocking Issues

None.

---

## F. Implementation Prompt Requirements (READY)

The runner prompt must preserve:

1. **No V1 dependency** — no import of `daily_signal_generator.py`, no V1 output required
2. **DraftKings canonical** — read raw odds cache filtered to `draftkings` book key; do not use `line_snapshots_2026.json` as DK source
3. **Alt-book forensic optional** — FanDuel from line_snapshots or raw cache as alt-book; not required for first implementation
4. **PIT-safe starter rolling feature** — `shift(1).rolling(5, min_periods=3).mean()` on `hard_hit_rate` from `pitcher_statcast_per_start.parquet`, filtered to `game_date < today` per pitcher_id
5. **No same-game Statcast** — parquet max_date must be < today (4:45am rebuild ensures this)
6. **Starter identity from schedule API** — `modules.schedule.fetch_schedule()` → `home_probable_pitcher.id` / `away_probable_pitcher.id`; skip game if either is None with note `STARTER_UNAVAILABLE`
7. **Formula** — `p09_score = avg(home_hh_r5, away_hh_r5) * park_run_factor`; cutoff 31.7305 frozen; signal_fired = p09_score <= cutoff
8. **Park factor** — `config.STADIUMS[home_team]["park_factor"]`; if missing, use 100 with note
9. **Output schema** — per spec v1 Section 7; write to `mlb/logs/p09_shadow_2026.json`
10. **No dashboard yet** — dashboard wiring is a separate future task
11. **No live betting language** — shadow only
12. **Grading** — MLB Stats API linescore for actual_total; W if actual < market, L if actual > market, P if equal; DraftKings canonical book for ROI
13. **VM host** — cron at 11:30 UTC (7:30am ET); matches YRFI pattern
14. **DK market total from raw odds cache** — `data/cache/odds_full_YYYY-MM-DD.json` filtered to `bookmakers[].key == "draftkings"` → `markets[].key == "totals"`

---

## G. Not Applicable

No fixes required. All gates PASS.
