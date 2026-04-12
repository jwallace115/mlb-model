# Phase 5 — Best Next Target

**Date:** 2026-04-12

---

## Ranking of Active Objects by Expected Value

### 1. ADJ_HH (C2) — HIGHEST PRIORITY
- **2026 shadow:** 63.6% hit rate on 33 decisions (21W-12L)
- **Backtest context:** 2025 OOS was +5.6% ROI (best of all ADJ signals)
- **Fire rate:** 47 fires / 150 games = 31% (manageable volume)
- **Why best:** Strongest convergence of backtest improvement trend (2022-2025
  trajectory: -3.5%, -8.7%, -2.8%, +5.6%) AND strongest 2026 live performance.
  If 63.6% hit rate holds at N=50, this is a +20% ROI signal at -110.

### 2. adj_k_rate (C3) — HIGH PRIORITY
- **2026 shadow:** 60.7% hit rate on 28 decisions (17W-11L)
- **Backtest context:** 2025 OOS was +4.1% ROI
- **Fire rate:** 38 fires / 150 games = 25%
- **Why second:** Second-best convergence. K-rate is a fundamentally coherent
  feature (high-K pitchers suppress runs). Smaller sample than ADJ_HH though.

### 3. CS004 (C9) — MEDIUM PRIORITY
- **2026 shadow:** 60.0% hit rate on 20 decisions (12W-8L)
- **Backtest context:** No clean standalone backtest exists yet
- **Fire rate:** 25 fires / 158 games = 16%
- **Why third:** Promising hit rate but smallest resolved sample. Also lacks
  the multi-year backtest that ADJ signals have. Needs both more data AND
  a historical backtest to validate.

### 4. ADJ_RUN_SUPP (C5) — MEDIUM PRIORITY
- **2026 shadow:** 59.4% hit rate on 32 decisions (19W-13L)
- **Backtest context:** 2025 OOS was +1.8% ROI (weakest of the three ADJ survivors)
- **Fire rate:** 55 fires / 110 games = 50% (very high — may be too loose)
- **Why fourth:** Hit rate is decent but the high fire rate suggests the
  threshold may be too permissive. 2025 backtest ROI was only +1.8%.

### 5. ADJ_CONTACT (C1) — LOW PRIORITY
- **2026 shadow:** 55.6% hit rate on 63 decisions (35W-28L)
- **Backtest context:** 2025 OOS was +0.4% ROI (barely positive)
- **Fire rate:** 92 fires / 150 games = 61% (fires on almost everything)
- **Why last:** Highest sample but thinnest edge. 55.6% is only 3.2pp above
  breakeven at -110. This is the most likely to regress to noise.

---

## Recommended Next Action

**Wait for ADJ_HH to reach N=50 resolved decisions.** At current accumulation
rate (~2/day), this should occur around April 20-22, 2026.

At that point:
1. If hit rate >= 55%: Add closing under price logging and begin ROI tracking
2. If hit rate 52-55%: Continue monitoring to N=100
3. If hit rate < 52%: KILL

**Do not invest research time in new MLB totals ideas.** The entire totals
universe has been audited. The only remaining edge candidates are the ADJ
signals and CS004, both of which just need more shadow data. Research time
is better spent on other sports/markets.
