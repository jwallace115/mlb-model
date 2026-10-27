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
