# SIGNAL B THRESHOLD AND PIT — FINAL VERDICT

**Date:** 2026-04-12
**Auditor:** Claude (threshold provenance + PIT-safety proof)

---

## Three Claims — Verdicts

### Claim 1: The correct threshold is 1.5, not 1.0
**VERDICT: CONFIRMED**

The 1.0 threshold was a round-number heuristic selected from research that
used season-final (contaminated) xFIP. When tested with PIT-clean data
(expanding-mean xFIP, properly lagged), gap >= 1.0 shows only 50.3-53.1%
under rate — essentially a coin flip. Gap >= 1.5 shows 59.4-60.0% under rate,
stable across both 2024 and 2025. The threshold provenance chain has 8 events,
traced from original research through deployment to the current uncommitted fix.

**Evidence chain:**
1. Original research: 1.0 chosen on contaminated data
2. V1 dependency revalidation: PIT-clean test at 1.0 = borderline, at 1.5 = strong
3. Reset audit: directed change to 1.5
4. Signal B reactivation audit: implemented the change (uncommitted)

### Claim 2: The live pipeline is PIT-safe for daily operation
**VERDICT: CONFIRMED**

The live signal generator imports `get_pitcher_metrics()` from `modules/pitchers.py`,
which pulls xFIP from the FanGraphs API. This returns season-to-date stats
as of the day of the query. There is zero lookahead contamination in live
operation. The signal generator has NO imports from V1, S12, P09, feature_table,
sim_inputs, or any historical artifact. Confirmed by:
- Direct code inspection (imports only modules.pitchers and modules.odds)
- Phase 1 parity audit (signal_b_reactivation/phase1_parity_audit.md)
- 7 live signals showing varying xFIP values across dates and pitchers

### Claim 3: The historical backtest ROI (+27.9%) is inflated
**VERDICT: CONFIRMED**

The original research used `sim_inputs_historical_2022_2024.parquet` and
`sim_inputs_2025.parquet`, built from the feature_table. Direct inspection
confirms xFIP is STATIC per pitcher per season:
- MacKenzie Gore 2024: 4.151 for all 10+ starts (April through June)
- Chris Bassitt 2024: 4.422 for all starts
- Kutter Crawford 2024: 3.949 for all starts

This is end-of-season FanGraphs xFIP, applied retroactively to every start.
The model effectively knew each pitcher's full-season quality when betting
on their April games. The +27.9% pooled ROI and +29.1% 2025 OOS figures
are contaminated and should not be used as performance expectations.

---

## Threshold Decision Table

| Threshold | PIT Under Rate 2024 | PIT Under Rate 2025 | N per Season | Evidence Quality |
|-----------|--------------------|--------------------|-------------|-----------------|
| >= 0.8 | 47.3% | 52.2% | 284-303 | No edge |
| >= 1.0 | 50.3% | 53.1% | 175-181 | Borderline (coin flip) |
| >= 1.2 | 54.3% | 52.9% | 103-105 | Weak, unstable |
| >= 1.5 | 59.4% | 60.0% | 32-35 | STRONG, stable |

Only the 1.5 threshold shows consistent, meaningful edge in PIT-clean data.

---

## Operational Status

| Item | State |
|------|-------|
| Committed code threshold | 1.0 (needs commit) |
| Working tree threshold | 1.5 (correct) |
| Signal status | SHADOW |
| Tracker entries at >= 1.5 | 1 (0-1 record) |
| Reactivation gate | 30+ resolved at >= 1.5 |
| Estimated reactivation | ~September 2026 |

---

## Risk Acknowledgment

The 1.5 threshold has small sample sizes in PIT-clean testing (N=32-35 per season).
The 59-60% rate could regress. However:
1. It is stable across two independent seasons
2. The proxy used (full-game under rate) is conservative for F5 edge
3. The SHADOW status with 30-signal gate provides adequate validation runway
4. The -10% hard stop at N>=40 protects against catastrophic loss

---

## Files in This Audit

| File | Purpose |
|------|---------|
| phase0_claims_under_audit.md | Three claims under investigation |
| phase1_threshold_provenance.md | Chronological trace of all threshold mentions |
| phase2_threshold_decision_table.csv | Machine-readable threshold version table |
| phase3_pit_safety_source_lineage.md | xFIP source chain for live, research, and PIT contexts |
| phase4_manual_examples.md | All 7 live signals with xFIP source verification |
| phase5_live_research_identity.md | Side-by-side comparison of research vs live paths |
| SIGNAL_B_THRESHOLD_AND_PIT_FINAL_VERDICT.md | This file — final verdict |
