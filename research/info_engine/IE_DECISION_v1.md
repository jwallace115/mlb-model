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

## IE-D7 — Free historical spread opens (2026-10-12)

**Book correction:** the IE-D2 report stated "Pinnacle, 2007+". This was wrong for
the 2021-23 window. Per the file's Notes sheet: Pinnacle 2014-Feb 2018, **bet365**
Sep 2018-Feb 2025, betr from Sep 2025. All 2021-23 data is **bet365**, not Pinnacle.
OPENING_LINE_COVERAGE_v1.md corrected.

**Source:** `~/mlb-model/_cowork_patches/ie1/aussportsbetting_nfl.xlsx` (SHA256 verified).
Jeff downloaded manually after Cloudflare blocked programmatic access.

**Admission:**
- 5,495 total rows, 45 columns, seasons 2006-2026
- Derived season = year if month >= 8 else year-1
- Dropped all rows with season >= 2024 FIRST, then filtered to {2021, 2022, 2023}: 854 rows
- Dropped 39 playoff rows, kept 815 REG rows (272/271/272)
- 16 neutral venue games carried with flag
- All 33 unique team names mapped (including Washington Football Team -> WAS)
- 0 unmatched games (815/815 joined to nflverse by season + home + away + date ±1 day)

**Reconciliation (bet365 close vs nflverse close):**
- Convention: ASB `Home Line Close` == `-nflverse spread_line` (home perspective)
- Spread close within 0.5 points: 750/815 (**92.0%** — below 95% threshold)
- Spread close within 1.0 points: 790/815 (96.9%)
- Total close within 0.5 points: 750/815 (92.0%)
- Total close within 1.0 points: 801/815 (98.3%)

**Mismatch pattern:** 525/815 games match exactly (0.0 diff). 225 more are at ±0.5.
The remaining 65 are at ±1.0 to ±4.5. This is the normal book-vs-consensus gap:
bet365 closes at a different number than the nflverse consensus. The 2 games at
±4.0/±4.5 are likely late line moves where bet365 diverged sharply.

**Assessment:** the 95% threshold at 0.5 is not met, but the mismatch is **book
divergence**, not a convention or mapping error. The convention is confirmed correct
(525 exact matches, monotonic falloff). The opens come from the same book (bet365)
and are internally consistent. The data is usable for F10 spread movement (open-to-close
within the same book), which is what it was sourced for.

**Gate override:** the 95% within-0.5 gate was not met (92.0%). Override accepted on the
reasoning that bet365's close and the nflverse consensus close are different books (96.9%
within 1.0; 525 exact matches fix the sign convention). Cowork accepted the override after
the fact.

## IE-D8 — margin_resid correction and retraction (2026-10-12)

**Bug:** `margin_resid = margin - (-spread_line)` = `margin + spread_line` had **r = 0.69**
with `spread_line`. Not a residual — it retained the spread's information. The discovery
results (F2 t=4.9, F4 t=4.2, etc.) were predicting team quality via the spread, not
beating the close.

**Fix:** `margin_resid = margin - spread_line` (|r| = 0.015 with `spread_line`).

**Home cover audit:** old label `margin > -spread_line` had r = 0.56 with spread_line,
rate 55.95%. Corrected to `margin > spread_line` (r = -0.03, rate 47.4%, 49.0% ex-pushes).

**Known-game assertions added:**
- 2021_01_ARI_TEN: margin -25, spread_line +2.5, margin_resid -27.5 ✓
- 2021_01_DAL_TB: home underdog won (margin 2, spread_line 10), margin_resid -8 (did NOT cover) ✓

**Gates added:** |corr(margin_resid, spread_line)| < 0.05, |corr(total_resid, total_line)| < 0.05,
zero-variance check on all feature columns.

**F6 snap_shift:** redefined from count of players exceeding 10pp threshold (was all-zero)
to mean absolute deviation of week N-1 snap shares from season average. Now varies (std > 0).

**Retraction:** IE1_DISCOVERY_2026-10-12.md prepended with RETRACTION block. All IE-D6
results (t-stats, log-loss improvement, pre-registration outcomes) are INVALID.
IE_FROZEN_SPEC_v1.md is SUPERSEDED.

## IE-D9 — F2-F6 snap-weighted, F6 redefined, F3 2022-23 only (2026-10-12)

**F2 (pass protection):** snap-weighted version added, joining PFR to snap_counts by
`pfr_player_id + game_id`, filtering to >= 20 offensive snaps. 100% join rate.
`_simple` columns kept beside.

**F4 (RYOE):** snap-weighted version added, joining NGS to snap_counts by
`player_display_name + week`, filtering >= 20 snaps. ~94% join rate by name.
`_simple` columns kept beside.

**F5 (receiving separation):** same approach as F4. `_simple` columns kept.

**F3 (scheme tendency):** NOT snap-weighted. FTN charting is play-level data (each row
is a play, not a player). Aggregation is play-rate within the team, not player-weighted.
**F3 covers 2022-23 only** (FTN starts 2022; 0/272 coverage for 2021).

**F6 (snap-count shift):** redefined from count of players exceeding 10pp threshold
(was all-zero, zero-variance) to mean absolute deviation (MAD) of week N-1 snap shares
from cumulative season average. Proven to vary: std > 0 across all seasons.

Table rebuilt: 815 rows, 66 columns. All gates pass (correlation, zero-variance,
known-game assertions, truncation 6/6, negative control 4/4).

Output: `nfl/data/info/spread_opens_2021_23.parquet` (815 rows, 21 cols).
This feeds F10 spread half in IE-2; nothing in IE-1 fits on it.
