# Phase 1A: PIT Team Ratings Report

## PIT Definition

Rating for (season s, week w) uses plays from season s, weeks < w,
plus season s−1 all weeks as a regressed prior. Week 1 = prior only.
Shrink target is ALWAYS the s−1 league mean, never the current season's.
2020 is the prior for 2021; 2020 ratings are not written or evaluated.

Assertion test (FIX 5): ratings built from full data vs a frame truncated
at 2023 wk 10 match to 1e-9 for team, QB, kicker, and situational PROE.

## Chosen Parameters

- half_life: inf games
- prior_weight: 0.3
- k (shrinkage): 100 plays
- prior_regression: 0.5
- Tuned on: 2021–2024 ONLY. No row from 2025 or 2026 touched the tuning.

## Tuning Surface

Rolling-origin evaluation: each week-w rating predicts that week's actual
EPA/play using only prior data. Same 45-point pre-registered grid.

The RMSE surface is flat (range 0.2594–0.2624) because
single-game EPA/play is noise-dominated: SD of actual game pass EPA/play =
0.204, while SD of week-18 pass_off ratings = 0.087.
The signal-to-noise ratio is ~0.43. The chosen
parameters are kept as frozen. No row from 2025 or 2026 touched the tuning.

## Grid Results (sorted by RMSE)

| half_life | prior_wt | k | mean_RMSE | pass_RMSE | rush_RMSE |
|---|---|---|---|---|---|
| inf | 0.3 | 100 | 0.2594 | 0.3091 | 0.2098 |
| 12 | 0.3 | 100 | 0.2594 | 0.3091 | 0.2098 |
| 8 | 0.3 | 100 | 0.2595 | 0.3091 | 0.2099 |
| inf | 0.3 | 200 | 0.2595 | 0.3092 | 0.2098 |
| inf | 0.5 | 100 | 0.2596 | 0.3093 | 0.2099 |
| 6 | 0.3 | 100 | 0.2596 | 0.3092 | 0.2100 |
| 12 | 0.5 | 100 | 0.2597 | 0.3094 | 0.2100 |
| 12 | 0.3 | 200 | 0.2597 | 0.3095 | 0.2100 |
| 8 | 0.5 | 100 | 0.2597 | 0.3094 | 0.2101 |
| 6 | 0.5 | 100 | 0.2598 | 0.3095 | 0.2101 |
| 4 | 0.3 | 100 | 0.2598 | 0.3094 | 0.2102 |
| 8 | 0.3 | 200 | 0.2599 | 0.3096 | 0.2102 |
| inf | 0.5 | 200 | 0.2600 | 0.3099 | 0.2101 |
| 4 | 0.5 | 100 | 0.2600 | 0.3097 | 0.2103 |
| 6 | 0.3 | 200 | 0.2601 | 0.3098 | 0.2103 |
(showing top 15 of 45)

## RMSE by Season (Check 5)

| Season | Pass RMSE | Rush RMSE | Mean |
|---|---|---|---|
| 2021 | 0.3311 | 0.1952 | 0.2631 |
| 2022 | 0.2761 | 0.2251 | 0.2506 |
| 2023 | 0.3087 | 0.2057 | 0.2572 |
| 2024 | 0.3177 | 0.2120 | 0.2649 |

Weeks 1–4 pass RMSE: 0.3182
Weeks 5–18 pass RMSE: 0.3064

## Check 1b: QB Caveat

- Team-games with any second passer: 767 / 3416 (22.5%)
- Starter changed or shared (primary passer < 80% of dropbacks): 196 / 3416 (5.7%)

## Situational PROE

pass_oe is in nflverse units: percentage points above league expected pass rate.
Buckets: down (1/2/3/4) × distance (short ≤3, med 4–7, long 8+) × score state
(trail9+ / within8 / lead9+) × clock (Q1-3 / Q4). Written to
`nfl/data/sim/ratings/tendencies_situational_weekly.parquet`.

## Face Validity: Week 18 Ratings (2021–2024)

**2021 pass_off (wk 18):**
- Best 5: GB (0.185), KC (0.163), TB (0.149), SF (0.122), BUF (0.118)
- Worst 5: CHI (-0.067), JAX (-0.072), NYJ (-0.075), NYG (-0.111), CAR (-0.113)

**2021 rush_off (wk 18):**
- Best 5: IND (0.064), BUF (0.050), CLE (0.049), PHI (0.047), KC (0.040)
- Worst 5: LV (-0.066), DET (-0.067), MIA (-0.096), HOU (-0.103), ATL (-0.103)

**2021 pass_def (wk 18):**
- Best 5 (lowest EPA allowed): BUF (-0.077), DAL (-0.072), TB (-0.045), NO (-0.040), NE (-0.038)
- Worst 5 (highest EPA allowed): NYJ (0.184), JAX (0.179), DET (0.163), LV (0.118), HOU (0.116)

**2021 rush_def (wk 18):**
- Best 5 (lowest EPA allowed): NO (-0.095), LA (-0.064), ARI (-0.061), BAL (-0.058), SEA (-0.055)
- Worst 5 (highest EPA allowed): GB (0.056), JAX (0.034), MIN (0.027), DET (0.023), PIT (0.023)

**2022 pass_off (wk 18):**
- Best 5: KC (0.192), SF (0.124), CIN (0.108), BUF (0.107), DET (0.093)
- Worst 5: DEN (-0.074), NYJ (-0.086), IND (-0.097), HOU (-0.143), CHI (-0.144)

**2022 rush_off (wk 18):**
- Best 5: PHI (0.090), BUF (0.068), CHI (0.052), BAL (0.048), CLE (0.045)
- Worst 5: MIN (-0.072), NO (-0.075), IND (-0.090), TB (-0.114), HOU (-0.119)

**2022 pass_def (wk 18):**
- Best 5 (lowest EPA allowed): NE (-0.080), DAL (-0.076), PHI (-0.073), SF (-0.058), DEN (-0.049)
- Worst 5 (highest EPA allowed): ATL (0.117), LV (0.093), CHI (0.086), DET (0.064), PIT (0.060)

**2022 rush_def (wk 18):**
- Best 5 (lowest EPA allowed): SF (-0.089), TEN (-0.059), BUF (-0.057), DAL (-0.051), BAL (-0.048)
- Worst 5 (highest EPA allowed): DET (0.076), GB (0.057), NYG (0.053), CLE (0.051), CHI (0.049)

**2023 pass_off (wk 18):**
- Best 5: SF (0.183), MIA (0.112), DAL (0.090), BUF (0.088), DET (0.085)
- Worst 5: NYG (-0.133), ARI (-0.141), NE (-0.145), CAR (-0.159), NYJ (-0.193)

**2023 rush_off (wk 18):**
- Best 5: BUF (0.065), CHI (0.047), BAL (0.042), PHI (0.039), SF (0.034)
- Worst 5: NYG (-0.074), LAC (-0.093), HOU (-0.103), NYJ (-0.108), TB (-0.109)

**2023 pass_def (wk 18):**
- Best 5 (lowest EPA allowed): CLE (-0.155), BAL (-0.124), SF (-0.099), DAL (-0.092), NO (-0.088)
- Worst 5 (highest EPA allowed): ARI (0.090), WAS (0.070), TEN (0.063), CIN (0.032), TB (0.029)

**2023 rush_def (wk 18):**
- Best 5 (lowest EPA allowed): NE (-0.097), HOU (-0.079), ATL (-0.071), TEN (-0.069), TB (-0.062)
- Worst 5 (highest EPA allowed): PHI (0.037), SEA (0.033), NYG (0.028), CAR (0.017), ARI (0.007)

**2024 pass_off (wk 18):**
- Best 5: BAL (0.205), DET (0.187), BUF (0.171), GB (0.109), TB (0.107)
- Worst 5: TEN (-0.096), NE (-0.115), NYG (-0.118), CAR (-0.130), CLE (-0.176)

**2024 rush_off (wk 18):**
- Best 5: BUF (0.080), PHI (0.075), WAS (0.071), BAL (0.061), DET (0.022)
- Worst 5: DAL (-0.075), NYJ (-0.078), HOU (-0.095), MIA (-0.122), LV (-0.162)

**2024 pass_def (wk 18):**
- Best 5 (lowest EPA allowed): DEN (-0.064), HOU (-0.049), PHI (-0.043), LAC (-0.040), MIN (-0.037)
- Worst 5 (highest EPA allowed): JAX (0.118), CAR (0.090), NE (0.083), ARI (0.055), NYG (0.045)

**2024 rush_def (wk 18):**
- Best 5 (lowest EPA allowed): MIN (-0.109), BAL (-0.092), DEN (-0.072), PHI (-0.071), MIA (-0.070)
- Worst 5 (highest EPA allowed): CAR (0.079), DAL (0.057), NO (0.039), ARI (0.022), CIN (0.016)

## Rating Distributions (week 18)

| Season | Unit | Mean | SD | Min | Max |
|---|---|---|---|---|---|
| 2021 | pass_off | 0.035 | 0.080 | -0.113 | 0.185 |
| 2021 | rush_off | -0.015 | 0.047 | -0.103 | 0.064 |
| 2021 | pass_def | 0.037 | 0.069 | -0.077 | 0.184 |
| 2021 | rush_def | -0.014 | 0.035 | -0.095 | 0.056 |
| 2022 | pass_off | 0.004 | 0.077 | -0.144 | 0.192 |
| 2022 | rush_off | -0.014 | 0.050 | -0.119 | 0.090 |
| 2022 | pass_def | 0.008 | 0.050 | -0.080 | 0.117 |
| 2022 | rush_def | -0.012 | 0.039 | -0.089 | 0.076 |
| 2023 | pass_off | -0.016 | 0.091 | -0.193 | 0.183 |
| 2023 | rush_off | -0.029 | 0.048 | -0.109 | 0.065 |
| 2023 | pass_def | -0.016 | 0.057 | -0.155 | 0.090 |
| 2023 | rush_def | -0.027 | 0.033 | -0.097 | 0.037 |
| 2024 | pass_off | 0.010 | 0.095 | -0.176 | 0.205 |
| 2024 | rush_off | -0.029 | 0.055 | -0.162 | 0.080 |
| 2024 | pass_def | 0.008 | 0.042 | -0.064 | 0.118 |
| 2024 | rush_def | -0.028 | 0.042 | -0.109 | 0.079 |
