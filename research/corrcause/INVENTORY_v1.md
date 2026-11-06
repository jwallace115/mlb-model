# CC-1 Data Inventory (2026-11-06)

## NHL Data Sources

### 1. In-play 5-min tape
- **Path:** `~/mlb-model-nhlE/data/odds_archive/nhl/history/inplay/season={2022,2023}`
- **Files:** season=2022: 15,986 parquet + 15,986 json.gz (307 MB); season=2023: 16,545 parquet + 16,545 json.gz (316 MB)
- **Books (2022):** betmgm, betonlineag, betrivers, bovada, draftkings, fanduel, pinnacle, pointsbetus, williamhill_us (9)
- **Books (2023):** same + unibet_us (10)
- **Columns:** snapshot_utc, requested_utc, event_id, commence_time, home_team, away_team, bookmaker, book_last_update, market, outcome_name, description, point, price
- **Seasons present:** 2022, 2023, 2024, 2025

### 2. Pre-match lines (lines_all.parquet)
- **Path:** `~/mlb-model/research/nhl_sim/edge_hunt_2026-09-30/lines_all.parquet` (1.7 MB)
- **Shape:** 878,692 rows × 12 columns
- **Columns:** snapshot_utc, requested_utc, event_id, commence_time, home_team, away_team, bookmaker, market, outcome_name, description, point, price
- **Books:** betmgm, betonlineag, betrivers, bovada, draftkings, fanduel, lowvig, pinnacle, williamhill_us (9)
- **Markets:** h2h, spreads, totals
- **Date range:** 2022-10-08 to 2026-06-15
- **Events by season:** 2022: 580 (partial — only 2022 calendar year portion), 2023: 1,391, 2024: 1,426, 2025: 1,436, 2026: 775

### 3. Pre-match lines (nhl2 worktree, per-snapshot parquets)
- **Path:** `~/mlb-model-nhl2/data/odds_archive/nhl/history/lines/season={2022,2023,2024,2025}`
- **Format:** individual snapshot parquets (8-16 KB each)

### 4. Event markets (T-24h / T-1h derivative)
- **Path:** `~/mlb-model-nhlE/data/odds_archive/nhl/history/event_markets/`
- **Coverage:** season=2022: 0 files; season=2023: 5,370 files

### 5. SBRO games (outcomes + SBRO closing prices)
- **Path:** `~/mlb-model/research/nhl_sim/edge_hunt_2026-09-30/inputs/games.parquet` (3.6 MB)
- **Shape:** 22,842 rows × 86 columns
- **Seasons 2022-23:** 1,312 games; **2023-24:** 1,312 games
- **Date range:** 2007-09-29 to 2026-04-16

### 6. Events tables (shots, state_time, penalties)
- **Path:** `~/mlb-model-nhlsim1/nhl/data/sim/events/season={2022,2023}/`
- **Season 2022:** shots 114,088 rows (1,312 games), state_time 310,682 rows, penalties 10,063 rows
- **Season 2023:** shots 114,839 rows (1,312 games), state_time 323,390 rows, penalties 10,008 rows
- **Shots columns:** game_id, period, period_type, seconds, x, y, distance, angle, shot_type, shooting_team, shooter_id, goalie_id, strength, score_diff, rebound + 5 more

### 7. Goalie starts
- **Path:** `~/mlb-model/research/nhl_sim/edge_hunt_2026-09-30/inputs/nhl_goalie_starts.csv` (6.2 MB)
- **Shape:** 93,282 rows × 12 columns
- **Season 2022:** 2,983 starts; **Season 2023:** 2,979 starts

### 8. Goalie ratings (GSAx)
- **Path:** `~/mlb-model-nhlD/nhl/data/sim/ratings/goalie_ratings.parquet`
- **Shape:** 12,850 rows × 8 columns (game_id, season, date, goalie_id, team, role, n_prior_starts, gsax_per_att_rating)
- **Seasons:** from 2021 onward

### 9. NHL family.csv (existing ledger p-values)
- **Path:** `~/mlb-model/research/nhl_sim/edge_hunt_2026-09-30/hunt_2026-09-30/family.csv`
- **Rows:** 63 (header + 63 p-values)

---

## NBA Data Sources

### 1. Lines hourly (Pinnacle + soft books)
- **Path:** `~/mlb-model/data/odds_archive/nba/history/lines_hourly/season={2022,2023}`
- **Season 2022:** 4,775 parquet files + 4,775 json.gz (79 MB), 1,674,406 rows
- **Season 2023:** 4,626 parquet files + 4,626 json.gz (83 MB), 2,081,536 rows
- **Books:** betmgm, betonlineag, betrivers, bovada, draftkings, fanduel, lowvig, pinnacle, williamhill_us (9)
- **Columns:** snapshot_utc, requested_utc, event_id, commence_time, home_team, away_team, bookmaker, market, outcome_name, description, point, price, book_last_update, kind

### 2. In-play tape
- **Path:** `~/mlb-model/data/odds_archive/nba/history/inplay/`
- **Season 2022:** **0 files** (NOT AVAILABLE)
- **Season 2023:** 14,740 files (145 MB)
- **Impact:** For NBA 2022-23, the close comes from lines_hourly only (last pre-match snapshot). For 2023-24, the in-play tape's pre-tip rows are preferred per registry §2.

### 3. Games (outcomes)
- **Path:** `~/mlb-model/nba/data/games.parquet`
- **Shape:** 3,690 rows × 9 columns (game_id, date, home_team, away_team, home_score, away_score, actual_total, season, season_type)
- **2022-23:** 1,230 games (0 null scores); **2023-24:** 1,230 games (0 null scores)

### 4. Box stats (team-level per game)
- **Path:** `~/mlb-model/nba/data/box_stats.parquet`
- **Shape:** 7,380 rows × 17 columns (game_id, date, season, team, opponent, location, pts, opp_pts, poss, ortg, drtg, pace, went_ot, fg3a_rate, ft_rate, tov_rate, dreb_rate)
- **Seasons:** 2022-23, 2023-24, 2024-25

### 5. Player game logs
- **Path:** `~/mlb-model/nba/model_c/player_game_logs.parquet` (2.2 MB)
- **Shape:** 101,083 rows × 33 columns (FGM, FGA, FTA, TOV, MIN, PTS, PLUS_MINUS, etc.)
- **Seasons:** 2022-23, 2023-24, 2024-25, 2025-26

### 6. Schedule features
- **Path:** `~/mlb-model/nba/data/nba_schedule_features.parquet`
- **Shape:** 3,685 rows × 26 columns (rest days, games in windows, travel miles, etc.)
- **Seasons:** 2022-23, 2023-24, 2024-25

### 7. Game as-of (official injury reports)
- **Path:** `~/mlb-model-nbaS0d/data/injury_archive/nba/history_parsed/game_asof.parquet`
- **Shape:** 2,481 rows × 11 columns
- **Date range:** 2024-10-22 to 2026-04-12
- **Seasons covered:** 2024-25 (full) + part of 2025-26
- **NOT in DEV seasons** — NB4 and NB9 cannot be screened on 2022-23 or 2023-24

---

## Coverage Table (STOP gate check)

### NHL

| Metric | Season 2022 | Season 2023 |
|---|---|---|
| (i) Pinnacle pre-tip close (h2h) | 1,360 | 1,343 |
| (i) Pinnacle pre-tip close (totals) | 1,360 | 1,343 |
| (ii) Pinnacle opener ≥ 12h out | TBD (lines_all has snapshots; needs filtering) | TBD |
| (iii) ≥ 3 soft books at close | 1,404 | 1,401 |
| (iv) Outcome (scores, OT/SO) | 1,312 | 1,312 |
| (v) Events (shots/state_time) | 1,312 games | 1,312 games |
| **STOP gate: (i)+(iv) ≥ 900?** | **YES (1,312)** | **YES (1,312)** |

### NBA

| Metric | Season 2022-23 | Season 2023-24 |
|---|---|---|
| (i) Pinnacle pre-tip close (h2h) | 1,248 | 1,246 |
| (i) Pinnacle pre-tip close (totals) | 1,248 | 1,246 |
| (i) Pinnacle pre-tip close (spreads) | 1,248 | 1,246 |
| (ii) Pinnacle opener ≥ 12h out | TBD (lines_hourly; needs filtering) | TBD |
| (iii) ≥ 3 soft books at close | 1,254 | 1,249 |
| (iv) Outcome (scores) | 1,230 | 1,230 |
| (v) Box stats (possessions, etc.) | 1,230 games | 1,230 games |
| (v) Player game logs | present | present |
| **STOP gate: (i)+(iv) ≥ 900?** | **YES (1,230)** | **YES (1,230)** |
| **NBA 2022-23 lines_hourly present?** | **YES (4,775 files)** | YES |

### STOP gate: ALL PASS

---

## Read-time measurements (Item 0e)

| Archive | Season | Method | Files | Time |
|---|---|---|---|---|
| NHL in-play tape | 2022 | 100 parquet files read | 15,986 total | 0.26s → projected **41.3s** full season |
| NHL in-play tape | 2023 | (projected same rate) | 16,545 total | projected **~43s** |
| NBA lines_hourly | 2022 | all 4,775 parquet | 4,775 | **3.3s** actual |
| NBA lines_hourly | 2023 | all 4,626 parquet | 4,626 | **3.7s** actual |

**Projected Item 1 full read time:** NHL in-play 2 seasons ≈ 85s + NBA lines_hourly 2 seasons ≈ 7s + NHL lines_all (single parquet) < 1s + SBRO games < 1s + events tables < 2s + goalie starts < 1s + NBA box/games < 1s + NBA player logs < 1s = **~100s** for raw reads. Feature construction and join logic will add overhead; estimated total < 10 minutes wall time for the data pipeline.

---

## Data gaps affecting specific cells

| Cell | Gap | Impact |
|---|---|---|
| NB4 (star out, total cut) | game_asof covers 2024-10-22..2026-04-12 only — NO DEV season data | Cannot screen on DEV. Cell is **BLOCKED** unless an alternative injury-status source is found for 2022-24. |
| NB9 (late upgrade) | Same game_asof gap | Cannot screen on DEV. Cell is **BLOCKED**. |
| NB7 (early-season pace anchor) | Needs prior season's pts/game; 2022-23 needs 2021-22 data | NBA games.parquet starts at 2022-23; 2021-22 full-season pts/game must come from an external source or be hardcoded. **PARTIAL** — can use box_stats or player_game_logs for 2021-22 pts/game if available, else cell fires only in 2023-24. |
| NHL opener (all opener cells) | lines_all has 580 events for calendar-year 2022 (Oct-Dec 2022); full 2022-23 season needs Oct 2022 - Jun 2023 | Need to verify lines_all covers the full season via commence_time, not calendar year. Likely OK since it spans Oct 2022 - Jun 2026. |
| NBA in-play tape | Missing for 2022-23 | Close for 2022-23 comes from lines_hourly (last pre-match snapshot) rather than in-play tape's pre-tip rows. This is the fallback per registry §2 definition. |
