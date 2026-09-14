# Phase 3: Market Anchoring, Pricer, and Calibration

**Data:** 2021-2024 for fitting. 2025 scored once. 2026 not used.
**Market lines:** PBP `spread_line` and `total_line` — nflfastR consensus CLOSING lines
(verified: corr(spread_line, home_margin) = +0.50; positive = home favored).

---

## 1. Anchoring (D7)

### Mechanism
EPA offsets (delta_home, delta_away) added to the D6 additive EPA shift channel
(same yards/play shift on pass and rush completions). Jacobian estimated once from
30-game sample:

```
J = [[ 6.88, -5.48],    (d_margin / d_delta)
     [ 4.79,  4.01]]    (d_total  / d_delta)
```

One Newton step per game (2 engine runs), convergence to market within ~2 pts.
Anchoring residual MAE: margin 2.24, total 1.99.

### K1 Post-Anchoring (2021-2024, N=1000, 1087 games)

| Metric | Raw | Anchored | Actual | Status |
|--------|-----|----------|--------|--------|
| pts/team | 19.5 | **22.7** | 22.4 | **FIXED** |
| P(\|m\|=3) | 8.5% | 7.5% | 14.5% | **STILL FAIL** |
| P(\|m\|=7) | 7.6% | 7.3% | 8.2% | PASS |
| SD margin | 14.06 | 13.47 | 14.20 | PASS (within 1.0) |

**pts/team is fixed.** The 2.9 pt/team deficit that was the K1 residual is resolved
by anchoring — the mean now matches the market total by construction.

**P(|m|=3) is NOT fixed.** Anchoring shifts the mean but does not alter the FG/TD mix.
The 3-point margin mass (7.5% vs 14.5%) remains under-generated. This is a structural
issue in the drive-level engine (EPA-success/fail split under-produces FG-range drives).
Key-number pricing at +/-3 and +/-6 cannot be trusted.

### Convergence stats (2021-2024)

| Season | Games | Time | s/game | pts/team |
|--------|-------|------|--------|----------|
| 2021 | 272 | 494s | 1.8 | 23.7 |
| 2022 | 271 | 492s | 1.8 | 22.4 |
| 2023 | 272 | 498s | 1.8 | 21.9 |
| 2024 | 272 | 494s | 1.8 | 22.7 |

---

## 2. K2: Anchored Distribution vs Naive (2021-2024)

### Spread reliability (P(home covers) by decile)

| Dec | Sim P | Actual | Gap |
|-----|-------|--------|-----|
| 0 | 0.333 | 0.505 | -0.172 |
| 1 | 0.385 | 0.411 | -0.027 |
| 2 | 0.411 | 0.464 | -0.053 |
| 3 | 0.435 | 0.548 | -0.112 |
| 4 | 0.456 | 0.435 | +0.021 |
| 5 | 0.480 | 0.450 | +0.031 |
| 6 | 0.502 | 0.525 | -0.023 |
| 7 | 0.525 | 0.477 | +0.048 |
| 8 | 0.555 | 0.546 | +0.009 |
| 9 | 0.613 | 0.450 | +0.164 |

**FAIL:** The sim's spread probabilities range 0.33-0.61 when the actual cover rate
is ~50% throughout. The sim compresses around 50% (weak discrimination) and is
over-confident at decile 9. This is expected: the sim's team differentiation
(SD 5.6 vs spread SD 6.1) means it roughly agrees with the market on who is favored,
but adds no independent information about BY HOW MUCH.

### Over/under reliability

| Dec | Sim P | Actual | Gap |
|-----|-------|--------|-----|
| 0 | 0.365 | 0.418 | -0.053 |
| 1 | 0.424 | 0.417 | +0.007 |
| 4 | 0.499 | 0.527 | -0.028 |
| 9 | 0.639 | 0.383 | +0.256 |

**FAIL:** Same pattern. Decile 9 over-confident by 26pp.

### Accuracy summary

| Market | Sim accuracy | Baseline |
|--------|-------------|----------|
| Home cover | 51.7% | 50% (coin flip) |
| Over/under | 51.5% | 50% |
| Home win | 66.2% | ~67% (market-implied) |

The sim does not beat the market for straight picks. Its value is in the
JOINT distribution (player props, correlations, SGP).

---

## 3. Calibration Maps (calibration_v1.json)

Isotonic regression fitted on 2021-2024 for three game-level families:
- **margin_side**: P(home covers) -> calibrated
- **total_side**: P(over) -> calibrated
- **moneyline**: P(home wins) -> calibrated

Player-prop calibration maps require anchored sims WITH players (90+ min runtime,
deferred to Phase 3 follow-up or Phase 4 pipeline). The pricer outputs both
`fair_prob` (raw) and `calibrated_prob` (after maps) for all markets where a map exists.

### Before/after reliability (margin_side, 2021-2024 in-sample)

| Dec | Raw gap | Cal gap |
|-----|---------|---------|
| 0 | -0.172 | -0.056 |
| 4 | +0.021 | +0.044 |
| 9 | +0.164 | +0.071 |

Calibration reduces the worst gaps by ~50% but the underlying compression
(all deciles within 0.33-0.61) means the maps flatten probabilities further.

---

## 4. 2025 Holdout (Scored Once)

**272 games, N=1000, scored with frozen calibration_v1.json maps.**
Lock file: `research/nfl_sim/HOLDOUT_2025_SCORED.lock`.

| Metric | 2025 | 2021-2024 |
|--------|------|-----------|
| pts/team | 22.9 | 22.7 |
| Home cover accuracy | 44.1% | 51.7% |
| Over/under accuracy | 51.8% | 51.5% |
| Home win accuracy | 65.8% | 66.2% |
| P(\|m\|=3) | 7.6% | 7.5% |
| SD margin | 13.40 | 13.47 |
| Margin MAE vs actual | 10.21 | 10.10 |

**Home cover accuracy 44.1%** — BELOW coin flip on 2025. The calibration maps
(fitted on 2021-2024) did not transfer. This confirms the sim has no spread edge.

By week range:
- Weeks 1-4: HC acc 60.9% (N=64) — early-season inflated by variance
- Weeks 5-18: HC acc 38.9% (N=208) — below chance

---

## 5. Pricer (nfl/sim/pricer.py)

Implemented markets from the anchored joint sample:
- Home moneyline
- Spread ladder: home -14 to +14 by 0.5
- Total ladder: market +/-10 by 0.5
- Team totals (both teams)
- 1H spread and total (from home_1h, away_1h columns)
- Player props: receptions >= k, rec yards >= y, rush yards >= y, rush attempts >= k,
  passing yards >= y, passing TDs >= k, anytime TD
  — for top 6 target-share + top 2 carry-share + QB per team
- SGP: `sgp_probability(legs)` = joint frequency in the sample
- Leg correlation: phi coefficient from indicators

All operations are column ops over the sample (no per-sim Python loops).
Output: one parquet per game with (market, side, line, fair_prob, fair_american, calibrated_prob, n_sims).

---

## 6. WHAT THE BOARD CAN AND CANNOT TRUST

### Can trust (calibrated within +/-5pp or adds genuine information)

| Family | Status | Notes |
|--------|--------|-------|
| Player props | **USE WITH CAUTION** | Sim generates player-level distributions from the joint sample. Calibration maps not yet fitted (Phase 3 follow-up). Use for SGP correlation structure, not for raw probabilities. |
| SGP correlations | **USE** | The leg-correlation function captures genuine within-game dependencies (e.g., RB rushing yards correlated with game total). This is the primary value proposition. |
| 1H totals | **USE WITH CAUTION** | 1H scores from the sim have the same distribution shape issues as full-game. |

### Cannot trust

| Family | Status | Mechanism |
|--------|--------|-----------|
| Spread (ATS) | **NO EDGE** | 51.7% accuracy in-sample, 44.1% on 2025 holdout. Sim agrees with market. |
| Total (O/U) | **NO EDGE** | 51.5% in-sample. Decile 9 over-confident by 26pp. |
| Key numbers (+/-3, +/-6) | **STRUCTURALLY WRONG** | P(\|m\|=3) = 7.5% vs actual 14.5%. FG-margin mass under-generated. |
| Alt spreads near 3 | **MISPRICED** | Downstream of the key-number deficit. |

### Requires further work

| Item | What's needed |
|------|--------------|
| Player prop calibration maps | Run anchored sims WITH players (1087 games x 1000 sims x 5s/game = 90 min) |
| K4 (real price comparison) | Match props archive to sim predictions; compute CLV and ROI |
| Key-number calibration layer | Empirical reweighting of the margin histogram (v2 per D15) |

---

## 7. Statement on Data Seasons

All calibration maps fitted on **2021-2024 regular season only** (weeks 1-18).
The 2025 season was scored ONCE with frozen maps and locked.
The 2026 season was not used in any fitting, scoring, or evaluation.
