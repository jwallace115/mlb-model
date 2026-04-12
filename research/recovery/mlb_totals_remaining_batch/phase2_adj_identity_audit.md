# Phase 2 — ADJ Signal Identity Audit

**Date:** 2026-04-12
**Objects:** C1 ADJ_CONTACT, C2 ADJ_HH, C3 ADJ_K_RATE, C5 ADJ_RUN_SUPP

---

## Identity Discrepancy

The ADJ signals exist in TWO forms:

### Form 1: Live Shadow (mlb_sim/pipeline/shadow_signals.py)
- Features: opponent-adjusted rolling(3) metrics from pitcher_recent_adjusted_features.parquet
- Gate: combined = (home_val + away_val) / 2; favorable_zone = combined > 0
- Direction: UNDER when favorable_zone_flag = True
- **No V1 interaction gate.** Fires purely on pitcher form.

### Form 2: Original Scanner (research/signal_discovery/)
- Same underlying features
- Gate: V1 p_under > 0.57 AND signal condition met
- The V1 gate was CONTAMINATED (look-ahead bias)

### Standalone Rebuild (research/recovery/adj_standalone_rebuild/)
- Tested Form 1 (no V1 gate) on 2022-2025 with actual closing under prices
- All 5 signals: DIMINISHED (ROI -0.6% to -3.6% across full sample)
- BUT: 2025 showed positive ROI for ADJ_HH (+5.6%), adj_k_rate (+4.1%),
  ADJ_RUN_SUPP (+1.8%), ADJ_CONTACT (+0.4%)
- This 2025 improvement motivated continued shadow monitoring

## Current Identity

The live shadow IS the same object as the standalone rebuild test.
Both use combined > 0 with no V1 gate. The identity is consistent.

The 2022-2025 backtest showed these signals are breakeven-to-slightly-negative
across the full sample. The question is whether 2025 improvement + 2026 shadow
represent genuine signal emergence or noise.

## 2026 Shadow State (as of 2026-04-12)

| Signal | Fired | Resolved | W | L | P | Hit% |
|--------|-------|----------|---|---|---|------|
| ADJ_HH | 47 | 34 | 21 | 12 | 1 | 63.6% |
| adj_k_rate | 38 | 30 | 17 | 11 | 2 | 60.7% |
| ADJ_RUN_SUPP | 55 | 34 | 19 | 13 | 2 | 59.4% |
| ADJ_CONTACT | 92 | 65 | 35 | 28 | 2 | 55.6% |
| ADJ_BB_RATE | 26 | 16 | 8 | 8 | 0 | 50.0% |

### Key Observations

1. **ADJ_HH is the strongest** (63.6% hit rate on 33 decisions). Breakeven at -110
   is 52.4%. This is well above breakeven IF the sample holds.

2. **adj_k_rate is second** (60.7% on 28 decisions). Also well above breakeven.

3. **ADJ_RUN_SUPP is third** (59.4% on 32 decisions). Above breakeven.

4. **ADJ_CONTACT is marginal** (55.6% on 63 decisions). Above breakeven but the
   largest sample and thinning toward the 52.4% breakeven.

5. **ADJ_BB_RATE confirms CLEAN KILL** (50.0% on 16 decisions). Dead.

### Missing Data Problem

**No closing under prices are logged in the shadow tracker.** The W-L record
uses total line vs actual total, which is equivalent to -110 flat bet grading.
Real under prices vary from -105 to -125. Without actual prices, ROI cannot
be computed precisely.

## Verdict Update

| Signal | Prior | Updated | Rationale |
|--------|-------|---------|-----------|
| ADJ_HH | RETEST @ N=100 | CONTINUE SHADOW | 63.6% hit on 33 decisions is promising but N too small |
| adj_k_rate | RETEST @ N=100 | CONTINUE SHADOW | 60.7% hit on 28 decisions; same caveat |
| ADJ_RUN_SUPP | RETEST @ N=100 | CONTINUE SHADOW | 59.4% on 32; same caveat |
| ADJ_CONTACT | RETEST @ N=100 | CONTINUE SHADOW | 55.6% on 63; approaching evaluation threshold |
| ADJ_BB_RATE | CLEAN KILL | CONFIRMED KILL | 50.0% on 16; consistent with backtest |

**Action items:**
1. Add closing under price logging to shadow_signals.py (one-time fix, NOT done in this batch)
2. Review ADJ_HH, adj_k_rate, ADJ_RUN_SUPP at N=50 resolved (est. late April 2026)
3. Review ADJ_CONTACT at N=100 resolved (est. early May 2026)
4. Kill threshold remains: hit rate < 52% at review date
