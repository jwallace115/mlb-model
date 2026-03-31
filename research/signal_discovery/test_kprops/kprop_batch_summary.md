# K Prop Signal Tests — Batch Summary

**Date:** 2026-03-28
**Signals tested:** KP01, KP02, KP03A, KP03B

## Market Baseline Efficiency

| Metric | Value |
|--------|-------|
| Total starts | 8,653 |
| Over hit rate | 48.67% |
| Under hit rate | 51.33% |
| Push rate | 0.00% (half-integer lines) |
| Over ROI (all starts) | **-7.39%** |
| Under ROI (all starts) | **-4.47%** |
| Mean k_line | 4.95 |
| Mean actual_k | 4.98 |

Market is efficient — neither side is exploitable at baseline. Under side
has smaller vig loss (-4.5% vs -7.4%) suggesting books shade K lines
slightly toward the over.

## Result Table

| Signal | N (2023 freeze) | Hit Rate | ROI | Perm %ile | 2025 ROI | Verdict |
|--------|-----------------|----------|-----|-----------|----------|---------|
| KP01 | 449 | 52.8% (2023) | -6.63% | 70.8 | -8.8% | FAIL |
| KP02 | 338 | 53.6% (2023) | -4.65% | 89.0 | -7.3% | FAIL |
| KP03A | 72 | 37.5% (2023) | -26.38% | 0.2 | -15.5% | FAIL |
| KP03B | 49 | 53.1% (2023) | +0.25% | 74.0 | -0.7% | NEEDS_MORE_DATA |

**0 passed, 0 near-misses, 3 failed, 1 needs more data.**

## Signal Details

### KP01 — Opponent-adjusted K upshift (FAIL)

Frozen threshold: adj_k_upshift >= 0.0467 (P80, 2023). Shows promising
2023 hit rate (52.8%, ROI +0.2%) but collapses in 2024 (-10.7%) and
2025 (-8.8%). Permutation 70.8th — the upshift signal has some
signal-vs-noise separation but not enough to overcome the vig.

### KP02 — K upshift + stable leash (FAIL)

Adds IP >= 5.0 requirement to KP01. Permutation reaches **89.0th** —
passes the permutation gate. But 2025 ROI is -7.3%, failing the
binding OOS validation. The pattern is classic: in-sample (2023 +1.6%)
works, OOS collapses. The leash filter narrows the population (75.8%
of KP01 flags) but doesn't improve OOS performance.

**KP01/KP02 redundancy:** 100% by construction (all KP02 flags are
KP01 flags). 75.8% of KP01 flags also qualify for KP02.

### KP03A — Loose umpire zone x K OVER (FAIL)

**Conclusive wrong direction.** Permutation 0.2nd percentile — loose
zone games have dramatically FEWER Ks, not more. Hit rate 37.5% (2023),
33.9% (2024), 44.6% (2025). The hypothesis that "loose zone increases
K opportunities" is empirically false. Loose zones produce more walks
and contact, fewer strikeouts.

### KP03B — Tight umpire zone x K UNDER (NEEDS_MORE_DATA)

N=49 in freeze window (just under threshold of 50). Directionally
correct: 53.1% under rate in 2023, 53.7% in 2024, 55.0% in 2025.
ROI near breakeven (+0.25% combined). Permutation 74th — close to
near-miss territory. The mechanism (tight zone → faster counts →
fewer Ks) has mild support but the sample is too thin to confirm.

## Domain Findings

1. **Adj K upshift domain:** The opponent-adjusted K rate form signal
   shows some in-sample signal (perm 71-89th) but collapses OOS.
   The K prop market prices pitcher K form efficiently enough that
   the vig absorbs any edge from adj_k tracking.

2. **Umpire zone x K prop domain:** Loose zone is conclusively wrong
   direction for K OVER. Tight zone shows weak directional support
   for K UNDER but insufficient sample. This domain is mostly closed.

3. **Overall K prop efficiency:** The -7.4% over / -4.5% under
   baseline ROI leaves very little room for signal alpha after vig.
   Any signal needs to produce >7pp ROI lift to break even on the
   over side, or >4.5pp on under. None of the tested signals achieve this.

## Recommended Next Steps

- **KP01:** Archive. Adj K upshift doesn't survive OOS.
- **KP02:** Archive. Permutation passes but 2025 binding fails.
- **KP03A:** Archive. Wrong direction — conclusive fail.
- **KP03B:** Monitor if dataset grows. Could revisit if tight zone
  sample reaches N=80+ with continued directional support. Do not
  promote on current evidence.
