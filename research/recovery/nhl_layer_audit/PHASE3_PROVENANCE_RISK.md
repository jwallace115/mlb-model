# NHL Layer Provenance / PIT / Economics Risk (Phase 3)

## Date: 2026-04-10

---

## PIT (Point-in-Time) Violations

### Layer 1: DRIFT CORRECTION
**PIT Status: VIOLATED**
- The +0.4458 drift was derived from the OLD model's validate-season performance
- It is now being applied to a DIFFERENT model (rebuild Model A)
- This is a cross-model PIT leak: using one model's calibration for another

### Layer 2: POISSON SIM PUSH CORRECTIONS
**PIT Status: MINOR VIOLATION**
- Push corrections derived from old model's distribution
- Directionally correct but quantitatively wrong for new lambdas

### Layer 4: CONFIDENCE TIER THRESHOLDS
**PIT Status: VIOLATED**
- 0.12/0.15 thresholds set on old model's edge distribution
- New model has completely different edge distribution (92% UNDER signals)

### Layer 7: SIGNAL THRESHOLD
**PIT Status: VIOLATED**
- THRESHOLD = 0.12 from Phase 4.5 calibrated on old model

### Layer 15: LIVE FEATURE COMPUTATION
**PIT Status: STRUCTURAL MISMATCH**
- Features computed live differ systematically from training distribution
- This is not a calibration issue but a feature engineering mismatch

---

## Economic Impact

### Current live performance (2025-26 season, n=65 graded signals):
| Tier | W | L | P | Hit Rate | Status |
|------|---|---|---|----------|--------|
| HIGH | 5 | 7 | 0 | 41.7% | ACTIVE (losing) |
| MEDIUM | 15 | 17 | 0 | 46.9% | NOW SHADOWED |
| LOW | 4 | 11 | 0 | 26.7% | NOW SHADOWED |
| SHADOW_MEDIUM | 3 | 3 | 0 | 50.0% | SHADOW |

**Overall: 27W-38L-0P = 41.5% hit rate**
**At -110, break-even is 52.4%. This is a catastrophic result.**

**Estimated unit loss:**
- HIGH: 5 * 0.909 - 7 = -2.545 units
- MEDIUM: 15 * 0.909 - 17 = -3.365 units (pre-shadow)
- LOW: 4 * 0.909 - 11 = -7.364 units (pre-shadow)

**Root cause:** The drift miscalibration produces lambda_total ~0.72 goals
below the market line on average (lambda mean 5.67 vs closing_total mean 6.39).
This creates a systematic UNDER bias, generating 60/65 UNDER signals.
The actual total averages 6.57, meaning the market is more accurate.

### Compare to historical backtest:
| Split | W | L | P | Hit Rate |
|-------|---|---|---|----------|
| Validate (2023-24) | 136 | 117 | 2 | 53.8% |
| OOS (2024-25) | 82 | 72 | 0 | 53.2% |

Historical performance was marginal but above break-even.
Live performance is 12pp below historical — entirely explained by
drift miscalibration.

---

## Risk Summary by Layer

| Layer | PIT Risk | Economic Risk | Action Required |
|-------|----------|---------------|-----------------|
| 1. Drift correction | HIGH | CRITICAL | Recalibrate from scratch |
| 2. Poisson sim | LOW | LOW | Re-validate after drift fix |
| 3. Goalie handling | NONE | NONE | Native to model |
| 4. Tier system | MEDIUM | MEDIUM | Recalibrate after drift fix |
| 5. Stop rules | NONE | POSITIVE | Working as designed |
| 6. Edge calc | NONE | NONE | Standard math |
| 7. Signal threshold | MEDIUM | MEDIUM | Recalibrate after drift fix |
| 8. Grading | NONE | NONE | Standard |
| 9. OT diagnostics | NONE | NONE | Diagnostic only |
| 10. Summaries | LOW | NONE | Update benchmarks |
| 11. CLV snapshots | NONE | NONE | Infrastructure |
| 12. Line movement | NONE | NONE | Infrastructure |
| 13. Data quality | NONE | NONE | Validation |
| 14. Season perf | NONE | NONE | Aggregation |
| 15. Live features | HIGH | CRITICAL | Root cause investigation |
