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
