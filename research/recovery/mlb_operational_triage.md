# MLB Operational Triage — Three Buckets

**Date:** 2026-04-10

---

## BUCKET A — SAFE (No contamination in any path)

These objects can be trusted fully. No action needed.

| Object | Reason |
|--------|--------|
| V1 Rules Mode | No trained model; live FG API daily |
| CS013 Shadow | Per-game boxscores with shift(1) |
| CS028 Shadow | Per-game boxscores with shift(1) |
| CS004 Shadow | Per-game boxscores with shift(1) |
| KP04 Shadow | Per-start Statcast with shift(1) |
| ST02 Overlay | Schedule data only |
| ADJ Signals (v2) | Per-start Statcast shift(1).rolling() |
| P09 per-start metrics | Per-start Statcast shift(1).rolling() |
| Combined Short Exit Shadow | Per-start IP shift(1).rolling(15) |
| high_leverage_avail (V1 feature) | Per-game boxscores shift(1) |
| park, weather, umpire, rest, DH features | Static/per-game, no historical dependency |
| Team Totals Engine | Live MLB API + PIT-fixed PGL |
| Cross-market triangle research | Market data only |
| TT-to-side feasibility research | Market data only |
| Side Engine clean rerun | Rebuilt with PIT features |

---

## BUCKET B — CAVEATED (Live inference clean, historical basis contaminated)

These are safe to keep running live. The live data pipeline is clean. But the model weights, thresholds, or cutoffs were derived from contaminated historical data and should be re-validated after the V1 PIT retrain.

### B1. V1 Ridge Model — KEEP LIVE

**Assessment:** The model weights were learned from contaminated features, but:
- Live inference pulls current-day FG API (clean)
- The contamination made features MORE predictive in training (less noise), so weights may be slightly over-confident in pitcher quality
- Over-confidence in a directionally-correct feature is suboptimal, not catastrophic
- Turning off V1 entirely means no simulation model — worse outcome
- The model sigma (4.361) may be slightly too tight (contaminated training had less noise than reality)

**Risk:** Model may fire more signals than warranted, with slightly inflated confidence. The STRONG tier (+2.3% OOS) was measured against contaminated training — true OOS edge may be smaller.

**Mitigation:** Continue monitoring live shadow performance. When PIT-retrained V1 is ready, swap via MODEL_MODE flag.

### B2. S2 Starter Path Model — KEEP LIVE

**Assessment:** Only 1 of 9 features contaminated (sp_xfip). The other 8 (CSW, whiff, fstrike, rest, recent pitch count, opponent wOBA, park, weather) are all clean. Path classification is relatively robust to a single noisy feature.

**Risk:** Low. Path bucket assignments may be slightly off, but the CSW/whiff features carry most of the signal for path prediction.

### B3. S12 Overlay — KEEP LIVE

**Assessment:** Live computation is clean (current CSW + xFIP). The frozen cutoff (8.4468) was the P80 of 2024 S12 values computed with season-final xFIP. With PIT-clean xFIP, the percentile boundary may shift modestly.

**Risk:** May fire on ~5-10% wrong set of games. Since this is a 1.25x stake amplifier (not a new bet generator), the downside is bounded.

### B4. F5 Totals Engine — KEEP LIVE

**Assessment:** Reads V1 p_under/p_over directly. Thresholds (0.57) tuned on contaminated V1 output.

**Risk:** Threshold may be too aggressive if V1 probabilities are slightly inflated. But F5 has an independent hard stop and separate performance tracker.

### B5. F5 Run Line Signal — KEEP LIVE

**Assessment:** Uses live FG xFIP (clean). The threshold (xFIP gap >= 1.0) was not validated with PIT-clean data but is a simple gap rule, not a fitted model.

**Risk:** Low. The gap itself is measured live and correctly. The question is whether 1.0 is the right threshold — it's a reasonable heuristic regardless.

---

## BUCKET C — VOID (Research conclusions that cannot be trusted)

| Object | Status | Notes |
|--------|--------|-------|
| MLB Side Engine Phases 2-4 (original) | VOIDED | Already rebuilt clean. Clean rerun: NEAR MISS (not profitable, but close). Original research conclusions were invalid. |

---

## Key Decision: V1 Ridge Live Status

**Question:** Should V1 Ridge be demoted to shadow-only?

**Answer: NO. Keep live.**

**Rationale:**
1. The live inference path is provably clean — it calls `modules/pitchers.py` which hits the current FG API
2. The alternative is reverting to Rules Mode, which has no trained model and no probability calibration
3. The contamination affects weight optimization, not direction. xFIP-like features genuinely predict totals — the model just learned slightly inflated coefficients
4. The sigma estimate (4.361) is based on contaminated residuals and may be ~0.1-0.2 too tight, making confidence intervals slightly too narrow
5. Worst case: the model fires 10-15% more signals than it should, with slightly less edge per signal
6. The PIT retrain is a bounded, well-defined fix — aim for completion within 1-2 weeks

**What changes operationally:**
- Treat all V1 signals as MEDIUM confidence until PIT retrain is complete
- Do not increase any stake sizes based on V1 output
- Monitor shadow_log for any divergence between rules vs simulation mode
- Prioritize the PIT retrain over all other research work
