# Final Keep/Kill Classification Table

Date: 2026-04-10

## Classification Rules

- **KEEP**: 0-1 flags, clean evidence of edge, independent pipeline
- **SHADOW-CONTINUE**: 1-2 flags, promising early data but insufficient sample, needs more shadow time
- **FREEZE**: 2-3 flags, no evidence yet, keep code but stop running daily
- **KILL**: 3+ flags, contaminated identity, negative evidence, or dead parent dependency

---

| # | Object | Flags | Classification | Rationale |
|---|--------|-------|---------------|-----------|
| 1 | F5 Run Line (Signal B) | 0 | **KEEP** | PIT-safe, independent, clean threshold, directionally confirmed 2024-2025 |
| 2 | ADJ_CONTACT | 1 | **SHADOW-CONTINUE** | 53.8% hit rate (65 resolved), PIT-safe, independent in live code |
| 3 | ADJ_HH | 1 | **SHADOW-CONTINUE** | 61.8% hit rate (34 resolved), best early performer, needs larger sample |
| 4 | ADJ_K_RATE | 1 | **SHADOW-CONTINUE** | 56.7% hit rate (30 resolved), PIT-safe, independent |
| 5 | ADJ_BB_RATE | 2 | **FREEZE** | 50.0% hit rate = no edge. Keep logging but do not pursue activation. |
| 6 | ADJ_RUN_SUPP | 1 | **SHADOW-CONTINUE** | 55.9% hit rate (34 resolved), PIT-safe |
| 7 | CS013 | 2 | **FREEZE** | 0 fires in 128 games. Signal may be too rare. Keep code, stop daily review. |
| 8 | CS028 | 2 | **FREEZE** | 2 fires, 1 resolved. Trivially small. Keep code, stop daily review. |
| 9 | KP04 | 2 | **FREEZE** | 0 fires in 226 games. Signal never activates. Keep code, stop daily review. |
| 10 | ST02 | 3 | **KILL** | 0 fires, V1-dependent overlay, no standalone value demonstrated |
| 11 | P09 Overlay | 3 | **KILL** | OOS collapses (active 50.9% vs inactive 52.8%). V1-dependent. No standalone path. |
| 12 | S12 Overlay | 4 | **KILL** | Negative in-sample at every threshold. Cutoff contaminated. Amplifies losing bets. |
| 13 | V2 Baseline Engine | 2 | **FREEZE** | No bettable edge (RMSE +0.01 vs market). Strong over bias. Academic interest only. |
| 14 | flyball_wind (discrete) | 2 | **FREEZE** | +4pp lift but within unprofitable universe. Already continuous feature in V2. |
| 15 | F5 Totals Engine | 4 | **KILL** | 85% signal collapse with clean V1. Threshold contaminated. Fully V1-dependent. |
| 16 | F5 Standalone | N/A | **DEFERRED** | Not built. Would need independent clean architecture. |
| 17 | Team Totals (Home) | 5 | **KILL** | Identity NEVER-MATCHED. Three different objects. Coefficient contamination. |
| 18 | Team Totals (Away) | 5 | **KILL** | Same as Home TT. Most contaminated object in the system. |
| 19 | Combined Short Exit | 2 | **FREEZE** | PIT-safe, independent, but 0 fires in 128 games. |

---

## Summary Counts

| Classification | Count | Objects |
|---------------|-------|---------|
| **KEEP** | 1 | F5 Run Line |
| **SHADOW-CONTINUE** | 4 | ADJ_CONTACT, ADJ_HH, ADJ_K_RATE, ADJ_RUN_SUPP |
| **FREEZE** | 7 | ADJ_BB_RATE, CS013, CS028, KP04, V2 Engine, flyball_wind, Combined Short Exit |
| **KILL** | 5 | ST02, P09, S12, F5 Totals, Team Totals (x2) |
| **DEFERRED** | 1 | F5 Standalone (not built) |
| **N/A** | 1 | Team Totals Away (same verdict as Home) |

## Decision Boundary Notes

- KEEP requires: 0-1 flags AND positive directional evidence AND independent of V1
- SHADOW-CONTINUE requires: positive early hit rate (>52%) AND PIT-safe AND independent in live code
- ADJ signals survive despite research using V1 gate because live code fires independently (combined > 0)
- FREEZE objects retain code but consume zero operational attention until next review
- KILL objects should have shadow logging disabled to reduce noise in daily pipeline
