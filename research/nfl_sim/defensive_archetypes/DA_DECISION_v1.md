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
