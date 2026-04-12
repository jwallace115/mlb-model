# Phase 7: Reactivation Decision

## Gate: 30+ resolved signals at gap >= 1.5

### Current State
- Resolved signals at gap >= 1.5: **1** (the 2026-04-05 entry, gap=1.503, LOSS)
- Required: 30+
- **GATE: FAIL (1/30)**

### Projected Timeline
Historical firing rate at gap >= 1.5:
- 2024: 32 signals over full season (~162 games)
- 2025: 35 signals over full season
- Average: ~0.2 signals per day (roughly 1 every 5 days)
- Time to 30 signals: approximately 150 calendar days from now
- **Estimated gate date: ~September 2026**

### Decision: SHADOW
Signal B is assigned to SHADOW status. It will:
1. Continue generating signals daily (when gap >= 1.5 exists)
2. Continue logging to tracker (parquet + JSON)
3. Continue being pushed to GitHub (for dashboard access)
4. NOT show as a live play on the dashboard (no green pill)
5. NOT be treated as a live betting recommendation

### Reactivation Criteria
To move from SHADOW to LIVE, Signal B must meet ALL of:
1. 30+ resolved signals at gap >= 1.5 threshold
2. Win rate >= 55% on resolved signals
3. ROI > 0% on resolved signals
4. No hard stop triggered
5. Manual review and authorization

### Monitoring
- Weekly: Check `f5_runline_performance_2026.json` for accumulating signals
- Monthly: Review win rate trend at 1.5 threshold
- At N=30: Run formal reactivation review
