# NHL Minimal Revalidation (Phase 5)

## Date: 2026-04-10

---

## Test 1: Old drift correction (+0.4458) on rebuild predictions

### Historical OOS (2024-25) — rebuild Model A
- Model A raw lambda mean: 5.918
- Model A + 0.4458 drift: 6.364
- Actual total mean: 6.081
- Bias after old drift: +0.283 (OVER-predicts by 0.28 goals)

**Verdict: OLD DRIFT WORSENS REBUILD MODEL.**
The rebuild model with old drift over-predicts OOS by 0.28 goals,
whereas without drift it under-predicts by only 0.16 goals.
The old drift makes things WORSE, not better.

### Live 2025-26 season
- Lambda_total_calibrated (with drift) mean: 5.674
- Actual total mean: 6.569
- Bias: -0.896 (still under-predicts by 0.90 goals)

The live feature discrepancy is so large (~1.34 raw) that even the
over-generous +0.4458 drift cannot bring predictions close to actual.

---

## Test 2: What drift WOULD work for live?

- Live raw lambda (estimated): 5.228
- Live actual mean: 6.569
- Required total drift: +1.341

This is an absurdly large drift. If the model needs a +1.34 goal
constant correction, the features are not providing useful signal.
A drift this large would dominate the model output and make the
feature-based predictions nearly irrelevant.

**Verdict: DRIFT ALONE CANNOT FIX THE LIVE PIPELINE.**
The feature computation must be investigated and fixed first.

---

## Test 3: Old tier thresholds on rebuild edge distribution

### Live edge distribution:
- 92.3% of signals are UNDER
- Mean edge: 0.146
- This is not a meaningful edge distribution; it is a bias artifact

### Historical edge distribution (Phase 5 results):
- Validate: mean edge 0.138, mixed OVER/UNDER signals
- OOS: mean edge 0.128, mixed OVER/UNDER signals

### After hypothetical correct drift:
If features were correct and drift were ~+0.16:
- Lambda would be closer to the market line
- Signal side distribution would be mixed (as in historical)
- Edges would be smaller on average
- The 0.12/0.15 thresholds might need lowering

**Verdict: CANNOT VALIDATE THRESHOLDS until feature/drift issues are fixed.**

---

## Test 4: Which layers are SAFE to carry forward right now?

### Safe (no dependency on drift/features):
1. Poisson simulation mechanics
2. Edge calculation
3. Grading logic
4. OT/SO diagnostics
5. CLV snapshot infrastructure
6. Line movement tracking
7. Data quality audit
8. Season performance aggregation
9. Summary generation (with benchmark update)

### Unsafe (require recalibration):
1. DRIFT CORRECTION — must be recalibrated from scratch
2. LIVE FEATURES — must investigate feature mismatch
3. TIER THRESHOLDS — must recalibrate after drift fix
4. SIGNAL THRESHOLD — must recalibrate after drift fix
5. STOP RULES — must reset after drift fix
6. PUSH CORRECTIONS — should re-validate after drift fix

---

## Test 5: Is the stop-rule mechanism working correctly?

**YES.** The stop rules correctly identified that MEDIUM (33.3% hit) and
LOW (26.7% hit) tiers were losing money and shadowed them on 2026-04-09.
HIGH tier is still active despite 41.7% hit rate (5W-7L), which is below
break-even but within a small sample where shadowing would be premature.

The stop-rule mechanism is a well-designed safety layer that functions
independently of the base model.
