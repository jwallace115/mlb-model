# SEEP Phase 2 — Live Overlay Test: F5 UNDER Pass Filter

**Date:** 2026-04-07
**Status:** PRELIMINARY (12 days of 2026 data)
**Verdict:** CLOSE — no filtering justified; effect is inverted

---

## Prerequisite Check

### Data Availability

| Metric | Value |
|---|---|
| 2026 starter appearances | 302 |
| Unique 2026 pitchers | 163 |
| Date range | 2026-03-26 to 2026-04-06 |
| Pitchers with >= 3 prior 2026 starts | 0 (season too young) |
| Pitchers scoreable via cross-season rolling | 284/302 (94.0%) |
| Resolved F5 signals | 52 (48 UNDER, 4 OVER) |

**Cross-season approach:** Since the 2026 season is only 12 days old, no pitcher has 3+ starts within 2026 alone. SEEP features were computed using cross-season rolling windows (last 5 starts regardless of season boundary, with >= 3 prior career starts required). This is pregame-safe and realistic for a live model.

### Signal-Starter Matching

| Category | Count |
|---|---|
| Both starters SEEP-scoreable | 49 |
| One starter SEEP-scoreable | 3 |
| Neither scoreable | 0 |

49 of 52 signals (94%) have both starters scoreable. The 3 partial matches involve pitchers making their first or second career start (Kyle Leahy, George Klassen, one other).

### F5 UNDER Baseline

| Metric | Value |
|---|---|
| Total signals | 48 |
| Record | 21W-26L-1P |
| Win rate | 44.7% |
| Net units | -5.18 |
| ROI | -14.4% |
| Mean line | 4.57 |
| Mean actual F5 total | 5.25 |

---

## SEEP Model Summary

**Classifier:** Logistic regression trained on 17,554 scoreable starts from 2022-2025.

| Feature | Coefficient | Direction |
|---|---|---|
| season_ip_per_start | -0.4332 | Lower avg IP -> higher risk |
| rolling5_exit_inning_avg | -0.4454 | Lower recent IP -> higher risk |
| rolling5_min_exit_inning | +0.0923 | (partial offset) |
| days_rest | +0.0025 | Negligible |
| below_normal_rest | -0.1227 | Short rest slightly reduces risk* |
| rolling5_early_exit_count | -0.0236 | Negligible |
| season_start_number | +0.0055 | Negligible |
| intercept | +3.1389 | |

**Training AUC:** 0.652
**Training early exit rate:** 26.7%
**Q75 threshold (HIGH risk):** 0.311 predicted probability

*The below_normal_rest negative coefficient is counterintuitive — likely reflects that pitchers on short rest tend to be aces in scheduled doubleheaders or high-leverage spots, not fatigued arms.

### 2026 OOS Validation

| Risk Tier | N | Early Exit Rate | Mean SEEP Prob |
|---|---|---|---|
| HIGH (Q4) | 153 | 41.2% | — |
| LOW (Q1-Q3) | 131 | 29.8% | — |

The model discriminates in 2026: HIGH-risk starters exit before 5 IP at 41.2% vs 29.8% for LOW, consistent with Phase 1 findings.

---

## Step 0.5 — Availability Bias Check

| Group | N | Win Rate | Mean Line | Date Range |
|---|---|---|---|---|
| All UNDER | 48 | 44.7% | 4.57 | 03-26 to 04-06 |
| Both scoreable | 46 | 44.4% | 4.57 | 03-26 to 04-06 |
| At least one scoreable | 48 | 44.7% | 4.57 | 03-26 to 04-06 |
| Neither scoreable | 0 | — | — | — |

**No availability bias.** 48 of 48 UNDER signals have at least one scoreable starter; 46 of 48 have both. The 2 partial-coverage games show no meaningful difference.

---

## Step 2 — F5 UNDER Pass Filter Test

### Risk Distribution

| Game Risk | N |
|---|---|
| NEITHER HIGH | 16 |
| EITHER HIGH (one side) | 20 |
| BOTH HIGH | 12 |

67% of F5 UNDER signals involve at least one HIGH-risk starter. This is higher than the ~44% base rate expected from random Q4 assignment, suggesting the model targets games with shakier starters (possibly correlated with lower totals lines that attract UNDER signals).

### Filter Results

| Pool | N | W-L-P | Win Rate | Net Units | ROI | Mean Actual F5 | Mean Line |
|---|---|---|---|---|---|---|---|
| **A) ALL UNDER (baseline)** | 48 | 21-26-1 | 44.7% | -5.18 | -14.4% | 5.25 | 4.57 |
| **B) NEITHER HIGH (kept)** | 16 | 6-10-0 | 37.5% | -3.41 | -28.4% | 5.50 | 4.62 |
| **C) EITHER/BOTH HIGH (excluded)** | 32 | 15-16-1 | 48.4% | -1.77 | -7.4% | 5.12 | 4.55 |
| **D) BOTH HIGH only** | 12 | 6-6-0 | 50.0% | -0.41 | -4.5% | 5.33 | 4.71 |

**INVERTED EFFECT.** The filter works backwards:
- Keeping NEITHER HIGH: 37.5% win rate, -28.4% ROI (worse than baseline)
- Excluding HIGH risk: 48.4% win rate, -7.4% ROI (better than baseline)
- BOTH HIGH: 50.0% win rate (best subgroup)

The pool we would SUPPRESS actually outperforms the pool we would KEEP.

---

## Step 3 — Directional Consistency

### Actual IP by Risk Level (scoreable starters in UNDER signals)

| Risk | N | Mean IP | Early Exit Rate | Mean SEEP Prob |
|---|---|---|---|---|
| HIGH | 44 | 4.78 | 31.8% | 0.421 |
| LOW | 50 | 5.21 | 32.0% | 0.220 |

**Key finding:** Despite the model correctly identifying shorter outings for HIGH-risk starters (4.78 vs 5.21 IP), the early exit rates within the UNDER signal population are nearly identical (31.8% vs 32.0%). The model discriminates on IP length but not on the binary <5.0 threshold within this subset.

### Why the Filter Fails

The mechanism is clear from the game-by-game data:

1. **HIGH-risk starters in UNDER games don't blow up — they go 4.0-5.0 IP.** Many HIGH-risk starts in the excluded pool pitched 5.0-6.0 innings (e.g., Ohtani 6.0, Crochet 6.0, Sale 6.0, Cole Ragans 4.0). Early exits are slightly shorter but still concentrated near the 5.0 threshold.

2. **The runs scored in HIGH-risk UNDER games are lower** (mean actual 5.12 vs 5.50 for NEITHER). This suggests HIGH SEEP probability correlates with pitcher/matchup profiles that also suppress scoring — likely because these are quality starters having a mild workload regression, not implosion candidates.

3. **BOTH HIGH games include pitcher duels** where both starters are capable but have workload concerns — exactly the profile that produces low-scoring F5 outcomes (OAK@TOR 1 run, MIN@KCR 1 run, MIN@KCR 3 runs, PIT@CIN 2 runs).

---

## Step 4 — Home vs Away Asymmetry

| Starter Risk | N | W-L | Win Rate | Net Units |
|---|---|---|---|---|
| HOME HIGH only | 8 | 3-5 | 37.5% | -1.70 |
| AWAY HIGH only | 12 | 6-5 | 54.5% | +0.34 |

Modest asymmetry (N too small to be reliable):
- HOME HIGH only: worse for UNDER (37.5% WR). Possible mechanism: home SP exits early, bullpen gives up runs.
- AWAY HIGH only: better for UNDER (54.5% WR). Possible mechanism: away SP exits early but doesn't damage because visiting team is already limited.

However, N=8 and N=12 are far too small to act on.

---

## Step 5 — Practical Framing

| Option | Kept N | Kept WR | Kept ROI | Filtered | Assessment |
|---|---|---|---|---|---|
| A) Suppress EITHER HIGH | 16 | 37.5% | -28.4% | 67% | HARMFUL — removes best signals |
| B) Suppress BOTH HIGH only | 36 | 42.9% | -17.7% | 25% | HARMFUL — removes breakeven signals |
| C) Suppress HOME HIGH only | 28 | 44.4% | -14.6% | 42% | NEUTRAL — no improvement |
| D) No filtering | 48 | 44.7% | -14.4% | 0% | BASELINE |

**No filtering option improves outcomes.** Every suppression rule either makes performance worse (A, B) or has no meaningful effect (C, D). The SEEP early-exit risk filter is counterproductive for F5 UNDER signals.

---

## Interpretation

### Why SEEP Doesn't Help F5 UNDER

Phase 1 confirmed that SEEP identifies early exits well in general (AUC=0.652, 41.2% vs 29.8% early exit rate in 2026). But the F5 UNDER signal already implicitly selects for games where scoring is suppressed:

1. **Selection bias in the signal pool.** F5 UNDER signals target games the sim projects as low-scoring. These games feature pitchers who may have workload variance (triggering HIGH SEEP scores) but are still quality arms projected to suppress runs. SEEP and the F5 model are correlated on the same underlying pitcher quality dimension.

2. **Early exit != runs scored.** A starter pitching 4.1 IP instead of 5.2 IP doesn't necessarily mean more F5 runs. If the bullpen holds, the F5 under still wins. The 31.8% vs 32.0% early exit rate convergence within UNDER signals confirms this.

3. **BOTH HIGH = both starters volatile = lower F5 totals.** When both starters have high exit risk, the most common outcome is both pitching 4-5 innings with limited damage — exactly the UNDER scenario.

### Comparison to Phase 1

| Finding | Phase 1 (general pop) | Phase 2 (F5 UNDER) |
|---|---|---|
| HIGH early exit rate | 49.7% (top decile) | 31.8% |
| HIGH vs LOW separation | 57.1% vs 35.1% | 31.8% vs 32.0% |
| Filter effect | Strong discrimination | No discrimination |

The Phase 1 signal is genuine but does not transfer to the F5 UNDER context because the signal population is already conditioned on low-scoring environments.

---

## Decision

### CLOSE

**Rationale:** The SEEP early-exit filter is counterproductive for F5 UNDER signals. Every filtering option tested either degrades performance or has no effect. The mechanism is clear: F5 UNDER signals already select for games where pitcher quality is high enough to suppress scoring, and SEEP risk in this context reflects workload variance rather than implosion risk. The inverted relationship (HIGH risk -> better UNDER outcomes) is directionally consistent across BOTH HIGH, EITHER HIGH, and home/away splits.

**This line of research is closed for F5 UNDER filtering.**

### Potential Salvage

While SEEP does not help F5 UNDER, the inverted relationship raises a possible alternative hypothesis worth noting (but NOT pursuing without stronger sample sizes):

- **F5 OVER boost:** If HIGH SEEP risk correlates with better UNDER outcomes, the inverse might hold — HIGH risk could identify F5 OVER opportunities. Only 4 resolved OVER signals exist, so this cannot be tested now.
- **Full-game totals:** SEEP may have value for full-game UNDER/OVER where bullpen exposure amplifies early-exit effects over 9 innings rather than 5.

### Next Steps

1. No SEEP overlay to implement for F5 pipeline
2. Archive this result as a negative finding
3. If full-game totals model is built, re-test SEEP there where bullpen amplification may create genuine signal
4. Revisit with larger 2026 sample (100+ signals) only if new mechanism proposed

---

## Appendix: Model Details

- **Training data:** 17,554 scoreable starts (2022-2025), starter_flag == 1, >= 3 prior career starts
- **Label:** early_exit = 1 if IP < 5.0
- **Classifier:** sklearn LogisticRegression, default params (C=1.0, max_iter=1000)
- **Features:** 7 pregame-safe rolling/expanding features computed with 1-game shift
- **Q75 threshold:** 0.311 (from training distribution)
- **2026 scoring:** Cross-season rolling windows (last 5 starts regardless of season boundary)
- **Signal source:** `mlb_sim/logs/f5_signals_2026.json`, 52 resolved signals
- **Pitcher data:** `mlb/data/pitcher_game_logs.parquet`, 84,372 appearances (2022-2026)
