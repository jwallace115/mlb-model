# CC Decision Log v1

## CC-D1 — Inventory, gaps, and cell status (2026-11-06)

**What exists:**
- NHL: in-play 5-min tape (2022-23, 2023-24) with Pinnacle + 8-9 soft books; lines_all.parquet with
  Pinnacle h2h/spreads/totals 2022-26; SBRO games with outcomes for 1,312 games per DEV season;
  events tables (shots, state_time, penalties) for 1,312 games per season; goalie starts and GSAx
  ratings from 2021+; family.csv with 63 existing ledger p-values.
- NBA: lines_hourly with Pinnacle + 8 soft books for 1,248/1,246 events per DEV season;
  games.parquet with 1,230 outcomes per season; box_stats with possessions/pace/ratings;
  player_game_logs (FGA, FTA, TOV, MIN) for 2022-26; schedule_features with rest/travel.

**What is missing:**
- game_asof (official injury report index): covers only 2024-25 and part of 2025-26. NO DEV season
  data. This blocks NB4 (star out, total cut) and NB9 (late upgrade) entirely.
- NBA in-play tape for 2022-23: absent. Close for that season comes from lines_hourly only.
- NBA 2021-22 season data: needed for NB7's "prior season pts/game" in the 2022-23 window. Not in
  games.parquet. Would need external source.

**Cell status after inventory:**

| Cell | Status | Notes |
|---|---|---|
| NH1 | RUNNABLE | opener→close total move from lines_all; outcome from SBRO games |
| NH2 | RUNNABLE | mirror of NH1 |
| NH3 | RUNNABLE | soft book prices from in-play tape or lines_all; Pinnacle from same |
| NH4 | RUNNABLE | backup from goalie_starts; GSAx from goalie_ratings; ML move from lines_all |
| NH5 | RUNNABLE | B2B/OT from SBRO games; travel from schedule derivation; events for Q |
| NH6 | RUNNABLE | EN goals from state_time (home_skaters < 5 or away_skaters < 5 when goal scored); p_fair from lines_all |
| NH7 | RUNNABLE | rest from SBRO games schedule; shooting % from shots table |
| NB1 | RUNNABLE | opener/close from lines_hourly; outcome from games |
| NB2 | RUNNABLE | mirror of NB1 |
| NB3 | RUNNABLE | soft spreads from lines_hourly; Pinnacle spread from same |
| NB4 | **BLOCKED** | game_asof not available for DEV seasons |
| NB5 | RUNNABLE | schedule features (3-in-4, travel) derivable from games + venue mapping |
| NB6 | RUNNABLE | B2B + OT from box_stats; player minutes from player_game_logs |
| NB7 | **PARTIAL** | needs 2021-22 season pts/game for the 2022-23 window; only 2023-24 window is runnable with existing data |
| NB8 | RUNNABLE | rest from schedule_features; B2B from same; spreads from lines_hourly |
| NB9 | **BLOCKED** | game_asof not available for DEV seasons |

**Decision:** Proceed with 14 of 16 Tier 1 cells. NB4 and NB9 are dropped from the CC-1 screen
(they can be revisited if game_asof data for 2022-24 is later obtained or constructed from raw
injury PDFs). NB7 runs on 2023-24 only (one DEV season) and is marked EXPLORATORY per registry §4.

REGISTRY_v1.md sha256: `ee85d564382bab563c9876156292bae74ab590984cc6b156c096fdd55cc426c1`

---

## CC-D2 — Pre-registration: Item 1 expected counts and close age (2026-11-06)

**Expected game counts** (from Item 0c):
- NHL 2022-23: ~1,312 games with outcomes + Pinnacle close
- NHL 2023-24: ~1,312 games
- NBA 2022-23: ~1,230 games
- NBA 2023-24: ~1,230 games

**Expected close age:** < 60 min mean where in-play tape is the close source (NHL both
seasons; NBA uses lines_hourly due to sparse in-play tape pre-tip coverage).

### Actual results:
- NHL: 2,624 outcome matches out of 2,638 events (14 unmatched = playoff/preseason fringe).
  Season 2022: 1,312 outcomes. Season 2023: 1,312 outcomes. **Matches expectation.**
- NHL Pinnacle close age: mean=17.7 min, median=4.3 min (in-play tape). **Meets bar.**
- NHL openers (≥12h): 1,907/2,638 = 72.3%. Cells requiring openers have ~72% fill.
- NBA: 2,505 outcome matches out of 2,546 events.
  Season 2022: 1,243. Season 2023: 1,262. **Matches expectation.**
- NBA close age: mean=500 min (skewed by outliers), median=9.3 min (lines_hourly).
  2,466/2,546 (96.9%) have close age < 60 min. Adequate for the screen.
- NBA openers: 1,886/2,546 = 74.1%.

**Second prediction data fill:**
- NHL: 5v5 attempts/60 for 2,624/2,638 games. sh% for 2,624.
- NBA: possessions for 2,505/2,546 games.

**Tests:** All 6 passed.
- t1 truncation (NHL): home_rest_days verified correct for 20 random dates
- t1 truncation (NBA): home_poss_avg10 verified correct for 20 random dates
- t1 planted leak: detected (46/50 games differ forward vs backward rest)
- t2 null control: max implied prob diff vs lines_all = within threshold
- t3 isolation: build_features source does not reference second_pred; no column overlap

---

## CC-D3 — Pre-registration: Screen expectations (2026-11-06)

**Cowork priors** (from registry §7):
- CC-0a: ≥1 NHL Tier 1 passes screen: 30%
- CC-0b: ≥1 NBA Tier 1 passes screen: 45%
- CC-0c: Tier 2 BH survivor in NBA: 55%; in NHL: 25%
- CC-0f: First survivor is totals-suppression pair (NB1 > NH1 > NB4): 40%

**Claude Code pre-registration** (before running):
- Expected BH survivors in Tier 2 under the null: ≈ 0.10 × BH-rank, i.e. 1–3 from ~420 cells
- "Home team" null control: mean r within ±0.01

**Actual results (CC-1b corrected):**
- 0 NHL Tier 1 cells pass → CC-0a OPEN (all 7 NHL cells now run as registered; 0 pass)
- 0 NBA Tier 1 cells pass → CC-0b OPEN (5 of 7 runnable NBA cells run; NB4/NB9 blocked; 0 pass)
- 2 Tier 2 BH survivors (both NBA, both April) → CC-0c NBA resolved at 1 (barely),
  NHL resolved at 0. The 2 survivors are consistent with chance (pre-registered: 1–3 expected).
- Home team null: NHL −0.004, NBA −0.007 → both within ±0.01 as pre-registered
- Positive control: planted +0.04 detected and survived BH → pipeline works

---

## CC-D4 — April diagnostic pre-registration (2026-11-06)

**Cowork prior:** artefact 60% (stale close or non-regular-season rows), real-but-priced 25%, noise 15%.

**Claude Code prior:** artefact 55% (April close quality is visibly worse in the data; p90 age
is likely > 100 min), noise 35%, real 10%.

### CC-D4 RESULT

**3a — Close age by month:**

| Month | n | median (min) | p90 (min) | share > 60 min |
|---|---|---|---|---|
| Oct | 151 | 9.3 | 9.4 | 0.7% |
| Nov | 459 | 9.3 | 14.3 | 7.8% |
| Dec | 440 | 9.3 | 9.4 | 0.9% |
| Jan | 454 | 9.4 | 9.4 | 0.7% |
| Feb | 338 | 9.3 | 9.4 | 1.2% |
| Mar | 473 | 9.3 | 9.4 | 0.8% |
| **Apr** | **231** | **9.3** | **1,209** | **12.1%** |

April's p90 and share > 60 min are **materially worse** than Nov–Mar. 12.1% of April
closes are stale (> 60 min old), compared to < 1.5% for Dec–Mar.

**3b — Cell cuts:**

| Cell | Cut | n | mean r |
|---|---|---|---|
| T2_NBA_month_4_away_ml | Original | 222 | +0.098 |
| | (i) close ≤ 15 min | 196 | +0.039 |
| | (ii) 2023-24 only | 130 | +0.086 |
| | (iii) Excl. play-in (30 removed) | 192 | **+0.012** |
| T2_NBA_month_4_over | Original | 192 | +0.112 |
| | (i) close ≤ 15 min | 188 | +0.109 |
| | (ii) 2023-24 only | 116 | +0.109 |
| | (iii) Excl. play-in (0 removed) | 192 | +0.112 |

**T2_NBA_month_str_4_away_ml**: collapses from +0.098 to +0.012 after excluding play-in games.
The signal was entirely carried by 30 play-in/non-regular-season games. **DEAD-ARTEFACT.**

**T2_NBA_month_str_4_over**: survives all three cuts (r stays +0.109 to +0.112). However,
it is a single-feature Tier 2 cell with no mechanism, Q, or prior — it remains a HYPOTHESIS
per registry §5. Not promoted.

**3c — Q for fired April games:**
- Possessions vs prior-10: mean diff +2.9, median +1.7 (April games have slightly higher pace)
- Top-5 minutes avg: 32.5 min (no prior-20 baseline to compare against in this output)

**Verdict:** away_ml cell is DEAD-ARTEFACT (play-in contamination). Over cell is noise-or-pace
but cannot be distinguished from chance without a mechanism. Neither changes the screen conclusion.

---

## CC-D5 — CHECK 2 gate for NB10 CONFIRM (2026-11-06)

**Question:** Does any legacy NBA research contain an April / late-season / month-of-season
totals cell that touched 2024-25 data?

**Grep results (every hit with path + line):**

1. `nba/backtest.py:114` — "Late season (Jan-Apr)" MAE/bias breakdown. General model diagnostic,
   not a cell. Touches all seasons including 2024-25 but reports aggregate model performance, not
   a betting hypothesis.
2. `nba/backtest_h1.py:85` — Same "Late season" diagnostic for H1 totals.
3. `nba/phase6.py:181` — Same "Late season" diagnostic.
4. `nba/phase7b/master_summary.txt:243`, `results_7b_c.txt:100`, `master_summary_v2.txt:66` —
   "A9 — Late season playoff race": **SKIPPED**. Never ran, no results.
5. `nba/diagnostics.py:177,196` — Ridge coefficients for `days_rest_home` / `days_rest_away`.
   Rest features in the totals model, not April-specific. General model, not a cell.
6. `research/nba_layers/legacy_review_2026-09-30/NBA_LEGACY_REVIEW_2026-09-30.md:27-29` — April
   venue-board analysis touched 2024-25, but this was about ML/ATS team lists (ROAD_WARRIOR,
   STRONG_HOME), not a month-of-season totals cell. CHECK 2 failed for the venue board on
   different grounds.
7. `research/nba_layers/legacy_review_2026-09-30/PREREG_rw_sh_2025_26.md:4-7` — Same venue-board
   April revalidation. About the team-list selection, not totals.
8. `research/corrcause/` itself — `T2_NBA_month_str_4_over` screened on DEV 2022-23 + 2023-24
   only. Did NOT touch 2024-25.

**No cell found.** The legacy NBA research has:
- General late-season model diagnostics (backtest splits): not cells, not hypotheses
- A9 (late-season playoff race amplifier): SKIPPED, never produced results
- Venue-board April analysis: touched 2024-25 but is about team selection for ML/ATS, not a
  month-of-season totals cell
- The corrcause Tier 2 April over cell: DEV-only, no 2024-25 data

**Decision: GATE OPEN.** No prior April / late-season / month-of-season NBA totals cell touched
2024-25 data. Item 2 (NB10 CONFIRM) proceeds.

---

## CC-D5c — Data availability for NB10 CONFIRM (2026-11-06)

**lines_hourly season=2024:**
- 4,743 total files
- April 2025 events with Pinnacle totals: 119

**games.parquet (outcomes):**
- April 2025 games with actual_total: 105
- All 105 are regular-season (date range: 2025-04-01 to 2025-04-13)
- 2024-25 regular-season finale: 2025-04-13

**box_stats.parquet:**
- April 2025 rows: 210 (105 games × 2 teams), all with possessions

**Merged (both Pinnacle total close AND outcome): 105 games**

GATE CHECK: 105 ≥ 80 → **PASS**

REGISTRY_v2_ADDENDUM.md sha256: `f27d476055872bb242139843bbb55dcfad6193317564e934db90fbb56a6f67a6`
