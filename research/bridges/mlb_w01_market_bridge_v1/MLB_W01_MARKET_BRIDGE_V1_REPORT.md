# MLB W01 MARKET BRIDGE V1 — BUILD REPORT

**Build Date:** 2026-04-19
**Shape:** 19,430 x 131
**Purpose:** One-time closing total bridge for W01B economic reality check

## Source
- Bridge source: `mlb_sim/data/mlb_odds_closing_canonical.parquet`
- Bookmaker: DraftKings (`book_key == "draftkings"`)
- Market: full-game total (`total_line` field)
- Selection: latest `pull_timestamp` per `game_pk`, null total_line dropped

## Join
- Key: `game_pk` (type-aligned to int64)
- Rows before: 19,430 | Rows after: 19,430
- Grain duplicates: 0
- closing_total null rate: 2.2% (436/19,430)

## Coverage by Season
| Season | Non-null | Total | Coverage |
|---|---|---|---|
| 2022 | 4,674 | 4,860 | 96.2% |
| 2023 | 4,742 | 4,860 | 97.6% |
| 2024 | 4,784 | 4,854 | 98.6% |
| 2025 | 4,794 | 4,856 | 98.7% |

## What This Does Not Authorize
- Does not modify MLB_RUNTIME_OBJECT_V1
- Does not promote the closing source into the frozen package
- Does not authorize general market-data use outside this bridge
- Does not prove any W01 economic result by itself

## Final Status
**BRIDGE_READY**
