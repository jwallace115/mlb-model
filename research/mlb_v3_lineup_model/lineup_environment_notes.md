# Lineup Environment Notes

Total team-game rows: 19430

## Aggregation Method
- Simple mean across 9 starters (v1; order-weighting not implemented yet)
- top4_iso_last20: mean ISO of 4 highest-ISO starters
- bottom3_k_rate_last20: mean K rate of 3 highest-K starters (weak spots)

## Features Built
- lineup_k_rate_last20, lineup_bb_rate_last20, lineup_contact_rate_last20, lineup_iso_last20
- top4_iso_last20, bottom3_k_rate_last20

## Not Built
- lineup_handedness_balance: batSide not available
- Order-weighted aggregation: deferred to Phase 2
- Hard-hit/barrel/pull/launch angle: Statcast batter data not available locally
