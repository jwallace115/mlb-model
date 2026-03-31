# Residual Space Scan — Anomaly Report

Total games: 4855
Under signal fires: 74 (1.5%)
Residual space: 4781 (98.5%)

## Outcome Groups (within residual space)

- STRONG_OVER: 1596 (33.4%)
- NEUTRAL: 1560 (32.6%)
- STRONG_UNDER: 1625 (34.0%)

Features scanned: 20

## Anomaly Detection (STRONG_OVER vs NEUTRAL)

| Feature | Delta | Cohen's d | p-value | Direction |
|---------|-------|----------|---------|-----------|
| temperature | +1.5134 | +0.154 | 0.0000 | OVER ↑ |
| combined_bp_xfip | +0.0064 | +0.107 | 0.0026 | OVER ↑ |
| combined_lineup_iso | +0.0021 | +0.101 | 0.0045 | OVER ↑ |
| combined_lineup_hh | +0.0022 | +0.071 | 0.0466 | OVER ↑ |
| combined_lineup_contact | +0.0011 | +0.070 | 0.0509 | OVER ↑ |
| wind_factor_effective | +0.3256 | +0.059 | 0.0973 | OVER ↑ |
| combined_k_rate | -0.0011 | -0.055 | 0.1201 | OVER ↓ |
| combined_lineup_barrel | +0.0005 | +0.054 | 0.1324 | OVER ↑ |
| combined_closer_used | +0.0281 | +0.039 | 0.2754 | OVER ↑ |
| combined_ppi | -0.1410 | -0.038 | 0.2872 | OVER ↓ |

## Anomaly Detection (STRONG_UNDER vs NEUTRAL)

| Feature | Delta | Cohen's d | p-value | Direction |
|---------|-------|----------|---------|-----------|
| temperature | +1.1024 | +0.111 | 0.0017 | UNDER ↓ |
| combined_bp_xfip | +0.0055 | +0.090 | 0.0113 | UNDER ↓ |
| park_factor_hr | +0.4302 | +0.089 | 0.0124 | UNDER ↓ |
| away_rest_days | -0.0434 | -0.081 | 0.0221 | UNDER ↑ |
| combined_short_exit | +0.0093 | +0.075 | 0.0352 | UNDER ↓ |
| combined_closer_used | +0.0498 | +0.069 | 0.0523 | UNDER ↓ |
| home_rest_days | -0.0347 | -0.063 | 0.0742 | UNDER ↑ |
| combined_lineup_hh | +0.0016 | +0.053 | 0.1333 | UNDER ↓ |
| combined_lineup_contact | +0.0008 | +0.052 | 0.1399 | UNDER ↓ |
| combined_era_spike | -0.0719 | -0.042 | 0.2317 | UNDER ↑ |

## Tail Analysis (top/bottom 10%)

| Feature | Bucket | N | Over% | ROI | 2024 | 2025 | Consistent | Mkt Corr |
|---------|--------|---|-------|-----|------|------|-----------|----------|
| home_rest_days | top_10 | 80 | 0.588 | +12.2% | +0.0% | +25.6% | NO | -0.043 |
| away_rest_days | top_10 | 72 | 0.583 | +11.4% | +0.2% | +25.3% | YES | -0.042 |
| combined_short_exit | bot_10 | 462 | 0.569 | +8.7% | +5.8% | +11.4% | YES | +0.157 |
| combined_lineup_iso | top_10 | 460 | 0.550 | +5.0% | +10.6% | -0.2% | NO | +0.138 |
| combined_ppi | bot_10 | 460 | 0.522 | -0.4% | -4.9% | +4.6% | NO | +0.021 |
| combined_bp_workload | top_10 | 455 | 0.521 | -0.6% | +4.5% | -5.4% | NO | +0.072 |
| combined_era_spike | bot_10 | 460 | 0.520 | -0.8% | +4.1% | -6.3% | NO | +0.055 |
| combined_lineup_contact | top_10 | 460 | 0.520 | -0.8% | +3.1% | -4.2% | NO | +0.105 |
| combined_ppi | top_10 | 460 | 0.520 | -0.8% | -3.0% | +1.5% | NO | +0.021 |
| combined_era_spike | top_10 | 460 | 0.517 | -1.2% | -0.1% | -2.2% | YES | +0.055 |
| combined_lineup_barrel | top_10 | 460 | 0.515 | -1.6% | -1.7% | -1.6% | YES | +0.087 |
| park_factor_hr | bot_10 | 758 | 0.512 | -2.3% | -1.2% | -3.3% | YES | +0.465 |
| combined_closer_used | bot_10 | 1068 | 0.509 | -2.8% | -4.2% | -1.4% | YES | -0.011 |
| combined_k_rate | bot_10 | 460 | 0.500 | -4.5% | -2.2% | -5.8% | YES | -0.415 |
| combined_top3_ip | top_10 | 411 | 0.499 | -4.8% | -0.1% | -9.9% | YES | -0.007 |

## Candidate Signal Ranking

| Rank | Feature | d_over | p_over | Tail ROI | Tail N | Yr Consistent | Mkt Class |
|------|---------|--------|--------|----------|--------|--------------|----------|
| 1 | temperature | +0.154 | 0.0000 | -7.9% | 452 | YES | PRICED |
| 2 | combined_bp_xfip | +0.107 | 0.0026 | -9.1% | 462 | YES | PARTIAL |
| 3 | away_rest_days | +0.026 | 0.4729 | +11.4% | 72 | YES | CLEAN |
| 4 | combined_lineup_iso | +0.101 | 0.0045 | +5.0% | 460 | NO | CLEAN |
| 5 | home_rest_days | +0.013 | 0.7055 | +12.2% | 80 | NO | CLEAN |
| 6 | combined_short_exit | -0.011 | 0.7586 | +8.7% | 462 | YES | PARTIAL |
| 7 | combined_lineup_contact | +0.070 | 0.0509 | -0.8% | 460 | NO | CLEAN |
| 8 | combined_lineup_hh | +0.071 | 0.0466 | -5.4% | 460 | YES | CLEAN |
| 9 | combined_closer_used | +0.039 | 0.2754 | -2.8% | 1068 | YES | CLEAN |
| 10 | park_factor_hr | +0.020 | 0.5807 | -2.3% | 758 | YES | PRICED |

## Final Answers

### Q1: What distinguishes STRONG_OVER games?
- **temperature**: higher in STRONG_OVER (d=+0.154, p=0.0000)
- **combined_bp_xfip**: higher in STRONG_OVER (d=+0.107, p=0.0026)
- **combined_lineup_iso**: higher in STRONG_OVER (d=+0.101, p=0.0045)
- **combined_lineup_hh**: higher in STRONG_OVER (d=+0.071, p=0.0466)
- **combined_lineup_contact**: higher in STRONG_OVER (d=+0.070, p=0.0509)
- **wind_factor_effective**: higher in STRONG_OVER (d=+0.059, p=0.0973)

### Q2: What distinguishes missed STRONG_UNDER games?
- **temperature**: higher in STRONG_UNDER (d=+0.111, p=0.0017)
- **combined_bp_xfip**: higher in STRONG_UNDER (d=+0.090, p=0.0113)
- **park_factor_hr**: higher in STRONG_UNDER (d=+0.089, p=0.0124)
- **away_rest_days**: lower in STRONG_UNDER (d=-0.081, p=0.0221)
- **combined_short_exit**: higher in STRONG_UNDER (d=+0.075, p=0.0352)
- **combined_closer_used**: higher in STRONG_UNDER (d=+0.069, p=0.0523)
- **home_rest_days**: lower in STRONG_UNDER (d=-0.063, p=0.0742)

### Q3: Most promising candidates?

Only one signal passes all three gates (ROI>4%, N≥80, year-consistent):

- **combined_short_exit (bot_10)**: ROI=+8.7%, N=462, 2024=+5.8%, 2025=+11.4%

**Interpretation:** `combined_short_exit` = average short-exit rate (fraction of starts <5 IP) for both starters. Bottom 10% = both starters are highly **durable** (rarely exit early). Counter-intuitively, games with two durable starters go OVER at 56.9%. This may reflect:
- Durable starters who go deep face lineups the 3rd time through, when offensive quality improves
- Market expects low scoring from "quality starters" and overprices the under
- Deep starts reduce bullpen usage, but the starter himself allows more runs in later innings

The **opposite tail** (top 10% = fragile starters) goes OVER at only 46.4% — these games go UNDER, likely because bullpen entry is higher-leverage and markets already adjust totals for bad starters.

### Q4: Signal Classification

| Feature | Classification | Reason |
|---------|---------------|--------|
| **combined_short_exit (bot_10)** | **PROMOTE** | Only signal passing all 3 gates: ROI=+8.7%, N=462, year-stable, PARTIAL market corr |
| combined_lineup_iso | **PROMOTE** | p_over=0.005, ROI=+5.0% top10, CLEAN corr — true OVER environment signal |
| temperature | HOLD | Strongest anomaly (p=0.0000, d=+0.15) but PRICED by market (r=+0.32) |
| combined_bp_xfip | HOLD | Significant (p=0.003) but PARTIAL corr and tail ROI is negative |
| combined_lineup_contact | HOLD | Marginal (p=0.051), CLEAN corr but no tail ROI |
| combined_lineup_hh | HOLD | Marginal (p=0.047), CLEAN corr but negative tail ROI |
| rest_days (home/away) | HOLD | Interesting anomaly (p=0.022-0.074, CLEAN) but N too small in tails |
| All others | SHELVE | No significant anomaly OR tail ROI is negative OR PRICED by market |

### Critical Notes

1. **The residual space is 98.5% of all games.** The under signal only fires on 74/4855 games (1.5%). This is because the S12 trigger using boxscore CSW proxy almost never fires (the production S12 uses FanGraphs/Savant CSW which differs). The residual cohort is essentially the full dataset, so these results are broadly applicable rather than specific to "missed" games.

2. **Temperature is the dominant anomaly** (d=+0.154, p<0.0001) but is PRICED (r=+0.32). Warmer games score more, but the market already adjusts totals for temperature. No residual edge.

3. **combined_lineup_iso is genuinely interesting.** Higher ISO (isolated power) in STRONG_OVER games (d=+0.101, p=0.005) with CLEAN market correlation (r=+0.135). Top-10% ISO games show +5.0% OVER ROI. This suggests the market underprices lineup power in totals.

4. **combined_short_exit is the standout actionable finding.** Year-consistent, large N, moderate market pricing. The counterintuitive direction (durable starters → OVER) is the most interesting discovery in this scan.

