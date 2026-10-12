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

**Invariant note:** the correlation gate applies to the OUTCOME residual
(actual_margin - spread_line), not the prediction residual (ours_m - spread_line).
Our prediction naturally correlates with the close (r=0.82) because both capture
team quality. The outcome residual is uncorrelated (r=0.015).

## ON-D2 — Scoring on 2021-23 (2026-10-12)

**ON-1a (prior 45%): CONFIRMED.** Confident subset direction agreement = 73.6%
(92/125), well above 55%. Wilson [0.652, 0.806]. By season: 2021 N/A (no confident
games — 2021 uses flat prior with huge err_m), 2022 72.5% (50/69), 2023 75.0% (42/56).

**ON-1b (prior 60%): FALSIFIED.** Non-confident direction agreement = 55.0% (312/567),
outside 48-52%. The error bar does NOT cleanly separate signal from noise — there is
signal outside the confident subset too.

**Null control:** real direction agreement 58.4%, null mean 48.4%, null SD 1.4%,
Z = 7.28. The null sits at ~50% as expected. The real signal is genuine.

**Totals:** 63.0% direction agreement (466/740) — not pre-registered but reported.

**Breakdowns:**
- By week tercile: early 55.0%, mid 59.1%, late 61.4% (improves as ratings deepen)
- Confident by week: early 70.2%, mid 81.2%, late 66.7%
- By err_m tercile: low_err 61.9%, mid 57.8%, high 55.4% (lower error → better agreement)
- By fav/dog: home_fav 56.5%, away_fav 59.4%

**ON-2: STOPPED.** `build_active_universe` in usage.py joins injuries by
`(season, week, team, player_id)` — it uses the FINAL week-level `report_status`,
not a timestamped version. To implement Monday-noon-vs-kickoff comparison, usage.py
would need a `date_cutoff` parameter to filter `injuries.date_modified < cutoff`
before the join. This requires editing usage.py, which this order prohibits.

**What it would take:** Add an optional `injury_cutoff: datetime | None` parameter
to `build_active_universe`. When set, filter `injuries` to rows with
`date_modified < injury_cutoff` before the merge. Then call it twice per game:
once with Monday 12:00 ET, once with kickoff time. Estimated 2-hour implementation
+ the same ~18 min sim run for the kickoff-state numbers.

## ON-D3 — 2026 interim look, weeks 2-6 (2026-10-12)

**LABEL: interim look at forward data. Nothing is tuned on it. The registry of
priors is not changed by it.**

77 games, 75 with Hard Rock opens, 50 confident (|ours - HR| >= err_m AND >= 1pt).

HR spread open→close movement present in 61 games.
- Direction agreement (all): 59.0% (36/61)
- Direction agreement (confident): 60.0% (24/40), Wilson [0.446, 0.737]
- By week: wk2 62.5% (10/16), wk3 68.8% (11/16), wk4 66.7% (10/15), wk5 35.7% (5/14)

**Assessment:** too early to draw conclusions. The Wilson CI on the confident subset
includes 50%. Week 5 pulled the overall down hard (5/14). The 2021-23 backtest
(73.6%, N=125) is the stronger signal; this is 5 weeks of noisy forward data.

## ON-D4 — Monday runner (2026-10-12)

`research/own_numbers/run_monday.py --season 2026 --week N`

HALTs: (a) not Monday/Tuesday ET, (b) week file exists, (c) snapshot > 3h old,
(d) unmapped team name.

Output: `nfl/data/own/forward/week=2026_NN.parquet` — our number + err, HR and
Pinnacle openers by event_id, confident flag, MODE=PILOT.

Tests: refuses overwrite ✓, refuses stale snapshot ✓ (code path verified),
refuses unmapped team ✓ (32 teams in FULL_TO_ABBR), confident flag verified
against 2026 data (50 confident, 25 not) ✓.

"How to run on Monday" paragraph appended to ON_SPEC_v1.md.
