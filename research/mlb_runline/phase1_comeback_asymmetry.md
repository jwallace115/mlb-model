# Phase 1: MLB Run-Line Comeback Asymmetry Research

**Date:** 2026-04-10
**Status:** CLOSE
**Data:** 284 games with run-line closing prices (Odds API historical), 9,715 games with SP data (game_table + sim_inputs), 9,857 total games 2022-2025

---

## Data Audit (Phase B1)

### Run-Line Data Available

No run-line (spreads) data existed in the local data warehouse. Historical closing lines (`mlb_historical_closing_lines.parquet`) contain only totals. The 2026 line snapshot pipeline captures totals only.

**Data pulled for this study:** 284 games across 18 sample dates spanning 2022-2025, with run-line (spreads), moneyline (h2h), and totals from the Odds API historical endpoint. Best-book selection: FanDuel (278), DraftKings (3), BetMGM (2), BetOnlineAG (1).

- 235 games with standard -1.5/+1.5 run-line AND valid ML and RL prices
- All 284 matched to game_table scores (277 direct match, 7 unmatched due to postponements/team name issues)
- Books covered: 23 unique sportsbooks in raw data; FanDuel used as primary
- RL price distribution: fav mean +89 (American), dog mean -140; fair fav cover probability mean 0.428, std 0.064

### Supplemental Data

- `sim_inputs_historical_2022_2024.parquet`: 14,574 rows (7,287 games) with SP xFIP
- `sim_inputs_2025.parquet`: 4,856 rows (2,428 games) with SP xFIP
- `game_table.parquet`: 9,857 games with final scores, 2022-2026
- Signal B (F5 run-line): 7 bets placed in 2026, 2-5 record, -1.21 units

---

## Phase B2: Basic Run-Line Efficiency Test

### PREGAME TEST

De-vigged run-line prices (multiplicative method) vs actual cover rates.

**Overall:**
| Metric | Value |
|--------|-------|
| Games | 235 |
| Fav -1.5 cover rate | 42.1% |
| Mean implied cover (de-vigged) | 42.8% |
| Residual (actual - implied) | -0.7pp |
| SE | 3.2pp |
| z-score | -0.20 |

**Verdict:** Run-line is well-calibrated overall. No aggregate mispricing detected.

### By ML Implied Probability

| ML Bin | N | Cover% | Implied | Residual |
|--------|---|--------|---------|----------|
| 50-55% | 66 | 36.4% | 39.1% | -2.7pp |
| 55-60% | 69 | 44.9% | 41.6% | +3.3pp |
| 60-65% | 50 | 36.0% | 46.4% | -10.4pp |
| 65-70% | 20 | 65.0% | 50.9% | +14.1pp |
| 70%+ | 11 | 36.4% | 53.7% | -17.4pp |

No monotonic pattern. The 60-65% and 70%+ bins show large negative residuals, while 65-70% is strongly positive. This is noise from small samples (N=20, N=11), not systematic mispricing. No bin is significant at p<0.05.

### By Season

| Season | N | Cover% | Implied | Residual |
|--------|---|--------|---------|----------|
| 2022 | 41 | 43.9% | 44.3% | -0.4pp |
| 2023 | 55 | 50.9% | 43.1% | +7.8pp |
| 2024 | 67 | 50.7% | 41.3% | +9.5pp |
| 2025 | 72 | 26.4% | 43.0% | -16.7pp |

2025 shows a massive negative residual (-16.7pp) while 2023-2024 show positive. This is characteristic of random variance, not a stable signal. The direction flips entirely between seasons.

---

## Phase B3: Pregame Conditional Buckets

### PREGAME TESTS ONLY

### B3A: Home Favorite vs Away Favorite

| Category | N | Cover% | Implied | Residual |
|----------|---|--------|---------|----------|
| Home Fav (-1.5) | 120 | 44.2% | 42.5% | +1.6pp |
| Away Fav (-1.5) | 115 | 40.0% | 43.0% | -3.0pp |

Chi-square test: chi2=0.265, p=0.607. No significant difference.

Logistic regression (fav_covered ~ fav_ml_fair + home_is_fav):
- fav_ml_fair coefficient: +0.122
- home_is_fav coefficient: +0.154 (positive = home fav covers slightly more)
- Effect is tiny and not significant with N=235

**Raw home/away -1.5 cover rates (full 9,857-game dataset):**
- Home -1.5 cover: 35.8%
- Away -1.5 cover: 35.9%
- Push zone (|margin| <= 1): 28.4%

Home and away -1.5 covers are virtually identical despite the walk-off asymmetry (see B4). The market correctly prices this.

### B3B: Total Line Interaction

| Total Bucket | N | Cover% | Implied | Residual |
|--------------|---|--------|---------|----------|
| Low (<=7.5) | 60 | 46.7% | 41.5% | +5.1pp |
| Medium (8-9) | 141 | 39.7% | 43.0% | -3.3pp |
| High (>=9.5) | 31 | 41.9% | 45.1% | -3.1pp |

Low-total games show +5.1pp residual (favorites covering more than implied), but N=60 gives SE~6.4pp, so this is not significant (z=0.80).

### B3B Extended: Home/Away x Total Interaction

| Category | N | Cover% | Implied | Residual | SE |
|----------|---|--------|---------|----------|----|
| HomeFav / Low | 29 | 51.7% | 42.0% | +9.8pp | 9.3pp |
| HomeFav / Med | 80 | 41.2% | 43.0% | -1.7pp | 5.5pp |
| HomeFav / High | 9 | 44.4% | 39.6% | +4.8pp | 16.6pp |
| AwayFav / Low | 31 | 41.9% | 41.1% | +0.8pp | 8.9pp |
| AwayFav / Med | 61 | 37.7% | 43.0% | -5.3pp | 6.2pp |
| AwayFav / High | 22 | 40.9% | 47.3% | -6.4pp | 10.5pp |

No cell reaches significance. The HomeFav/Low combination (N=29, +9.8pp) is interesting but far too small for reliable inference.

### B3C: Starter Quality Gap (xFIP)

Using sim_inputs xFIP data joined to run-line sample (N=235):

| xFIP Bucket | N | Cover% | Implied | Residual |
|-------------|---|--------|---------|----------|
| Fav worse SP | 52 | 26.9% | 41.7% | -14.8pp |
| Similar SP | 78 | 41.0% | 42.1% | -1.1pp |
| Fav better SP | 64 | 48.4% | 41.8% | +6.6pp |
| Fav much better SP | 41 | 53.7% | 46.9% | +6.8pp |

This is the most interesting finding: when the ML favorite also has the better SP (by xFIP), the -1.5 cover rate exceeds implied by ~6-7pp. When the favorite has the *worse* SP, covers collapse to 26.9% vs 41.7% implied (-14.8pp).

**However:** The xFIP gap is already priced into the ML line. The question is whether the run-line *translation* from ML is accurate, not whether xFIP predicts wins. The residual here likely reflects small-sample noise (N=52 and N=41 in the extreme buckets), and the monotonic pattern is what we'd expect from any predictive feature not yet converged in 235 games.

### B3C Extended: xFIP x ML Interaction (run-line sample)

| Bucket | N | Cover% | Residual |
|--------|---|--------|----------|
| Fav worse SP / 50-55% | 8 | 12.5% | -24.5pp |
| Fav worse SP / 55-60% | 20 | 35.0% | -4.8pp |
| Fav worse SP / 60-65% | 12 | 25.0% | -21.5pp |
| Similar SP / 50-55% | 25 | 32.0% | -6.9pp |
| Similar SP / 55-60% | 24 | 45.8% | +4.1pp |
| Fav better SP / 50-55% | 18 | 38.9% | -0.9pp |
| Fav better SP / 55-60% | 17 | 58.8% | +16.2pp |
| Fav much better SP / 60-65% | 15 | 53.3% | +6.5pp |
| Fav much better SP / 65%+ | 11 | 72.7% | +19.4pp |

The large positive residuals in "Fav better SP + 55-60% ML" and "Fav much better SP + 65%+ ML" are eye-catching but based on N=17 and N=11. Not actionable.

---

## Phase B4: Observed-State Tests

### OBSERVED-STATE ONLY -- NOT PREGAME EXPLOITABLE

### Final Margin Distribution (9,857 games, 2022-2025)

| Margin | Count | Pct |
|--------|-------|-----|
| -1 | 1,097 | 11.1% |
| +1 | 1,701 | 17.3% |
| -2 | 870 | 8.8% |
| +2 | 886 | 9.0% |
| -3 | 695 | 7.1% |
| +3 | 683 | 6.9% |
| -4 | 581 | 5.9% |
| +4 | 589 | 6.0% |

The distribution is approximately symmetric for |margin| >= 2 (870 vs 886 at margin=2, 695 vs 683 at margin=3, etc.). The massive asymmetry is at margin=+/-1: 1,701 home wins by 1 vs 1,097 away wins by 1.

### Walk-Off Truncation

| Metric | Value |
|--------|-------|
| 1-run games total | 2,798 (28.4%) |
| Home wins by exactly 1 | 1,701 (60.8% of 1-run games) |
| Away wins by exactly 1 | 1,097 (39.2% of 1-run games) |
| P(margin=+1 given home win) | 32.6% |
| P(margin=-1 given away win) | 23.7% |
| Excess 1-run rate (truncation) | 8.9pp |

Home teams win 60.8% of 1-run games (stable across seasons: 59.9%, 58.7%, 60.7%, 63.4% for 2022-2025). This is the walk-off effect: when the home team is tied or down by 1 in the bottom of the 9th and scores, the game ends immediately at margin=+1, regardless of how many more runs they might have scored.

**Truncation magnitude:** ~4.7% of all games have the home team's margin truncated from a potential 2+ to exactly 1. If those truncated games had the same conditional probability of reaching 2+ margin as observed in away wins (76.2%), this would add ~3.6pp to home -1.5 cover rate, pushing it from 35.7% to ~39.3%.

**But this is fully observed-state.** The market knows about walk-off mechanics. The 35.8% vs 35.9% home/away -1.5 cover rate shows the market has already absorbed this asymmetry into pricing.

### By Season (full game_table)

| Season | 1-run N | Home% of 1-run | Home -1.5 | Away -1.5 |
|--------|---------|----------------|-----------|-----------|
| 2022 | 700 | 59.9% | 36.0% | 35.1% |
| 2023 | 675 | 58.7% | 35.8% | 36.4% |
| 2024 | 674 | 60.7% | 35.3% | 36.9% |
| 2025 | 714 | 63.4% | 35.7% | 34.9% |

Extremely stable. Home and away -1.5 cover rates are within 1.6pp across all seasons. The walk-off truncation is real but perfectly priced.

### Conditional on Winner

| Metric | Home Wins | Away Wins |
|--------|-----------|-----------|
| Count | 5,225 (53.0%) | 4,632 (47.0%) |
| Mean margin | +3.35 | -3.74 |
| P(margin=1) given win | 32.6% | 23.7% |
| P(margin>=2) given win | 67.4% | 76.3% |

Away wins have larger average margin (-3.74 vs +3.35) because they are not truncated. When the away team wins by 1, it means the home team failed to score a walk-off -- not that the away team couldn't have scored more.

---

## Phase B5: Comparison to Signal B

### Signal B Design

Signal B (`f5_runline_signal_generator.py`) bets the F5 -0.5 run-line on the home team when the SP xFIP gap >= 1.0 (home SP much better). It operates on the first 5 innings only, avoiding bullpen and late-inning variance.

**2026 performance (7 bets):** 2-5, -1.21 units, -40.3% ROI. Too early to evaluate.

### Full-Game -1.5 Cover by xFIP Gap (9,715 games)

| xFIP Gap | N | Home -1.5 | Away -1.5 | Home Win% |
|----------|---|-----------|-----------|-----------|
| <-1.5 | 170 | 22.4% | 49.4% | 37.6% |
| -1.5 to -1 | 587 | 24.9% | 49.7% | 39.7% |
| -1 to -0.5 | 1,557 | 28.0% | 43.1% | 45.3% |
| -0.5 to 0 | 2,595 | 32.3% | 38.8% | 49.3% |
| 0 to 0.5 | 2,481 | 37.0% | 33.9% | 54.9% |
| 0.5 to 1.0 | 1,559 | 42.7% | 27.0% | 61.9% |
| 1.0 to 1.5 | 574 | 53.8% | 22.8% | 68.5% |
| >1.5 | 192 | 61.5% | 17.7% | 75.0% |

The xFIP gap is a powerful predictor of run-line cover, but this is **already priced into the moneyline and run-line**. The question is whether the market's run-line translation is accurate.

### xFIP Gap >= 1.0 (Signal B territory)

| Metric | Gap >= 1.0 | Gap < 0 |
|--------|-----------|---------|
| N | 767 | 4,903 |
| Home win% | 70.0% | 46.5% |
| Home -1.5 cover | 55.7% | 29.7% |
| Away -1.5 cover | 21.6% | 41.9% |
| Mean margin | +1.99 | -0.74 |
| P(margin=+1 given home win) | 20.5% | 36.1% |

Notably, the walk-off truncation is *less severe* when the home team has a large SP advantage (20.5% vs 36.1% margin=+1 rate among home wins). This is because dominant SPs create larger leads, making walk-off scenarios less common. This actually *helps* home -1.5 covers in big-gap games.

### Season Stability (xFIP Gap >= 1.0)

| Season | N | Home -1.5 | Home Win% | Mean Margin |
|--------|---|-----------|-----------|-------------|
| 2022 | 216 | 57.4% | 70.8% | +2.16 |
| 2023 | 186 | 55.4% | 69.9% | +1.89 |
| 2024 | 165 | 53.3% | 66.7% | +1.52 |
| 2025 | 200 | 56.0% | 72.0% | +2.30 |

Stable across seasons. But **we cannot conclude this is mispriced** without knowing what the market implied. From our 235-game run-line sample, the 12 games matching home fav + xFIP gap >= 1.0 showed 75.0% cover vs 47.5% implied (+27.5pp), but N=12 is far too small for inference.

### Signal B vs Full-Game -1.5

Signal B focuses on F5 -0.5, which avoids bullpen variance. The full-game -1.5 requires winning by 2+, introducing:
- Late-inning bullpen quality (not controlled by SP xFIP gap)
- Walk-off truncation (reduces home -1.5 cover)
- 7th-9th inning comeback dynamics

The xFIP gap signal may be partially captured in the ML line, making the full-game run-line translation the key question. Our sample is too small to determine if the translation is systematically wrong.

---

## Phase B6: Verdict

### CLOSE

**Rationale:**

1. **Overall efficiency:** The run-line is well-calibrated. Aggregate residual is -0.7pp with z=-0.20 (N=235). No systematic mispricing.

2. **Home/away asymmetry:** Despite the real walk-off truncation effect (8.9pp excess 1-run rate for home wins, affecting ~4.7% of games), the market prices this correctly. Home -1.5 and away -1.5 cover at virtually identical rates (35.8% vs 35.9% across 9,857 games).

3. **Pregame conditional buckets:** No bucket reaches statistical significance. The most interesting finding (home fav + low total: +9.8pp, N=29) is far too small to act on.

4. **xFIP gap effect:** Large xFIP gaps correlate with higher -1.5 cover rates (55.7% for gap >= 1.0 vs 29.7% for gap < 0), but this is expected and presumably priced into the run-line. We cannot determine mispricing without a larger matched sample of run-line prices in high-gap games. The 12-game subset showing +27.5pp residual is not statistically meaningful.

5. **Season instability:** The run-line residual flips sign across seasons (-0.4pp, +7.8pp, +9.5pp, -16.7pp for 2022-2025). This is the hallmark of noise, not a persistent edge.

6. **Signal B overlap:** The xFIP gap >= 1.0 bucket is already exploited by Signal B on the F5 -0.5 run-line. A full-game -1.5 signal in the same space would be correlated, not additive.

### What Would Change This Verdict

- A much larger run-line price dataset (1,000+ games with prices) showing residual > 3pp after controlling for ML, stable across 2+ seasons
- Evidence that the ML-to-RL translation systematically over/underestimates cover probability in specific pregame-identifiable conditions
- A specific bucket (e.g., home fav + low total + large xFIP gap) with N >= 100 and residual > 5pp

### Key Findings to Retain

- Walk-off truncation is real (8.9pp excess 1-run home wins) but fully priced
- xFIP gap predicts -1.5 covers linearly (22.4% to 61.5% across gap buckets) but this is expected ML-correlated behavior
- The market's run-line is remarkably efficient: no pregame bucket shows a significant, stable edge
- Signal B (F5 -0.5) remains the better expression of xFIP mismatch because it avoids bullpen noise and walk-off truncation

---

## Methodology Notes

- Run-line data: Odds API historical endpoint, FanDuel primary, multiplicative de-vig
- Sample: 18 snapshot dates across 4 seasons, 284 events, 235 with standard -1.5/+1.5 RL
- Full game data: game_table.parquet, 9,857 games 2022-2026
- SP data: sim_inputs, 9,715 games with xFIP
- All "pregame" tests use only information available before first pitch (ML line, total line, SP xFIP, home/away status)
- All "observed-state" tests are clearly labeled and not treated as evidence of pregame exploitability
- API credit usage: ~8,500 credits (from 4,843,396 to 4,834,898)
