# Phase 2: Tracker Audit

## Current Tracker State (2026-04-12)

### Signal Log: mlb_sim/logs/f5_runline_2026.parquet
| Date | Gap | Side | Resolved | Result |
|------|-----|------|----------|--------|
| 2026-03-30 | 1.080 | HOME | 1 | LOSS |
| 2026-04-01 | 1.005 | HOME | 1 | WIN |
| 2026-04-04 | 1.130 | HOME | 1 | LOSS |
| 2026-04-05 | 1.503 | HOME | 1 | LOSS |
| 2026-04-06 | 1.208 | HOME | 1 | LOSS |
| 2026-04-07 | 1.009 | HOME | 1 | WIN |
| 2026-04-10 | 1.074 | HOME | 1 | LOSS |

- Total entries: 7
- All resolved: 7/7
- Record: 2W-5L (28.6% win rate)
- Gap < 1.5: 6 entries (should NOT have fired under revised threshold)
- Gap >= 1.5: 1 entry (would have fired under revised threshold)

### Mixed Threshold Problem
The tracker contains signals from TWO different threshold eras:
- 6 entries fired at gap 1.0-1.49 (old threshold, should not exist under 1.5 rule)
- 1 entry fired at gap >= 1.5 (valid under new threshold)

These populations are NOT comparable. The 1.0 and 1.5 thresholds produce
fundamentally different signal quality (50-53% vs 59-60% hit rate in PIT analysis).

### Decision: TRACKER REQUIRES SEPARATION
Options:
1. **Date cutoff:** Mark all pre-fix entries as "legacy_threshold_1.0"
2. **New tracker:** Start fresh post-fix (cleanest)
3. **Filter:** Only count gap >= 1.5 entries going forward

**Recommended: Option 1 — add a threshold_era field and date cutoff.**
The single gap=1.503 entry is a valid signal but a LOSS. Starting count from
the fix date is cleanest for performance tracking.

### Status File
```json
{
  "status": "ACTIVE",
  "last_updated": "2026-03-25",
  "deployment_note": "Signal B live launch with conservative 0.5u stake"
}
```
Status says ACTIVE but the state map (02_state_map.md) directed SHADOW.
This is a second mismatch: Signal B should be in SHADOW until reactivation is approved.

### Performance File
Not yet checked — will be recomputed after threshold fix.
