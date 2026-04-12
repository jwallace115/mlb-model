# PHASE 7 — Clean Kill Registry

**Date:** 2026-04-12
**Purpose:** Permanent record of ideas that were fairly tested and definitively failed

---

## Clean Kill #1: V1 PIT Clean Rebuild (A2)

**Test:** Ridge alpha=50, 25 features, PIT-safe expanding means, honest temporal split
**Results:** 2024 ROI=-10.5% (N=175), 2025 ROI=-13.2% (N=55) at p>0.57
**Threshold scan:** Negative at every threshold from 0.53 to 0.61
**Verdict:** The V1 Ridge architecture with these features cannot beat the MLB totals market.
**Reopening condition:** NONE. This was the most thorough possible test of V1.

---

## Clean Kill #2: V2 Baseline Engine (A4)

**Test:** Ridge alpha=50, 14 PIT-safe features, target=market_error
**Results:** RMSE +0.01 vs market. Mean predicted edge +0.43 (over bias). ~0 under signals.
**Verdict:** V2 architecture lacks the feature resolution to beat the totals market.
**Reopening condition:** NONE unless entirely new feature class discovered.

---

## Clean Kill #3: S12 Overlay (B1)

**Test:** PIT-safe CSW + xFIP composite. Tested at multiple cutoffs.
**Results:** Overall ROI=-0.8% (N=2596). In-sample negative at EVERY threshold. 2/4 seasons positive.
**OOS V2 overlay:** Active=50.9%, inactive=52.8% (COLLAPSES — inverts direction)
**Verdict:** Neither as standalone nor as overlay does S12 improve any base signal.
**Reopening condition:** NONE.

---

## Clean Kill #4: P09 Overlay (B2)

**Test:** Hard-hit x park factor composite. PIT-safe. Multiple cutoffs.
**Results:** OOS blind-under: active=50.9%, inactive=52.8%. Active is WORSE.
**Verdict:** Overlay inverts. Adding P09 makes any base signal worse.
**Reopening condition:** NONE.

---

## Clean Kill #5: ST02 Overlay (B3)

**Test:** road_trip_game_num >= 6 filter. 2022-2025 historical.
**Results:** N=2,172 qualifying, under rate=52.21%, ROI=-0.3%.
**Verdict:** Market prices travel fatigue correctly. No residual edge.
**Reopening condition:** NONE.

---

## Clean Kill #6: ADJ_BB_RATE (C4)

**Test:** PIT-safe per-start BB rate, shift(1).rolling.
**Results:** Shadow 2026: 50.0% hit rate (16 resolved). Flat noise.
**Verdict:** Walk rate does not independently predict totals direction.
**Reopening condition:** NONE.

---

## Clean Kill #7: F5 Run Line Away (D4)

**Test:** xFIP gap <= -1.0 for away starter dominance, F5 RL.
**Results:** 2025 ROI=-3.5%. Away signals consistently negative.
**Verdict:** F5 RL edge is structurally home-side only. Market correctly prices away dominance.
**Reopening condition:** NONE.

---

## Clean Kill #8: Run-Line Comeback Asymmetry (F2)

**Test:** 9,857 games, walk-off truncation analysis.
**Results:** Home -1.5 cover=35.8%, away -1.5 cover=35.9%. Perfect parity.
**Verdict:** Walk-off truncation is real but perfectly priced. Clean null.
**Reopening condition:** NONE.

---

## Clean Kill #9: Team Totals Away Over (E3)

**Test:** Research showed 52-54% hit rate.
**Results:** Below profitability threshold at standard vig.
**Verdict:** Correctly suppressed in live code.
**Reopening condition:** NONE.

---

## Summary: 9 Clean Kills

These 9 ideas are permanently closed. No further resources should be spent on them.
Any future proposal to retest these ideas must present NEW evidence not available
at the time of this audit (new data source, new market structure, etc.).
