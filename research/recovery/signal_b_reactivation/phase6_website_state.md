# Phase 6: Website State Check

## Dashboard References
The active dashboard is `dashboard_original_pre_refactor.py`.

### Signal B Display Points
1. **Green pill** (line 3230-3235): Shows "Signal B (F5 RL)" green pill when
   status file reads ACTIVE. With SHADOW status, pill will NOT appear. CORRECT.

2. **Tracker tab** (lines 3326, 3576): Loads `f5_runline_2026.json` and displays
   W-L-P record. Will still show 7 legacy entries. These should display with
   a disclaimer or be filtered to gap >= 1.5 in a future dashboard update.

3. **Signal board** (line 5930-5969): Computes W-L-P and ROI from the JSON file.
   Currently shows 2-5-0 record from legacy threshold signals. Misleading but
   low-impact since the signal board is an internal reference.

### Push Pipeline
- `push_results.py` line 411 pushes `f5_runline_2026.json` to GitHub for Streamlit.
- This continues to work regardless of SHADOW status.

## Website State Summary
| Component | Current State | Correct? |
|-----------|--------------|----------|
| Green pill | Hidden (SHADOW status) | YES |
| Tracker record | Shows 2-5-0 (legacy) | NEEDS DISCLAIMER |
| Signal board | Shows legacy ROI | NEEDS DISCLAIMER |
| JSON push | Active | YES |

## Recommended Dashboard Actions (future, not blocking)
1. Add "Legacy (threshold 1.0)" label to pre-2026-04-12 entries
2. Show separate "Post-fix record" section for gap >= 1.5 signals
3. Consider adding threshold_era column to tracker display
