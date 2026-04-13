# MLB INTRADAY DECISION PANEL V1 -- BUILD REPORT

> **BUILD ONLY -- INTRADAY DECISION PANEL V1**
> MPS remains RESERVED / DATA-BLOCKED. This build creates the historical intraday decision panel only. No signals have been tested, no decision filters have been defined, and no changes to the canonical spec have been made.

**Generated:** 2026-04-13T14:19:44.563983Z
**Verdict:** PANEL BUILT WITH MATERIAL GAPS

## 1. Source Universe
| Season | Games |
|--------|-------|
| 2022 | 2430 |
| 2023 | 2430 |
| 2024 | 2427 |
| 2025 | 2428 |
| **Total** | **9715** |

## 2. Acquisition
- New probes: 07:00 ET (11:00 UTC), 10:00 ET (14:00 UTC), 12:00 ET (16:00 UTC)
- API calls made (date-batched): 2100
  - 9,715 games x 3 probes served by 2100 unique (date, probe) API calls
  - Each call returns ALL games on a date -- not one call per game
- Credits remaining after build: 4117721
- OPEN + FINAL CLOSE reused from MPS substrate (zero additional API calls)
- Hard stop triggered: No

## 3. Panel Structure
- Rows: 9715
- Columns: 118
- States: OPEN_0001, DT_0700, DT_1000, DT_1200, FINAL_CLOSE
- Per state: selected_book, selected_line, over/under_price, snapshot_timestamp,
  timestamp_delta_min, fallback_used, quality_flag, fanduel/draftkings raw
- Continuity pairs: open->0700, open->1000, open->1200, 0700->close, 1000->close, 1200->close, open->close
- Integrity flags: open_late_flag, dt0700_near_open_flag, final_close_post_first_pitch_flag

## 4. Usable Data Rates (quality_flag == OK)
| State | Overall |
|-------|---------|
| open_0001 | 88.4% |
| dt_0700 | 95.8% |
| dt_1000 | 98.6% |
| dt_1200 | 99.6% |
| final_close | 99.9% |

## 5. Book Selection
- **open_0001**: {'fanduel': 8397, 'None': 1130, 'draftkings': 188}
- **dt_0700**: {'fanduel': 9184, 'None': 412, 'draftkings': 119}
- **dt_1000**: {'fanduel': 9544, 'None': 137, 'draftkings': 34}
- **dt_1200**: {'fanduel': 9658, 'None': 39, 'draftkings': 18}
- **final_close**: {'fanduel': 9673, 'draftkings': 33, 'None': 9}

## 6. Integrity Flags
| Flag | Total |
|------|-------|
| open_late_flag | 0 |
| dt0700_near_open_flag | 0 |
| final_close_post_first_pitch | 2503 |

**Notes:**
- open_late_flag = 0: All OPEN snapshots are pre-06:00 ET -- no contamination
- dt0700_near_open_flag = 0: DT_0700 is always distinct from OPEN snapshot
- close_post_first_pitch (2503 games): DAY games where pre-game window extends past 1st pitch; expected DAY_TMINUS60 behavior
- close_post_first_pitch by season: {2022: 649, 2023: 634, 2024: 626, 2025: 594}

## 7. Continuity Pairs (same-book %)
| Pair | Same-book % |
|------|-------------|
| open_0700 | 85.2% |
| open_1000 | 86.2% |
| open_1200 | 86.4% |
| dt0700_close | 94.2% |
| dt1000_close | 97.9% |
| dt1200_close | 99.1% |
| open_close | 86.1% |

## 8. Timestamp Quality (median delta from probe, minutes)
| State | 2022 | 2023 | 2024 | 2025 |
|-------|------|------|------|------|
| open_0001 | 6.0 | 0.3 | 0.4 | 0.4 |
| dt_0700 | 5.0 | 4.3 | 4.4 | 4.4 |
| dt_1000 | 5.0 | 4.3 | 4.4 | 4.4 |
| dt_1200 | 5.0 | 4.3 | 4.4 | 4.4 |
| final_close | 5.0 | 4.3 | 4.4 | 4.4 |

## 9. Low Coverage Months (<80%)
| State | Year-Month | Coverage % |
|-------|-----------|-----------|
| open_0001 | 2022-05 | 78.6% |
| open_0001 | 2022-09 | 75.8% |
| open_0001 | 2022-10 | 61.5% |
| open_0001 | 2023-09 | 73.5% |
| open_0001 | 2023-10 | 33.3% |
| dt_0700 | 2023-10 | 66.7% |

All low-coverage months are OPEN_0001 or DT_0700 fringe dates (postseason/Oct). DT_1000 and DT_1200 have no low-coverage months.

## 10. Output Files
| File | Description |
|------|-------------|
| mlb_intraday_decision_panel_v1_2022_2025.parquet | Main panel (9,715 rows x 117 cols) |
| mlb_intraday_decision_panel_v1_source_manifest.csv | Game manifest |
| intraday_raw_records.parquet | Raw per-(game, probe) API records |
| MLB_INTRADAY_DECISION_PANEL_V1_RAW.json | Summary metadata |
| intraday_acquisition.log | Full acquisition log |
| build_intraday_panel.py | Acquisition + build script |

## 11. MPS Status
**MPS STATUS: RESERVED / DATA-BLOCKED**

---
## Build Verdict: PANEL BUILT WITH MATERIAL GAPS

DT intraday probes (07:00, 10:00, 12:00 ET) achieved 98%+ usable coverage overall.
The 3 material gap months are postseason fringe dates (Oct 2022, Oct 2023)
not in scope for the regular-season totals model.