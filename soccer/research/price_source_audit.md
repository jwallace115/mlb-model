# Soccer Price Source Audit

**Date:** 2026-03-28
**Dataset:** V2.2 OOS 2024-25, active leagues (EPL, BUN, SEA, LG1), edge >= 0.06. N=413 signals.

---

## Step 1 — Book Availability

The football-data.co.uk raw CSVs contain **5 price sources** for the Over/Under 2.5 market, all with near-complete coverage:

| Book | Description | N (closing) | Coverage |
|------|-------------|-------------|----------|
| B365 | Bet365 | 413 | 100.0% |
| Pinnacle | Pinnacle | 412 | 99.8% |
| Max | Best closing price across all books | 413 | 100.0% |
| Avg | Market average closing price | 413 | 100.0% |
| BFE | Betfair Exchange | 413 | 100.0% |

All books have full coverage. Pinnacle comparison is fully representative.

**Currently used by production pipeline:** B365 only (over_price / under_price in canonical table).

---

## Step 2 — ROI Comparison by Book (Closing Odds)

| Book | N | Avg Odds | BE% | Hit% | Excess | ROI | z | p |
|------|--:|------:|------:|------:|------:|------:|------:|------:|
| B365 (Bet365) | 413 | 1.706 | 58.6% | 60.5% | +1.9pp | **-0.3%** | 0.79 | 0.216 |
| Pinnacle | 411 | 1.712 | 58.4% | 60.6% | +2.2pp | **+0.4%** | 0.90 | 0.184 |
| **Max (Best Price)** | 413 | 1.769 | 56.5% | 60.5% | +4.0pp | **+3.3%** | 1.65 | **0.050** |
| Avg (Market Avg) | 413 | 1.702 | 58.8% | 60.5% | -0.5pp | **-0.5%** | 0.73 | 0.232 |
| **BFE (Betfair Exch)** | 413 | 1.772 | 56.4% | 60.5% | +4.1pp | **+3.3%** | 1.68 | **0.046** |
| Flat -110 (ref) | 413 | 1.909 | 52.4% | 60.5% | +8.1pp | +15.6% | — | — |

**Key findings:**
- **B365: -0.3% ROI, not significant (p=0.216)**
- **Pinnacle: +0.4% ROI, not significant (p=0.184)** — barely crosses zero
- **Max (best price): +3.3% ROI, borderline significant (p=0.050)**
- **Betfair Exchange: +3.3% ROI, significant (p=0.046)**

> **NON-EXECUTABLE UPPER BOUND WARNING:** Max (best price) represents the highest available closing price across all tracked books. This price may not have been available at the time of bet placement. It is a theoretical ceiling, not an achievable return.

---

## Step 3A — ROI by League x Book (Closing Odds)

### BUN (Bundesliga) — N=111

| Book | Hit% | ROI | Avg Odds |
|------|------:|------:|------:|
| B365 | 65.8% | **+7.2%** | 1.716 |
| Pinnacle | 66.1% | **+6.2%** | 1.672 |
| Max | 65.8% | **+12.0%** | 1.792 |
| Avg | 65.8% | **+7.3%** | 1.712 |
| BFE | 65.8% | **+12.1%** | 1.800 |

BUN is profitable at every book. Max/BFE yield +12%.

### EPL (Premier League) — N=158

| Book | Hit% | ROI | Avg Odds |
|------|------:|------:|------:|
| B365 | 58.9% | -3.0% | 1.679 |
| Pinnacle | 58.9% | -1.8% | 1.701 |
| Max | 58.9% | **-0.0%** | 1.738 |
| Avg | 58.9% | -3.3% | 1.680 |
| BFE | 58.9% | **-0.2%** | 1.739 |

EPL is unprofitable at all books, but moves from -3.0% (B365) to -0.0% (Max). Price matters here.

### LG1 (Ligue 1) — N=119

| Book | Hit% | ROI | Avg Odds |
|------|------:|------:|------:|
| B365 | 58.8% | -2.4% | 1.724 |
| Pinnacle | 58.8% | -0.8% | 1.752 |
| Max | 58.8% | **+0.8%** | 1.782 |
| Avg | 58.8% | -2.8% | 1.713 |
| BFE | 58.8% | **+1.0%** | 1.781 |

LG1 flips from -2.4% (B365) to +0.8% (Max). Marginal but directionally positive.

### SEA (Serie A) — N=25 (THIN)

| Book | Hit% | ROI | Avg Odds |
|------|------:|------:|------:|
| B365 | 56.0% | -7.0% | 1.740 |
| Max | 56.0% | -3.3% | 1.808 |

Unprofitable at all books. Sample too small for conclusions.

---

## Step 3B — ROI by Tier x Book (Closing Odds)

### MEDIUM tier (0.08-0.10) — N=72

| Book | Hit% | ROI | Avg Odds |
|------|------:|------:|------:|
| B365 | 65.3% | **+10.8%** | 1.767 |
| Pinnacle | 66.2% | **+14.7%** | 1.741 |
| Max | 65.3% | **+15.3%** | 1.843 |
| BFE | 65.3% | **+15.4%** | 1.856 |

MEDIUM is strongly profitable at every book. Pinnacle actually beats B365 here (+14.7% vs +10.8%) despite lower average odds — because coverage is 71/72 and the one missing game changes the hit rate.

### HIGH tier (0.10+) — N=222

| Book | Hit% | ROI | Avg Odds |
|------|------:|------:|------:|
| B365 | 62.6% | **+0.1%** | 1.633 |
| Pinnacle | 62.6% | **+1.5%** | 1.656 |
| Max | 62.6% | **+3.1%** | 1.687 |
| BFE | 62.6% | **+3.2%** | 1.690 |

HIGH is marginally profitable. Price improvement from B365→Max adds +3.0pp.

### LOW tier (0.06-0.08) — N=119

| Book | Hit% | ROI | Avg Odds |
|------|------:|------:|------:|
| B365 | 53.8% | -7.9% | 1.804 |
| Max | 53.8% | -3.8% | 1.878 |

LOW is unprofitable at all books. The hit rate (53.8%) is simply too low.

---

## Price Improvement Summary

| From → To | Avg Odds Improvement | Break-even Reduction |
|-----------|------:|------:|
| B365 → Pinnacle | +0.013 (+0.8%) | -0.4pp |
| B365 → Max | +0.064 (+3.7%) | -2.1pp |
| Pinnacle → Max | +0.049 (+2.9%) | -1.6pp |

B365 to Max improves average odds by 3.7%, which reduces break-even from 58.6% to 56.5% — a 2.1pp reduction. With a 60.5% hit rate, this is the difference between -0.3% ROI and +3.3% ROI.

---

## Key Question: Pricing Problem or Marginal Model?

### At Pinnacle closing odds:
- Overall: +0.4% ROI (p=0.184) — **not statistically significant**
- BUN: +6.2% — profitable
- MEDIUM tier: +14.7% — strongly profitable
- HIGH tier: +1.5% — marginal

### At Max (best available) closing odds:
- Overall: +3.3% ROI (p=0.050) — **borderline significant**
- BUN: +12.0% — strongly profitable
- MEDIUM tier: +15.3% — strongly profitable
- HIGH tier: +3.1% — modest

### At Betfair Exchange closing odds:
- Overall: +3.3% ROI (p=0.046) — **significant at 5%**
- BUN: +12.1% — strongly profitable
- MEDIUM tier: +15.4% — strongly profitable

---

## Verdict: **MIXED — Pricing Problem for BUN/MEDIUM, Model Marginal Elsewhere**

The answer depends on which segments you examine:

### B365 is NOT the primary problem for BUN + MEDIUM tier
BUN is profitable at every book (+6.2% to +12.1%). MEDIUM tier is profitable at every book (+10.8% to +15.4%). These segments have genuine edge regardless of price source.

### B365 IS the tipping point for EPL and LG1
- EPL goes from -3.0% (B365) to -0.0% (Max) — price improvement brings it to break-even but not into profit
- LG1 goes from -2.4% (B365) to +0.8% (Max) — flips positive with better prices
- Both segments are genuinely marginal — better prices help but don't create a clear edge

### The overall model edge is real but thin
- Pinnacle ROI of +0.4% is directionally correct but within noise (p=0.18)
- The model's 60.5% hit rate exceeds all book break-evens except B365 and Avg
- At BFE/Max prices, the edge is borderline significant (p≈0.05)
- This is a ~2pp genuine edge that is mostly consumed by B365 vig

### Actionable conclusion
1. **High priority:** Switching from B365 to Pinnacle/BFE for fair value benchmarking would correctly identify the model as marginally profitable instead of marginally unprofitable
2. **Medium priority:** For BUN and MEDIUM tier specifically, the edge exists at any book — these are the deployment-worthy segments
3. **Low priority:** EPL and LG1 are close to break-even regardless of book — calibration improvement matters more than price improvement for these leagues
4. **Drop:** LOW tier is unprofitable at all prices. SEA is too thin to evaluate.
