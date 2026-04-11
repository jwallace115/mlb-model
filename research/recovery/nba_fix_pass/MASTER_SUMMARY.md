# NBA Fix Pass -- Master Summary

**Date:** 2026-04-11
**Verdict:** READY FOR TAB BUILD

---

## What Changed

### nba/run_nba.py (6 edits, 0 files created)

1. **ELITE_DEF2 signal killed** (line 631) -- `if False:` guard prevents all firing paths
2. **Location-split rolling added** to `_build_current_team_states()` -- computes ortg/drtg/pace separately for home and away games, matching training features.py
3. **feat_row wired to location splits** -- Ridge now receives `ortg_home`/`ortg_away` instead of overall values; uses raw state (pre-injury) matching training's injury_adj=0.0
4. **Playoff blend extended** to location-split keys in `_blend_playoff_features()`
5. **Playoff blend applied to raw state** so feat_row receives playoff adjustments
6. **LOCATION_MIN_GAMES imported** from config

### What Did NOT Change
- ROAD_WARRIOR signal (only surviving archetype)
- All other archetype signals (context-only, no standalone bets)
- Playoff boards P1/P2/P4 (structurally sound)
- Training code, model files, features.py
- No MLB, NHL, Golf, Soccer, or dashboard files touched

---

## Impact Estimate

- **ELITE_DEF2 kill:** Removes ~9 harmful UNDER signals per season (~1 per month during RS)
- **Location splits:** Corrects median 1.8 pts of feature noise on 6 of 15 Ridge inputs (the 6 with largest coefficients)
- **Injury disable:** Removes up to 4.5 pts of train/live ORtg shift on games with multiple injuries

---

## Files Modified
- `/root/mlb-model/nba/run_nba.py`

## Documentation Created
- `research/recovery/nba_fix_pass/NBA_FIX_PASS_FINAL_VERDICT.md`
- `research/recovery/nba_fix_pass/MASTER_SUMMARY.md`
- `research/recovery/nba_fix_pass/nba_fix_pass_verdicts.csv`
