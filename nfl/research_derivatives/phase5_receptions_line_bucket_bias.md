# NFL Receptions Line-Bucket Structural Bias Test — Phase 5

**Date:** 2026-04-06
**Data:** 3 NFL seasons (2023-2025), 9,466 matched player-game-weeks, 855 games

---

## Verdict: CLOSE THIS BRANCH

The low-line reception over-bias from the Phase 3 single-season audit does not
hold across the full 3-season dataset. The only surviving cell (TE / LOW) has a
residual of +2.7pp but is decaying rapidly across seasons and does not clear the
+3pp threshold. The broad market is well-calibrated to slightly under-lean on
receptions across all line buckets.

---

## Step 2 — Raw Hit Rate by Bucket (3 seasons)

| Bucket | N | Mean Line | Over% | Implied% | Residual |
|--------|---|-----------|-------|----------|----------|
| LOW (0.5-2.5) | 5,345 | 1.9 | .500 | .523 | **-2.4pp** |
| MID (3.0-4.5) | 3,136 | 3.9 | .458 | .510 | **-5.2pp** |
| HIGH (5.0+) | 985 | 6.0 | .444 | .512 | **-6.8pp** |

**The original Phase 3 finding is reversed.** With 3 seasons of data, ALL buckets
show the market overprices OVER — the actual over rate is below implied across
the board. The single-season 2025 result that showed 51.2% over at low lines was
a one-year artifact.

### By Season

| Season | LOW over% | LOW resid | MID resid | HIGH resid |
|--------|-----------|-----------|-----------|------------|
| 2023 | .532 | **+0.1pp** | -3.2pp | -7.1pp |
| 2024 | .487 | -3.7pp | -6.2pp | -4.8pp |
| 2025 | .484 | -3.2pp | -6.5pp | -8.6pp |

The low-line "over bias" was a 2023-specific effect (+0.1pp, essentially flat)
that disappeared in 2024 and 2025. It was never a structural bias — it was noise.

---

## Step 3 — Role x Bucket Interaction

| Role | Bucket | N | Over% | Impl% | Residual |
|------|--------|---|-------|-------|----------|
| **TE** | **LOW** | **1,175** | **.555** | **.528** | **+2.7pp** |
| WR3 | LOW | 1,094 | .484 | .511 | -2.6pp |
| RB | LOW | 1,909 | .484 | .526 | -4.2pp |
| WR2 | LOW | 737 | .467 | .523 | -5.7pp |
| WR1 | MID | 894 | .475 | .522 | -4.7pp |
| TE | MID | 830 | .466 | .510 | -4.4pp |
| WR2 | MID | 829 | .445 | .509 | -6.4pp |

**Only one cell shows positive residual:** TE / LOW (0.5-2.5) at +2.7pp. All
other role x bucket combinations have negative residuals (market overprices OVER).

---

## Step 4-5 — Market Calibration and Controls

**TE / LOW cell:**
- Present across all 11 bookmakers (not a single-book artifact)
- Logistic regression coefficient for `in_cell` = +0.20 (positive, survives
  controls for line value and implied probability)

---

## Step 6 — Concentration Check

**TE / LOW** is well-distributed:
- Top 3 players contribute only 11% of observations
- After removing top 3 players: over rate stays at .556 (unchanged from .555)
- 32 teams contribute, no team > 6% of sample
- Not concentrated

---

## Step 7 — Season Stability (the critical test)

| Season | N | Over% | Implied% | Residual |
|--------|---|-------|----------|----------|
| 2023 | 360 | .603 | .538 | **+6.5pp** |
| 2024 | 376 | .540 | .522 | +1.8pp |
| 2025 | 439 | .528 | .525 | **+0.3pp** |

**The TE / LOW effect is decaying rapidly.** It was +6.5pp in 2023, shrank to
+1.8pp in 2024, and is essentially zero (+0.3pp) in 2025. This is a classic
market-learning pattern: the bias existed, the market corrected for it, and it
is now gone.

---

## Decision Criteria Assessment

| Criterion | Result | Status |
|-----------|--------|--------|
| Residual > 3pp | +2.7pp overall (pooled) | **FAIL** (below threshold) |
| Survives controls | Yes (+0.20 coefficient) | PASS |
| Consistent across 2+ seasons | 2023 YES, 2024 marginal, 2025 NO | **FAIL** |
| N >= 50 | 1,175 | PASS |
| Not concentrated | Top 3 = 11% | PASS |

Two of five criteria fail. The residual is below +3pp and is not consistent
across seasons — it is actively decaying to zero.

---

## Why This Branch Failed

1. **The 2023 TE low-line over-bias was real** — TEs with 0.5-2.5 reception
   lines hit OVER at 60.3% in 2023, well above the 53.8% implied. This was
   likely driven by the market underpricing checkdown/short-route TE usage
   in early game scripts.

2. **The market corrected.** By 2024-2025, bookmakers adjusted TE low-line
   props. The 2025 residual of +0.3pp is indistinguishable from noise.

3. **The broader pattern is UNDER-lean.** Across all roles and buckets,
   receptions props hit OVER less than the market implies. The structural
   bias in NFL receptions is that markets slightly overprice OVER across the
   board, not that specific buckets are underpriced.

---

## Implications for NFL Derivatives Program

The reception props line-bucket approach is exhausted. No role x bucket
combination shows a stable, market-beating bias across 3 seasons.

**Remaining options:**
1. **Multi-season WR1 absence test** — now feasible with 855 games but requires
   clean ID crosswalk between injury reports and props
2. **Receiving yards** — different market structure, may have different
   bias patterns than receptions
3. **Game-script interaction** — test whether receptions props are mispriced
   specifically in games where the script favors passing (trailing teams)
4. **Pause NFL props** — wait for 2026 season forward collection to test
   opener→close movement patterns (the 2023-2024 archive only has closing
   snapshots, limiting time-series analysis)

The NFL props research program should be queued behind more promising
work in other sports unless a specific new hypothesis emerges.
