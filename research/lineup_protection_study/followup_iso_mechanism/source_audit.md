# Source Audit — ISO Mechanism Follow-up

## Data Available
- protection_pa_dataset.parquet: 174870 batter-games
- Statcast per-start (pitcher): zone_rate, whiff_rate, hard_hit_rate, barrel_rate

## CRITICAL LIMITATION
**No batter-level pitch attack data available locally.**
- zone_rate: PITCHER-GAME level only (not per-batter or per-PA)
- first_pitch_strike: NOT available
- fastball_rate: NOT available
- hard_hit / barrel: PITCHER-GAME level only (not per-batter)

## What We CAN Test
- Batter-game K rate, BB rate, ISO, contact rate, wOBA as outcomes
- Extra-base-hit rate (2B+3B+HR) / PA as damage proxy
- HR rate as isolated power proxy
- Pitcher-game aggregate Statcast (zone_rate, whiff_rate, hard_hit_allowed)
  as environmental context (not per-batter causal)

## Design Implication
Cannot directly test: 'does protector change zone rate to THIS batter?'
CAN test: 'does protector change batter outcomes in ways consistent with
attack-mechanism hypothesis vs clustering hypothesis?'
