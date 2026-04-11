# NHL Audit -- Phase 2: Feature Provenance and PIT Safety

## Date: 2026-04-10

## Rolling Feature Construction (phase3_build_features_and_ridge.py)

### Method
- Team game log: one row per (team, game) from both perspectives
- Rolling: for each game i, uses strictly prior games in same season
- Goalie rolling: same pattern -- strictly prior starts
- Goalie fatigue/b2b: uses game_date with strict less-than comparison
- Backup flag: uses cumulative starts count through prior games

### PIT Safety Assessment: PASS (with one caveat)

Rolling features: PASS
The compute_team_rolling() function uses prior = grp.iloc[:i] which is
strictly games before the current one, sorted by (game_date, game_id).
This is correctly PIT-safe -- no lookahead.

Goalie rolling: PASS -- same pattern as team rolling.

Goalie fatigue/b2b: PASS -- uses date arithmetic with strict < comparison.

Backup flag: PASS -- uses cumulative starts count up to (not including) current game.

### FINDING F1 -- League Average Shrinkage Prior: MINOR LOOKAHEAD

Severity: LOW-MODERATE

compute_league_avgs() (Step 9) computes season-wide means from ALL games
in the season, then uses these as shrinkage priors for every game in that season.

For game 1 of the 2022-23 season, the shrinkage prior includes data from all
1312 games of that season -- including 1311 future games. The code itself
acknowledges this: "In training, we use all games in the season (conservative
approximation)."

Impact assessment:
- Shrinkage weight = min(n, window) / window, where window=20
- For game 1: weight = 0/20 = 0, so 100% league prior
- For game 10: weight = 10/20 = 0.5, so 50% prior, 50% raw
- For game 20+: weight = 1.0, so 0% prior
- Lookahead only affects early-season games (1-19 per team)
- League averages are relatively stable within a season
- Cross-season variation is the concern: if a season has unusual scoring
  levels, the prior absorbs this and biases early-season features

Estimated impact: roughly 0.5-1.0pp on ROI -- minor but creates a small
optimistic bias in the backtest for early-season games.

Fix: Use prior-season league average, or expanding mean from prior games.

### FINDING F2 -- OT/SO Goals in Rolling Features

Severity: LOW

Rolling goals_scored and goals_allowed include OT and SO goals.
- SO games add exactly 1 extra goal to the winner's total
- 22.3% of games go to OT, 7.2% to SO
- OT/SO accounts for 3.6% of all goals scored

For totals betting, this is technically correct since NHL totals settle on
final score including OT/SO. However, the Poisson model assumes independence
and constant rate, while OT is a distinct game state (3-on-3, higher scoring
rate). A team's OT win rate is partially random, so including SO goals in
rolling averages adds noise to the offensive skill signal.

Impact: negligible -- 3.6% of scoring, noise-dominated.

## Feature Table Summary (44 model features across both models)

### Live Status Distribution
- LIVE (varies per game): 10 features, 20.6% of prediction variance
- FROZEN (static league avg prior): 14 features, 79.4% of prediction variance

### Features by contribution variance (Home Model)
| Pct | Feature | Source | Live? |
|-----|---------|--------|-------|
| 26.2% | away_xga_rolling_20 | MoneyPuck | FROZEN |
| 21.4% | home_xgf_rolling_20 | MoneyPuck | FROZEN |
| 9.3% | away_shots_against_rolling_20 | MoneyPuck | FROZEN |
| 9.1% | home_games_last_7 | NHL API | LIVE |
| 7.5% | away_hd_shots_against_rolling_20 | MoneyPuck | FROZEN |
| 7.4% | home_hd_shots_for_rolling_20 | MoneyPuck | FROZEN |
| 4.5% | home_shots_for_rolling_20 | MoneyPuck | FROZEN |
| 3.8% | away_b2b | Calendar | LIVE |
| 3.1% | away_backup_flag | NHL API | LIVE |
| 1.5% | home_goals_scored_rolling_10 | NHL API | LIVE |
| 1.3% | home_days_rest | Calendar | LIVE |
| 1.1% | home_pp_pct_rolling_20 | NHL API | FROZEN |
| 0.6% | away_goalie_fatigue | NHL API | LIVE |
| 0.6% | away_goalie_sv_pct_rolling_10 | NHL API | FROZEN |
| 0.6% | away_pk_pct_rolling_20 | NHL API | FROZEN |
| 0.5% | away_days_rest | Calendar | LIVE |
| 0.5% | away_goalie_vs_team_baseline | NHL API | FROZEN |
