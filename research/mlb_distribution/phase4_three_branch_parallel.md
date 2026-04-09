# Phase 4: Three-Branch Parallel Investigation
## Distribution Shape Drivers in MLB Totals

Date: 2026-04-08
Dataset: 9,715 games (2022-2025), 19,430 starter appearances, 63,612 reliever appearances

---

## Branch 1 -- Park as Conditional Distribution Shape

### 1A: Negative-Binomial Fit per Park

Fit overdispersion ratio (variance / mean) to game totals per venue (min 100 games).

**Top 5 fat-tailed parks (highest shape_ratio):**

| Rank | Venue                     | Shape Ratio | Mean  | Variance | N   |
|------|---------------------------|-------------|-------|----------|-----|
| 1    | Oakland Coliseum          | 2.713       | 8.51  | 23.08    | 242 |
| 2    | Wrigley Field             | 2.597       | 8.55  | 22.21    | 322 |
| 3    | Guaranteed Rate Field     | 2.532       | 8.72  | 22.08    | 243 |
| 4    | Kauffman Stadium          | 2.488       | 8.94  | 22.24    | 324 |
| 5    | Oriole Park at Camden Yds | 2.477       | 8.80  | 21.80    | 323 |

**Top 5 compressed parks (lowest shape_ratio):**

| Rank | Venue                | Shape Ratio | Mean  | Variance | N   |
|------|----------------------|-------------|-------|----------|-----|
| 1    | Rogers Centre        | 1.787       | 8.90  | 15.90    | 324 |
| 2    | Dodger Stadium       | 1.836       | 9.14  | 16.79    | 323 |
| 3    | T-Mobile Park        | 1.837       | 7.73  | 14.20    | 324 |
| 4    | Progressive Field    | 1.893       | 8.13  | 15.40    | 323 |
| 5    | American Family Field | 1.906       | 8.52  | 16.24    | 324 |

Key observation: Shape ratio ranges from 1.787 to 2.713 -- a 52% spread. This is not merely a mean shift; parks generate structurally different distributions. Oakland Coliseum and Rogers Centre have nearly identical means (~8.5-8.9) but wildly different variances (23.1 vs 15.9). Coors Field (shape_ratio=2.367) is notably NOT the most fat-tailed park -- its high variance is partly explained by its high mean (11.4).

### 1B: Tail Frequencies by Park Tier

Parks split into terciles by shape_ratio:

| Tier   | N     | Mean | Std  | P(<=4) | P(13+) | P(16+) |
|--------|-------|------|------|--------|--------|--------|
| HIGH   | 3,068 | 9.09 | 4.80 | 0.158  | 0.224  | 0.101  |
| NORMAL | 3,234 | 8.96 | 4.52 | 0.144  | 0.205  | 0.084  |
| LOW    | 3,072 | 8.54 | 4.08 | 0.149  | 0.171  | 0.058  |

**Critical finding:** P(16+) is 10.1% in HIGH parks vs 5.8% in LOW parks -- a 74% relative increase in extreme-over probability. This is a substantial tail effect that a Gaussian or fixed-sigma model completely misses. The means differ by only 0.55 runs, but the tail probabilities differ by 4.3 percentage points.

### 1C: Alt-Total Data Needs

Alt-total pricing (e.g., over 10.5 at +180) would directly validate whether the market already prices park-specific shape. Required data: alt-total lines by book by venue, matched to outcomes. Not currently available in our pipeline. Would need Odds API `alternate_totals` market or a specialized feed.

### 1D: Year-to-Year Stability

| Period      | Correlation | N Parks |
|-------------|-------------|---------|
| 2022 vs 2023 | r = -0.009 | 26      |
| 2023 vs 2024 | r = +0.048 | 26      |
| 2024 vs 2025 | r = +0.300 | 26      |
| Pooled       | r = +0.018 | 78      |

**Verdict: Park shape_ratio is NOT stable year-to-year.** The pooled consecutive-year correlation is essentially zero (r=0.018). The single elevated pair (2024-2025 at r=0.300) is likely noise with n=26. This means park overdispersion is driven more by which pitchers/teams play there in a given season than by the venue itself.

**Implication:** A fixed park-shape parameter would overfit. If park shape is used at all, it must be computed as a rolling/expanding window within-season, not as a historical constant.

---

## Branch 2 -- Pitcher Outcome-Shape Typing

### 2A: Pitcher Archetypes

330 pitchers with >= 15 starts classified by variance and P(runs >= 6):
- LOW_VAR: 88 pitchers (bottom tercile of both variance and blowup rate)
- NORMAL: 132 pitchers
- HIGH_VAR: 110 pitchers

**Notable pitcher classifications:**

| Pitcher             | Archetype | Starts | Mean RA | Var  | P(<=1) | P(>=6) | CV   |
|---------------------|-----------|--------|---------|------|--------|--------|------|
| Paul Skenes         | LOW_VAR   | 55     | 1.38    | 1.80 | 0.56   | 0.00   | 0.97 |
| Shane McClanahan    | LOW_VAR   | 50     | 1.88    | 2.23 | 0.46   | 0.00   | 0.79 |
| Jacob deGrom        | LOW_VAR   | 50     | 1.84    | 2.34 | 0.44   | 0.00   | 0.83 |
| Shohei Ohtani       | LOW_VAR   | 65     | 1.69    | 3.44 | 0.61   | 0.03   | 1.09 |
| Tarik Skubal        | LOW_VAR   | 98     | 1.94    | 3.58 | 0.52   | 0.04   | 0.98 |
| Corbin Burnes       | LOW_VAR   | 108    | 2.31    | 3.45 | 0.38   | 0.07   | 0.81 |
| Clayton Kershaw     | LOW_VAR   | 75     | 1.87    | 2.90 | 0.52   | 0.03   | 0.91 |
| Chris Sale          | LOW_VAR   | 71     | 1.97    | 3.31 | 0.51   | 0.06   | 0.92 |
| Max Scherzer        | LOW_VAR   | 76     | 2.28    | 3.22 | 0.41   | 0.05   | 0.79 |
| Logan Webb          | LOW_VAR   | 132    | 2.46    | 3.00 | 0.33   | 0.07   | 0.70 |
| Gerrit Cole         | NORMAL    | 83     | 2.21    | 3.65 | 0.43   | 0.10   | 0.87 |
| Zack Wheeler        | NORMAL    | 114    | 2.14    | 3.77 | 0.47   | 0.08   | 0.91 |
| Framber Valdez      | NORMAL    | 121    | 2.47    | 4.02 | 0.39   | 0.11   | 0.81 |
| Justin Verlander    | NORMAL    | 101    | 2.34    | 4.37 | 0.43   | 0.12   | 0.89 |
| Dylan Cease         | NORMAL    | 130    | 2.49    | 4.38 | 0.42   | 0.09   | 0.84 |
| Aaron Nola          | HIGH_VAR  | 114    | 2.89    | 4.42 | 0.31   | 0.10   | 0.73 |
| Zac Gallen          | HIGH_VAR  | 126    | 2.49    | 4.46 | 0.40   | 0.11   | 0.85 |
| Shota Imanaga       | HIGH_VAR  | 53     | 2.42    | 5.17 | 0.41   | 0.09   | 0.94 |

The LOW_VAR group reads like an All-Star roster. Skenes (var=1.80) and deGrom (var=2.34) are the most outcome-compressed starters in the dataset.

### 2B: Matchup Type Distributions

| Matchup | N     | Mean  | Std  | Variance | P(<=4) | P(13+) | P(16+) |
|---------|-------|-------|------|----------|--------|--------|--------|
| LV_LV   | 404   | 8.00  | 3.95 | 15.64    | 0.173  | 0.126  | 0.042  |
| LV_NM   | 1,359 | 8.25  | 4.10 | 16.79    | 0.170  | 0.141  | 0.052  |
| NM_NM   | 1,033 | 8.63  | 4.38 | 19.17    | 0.144  | 0.182  | 0.071  |
| HV_NM   | 1,649 | 9.27  | 4.75 | 22.55    | 0.143  | 0.225  | 0.109  |
| HV_LV   | 1,056 | 8.83  | 4.48 | 20.03    | 0.158  | 0.204  | 0.080  |
| HV_HV   | 640   | 9.43  | 4.76 | 22.69    | 0.147  | 0.256  | 0.116  |

**Critical finding:** The variance gradient is massive. LV_LV games have variance=15.64 while HV_HV games have variance=22.69 -- a 45% increase. P(16+) ranges from 4.2% to 11.6%, nearly a 3x difference. The mean shift (8.00 to 9.43) is moderate, but the variance shift is the dominant effect.

The HV_LV mixup is informative: mean=8.83 (between the pure types) but variance=20.03 (closer to HV_HV than LV_LV). One high-variance pitcher in the matchup drags the distribution fat-tailed.

### 2C: Market Residuals by Matchup Type

| Matchup | N     | Mean Resid | Std Resid | Var Resid |
|---------|-------|------------|-----------|-----------|
| LV_LV   | 130   | -0.100     | 3.710     | 13.76     |
| LV_NM   | 549   | -0.114     | 3.888     | 15.11     |
| NM_NM   | 471   | +0.327     | 4.394     | 19.31     |
| HV_NM   | 711   | +0.757     | 4.639     | 21.52     |
| HV_LV   | 403   | +0.151     | 4.292     | 18.43     |
| HV_HV   | 267   | +1.124     | 4.808     | 23.11     |

**Two findings:**
1. **Variance of residuals scales with matchup type.** Var(resid) goes from 13.76 (LV_LV) to 23.11 (HV_HV) -- a 68% increase. The market does NOT fully adjust its implied sigma for pitcher archetype.
2. **Mean bias:** HV_HV games go over the closing line by +1.12 runs on average. The market under-prices high-variance matchups. This is a candidate signal for the model.

### 2D: Archetype Stability

157 pitchers appeared in both 2022-2023 and 2024-2025 with >= 10 starts per period.

**Same archetype retention: 47/157 = 29.9%**

Transition matrix (rows = early, columns = late):

|            | HIGH_VAR | LOW_VAR | NORMAL |
|------------|----------|---------|--------|
| HIGH_VAR   | 11       | 11      | 25     |
| LOW_VAR    | 11       | 13      | 14     |
| NORMAL     | 32       | 17      | 23     |

**Verdict: Pitcher archetypes are NOT stable across 2-year windows.** At 29.9% retention with 3 categories, this is barely above the 33% expected by chance. HIGH_VAR pitchers are especially unstable -- only 11/47 (23%) remain HIGH_VAR. This makes sense: a pitcher who gets blown up frequently either improves, gets injured, or loses their rotation spot.

**Implication:** Archetype must be computed as a rolling/expanding within-season measure, not a career label. A 15-start rolling window would be the minimum viable implementation.

---

## Branch 3 -- Bullpen Path-Tree Foundation

### 3A: Data Coverage

5,535 games with full starter + reliever data (57% of total). Reliever data includes innings_pitched, runs_allowed, strikeouts, batters_faced per appearance.

### 3B: Game-State Branch Classification

Classification rule based on BOTH starters' performance:
- CLOSE: Both starters 6+ IP with <= 2 runs
- BLOWOUT: Either starter < 5 IP with 4+ runs
- MODERATE: Everything else

| Branch   | N     | % of Games |
|----------|-------|------------|
| MODERATE | 3,441 | 62.2%      |
| BLOWOUT  | 1,585 | 28.6%      |
| CLOSE    | 509   | 9.2%       |

Branch characteristics:

| Branch   | Home Rel K% | Away Rel K% | Home Rel Runs/IP | Away Rel Runs/IP | Home # Rel | Away # Rel |
|----------|-------------|-------------|------------------|------------------|------------|------------|
| CLOSE    | 0.270       | 0.267       | 0.679            | 1.071            | 2.9        | 2.6        |
| MODERATE | 0.256       | 0.251       | 0.572            | 0.682            | 3.4        | 3.2        |
| BLOWOUT  | 0.237       | 0.235       | 0.578            | 0.658            | 3.6        | 3.4        |

**Finding:** Close games deploy higher-K-rate relievers (0.270 vs 0.237 -- a 14% gap). This confirms managers use their best arms in close games and mop-up relievers in blowouts.

**Paradox:** Despite better relievers, CLOSE games show HIGHER away runs/IP (1.071 vs 0.658). This is a selection effect -- close games have fewer reliever innings (4.5 total IP vs 7.9 in blowouts), so a single bad inning from a closer inflates the rate metric disproportionately.

### 3C: Reliever Run Environment by Branch

| Branch   | Rel Total Runs | Std  | Variance | Runs/IP | Total Rel IP | Game Total Mean | Game Total Std |
|----------|---------------|------|----------|---------|--------------|-----------------|----------------|
| CLOSE    | 2.57          | 2.24 | 5.01     | 0.611   | 4.50         | 4.46            | 2.52           |
| MODERATE | 3.44          | 2.96 | 8.75     | 0.558   | 6.34         | 7.86            | 3.67           |
| BLOWOUT  | 4.56          | 3.46 | 11.94    | 0.592   | 7.88         | 12.50           | 4.35           |

BLOWOUT games produce 77% more reliever runs than CLOSE games (4.56 vs 2.57), with 139% more variance (11.94 vs 5.01). But the runs/IP rates are surprisingly similar across branches (0.558-0.611), meaning the run expansion is primarily an exposure (innings) effect, not a rate-of-scoring effect.

### 3D: Blowout Quality Degradation

Runs/IP distribution by branch:

| Branch   | Median | P75   | P90   | P(zero) |
|----------|--------|-------|-------|---------|
| CLOSE    | 0.476  | 0.870 | 1.395 | 0.168   |
| MODERATE | 0.455  | 0.784 | 1.190 | 0.140   |
| BLOWOUT  | 0.492  | 0.825 | 1.232 | 0.075   |

**Key finding:** P(zero reliever runs) drops from 16.8% in CLOSE to 7.5% in BLOWOUT. This is the real mechanism -- in blowouts, there are simply more innings for the bullpen to allow runs, and the probability of a clean bullpen outing approaches zero. The rate does not spike dramatically, but the exposure time roughly doubles.

Game total distribution by branch:

| Branch   | Mean  | Std  | P(<=4) | P(13+) | P(16+) |
|----------|-------|------|--------|--------|--------|
| CLOSE    | 4.46  | 2.52 | 0.532  | 0.008  | 0.000  |
| MODERATE | 7.86  | 3.67 | 0.164  | 0.112  | 0.034  |
| BLOWOUT  | 12.50 | 4.35 | 0.006  | 0.459  | 0.215  |

Market residuals by branch:

| Branch   | N     | Mean Resid | Std Resid | Var Resid |
|----------|-------|------------|-----------|-----------|
| CLOSE    | 205   | -3.713     | 2.783     | 7.74      |
| MODERATE | 1,441 | -0.503     | 3.579     | 12.81     |
| BLOWOUT  | 685   | +3.712     | 4.444     | 19.75     |

**Critical finding:** The market's residual variance expands 2.5x from CLOSE (7.74) to BLOWOUT (19.75). This is expected since branch classification is done ex-post (we already know how the game went). The actionable question is whether we can predict the branch distribution ex-ante.

---

## Synthesis

### Q1: Highest Structural-Value Finding?

**Pitcher matchup archetype determines game-total variance more than park does.** HV_HV vs LV_LV games show a 45% variance spread (22.69 vs 15.64) with a 3x difference in P(16+). Park tier shows a similar but slightly smaller effect (HIGH vs LOW: 23.04 vs 16.65 variance, 74% spread in P(16+)). Both are larger effects than the mean shift, meaning a fixed-sigma model is leaving substantial edge on the table for tail bets.

### Q2: Most Architecture-Changing Result?

**Neither park shape nor pitcher archetype is stable year-to-year.** Park shape_ratio has r=0.018 pooled consecutive-year correlation. Pitcher archetype retention is 29.9% (barely above chance). This means any sigma-conditioning feature must be computed as a rolling/expanding within-season statistic, not a historical label. The architecture implication: the Phase 9 model's fixed sigma=4.361 cannot be replaced by a lookup table. It requires a live sigma prediction model that ingests current-season rolling features.

### Q3: Most Foundational Finding?

**The bullpen path-tree is primarily an exposure effect, not a rate effect.** Reliever runs/IP is similar across game states (0.56-0.61), but total reliever innings range from 4.5 (CLOSE) to 7.9 (BLOWOUT). The variance expansion is driven by how many innings the bullpen must cover, which is determined by starter performance. This means:
- Starter IP prediction is the key upstream variable for distribution shape
- Bullpen quality (K rate) matters mainly for determining which relievers absorb the extra innings
- A path-tree model should branch on predicted starter depth, not on bullpen quality

### Q4: Best for Derivative-Market Architecture?

**The HV_HV mean-residual finding (+1.12 runs vs closing line).** The market under-prices high-variance matchups by over a run on average. Combined with the 68% increase in residual variance (23.11 vs 13.76 for LV_LV), this suggests:
1. Over bets in HV_HV matchups have a positive mean bias AND wider distribution
2. Alt-over bets (e.g., over 12.5) in HV_HV matchups would compound both advantages
3. Under bets in LV_LV matchups have a compressed-distribution advantage (tighter outcomes around the line)

**Caution:** The +1.12 mean bias could partially reflect sample composition (HV pitchers may be tagged HV precisely because they had bad seasons in the closing-line sample period). The archetype instability finding (29.9% retention) supports this concern.

---

## Verdicts and Next Steps

| Branch | Signal Found? | Stable? | Actionable? | Priority |
|--------|---------------|---------|-------------|----------|
| Park shape | Yes -- 74% P(16+) spread | No (r=0.02) | Only if rolling | Low |
| Pitcher archetype | Yes -- 45% variance spread, +1.12 mean bias | No (30% retention) | Rolling within-season | **High** |
| Bullpen path-tree | Yes -- exposure effect confirmed | N/A (ex-post) | Needs starter IP prediction | Medium |

**Recommended next steps:**
1. Build a rolling (15-start window) pitcher variance feature and test as a sigma-conditioning input to the simulation model
2. Test whether adding a pitcher-variance interaction term to the Phase 9 Ridge model improves residual calibration
3. Acquire alt-total line data to directly validate whether the market already prices park/pitcher shape differences
4. Build a starter-IP prediction model as the upstream branch predictor for the path-tree architecture
