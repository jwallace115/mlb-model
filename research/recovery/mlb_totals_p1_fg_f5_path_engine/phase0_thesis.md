# MLB Totals P1 — FG/F5 Path Mismatch Engine

## Thesis

The full-game (FG) total and first-five-inning (F5) total together imply a **scoring path**.
When the market's implied early/late split is structurally wrong — e.g., the market expects
late scoring but the game structure (elite bullpen, short-leash SP, park effects) suggests
early resolution — there may be exploitable FG total mispricing.

## Key Definitions

- **F5_ratio** = F5_total / FG_total — the share of scoring the market expects in innings 1-5
- **late_implied** = FG_total - F5_total — market's expected late-inning (6-9) scoring
- **path_error** = actual_late_runs - late_implied — how wrong the market's late-scoring expectation was

## What We Are NOT Doing

- No V1 anything
- No broad mean-prediction models
- F5 total is an INPUT (market signal), not a target market
- Target is FULL-GAME totals betting only
- No ADJ family features (separate shadow lane)

## Splits

- Discovery: 2022-2023 (or 2023-only if F5 data limited)
- Validation: 2024
- OOS: 2025

## PIT-Safety

All features must be point-in-time safe — no leakage from game-day information
that would not have been available pre-game.
