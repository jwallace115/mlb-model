# CS028 — Bullpen Positive State as V1 UNDER Amplifier

**Date:** 2026-03-28
**Verdict:** NEEDS_MORE_DATA (filed as SUSPECT due to extreme 2025 ROI on N=7)

## Data Limitation

V1 p_under probabilities only available from model_outputs for 2024-2025.
Threshold freeze uses 2024 (earliest available) instead of the pre-registered
2022-2023 window. This is a binding limitation — results should be interpreted
with caution.

## Component Prevalence (V1 UNDER games, N=932)

| Component | Home | Away |
|-----------|------|------|
| No CS013 deterioration | 88.1% | 84.7% |
| BP RA below baseline (r7) | 33.2% | 38.9% |
| Key relievers available | 31.1% | 33.8% |
| **All 3 positive** | **12.9%** | **13.5%** |
| **Both teams positive** | **2.0%** | |

The "both positive" requirement is extremely restrictive — only 19 of 932
V1 UNDER games (2.0%) qualify. This is far below the minimum_n=80 threshold.

## Primary Three-Way Comparison

| Group | N | Under HR | ROI | Residual | Pushes |
|-------|---|----------|-----|----------|--------|
| V1 UNDER baseline | 890 | 0.5596 | +6.8% | +0.131 | 42 |
| + Both BP positive | 18 | 0.4444 | -15.2% | +1.395 | 1 |
| + Not both positive | 872 | 0.5619 | +7.3% | +0.105 | 41 |

**The amplified group performs WORSE than baseline** (44.4% vs 56.0%).
This is the opposite of the hypothesis.

## Season Breakdown (Both BP Positive)

| Year | N | Under HR | ROI |
|------|---|----------|-----|
| 2024 | 11 | 0.1818 | -65.3% |
| 2025 | 7 | 0.8571 | +63.6% |

Extreme reversal pattern — 2/11 in 2024, 6/7 in 2025. This is pure noise
on tiny samples, not a real signal.

## Permutation Test (Parent-Scoped)

- **Observed hit rate:** 0.4444
- **Permutation mean:** 0.5572
- **Percentile:** 11.0 (signal goes wrong direction)
- **Parent-scoped:** Yes (shuffled within V1 UNDER games only)

The permutation test correctly uses parent_mask. The 11th percentile
means the "amplified" group performs WORSE than random subsets of
V1 UNDER games.

## Secondary Variants (N + HR only)

| Variant | N | Under HR |
|---------|---|----------|
| Home BP positive only | 118 | 0.5339 |
| Away BP positive only | 123 | 0.5528 |
| Either BP positive | 223 | 0.5516 |

Single-team positive state shows near-baseline performance.
No amplification effect in any variant.

## Redundancy Check

S12 and P09 overlay flags are runtime-only (not stored in historical data).
Overlap cannot be computed directly. Filed as OVERLAP_UNKNOWN.

## Verdict: SUSPECT / NEEDS_MORE_DATA

Filed as SUSPECT due to extreme 2025 ROI (+63.6%) on N=7, but the
underlying reality is NEEDS_MORE_DATA:

- **N=18** at the primary threshold (below minimum_n=80 by 4x)
- **2.0% flag rate** is too restrictive to be actionable
- **Wrong direction** in the primary test (44.4% vs 56.0% baseline)
- **Permutation 11th percentile** — signal goes OVER, not UNDER
- The three-component conjunction is too rare to test reliably

## Recommendation

**Archive.** The bullpen positive state concept as defined (all three
components on both teams) is too restrictive to produce a testable signal.
The 2.0% flag rate means fewer than 20 games per season qualify.

If revisited, consider:
- Relaxing to "either team positive" (N=223, HR=0.5516) — but this shows
  no amplification vs baseline (55.2% vs 56.0%)
- Dropping the key-reliever-availability component (hardest to measure,
  lowest standalone signal)
- Using a continuous score rather than all-or-nothing conjunction
