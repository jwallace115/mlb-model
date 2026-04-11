# Site Reset Executive Memo
Date: 2026-04-11

## What Happened
Operational reset of the dashboard to align displayed states with audited truth.
Multiple objects had stale or misleading status labels. No model logic, signal
generation, or cron scheduling was modified.

## Summary of Changes

### Dashboard File
- `/root/mlb-model/dashboard.py` (backup at `dashboard.py.bak.20260411`)
- Applied via `research/recovery/site_reset/apply_dashboard_patch.py`

### MLB Tab
1. **V1 Full-Game Totals** pill changed from green "V1" to amber "V1 Legacy"
2. **F5 Totals Engine** pill changed from green to gray "F5 Inactive"
3. **S12 Overlay** pill changed from green to gray "S12 Archived"
4. **P09 Overlay** pill changed from green to gray "P09 Archived"
5. **Signal B (F5 RL)** relabeled from "F5 RL Signal B" to "Signal B (F5 RL)"
6. Consolidated engine panel restructured into 4 categories:
   - Active: Signal B (F5 RL)
   - Shadow: CS013, CS028, KP04, ST02, CS004, BASE_HIGH, S12_HIGH
   - Inactive: F5 Totals, ADJ Hard Hit, ADJ Contact, ADJ K-rate, ADJ BB rate, ADJ Run Supp
   - Archived: V1 Totals, S12 overlay, P09 overlay, Team Totals
7. V1 legacy disclaimer added below hard stop monitor
8. Season banner label changed from "Live Production" to "Production Record"

### NHL Tab
1. Legacy system disclaimer added above 14-day results banner
2. Legacy system disclaimer added above recent results section
3. "ARCHIVED -- Legacy System" label added to Season Performance (Historical Backtest) section
4. Note: "MoneyPuck-dependent, identity broken Apr 11. New aligned Model A tracker starts fresh."

### NBA Tab
- No display changes needed. BALANCED_OFF, ELITE_OREB, and ELITE_DEF2 are not
  explicitly surfaced in the UI (they are implicit in the archetype classification
  system). The active tiers (TIER_1A, TIER_1B, TIER_2, REF_UNDER, P1, P2, P4)
  correctly reflect LIVE status for the core ridge model.

### Tracker Tab
1. "V1 UNDER" relabeled to "V1 Legacy"
2. "F5 Run Line" relabeled to "Signal B (RL)"
3. "S12 overlay" relabeled to "S12 Archived"
4. "P09 overlay" relabeled to "P09 Archived"

## What Was NOT Changed
- No model logic modified
- No signal generation modified
- No cron/launchd scheduling modified
- No data files deleted or modified
- No tracker data purged -- all historical records preserved
- V1 engine still runs daily (clean inference), just honestly labeled
- All shadow monitors continue operating identically

## Files Created
- `research/recovery/site_reset/01_inventory.md` -- full object inventory
- `research/recovery/site_reset/02_state_map.md` -- LIVE/SHADOW/INACTIVE/ARCHIVED assignments
- `research/recovery/site_reset/03_tracker_reset_plan.md` -- tracker separation plan
- `research/recovery/site_reset/04_executive_memo.md` -- this file
- `research/recovery/site_reset/apply_dashboard_patch.py` -- reproducible patch script
