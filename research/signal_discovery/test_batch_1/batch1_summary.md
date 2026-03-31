# Test Batch 1 — Summary Report

**Date:** 2026-03-27
**Signals tested:** CS001-CS006
**Safety layer:** All tests ran through hypothesis_registry.json with pre-registered thresholds

---

## Result Table

| Signal | Name | Direction | N (2025) | Perm %ile | 2024 | 2025 | Verdict |
|:-------|:-----|:----------|---:|---:|:-----|:-----|:--------|
| CS001 | Pitcher command regime shift | UNDER | 98 | 64.4 | + | + | **FAIL** |
| CS002 | Starter short-leash / early exit | OVER | 1,105 | 60.2 | - | - | **FAIL** |
| CS003 | Pitcher latent fatigue state | OVER | 315 | 21.0 | - | - | **FAIL** |
| CS004 | Bullpen collapse tail risk | OVER | 740 | **89.8** | + | + | **PASS** |
| CS005 | Bullpen latent fatigue state | OVER | 461 | 30.0 | - | - | **FAIL** |
| CS006 | Cross-market prop-to-total arb | BIDIR | — | — | — | — | **DATA_GAP** |

---

## Verdicts

### PASS: CS004 — Bullpen Collapse Tail Risk

- **Permutation:** 89.8th percentile (>85 required) — statistically significant
- **2024 direction:** Positive (50.2% over rate in flagged games vs 49.3% baseline)
- **2025 direction:** Positive (50.1% over rate)
- **Mechanism:** Bullpen run-allowed variance (rolling 10-game) identifies teams with fat-tailed reliever distributions; these teams allow slightly more scoring than market expects
- **Effect size:** Small (~0.5pp over rate lift) — directionally correct but may not survive vig
- **Next step:** Advance to shadow monitoring; evaluate whether the effect intensifies in tail-scored games (>12 runs) or in specific park/weather conditions

### FAIL: CS001 — Pitcher Command Regime Shift

- **Permutation:** 64.4th — below 85th threshold
- **Failure:** Signal was directionally positive in both 2024 and 2025 but the effect was indistinguishable from random at the permutation level
- **Issue:** Only 98 flagged games in 2025 validation (bad-command state is rare with the dual-condition threshold)
- **Recommendation:** Archive. The rolling z-score proxy detected too few bad-command games. A more sensitive threshold would increase N but dilute the signal. The mechanism may be real but is not capturable with available per-start CSW/BB data at this granularity.

### FAIL: CS002 — Starter Short-Leash / Early Exit

- **Permutation:** 60.2th — below threshold
- **Failure:** Over rate in flagged games was *below* baseline in both 2024 (49.3%) and 2025 (47.3%). The hypothesis is directionally wrong.
- **Issue:** The market already prices short-leash starters. Games with high early-exit risk tend to have lower totals already set by the market, absorbing the expected bullpen exposure.
- **Recommendation:** Archive. This mechanism is priced. The existing `combined_short_exit` shadow signal already captures this more precisely and also showed limited edge.

### FAIL: CS003 — Pitcher Latent Fatigue State

- **Permutation:** 21.0th — far below threshold
- **Failure:** Over rate in fatigued-starter games was 47.3% — *below* the baseline 50%. The signal is anti-directional.
- **Issue:** Whiff decline + BB rise as a fatigue proxy may actually be capturing regression-to-mean effects (pitchers who were overperforming return to baseline), which is already embedded in closing lines via ERA adjustments.
- **Recommendation:** Archive. The simple dual-condition flag does not capture meaningful latent fatigue beyond what market pricing already reflects.

### FAIL: CS005 — Bullpen Latent Fatigue State

- **Permutation:** 30.0th — well below threshold
- **Failure:** Over rate in high-fatigue-bullpen games was 47.7% — below baseline. Signal is anti-directional.
- **Issue:** High leverage-weighted bullpen fatigue may correlate with teams in close games (where bullpens worked hard because the game was tight), which are actually *lower*-scoring environments on average.
- **Recommendation:** Archive. Consistent with the prior bullpen fatigue research finding (WEAK SIGNAL / NO EFFECT). The leverage-weighted proxy does not improve on the regression-feature approach used in the original bullpen study.

### DATA_GAP: CS006 — Cross-Market Prop-to-Total Arbitrage

- **Status:** SP K prop odds data found in `research/kprop/` (pull scripts only, no structured prop dataset matched to game outcomes)
- **Recommendation:** Remain REGISTERED. Requires K prop data integration before testing. This is a data engineering task, not a signal design issue.

---

## Top Finding

**CS004 (Bullpen Collapse Tail Risk) is the only signal that passed all gates.** However, the effect size is small (~0.5pp over rate lift). This is consistent with the general finding throughout this project: bullpen-related signals are directionally real but individually too small to generate positive ROI after vig.

The CS004 PASS is notable because it used a different framework (EVT tail risk via run-allowed variance) than the prior bullpen research (regression features). The framework_revisit approach found weak but statistically significant signal where the original linear approach did not.

---

## Recommended Next Steps

| Signal | Action |
|:-------|:-------|
| CS004 | Shadow monitor — track over rate and tail-game frequency in 2026 |
| CS001 | Archive — insufficient N, weak permutation |
| CS002 | Archive — mechanism is priced by market |
| CS003 | Archive — anti-directional, fatigue proxy captures mean reversion not true fatigue |
| CS005 | Archive — anti-directional, consistent with prior bullpen fatigue null result |
| CS006 | Keep REGISTERED — acquire K prop data for testing |

---

## Safety Layer Performance

All 5 tested signals ran through the full safety protocol:
- Pre-registration verified for each
- Frozen thresholds matched (no tampering)
- 500-permutation tests completed
- 2025 treated as binding out-of-sample validation
- 2026 holdout never touched
- Results logged to `test_results_log.json` and `signal_board.json`

The safety layer correctly:
- Failed 4 signals on permutation (< 85th percentile)
- Passed 1 signal that cleared all gates
- Detected and reported DATA_GAP for CS006
- Produced zero suspect flags (no ROI > 30%, no extreme rates)
