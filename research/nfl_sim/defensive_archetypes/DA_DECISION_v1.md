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
