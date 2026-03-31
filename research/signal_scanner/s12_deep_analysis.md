# S12 Deep Analysis — combined_pitcher_score

Formula: `(home_csw + away_csw)/2 - 5*(home_xfip + away_xfip)/2`
Dataset: 4666 non-push games (2024+2025)

## 1. Season Stability
- 2024: coef=+0.009199, p=0.0081
- 2025: coef=+0.008374, p=0.0098
- Same sign: True

## 2. Decile Analysis
- Monotonic: No

## 3. Market Correlation
- corr(S12, close_total) = -0.4255
- S12 after controlling for close_total: p=0.0000

## 4. Robustness
- Full model S12 p=0.0001

## 5. V1 Independence
- S12 after V1 control: p=0.0259

## 6. Threshold Sensitivity
See console output for full table.

## 7. Verdict: **ADVANCE**
- Season stable: True
- Not absorbed: True
- Robust: True
- Incremental: True
- Score: 4/4
