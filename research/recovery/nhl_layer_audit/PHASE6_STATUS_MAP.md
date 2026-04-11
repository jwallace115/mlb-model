# NHL Layer Status Map (Phase 6)

## Date: 2026-04-10

---

## Classification Legend

- **PORTABLE**: Can be carried forward as-is onto rebuilt base
- **NATIVE**: Part of the rebuilt base model, not a separate layer
- **RECALIBRATE**: Mechanism is sound, but constants/thresholds need re-derivation
- **BROKEN**: Currently producing wrong outputs; needs root cause fix
- **INFRASTRUCTURE**: Model-agnostic supporting system

---

## Final Layer Classification

| # | Layer | Classification | Priority | Blocks Deployment? |
|---|-------|----------------|----------|-------------------|
| 1 | Drift Correction | BROKEN | P0 | YES |
| 2 | Poisson Simulation | PORTABLE | P2 | No |
| 3 | Goalie Handling | NATIVE | N/A | No |
| 4 | Confidence Tiers | RECALIBRATE | P1 | YES |
| 5 | Stop Rules | PORTABLE | P2 | No |
| 6 | Edge Calculation | PORTABLE | N/A | No |
| 7 | Signal Threshold | RECALIBRATE | P1 | YES |
| 8 | Grading | PORTABLE | N/A | No |
| 9 | OT/SO Diagnostics | PORTABLE | N/A | No |
| 10 | Summaries | PORTABLE | P3 | No |
| 11 | CLV Snapshots | INFRASTRUCTURE | N/A | No |
| 12 | Line Movement | INFRASTRUCTURE | N/A | No |
| 13 | Data Quality Audit | INFRASTRUCTURE | N/A | No |
| 14 | Season Performance | INFRASTRUCTURE | N/A | No |
| 15 | Live Features | BROKEN | P0 | YES |

---

## Deployment Blockers (must resolve in order)

### P0 — Live Feature Mismatch (Layer 15)
The live feature computation produces predictions ~1.34 goals below actual.
This is the root cause of all downstream failures. Must investigate:
- Are live SOG/PP features computed identically to historical?
- Is goalie SV% tracking goalie-specific or team-level?
- Are shrinkage priors correct for 2025-26 season?
- Is there a systematic difference in rolling window behavior?

### P0 — Drift Recalibration (Layer 1)
After Layer 15 is fixed, recalibrate drift using:
1. Run Model A on 2025-26 live features (corrected) vs actuals
2. Compute new seasonal drift
3. Implement dynamic drift (the stub exists but was never completed)

### P1 — Threshold Recalibration (Layers 4, 7)
After drift is correct:
1. Compute edge distribution on corrected predictions
2. Find new empirical threshold (lowest band with hit >= 52.5%, n >= 30)
3. Set new tier boundaries based on edge distribution percentiles

---

## Layers Ready for Immediate Use

The following 10 layers can be carried forward immediately with zero changes:
- Edge calculation (6)
- Grading (8)
- OT/SO diagnostics (9)
- CLV snapshots (11)
- Line movement (12)
- Data quality audit (13)
- Season performance (14)
- Poisson simulation (2) — re-validate push corrections later
- Stop rules (5) — reset tiers after recalibration
- Summaries (10) — update league avg benchmarks

---

## Architecture Note

The pipeline architecture is sound. The issue is not structural — it is
a calibration failure caused by swapping the base model (from old MoneyPuck
model to rebuild Model A) without recalibrating the drift correction and
without validating that live features match training features.

The fix sequence is:
1. Diagnose live feature mismatch (Layer 15)
2. Fix feature computation to match training distribution
3. Recalibrate drift on corrected features
4. Recalibrate thresholds on corrected edge distribution
5. Reset stop rules
6. Shadow deploy for minimum 2 weeks before activating stakes
