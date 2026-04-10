# Synthesis: Alt-Total Surface Mispricing + Run-Line Comeback Asymmetry

**Date:** 2026-04-10
**Branch A verdict:** CLOSE
**Branch B verdict:** CLOSE

---

## 1. Which Finding Has Higher Structural Value?

Neither finding advances. If forced to rank residual informational value:

**Branch A (alt-total curvature) is structurally more interesting** — a real, stable, directionally consistent curvature error exists in the alt-total ladder (82% consistency across two independent windows). Books overestimate Over probability at distance +2 to +5 from the main line because they use smooth interpolation that doesn't capture the actual run-scoring distribution's thinner tails. But the hold widens at exactly the same extremes (5.9% at main line → 7.0-7.2% at distance +3-4), absorbing the raw 4-7% edge. Only 1-2 of 7 books showed positive ROI, and the strongest single result (williamhill_us +5.0%, N=366) is a single-book finding.

**Branch B (run-line asymmetry) is a clean null.** The run-line market is remarkably well-calibrated. Walk-off truncation is real (8.9pp excess 1-run home wins) but perfectly priced — home and away -1.5 cover rates are 35.8% vs 35.9% across 9,857 games. No pregame conditional bucket reaches significance. Season residuals flip sign year to year.

## 2. Do They Interact?

**No meaningful interaction.**

- Alt-total mispricing is a distribution-shape phenomenon — books assume a smoother CDF than reality. Run-line mispricing would be a conditional-probability phenomenon — books misprice win margin given win probability. These are orthogonal market mechanics.
- Alt-total curvature errors occur at every ladder point regardless of V1 signal direction (the V1-UNDER subsample was suggestive but N=15). Run-line efficiency holds across all pregame conditional buckets. There is no evidence that games with mispriced alt ladders also have mispriced run-lines.
- Both findings converge on the same conclusion: **the MLB market is efficient at translating its main-line pricing into derivative markets (alt totals, run-line).** The translation mechanisms (smooth ladder interpolation, ML-to-RL conversion) are imperfect in theory but the hold structure and market competition absorb the theoretical errors.

## 3. How Do These Findings Fit With Existing Live Signals?

| Signal | Status | Relationship to This Research |
|--------|--------|-------------------------------|
| **V1 under engine** | LIVE | Alt-total curvature is strongest in V1-UNDER games (suggestive, N=15) but not actionable as standalone. V1 already captures the shape insight. |
| **Signal B (F5 RL)** | LIVE | Run-line research confirms Signal B is the correct expression of xFIP mismatch — F5 -0.5 avoids bullpen noise and walk-off truncation that plague full-game -1.5. No additive full-game RL signal found. |
| **Team-total engine** | SHADOW | Alt-total ladder errors could theoretically inform TT pricing, but the effect is too small after vig. TT engine already uses its own truncation model. |
| **ADJ signals** | SHADOW | ADJ identifies games where both starters suppress — these should have more compressed distributions, amplifying alt-total curvature errors on the under side. Not tested (ADJ N too small in the alt-total sample window). Worth revisiting if ADJ sample grows. |
| **CS028/CS013/KP04** | SHADOW | No interaction. These are game-specific conditional signals, not market-structure plays. |

**Net conclusion:** Neither branch adds anything deployable to the existing signal portfolio. The existing signals are already operating in the right markets with the right mechanics.

## 4. Recommended Build Order

**Neither advances.** No build required.

If the alt-total finding were to strengthen in the future (e.g., a book with consistently lower hold at the extremes, or a larger sample confirming the williamhill_us +5.0% ROI), the build order would be:

1. Alt-total under signal at distance +2 to +3.5 from main line, single-book (williamhill_us)
2. V1-UNDER overlay filter (only fire when V1 also fires under)
3. But this is speculative — the current data does not support it.

## 5. Updated MLB Discovery Map After This Cycle

### CLOSED (no further work)
- SEEP (3 phases) — no residual signal
- Command Volatility — no orthogonal value
- Opener/Bulk Subtype A — too rare, no edge
- Mixture Model / Distribution Shape — absorbed by V1
- Rolling Sigma — market already embeds
- Bullpen Depletion / Elite Availability / Correction Layer — absorbed by Phase 8
- Bullpen Path-Tree pregame — no pregame exploitability
- Home-Field Erosion — no signal
- Coaching Cascade — no signal
- Second-Year Portal Build — no orthogonal value
- F5 Settlement Divergence — **CLOSED** (proxy artifact confirmed with real lines)
- **Alt-Total Surface Mispricing — CLOSED** (curvature error real but absorbed by hold)
- **Run-Line Comeback Asymmetry — CLOSED** (market fully prices walk-off mechanics)

### NEAR MISS (monitoring only)
- Umpire Edge-Call — real effect, small magnitude
- F5 Path Mismatch — real effect, market aware
- Bullpen Path-Tree live — 70% blowout over rate, needs live infrastructure
- Schedule Front-Loading — suggestive, needs more data
- Home Total Truncation — suggestive, feeds TT engine
- Cross-Market Triangle — advancing to next phase

### ACTIVE / DEPLOYED
- V1 totals engine — LIVE
- Signal B F5 run-line — LIVE
- F5 totals engine — LIVE (paused for sample collection)
- Team-total engine — SHADOW
- ADJ signals — SHADOW
- CS028/CS013/KP04/ST02/CS004 — SHADOW
- Combined Short Exit — SHADOW

### HIGHEST-VALUE NEXT BUILD

**Cross-Market Triangle** is the single highest-value next MLB build.

Rationale:
- It was the only research branch to receive ADVANCE from the market structure tests
- It exploits the relationship between three independently-set market lines (ML, total, run-line) rather than trying to beat any single market
- It is orthogonal to all existing signals (V1, Signal B, ADJ, TT)
- The alt-total and run-line research confirmed that individual derivative markets are well-calibrated on their own — but the *cross-market consistency* between them has not been tested
- If books set ML, total, and RL independently (which they do), there may be arbitrage-like conditions when all three disagree about the same underlying game state

Secondary priorities:
1. Team-total promotion gate evaluation (approaching N thresholds)
2. ADJ signal promotion gate evaluation
3. Live bullpen path-tree (requires infrastructure not yet built)

---

## Final Verdicts

| Branch | Verdict | Confidence | Key Evidence |
|--------|---------|------------|--------------|
| **A: Alt-Total Surface** | **CLOSE** | High | Curvature error real (82% stable) but hold absorbs edge. Only 1-2 of 7 books show positive ROI. N=97 games insufficient for minimum thresholds. |
| **B: Run-Line Asymmetry** | **CLOSE** | High | Market perfectly prices walk-off truncation (35.8% vs 35.9% cover rates, N=9,857). No pregame bucket significant. Season residuals flip sign. Signal B already captures xFIP mismatch optimally. |
| **Combined** | **No interaction, no build** | — | Both confirm MLB derivative markets are well-calibrated. Cross-Market Triangle is the next priority. |
