# Finish Distribution Simulator

## Method
- 20000 simulations per event
- 4-round tournament with cut after R2
- Player scores: Normal(strength, sd) per round
- Cut: 50/50 blend of simulation rank and cut engine probability
- Strength: Ridge-predicted finish percentile (inverted)
- SD: Ridge-predicted event score volatility

## Outputs
- sim_make_cut_prob, sim_top_20/10/5_prob, sim_win_prob
