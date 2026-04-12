# Phase 7: Live Feasibility

## bp_adv_dog
- BP ERA from pitcher_game_logs: available daily, updated after each game
- Requires: pitcher_game_logs refresh before game time
- Lag: previous day's games are in PGL by morning
- VERDICT: LIVE-FEASIBLE (morning computation, no real-time feed needed)

## night_dog
- Day/night from MLB schedule API local_start_hour
- Available at schedule release (typically days in advance)
- VERDICT: LIVE-FEASIBLE (trivially available)
