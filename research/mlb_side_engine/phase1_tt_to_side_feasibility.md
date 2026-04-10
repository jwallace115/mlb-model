# Phase 1: TT-to-Side Feasibility Report

## Methodology

**Objective**: Test whether Team Total (TT) fair values contain side (moneyline) information
not already absorbed by ML closing prices.

**Data**:
- Total games in master table: 9510
- Calibration (2022-2023): 4720
- Out-of-sample (2024-2025): 4790
- Distribution model selected: Poisson (lower Brier on calibration)
  - Poisson cal Brier: 0.271561
  - NB cal Brier: 0.527966

**Point-in-time ERA**: For each game, starter ERA computed from all prior starts in that
season only (strict < game_date). First start of season gets league-average 4.50.
Games with both SP ERA available: 8406 / 9510

**TT fair value formula**:
```
sp_adj_home = (away_sp_era - 4.50) * 0.621
sp_adj_away = (home_sp_era - 4.50) * 0.621
fair_home = total * 0.5015 - 0.248 + sp_adj_home
fair_away = total * (1 - 0.5015) + sp_adj_away
```

**Side translation**: Independent Poisson/NB -> P(home wins) = sum P(h>a) + 0.5*P(tie)

**Combination**: Logistic regression on (p_home_ml, p_home_tt), trained 2022-2023, applied 2024-2025

## Stage 1: Aggregate Results

| Period | N | Brier_ML | Brier_TT | Brier_Combo | Brier_Delta | LL_ML | LL_TT | LL_Combo | LL_Delta |
|--------|---|----------|----------|-------------|-------------|-------|-------|----------|----------|
| Cal 2022-2023 | 4720 | 0.239960 | 0.271561 | 0.239944 | +0.000016 | 0.672737 | 0.753394 | 0.672701 | +0.000036 |
| OOS 2024-2025 | 4790 | 0.241874 | 0.274903 | 0.241945 | -0.000071 | 0.676510 | 0.760212 | 0.676665 | -0.000155 |
| OOS 2024 | 2392 | 0.241310 | 0.271426 | 0.241280 | +0.000030 | 0.675499 | 0.750775 | 0.675419 | +0.000080 |
| OOS 2025 | 2398 | 0.242436 | 0.278372 | 0.242608 | -0.000172 | 0.677519 | 0.769625 | 0.677908 | -0.000389 |

**Logistic combo weights**: ML=4.0098, TT=0.0471, intercept=-2.0326
**TT weight share**: 1.2%
**OOS information gain**: -0.000224 bits/game

## Stage 2: Conditional Bucket Tests (OOS 2024-2025)

### A. SP ERA Gap

| Bucket | N | Brier_ML | Brier_Combo | Delta | LL_ML | LL_Combo | LL_Delta |
|--------|---|----------|-------------|-------|-------|----------|----------|
| Large (>1.5) | 2185 | 0.240524 | 0.240553 | -0.000030 | 0.673746 | 0.673825 | -0.000079 |
| Medium (0.75-1.5) | 1117 | 0.242891 | 0.243072 | -0.000181 | 0.678469 | 0.678878 | -0.000410 |
| Small (<0.75) | 1486 | 0.243143 | 0.243184 | -0.000041 | 0.679204 | 0.679264 | -0.000060 |

Season stability:
- 2024 Large (>1.5): N=1043, Brier delta=+0.000179
- 2024 Medium (0.75-1.5): N=563, Brier delta=-0.000147
- 2024 Small (<0.75): N=785, Brier delta=-0.000031
- 2025 Large (>1.5): N=1142, Brier delta=-0.000220
- 2025 Medium (0.75-1.5): N=554, Brier delta=-0.000217
- 2025 Small (<0.75): N=701, Brier delta=-0.000052

### B. Total Band

| Bucket | N | Brier_ML | Brier_Combo | Delta | LL_ML | LL_Combo | LL_Delta |
|--------|---|----------|-------------|-------|-------|----------|----------|
| High (>9.0) | 641 | 0.247763 | 0.247622 | +0.000142 | 0.688826 | 0.688444 | +0.000382 |
| Low (<7.5) | 1141 | 0.238161 | 0.238450 | -0.000288 | 0.668831 | 0.669478 | -0.000647 |
| Mid (7.5-9.0) | 3008 | 0.242027 | 0.242060 | -0.000034 | 0.676799 | 0.676882 | -0.000083 |

Season stability:
- 2024 High (>9.0): N=263, Brier delta=+0.000120
- 2024 Low (<7.5): N=623, Brier delta=+0.000009
- 2024 Mid (7.5-9.0): N=1506, Brier delta=+0.000024
- 2025 High (>9.0): N=378, Brier delta=+0.000157
- 2025 Low (<7.5): N=518, Brier delta=-0.000646
- 2025 Mid (7.5-9.0): N=1502, Brier delta=-0.000091

### C. ML Favorite Strength

| Bucket | N | Brier_ML | Brier_Combo | Delta | LL_ML | LL_Combo | LL_Delta |
|--------|---|----------|-------------|-------|-------|----------|----------|
| Heavy away | 96 | 0.196350 | 0.196485 | -0.000135 | 0.583837 | 0.583807 | +0.000030 |
| Heavy home | 425 | 0.204276 | 0.204795 | -0.000520 | 0.598349 | 0.599591 | -0.001241 |
| Mod away | 814 | 0.246090 | 0.246150 | -0.000061 | 0.685330 | 0.685452 | -0.000122 |
| Mod home | 1644 | 0.243183 | 0.243173 | +0.000011 | 0.679374 | 0.679357 | +0.000017 |
| Pick'em | 1811 | 0.250027 | 0.250067 | -0.000041 | 0.693201 | 0.693283 | -0.000081 |

Season stability:
- 2024 Heavy away: N=39, Brier delta=-0.000543
- 2024 Heavy home: N=190, Brier delta=+0.000157
- 2024 Mod away: N=421, Brier delta=+0.000094
- 2024 Mod home: N=854, Brier delta=-0.000027
- 2024 Pick'em: N=888, Brier delta=+0.000053
- 2025 Heavy away: N=57, Brier delta=+0.000144
- 2025 Heavy home: N=235, Brier delta=-0.001067
- 2025 Mod away: N=393, Brier delta=-0.000227
- 2025 Mod home: N=790, Brier delta=+0.000051
- 2025 Pick'em: N=923, Brier delta=-0.000131

### D. Home vs Away Favorite

| Bucket | N | Brier_ML | Brier_Combo | Delta | LL_ML | LL_Combo | LL_Delta |
|--------|---|----------|-------------|-------|-------|----------|----------|
| Away fav | 1726 | 0.245402 | 0.245460 | -0.000057 | 0.683842 | 0.683941 | -0.000099 |
| Home fav | 3064 | 0.239886 | 0.239965 | -0.000078 | 0.672380 | 0.672567 | -0.000187 |

Season stability:
- 2024 Away fav: N=858, Brier delta=+0.000081
- 2024 Home fav: N=1534, Brier delta=+0.000002
- 2025 Away fav: N=868, Brier delta=-0.000195
- 2025 Home fav: N=1530, Brier delta=-0.000159

### E. TT Disagreement Magnitude

| Bucket | N | Brier_ML | Brier_Combo | Delta | LL_ML | LL_Combo | LL_Delta |
|--------|---|----------|-------------|-------|-------|----------|----------|
| Large (top tercile) | 1581 | 0.240361 | 0.240396 | -0.000035 | 0.673538 | 0.673596 | -0.000059 |
| Medium | 1628 | 0.242088 | 0.242163 | -0.000075 | 0.676922 | 0.677091 | -0.000168 |
| Small (bottom tercile) | 1581 | 0.243165 | 0.243268 | -0.000103 | 0.679059 | 0.679297 | -0.000238 |

Season stability:
- 2024 Large (top tercile): N=789, Brier delta=+0.000175
- 2024 Medium: N=832, Brier delta=-0.000061
- 2024 Small (bottom tercile): N=771, Brier delta=-0.000019
- 2025 Large (top tercile): N=792, Brier delta=-0.000244
- 2025 Medium: N=796, Brier delta=-0.000089
- 2025 Small (bottom tercile): N=810, Brier delta=-0.000183

## Stage 3: Residual Structure

**Overall correlation** (ML residual vs TT disagreement): -0.0009

Correlation by ERA gap:
- Large (>1.5): -0.0012 (N=2185)
- Medium (0.75-1.5): 0.0158 (N=1117)
- Small (<0.75): -0.0079 (N=1486)

Correlation by total band:
- High (>9.0): 0.0048 (N=641)
- Low (<7.5): -0.0449 (N=1141)
- Mid (7.5-9.0): 0.0149 (N=3008)

**Correction direction test** (when ML picks wrong side, N=2058):
- TT disagreement points toward correction: 0.5777 (57.8%)
- By disagreement magnitude:
  - Bottom tercile: 0.5066 (50.7%, N=679)
  - Middle: 0.5757 (57.6%, N=700)
  - Top tercile: 0.6510 (65.1%, N=679)

## Stage 4: Information Gain Summary

- OOS Brier delta (ML -> ML+TT): -0.000071
- OOS log-loss delta: -0.000155 nats = -0.000224 bits/game
- TT weight share in combo: 1.2%

**Verdict**: NEGATIVE on aggregate scoring metrics. The logistic ML+TT combo is OOS-worse than ML alone
(Brier delta -0.000071, LL delta -0.000155 nats). TT weight share is 1.2% -- effectively zero.

However, the **correction direction test** is noteworthy: when ML picks the wrong side (N=2058),
TT disagreement points toward the correct outcome 57.8% of the time overall, rising to **65.1%
in the top tercile of disagreement magnitude** (N=679). This suggests TT contains directional
information about ML mispricing, but the signal is too noisy for a linear logistic combination
to extract reliably in OOS.

**Recommended action**: Do not build a standalone TT-to-side engine. The aggregate information
gain is zero-to-negative. The correction direction finding (65.1% top tercile) is interesting
but insufficient to overcome the noise floor in a probability-weighted framework. If a side
engine is pursued in the future, TT disagreement magnitude could serve as a filtering criterion
(flag games where TT strongly disagrees with ML) rather than as a probability adjustment input.

## Stage 5: Line Movement

No opening ML data in canonical parquet. Skipped.

## Limitations

1. Point-in-time ERA uses only current-season starts. First ~2 weeks of each season default to league-average ERA (4.50).
2. TT formula uses fixed constants (HOME_SHARE=0.5015, etc.) -- not optimized for side prediction.
3. Logistic combo trained on 2022-2023 only (in-sample). OOS is 2024-2025.
4. Team totals not available in canonical for 2022 (0 games) and sparse for 2023 (650 games).
   TT falls back to market total split for these games, which dilutes the TT signal in calibration.
5. No starter identity features -- only raw ERA, which is a noisy proxy for true quality.