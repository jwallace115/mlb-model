# MASTER COMPARISON — Contaminated V1 vs Clean V1

## Model Specifications

| Property | Contaminated V1 | Clean V1 |
|----------|-----------------|----------|
| Algorithm | Ridge(alpha=50) | Ridge(alpha=50) |
| Features | 25 | 25 (same names, different values) |
| Sigma | 4.361 | 4.424 |
| Feature Source | FanGraphs end-of-season aggregates | PGL expanding mean + shift(1) |
| Lookahead | YES — full season stats for all games | NO — strict point-in-time |

## Feature Value Comparison (sample)

The contaminated V1 uses a SINGLE xFIP value per pitcher per season (end-of-year aggregate).
The clean V1 uses an EXPANDING cumulative xFIP that evolves game by game.

Example: Gerrit Cole 2022
- Contaminated: xFIP = 3.626 for ALL 16 starts
- Clean: xFIP varies from 3.332 to 4.580 across career

## Performance at Primary Threshold (p_under > 0.57)

| Season | Clean Bets | Clean WR | Clean ROI | 
|--------|-----------|----------|-----------|
| 2022 | 0 | 0.0% | +0.0% |
| 2023 | 0 | 0.0% | +0.0% |
| 2024 | 175 | 46.9% | -10.5% |
| 2025 | 55 | 45.5% | -13.2% |

## Key Findings

1. **Feature Variation**: Clean V1 features vary within-season (confirmed by Gate 4: 
   Gerrit Cole had 15 unique xFIP values in 2022 vs 1 in contaminated)

2. **Sigma**: Clean sigma = 4.424 vs contaminated 4.361
   - Higher sigma means wider prediction intervals

3. **Feature Correlations**: Clean features have weaker correlation with actual totals
   (expected — point-in-time features contain less information than full-season aggregates)

## Interpretation

If the clean V1 shows worse ROI than contaminated V1, the contaminated model's
apparent profitability was **inflated by lookahead bias**. The model was "cheating"
by using information that would not have been available at prediction time.

This does NOT mean the clean model is useless — it means the honest baseline
is the correct starting point for future development.
