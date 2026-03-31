# V3 Phase 2 — Actual-Lineup Ceiling Test Report

Dataset: 4855 games (2024-2025 with closing lines)
Non-push: 4666

## Q1: Do lineup features differ from team baselines?

| Family | Side | Correlation | Mean Diff | p90 Diff |
|--------|------|------------|-----------|----------|
| contact_rate_last20 | home | 0.6099 | 0.01734 | 0.03677 |
| contact_rate_last20 | away | 0.6084 | 0.01754 | 0.03671 |
| k_rate_last20 | home | 0.7764 | 0.03277 | 0.05742 |
| k_rate_last20 | away | 0.7809 | 0.03259 | 0.05780 |
| bb_rate_last20 | home | 0.6880 | 0.01640 | 0.03161 |
| bb_rate_last20 | away | 0.6896 | 0.01651 | 0.03164 |
| iso_last20 | home | 0.7118 | 0.01855 | 0.03940 |
| iso_last20 | away | 0.7063 | 0.01898 | 0.04074 |

Average correlation: 0.6964
**Substantial differentiation** (r < 0.75). Lineups carry meaningful unique information.

## Q2: Do lineup features add signal beyond team?

| Family | Side | Team R² | Lineup R² | Both R² | Lineup p (combined) | Verdict |
|--------|------|---------|-----------|---------|--------------------|---------| 
| contact_rate_last20 | home | 0.000589 | 0.004979 | 0.012191 | 0.0000 | **ADDS_VALUE** |
| contact_rate_last20 | away | 0.000039 | 0.003666 | 0.006619 | 0.0000 | **ADDS_VALUE** |
| k_rate_last20 | home | 0.000161 | 0.000643 | 0.003280 | 0.0001 | **ADDS_VALUE** |
| k_rate_last20 | away | 0.000139 | 0.000004 | 0.000459 | 0.2133 | **WEAK** |
| bb_rate_last20 | home | 0.000056 | 0.000999 | 0.002620 | 0.0004 | **ADDS_VALUE** |
| bb_rate_last20 | away | 0.000193 | 0.001039 | 0.003524 | 0.0001 | **ADDS_VALUE** |
| iso_last20 | home | 0.001881 | 0.000694 | 0.008513 | 0.0000 | **ADDS_VALUE** |
| iso_last20 | away | 0.001351 | 0.000985 | 0.007913 | 0.0000 | **ADDS_VALUE** |

ADDS_VALUE: 7/8, WEAK: 1, REDUNDANT: 0

## Q3: Which lineup metrics matter most?

- home contact_rate_last20: lineup_p=0.0000 (ADDS_VALUE)
- home iso_last20: lineup_p=0.0000 (ADDS_VALUE)
- away contact_rate_last20: lineup_p=0.0000 (ADDS_VALUE)
- away iso_last20: lineup_p=0.0000 (ADDS_VALUE)
- away bb_rate_last20: lineup_p=0.0001 (ADDS_VALUE)

## Q4: Structural features useful?

| Feature | Standalone p | Incremental p |
|---------|-------------|--------------|
| home_top4_iso_last20 | 0.2076 | 0.0000 |
| home_bottom3_k_rate_last20 | 0.1438 | 0.0090 |
| away_top4_iso_last20 | 0.0666 | 0.0000 |
| away_bottom3_k_rate_last20 | 0.9755 | 0.4749 |

## Tail Tests (top results)

| Feature | Bucket | N | Over% | ROI Over | 2024 | 2025 |
|---------|--------|---|-------|----------|------|------|
| home_lineup_iso_last20 | bot_20 | 934 | 0.531 | +1.4% | +11.7% | -7.6% |
| away_top4_iso_last20 | bot_10 | 467 | 0.527 | +0.6% | +13.9% | -8.3% |
| home_lineup_iso_last20 | bot_10 | 469 | 0.525 | +0.1% | +10.0% | -8.3% |
| home_lineup_k_rate_last20 | top_10 | 466 | 0.524 | -0.0% | -0.5% | +0.9% |
| home_top4_iso_last20 | bot_10 | 467 | 0.522 | -0.3% | +7.9% | -7.2% |
| home_lineup_k_rate_last20 | top_20 | 933 | 0.522 | -0.4% | -3.2% | +4.3% |
| away_lineup_iso_last20 | bot_20 | 934 | 0.513 | -2.1% | +2.6% | -6.1% |
| home_top4_iso_last20 | bot_20 | 936 | 0.513 | -2.1% | +4.0% | -7.4% |

## Q5: Proceed to Phase 3?

## Q6: V2 Opponent-Adjusted Upgrade

Lineup-adjusted K rate vs team-adjusted K rate against market_error:
(see console output for exact numbers)

## Critical Assessment

### What passed convincingly

1. **Lineup-level features are genuinely different from team averages.** Average r=0.70 means lineups share only ~49% of variance with team baselines. The remaining 51% is unique to actual lineup composition.

2. **Incremental value is statistically real.** 7/8 family-side tests show lineup adds signal after controlling for team (p<0.001 in 6 of 7). This is not noise.

3. **Contact rate is the strongest family.** Lineup contact_rate explains 5× more market error variance than team contact_rate (R²=0.005 vs 0.001). The specific batters hitting matters more for contact than the team average.

4. **Structural features work incrementally.** top4_iso adds value beyond team ISO (p<0.0001). The power concentration in the lineup matters, not just the average.

5. **V2 opponent-adjusted concept improves with lineup-level context.** Lineup-adjusted K rate (p=0.052) vs team-adjusted (p=0.956). In combined model both are significant (p<0.001), confirming independent information.

### What did NOT pass

1. **Tail tests are year-unstable.** Every ISO tail that works in 2024 fails in 2025 (all show +8 to +14% in 2024, -7 to -11% in 2025). This is a red flag for deployment.

2. **R² values remain tiny.** Best combined model R²=0.012 (1.2% of market error explained). Lineup features are statistically significant but practically small.

3. **No tail produces consistent ROI across years.** The tails are 2024-specific. Zero tail passes the (ROI>4%, N≥80, year-consistent) triple gate.

4. **Market partially prices lineup power.** High-ISO lineups see +0.10 to +0.21 higher closing totals. The market notices lineup composition, even if imperfectly.

### The ceiling test paradox

This test used ACTUAL lineups (known post-game) as the ceiling. Despite this perfect information advantage, lineup features:
- Add statistically significant but small predictive value
- Cannot produce year-stable betting tails
- Market partially prices the effect

A projected-lineup engine would have LESS information than this ceiling test (projected lineups have error). So the practical deployment value will be even smaller than what we see here.

## Final Verdict

**INVESTIGATE — qualified advance with caveats**

The statistical evidence is clear: lineup-level features carry genuine information beyond team averages (7/8 ADDS_VALUE, multiple p<0.0001). This justifies further research.

However, the practical deployment value is uncertain:
- No year-stable tails
- Tiny R² improvements
- Market partially prices lineup composition
- A projected-lineup engine will have less information than this ceiling test

### Recommendation for Phase 3

Phase 3 should be **narrow and targeted**, not a full projected-lineup engine build:

1. **Test lineup-level features as V2 opponent-adjustment upgrade** — the most promising path (combined model R²=0.003 vs lineup-only 0.0008)
2. **Test lineup contact rate as pitcher-matchup interaction** — strongest individual signal
3. **Do NOT build a full projected-lineup prediction engine yet** — the ceiling test shows insufficient tail-level edge to justify the complexity
4. **Investigate Statcast batter-level data pull** — hard_hit/barrel at batter level could unlock stronger lineup composition signals that boxscore metrics miss

### Top 5 Lineup Features Worth Carrying Forward
1. home_lineup_contact_rate_last20 (p<0.0001, strongest individual signal)
2. home_lineup_iso_last20 (p<0.0001)
3. away_lineup_contact_rate_last20 (p<0.0001)
4. away_lineup_iso_last20 (p<0.0001)
5. home/away_top4_iso_last20 (structural power concentration, p<0.0001 incremental)

### Clearly Redundant
- away_k_rate_last20 (WEAK, p=0.21 — only lineup family that doesn't add value)
- away_bottom3_k_rate_last20 (p=0.47 incremental — not useful)

### Biggest Phase 3 Gaps
1. Statcast batter-level metrics (hard_hit, barrel, pull, launch_angle)
2. Batter handedness for platoon splits
3. Year-stable tail signals (none found in ceiling test)
