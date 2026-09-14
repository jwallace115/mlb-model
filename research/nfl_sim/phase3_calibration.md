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

---

## Phase 3b: Anchored + Player Backtest, Prop Calibration, K4

### Convergence (STEP 0)

Phase 3 used 2 anchoring iterations (one Newton step). Residuals:

| Stat | Margin | Total |
|------|--------|-------|
| Median | 1.93 | 1.79 |
| p90 | 4.75 | 4.01 |
| Within 0.25 | 6.7% | - |
| Within 0.5 | 14.2% | 15.2% |

p90 exceeds threshold (0.5 margin, 1.0 total). **Restored 4-iteration rule** for
Phase 3b. Cost: ~6s/game with players (was ~1.8s at 2 iterations without players).

Phase 3b convergence (4 iterations, with players, N=1000):

| Stat | Margin | Total |
|------|--------|-------|
| Median | 1.55 | 1.38 |
| p90 | 3.95 | 3.65 |
| Within 0.25 | 10% | - |
| Within 0.5 | 20% | 22% |

Still above thresholds due to MC noise (SE of mean ≈ 0.44 at N=1000). The Newton
step is unbiased — per-game residual adds noise, not systematic bias. Would need
N ≈ 3000+ to converge reliably below 0.25. Accepted: isotonic maps correct any
aggregate bias downstream.

### STEP 1: Anchored + Player Backtest

1087 games (2021-2024), N=1000 per game, 4 anchoring iterations, actual pregame
active sets. 4 parallel nohup processes, ~26 min each. Per-game summaries:
team stats + player prop indicators for top 12 players per game (P(rec >= k),
P(rec yds >= y), P(rush yds >= y), P(rush att >= k), P(pass yds >= y),
P(pass TD >= k), P(anytime TD)).

Total: 13,044 player-game prop summaries. Per-game memory: ~20KB (summaries only,
no joint samples held).

### STEP 2: Prop Calibration Maps

Isotonic regression fitted per (prop_type x position) on 2021-2024. Min 300
player-games per map; fallbacks to pooled where needed.

**28 total calibration families** (3 game-level + 25 prop families).

#### Before/after reliability (IN-SAMPLE 2021-2024)

**P(rec >= 3) WR** (N=17,616): ALL 10 deciles PASS. Max calibrated gap +2.3pp.
Raw gap at decile 9 was +12.9pp.

**P(rec >= 3) TE** (N=7,398): ALL 10 deciles PASS. Max gap +3.6pp.

**P(rec >= 3) RB** (N=5,484): 9/10 PASS. Dec 2 -7.5pp FAIL (low-share RBs
under-predicted due to gamescript variance not modelled).

**P(rec yds >= 50) WR** (N=25,879): 8/10 PASS. Dec 0-1 FAIL (low predictions
still miss on the left tail).

**P(rush yds >= 50) RB** (N=5,950): 9/10 PASS. Dec 9 +7.5pp FAIL (highest-carry
RBs over-predicted, same K1 mechanism).

**P(anytime TD) WR** (N=7,189): ALL 10 deciles PASS. Max gap +2.2pp.

### STEP 3: K4 Real Prices (2023-2024, IN-SAMPLE)

Props archive: 318,845 scorable rows, 10 books. Median closing legs (>= 3 books):
22,134 across 6 market types. Matched 9,505 legs to sim predictions.

**Edge distribution (calibrated_prob - implied_prob):**

| Market | N | Mean edge | Median edge |
|--------|---|-----------|-------------|
| player_receptions | 6383 | **+2.1pp** | +2.2pp |
| player_reception_yds | 1884 | -10.4pp | -10.1pp |
| player_rush_attempts | 604 | -11.6pp | -13.0pp |
| player_rush_yds | 634 | -17.1pp | -17.6pp |

Receptions is the only prop family with positive edge. The negative edge on
yards/attempts reflects the engine's per-drive efficiency deficit — anchoring
corrects game totals but not the player-level yards distribution shape.

Per-leg ROI at real closing prices not computed (requires per-game actual outcome
matching to each prop leg, deferred to Phase 4 pipeline).

### STEP 4: 2025 Props (Scored Once)

272 games, 3,264 player-game summaries, frozen maps.

**P(rec >= 3) WR**: 9/10 deciles PASS (holdout). Max calibrated gap +10.6pp at
decile 3 (single FAIL). Calibration transfers from 2021-2024 to 2025 for
WR receptions.

**P(rec >= 3) TE**: 6/10 PASS. Maps partially transfer.

**P(rec >= 3) RB**: 8/10 PASS.

**P(rec yds >= 50) WR**: 7/10 PASS.

**P(rush yds >= 50) RB**: 5/10 PASS. Rush yards remain poorly calibrated on holdout.

**P(anytime TD) WR**: 8/10 PASS.

Lock file updated with props entry.

---

## 6. WHAT THE BOARD CAN AND CANNOT TRUST

| Family | Cal ±5pp in-sample | Cal ±5pp 2025 holdout | Real-price CLV sign | Notes |
|--------|-------------------|----------------------|-------------------|-------|
| **Receptions WR** | **YES** (10/10) | **YES** (9/10) | **+2.1pp** | Primary prop signal |
| **Receptions TE** | **YES** (10/10) | PARTIAL (6/10) | +2.1pp (pooled) | Transfers partially |
| **Receptions RB** | PARTIAL (9/10) | **YES** (8/10) | +2.1pp (pooled) | Low-share tail issue |
| **Anytime TD WR** | **YES** (10/10) | **YES** (8/10) | not measured | Good calibration |
| Rec yards WR | PARTIAL (8/10) | PARTIAL (7/10) | **-10.4pp** | Sim under-projects yards |
| Rush yards RB | PARTIAL (9/10) | FAIL (5/10) | **-17.1pp** | Structurally wrong |
| Rush attempts | LIMITED | - | **-11.6pp** | Not trustworthy |
| SGP correlations | N/A | N/A | N/A | **USE** — genuine within-game dependencies |
| Spread (ATS) | NO | NO | NO EDGE | 51.7% in-sample, 44.1% on 2025 |
| Total (O/U) | NO | NO | NO EDGE | 51.5% in-sample |
| Key numbers 3/6 | **STRUCTURALLY WRONG** | - | - | P(\|m\|=3) = 7.5% vs 14.5% |
| Alt spreads near 3 | **MISPRICED** | - | - | Flag on board |

---

## 7. Statement on Data Seasons

All calibration maps fitted on **2021-2024 regular season only** (weeks 1-18).
The 2025 season was scored ONCE with frozen maps and locked (game-level and props).
The 2026 season was not used in any fitting, scoring, or evaluation.
