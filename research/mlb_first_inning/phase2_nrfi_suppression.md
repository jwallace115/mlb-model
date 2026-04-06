# Phase 2 — NRFI Bottom-Tail Suppression Test

**Date:** 2026-04-06
**Design:** Train on 2024, test on 2025 (pure year holdout). Micro model only.

---

## Verdict: NO PRACTICAL FILTER

The bottom-tail NRFI pocket does not survive the decision criteria. The effect is real
but is almost entirely explained by obvious low-total context (park, weather, broad
pitcher quality). After residualizing those controls, the micro model's unique
contribution disappears.

---

## Bottom-Tail Buckets

### 2024 (in-sample, N=874)

| Bucket | N | NRFI rate | Base | Lift | Mkt implied | Residual | ROI@-110 |
|--------|---|-----------|------|------|-------------|----------|----------|
| Bottom 10% | 88 | 0.636 | 0.511 | 1.24x | 0.563 | +0.074 | +21.5% |
| Bottom 20% | 175 | 0.617 | 0.511 | 1.21x | 0.560 | +0.058 | +18.1% |
| Bottom 30% | 262 | 0.592 | 0.511 | 1.16x | 0.559 | +0.031 | +12.8% |

### 2025 (OOS, N=1,048)

| Bucket | N | NRFI rate | Base | Lift | Mkt implied | Residual | ROI@-110 |
|--------|---|-----------|------|------|-------------|----------|----------|
| Bottom 10% | 105 | 0.562 | 0.516 | 1.09x | 0.558 | **+0.010** | +8.3% |
| Bottom 20% | 210 | 0.533 | 0.516 | 1.03x | 0.555 | **-0.016** | +2.9% |
| Bottom 30% | 315 | 0.540 | 0.516 | 1.05x | 0.554 | **-0.011** | +3.7% |

**Both-year directional check:** Bottom 10% is directionally positive in both 2024
(+0.074 residual) and 2025 (+0.010 residual). PASSES — but the 2025 residual is
+1.0pp, essentially zero.

---

## Leakage Controls (2025 OOS)

### Does the micro model add anything beyond obvious context?

**Residualized p_yrfi** — after removing park_factor, temperature, wind, broad team
offense (OBP/SLG rolling 15), and pitcher ERA rolling 5:

| Group | N | NRFI rate | Delta vs base |
|-------|---|-----------|---------------|
| Residual bottom 10% | 105 | **0.505** | **-0.011** |
| Rest | 943 | 0.517 | — |

R² of controls on p_yrfi: 0.378

**The residual bottom 10% is WORSE than the base rate.** The micro model's entire
NRFI suppression comes from low-total context that the controls already capture.
There is no independent micro signal.

### Model vs simple low-total selection

| Method | N | NRFI rate |
|--------|---|-----------|
| Micro model bottom 10% | 105 | 0.562 |
| Simple low-total bottom 10% | 105 | 0.476 |
| Delta | — | **+0.086** |

The micro model does outperform simple low-total selection by 8.6pp. But this means
the micro model is a slightly better ranker of low-total games — it is NOT discovering
a structural NRFI pocket that the market misses. The market already prices these games
at 55.8% NRFI implied, and the actual rate is 56.2%. There is no residual edge.

---

## Concentration Checks (2025 OOS bottom 10%)

| Removal | N | NRFI rate | vs full (0.562) |
|---------|---|-----------|-----------------|
| Full bottom-10% | 105 | 0.562 | baseline |
| Remove top-5 teams | 35 | 0.571 | +0.009 (survives) |
| Remove top-5 starters | 76 | 0.592 | +0.030 (survives) |
| Remove below-median total games | 53 | **0.509** | **-0.053 (collapses)** |

The effect **collapses when you remove low-total games**. After removing games with
actual total below the bucket median (8 runs), the NRFI rate drops from 56.2% to
50.9% — indistinguishable from the base rate.

This confirms the bottom-tail pocket is **low-total leakage, not structural NRFI
suppression**.

---

## Decision Criteria Assessment

| Criterion | Result | Status |
|-----------|--------|--------|
| Directionally positive in both 2024 AND 2025 | 2024: +7.4pp, 2025: +1.0pp | **MARGINAL** — 2025 residual is ~0 |
| Residual vs market positive after controls | Residual bottom-10% NRFI = 0.505 (BELOW base) | **FAIL** |
| Concentration removal does not collapse | Collapses when low-total games removed | **FAIL** |

Two of three criteria fail. The branch does not advance.

---

## Why This Is Not a Usable NRFI Filter

The micro model's bottom tail selects games that are low-total environments (pitcher
parks, cold weather, strong starters). The market already knows this — NRFI is priced
at ~55-56% implied for these games, and the actual NRFI rate is 56.2%. The residual
of +1.0pp in 2025 OOS does not survive vig.

The top-of-order concentration features (top-3 OBP/ISO/platoon) do not add
distinguishable information beyond what broad pitcher ERA and park factor already
provide. Phase C's conclusion (platoon features flip OOS) holds in the first-inning
scope as well.

**One sentence:** The bottom-tail NRFI pocket is low-total game selection with a
micro-feature veneer — it does not identify games the market misprices.
