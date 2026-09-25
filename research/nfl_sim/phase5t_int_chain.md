# Phase 5T Item 1 — INT chain decomposition

Date: 2026-09-25. Runtime: 128s. 200 K1 games, N=100, drive_log=True.
Engine fingerprint `2b9666346a810f9f` (changed from `06caa0cbb12bbe6e` because engine.py
was edited for the log instrumentation; the change is drive_log-gated and does not affect
simulation outcomes).

## Pre-registered predictions (written before looking)

1. Sim ez share < 8% AND that cell explains >= 1.5 of the gap.
2. Sim LOS mean within 2 of real.
3. NULL: returns and air match real within 1 yard at the mean.

## Results

### Three-cell decomposition (excl-six unless noted)

| cell | real share | real next_start | sim share | sim next_start |
|------|-----------|-----------------|-----------|----------------|
| six | 9.7% | 73.7 | 9.2% | nan (kickoff) |
| ez (catch in EZ) | 10.1% | 79.9 | 6.6% | 80.0 |
| other | 80.2% | 50.9 | 84.2% | 48.1 |
| overall (excl six) | 90.3% | 54.2 | 90.8% | 50.4 |

Gap: sim 50.4 vs real 54.2 = -3.8 (was -3.3 in D144 before the stale-yl fix; now correct).

### LOS, air, return distributions

| metric | real mean | sim mean | diff |
|--------|----------|---------|------|
| LOS | 52.8 | 53.5 | +0.7 |
| Air yards | 15.8 | 14.6 | -1.2 |
| Return yards | 12.7 | 11.0 | -1.7 |

### Pre-registered evaluation

**Prediction (1): PARTIALLY HELD / FAILED.** Sim ez share 6.6% < 8% (first part HELD). Impact
of the ez deficit: 3.5pp fewer ez events × (80.0 - 48.1) = 1.12 yards, scaled to non-six pool
= 1.23 yards of the 3.8 gap. Below the 1.5 threshold (second part FAILED).

**Prediction (2): HELD.** LOS mean 53.5 vs 52.8 = diff 0.7 (within 2).

**Prediction (3) NULL: FAILED.** Air -1.2, return -1.7 (both outside 1.0). The air deficit comes
from the LOS-bucket quantile draw: the table's integer-clipped percentiles undercount extreme
depths (real end-zone throws at LOS 75+ draw air 25+, but the table's 81-99 bucket median is 17).
The return deficit is partly compositional: the sim has fewer ez (touchback = 0 return) and more
"other" where the return is conditional on the catch location, and the return table was built from
the unconditional distribution.

## Diagnosis — where the 3.8 yards sit

The gap decomposes into two sources:

1. **Missing end-zone catches (ez 6.6% vs 10.1%): ~1.2 yards.** The sim's LOS-bucket quantile
   draw for air_yards doesn't produce enough end-zone-reaching throws. Real QBs throw INTO the
   end zone on ~10% of intercepted passes; the sim's marginal air draw only produces catch_yl <= 0
   on ~7%. The fix is to condition the air draw on the play's actual pass depth (the engine already
   draws depth for completion/incompletion outcomes) or add an explicit end-zone probability by
   LOS bucket.

2. **"Other" cell (48.1 vs 50.9): ~2.6 yards.** The non-end-zone catches start 2.8 yards closer
   in the sim. This is partly the air-yard deficit (-1.2 at the mean, compressing the catch point)
   and partly the return-yard deficit (-1.7 at the mean, returning less). The return deficit is
   itself partly compositional: fewer ez events mean more events in the return pool, and the
   return quantiles are unconditional (not conditioned on catch location).

Both sources share the same root: the INT-spot table draws air_yards from a flat quantile per LOS
bucket, independent of the pass depth the engine already chose. Conditioning on pass depth would
fix both (deeper throws produce more end-zone catches AND more realistic catch locations).

## NOT DONE
- The pass-depth-conditioned air draw (the fix for prediction 1).
- Cowork's reproduction of the three-cell numbers from the parquet.

## UNVERIFIED
- Whether the return quantile unconditional bias is the full explanation for the -1.7 return gap.
