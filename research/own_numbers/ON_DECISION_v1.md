# ON Decision Log

## ON-D1 — The Monday number with error bar (2026-10-12)

**As-of definition:** Monday 12:00 ET before kickoff. In practice this means:
ratings built from plays in weeks < game_week of the same season, plus the prior
season as prior (the standard ratings.py as-of path). For week 1, only the prior
season is used. For week 2+, all completed prior-week games are included.

**HFA offset route:** main's engine.py has no `hfa=` parameter. HFA is applied
via the existing `epa_home_offset=+h, epa_away_offset=-h` arguments, where
h=0.1719 EPA units (from `hfa_v1.json`, measured on 2021-23 REG, 815 games,
mean home margin 2.125).

**Calibration method:** `err_m = sqrt(mc_se_m² + cal_var_m(n_games))` where:
- `mc_se_m` = SE from 2 × 2,500 chunk means (Monte-Carlo sampling noise)
- `cal_var_m(n_games)` = variance of (ours_m − close) from PRIOR seasons, bucketed
  by min(n_games_home, n_games_away) in 4 buckets: ≤3, 4-8, 9-13, 14+
- 2021: flat prior (margin SD ≈ 13.5 → var ≈ 182.25; total SD ≈ 13.2 → var ≈ 174.24;
  from NFL scoring variance, not fitted)
- 2022: calibrated on 2021 data
- 2023: calibrated on 2021-22 data

**Targets:** open = -bet365_spread_open (negated to nflverse home-margin convention,
labelled "bet365 open"); close = nflverse spread_line. Residuals with the invariant
(|corr(residual, close)| < 0.05; known-game assertions; zero-variance HALT).
