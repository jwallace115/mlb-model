# NBA Current Archetypes -- Keep/Kill Memo
Generated: 2026-04-10
Data: 3 seasons (2022-23 through 2024-25), 3690 games
TRUE OOS window: 2022-23, 2023-24 (pre-discovery)
In-sample window: 2024-25 (discovery/contaminated)

## Summary Table

| Archetype | Dir | OOS N | OOS Hit% | OOS ROI | InS Hit% | InS ROI | Verdict |
|-----------|-----|-------|----------|---------|----------|---------|---------|
| ELITE_DEF2_at_ELITE_DEF | UNDER | 122 | 43.0% | -18.0% | 45.9% | -12.4% | **COLLAPSES** |
| BALANCED_OFF_vs_PASSIVE_DEF | OVER | 319 | 51.4% | -1.8% | 55.5% | +5.9% | **DIMINISHED** |
| ROAD_WARRIOR_at_STRONG_HOME | OVER | 226 | 63.2% | +20.7% | 65.5% | +25.0% | **SURVIVES** |
| ELITE_OREB_vs_WEAK_BOXOUT | OVER | 1121 | 50.4% | -3.7% | 53.6% | +2.3% | **DIMINISHED** |

## Detailed Verdicts

### ELITE_DEF2_at_ELITE_DEF -- COLLAPSES (KILL)
- OOS hit rate 43.0% below breakeven, ROI -18.0%

### BALANCED_OFF_vs_PASSIVE_DEF -- DIMINISHED (MONITOR)
- OOS hit rate 51.4% at breakeven, edge +1.3pts positive but thin

### ROAD_WARRIOR_at_STRONG_HOME -- SURVIVES (KEEP)
- OOS hit rate 63.2% with positive ROI +20.7%

### ELITE_OREB_vs_WEAK_BOXOUT -- DIMINISHED (MONITOR)
- OOS hit rate 50.4% at breakeven, edge +0.2pts positive but thin

## Methodology
- Frozen team sets from nba/run_nba.py applied to all historical games
- Graded against real DK/FD closing lines from nba/data/nba_historical_closing_lines.parquet
- ROI computed at standard -110 juice
- Hit rate excludes pushes (actual == line)
- TRUE OOS = seasons that predate the archetype discovery work
- 52.4% is breakeven at -110