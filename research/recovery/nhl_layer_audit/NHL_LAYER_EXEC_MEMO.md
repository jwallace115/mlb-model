# NHL Layer Compatibility Audit — Executive Memo

## Date: 2026-04-10

---

## Bottom Line

The NHL pipeline has 15 distinct layers. **10 are portable** and can be carried
forward immediately. **2 are broken** (drift correction and live feature computation)
and are the root cause of the 41.5% hit rate in 2025-26 live betting. **3 need
recalibration** after the broken layers are fixed.

**The pipeline architecture is sound. The failure is a calibration mismatch
caused by swapping the base model without recalibrating downstream constants.**

---

## What Happened

1. The original NHL model used MoneyPuck features (xGF, xGA, HD shots).
2. MoneyPuck data became unavailable, so the model was rebuilt (Model A) using
   only NHL API data (SOG, PP%, PK%, goalie SV%).
3. Model A demonstrated genuine predictive power on historical data:
   - OOS MAE 1.3% better than market
   - Edge correlation with market error: 0.155
4. However, when deployed live:
   - The old model's drift correction (+0.4458) was kept, but Model A only needs ~+0.16
   - The live feature computation produces systematically different features than
     historical training data, creating a 1.34-goal raw prediction bias
   - Result: 92% of signals are UNDER, and the overall hit rate is 41.5%

---

## Key Numbers

| Metric | Historical (OOS) | Live (2025-26) |
|--------|-------------------|-----------------|
| Model bias (lambda - actual) | -0.16 goals | -0.90 goals |
| Raw lambda gap | -0.16 | -1.34 |
| Signal side split | Mixed OVER/UNDER | 92% UNDER |
| Hit rate | 53.2% | 41.5% |
| Edge mean | 0.128 | 0.146 (inflated) |

---

## Layer Classification Summary

| Status | Count | Layers |
|--------|-------|--------|
| PORTABLE (carry forward as-is) | 7 | Edge calc, Grading, OT diagnostics, Poisson sim, Stop rules, Summaries, All infrastructure |
| NATIVE (part of base model) | 1 | Goalie handling |
| RECALIBRATE (sound mechanism, wrong constants) | 3 | Tier system, Signal threshold, Push corrections |
| BROKEN (wrong outputs) | 2 | Drift correction, Live features |
| INFRASTRUCTURE | 4 | CLV, Line movement, Data quality, Season perf |

---

## Immediate Actions

### 1. Shadow ALL tiers (today)
HIGH tier is still active with 41.7% hit rate (5W-7L). Shadow it now.
The stop rules correctly shadowed MEDIUM and LOW already.

### 2. Diagnose live feature mismatch (this week)
Compare live-computed features for completed games against what the rebuild
feature table would produce for the same games. Find which features diverge
and why. Likely causes:
- Goalie tracking: live uses team-level proxy, historical had goalie-specific data
- SOG/PP counting: possible API response format differences
- Shrinkage priors: early-season averaging may differ from historical

### 3. Fix features, then recalibrate drift (next)
Once features match training distribution, compute new seasonal drift from
2025-26 games. Implement the dynamic drift stub that already exists in the code.

### 4. Recalibrate thresholds (after drift)
Sweep edge bands on corrected predictions. Set new THRESHOLD and tier boundaries.

### 5. Shadow deploy 14+ days (before any real stakes)
Log corrected signals, grade daily, verify hit rate >= 52% before promoting.

---

## What Is NOT Wrong

- The pipeline architecture (schedule fetch -> features -> predict -> simulate -> edge -> qualify -> grade) is correct
- The Poisson simulation mechanics work correctly
- The grading system works correctly (game_id match, idempotent, OT-aware)
- The CLV infrastructure captures lines correctly
- The stop-rule mechanism correctly identified poor performance
- Model A has genuine predictive power on historical data

---

## Timeline Estimate

| Phase | Duration | Dependency |
|-------|----------|------------|
| Shadow HIGH tier | Today | None |
| Feature mismatch diagnosis | 2-3 days | None |
| Feature fix + drift recalibration | 1-2 days | After diagnosis |
| Threshold recalibration | 1 day | After drift fix |
| Shadow validation | 14+ days | After all fixes |
| Promotion decision | 1 day | After shadow validation |
| **Total to first real stake** | **~3-4 weeks** | |

---

## Files Produced

- `PHASE1_LAYER_INVENTORY.md` — Complete 15-layer inventory
- `PHASE2_DEPENDENCY_AUDIT.md` — Dependency analysis per layer
- `PHASE3_PROVENANCE_RISK.md` — PIT violations and economic impact
- `PHASE4_COMPATIBILITY.md` — Compatibility with rebuilt base model
- `PHASE5_REVALIDATION.md` — Validation tests on portable layers
- `PHASE6_STATUS_MAP.md` — Final classification and fix sequence
- `NHL_SHADOW_RULESET.md` — Shadow deployment rules and promotion gates
- `NHL_LAYER_FINAL_TABLE.csv` — Machine-readable layer status table
- `NHL_LAYER_EXEC_MEMO.md` — This document
