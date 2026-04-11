# Phase 1: Site Object Inventory
Generated: 2026-04-11

## MLB Tab Objects

| Object | Location | Current Display State | Tracker Source |
|--------|----------|----------------------|----------------|
| V1 Full-Game Totals UNDER | Game cards (green pill "V1"), season banner, tracker | ACTIVE — shown as live play with unit sizing | `mlb_sim/logs/signals_2026.json` |
| F5 Totals Engine | Game cards (green pill "F5 engine"), tracker | ACTIVE — shown as live play | `mlb_sim/logs/f5_signals_2026.json` |
| F5 Run Line (Signal B) | Game cards (green pill "F5 RL Signal B"), tracker | ACTIVE — shown as live play | `mlb_sim/logs/f5_runline_2026.json` |
| S12 Overlay | Game cards (green pill "S12"), tracker sub-row | ACTIVE — overlay on V1 | `s12_overlay_config.json` status check |
| P09 Overlay | Game cards (green pill "P09"), tracker sub-row | ACTIVE — overlay on V1 | `p09_overlay_config.json` status check |
| CS013 Bullpen | Game cards (yellow pill), consolidated panel | SHADOW | `cs013_shadow` logs |
| CS028 Blowup | Game cards (yellow pill), consolidated panel | SHADOW | `cs028_shadow` logs |
| KP04 K-prop | Game cards (yellow pill), consolidated panel | SHADOW | `kp04_shadow` logs |
| ST02 Road Fatigue | Game cards (yellow pill), consolidated panel | SHADOW | `shadow_signals` logs |
| ADJ Hard Hit | Game cards (yellow pill), consolidated panel | SHADOW | `shadow_signals` logs |
| ADJ Contact | Game cards (yellow pill), consolidated panel | SHADOW | `shadow_signals` logs |
| ADJ K-rate | Game cards (yellow pill), consolidated panel | SHADOW | `shadow_signals` logs (removed from panel) |
| ADJ BB rate | Game cards (yellow pill), consolidated panel | SHADOW | `shadow_signals` logs |
| ADJ Run Supp | Game cards (yellow pill), consolidated panel | SHADOW | `shadow_signals` logs |
| Team Totals | Game cards (blue pill TT↓H/TT↓A), consolidated panel | SHADOW | `team_total_shadow` logs |
| BASE_HIGH / S12_HIGH | Shadow monitor section below season banner | SHADOW (shadow_only=True) | `signals_2026.json` (shadow_only flag) |
| Sim engine status | Consolidated panel green pill | Engine status check | `engine_status.json` |
| Hard stop monitor | Below season banner | Active through Apr 30 | Computed from `signals_2026.json` |

## NBA Tab Objects

| Object | Location | Current Display State | Tracker Source |
|--------|----------|----------------------|----------------|
| Core Ridge Totals | Game cards, TIER_1A/1B/2 plays | ACTIVE | `nba_results.json` |
| ROAD_WARRIOR @ STRONG_HOME | Part of bet_tier system (venue matchup) | ACTIVE via TIER_1A/1B | `nba_signal_log.parquet` |
| Venue OVER | Signal status pill, tracker | ACTIVE | `nba_signal_log.parquet` |
| OREB overlay | Signal status pill, tracker | ACTIVE | `nba_signal_log.parquet` |
| REF UNDER | Signal status pill, active tier, tracker | ACTIVE | `nba_signal_log.parquet` |
| Archetype UNDER | Shadow pill, shadow section | SHADOW | `nba_results.json` archetype_signal |
| Shot profile | Shadow pill, shadow section | SHADOW | `nba_results.json` shot_signal |
| Pace UNDER | Shadow pill | SHADOW | N/A |
| BALANCED_OFF | Part of archetype system | Implicit (no explicit display) | N/A |
| ELITE_OREB | Part of archetype system | Implicit (no explicit display) | N/A |
| ELITE_DEF2 | Part of archetype system | Not visible | N/A |
| Playoff P1/P2/P4 | Active tiers in _ACTIVE_TIERS | ACTIVE | `nba_results.json` |

## NHL Tab Objects

| Object | Location | Current Display State | Tracker Source |
|--------|----------|----------------------|----------------|
| Totals Model (old) | Signal cards, season performance, tracker | ACTIVE (live) | `nhl_decisions.parquet` |
| HIGH tier signals | Play cards | ACTIVE | `nhl_results.json` today_signals |
| MEDIUM tier signals | Shadow cards (SHADOW_) | SHADOW | `nhl_results.json` today_signals |
| Season Performance (Historical) | Backtest tabs (validate/OOS/combined) | Displayed as historical | `nhl_results.json` season_performance |
| Recent results table | 14-day table | ACTIVE | `nhl_results.json` recent_results |
| CLV Summary | CLV section | ACTIVE | `nhl_results.json` clv_summary |
| OT Diagnostics | OT section | ACTIVE | `nhl_results.json` ot_diagnostics |

## Tracker Tab Objects

| Object | Location | Current Display State | Tracker Source |
|--------|----------|----------------------|----------------|
| MLB panel | Full season + post-restructure + shadow | ACTIVE | Signal JSON files |
| NBA panel | Season W-L-P with sub-signals | ACTIVE | `nba_signal_log.parquet` |
| NHL panel | OVER/UNDER + tier breakdown | ACTIVE | `nhl_decisions.parquet` |
| Soccer panel | League + tier breakdown | ACTIVE | `soccer_decisions.parquet` |
| Golf panel | Market breakdown | ACTIVE | `golf_shadow_log.parquet` |
