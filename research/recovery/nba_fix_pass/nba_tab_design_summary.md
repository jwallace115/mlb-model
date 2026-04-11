# NBA Tab Build Summary

**Date**: 2026-04-11
**File modified**: `dashboard.py` (`_render_nba_tab` only)
**Other files modified**: None

## Data Sources

| Source | Path | Purpose |
|--------|------|---------|
| Signal log | `nba/data/nba_signal_log.parquet` | Historical signals + results (35 rows, 2026-03-24 to 2026-04-10) |
| Today's card | `nba_results.json` | Current-day plays, season accuracy, signal tracking |
| Timestamps | `shared/last_updated.json` | Pipeline freshness (`nba` key) |

## Signal Log Schema

- **Columns**: game_date, home_team, away_team, signal_type, tier, direction, closing_line, book_used, units, venue_signal, oreb_confirms, shot_over_signal, pace_signal, shot_under_signal, actual_total, result, units_won_lost, notes
- **signal_type values**: ROAD_WARRIOR_at_STRONG_HOME (7), REF_UNDER (19), OREB_CONFIRMS (7), BALANCED_vs_PASSIVE (2)
- **tier values**: TIER_1A, TIER_1B, TIER_2 (Road Warrior); REF_UNDER (referee signals)
- **result values**: WIN, LOSS, PUSH, NaN (pending)

## Tab Layout (10 sections)

1. **Status header** (LIVE) -- Road Warrior model, ID `nba_road_warrior_20260322`, started March 22
2. **Status header** (SHADOW) -- Referee Under, ID `nba_ref_under_20260322`
3. **Signal status pills** -- Active: Road Warrior + tier pills; Shadow: Ref Under, OREB Confirms
4. **Archetype rules block** -- Stake sizing: TIER_1A/1B = 1.5u, TIER_2 = 1.0u, REF_UNDER = 0.75u
5. **Today's signals** -- From nba_results.json plays list, fallback to signal log for today's date
6. **Road Warrior tracker** -- W-L-P, hit rate, ROI (units P&L / units staked), pending count
7. **Road Warrior table** -- Date, Matchup, Tier, Dir, Line, Units, Result, P&L
8. **Ref Under shadow tracker** -- Same layout as Road Warrior but labeled "shadow"
9. **Core model accuracy** -- From nba_results.json season_accuracy (MAE, hit rate, bias)
10. **Legacy disclosure** -- NBA Base Model archived March 2026, PLAYOFF_BOARDS inactive

## Design Decisions

- Road Warrior is marked LIVE (it has real unit sizing and tracked results)
- REF_UNDER is marked SHADOW (flat 0.75u, tracking only)
- ROI calculated as units_won_lost / units_staked (actual P&L, not flat-bet approximation)
- Today's signals: primary source is nba_results.json `plays` list; fallback to signal_log filtered to today's date
- Follows NHL tab pattern: render_status_header, _universal_pill, _render_game_card_universal from dashboard_components.py

## Current Tracker State (at build time)

**Road Warrior**: 7 total signals, 4 resolved (2W-2L-0P), 3 pending
**Ref Under**: 19 total signals, all resolved direction UNDER
