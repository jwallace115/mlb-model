# V2 Deep Analysis — ADJ_CONTACT and ADJ_HH

Dataset: 4855 games (2024-2025), 4666 non-push
V1 baseline (p_under>0.57): N=887

## Signal Definitions

| Signal | Field | Direction | Hypothesis |
|--------|-------|-----------|-----------|
| ADJ_CONTACT | combined_adj_contact_rate_last3 | HIGH tail → UNDER | Higher adjusted contact suppression → UNDER |
| ADJ_HH | combined_adj_hard_hit_last3 | LOW tail → UNDER | Lower adjusted hard-hit suppression → UNDER (counterintuitive, needs validation) |

---
## ADJ_CONTACT: combined_adj_contact_rate_last3

### Test 1 — Season Stability

| Year | Coefficient | p-value | R² |
|------|-----------|---------|-----|
| 2024 | +0.27052 | 0.2603 | 0.000568 |
| 2025 | +0.40804 | 0.1048 | 0.001177 |

Verdict: **STABLE** — same sign both years

### Test 2 — Decile Structure

| Decile | N | Mean | Resid | Under% | ROI |
|--------|---|------|-------|--------|-----|
| 0 | 429 | -0.0622 | -0.0302 | 0.490 | -6.5% |
| 1 | 429 | -0.0297 | -0.0168 | 0.506 | -3.4% |
| 2 | 429 | -0.0138 | -0.0190 | 0.513 | -2.1% |
| 3 | 429 | -0.0012 | -0.0090 | 0.510 | -2.5% |
| 4 | 429 | 0.0099 | -0.0235 | 0.494 | -5.7% |
| 5 | 429 | 0.0214 | -0.0414 | 0.466 | -11.0% |
| 6 | 429 | 0.0324 | +0.0202 | 0.538 | +2.8% |
| 7 | 429 | 0.0444 | +0.0436 | 0.562 | +7.2% |
| 8 | 429 | 0.0589 | -0.0369 | 0.485 | -7.4% |
| 9 | 429 | 0.0880 | +0.0391 | 0.566 | +8.1% |

Gradient: **noisy**

### Test 3 — Threshold Sensitivity

| Threshold | N | Under% | Resid | ROI | 2024 ROI | 2025 ROI |
|-----------|---|--------|-------|-----|----------|----------|
| top_10 | 426 | 0.566 | +0.066 | +8.0% | +2.8% | +13.6% |
| top_20 | 848 | 0.528 | +0.028 | +0.9% | -1.9% | +3.7% |
| top_30 | 1286 | 0.537 | +0.037 | +2.6% | +0.5% | +4.6% |
| bot_10 | 431 | 0.487 | -0.013 | -7.0% | -10.2% | -3.1% |
| bot_20 | 855 | 0.498 | -0.002 | -4.9% | -5.8% | -3.8% |
| bot_30 | 1277 | 0.502 | +0.002 | -4.2% | -7.4% | -0.6% |

### Test 4 — Robustness Controls

Note: home_sp_csw_pct not available in dataset (CSW proxy not in game_level table).
Controls used: home_sp_xfip, away_sp_xfip, closing_total, park_factor_runs

- Signal coefficient: +0.16407
- Signal p-value: 0.3693
- Verdict: **NOT ROBUST**

### Test 5 — Independence from S12/P09

S12 and P09 fields are not directly available in the V2 engine dataset.
S12 uses production CSW (FanGraphs/Savant) which differs from boxscore strike%.
P09 requires pitcher-level Statcast hard-hit lookups not joined here.

Proxy check: correlation with closing_total and xFIP (which S12/P09 partially capture)

- corr(ADJ_CONTACT, closing_total): r=-0.2196
- corr(ADJ_CONTACT, home_sp_xfip): r=-0.2039
- corr(ADJ_CONTACT, away_sp_xfip): r=-0.2306

S12/P09 direct test: SKIPPED (field mismatch — would require production CSW/Statcast join)

### Test 6 — V1 Interaction (walk-forward safe)

Warmup: first 50 V1 UNDER games per season excluded
Threshold: HIGH 20% (p80), expanding within season
Frozen 2024 threshold: 0.06156

| Cohort | N | Under% | Resid | ROI | 2024 ROI | 2025 ROI |
|--------|---|--------|-------|-----|----------|----------|
| A: V1 alone | 887 | 0.558 | +0.058 | +6.5% | +5.0% | +8.4% |
| B: V1 + ADJ_CONTACT (expanding) | 152 | 0.605 | +0.105 | +15.6% | +16.3% | +14.5% |
| B2: V1 + ADJ_CONTACT (frozen) | 161 | 0.602 | +0.102 | +15.0% | +16.8% | +13.0% |

### Test 7 — Permutation (2025)

- N flagged: 65
- Observed: under%=0.600, ROI=+14.5%
- Permutation (200 shuffles): median=+8.7%, p5=-11.9%, p95=+26.4%
- Percentile: 79.0%
- MARGINAL

### Test 8 — Availability Bias

| Group | N | Under% | Avg Close | ROI |
|-------|---|--------|-----------|-----|
| Available | 819 | 0.562 | 7.68 | +7.2% |
| Unavailable | 68 | 0.515 | 8.08 | -1.7% |

Availability bias: 0.047 (WARNING)

---
## ADJ_HH: combined_adj_hard_hit_last3

### Test 1 — Season Stability

| Year | Coefficient | p-value | R² |
|------|-----------|---------|-----|
| 2024 | +0.00415 | 0.9818 | 0.000000 |
| 2025 | +0.11854 | 0.5062 | 0.000206 |

Verdict: **STABLE** — same sign both years

### Test 2 — Decile Structure

| Decile | N | Mean | Resid | Under% | ROI |
|--------|---|------|-------|--------|-----|
| 0 | 412 | -0.1122 | -0.0198 | 0.500 | -4.5% |
| 1 | 413 | -0.0671 | -0.0058 | 0.513 | -2.0% |
| 2 | 410 | -0.0445 | +0.0198 | 0.544 | +3.8% |
| 3 | 412 | -0.0268 | -0.0152 | 0.505 | -3.6% |
| 4 | 412 | -0.0103 | -0.0035 | 0.522 | -0.4% |
| 5 | 411 | 0.0043 | -0.0058 | 0.516 | -1.5% |
| 6 | 412 | 0.0194 | -0.0221 | 0.498 | -5.0% |
| 7 | 411 | 0.0375 | +0.0058 | 0.523 | -0.1% |
| 8 | 412 | 0.0592 | -0.0082 | 0.512 | -2.2% |
| 9 | 412 | 0.1016 | -0.0012 | 0.519 | -0.8% |

Gradient: **noisy**

### Test 3 — Threshold Sensitivity

| Threshold | N | Under% | Resid | ROI | 2024 ROI | 2025 ROI |
|-----------|---|--------|-------|-----|----------|----------|
| top_10 | 411 | 0.521 | +0.021 | -0.6% | -0.2% | -1.3% |
| top_20 | 825 | 0.515 | +0.015 | -1.7% | -1.3% | -2.2% |
| top_30 | 1239 | 0.518 | +0.018 | -1.1% | -1.9% | +0.2% |
| bot_10 | 410 | 0.502 | +0.002 | -4.1% | +3.6% | -8.1% |
| bot_20 | 825 | 0.507 | +0.007 | -3.3% | +1.0% | -5.8% |
| bot_30 | 1234 | 0.519 | +0.019 | -0.8% | +2.2% | -2.9% |

### Test 4 — Robustness Controls

Note: home_sp_csw_pct not available in dataset (CSW proxy not in game_level table).
Controls used: home_sp_xfip, away_sp_xfip, closing_total, park_factor_runs

- Signal coefficient: -0.13021
- Signal p-value: 0.3150
- Verdict: **NOT ROBUST**

### Test 5 — Independence from S12/P09

S12 and P09 fields are not directly available in the V2 engine dataset.
S12 uses production CSW (FanGraphs/Savant) which differs from boxscore strike%.
P09 requires pitcher-level Statcast hard-hit lookups not joined here.

Proxy check: correlation with closing_total and xFIP (which S12/P09 partially capture)

- corr(ADJ_HH, closing_total): r=-0.1015
- corr(ADJ_HH, home_sp_xfip): r=-0.1925
- corr(ADJ_HH, away_sp_xfip): r=-0.1768

S12/P09 direct test: SKIPPED (field mismatch — would require production CSW/Statcast join)

### Test 6 — V1 Interaction (walk-forward safe)

Warmup: first 50 V1 UNDER games per season excluded
Threshold: LOW 20% (p20), expanding within season
Frozen 2024 threshold: -0.03642

| Cohort | N | Under% | Resid | ROI | 2024 ROI | 2025 ROI |
|--------|---|--------|-------|-----|----------|----------|
| A: V1 alone | 887 | 0.558 | +0.058 | +6.5% | +5.0% | +8.4% |
| B: V1 + ADJ_HH (expanding) | 143 | 0.622 | +0.122 | +18.8% | +13.4% | +23.2% |
| B2: V1 + ADJ_HH (frozen) | 175 | 0.623 | +0.123 | +18.9% | +20.5% | +17.5% |

### Test 7 — Permutation (2025)

- N flagged: 79
- Observed: under%=0.646, ROI=+23.2%
- Permutation (200 shuffles): median=+8.7%, p5=-5.8%, p95=+20.8%
- Percentile: 97.5%
- PASS

### Test 8 — Availability Bias

| Group | N | Under% | Avg Close | ROI |
|-------|---|--------|-----------|-----|
| Available | 778 | 0.564 | 7.67 | +7.7% |
| Unavailable | 109 | 0.514 | 8.00 | -1.9% |

Availability bias: 0.051 (WARNING)

---
## Final Verdict

### ADJ_CONTACT: combined_adj_contact_rate_last3

| Criterion | Result |
|-----------|--------|
| Robustness (p after controls) | 0.3693 — **NOT ROBUST** |
| Year stability | STABLE (+0.271 / +0.408) |
| V1 walk-forward lift | +9.1pp expanding, +8.5pp frozen (N=152/161) |
| Permutation 2025 | 79th percentile — **MARGINAL** |
| Market independence | partially correlated (r=-0.22 with closing_total) |
| Availability bias | 4.7pp — **WARNING** |
| Decile structure | **Noisy** — no monotonic gradient |
| Standalone | top_10: +8.0% ROI, top_20: +0.9% ROI — tail-only |

**Verdict: INVESTIGATE**

The V1 interaction is genuinely positive (+15.6% ROI walk-forward, stable both years at +16.3/+14.5%), but three yellow flags prevent ADVANCE:
1. Not robust after controls (p=0.37)
2. Permutation only 79th percentile (below 85% gate)
3. Noisy decile structure — effect is tail-only, not a gradient

- Best role: V1 amplifier candidate (needs 2026 validation)
- Independence: partially correlated with closing_total (r=-0.22); S12/P09 direct test skipped
- Minimum viable N for live use: 100 qualifying V1+signal games per season
- Promotion gate: 2026 V1+ADJ_CONTACT under% ≥ 55%, ROI ≥ +5%, permutation ≥ 85th pctile

### ADJ_HH: combined_adj_hard_hit_last3

| Criterion | Result |
|-----------|--------|
| Robustness (p after controls) | 0.3150 — **NOT ROBUST** |
| Year stability | STABLE but 2024 is essentially zero (+0.004) |
| V1 walk-forward lift | +12.3pp expanding, +12.4pp frozen (N=143/175) |
| Permutation 2025 | **97.5th percentile — PASS** |
| Market independence | independent (r=-0.10 with closing_total) |
| Availability bias | 5.1pp — **WARNING** |
| Decile structure | **Noisy** — no signal whatsoever standalone |
| Standalone | All buckets near 50% under rate — zero standalone value |

**Verdict: INVESTIGATE**

ADJ_HH is the more statistically interesting signal despite having zero standalone value:
1. **Permutation PASSES at 97.5th pctile** — the 2025 V1 interaction is genuinely non-random
2. **Direction is counterintuitive.** LOW adj_hard_hit means pitcher allows MORE hard contact than expected, yet V1+low_adj_hh goes UNDER. This likely captures a selection effect: V1 p_under>0.57 already identifies run-suppression environments, and within that, pitchers with "worse" recent hard-hit luck may be reverting to their baseline skill.
3. **2024 standalone OLS coefficient is 0.004** — essentially zero. The signal only activates as a V1 interaction, not independently.
4. **Not robust after controls** (p=0.32)

- Best role: V1 amplifier candidate, but the counterintuitive direction is a red flag
- Independence: independent from closing_total (r=-0.10) — market does not price this
- Minimum viable N for live use: 100 qualifying V1+signal games per season
- Promotion gate: 2026 must confirm BOTH the direction (LOW = UNDER) AND the V1 interaction lift

### Comparative Summary

| | ADJ_CONTACT | ADJ_HH |
|---|---|---|
| V1 walk-forward ROI | +15.6% | +18.8% |
| V1 lift (pooled) | +9.1pp | +12.3pp |
| 2024 V1 lift | +11.3pp | +6.9pp |
| 2025 V1 lift | +8.0pp | +16.7pp |
| Permutation | 79th (MARGINAL) | 97.5th (PASS) |
| Robustness | NOT ROBUST (p=0.37) | NOT ROBUST (p=0.32) |
| Standalone | +8.0% top_10 | -0.6% top_10 |
| Market corr | -0.22 (PARTIAL) | -0.10 (CLEAN) |
| Direction | Intuitive | Counterintuitive |
| Deciles | Noisy | Noisy |

**ADJ_HH passes the harder test (permutation) but has a counterintuitive direction and zero standalone value.**
**ADJ_CONTACT has the more interpretable signal but fails to clear the permutation threshold.**

Neither signal is ready for ADVANCE. Both deserve 2026 shadow monitoring as V1 amplifier candidates, with ADJ_HH being the more statistically surprising result that needs directional confirmation.

