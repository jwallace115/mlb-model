# OBJECT 1: F5 Totals Engine

## Dependency Analysis

The F5 signal generator (`mlb_sim/pipeline/f5_signal_generator.py`) reads
`p_under_full` and `p_over_full` from V1 signal outputs (`signals_2026.parquet`).
It fires F5 UNDER when `p_under_full >= 0.57` and F5 OVER when `p_over_full >= 0.57`.
The F5 line comes from independently collected F5 closing lines.

**F5 DEPENDS on V1 probabilities.** The F5 engine does NOT have its own model;
it consumes V1 full-game probabilities as the signal trigger.

## Revalidation with Clean V1

The F5 research dataset (`research/f5/data/v1_probabilities_2024_2025.parquet`)
contains V1 probabilities that were computed from the CONTAMINATED model.
We now have clean V1 probabilities. Let's check how signal frequency changes.

F5 UNDER signals (p>=0.57): contaminated=1033, clean=160
F5 OVER signals (p>=0.57): contaminated=417, clean=1403

Correlation(contaminated p_under, clean p_under): 0.5036
Mean delta (clean - contaminated): -0.0677

## Verdict: DIMINISHED
F5 directly consumes V1 probabilities. Clean V1 has worse signal performance
(see Object 6 tier analysis). F5 inherits all V1 degradation.
F5 threshold (0.57) was tuned on contaminated V1 — needs re-derivation on clean V1.