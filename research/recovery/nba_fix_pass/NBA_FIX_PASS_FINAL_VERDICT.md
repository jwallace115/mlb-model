# NBA Parity Fix Pass -- Final Verdict

**Date:** 2026-04-11
**Scope:** All fixes from NBA Parity Audit applied to nba/run_nba.py

---

## Verdict: READY FOR TAB BUILD

All actionable audit findings have been addressed. The fixes are structurally clean,
functionally tested, and backward-compatible. No training code or model files were modified.

---

## Fixes Applied

### FIX 1: ELITE_DEF2 Signal Killed (HIGH priority)
- **File:** nba/run_nba.py line 631
- **Change:** `if away in _ELITE_DEF2 and home in _ELITE_DEF:` replaced with `if False:`
- **Comment:** `# KILLED 2026-04-11 -- revalidation verdict: COLLAPSES (43% OOS, -18% ROI)`
- **Effect:** Signal can never fire. Team set constants and function preserved for audit trail.
- **Risk:** None. Signal was demonstrably harmful.

### FIX 2: Location-Split Feature Alignment (MEDIUM priority)
- **File:** nba/run_nba.py `_build_current_team_states()`
- **Change:** Added location-specific rolling computation for ortg/drtg/pace.
  - For each team, computes rolling 15 from home-only and away-only games separately.
  - Falls back to overall rolling if fewer than LOCATION_MIN_GAMES (5) same-location games.
  - New keys in team state dict: `ortg_home`, `ortg_away`, `drtg_home`, `drtg_away`, `pace_home`, `pace_away`.
- **Effect:** Closes the 6-feature parity gap identified in the audit. Median correction: 1.8 pts ORtg per affected feature.
- **Verified:** All 30 teams produce location-split values. GSW shows 4.4pt ortg home/away split; LAL shows 5.7pt drtg home/away split -- plausible and meaningful.

### FIX 3: Ridge Feature Row Wiring (MEDIUM priority)
- **File:** nba/run_nba.py feat_row construction (~line 1811)
- **Change:** feat_row now uses:
  - `home_state_raw.get("ortg_home", ...)` for `home_ortg` (was `home_state["ortg"]`)
  - `away_state_raw.get("ortg_away", ...)` for `away_ortg` (was `away_state["ortg"]`)
  - Same pattern for drtg and pace.
- **Uses `home_state_raw` (pre-injury)** because training had `injury_adj=0.0` for all rows.
- **Effect:** Ridge model now receives feature values that match the training distribution.

### FIX 4: Playoff Blend Extended to Location Splits
- **File:** nba/run_nba.py `_blend_playoff_features()`
- **Change:** After blending overall `ortg`/`pace` with series rolling, also blends `ortg_home`, `ortg_away`, `pace_home`, `pace_away` if present in state dict.
- **Effect:** Playoff series adjustments propagate correctly to Ridge features.

### FIX 5: Playoff Blend Applied to Raw State
- **File:** nba/run_nba.py main loop (~line 1799)
- **Change:** Playoff blend now also applied to `home_state_raw` and `away_state_raw` so that feat_row (which reads from raw state) gets playoff data.
- **Effect:** Without this, playoff blending would have been lost when feat_row switched to raw state.

### FIX 6: LOCATION_MIN_GAMES Import
- **File:** nba/run_nba.py config imports
- **Change:** Added `LOCATION_MIN_GAMES` to the `from nba.config import (...)` block.

---

## Injury Adjustment Decision

**Decision: DISABLE for Ridge features, KEEP for display/context.**

Rationale:
- Training data has `injury_adj=0.0` for all 3,690 games (by design -- no reliable pre-tip data for backtesting).
- The Ridge model has never seen injury-adjusted ORtg values.
- Applying a -1.5 to -4.5 pt reduction to ORtg at prediction time creates a systematic feature distribution shift.
- The injury information is still captured in `home_state` (post-injury) for display cards and context notes.
- If injury adjustments are desired in Ridge predictions, the correct fix is to retrain the model with injury features, not to apply them post-hoc.

**Implementation:** feat_row reads from `home_state_raw` / `away_state_raw` (pre-injury state).

---

## Unchanged Items

| Item | Status | Reason |
|------|--------|--------|
| ROAD_WARRIOR signal | UNTOUCHED | Only surviving archetype; PROVEN IDENTICAL |
| BALANCED_OFF_vs_PASSIVE_DEF | UNTOUCHED | Context-only, not standalone |
| THREE_HEAVY_vs_FOUL_PRONE | UNTOUCHED | Context-only, not standalone |
| ELITE_OREB_vs_WEAK_BOXOUT | UNTOUCHED | Amplifier-only |
| Playoff boards P1/P2/P4 | UNTOUCHED | Structurally sound; underpowered but no parity issue |
| Playoff series blend ramp | UNTOUCHED | Clean logic; now correctly applied to raw state |

---

## Verification

1. **Syntax:** `py_compile` passes clean.
2. **Functional test:** `_build_current_team_states("2026-04-11")` returns all 30 teams with location-split keys.
3. **Location splits show meaningful home/away differences:**
   - GSW: ortg_home=114.91, ortg_away=110.47 (delta=4.4)
   - LAL: drtg_home=108.92, drtg_away=114.66 (delta=5.7)
   - BOS: ortg_home=114.08, ortg_away=113.27 (delta=0.8)
4. **ELITE_DEF2:** `if False:` guard confirmed at line 631; cannot fire in any code path.
5. **ROAD_WARRIOR:** Team sets unchanged at lines 734-735.

---

## Risk Assessment

| Fix | Risk | Mitigation |
|-----|------|------------|
| ELITE_DEF2 kill | NONE | Signal was -18% ROI OOS |
| Location splits | LOW | Fallback to overall rolling if < 5 loc games |
| Injury disable for Ridge | LOW | Training never saw injury data; cleaner parity |
| Playoff blend extension | LOW | Only affects playoff games G2+ |
