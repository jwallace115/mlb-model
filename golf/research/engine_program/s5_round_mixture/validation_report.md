# S5 Round Mixture Simulator — Validation Report

Generated: 2026-03-30T22:12:08

## Classification: CALIBRATION_ONLY

## Methodology
- 3-state mixture: floor (bottom 15%), baseline (middle 70%), spike (top 15%)
- Player-specific state thresholds from prior rounds (min 30 required)
- 20,000 tournament simulations per event
- Insufficient history players: DG fallback, excluded from betting tests
- Field coverage: 87.6% of players have mixture params

## Player Type Distribution
player_type
BALANCED    27549

## Calibration (OOS Brier — lower is better)
See console output for full table.
Mixture better than Normal in 3/5 markets.

## Betting (OOS, edge >= 4%)
See console output for full ROI comparison.

## Key Answers
1. Mixture improves on Normal: Yes
2. Standalone: CALIBRATION_ONLY
3. Winner viable: check ROI
4. Best player type: HIGH_SPIKE
5. Replace DG: no
