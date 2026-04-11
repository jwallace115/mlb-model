# NHL Audit -- Phase 3: Research vs Live Identity Mismatch

## Date: 2026-04-10

## FINDING F3 -- CRITICAL: Massive Research/Live Feature Identity Gap

Severity: CRITICAL -- PRIMARY FAILURE MODE

### The Problem

The Ridge models were trained on features computed from MoneyPuck advanced
stats (xGoals, Corsi, HD shots, shots on goal) and full NHL API boxscore
data (PP%, PK%, goalie SV%, penalties). These features account for 79.4%
of the model's prediction variance.

In the live pipeline (nhl_daily_pipeline.py), MoneyPuck data is unavailable
for the 2025-26 season. The code explicitly acknowledges this:

    "MoneyPuck 2025-26 not yet available -- using 2024-25 priors. Known degradation."

The build_live_team_features() function freezes ALL MoneyPuck-dependent
features at their 2024-25 league-average values. Additionally, PP%, PK%,
goalie SV%, and goalie_vs_team_baseline are also frozen at league priors,
even though they could be computed from live NHL API data.

### What This Means

The live model is effectively a reduced model with only 10 live features
(goals_scored/allowed rolling, rest, b2b, backup flag, goalie fatigue/b2b)
contributing just 20.6% of prediction variance. The remaining 79.4% is
constant across all games -- the model cannot distinguish between, say,
the Panthers' elite defense and the Sharks' poor defense.

The live model degenerates to approximately:
    predicted_total = constant + f(rest, b2b, backup, recent_goals)

This is a fundamentally different model than what was validated in the
historical backtest.

### Live Feature Gaps (features frozen at prior)

1. xGF rolling 20 (home + away) -- MoneyPuck
2. Shots for rolling 20 (home + away) -- MoneyPuck, but available from NHL API
3. HD shots for rolling 20 (home + away) -- MoneyPuck
4. xGA rolling 20 (home + away) -- MoneyPuck
5. Shots against rolling 20 (home + away) -- MoneyPuck, but available from NHL API
6. HD shots against rolling 20 (home + away) -- MoneyPuck
7. PP% rolling 20 (home + away) -- available from NHL API boxscores
8. PK% rolling 20 (home + away) -- available from NHL API boxscores
9. PP opp per game rolling 20 (home + away) -- available from NHL API boxscores
10. Penalties taken rolling 20 (home + away) -- available from NHL API boxscores
11. Goalie SV% rolling 10 (home + away) -- available from NHL API boxscores
12. Goalie vs team baseline (home + away) -- derivable from goalie data
13. Shot pressure (home + away) -- derived from frozen shots
14. HD pressure (home + away) -- derived from frozen HD shots
15. Games last 7 -- uses fixed 2.5 rather than computing from live schedule

### Features That Could Be Live But Aren't

Items 7-12 and 15 above (PP%, PK%, penalties, goalie SV%, games_last_7)
are all available from the same NHL API boxscore data that the pipeline
already fetches for goalie starter identification. These could be computed
from the live cache (nhl_live_season.parquet) but the pipeline doesn't
extract them.

Similarly, shots_for and shots_against (items 2, 5) are available from
the NHL API boxscore (shots on goal is reported), but the pipeline only
fetches goals.

### Quantified Impact

Historical backtest: 53.25% hit rate (OOS, 154 signals)
Live performance:    41.5% hit rate (65 signals, 27-38 W-L)
Degradation:         -11.8 percentage points

This degradation is entirely consistent with 79.4% of the model's
discriminative power being eliminated by feature freezing.

### Monthly Live Performance
- 2026-03: 18-24 (42.9%), ROI = -18.2%
- 2026-04: 9-14 (39.1%), ROI = -25.3%

Performance is worsening over time, which is consistent with increasing
divergence between 2024-25 league priors and actual 2025-26 team stats.

### Under Bias

93.2% of live signals (69/74) are UNDER signals. The frozen features
all default to 2024-25 league averages, which shifts the model's baseline
projection lower than current-season reality (2025-26 scoring may be
higher). The static drift correction of +0.4458 (from 2023-24 validate
season) partially compensates but is calibrated to a different season.

## VERDICT

The live NHL model is NOT the same object that was validated in backtest.
The backtest ROI of +1.65% OOS is irrelevant to the live system because
the live system runs with 79.4% of its features frozen. This constitutes
a complete research/live identity failure.

The model should be immediately suspended from active betting until either:
1. MoneyPuck data becomes available for 2025-26, OR
2. The pipeline is upgraded to compute rolling stats from NHL API boxscores
   (shots, PP%, PK%, goalie SV%), which would recover roughly 15-20% of
   the frozen feature variance
