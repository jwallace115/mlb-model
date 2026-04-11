# Phase 4: Tracker Reset Plan
Generated: 2026-04-11

## Trackers Requiring Reset

### 1. NHL Live Record
- **Old tracker:** `nhl/nhl_decisions.parquet` (split="live")
- **Old state:** Contains all graded signals from old MoneyPuck-dependent system
- **Issue:** MoneyPuck source identity broken; old calibration no longer valid
- **Action:** Old records remain in parquet (no deletion). Dashboard now labels them as
  "Legacy record from pre-reset system." New aligned Model A tracker starts from
  the next signal generated after model alignment.
- **New tracker start date:** 2026-04-11 (first signal after reset)
- **Implementation:** Dashboard disclaimer added above W-L-P banner and recent results.
  No data file changes needed — the `split` field or a date cutoff will separate eras.

### 2. MLB Signal B (F5 Run Line)
- **Old tracker:** `mlb_sim/logs/f5_runline_2026.json`
- **Old state:** Tracking with threshold 1.0
- **Issue:** Threshold changed to 1.5; old signals under 1.0 threshold are not comparable
- **Action:** Old records remain in JSON (no deletion). If threshold change produces
  materially different signal population, a date cutoff should be applied.
  Dashboard relabeled from "F5 Run Line" to "Signal B (F5 RL)".
- **New tracker separation:** Apply date cutoff at threshold change date if needed.

### 3. MLB V1 Full-Game Totals
- **Old tracker:** `mlb_sim/logs/signals_2026.json`
- **Old state:** Tracking as live production record
- **Issue:** Historical validation void. Record is unvalidated legacy data.
- **Action:** Records remain. Dashboard now labels as "V1 Legacy" and shows disclaimer:
  "V1 historical validation void (Apr 11 reset). Engine runs for research continuity.
  Record shown is unvalidated legacy data."
- **No new tracker:** V1 is ARCHIVED, not expected to return.

### 4. MLB S12/P09 Overlays
- **Old tracker:** Computed from `signals_2026.json` (s12_overlay_active, p09_overlay_active)
- **Old state:** Tracked as active overlays in tracker tab
- **Action:** Labels changed to "S12 Archived" and "P09 Archived" in tracker.
  Records remain for historical reference.

## Trackers NOT Requiring Reset

- **NBA:** Core Ridge model and ROAD_WARRIOR @ STRONG_HOME continue as LIVE.
  Signal log (`nba_signal_log.parquet`) unchanged.
- **Soccer:** Continues as SHADOW. No changes.
- **Golf:** Continues as SHADOW. No changes.
- **MLB CS013/CS028/KP04/ST02/CS004:** Continue as SHADOW. No changes.
- **MLB BASE_HIGH/S12_HIGH:** Continue as SHADOW observation. No changes.
