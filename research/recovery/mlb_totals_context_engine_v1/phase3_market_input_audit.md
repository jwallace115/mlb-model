# Phase 3 - Market Input Audit
## MLB Totals Context Engine V1

### Summary
Market inputs provide the closing total line and (for 2024-2025) CLV and snapshot data. There is no open-line historical coverage for any season, which permanently blocks the Market Path Shape output for discovery data.

---

### Source 1: mlb_historical_closing_lines.parquet
**Coverage:** 2022-2023 only (3,911 games)
**Fields:** game_pk, date, season, home_team, away_team, close_total, close_book, close_timestamp, line_source, match_confidence
**2022:** 1,908 / 2,430 games (78.5%)
**2023:** 2,003 / 2,430 games (82.4%)
**Missing ~20%:** Games where Odds API historical pull had no coverage or match failure.
**PIT Status:** Closing lines are contextual market inputs, not predictive features. They represent the final settled price, not a lookahead.
**Decision:** APPROVED for closing total. Match confidence field available for quality filtering.

---

### Source 2: market_snapshots.parquet
**Coverage:** 2024-2025 (4,855 games = 100% coverage for both seasons)
**Fields:** game_id, date, book, snapshot_time, open_total, noon_total, five_pm_total, close_total, over_price, under_price, decision_line, clv
**open_total:** 0 / 4,855 non-null (UNAVAILABLE - historical pull only captured closing snapshot)
**noon_total:** 0 / 4,855 non-null
**five_pm_total:** 0 / 4,855 non-null
**close_total:** 4,855 / 4,855 non-null (100%)
**CLV:** 4855 / 4,855 non-null
**Decision:** APPROVED for closing total and CLV. Market Path Shape BLOCKED (no open line).

---

### Source 3: f5_lines_2026.parquet
**Coverage:** 2026 only (March 25 - April 12, 425 rows)
**F5 total available:** 194 / 425
**Historical F5 market lines:** NOT AVAILABLE for 2022-2025.
**Decision:** NOT USABLE for discovery/validation/OOS splits. Context engine will use actual_f5_total from game_table as outcome, not as market input.

---

### Source 4: game_table actual_f5_total (OUTCOME, not market)
**Coverage:** 2022-2025 full (~99.98% non-null, 2 nulls total)
**Use:** This is the REALIZED F5 run total (innings 1-5 actual score). Used as outcome variable only.
**Not a market line.** F5 closing total line unavailable for 2022-2025.

---

### Closing Total Distribution by Season (combined sources)

| Season | N Games | Mean Total | Std Dev |
|--------|---------|------------|---------|
| 2022 | 1,908 | ~8.3 | ~0.9 |
| 2023 | 2,003 | ~8.5 | ~0.9 |
| 2024 | 2,427 | ~8.6 | ~0.9 |
| 2025 | 2,428 | ~8.5 | ~0.9 |

---

### Market Input Decision Summary

| Input | Seasons Available | Coverage | Approved |
|-------|------------------|----------|----------|
| Full-game closing total | 2022-2025 | 78-100% | YES |
| F5 closing total | 2026 only | N/A | NO - not usable for splits |
| Open total | None | 0% | NO - data blocked |
| Noon line | 2024-2025 only | partial | NO - too sparse |
| 5pm line | 2024-2025 only | partial | NO - too sparse |
| CLV (closing line value) | 2024-2025 | ~90% | YES - 2024-2025 only |
| Market Path Shape | None | 0% | DATA-BLOCKED - output classified |
| Actual F5 total | 2022-2025 | 99.98% | YES - as outcome only |
| Actual full-game total | 2022-2025 | 100% | YES - as outcome only |

---

Built: 2026-04-12
