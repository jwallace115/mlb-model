# MLB Runtime Object V6 — Start Here

**Built:** 2026-04-22

V5 + 11 starter exit probability features. 19430×263.

## What V6 Adds
- `exit_prob_by_4/5/6/7_last_5/10` — P(starter exits by inning N) rolling
- `exit_prob_by_5_baseline` — expanding season baseline
- `exit_prob_by_5_drift_last_5` — drift from baseline
- `deterioration_score_norm` — composite exit+velo+zone deterioration

## CRITICAL: Outcome Columns EXCLUDED
exit_inning, exited_by_4/5/6/7 are NOT in V6 — these are outcomes.
Only pre-game probability estimates are included.

## Version Stack
- **V6:** + Starter exit probability (sim phase 1 complete)
- **V5:** + Bullpen leverage tiers
- **V4:** + Lineup quality
- **V3:** + Pitch-level drift
- **V2:** + Batting rolling
- **V1:** Pitcher rolling + context

## Simulation Status
V6 contains BOTH Phase 1 simulation components:
1. Bullpen leverage-tier quality (from V5)
2. Starter exit probability distribution (this build)
Ready for Phase 2A state-transition testing.

## Caveats
- All new features null for 2022
- Effective window: 2023-2025
