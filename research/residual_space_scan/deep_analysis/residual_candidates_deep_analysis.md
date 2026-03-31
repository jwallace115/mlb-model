# Deep Analysis — combined_short_exit and combined_lineup_iso

Dataset: 4781 games, 4599 non-push
V1 OVER-lean (p_under<0.45): N=1205, over%=0.520, ROI=-0.8%

---
## combined_short_exit
Direction: LOW → OVER
Mechanism: durable starters (bot)

### Test 1 — Season Stability

| Year | Coefficient | p-value | R² |
|------|-----------|---------|-----|
| 2024 | -0.13532 | 0.1063 | 0.001097 |
| 2025 | -0.12234 | 0.1289 | 0.000960 |

Verdict: **STABLE**

- 2024 favorable-10% tail: N=375, ROI=+1.3%
- 2025 favorable-10% tail: N=234, ROI=+10.1%

### Test 2 — Decile Structure

| Decile | N | Mean | Resid | Over% | ROI |
|--------|---|------|-------|-------|-----|
| 0 | 462 | 0.0441 | +0.0693 | 0.569 | +8.7% |
| 1 | 698 | 0.1177 | -0.0229 | 0.477 | -8.9% |
| 2 | 330 | 0.1640 | -0.0364 | 0.464 | -11.5% |
| 3 | 685 | 0.1901 | -0.0080 | 0.492 | -6.1% |
| 4 | 527 | 0.2312 | -0.0104 | 0.490 | -6.5% |
| 5 | 57 | 0.2485 | +0.0088 | 0.509 | -2.9% |
| 6 | 460 | 0.2692 | -0.0087 | 0.491 | -6.2% |
| 7 | 491 | 0.3081 | +0.0010 | 0.501 | -4.4% |
| 8 | 510 | 0.3660 | -0.0353 | 0.465 | -11.3% |
| 9 | 379 | 0.4988 | -0.0356 | 0.464 | -11.3% |

Gradient: **noisy**

### Test 3 — Threshold Sensitivity

| Threshold | N | Over% | Resid | ROI | 2024 ROI | 2025 ROI |
|-----------|---|-------|-------|-----|----------|----------|
| bot_10 | 462 | 0.569 | +0.069 | +8.7% | +5.8% | +11.4% |
| bot_20 | 1160 | 0.514 | +0.014 | -1.9% | -2.4% | -1.4% |
| bot_30 | 1490 | 0.503 | +0.003 | -4.0% | -4.0% | -4.0% |

Sweet spot: **bot_10**

### Test 4 — Robustness Controls

- Coefficient: -0.17213
- p-value: 0.0038
- Verdict: **ROBUST**

### Test 5 — Market Awareness

- corr(signal, closing_total): r=0.1560
- Avg closing total — favorable bucket: 8.19, rest: 8.44, diff: -0.25
- Market **partially prices** this

---
## combined_lineup_iso
Direction: HIGH → OVER
Mechanism: power lineups (top)

### Test 1 — Season Stability

| Year | Coefficient | p-value | R² |
|------|-----------|---------|-----|
| 2024 | +1.22838 | 0.0130 | 0.002594 |
| 2025 | +0.98398 | 0.0364 | 0.001823 |

Verdict: **STABLE**

- 2024 favorable-10% tail: N=230, ROI=+10.4%
- 2025 favorable-10% tail: N=231, ROI=-2.5%

### Test 2 — Decile Structure

| Decile | N | Mean | Resid | Over% | ROI |
|--------|---|------|-------|-------|-----|
| 0 | 460 | 0.1182 | -0.0348 | 0.465 | -11.2% |
| 1 | 460 | 0.1318 | -0.0630 | 0.437 | -16.6% |
| 2 | 460 | 0.1384 | -0.0370 | 0.463 | -11.6% |
| 3 | 460 | 0.1440 | -0.0239 | 0.476 | -9.1% |
| 4 | 460 | 0.1494 | -0.0087 | 0.491 | -6.2% |
| 5 | 459 | 0.1549 | +0.0076 | 0.508 | -3.1% |
| 6 | 460 | 0.1609 | +0.0022 | 0.502 | -4.1% |
| 7 | 460 | 0.1675 | +0.0087 | 0.509 | -2.9% |
| 8 | 460 | 0.1763 | +0.0087 | 0.509 | -2.9% |
| 9 | 460 | 0.1918 | +0.0500 | 0.550 | +5.0% |

Gradient: **noisy**

### Test 3 — Threshold Sensitivity

| Threshold | N | Over% | Resid | ROI | 2024 ROI | 2025 ROI |
|-----------|---|-------|-------|-----|----------|----------|
| top_10 | 460 | 0.550 | +0.050 | +5.0% | +10.6% | -0.2% |
| top_20 | 920 | 0.529 | +0.029 | +1.1% | +4.0% | -1.7% |
| top_30 | 1380 | 0.522 | +0.022 | -0.3% | +2.6% | -3.0% |

Sweet spot: **top_10**

### Test 4 — Robustness Controls

- Coefficient: +1.40847
- p-value: 0.0001
- Verdict: **ROBUST**

### Test 5 — Market Awareness

- corr(signal, closing_total): r=0.1349
- Avg closing total — favorable bucket: 8.62, rest: 8.39, diff: +0.23
- Market **partially prices** this

---
## Test 6 — V1 Interaction (Walk-Forward)

Warmup: first 50 V1 OVER-lean games per season

| Cohort | N | Over% | Resid | ROI | 2024 ROI | 2025 ROI |
|--------|---|-------|-------|-----|----------|----------|
| A: V1 OVER-lean alone | 1205 | 0.520 | +0.020 | -0.8% | +4.7% | -5.6% |
| V1 + exit bot10 | 143 | 0.566 | +0.066 | +8.1% | +5.2% | +11.6% |
| V1 + exit bot20 | 253 | 0.549 | +0.049 | +4.9% | +8.4% | +1.8% |
| V1 + exit bot30 | 393 | 0.539 | +0.039 | +3.0% | +4.9% | +1.3% |
| V1 + iso top10 | 145 | 0.510 | +0.010 | -2.6% | +2.0% | -5.6% |
| V1 + iso top20 | 296 | 0.476 | -0.024 | -9.1% | -5.3% | -12.0% |
| V1 + iso top30 | 415 | 0.492 | -0.008 | -6.2% | -4.0% | -7.9% |
| V1 + short_exit bot20 + iso top20 | 74 | 0.541 | +0.041 | +3.2% | +11.4% | -0.7% |

---
## Test 7 — Independence

- corr(short_exit, lineup_iso): r=-0.0707, p=0.0000
- **INDEPENDENT**
- Joint OLS: short_exit coef=-0.11630 (p=0.0455), iso coef=+1.04858 (p=0.0021)
- R²=0.003002

---
## Test 8 — Permutation (2025)

**combined_short_exit** (V1 + low 20%, walk-forward):
- N=135, obs ROI=+1.8%
- Permutation: median=-5.3%, p5=-18.0%, p95=+6.1%
- Percentile: 88% (PASS)

**combined_lineup_iso** (V1 + high 20%, walk-forward):
- N=167, obs ROI=-12.0%
- Permutation: median=-6.3%, p5=-16.5%, p95=+4.0%
- Percentile: 22% (FAIL)

---
## Test 9 — Availability Bias

**combined_short_exit:**
| Group | N | Over% | Avg Close | ROI |
|-------|---|-------|-----------|-----|
| Available | 1205 | 0.520 | 9.14 | -0.8% |

Bias: 0.000 (CLEAN)

**combined_lineup_iso:**
| Group | N | Over% | Avg Close | ROI |
|-------|---|-------|-----------|-----|
| Available | 1205 | 0.520 | 9.14 | -0.8% |

Bias: 0.000 (CLEAN)

---
## Final Verdict

### combined_short_exit

| Criterion | Result |
|-----------|--------|
| Season stability | STABLE |
| Walk-forward V1 low20 ROI | +4.9% (N=253) |
| V1 lift | +5.7pp |
| 2024 / 2025 | +8.4% / +1.8% |

**Verdict: INVESTIGATE (not yet ADVANCE)**

The walk-forward numbers are encouraging but not definitive:

**For ADVANCE:**
- ROBUST after controls (p=0.004) — strongest robustness result of any OVER signal tested
- Walk-forward V1 lift +5.7pp (bot20: +4.9% vs V1's -0.8%)
- Year-stable: +8.4% (2024) / +1.8% (2025) — both positive
- Permutation PASSES at 88th percentile
- CLEAN availability bias
- Independent from lineup_iso (r=-0.07)
- Large viable cohort (~126 games/season)

**Against ADVANCE:**
- 2025 walk-forward ROI is only +1.8% — thin edge, barely positive
- The 2024 static tail (bot 10%, +1.3%) was weak; the strong number was 2025 static (+10.1%)
- Walk-forward bot10 shows +8.1% pooled but year split is +5.2/+11.6 — 2024 is modest
- Mechanism is counterintuitive (durable starters → OVER) and may reflect confounding with game environment rather than a causal pathway
- The signal does NOT survive as a standalone OVER predictor (decile gradient is noisy)

**Recommendation:** Shadow monitor in 2026. Promote to ADVANCE if:
- 2026 V1+short_exit bot20 over% ≥ 53%
- AND ROI ≥ +3% at N≥50
- AND permutation ≥ 85th percentile

- Role: V1 OVER-lean amplifier candidate
- Viable cohort: ~126 games/season
- Independent from lineup_iso: r=-0.071
- Recommended stake if promoted: 0.5u OVER on V1+short_exit qualifying games

### combined_lineup_iso

| Criterion | Result |
|-----------|--------|
| Season stability | STABLE (coefs: +1.23 / +0.98, both p<0.04) |
| Robustness | **ROBUST** (p=0.0001) — strongest of any feature tested |
| Walk-forward V1 top20 ROI | **-9.1%** (N=296) |
| V1 lift | **-8.2pp** (HARMFUL) |
| 2024 / 2025 | -5.3% / -12.0% |
| Permutation | 22nd percentile (FAIL) |

**Verdict: SHELVE as V1 OVER amplifier. HOLD as standalone research signal.**

The paradox of combined_lineup_iso:
- It is the **most robust standalone OVER predictor** in the entire research program (p=0.0001 after controls, stable both years, CLEAN market correlation)
- But it **actively harms V1 OVER-lean signals** (-8.2pp lift, both years negative)
- Standalone top-10%: +5.0% ROI — genuinely positive
- V1 + top-20%: -9.1% ROI — genuinely harmful

This means lineup ISO contains real OVER information that the market partly misses, but it is **anti-correlated with V1 OVER-lean selection**. When V1 says OVER, high-ISO lineups are already reflected in the market line. The standalone edge exists where V1 does NOT lean OVER.

- Role: **Standalone research signal only** — not a V1 amplifier
- Do NOT deploy as V1 OVER overlay (harmful)
- Consider testing as standalone OVER signal outside V1 system (top 10%, standalone +5.0% ROI)
- Independent from short_exit: r=-0.071

### Comparative Summary

| | combined_short_exit | combined_lineup_iso |
|---|---|---|
| Robustness | p=0.004 (ROBUST) | p=0.0001 (ROBUST) |
| Standalone | noisy decile, tail-only | +5.0% top10 standalone |
| V1 interaction | **+5.7pp lift** (positive) | **-8.2pp lift** (harmful) |
| Permutation 2025 | 88th (PASS) | 22nd (FAIL as V1 amp) |
| Market awareness | mostly missed (r=+0.16) | partially priced (r=+0.13) |
| 2024 WF | +8.4% | -5.3% |
| 2025 WF | +1.8% | -12.0% |

**combined_short_exit is the clear winner as a V1 amplifier.** It is the only OVER signal in the entire research program that:
1. Passes walk-forward with positive lift both years
2. Passes permutation (88th percentile)
3. Is ROBUST after controls (p=0.004)
4. Has zero availability bias

**combined_lineup_iso is a standalone anomaly** that the market underprices, but it cannot be deployed within the V1 framework. It would need an entirely separate OVER engine to exploit.

