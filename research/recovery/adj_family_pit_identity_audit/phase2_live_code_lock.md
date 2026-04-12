# Phase 2 — Live/Shadow Object Lock

## Live Code: `mlb_sim/pipeline/shadow_signals.py`

### Gate Logic (lines 197-232)
```python
def compute_adj_signals(home_pitcher_id, away_pitcher_id):
    home_form = get_pitcher_adj_form(home_pitcher_id) or {}
    away_form = get_pitcher_adj_form(away_pitcher_id) or {}
    for metric in [...]:
        combined = (h_val + a_val) / 2
        results[metric] = {
            "favorable_zone_flag": combined > 0,   # <-- STANDALONE gate
        }
```

### V1 Direction Context (lines 237-257)
```python
def _v1_direction(proj):
    v1_p_under = 1.0 - proj.get("sim_p_over", 0.5)
    if v1_p_under > 0.57: return "UNDER"
    elif v1_p_under < 0.45: return "OVER"
    else: return "NEUTRAL"
```

V1 direction is computed and LOGGED as `v1_direction_context` but does NOT gate
`favorable_zone_flag`. It is metadata only.

### Confirmation from Shadow Log
All 258 favorable-zone records in the 2026 shadow log have:
```
v1_direction_context: "NONE"
```
This means the V1 projection is either not available or not being passed in.
The signals fire purely on `combined > 0`.

## Verdict
The live shadow code implements the STANDALONE version, not the V1-interaction
version from the original research. This is a different object.
