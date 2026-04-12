# Phase 3: Implementation Fixes

## Fix 1: Threshold Update
- **File:** `mlb_sim/pipeline/f5_runline_signal_generator.py`
- **Change:** `XFIP_GAP_THRESHOLD = 1.0` -> `XFIP_GAP_THRESHOLD = 1.5`
- **Docstring:** Updated to reflect "xFIP mismatch >= 1.5"
- **Rationale:** Reset audit directive + PIT FIP gap analysis shows 1.5 is the
  clean threshold with consistent 59-60% hit rate across 2024-2025.

## Fix 2: Status File Update
- **File:** `mlb_sim/pipeline/f5_runline_status.json`
- **Change:** `"status": "ACTIVE"` -> `"status": "SHADOW"`
- **Rationale:** State map (02_state_map.md) directed Signal B to SHADOW.
  SHADOW allows signal generation to continue (for tracking) but communicates
  that the signal is not being live-traded.
- **Note:** Code only blocks on `"PAUSED"`, so SHADOW signals will still fire and log.

## No Other Changes Required
- Home-only routing: already correct
- Feature source: already clean (live FG API)
- Grading logic: already correct
- Hard stop logic: already correct (-10% ROI at N>=40)
- Tracker files: not modified (old entries preserved with legacy threshold data)

## Tracker Handling
The existing 7 tracker entries remain unchanged. They were generated under the
1.0 threshold and are labeled with their actual xfip_gap values. Any performance
analysis should filter to gap >= 1.5 only, or use a date cutoff of 2026-04-12.
