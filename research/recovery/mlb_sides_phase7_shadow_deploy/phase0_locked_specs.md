# Phase 0: Locked Specifications

## Frozen Discovery Thresholds (2022-2023, p50)

| Feature | Threshold | Source |
|---------|-----------|--------|
| SP FIP diff | 0.814 | p50 of |fav_sp_fip - dog_sp_fip| in discovery |
| Offense R20 diff | 0.800 | p50 of |fav_off_r20 - dog_off_r20| in discovery |
| BP ERA diff | 0.583 | p50 of |fav_bp_era - dog_bp_era| in discovery |

## MIXED Classification

A game is MIXED if ALL THREE of:
- |SP FIP diff| < 0.814
- |Offense R20 diff| < 0.800
- |BP ERA diff| < 0.583

## Close-Game Universe
- fav_implied >= 0.512 and fav_implied <= 0.556
- Implied probability derived from closing ML, vig-removed via normalization

## Object 1: night_dog
- Trigger: MIXED + local_start_hour >= 17 (night game)
- Action: back the dog at closing ML
- Historical: disc N=381 resid=+0.0349, val N=245 resid=+0.0337, OOS N=268 resid=+0.0533
- Expected frequency: ~268/season

## Object 2: bp_adv_dog
- Trigger: MIXED + fav_bp_era > dog_bp_era (dog has better bullpen)
- bp_era_diff = fav_bp_era - dog_bp_era > 0
- Action: back the dog at closing ML
- Historical: disc N=241 resid=+0.0624, val N=147 resid=+0.0519, OOS N=179 resid=+0.0416
- Expected frequency: ~179/season

## Feature Computation (PIT-safe)
- SP FIP: expanding cumulative from pitcher_game_logs (starter_flag==1), shift(1), min 10 IP
- BP ERA: expanding cumulative from pitcher_game_logs (starter_flag==0), per team per game, shift(1), min 10 IP
- Offense R20: rolling 20-game mean of runs scored from game_table, shift(1), min 10 games
- All features use strict shift(1) to prevent lookahead

## Monitoring Rules (from Phase 6)
- Kill switch: ROI < -15% after 50+ bets
- Promotion gate: ROI > 0% after 100+ bets with residual > +1.5%
- Weekly cumulative ROI tracking
