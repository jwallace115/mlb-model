# Phase 5 — F5 Settlement Divergence with Real Closing Lines

**Date:** 2026-04-10
**Scope:** Rerun of Phase 4 F5 settlement divergence analysis using actual historical F5 closing lines instead of constant-ratio proxy.
**Data:** 4,367 games (2024-2025) with both real F5 closing lines (f5_lines_historical.parquet) and full-game closing lines (market_snapshots.parquet close_total).
**Key improvement over Phase 4:** The prior analysis used F5_proxy = closing_total x 0.5647. This analysis uses actual book-posted F5 closing totals, allowing the late-runs pricing proxy (fg_line - f5_line) to vary per game as the market intended.

---

## Phase 1 — Data Audit

| Item | Value |
|------|-------|
| f5_lines_historical rows | 6,910 (all canonical) |
| game_table rows | 9,857 |
| market_snapshots (close_total) | 4,855 |
| Three-way join (f5 x game_table x close_total) | 4,799 |
| After 9-inning filter | 4,367 |
| Season: 2024 | 2,171 |
| Season: 2025 | 2,196 |

### F5 line distribution (actual market lines)

| Metric | f5_line | fg_line | late_runs_proxy (fg - f5) |
|--------|---------|---------|---------------------------|
| Mean | 4.514 | 8.411 | 3.896 |
| Median | 4.500 | 8.500 | 4.000 |
| Std | 0.877 | 0.913 | 0.867 |
| Min | 0.5 | — | -5.0 |
| Max | 14.5 | — | 8.5 |

### Key observations vs Phase 4 proxy

| Metric | Phase 4 (proxy) | Phase 5 (real lines) |
|--------|-----------------|----------------------|
| F5/FG ratio | 0.5647 (constant) | 0.5370 mean, 0.0887 std |
| Mean late_runs_proxy | 3.656 | 3.896 |
| Correlation f5_line vs fg_line | 1.000 (by construction) | 0.5314 |

The real F5/FG ratio (0.537) is **lower** than the constant proxy (0.565), meaning real F5 lines are set lower relative to full-game totals than the proxy assumed. More importantly, the correlation between f5_line and fg_line is only 0.53 — the two markets carry substantial independent information. The constant-ratio proxy forced perfect correlation, which was a major limitation.

The late_runs_proxy (fg_line - f5_line) has a wide range (-5.0 to 8.5), reflecting game-specific market expectations for innings 6-9 scoring based on pitcher matchup, bullpen depth, and park. The proxy in Phase 4 had almost no variance since it was just 0.4353 x closing_total.

---

## Phase 2 — Late Residual Analysis

Definitions (unchanged from Phase 4, but now using real market lines):
- late_runs_proxy = fg_line - f5_line (market-implied innings 6-9 expectation)
- actual_late_runs = actual_total - actual_f5_total
- late_residual = actual_late_runs - late_runs_proxy
- f5_deviation = actual_f5_total - f5_line

**Important framing:** The late_runs_proxy is not a quoted market line for innings 6-9 or a second-half total. It is the arithmetic difference between two independently set markets (full-game total and F5 total). It serves as a proxy for market-implied late scoring but is not directly bettable.

### Overall

| Metric | Phase 4 (proxy) | Phase 5 (real lines) |
|--------|-----------------|----------------------|
| Mean late_residual | +0.214 | **-0.192** |
| Median late_residual | -0.264 | **-0.500** |
| Std | 2.972 | 3.001 |
| Skewness | +1.102 | +1.152 |

**Direction reversal.** With real lines, the mean residual flips from +0.21 to -0.19. The market-implied late-runs proxy (fg_line - f5_line) **overestimates** actual late-inning scoring by ~0.19 runs on average. This means the constant-ratio proxy in Phase 4 was underpricing late innings (ratio too low), creating the illusion of systematic excess late scoring.

### Season splits

| Season | Mean Residual | Median | Std | N |
|--------|---------------|--------|-----|---|
| 2024 | -0.204 | -0.500 | 2.892 | 2,171 |
| 2025 | -0.180 | -1.000 | 3.105 | 2,196 |

Stable across seasons. Both years show the same negative mean residual.

### By F5 State

F5 state definitions (based on actual F5 scoring vs real F5 line):
- CLOSE: |f5_deviation| < 2
- MODERATE: |f5_deviation| 2-3
- BLOWOUT: |f5_deviation| >= 4

| F5 State | N | Mean Proxy | Mean Actual | Mean Residual | Over% | Under% |
|----------|---|------------|-------------|---------------|-------|--------|
| CLOSE | 2,150 | 3.891 | 3.596 | -0.295 | 36.0% | 56.9% |
| MODERATE | 1,459 | 3.878 | 3.751 | -0.128 | 37.3% | 55.1% |
| BLOWOUT | 758 | 3.947 | 3.925 | -0.022 | 37.6% | 52.8% |

**The U-shape collapses.** In Phase 4, the proxy showed a clear U-shape where both F5 extremes produced elevated late residuals. With real lines:
- CLOSE games have the most negative residual (-0.295): late innings produce fewer runs than the market implies.
- BLOWOUT games have residual near zero (-0.022): the market roughly prices late-inning scoring correctly in extreme F5 games.
- The gradient is monotonic (CLOSE -> MODERATE -> BLOWOUT), not U-shaped.

### Season stability by state

| F5 State | 2024 | 2025 |
|----------|------|------|
| CLOSE | -0.283 (n=1,086) | -0.307 (n=1,064) |
| MODERATE | -0.114 (n=718) | -0.140 (n=741) |
| BLOWOUT | -0.146 (n=367) | +0.093 (n=391) |

CLOSE and MODERATE are stable negative across both seasons. BLOWOUT flips sign between seasons (-0.15 in 2024, +0.09 in 2025), which is consistent with noise rather than a stable structural effect.

### Fine-grained 1-run bins

| F5 Dev Bin | N | Mean Proxy | Mean Actual | Residual |
|------------|---|------------|-------------|----------|
| -4 | 126 | 3.837 | 4.127 | +0.290 |
| -3 | 342 | 3.827 | 3.915 | +0.088 |
| -2 | 472 | 3.825 | 3.754 | -0.071 |
| -1 | 571 | 3.842 | 3.508 | -0.335 |
| 0 | 607 | 3.926 | 3.549 | -0.377 |
| +1 | 525 | 3.881 | 3.709 | -0.172 |
| +2 | 448 | 3.915 | 3.650 | -0.266 |
| +3 | 365 | 3.953 | 3.745 | -0.208 |
| +4 | 280 | 3.936 | 3.532 | -0.404 |
| +5 | 192 | 3.919 | 3.823 | -0.096 |
| +6 | 160 | 4.006 | 3.675 | -0.331 |
| +7 | 86 | 3.983 | 3.872 | -0.111 |

No U-shape visible. The only positive residual bin is -4 (F5 way under line), and it is small (+0.29 on n=126). The positive extremes (+4 through +7) are all negative. The Phase 4 U-shape was an artifact of using a constant ratio that did not account for game-specific late-inning pricing.

---

## Phase 3 — Regression Analysis

### Model 1: late_residual ~ f5_state dummies (baseline = BLOWOUT)

| Feature | Coef | SE | t | p |
|---------|------|----|---|---|
| intercept | -0.022 | 0.109 | -0.21 | 0.837 |
| CLOSE | -0.273 | 0.127 | -2.15 | 0.032 * |
| MODERATE | -0.105 | 0.134 | -0.78 | 0.434 |

R-squared: 0.0013

F5 state alone explains 0.13% of late-run variance (vs 1.4% with proxy in Phase 4). CLOSE is marginally significant against BLOWOUT, but the effect is weak.

### Model 2: late_residual ~ f5_line + fg_line

| Feature | Coef | SE | t | p |
|---------|------|----|---|---|
| intercept | +0.342 | 0.407 | 0.84 | 0.402 |
| f5_line | +1.021 | 0.059 | 17.26 | <0.001 *** |
| fg_line | -0.612 | 0.057 | -10.77 | <0.001 *** |

R-squared: 0.0646

The two market lines together explain 6.5% of late-run variance — **50x more** than f5_state alone. The positive f5_line coefficient (+1.02) and negative fg_line coefficient (-0.61) indicate: higher F5 lines (controlling for fg_line) predict more actual late scoring, and higher fg_lines (controlling for f5_line) predict less late scoring than expected. This is consistent with the market slightly mispricing the F5/full-game relationship.

### Model 3: late_residual ~ f5_state + f5_line + fg_line

| Feature | Coef | SE | t | p |
|---------|------|----|---|---|
| intercept | +0.564 | 0.424 | 1.33 | 0.184 |
| CLOSE | -0.271 | 0.123 | -2.20 | 0.028 * |
| MODERATE | -0.123 | 0.130 | -0.95 | 0.344 |
| f5_line | +1.020 | 0.059 | 17.24 | <0.001 *** |
| fg_line | -0.616 | 0.057 | -10.85 | <0.001 *** |

R-squared: 0.0658

**F-test (Model 3 vs Model 2): F=2.77, p=0.063**

F5 state does **not** add statistically significant explanatory value (p=0.063) once both market lines are included. The marginal R-squared gain is 0.0012 (from 0.0646 to 0.0658). The market lines absorb almost all of the F5 state information.

### Model 4 (Quadratic): late_residual ~ f5_deviation + f5_deviation^2 + f5_line + fg_line

| Feature | Coef | SE | t | p |
|---------|------|----|---|---|
| intercept | +0.351 | 0.407 | 0.86 | 0.389 |
| f5_deviation | -0.027 | 0.018 | -1.52 | 0.129 |
| f5_deviation^2 | +0.007 | 0.003 | 2.34 | 0.019 * |
| f5_line | +1.015 | 0.059 | 17.12 | <0.001 *** |
| fg_line | -0.616 | 0.057 | -10.84 | <0.001 *** |

R-squared: 0.0658

The quadratic term is marginally significant (p=0.019) but weaker than in Phase 4 (p=0.001 with proxy). With real lines, the quadratic U-shape effect is attenuated. The coefficient (+0.007) implies that a 5-run F5 deviation adds only 0.007 x 25 = 0.18 runs of expected late scoring beyond what the market lines already predict — barely distinguishable from noise.

---

## Phase 4 — Book-Level Analysis

The historical F5 line backfill stored one canonical book per game:

| Book | N lines |
|------|---------|
| fanduel | 5,514 |
| draftkings | 1,117 |
| bovada | 141 |
| other | 138 |

Only 101 out of 6,537 unique games have lines from 2+ books. Book-level dispersion analysis (testing whether specific books systematically misprice the F5/full-game relationship) is not feasible with this data. The raw multi-book data was not stored during the historical backfill.

**Note:** This is a limitation. If one book consistently sets F5 lines too low relative to full-game totals, that would create a bettable opportunity even if the aggregate analysis shows no signal. This would require collecting multi-book F5 snapshots in 2026.

---

## Phase 5 — Actionability Test

### Late residual by F5 state

| F5 State | N | Mean Actual | Mean Proxy | Mean Resid | Median Resid | Std | Over% | Under% |
|----------|---|-------------|------------|------------|--------------|-----|-------|--------|
| CLOSE | 2,150 | 3.596 | 3.891 | -0.295 | -1.000 | 2.938 | 36.0% | 56.9% |
| MODERATE | 1,459 | 3.751 | 3.878 | -0.128 | -0.500 | 3.079 | 37.3% | 55.1% |
| BLOWOUT | 758 | 3.925 | 3.947 | -0.022 | -0.500 | 3.020 | 37.6% | 52.8% |

All three states show under% > over%, with the gap largest for CLOSE games. This is a distributional property of the market pricing, not a tradeable signal — the late_runs_proxy is not a posted market line.

### BLOWOUT monotonicity

| |f5_deviation| threshold | N | Mean Residual | Median Residual |
|--------------------------|---|---------------|-----------------|
| >= 4 | 758 | -0.022 | -0.500 |
| >= 5 | 439 | -0.075 | -0.500 |
| >= 6 | 262 | +0.013 | -0.500 |
| >= 7 | 175 | +0.051 | -0.500 |
| >= 8 | 119 | -0.050 | -0.500 |

**No monotonicity.** The mean residual oscillates around zero as the deviation threshold increases, with no clear trend. The median is stable at -0.5 throughout, confirming that even in extreme F5 states, late-inning scoring is a coin flip relative to the market-implied expectation.

### BLOWOUT direction split

| Direction | N | Mean Residual |
|-----------|---|---------------|
| F5 way OVER (dev >= +4) | 614 | -0.121 |
| F5 way UNDER (dev <= -4) | 144 | +0.396 |

The F5-under direction shows a small positive residual (+0.40) but on only 144 games. This is the mean-reversion signal from Phase 4, but it is much weaker with real lines and not statistically significant given the std of 3.0.

### Late_runs_proxy by state

| State | Mean Proxy | Std Proxy |
|-------|------------|-----------|
| CLOSE | 3.891 | 0.919 |
| MODERATE | 3.878 | 0.839 |
| BLOWOUT | 3.947 | 0.762 |

The market-implied late-runs expectation is nearly identical across F5 states (3.88 to 3.95). The market does not substantially adjust the full-game/F5 gap based on game-specific factors that correlate with extreme F5 outcomes.

---

## Phase 6 — Comparison to Phase 4 Proxy Results

| Metric | Phase 4 (constant proxy) | Phase 5 (real lines) | Change |
|--------|--------------------------|----------------------|--------|
| **N games** | 4,853 | 4,367 | -486 (9-inning filter) |
| **Mean late_residual** | +0.214 | -0.192 | **Sign reversal** |
| **Median late_residual** | -0.264 | -0.500 | More negative |
| **U-shape (quadratic p)** | 0.001 *** | 0.019 * | Weakened 19x |
| **Quadratic R-squared** | 0.0140 | 0.0658 | Higher (market lines dominate) |
| **F5_VERY_LOW residual** | +0.441 | +0.290 (bin -4 only) | Reduced, noisy |
| **F5_VERY_HIGH residual** | +0.282 | -0.121 (dev >= +4) | **Sign reversal** |
| **BLOWOUT monotonicity** | Monotonic (+0.35 to +0.47) | Flat, oscillates around 0 | **Gone** |
| **BLOWOUT season stability** | Same sign both seasons | Flips sign (2024: -0.15, 2025: +0.09) | **Unstable** |
| **F-test: state adds value over lines** | Not tested (no real lines) | p=0.063 (NO) | Market absorbs signal |

### What the proxy got wrong

The constant-ratio proxy (F5 = 0.5647 x total) created two systematic artifacts:

1. **Inflated mean residual.** The true F5/FG ratio averages 0.537, not 0.565. The proxy overestimated expected F5 scoring and underestimated expected late scoring, creating the illusion of +0.21 excess late runs that do not exist when measured against real market lines.

2. **Artificial U-shape.** By forcing the F5/FG ratio to be constant, the proxy could not account for the fact that games with extreme F5 outcomes often have game-specific reasons (elite pitcher vs poor lineup, extreme park) that the real F5 line already prices in. The real F5 line varies with the matchup, so the F5 deviation against a real line carries different information than deviation against a constant ratio.

---

## Decision

**CLOSE.**

Evidence:
- The Phase 4 U-shaped quadratic finding was **primarily a proxy artifact.** With real F5 closing lines, the quadratic term weakens from p=0.001 to p=0.019, and the practical effect size shrinks to +0.007 runs per unit deviation squared — negligible.
- The overall mean late_residual **reverses sign** from +0.21 (proxy) to -0.19 (real lines). The real market slightly overprices late-inning scoring relative to actual outcomes, the opposite of what the proxy suggested.
- **F5 state adds no significant explanatory value** once both real market lines (f5_line and fg_line) are included (F-test p=0.063). The market lines absorb almost all of the conditional information.
- **BLOWOUT residuals are not monotonic and not stable across seasons.** The BLOWOUT mean residual flips sign between 2024 (-0.15) and 2025 (+0.09).
- The F5-way-under positive residual (+0.40, n=144) is the only surviving signal fragment, but it sits on too few games and is within 0.13 standard deviations of the late_residual distribution.

The market already fully prices the conditional late-scoring dynamics that appeared as structural residuals in the proxy analysis. The two independently set markets (F5 total and full-game total) together capture the information that F5 state was proxying for.

### Recommendation

- **Do not advance** this line of research for innings 6-9 settlement divergence.
- **Do not retain** f5_deviation^2 as a candidate feature for the path-tree engine. The quadratic effect is marginal and likely reflects remaining noise from F5 line granularity (lines are set in 0.5-run increments), not a structural late-scoring phenomenon.
- The Phase 4 path-tree blowout finding (+2.95 run full-game over-bias) remains valid as a **full-game total** effect — it is driven by F5 scoring, not late-inning scoring. That signal does not require an F5 settlement divergence mechanism.
- **Book-level dispersion** remains untested due to data limitations (only 101 games with multi-book F5 lines). If multi-book F5 snapshots are collected in 2026, a targeted test of whether specific books systematically misprice F5/full-game gaps could be worthwhile, but this is a lower-priority investigation given the aggregate null result.
