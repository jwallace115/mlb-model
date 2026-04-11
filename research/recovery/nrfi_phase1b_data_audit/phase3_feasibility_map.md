# NRFI Phase 1B — Feasibility Map

## Variable Classification

| Variable | Status | Source | Coverage | Notes |
|----------|--------|--------|----------|-------|
| home_total_line (full game) | FEASIBLE NOW | canonical odds | 5,543/11,406 (48.6%); 98%+ for 2024-2025 | Already in canonical parquet |
| away_total_line (full game) | FEASIBLE NOW | canonical odds | Same as above | Already in canonical parquet |
| tt_min / tt_max / tt_dispersion | FEASIBLE NOW | Derived from above | Same coverage | Simple arithmetic |
| both_below_4 / one_below_3_5 | FEASIBLE NOW | Derived from above | Same coverage | Boolean flags |
| nrfi_market_price | FEASIBLE NOW | yrfi_lines_historical | 4,399 games (2024-2025) | Already pulled |
| nrfi_implied_prob | FEASIBLE NOW | Derived from prices | Same as above | Standard conversion |
| first_inning_total_line | WITH PROXY | totals_1st_1_innings market | 4,399 games (always 0.5) | Line is always 0.5; only prices vary |
| f5_team_total_home | NOT FEASIBLE | Does not exist as market | 0 | Odds API does not offer F5 team totals |
| f5_team_total_away | NOT FEASIBLE | Does not exist as market | 0 | Same |
| first_inning_team_total | NOT FEASIBLE | Does not exist as market | 0 | No 1st-inning team-level total market |

## Derivation Options for Missing Variables

### F5 Team Totals (NOT a market)
- **Proxy A:** full_game_team_total * (f5_total / game_total) — crude scaling
- **Proxy B:** f5_total + f5_moneyline → approximate home/away split
- **Assessment:** Both proxies add noise without adding genuine information. The full-game team totals already capture the asymmetry we care about.

### First-Inning Team-Level Scoring
- The 1st-inning total market (totals_1st_1_innings) is game-level O/U 0.5 only
- No team-level 1st-inning market exists
- The NRFI market price itself IS the team-level information we need (it prices in both SPs + lineups)

## Summary

**5 variables are FEASIBLE NOW** from existing data:
1. home_total_line, away_total_line (from canonical odds, 2024-2025)
2. tt_min, tt_max, tt_dispersion (derived)
3. nrfi_market_price / nrfi_implied_prob (from YRFI backfill, 2024-2025)

**F5 team totals and 1st-inning team totals do not exist as markets** and cannot be reliably derived.
