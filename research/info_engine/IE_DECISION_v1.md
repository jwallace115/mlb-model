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

## IE-D5 — As-of feature table, 2021-23 (2026-10-12)

**Feature table:** 815 games (REG only), 56 columns (12 core + 44 family features).
Seasons: 2021, 2022, 2023. No 2024+ target data read.

**Row counts per family per season:**

| Family | Key column | 2021 | 2022 | 2023 | Notes |
|--------|-----------|------|------|------|-------|
| F1 Injury trajectory | f1_inj_trajectory_diff | 272/272 | 271/271 | 272/272 | Full coverage |
| F2 Pass protection | f2_pressure_diff | 256/272 | 255/271 | 256/272 | Missing wk1 (no prior) |
| F3 Scheme tendency | f3_home_motion_rate | **0/272** | 255/271 | 256/272 | **FTN starts 2022; 2021 entirely missing** |
| F4 Rushing RYOE | f4_ryoe_diff | 252/272 | 254/271 | 255/272 | NGS weekly, missing early weeks |
| F5 Receiving separation | f5_home_separation | 264/272 | 262/271 | 264/272 | Similar |
| F6 Snap-count shift | f6_home_snap_shift | 224/272 | 217/271 | 223/272 | Requires 2+ prior weeks |
| F7 Referee crew | f7_ref_avg_total | 239/272 | 239/271 | 240/272 | Missing wk1-2 + rare refs |
| F8 Depth chart | f8_home_dc_changes | 240/272 | 239/271 | 240/272 | Needs wk N-1 and N-2 |
| F9 Rest/surface/weather | f9_wind | 272/272 | 271/271 | 272/272 | Full (wind=0 for dome) |
| F10 Line movement | f10_line_move | 182/272 | 185/271 | 201/272 | Line movement coverage varies |

**Coverage holes:**
- F3 (FTN charting) has zero coverage for 2021. FTN data starts 2022. F3 discovery
  uses only 2022-23 (2 seasons instead of 3). Noted, not dropped — the source exists
  and the as-of rule is clean.
- F10 coverage is 67-74% because `nfl_line_movement.parquet` doesn't cover all games.

**Sources dropped:** None. All 10 families have at least partial coverage.

**Truncation-equivalence test:** 6/6 (season, week) pairs PASSED.
Negative control: 4/4 PASSED (future-week data correctly excluded or detected).
Target season assertion: verified {2021, 2022, 2023}, no duplicates.

## IE-D6 — Discovery fit, pre-registered, frozen (2026-10-12)

All four pre-registrations FALSIFIED — stronger signal than expected:

- P-IE1-1 FALSIFIED: F2 t=4.9, F4 t=4.2, F5 t=3.5, F3 t=3.1 on margin (predicted < 2.5)
- P-IE1-2 FALSIFIED: F7 t=1.96, F9 t=0.47 on totals (predicted >= 2; neither reached)
- P-IE1-3 FALSIFIED: F8 margin t=2.4, total t=-2.5 (predicted |t| < 1; the N-1 signal persists)
- P-IE1-4 FALSIFIED: log-loss improvement = 0.019 (predicted < 0.003; 6x higher than expected)

Frozen spec: 21 features, alpha=100 (margin), alpha=1000 (totals). See IE_FROZEN_SPEC_v1.md.

**Caution:** this is discovery on 2021-23 with LOSO, not true OOS. The 2024 clean look
(IE-2) is the real test. The strength of the discovery signal makes the OOS test higher-stakes:
if it replicates, the information layer has genuine value; if it doesn't, the discovery was
overfit. Do NOT tune anything to rescue a failed OOS.
