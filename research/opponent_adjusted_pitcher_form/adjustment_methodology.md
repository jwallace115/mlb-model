# Adjustment Methodology

## Concept
Raw per-start metrics are inflated/deflated by opponent quality.
A pitcher facing a strikeout-prone offense gets artificially high K rates.

## Formula (v1 — simple league-relative subtraction)

```
adj_metric_start = raw_metric_start - (opponent_rolling_20g - league_avg)
```

### Specific Definitions

**K rate:** adj_k_rate = raw_k_rate - (opp_k_rate_r20 - 0.2191)
- If opponent K rate is above league average, raw K rate is inflated → subtract excess

**BB rate:** adj_bb_rate = raw_bb_rate - (opp_bb_rate_r20 - 0.0797)
- If opponent BB rate is above league average, raw BB rate is inflated → subtract excess

**Strike% (CSW proxy):** adj_strike_pct = raw_strike_pct - (opp_k_rate_r20 - 0.2191)
- Strike% correlates with opponent swing-and-miss tendency → adjust via K rate proxy

## Opponent Rolling Features
- Window: last 20 completed games per team (excluding current game)
- Min periods: 10 games
- Source: team batting from MLB Stats API boxscores

## Limitations
- No handedness split (would require pitch-level data per game)
- Hard-hit / barrel not adjusted (no suitable team-level proxy available)
- Strike% is an imperfect CSW proxy (includes foul balls, called strikes on takes)
- Adjustment assumes linear opponent effect (v1 simplification)
