# NRFI Phase 1B — Framing Memo

## Research Question

Can team-level early-scoring expectations improve NRFI prediction beyond
game-level totals and SP quality metrics already captured in Phase 1?

## Variables of Interest

The NRFI outcome (no runs in the first inning) depends on BOTH lineups
failing to score in a single half-inning each. The Phase 1 table uses
game-level closing totals and SP metrics as proxies. But NRFI is
asymmetric: a game total of 8.5 could mean one elite SP + one mediocre
SP (team totals 3.5 / 5.0) or two average SPs (4.5 / 4.0). The
decomposition matters because NRFI requires BOTH halves to be scoreless.

### Candidate Team-Level Variables

| Variable | Definition | Why It Matters for NRFI |
|----------|-----------|----------------------|
| home_total_line | Market team total (full game, closing) | Proxy for home lineup expected scoring |
| away_total_line | Market team total (full game, closing) | Proxy for away lineup expected scoring |
| tt_min | min(home_total, away_total) | The "weaker" offense — less important for NRFI since BOTH must fail |
| tt_max | max(home_total, away_total) | The "stronger" offense — the bottleneck for NRFI |
| tt_dispersion | tt_max - tt_min | Imbalance between the two sides |
| both_below_4 | Both team totals <= 4.0 | Flag for two suppressed offenses |
| f5_team_total_home | Market F5 team total (home) | NOT AVAILABLE in current data |
| f5_team_total_away | Market F5 team total (away) | NOT AVAILABLE in current data |
| nrfi_market_price | NRFI/YRFI closing odds | Available 2024-2025 via YRFI backfill |
| first_inning_total_line | 1st inning O/U line | Available via totals_1st_1_innings market |

## Key Insight

NRFI is a "weakest link" problem. The game total captures the SUM of
expected scoring, but NRFI depends on the PRODUCT of two independent
scoreless-inning probabilities. Team total decomposition lets us model
this correctly.
