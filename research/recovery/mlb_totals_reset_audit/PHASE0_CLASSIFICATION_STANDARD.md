# PHASE 0 — Classification Standard

**Date:** 2026-04-12
**Scope:** MLB Totals Reset Audit — Governing Definitions

---

## Classification Definitions

### CLEAN KILL
The idea was tested fairly (no contamination, no lookahead, no identity mismatch) and
the result is definitively negative. The signal does not work. No retest is warranted.
Evidence is sufficient to close permanently.

**Criteria:** PIT-safe data, honest temporal split, negative ROI at all thresholds tested,
no season-by-season stability, or directionally inverts OOS.

---

### VOID / CONTAMINATED
The idea was never fairly tested because one or more inputs were contaminated
(lookahead, identity mismatch, parent dependency on contaminated object).
The research conclusions cannot be trusted in either direction.
The idea is neither confirmed nor refuted — it is simply unknown.

**Criteria:** Any of: end-of-season feature lookahead, threshold derived from
contaminated parent, research/live identity mismatch, consumed contaminated
V1 probabilities.

---

### RETEST REQUIRED
The idea has structural merit (sound hypothesis, clean data pipeline possible)
but was tested under contaminated conditions. A clean retest with PIT-safe data
and honest temporal splits could yield a definitive verdict.

**Criteria:** Void/contaminated test + plausible mechanism + feasible clean rebuild path.

---

### WRONG MARKET FRAME
The idea may contain real signal but is expressed in the wrong market, wrong
derivative, or wrong bet structure. The mechanism is real but the betting
expression absorbs the edge through vig, hold widening, or structural
market efficiency.

**Criteria:** Demonstrated statistical pattern (e.g., curvature, asymmetry) that
is correctly priced by the market or absorbed by the hold structure.

---

### UNVERIFIABLE
The idea cannot be tested with available data. Missing inputs (no historical
prices, no closing lines, no F5 actuals pre-2023, etc.) make definitive
evaluation impossible. The idea is neither confirmed nor refuted.

**Criteria:** Critical data gap that cannot be filled retroactively.

---

### ARCHIVE
The idea produced useful diagnostic information or infrastructure but does
not itself constitute a bettable signal. Retained for reference; no further
testing needed.

**Criteria:** Research output that informed other decisions (e.g., contamination
chain mapping, feature inventory) but is not itself actionable.

---

### REBUILD REQUIRED
The core model or engine was trained on contaminated data. The architecture
may be sound but the weights, thresholds, and calibration are unreliable.
A full rebuild from clean data is required before any conclusions can be drawn.

**Criteria:** Trained model (Ridge, logistic, etc.) where >50% of training
features were contaminated, or where the contamination affects the primary
signal path.

---

## Application Rules

1. Each idea receives exactly ONE classification.
2. If multiple classifications apply, the most severe takes precedence:
   VOID > REBUILD REQUIRED > RETEST REQUIRED > WRONG MARKET FRAME > CLEAN KILL > ARCHIVE > UNVERIFIABLE
3. Classification is based on the BEST available evidence as of 2026-04-12.
4. A CLEAN KILL cannot be reclassified without new data or a demonstrated methodological error in the original test.
5. A VOID classification does not imply the idea is bad — it implies the test was bad.
