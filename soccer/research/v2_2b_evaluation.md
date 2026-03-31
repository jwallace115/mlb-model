# V2.2b Challenger Calibration Evaluation

**Date:** 2026-03-28
**Approach:** Replace isotonic calibration (V2.2) with Platt scaling + league-specific intercept offsets.
**Fit on:** VALIDATE (2023-24, N=1372) | **Evaluated on:** OOS (2024-25, N=1372)
**Active leagues:** EPL, BUN, SEA, LG1

---

## Platt Calibrator

- **Slope:** 0.8640
- **Intercept:** 0.0839

### League Offsets (fit on validate)

| League | Offset |
|--------|--------|
| EPL | +0.0233 |
| BUN | -0.0144 |
| SEA | +0.0052 |
| LG1 | -0.0209 |

---

## Diagnostic 1: Calibration Curve (OOS)

| Bucket | N | Avg Pred | Actual | Gap (pp) |
|--------|---|----------|--------|----------|
| <0.40 | 21 | 0.3725 | 0.1429 | -23.0 |
| 0.40-0.45 | 82 | 0.4312 | 0.3415 | -9.0 |
| 0.45-0.50 | 160 | 0.4767 | 0.4375 | -3.9 |
| 0.50-0.55 | 244 | 0.5257 | 0.4754 | -5.0 |
| 0.55-0.60 | 249 | 0.5758 | 0.5382 | -3.8 |
| 0.60-0.65 | 235 | 0.6236 | 0.6213 | -0.2 |
| 0.65+ | 381 | 0.7108 | 0.6667 | -4.4 |

- **Calibration slope (OOS):** 0.99 (V2.2: 0.64)
- **Overall bias:** -4.2pp (V2.2: -3.8pp)
- **Brier score:** 0.2391 (V2.2: 0.2393)

**Key finding:** Calibration slope dramatically improved (0.64 to 0.99), meaning probabilities are now well-scaled. However, overall bias worsened slightly (-3.8 to -4.2pp), indicating the model consistently overpredicts overs.

---

## Diagnostic 2: Edge Calibration (OOS)

| Bucket | N | Avg Edge | Actual O2.5 | Avg Mkt Err |
|--------|---|----------|-------------|-------------|
| <=0.06 | 16 | -0.0889 | 0.6250 | -0.0884 |
| -0.06 to -0.03 | 19 | -0.0403 | 0.6842 | +0.0442 |
| -0.03 to 0.00 | 124 | -0.0131 | 0.5081 | -0.0766 |
| 0.00 to 0.03 | 436 | +0.0173 | 0.5482 | +0.0013 |
| 0.03 to 0.06 | 436 | +0.0434 | 0.5298 | +0.0045 |
| 0.06 to 0.10 | 234 | +0.0756 | 0.5513 | +0.0010 |
| 0.10+ | 107 | +0.1333 | 0.6168 | +0.0419 |

- **Spearman (bucket rank vs avg market error):** 0.357 (p=0.432)

The signal exists in the right direction (higher edge buckets show slightly higher market error) but is noisy and not statistically significant.

---

## Diagnostic 3: Closing Line Test (OOS)

### Overall
| Segment | N | Hit% | ROI@actual | ROI@-110 |
|---------|---|------|-----------|----------|
| All Active | 357 | 56.3% | -2.9% | +7.5% |

### By Tier
| Tier | N | Hit% | ROI@actual | ROI@-110 |
|------|---|------|-----------|----------|
| LOW (0.06-0.08) | 160 | 55.0% | -5.4% | +5.0% |
| MEDIUM (0.08-0.10) | 85 | 54.1% | -3.7% | +3.3% |
| HIGH (0.10+) | 112 | 59.8% | +1.4% | +14.2% |

### By League
| League | N | Hit% | ROI@actual |
|--------|---|------|-----------|
| BUN | 51 | 56.9% | +7.1% |
| EPL | 220 | 58.6% | -2.0% |
| LG1 | 63 | 58.7% | +1.8% |
| SEA | 23 | 26.1% | -46.4% |

### Special Combos
| Segment | N | ROI@actual |
|---------|---|-----------|
| MEDIUM-only | 85 | -3.7% |
| BUN+MEDIUM | 11 | -2.9% |

**Key finding:** ROI at -110 is strongly positive (+7.5% overall), indicating the model finds real value. However, the odds available in the market are too thin to capture that edge (ROI@actual = -2.9%). SEA collapsed completely (N=23, -46.4%).

---

## Diagnostic 4: Edge Overstatement (OOS)

OVER bets only (N=341):
- **Mean claimed edge:** 0.0937
- **Mean actual edge:** 0.0139
- **Overstatement ratio: 6.8x** (V2.2: 4.4x)

This is **worse** than V2.2. The Platt calibrator produces well-scaled probabilities overall, but the claimed edges on actionable bets are far larger than realized.

---

## Comparison Table

| Metric | V2.2 | V2.2b | Delta |
|--------|------|-------|-------|
| Calibration slope | 0.64 | 0.99 | +0.35 |
| Overall bias (pp) | -3.8 | -4.2 | -0.4 |
| Brier score | 0.2393 | 0.2391 | -0.0002 |
| BUN ROI @ actual | +7.5% | +7.1% | -0.4pp |
| EPL ROI @ actual | -4.9% | -2.0% | +2.9pp |
| LG1 ROI @ actual | -3.0% | +1.8% | +4.8pp |
| SEA ROI @ actual | -9.2% | -46.4% | -37.2pp |
| Overall ROI @ actual | -1.3% | -2.9% | -1.6pp |
| MEDIUM-only ROI @ actual | +10.1% | -3.7% | -13.8pp |
| Edge overstatement | 4.4x | 6.8x | +2.4x |

---

## Decision Gate

| Gate | Criterion | Result | Value |
|------|-----------|--------|-------|
| 1 | Calibration slope >= 0.85 | **PASS** | 0.99 |
| 2 | Overall bias < 1.5pp | **FAIL** | 4.2pp |
| 3 | Edge overstatement < 2x | **FAIL** | 6.8x |
| 4a | Overall ROI >= 0% | **FAIL** | -2.9% |
| 4b | BUN+ & EPL narrows >= 3pp | **FAIL** | BUN +7.1%, EPL delta +3.0pp (needs both + 3pp, got 2.9pp) |

### VERDICT: KEEP V2.2

---

## Summary

V2.2b successfully fixes the calibration slope (0.64 to 0.99), which was the primary motivation. However, it fails on three of four gates:

1. **Bias worsened** slightly (-3.8 to -4.2pp) -- the model still overpredicts overs.
2. **Edge overstatement increased** from 4.4x to 6.8x -- Platt scaling spreads probabilities more, creating larger claimed edges that are not realized.
3. **MEDIUM tier collapsed** from +10.1% to -3.7% -- the sweet spot that V2.2 found in the middle edge range does not survive recalibration.
4. **SEA catastrophe** (-46.4%) on tiny sample (N=23) drags overall results.

The calibration slope improvement is real and valuable, but the net effect on betting performance is negative. The isotonic calibrator in V2.2, despite its poor slope, effectively compressed probabilities in a way that happened to produce better-sized edges. Platt scaling is more principled but produces overconfident tails.

**Next steps to consider:**
- Explore Platt scaling with regularization (lower C) to reduce edge overstatement
- League-specific Platt fits (especially to fix SEA)
- Hybrid: use Platt for calibration slope but isotonic for edge sizing
- Drop SEA from active leagues (N too small, consistently negative)
