# Phase 0: C8 Exact Object Lock

## Signal Definition
**C8: Command vs Stuff Archetype** — Back the "command" pitcher when facing a "stuff" pitcher in close MLB moneyline games.

## Exact Thresholds

### Classification Method
- **Median split** on within-sample data (NOT fixed thresholds)
- Whiff rate and zone rate each split at their in-sample median
- This is a LEAK concern: medians shift per-phase

### Archetype Assignment
- **"Stuff" pitcher**: whiff_r10 > median AND zone_r10 <= median
  - High swing-and-miss, but poor command
- **"Command" pitcher**: zone_r10 > median AND whiff_r10 <= median
  - Good command/control, but not overpowering
- **"Both" or "Neither"**: excluded (bet_side = "skip")
  - Pitcher with both high whiff + high zone (elite) = skip
  - Pitcher with both low whiff + low zone (bad) = skip

### Feature Construction
- **Source**: `pitcher_statcast_per_start_starters_only.parquet`
- **whiff_r10**: rolling 10-start mean of `whiff_rate`, min_periods=5, shift(1)
- **zone_r10**: rolling 10-start mean of `zone_rate`, min_periods=5, shift(1)
- PIT-safe: shift(1) ensures no same-day leakage

### Bet Logic
- When home SP = command AND away SP = stuff: bet **home**
- When away SP = command AND home SP = stuff: bet **away**
- All other matchups: **skip**

### Universe
- Close moneyline games: max(p_home, p_away) in [0.512, 0.556]
  - Approx American odds: -105 to -125
- Excludes ties (pushed to settlement)
- 2022-2025 regular season

### Rolling Window
- 10 starts, min 5 starts required
- This means pitchers need 5+ starts in current season before qualifying

### Minimum Starts Requirement
- Implicit via min_periods=5 in rolling window
- No explicit min-starts gate beyond rolling requirement

### Discovery Medians (frozen reference)
- whiff_r10 median: 0.2245
- zone_r10 median: 0.4913

## Data Quality Note
Home-side Statcast coverage is 2,020/3,289 (61%) vs away-side 3,292/3,289 (100%+, due to merge inflation).
The home SP merge has fewer matches because PGL home starters cover only 7,452 unique games vs 9,932 away.
This asymmetry means C8 results may be biased toward away-SP-matched games.
