# IE Decision Log

## IE-D1 — Source inventory (2026-10-11)
See SOURCE_INVENTORY_v1.md. 18 NFL data sources catalogued.

## IE-D2 — Opening-line coverage (2026-10-11)
See OPENING_LINE_COVERAGE_v1.md. Spread opens missing pre-2026.

## IE-D3 — Feature families registry (2026-10-11)
See FEATURE_FAMILIES_v1.md. 10 families registered.

## IE-D4 — Register priors, tighten three families (2026-10-12)

Three edits to the registry:

1. **F8 as-of rule tightened:** "week N-1 depth chart only; week N is never read."
   Reason: the 2026-09-18 usage leak (A2). Depth charts for the current week may
   contain Saturday updates that were not available at feature-construction time.
   Reading only N-1 eliminates the leak at the cost of one week of staleness.

2. **F2-F6 aggregation fixed:** snap-weighted mean over players with >= 20
   offensive (or defensive, for defensive families) snaps in that week, by position
   group (QB, OL, WR/TE, RB; DL, LB, DB), computed through week N-1.
   Reason: leaves the aggregation method as a fixed spec rather than a discovery
   degree of freedom, preventing silent tuning during IE-1.

3. **F7 scoring target clarified:** totals as primary, margin as secondary.
   Reason: the Cowork prior gives 25% on totals vs 10% on margin. The registry
   should match the prior's structure.

Cowork priors pasted verbatim from `~/mlb-model/_cowork_patches/ie1/COWORK_PRIORS_IE1.md`
(SHA256: 6598caa27fe792b5782d1df5cef03018761d2822a72af1561a0edb5535baee10, verified OK).
IE-0b and IE-0c appended to `research/cross_ai/claude_prediction_ledger.md`.
"wk1-3" typo in OPENING_LINE_COVERAGE_v1.md corrected to "wk1-6".
