# Phase 1A: PIT Team Ratings Report
## PIT Definition
Rating for (season s, week w) uses plays from season s, weeks < w,
plus season s-1 all weeks as a regressed prior. Week 1 = prior only.
Assertion test: KC 2023 wk10 pass_off — verified 0 plays from week >= 10.

## Chosen Parameters
- half_life: inf games
- prior_weight: 0.3
- k (shrinkage): 200 plays
- Tuned on: 2021-2024 ONLY. No row from 2025 or 2026 touched the tuning.

## Grid Results (sorted by RMSE)

| half_life | prior_wt | k | mean_RMSE | pass_RMSE | rush_RMSE |
|---|---|---|---|---|---|
| inf | 0.3 | 200 | 0.2591 | 0.3087 | 0.2094 |
| 12 | 0.3 | 100 | 0.2591 | 0.3086 | 0.2096 |
| inf | 0.3 | 100 | 0.2591 | 0.3087 | 0.2095 |
| 8 | 0.3 | 100 | 0.2591 | 0.3087 | 0.2096 |
| 6 | 0.3 | 100 | 0.2592 | 0.3087 | 0.2097 |
| 12 | 0.3 | 200 | 0.2592 | 0.3089 | 0.2096 |
| inf | 0.5 | 100 | 0.2593 | 0.3089 | 0.2096 |
| 12 | 0.5 | 100 | 0.2593 | 0.3090 | 0.2097 |
| 8 | 0.3 | 200 | 0.2594 | 0.3090 | 0.2097 |
| 8 | 0.5 | 100 | 0.2594 | 0.3090 | 0.2098 |
| 4 | 0.3 | 100 | 0.2594 | 0.3090 | 0.2099 |
| 6 | 0.5 | 100 | 0.2595 | 0.3091 | 0.2098 |
| 6 | 0.3 | 200 | 0.2595 | 0.3092 | 0.2099 |
| inf | 0.5 | 200 | 0.2596 | 0.3094 | 0.2098 |
| 4 | 0.5 | 100 | 0.2596 | 0.3093 | 0.2100 |
(showing top 15 of 45)

## RMSE by Season (Check 5)

| Season | Pass RMSE | Rush RMSE | Mean |
|---|---|---|---|
| 2021 | 0.3313 | 0.1956 | 0.2635 |
| 2022 | 0.2753 | 0.2251 | 0.2502 |
| 2023 | 0.3094 | 0.2035 | 0.2564 |
| 2024 | 0.3159 | 0.2125 | 0.2642 |

Weeks 1-4 pass RMSE: 0.3178
Weeks 5-18 pass RMSE: 0.3060

## Check 1b: QB Caveat
Team-games where primary passer changed mid-game: 634 / 2852 (22.2%)

## Face Validity: Week-18 Ratings (2021-2024)

**2021 pass_off (wk 22):**
- Top 5: KC (0.122), LA (0.119), GB (0.102), TB (0.097), DAL (0.095)
- Bot 5: HOU (-0.055), NYJ (-0.059), CHI (-0.070), NYG (-0.102), CAR (-0.103)

**2021 pass_def (wk 22):**
- Top 5: NYJ (0.126), JAX (0.108), BAL (0.095), DET (0.092), LV (0.089)
- Bot 5: NE (-0.023), TB (-0.031), NO (-0.040), BUF (-0.058), DAL (-0.069)

**2021 rush_off (wk 22):**
- Top 5: BUF (0.055), IND (0.042), PHI (0.036), CLE (0.032), KC (0.026)
- Bot 5: LV (-0.053), MIA (-0.072), LA (-0.075), ATL (-0.078), HOU (-0.083)

**2021 rush_def (wk 22):**
- Top 5: GB (0.021), LAC (0.016), PIT (0.011), CLE (0.009), JAX (0.008)
- Bot 5: BAL (-0.050), LV (-0.053), ARI (-0.053), TB (-0.059), NO (-0.071)

**2022 pass_off (wk 22):**
- Top 5: KC (0.167), SF (0.114), CIN (0.083), DET (0.077), BUF (0.077)
- Bot 5: CAR (-0.081), NYJ (-0.082), IND (-0.097), HOU (-0.121), CHI (-0.136)

**2022 pass_def (wk 22):**
- Top 5: ATL (0.089), CHI (0.086), LV (0.077), DET (0.047), JAX (0.043)
- Bot 5: NO (-0.059), SF (-0.064), NE (-0.067), DAL (-0.073), PHI (-0.083)

**2022 rush_off (wk 22):**
- Top 5: PHI (0.095), BUF (0.057), CHI (0.046), CLE (0.044), KC (0.039)
- Bot 5: IND (-0.058), MIN (-0.060), NO (-0.063), TB (-0.089), HOU (-0.112)

**2022 rush_def (wk 22):**
- Top 5: NYG (0.063), DET (0.060), GB (0.052), LAC (0.048), CLE (0.038)
- Bot 5: DAL (-0.045), BUF (-0.045), WAS (-0.051), SF (-0.057), TEN (-0.058)

**2023 pass_off (wk 22):**
- Top 5: SF (0.155), DET (0.092), DAL (0.082), GB (0.078), BUF (0.076)
- Bot 5: ARI (-0.114), CLE (-0.118), NE (-0.151), CAR (-0.154), NYJ (-0.182)

**2023 pass_def (wk 22):**
- Top 5: ARI (0.076), WAS (0.071), TEN (0.050), DET (0.033), SEA (0.029)
- Bot 5: NO (-0.084), KC (-0.088), NYJ (-0.100), BAL (-0.102), CLE (-0.121)

**2023 rush_off (wk 22):**
- Top 5: BUF (0.053), CHI (0.026), SF (0.025), BAL (0.024), PHI (0.021)
- Bot 5: JAX (-0.079), LAC (-0.091), TB (-0.099), NYJ (-0.102), HOU (-0.113)

**2023 rush_def (wk 22):**
- Top 5: NYG (0.016), SEA (0.016), PHI (0.013), GB (0.004), CAR (0.002)
- Bot 5: TB (-0.064), DAL (-0.065), ATL (-0.070), TEN (-0.079), NE (-0.095)

**2024 pass_off (wk 22):**
- Top 5: BAL (0.183), DET (0.159), BUF (0.158), TB (0.121), SF (0.105)
- Bot 5: CHI (-0.065), NE (-0.082), CAR (-0.083), NYG (-0.100), CLE (-0.156)

**2024 pass_def (wk 22):**
- Top 5: JAX (0.104), CAR (0.091), NE (0.079), ARI (0.064), WAS (0.062)
- Bot 5: GB (-0.018), LAC (-0.026), PHI (-0.030), DEN (-0.036), HOU (-0.042)

**2024 rush_off (wk 22):**
- Top 5: BUF (0.079), BAL (0.074), PHI (0.071), WAS (0.058), DET (0.033)
- Bot 5: NYJ (-0.057), HOU (-0.059), TEN (-0.060), MIA (-0.091), LV (-0.129)

**2024 rush_def (wk 22):**
- Top 5: CAR (0.087), DAL (0.057), NO (0.040), SF (0.023), ARI (0.021)
- Bot 5: DEN (-0.048), PHI (-0.050), HOU (-0.052), BAL (-0.069), MIN (-0.083)

## Rating Distributions (week 18)

| Season | Unit | Mean | SD | Min | Max |
|---|---|---|---|---|---|
| 2021 | pass_off | 0.019 | 0.065 | -0.103 | 0.122 |
| 2021 | rush_off | -0.019 | 0.036 | -0.083 | 0.055 |
| 2021 | pass_def | 0.024 | 0.050 | -0.069 | 0.126 |
| 2021 | rush_def | -0.018 | 0.026 | -0.071 | 0.021 |
| 2022 | pass_off | -0.004 | 0.068 | -0.136 | 0.167 |
| 2022 | rush_off | -0.011 | 0.043 | -0.112 | 0.095 |
| 2022 | pass_def | 0.002 | 0.045 | -0.083 | 0.089 |
| 2022 | rush_def | -0.009 | 0.035 | -0.058 | 0.063 |
| 2023 | pass_off | -0.018 | 0.082 | -0.182 | 0.155 |
| 2023 | rush_off | -0.038 | 0.042 | -0.113 | 0.053 |
| 2023 | pass_def | -0.015 | 0.050 | -0.121 | 0.076 |
| 2023 | rush_def | -0.035 | 0.029 | -0.095 | 0.016 |
| 2024 | pass_off | 0.019 | 0.081 | -0.156 | 0.183 |
| 2024 | rush_off | -0.018 | 0.047 | -0.129 | 0.079 |
| 2024 | pass_def | 0.020 | 0.037 | -0.042 | 0.104 |
| 2024 | rush_def | -0.015 | 0.036 | -0.083 | 0.087 |
