# Phase 1: Parity / Identity Audit

## Line-by-Line Implementation Check

### 1. xfip_gap threshold
- **Spec (reset audit):** >= 1.5
- **Code (XFIP_GAP_THRESHOLD):** 1.0
- **MISMATCH — must fix**

### 2. Home-only routing
- **Spec:** HOME only (D4 away killed)
- **Code:** `bet_side = "HOME"` hardcoded at line 373
- **MATCH**

### 3. Feature source
- **Spec:** Live FanGraphs xFIP via get_pitcher_metrics()
- **Code:** `from modules.pitchers import get_pitcher_metrics` at line 306
  - get_pitcher_metrics() pulls from pitcher_db, which is populated from FanGraphs API
  - Fallback: Savant xERA -> league average
- **MATCH — clean, no V1/PIT dependency**

### 4. V1/S12/P09 dependency
- **Spec:** None
- **Code:** No imports from V1 engine, no feature_table references, no sim model calls
- **MATCH — fully independent**

### 5. Contaminated tables in chain
- **Check:** The signal generator imports only:
  - `modules.pitchers.get_pitcher_metrics` (clean: live API)
  - `modules.odds.ODDS_API_TEAM_MAP` + `config.ODDS_API_KEY` (clean: config)
  - `mlb_sim.pipeline.f5_runline_tracker` (clean: reads own log only)
- **MATCH — no contaminated inputs**

### 6. Bet mechanics
- **Spec:** Home -0.5 F5 spread, 0.5u stake
- **Code:** Validates `{h_line, a_line} == {0.5, -0.5}`, stake = 0.5
- **MATCH**

### 7. Grading logic
- **Code:** margin > 0 = WIN, < 0 = LOSS, == 0 = PUSH
- **Tracker:** Pushes treated as -stake (count as losses)
- **Consistent with conservative grading**

## Summary
| Check | Status |
|-------|--------|
| Threshold | MISMATCH (1.0 vs 1.5 required) |
| Home-only | PASS |
| Feature source | PASS (live FG API) |
| V1 dependency | PASS (none) |
| Contaminated tables | PASS (none) |
| Bet mechanics | PASS |
| Grading | PASS |

**Single defect: threshold must be updated from 1.0 to 1.5.**
