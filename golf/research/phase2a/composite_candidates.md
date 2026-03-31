# Phase 2A -- Composite Candidates

**G13×S6 entries removed 2026-03-31 — leakage artifact confirmed by weather revalidation.**
**G13×S3 entry suspended — depends on G13 wave signal which is invalidated.**

No active composite candidates remain.

## Reclassified (removed from candidates)

- G13 x S6(REGULAR_HARD) | make_cut | ROI=+11.8% | N=141 | INVALIDATED — LEAKAGE_ARTIFACT
  Reason: Score-based wave quintile contaminated by realized round scores.
  Weather-based revalidation: make_cut +1.8% ROI. Removed 2026-03-31.

- G13 x S6(REGULAR_HARD) | top_20 | ROI=+25.3% | N=141 | INVALIDATED — LEAKAGE_ARTIFACT
  Reason: Score-based wave quintile contaminated by realized round scores.
  Weather-based revalidation: top_20 +0.7% ROI. Removed 2026-03-31.

- G13 x S3 | top_20 | ROI=+19.4% | N=291 | SUSPENDED — DEPENDS_ON_G13
  Reason: G13 wave signal invalidated by weather revalidation. S3 interaction
  test used score-contaminated wave quintile. Cannot validate independently.

- G13 x S6(ELEVATED) | top_10 | ROI=+43.1% | N=257 | HIGH_VARIANCE_INTERACTION
  Reason: ROI driven by longshot hits (8-20x odds) and event concentration
  (82.3% of profit from top 3 events). Core odds range (3-8x) near breakeven.

- G13 x S6(REGULAR_EASY) | top_10 | ROI=+35.2% | N=119 | HIGH_VARIANCE_INTERACTION
  Reason: Same profile — high-variance longshot-driven result, not stable systematic edge.

- G15 x S6(REGULAR_HARD) | top_20 | ROI=-18.1% | N=219 | RATIO_ARTIFACT
  Reason: Negative ROI. Classified MULTIPLICATIVE by ratio math artifact (negative
  denominator inflated ratio). Not a real positive interaction.

- G15 x S6(ELEVATED) | top_20 | ROI=-5.4% | N=464 | RATIO_ARTIFACT
  Reason: Negative ROI. Classified ADDITIVE_FILTER because filter test passed
  (combo beat both individual signals) but all three signals had negative ROI.
  Beating two negatives is not a positive edge.
