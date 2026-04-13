# Phase 0 - Engine Charter
## MLB Totals Context Engine V1

### What This Engine Is NOT

This is not a betting model. A betting model takes inputs and produces a probability estimate plus an edge versus a posted line, optimized for ROI over a historical backtest. Betting models are evaluated by win rate and profitability. They fail when the signal degrades or when the market closes the gap.

This engine does not do that. It has no edge output. It has no ROI target. It will never be submitted to a sportsbook.

### What This Engine IS

This is a structural decomposition engine. It takes a single MLB game and answers eight structural questions about that game run environment. Each question has a bounded, interpretable answer derived from a frozen formula. The output is a labeled description of what kind of game this is likely to be, not a prediction of the final score.

A context engine is infrastructure, not alpha.

It provides scaffolding that allows downstream niche objects (specific market segments, specific game archetypes, specific situational triggers) to know which structural regime they are operating in. A niche object that fires in high-starter-stability, low-bullpen-instability, compressed-market games knows something fundamentally different about its historical edge than one that fires in fragile-starters, volatile-bullpen, weather-lift games, even if both have the same surface-level win rate.

### Why Not V1

The V1-era feature tables (sim/phase2_build_features.py output, opponent_adjusted_engine_v2 pitcher tables) were built with full-season aggregates embedded as game-level features. A pitcher xFIP computed over the full 2022 season was joined to games from April 2022, meaning the feature at game time included information from October 2022. This is target leakage.

The V1 feature table (sim/data/feature_table.parquet) is permanently excluded. No derived file with ambiguous lineage is used.

All features in this engine are point-in-time safe: for any game on date D, only data from dates strictly before D is allowed to enter any feature computation.

### Why Decomposition Matters

Decomposition forces interpretability by constraint. Each of the eight outputs is limited to 3-4 inputs. This is not an arbitrary aesthetic choice. It is a guardrail against:

1. Overfitting by complexity: A 25-feature ridge model can fit noise in a 2,400-game season. A 3-input formula with bounded output cannot fit the same noise.
2. Silent contamination: Complex pipelines hide lineage problems. Simple formulas expose them.
3. Regime collapse: Black-box models degrade silently when the game changes. Decomposition outputs show which component changed and why.
4. Attribution failure: When a bet wins or loses, decomposition tells you which structural component was responsible.

### How It Supports Niche Objects

Niche objects are downstream consumers. They need to know: given that this bet fired, what was the structural context of the game?

- P1B (Starter Dominance Under): Fires in games with both starters rated HIGH stability. The context engine tells P1B what fraction of its OOS sample had strong weather/park lift working against it.
- F5 Over pressure objects: Need to know if the F5 run pressure score was high or low, independently of the full-game total.
- Dead totals objects: Operate in compressed market path games. The context engine Market Path Shape output tells whether the total moved, stayed flat, or compressed into the close.

### Why Interpretability Beats Backtest Glamour

A backtest showing +6.5% ROI is not evidence of an edge. The Phase 7 model showed exactly this: +6.5% in 2024 validation, -0.5% OOS in 2025. The market had closed the gap. The backtest was glamorous. The live result was flat.

An interpretable decomposition engine that correctly identifies structural game regimes consistently across 2022-2025 is a durable foundation. It does not promise profit. It promises that when profit comes, we know why.

That is the charter of this engine.

---

Built: 2026-04-12 | Research split: Discovery 2022-2023, Validation 2024, OOS 2025
