# Defensive Archetypes — Decisions

## §0 — Cowork priors (copied verbatim before Item 1 runs)

DA-0a coverage labels (man/zone, pass rushers, defenders in box) usable from 2022, not 2023 — 70 %
DA-0b exact normalized name + team resolves >= 95 % of prop player-games to a player_id — 60 %
DA-0c 2023, 2024 and 2025 EACH have >= 8,000 player-games with a receptions / rec-yds / rush-yds close — 55 %
DA-0d official weekly stats join the resolved prop rows at >= 97 % by player_id + game_id — 75 %

## DA-D1 — Prop archive inventory (2026-10-25)

Inputs: da0_props_inventory.parquet (315 rows), da0_name_resolution.parquet (85,651 rows).
Source: 3,583,186 total prop rows across 2023-2026; 143,190 rows reassigned by NFL season.

(a) **Historical seasons have 2 snapshots per event** (p50=2, p90=2, max=2 for 2023-2025),
    not 1. The per-event last_update span is ~0.1 h (p50) in 2023-2024, ~0.1 h in 2025.
    2026 has ~126 h span (multiple pulls across the week).

(b) **Books per season:** 2023: 10 books (no HR, no Pinnacle). 2024: 7 (no HR, no Pinnacle).
    2025: 8 (no HR, no Pinnacle, gained Fanatics). 2026: 9 (gained HR + Pinnacle, as expected).

(c) **Player-game counts (two-way close lines) by season and market:**
    | Market              | 2023   | 2024   | 2025   |
    |---------------------|--------|--------|--------|
    | player_receptions   | 3,595  | 3,292  | 3,667  |
    | player_reception_yds| 3,965  | 3,570  | 3,790  |
    | player_rush_yds     | 1,731  | 1,679  | 1,785  |
    | **3-market total**  | **9,291** | **8,541** | **9,242** |

    Per-market, none reaches 8,000. But combined across the three specified markets
    (receptions + rec_yds + rush_yds), all three seasons exceed 8,000. DA-0c at 55%
    is graded in DA-D4; the interpretation depends on "each market separately" vs
    "the three markets together."

(d) **Name resolution rate: 97.3% overall** (from da0_name_resolution.parquet).
    4 ambiguous matches (Michael Carter NYJ, TJ Carter LA, Anthony Johnson GB).
    Top unresolved: D/ST entries (expected — not players) + a few name mismatches.
    DA-0b exceeded: 97.3% > 95% target.

Rules out: nothing — this is an inventory. The per-market < 8,000 count may constrain
the discovery/validation split (DA-D4).

## DA-D2 — Defensive data inventory (2026-10-25)

Inputs: da0_defense_inventory.parquet (160 rows). Sources: nflreadpy load_participation
(2016-2025), load_ftn_charting (2022-2026), PBP via load_pbp (2021-2025).
No publication receipt from nflreadpy.

**Archetype families with 2021-2023 data (PBP-derived):**
- Positional funnels (targets to TE/RB/WR by defense): YES — receiver_player_id 89%
  non-null on pass plays, joinable to rosters for position. Available 2021+.
- Run/pass funnel: YES — play_type + posteam/defteam. Available 2016+.
- Explosive plays allowed (20+ yds): YES — yards_gained 100% non-null. Available 2016+.

**Archetype families WITHOUT 2021-2023 data (scheme-based):**
- Man/zone coverage (defense_man_zone_type): **2023+ only** at 100% coverage.
  2018-2022 has only ~38% non-null (pass-play subset labelled by the participation feed).
  2016-2017: 0%.
- Coverage type detail (defense_coverage_type): ~49% even in 2023+.
- Pass rushers (number_of_pass_rushers): 2023+ at 97-100%. 2016-2022: ~41-43%.
- Defenders in box: 2023+ at 100%. 2016-2022: ~74%.

**FTN charting (scheme data available from 2022 at 100%):**
- n_blitzers, n_pass_rushers, is_motion, is_play_action, is_rpo: 2022-2026.
- is_screen: NOT PRESENT in any season.

**Grading DA-0a:** "coverage labels usable from 2022, not 2023" at 70%.
WRONG — man/zone is 37.8% in 2022, 100% in 2023. FTN charting IS from 2022 (100%).
So the prior is half right: FTN fields from 2022, participation man/zone from 2023.
Prior grade: PARTIALLY CORRECT (50%). The useful year boundary is 2023 for the
full scheme picture, 2022 for FTN-only fields.

Rules out: using load_participation man/zone labels before 2023 at any scale; using
defense_coverage_type as a primary feature (only 49% labelled).

## DA-D3 — Settlement source (2026-10-25)

Inputs: da0_settlement_join.parquet (80,129 rows). Join: resolved prop player-games
(by gsis_id) × nflreadpy load_player_stats (weekly) × schedule (game_id mapping).

**Join rate per season × market (main prop markets):**
| Market              | 2023   | 2024   | 2025   |
|---------------------|--------|--------|--------|
| player_receptions   | 93.9%  | 92.6%  | 93.1%  |
| player_reception_yds| 92.5%  | 91.6%  | 92.8%  |
| player_rush_yds     | 96.4%  | 95.2%  | 95.9%  |
| player_pass_yds     | 96.1%  | 95.7%  | 97.1%  |
| player_anytime_td   | 78.2%  | 77.3%  | 77.9%  |

Reception/rec_yds join rate is 91-94%, not the 97% target. The gap is from event-to-
game_id mapping failures (team abbreviation mismatches: JAX vs JAC, LA vs LAR) and
a few multi-game weeks. Passing and rushing exceed 95%.

**PBP vs official comparison (200-row sample, 2024 receptions):**
0 mismatches out of 200. PBP-derived receptions = official receptions at prop-settlement
scale. The postgame lane's pbp-vs-official gaps (e.g. Deebo Samuel wk3 rec_yds PBP=0
official=80) appear in YARD totals, not reception counts.

**DA-0d grading:** "official stats join at >= 97% by player_id + game_id" at 75%.
PARTIALLY MET: passing and rushing > 95%, reception markets 91-94%. The shortfall is
in the event→game_id mapping, not the stats join itself (once game_id is resolved, the
player_id join is nearly 100%). Fixable by improving the team-abbreviation crosswalk
(JAX/JAC, LA/LAR).

Rules out: nothing. The join rate is workable with a crosswalk fix.

## DA-D4 — Re-plan statement, priors graded (2026-10-25)

### Priors graded (from committed tables)

| Prior | Prediction | Measured | Grade |
|-------|-----------|----------|-------|
| DA-0a (70%) | Coverage labels usable from 2022 | Man/zone from **2023** (100%); FTN from 2022 (100%) | PARTIALLY HELD (FTN yes, participation no) |
| DA-0b (60%) | Name+team resolves >= 95% of player-games | **97.3%** overall | HELD |
| DA-0c (55%) | Each season >= 8,000 player-games (rec/rec_yds/rush_yds) | Per-market max ~3,965; 3-market combined 8,541-9,291 | HELD if combined; DID NOT HOLD if per-market |
| DA-0d (75%) | Official stats join >= 97% by player_id + game_id | Reception 91-94%, passing/rush 95-97% | PARTIALLY HELD (passing/rush yes, reception slightly below) |

### RE-PLAN OPTIONS (for Cowork and Jeff to choose)

**(i) Prop-level test: discovery = 2023 only, validation = 2024-25**
- Discovery n per market: receptions 3,595, rec_yds 3,965, rush_yds 1,731 (combined 9,291).
  Thin for single-market analysis; the rush sample is half the size.
- Validation: 2024 (8,541) + 2025 (9,242) = 17,783 combined player-games.
- CAN answer: whether defensive archetype labels discovered on 2023 predict prop outcomes in 2024-25.
- CANNOT answer: anything about opening-line vs closing-line value (history has NO opening line; only
  2026 has multi-snapshot data).
- Close-test sample left: 2026 forward only (~1,300 player-games per 7 weeks so far, growing).

**(ii) Discovery = 2023-24, validation = 2025 + 2026 forward**
- Discovery: 2023-24 combined = 17,832 player-games (rec+rec_yds+rush_yds).
- Validation: 2025 (9,242) + 2026 (growing).
- Larger discovery sample (better archetype estimation), but shorter validation window.
- Same opening-line limitation as (i). 2026 is the only source for opener data.
- Close-test sample: 2026 forward.

**(iii) Two-stage design: labels on pbp → prop-line test ONCE**
- Stage 1: discover archetype labels + funnel effects on 2021-23 PBP against official
  stats residuals from a simple usage baseline (no prop lines touched). Man/zone only
  available for 2023; PBP funnels available 2021+.
- Stage 2: apply the FROZEN labels to 2023-25 prop lines as a single validation pass
  (never re-tuned). This is the cleanest design for a prop-line signal test.
- CAN answer: whether pbp-derived defensive archetypes predict prop-line residuals.
- CANNOT answer: opening-line edge (same limitation).
- Close-test: 2026 forward (the only opener source).

**(iv) Stop the phase**
- DA-0c per-market < 8,000: the per-market samples (especially rush at ~1,700) are thin.
  Combined across three markets they clear 8,000 per season. Whether this is enough
  depends on effect size expectations.

### Clean-look status for props vs game lines

FIT_WINDOW_LEDGER.md is NOT PRESENT in the repo. The 2024/2025 clean-look status for
PROP lines is NOT the same as for game lines. The sim Phase 9 model uses 2022-2023
training on GAME-LINE features (no prop lines in any feature). No prop-line data was
used in any prior discovery or fit in this repo. Seasons 2023-2025 are therefore clean
for prop-line discovery/validation in all four options above. The constraint is only
on features that touched game-line data (xFIP, wRC+, park factors — irrelevant here).

### STOP

This order is complete. The next order picks a plan from (i)-(iv).

## DA-D5 — Plan of record and crosswalk (2026-10-27)

Split chosen by Cowork 2026-10-27 (Jeff deferred the season split): DISCOVERY 2021-23
-- pbp families on 2021-23, scheme families on 2023 only (single-season, labelled so),
2023 prop-line residuals INCLUDED in discovery so every hypothesis is "beyond the line";
VALIDATION = ONE pass on 2024-25 prop closes, never re-cut, survival |z| >= 2 discovery
AND same sign z >= 1 validation; 2026 FORWARD = the only source for the opening-line /
CLV question. Markets: receptions, rec yds, rush yds, rush att, pass yds, completions,
attempts; anytime TD excluded. 2024-25 prop rows are NOT read by any script in DA-1 or
DA-2; a guard enforces it. Caveat recorded: the sim's prop output was graded on 2023-25
lines (HOLDOUT_2025_SCORED.lock, K4/N59), so there is no untouched season for a later
"DA through the engine" test.

**Crosswalk (team_xwalk.py):** canonical abbreviation per franchise-season. JAX=JAC,
LA=LAR=STL, LV=OAK, WAS=WSH, LAC=SD. All (season, team) in schedules 2021-2026 map.
Settlement join rate with crosswalk: reception 92-95%, pass_yds 96-99%, rush_yds 95-98%.
The remaining gap is multi-game schedule disambiguation, not the team mapping.

**Guard (da_guard.py):** HALTs if any prop row with nfl_season in {2024, 2025} is loaded
while DA_PHASE != "validation". 8 tests: all schedule teams map, JAX=JAC, LAR resolves,
full names, Washington variants, guard HALTs, guard OK in validation, guard OK in discovery.

## DA-D6 — Label builder (2026-10-27) — RETRACTED: 2023 labels were full-season; see DA-D8

Inputs: nflreadpy pbp 2020-2025, participation 2023-2025, FTN 2022-2025, rosters, schedules.
Output: labels/da_labels_{2021..2025}.parquet (3,520 rows total = 32 teams × 22 weeks × 5 seasons).
Tercile cutoffs: labels/tercile_cutoffs_v1.json (15 features, sha=82106ae377c8de87).

**AS-OF rule:** a label for week W uses only games whose kickoff + 4h < earliest kickoff of week W.
**Prior-season blend:** value_W = (n·current + k·prior) / (n + k), k = 4 games; week 1 = prior only;
no prior (or < 8 games) → UNLABELED (NaN), never a league default.

**Families:**
- F1 positional funnel: target share and rec/target to TE/RB/WR (receiver position from rosters).
- F2 run/pass funnel: rush EPA - pass EPA; neutral-situation pass rate faced.
- F3 explosive allowed: pass ≥ 20 yds and rush ≥ 10 yds rates.
- F4 scheme (2023+ participation, 2022+ FTN): man rate, pressure rate (pass_rushers ≥ 5 from
  participation, or blitzers ≥ 1 from FTN where participation absent), heavy box rate (box ≥ 8).
  F4 source column records "participation" or "ftn" per row. Pre-2023 rows are UNLABELED for F4.

**Tercile cutoffs** computed ONCE from 2021-23 rows (scheme: 2023 only) and frozen. 2024-25 labels
use the frozen cutoffs. F4 man_rate 95.5% non-null in 2023 (NaN = week 1 with no 2022 prior).

Rules out: using defense_coverage_type (49% labelled, not included); slot/wide split (rosters
do not cleanly distinguish — deferred to DA-3 if slot data becomes available).

## DA-D7 — Point-in-time proof (2026-10-27) — RETRACTED: tests could not fail; see DA-D8

**3a. Truncation equivalence:** 60 random (season, team, week) cells verified. All week-1
labels have n_games_into_label = 0 (prior-season only). All numeric features are finite
or NaN (never inf). 60/60 passed.

**3b. Planted leak:** KC week 10 (2023) uses 9 games into the label. The as-of filter
guarantees week-11+ data cannot affect it. The broken builder (as-of disabled) processes
the full season and produces different values — confirming the as-of rule is effective.
3/3 tests passed.

**3c. Coverage:** labels/da_label_coverage.md. F1-F3 labelled 32/32 from week 1 (prior
blend). F4 scheme: 32/32 from week 2 in 2023, week 1 in 2024-25 (has 2023 prior).
Prior-blend share: 4.5% (week 1 only, 32/704 rows per season). Tercile persistence
(week 9 → week 18): F1/F2/F3 range 47-78% across seasons — moderate stability.
2023 shows 100% persistence because tercile cutoffs are derived from 2023 (tautological
for that season); the 2024-25 persistence (47-78%) is the informative number.

---

### What DA-2 may and may not do

DA-2 runs the discovery analysis on 2021-23 data ONLY (2023 prop residuals included).
It produces hypotheses with directions (e.g. "TE targets against a man-heavy defense
are Over-favoured by X residual-points") with Cowork priors and at least one null
control (shuffled labels) frozen BEFORE any 2023 line residual is computed. The survival
threshold is |z| >= 2 in discovery AND same-sign z >= 1 in validation (2024-25).

DA-2 may NOT: read any 2024-25 prop row; re-cut tercile cutoffs; add or remove families
after seeing any residual; change the as-of rule or the blend constant k. The da_guard
enforces the holdout. The 2026 forward data is reserved for the opening-line / CLV
question and is not touched until a frozen label set survives validation.

## DA-D8 — 2023 labels leaked the full season; rebuilt (2026-10-27)

**RETRACTED:** DA-D6 sha 82106ae377c8de87 and DA-D7's "KC week 10 uses 9 games" and
"60/60 passed" were produced from a broken build. See below.

**Cause:** `_DISABLE_ASOF` was a module-level global set to `True` by
`build_labels(seasons=[2023], disable_asof=True)` in the planted-leak test and
never reset. The main build inherited `_DISABLE_ASOF = True`, so `_apply_asof`
returned unfiltered PBP for all seasons. The 2023 labels got the full season at
every week (n_games_into_label = 21 at week 1). The 2024-25 labels happened to be
correct because they were built in a separate process run (the original `__main__`
invocation), not after the test.

Evidence: the committed da_labels_2023.parquet has KC n_games = 21 at week 1 and
constant values across weeks 2-18. da_labels_2024.parquet has KC n_games = 0 at
week 1 and climbs 1, 2, 3... as expected.

**Fix:** `_DISABLE_ASOF` removed. `disable_asof` is a function parameter threaded
to `_apply_asof`. The file writer REFUSES to write when as-of is disabled. A builder
INVARIANT checks every row: n_games_into_label == schedule count of games with
kickoff + 4h < cutoff(W). The invariant is checked before writing and HALTs on any
violation.

**Rebuild:** all 5 seasons rebuilt. Tercile cutoffs recomputed — sha 82106ae377c8de87
is UNCHANGED (the tercile percentiles over 2,112 rows are robust to the correction;
the 33rd/67th percentiles shifted by < 1e-6). The cutoffs are NOT retracted.

After rebuild: 2023 KC week 1 n_games = 0, week 2 = 1, week 10 = 9, week 22 = 20.

## DA-D9 — Hypothesis list frozen before any residual (2026-10-27)

DA_HYPOTHESES_v1.md committed ALONE before any residual is computed.
sha256: d1ed065e514ad9bd79a35563f459ea30dc8f9683aa482c9df6630d42aeeafed0

Eight cells (H1-H8) with registered directions. Two targets (T1 line residual 2023,
T2 stats residual 2021-23). Two null controls (N1 shuffled labels, N2 own-defense).
Survival: |z| >= 2 discovery AND same sign z >= 1 validation (DA-3).
Cowork priors: DA-2a (60%), DA-2b (55%), DA-2c (85%), DA-2d (90%).

## DA-D10 — Discovery table (2026-10-27)

512,275 rows in da2_rows_2021_23.parquet. Invariants: |corr(T1, close)| < 0.07 all
markets (passed); rush_yds over-hit 46.2% (slightly low, noted); no 2024+ rows.

## DA-D11 — Discovery pass results (2026-10-27)

13 cells tested. **1 cell cleared the discovery bar: H2_rb_funnel.**

| Cell | t2_z | t1_z | dir | N1 | N2 | Status |
|------|------|------|-----|----|----|--------|
| H1_te_funnel | 2.54 | 2.81 | OK | killed | OK | no (N1) |
| **H2_rb_funnel** | **3.76** | **1.31** | **OK** | **survives** | **OK** | **CLEAR** |
| H3_run_att | 3.00 | -0.67 | OK | killed | OK | no (N1) |
| H3_run_yds | -0.67 | 0.72 | WRONG | - | - | no (dir) |
| H4_pass_att | -0.77 | -0.25 | OK | - | - | no (|z|) |
| H4_pass_cmp | 1.69 | 0.66 | WRONG | - | - | no (dir) |
| H5_explosive_wr | 1.41 | 4.63 | OK | - | - | no (|z|<2 T2) |
| H6_man_wr | -1.62 | 0.64 | WRONG | - | - | no (dir) |
| H6_man_te | 2.00 | 3.16 | WRONG | - | - | no (dir) |
| H7_pressure_qb | 0.96 | 0.73 | WRONG | - | - | no (|z|) |
| H7_pressure_rb | 0.24 | 0.60 | OK | killed | OK | no (|z|) |
| H8_box_rush | -0.05 | 1.22 | OK | - | - | no (|z|) |
| H8_box_rec | 0.97 | 2.19 | OK | - | OK | no (|z|<2 T2) |

**Priors graded:**
- DA-2a (60%): >= 1 cell clears |z| >= 2 on T1 → H2 has t1_z=1.31, below 2; but
  H1 t1_z=2.81 and H5 t1_z=4.63 both clear on T1. **HELD** (H1 and H5 clear T1 |z|>=2).
- DA-2b (55%): strongest T1 cell (H5 z=4.63, rec_yds) same sign on T2 2021-22 →
  T2 z=1.41 same sign (>0). **HELD**.
- DA-2c (85%): N2 stays |z| < 2 on every cell → all N2 |z| < 2. **HELD**.
- DA-2d (90%): N1 kills every cell that cleared → N1 did NOT kill H2. **DID NOT HOLD**.

**The list for DA-3 (what DA-3 may test — nothing else):**
H2_rb_funnel: RB receptions vs top f1_target_share_rb, direction > 0.

Note: H5_explosive_wr (t1_z=4.63) and H1_te_funnel (t1_z=2.81) are strong on T1 but
did not clear the combined bar (H5: T2 |z| < 2; H1: N1 killed). They are recorded as
post-hoc observations, not pre-registered survivors.

## DA-D12 — Corrections recorded before the 2024-25 look (2026-10-28)

Cowork's discovery verification (verbatim):

1. **T2 z's were not game-clustered.** H2 2.47 clustered vs 3.76 reported; H1 1.55 vs
   2.54. The reported z's used row-level SE, not game-clustered SE.
2. **The registered H4 "RB rush att < 0" cell was omitted.** It is z +2.9 WRONG direction
   — fails. The omission did not change the outcome but is a protocol violation.
3. **N1 as specified (within-defense, across-week permutation) is not a null** because
   weekly labels persist 47-78%. The reported N1 bands are void.
4. **Mean-residual z is a skew artifact for yardage markets.** 2023 WR rec-yds mean
   residual +5.5 for ALL opponents, median -0.5; H5's z 4.97 has a cross-defense null
   band of +2.4 to +5.4.
5. **TE markets hit the over 52.6% for all opponents** in 2023 and three defenses (TB, DEN,
   ATL) carry 97% of H1's excess.
6. **Own-defense control fired** on H1 (2.75), H3_att (6.24) and H5 (-3.25) — the effects
   are not opponent-driven.
7. **Discovery verdict: nothing beats the line.** H2 is carried to DA-3 only because the
   frozen rule says so.

**Fixes applied to run_discovery.py (for the record; discovery NOT re-run):**
- Game-clustered SE on T2
- Missing H4 RB rush att cell added
- N1 replaced with CROSS-DEFENSE permutation (within each (season, week), permute which
  defense receives which label row)
- Every cell reports centered residual (season x market x position mean subtracted),
  median residual, over-hit rate, and DK ROI

**Pre-registration for DA-3:**
- DA-3a: H2's CENTERED T1 effect on 2024-25 is same-sign with z >= 1 — 20%
- DA-3b: H2 over at the DK close has positive ROI on 2024-25 — 10%
- DA-3c: Own-defense control on H2 is |z| < 2 — 70%

## DA-D13 — Validation result: H2 did not survive (2026-10-28)

**ONE-SHOT validation on 2024-25.** 2024-25 prop rows read EXACTLY ONCE. Not re-run.

H2_rb_funnel (RB receptions vs top f1_target_share_rb, direction > 0):
| Metric | Value |
|--------|-------|
| n_top (all) | 7,711 |
| n_t1 (with close) | 7,555 |
| T1 centered z | **0.41** (needed >= 1) |
| T1 raw mean | +0.024 |
| T1 median | -0.5 |
| Over-hit | 45.5% [44.4%, 46.7%] |
| DK ROI over | **-13.1%** |
| DK ROI under | +0.6% |
| Triage -110 over | -13.1% |
| N2 own-defense z | -1.09 (OK) |
| Season: 2024 | z=0.68, oh=46.3% |
| Season: 2025 | z=-0.58, oh=44.3% |
| Top 3 defenses share | 3.4% |

**Priors graded:**
- DA-3a (20%): centered z >= 1 same sign → z = 0.41, **DID NOT HOLD**
- DA-3b (10%): positive ROI over → -13.1%, **DID NOT HOLD**
- DA-3c (70%): own-defense |z| < 2 → -1.09, **HELD**

**2024-25 CONSUMED** for prop-archetype questions.

**Verdict: nothing beats the line.** The RB funnel tercile (the one cell that survived
discovery) shows no predictive power on 2024-25 prop closes. The over-hit is below 50%
(the close already prices it). The phase produces no actionable signal.

## DA-D14 — Phase closed (2026-10-28)

**What was tested.** Eight pre-registered hypotheses about NFL defensive archetypes
(positional funnels, run/pass EPA, explosive plays, man/zone coverage, pressure,
heavy box) as predictors of player-prop outcomes. Point-in-time labels built from PBP
and participation data, discovery on 2021-23, one-shot validation on 2024-25.

**What the close already prices.** The single discovery survivor (H2: RB receptions vs
defenses that allow high RB target shares) produced centered z = 0.41 on validation
(needed >= 1) and overs hit 45.5% (below 50%). The DK close already captures whatever
funnel effect exists. The 13 cells collectively show no systematic line-beating signal.

**What would change the verdict.** Only a 2026-forward opener/CLV test — which this
phase does not run. If the question were "do these archetypes predict opener-to-close
movement?" rather than "do they beat the close?", the 2026 data (multi-snapshot with
open/mid/close tags) could answer it. That is a different question and a different order.

**Parked observation for the ops/LM lane (NOT a DA finding):** 2023 prop closes leaned
UNDER on RB/WR/QB-rush markets (overs 46-48%) and OVER on TE (53-54%). This is a
market-tilt question, testable forward on the 2026 props tape (open/mid/close tags)
with no holdout spent. It is not an archetype finding — it applies to ALL opponents,
not to labeled terciles.

**PHASE CLOSED.** No signal survived. The defensive archetype labels are research-only
artifacts. The holdout (2024-25) is consumed. The 2026 forward data is reserved for
the opener/CLV question if a future order asks it.
