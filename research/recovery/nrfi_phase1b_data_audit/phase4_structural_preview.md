# NRFI Phase 1B — Structural Preview

## Dataset
- 5,398 games with team totals merged from canonical odds + NRFI research table
- Coverage: primarily 2024-2025 (team totals ~98% coverage those seasons)

## Key Findings

### 1. NRFI Rate by Min Team Total
The "weaker" offense side (min team total) shows modest signal:

| tt_min | N | NRFI Rate |
|--------|---|-----------|
| 2.5 | 479 | 0.524 |
| 3.5 | 3,791 | 0.523 |
| 4.5 | 1,079 | 0.472 |
| 5.5 | 44 | 0.409 |

Spread: 52.4% (low) to 40.9% (high) — 11.5pp range

### 2. NRFI Rate by Max Team Total
The "stronger" offense side (max team total) shows stronger signal:

| tt_max | N | NRFI Rate |
|--------|---|-----------|
| 3.5 | 1,248 | 0.550 |
| 4.5 | 3,451 | 0.512 |
| 5.5 | 580 | 0.441 |
| 6.5 | 92 | 0.446 |

Spread: 55.0% to 44.1% — 10.9pp range. The max team total (i.e., the
stronger offense) is the key discriminator, consistent with NRFI being
a "weakest link" problem.

### 3. NRFI Rate by TT Dispersion
Imbalance between the two team totals:

| Dispersion | N | NRFI Rate |
|------------|---|-----------|
| 0.0 | 2,003 | 0.516 |
| 1.0 | 2,623 | 0.520 |
| 2.0 | 664 | 0.477 |
| 3.0 | 102 | 0.422 |

High dispersion (one strong offense) hurts NRFI rate. Dispersion >= 2.0
drops NRFI to 47.7%.

### 4. NRFI Rate by Composite Flags

| Condition | N | NRFI Rate |
|-----------|---|-----------|
| Both below 4.0 | 1,253 | 0.550 |
| NOT both below 4.0 | 4,145 | 0.500 |
| One below 3.5 | 4,272 | 0.523 |
| NOT one below 3.5 | 1,126 | 0.469 |

**both_below_4** is the strongest binary signal: +5.0pp NRFI rate lift.

### 5. NRFI Rate by Team Total Sum

| TT Sum | N | NRFI Rate |
|--------|---|-----------|
| (5.0, 7.0] | 1,550 | 0.541 |
| (7.5, 8.0] | 2,379 | 0.520 |
| (8.5, 9.0] | 1,142 | 0.478 |
| (9.5, 12.0] | 316 | 0.427 |

Clear monotonic decline: 54.1% → 42.7% across the sum range.

### 6. NRFI Market Pricing Calibration
4,397 games with NRFI market prices (2024-2025):

| Implied Prob Range | N | Actual NRFI | Market Implied | Diff |
|-------------------|---|-------------|----------------|------|
| (0.378, 0.515] | 886 | 0.465 | 0.492 | -0.027 |
| (0.515, 0.535] | 1,008 | 0.488 | 0.529 | -0.041 |
| (0.535, 0.550] | 668 | 0.531 | 0.546 | -0.014 |
| (0.550, 0.569] | 864 | 0.530 | 0.562 | -0.031 |
| (0.569, 0.683] | 784 | 0.575 | 0.593 | -0.018 |

Market consistently OVERESTIMATES NRFI probability by 1.4-4.1pp across
all quintiles. The market is well-calibrated in rank ordering (actual
NRFI increases monotonically with implied probability) but systematically
biased toward NRFI (likely reflecting public money on NRFI).

## Implications

1. **Team total decomposition adds signal** beyond game-level totals.
   The max team total and both_below_4 flag are the strongest variables.
2. **The NRFI market is systematically biased** toward NRFI. This means
   YRFI may be the value side — consistent with a public preference for
   "nothing happens" bets.
3. **Coverage is sufficient** for 2024-2025 modeling (5,398 games with
   team totals; 4,397 with NRFI prices).
