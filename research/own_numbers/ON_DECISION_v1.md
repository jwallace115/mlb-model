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

## ON-D5 — Market signs, event identity, quote timing (2026-10-12)

**Source:** ChatGPT audit of c23e62419 (findings #4, #5, #7 in the audit;
adjudication items 4, 5 in Cowork's reply). Filed to `research/cross_ai/`.

**Repairs (ON-1b item 1):**

1a. **Sign normalisation.** Raw home handicap h → expected home margin q = −h.
    gap = ours_m − q. The OLD code used gap = ours_m − h, producing the wrong sign
    for home favourites. Audit fixture: raw home −3, ours_m 2, err_m 2 → gap −1,
    NOT confident. Old code gave +5, confident. run_monday.py and build_2026_interim.py
    both corrected. All code now uses `on_utils.compute_gap()` and `is_confident()`.

1b. **Event identity.** Match by (season, mapped home, mapped away,
    kickoff within ±1h, event_id). Ambiguous match HALTs. A rematch later in the
    season cannot be selected for the earlier meeting (±1h window enforces this).

1c. **Quote timing.** Close = last quote strictly BEFORE kickoff with a 3h
    max-age preference; flagged "stale" if older. In-play quotes (snapshot_utc ≥
    kickoff) are never usable as a close. Decision quote = last quote before the
    prediction cutoff. Both carry timestamps and ids. Future-dated quotes rejected.

1d. **2026 interim artifact INVALID.** `monday_numbers_2026.parquet` produced by
    `build_2026_interim.py` at c23e62419 is INVALID on two grounds:
    - Sign error: gap computed as ours_m − h instead of ours_m − (−h); 46 of 75
      confidence flags wrong (audit recompute: 50 → 30 confident, 24/40 → 11/25
      moving-confident direction agreement).
    - In-play close: `get_first_and_last_line()` accepted post-kickoff quotes as
      closes (CAR–ATL moved from +1 to +30.5 in-play).
    The file is retained as an audit artifact; it must not be overwritten. A corrected
    rebuild, if any, gets a new file name and experiment id.

**Tests:** `test_on_utils.py` — 33 behavioral fixtures covering sign normalisation
(home fav, home dog, pick'em), event matching (single, rematch, ambiguous HALT,
no-match), quote selection (in-play rejected, stale flagged, preferred, empty),
stable seeds (deterministic across PYTHONHASHSEED), Monday cutoff (MNF excluded).
Each test FAILS when the audited defect is reintroduced.

## ON-D6 — Monday-noon cutoff, honest counts, stable seeds; 2021-23 rescore (2026-10-12)

**Source:** ChatGPT audit findings #1, #6, #7, #9, #11; adjudication items 1, 6, 11.

**Repairs (ON-1b item 2):**

2a. **prediction_cutoff** = Monday 12:00 America/New_York of each game week (UTC
    recorded). Prior game admitted only if kickoff + 4h < cutoff. Week 1's MNF
    (same-day as week 2's Monday noon cutoff) is excluded from week 2 ratings.
    49 of 54 weeks had MNF exclusions. Team ratings rebuilt with excluded games
    removed; tendencies/sit/kicker use the standard tables (one MNF game has
    negligible effect on league-level tables). League shrink targets: prior season
    only; HALT on missing. Ratings built with FROZEN params (params_v1.json).

2b. **n_games_into_ratings** = actual admitted completed games per team (byes,
    cancellations, cutoff exclusions respected). 502/815 games changed from the old
    week-1 proxy; 100 changed calibration bucket.

2c. **Seeds** via `zlib.crc32(game_id:chunk_index:season:week)` — deterministic
    across PYTHONHASHSEED. Cross-process test passes.

2d. **Rebuild 2021-23.** 815 games at N=5,000, wall time 93 min (sims) + 2.6 min
    (ratings). All games produced exactly one result. Cache validated on seed scheme
    and game count.

**LABEL: DEVELOPMENT RESULT — mechanics fitted on 2021-24; not out-of-sample.**

Pre-registered predictions (from Cowork's no-leak recompute, stated before running):

| Metric | Pre-registered | Actual | Held? |
|---|---|---|---|
| Direction (moving confident) | 65-75% (Cowork: 71.8%) | 70.8% (80/113) | HELD |
| Mean signed movement (all selected) | +1.0 to +1.5 (Cowork: +1.37) | +1.528 | DID NOT HOLD (marginally above) |
| ATS at open (same side, excl pushes) | 47-55% (Cowork: 50.8%) | 52.0% (65W-60L-1P) | HELD |

Full population (unchanged lines included): 126 selected, 113 moved, 13 unchanged.
ATS at close: 47.1% (56W-63L-7P) — does not beat the close.
2021: 0 confident games (flat prior). 2022: 66.7% direction (66 games). 2023: 76.6% (47 games).
Non-confident direction: 53.9% (312/579) — signal exists outside the confident subset.

Null control: permutation rebuilds confident subset per shuffle (audit P6 fix).
Real 70.8%, null mean 48.1%, SD 2.1%, Z = 10.76. Null denominator: mean 282 games.

Mean movement did not hold: +1.528 vs upper bound +1.5. The excess is 0.028 pts,
within the SE of the estimate. Stated plainly as "did not hold" per the work order.

## ON-D7 — Freeze manifest, 2024 guard, ON_SPEC_v2 (2026-10-12)

3a. **FROZEN_MANIFEST_v2.json:** SHA256 of 47 files — every .py and .md in
    research/own_numbers/, engine.py, ratings.py, params_v1.json, hfa_v1.json,
    all 29 tables under nfl/data/sim/tables, calibration_table.parquet, and
    engine_fingerprint() = `156cd057a3b39e48`. Fit windows recorded: mechanics
    2021-2024, ratings params 2021-2024, calibration 2021-2023, HFA 2021-2023.

3b. **2024 guard:** `guard_2024()` in on_utils.py. Any ON build/score entry point
    given season=2024 HALTs before loading outcomes. Added to build_monday_number.py
    (TARGET_SEASONS guard) and run_monday.py (forward runner). Test: test_on_utils.py
    `TestGuard2024` — halts on 2024, allows 2021-23 and 2025-26.

3c. **ON_SPEC_v2.md:** forward protocol adopted from the audit's "valid forward test"
    section. SHA256: `f938a0d2297e5df8187a026a20f8c6c8b72b3303b84fbe4b36071a1d6e08ad6c`.
    Scope: team-level player-off, Monday 12:00 ET cutoff (UTC recorded), only
    still-upcoming fixtures, immutable snapshots with manifest, benchmark = HR quote
    at cutoff normalised to home margin. Selection: |ours − q| ≥ err_m AND ≥ 1 pt,
    side fixed at decision. PRIMARY = mean signed decision-to-close movement (all
    selected), paired vs prior-close comparator. ≥ 60 games and ≥ 12 weekly clusters
    for confirmatory read; no efficacy-based early stop; every look logged.

    2021-23: DEVELOPMENT. 2024: "used in engine development; not a holdout".

## ON-D8 — Earlier-close comparator and ridge comparison (2026-10-12)

4a. **Prior-close ratings** (`comparator_prior_close.py`): team ratings by least
    squares on home-minus-away indicators + home intercept, fitted ONLY on closes
    of games with kickoff + 4h < the same prediction_cutoff (prior season + current
    prior weeks; ≥ 32 training games or no prediction). 767 eligible games.

    Pre-registered: ~55% direction (audit measured 55.0 / 54.4).

    | Method | Threshold | Selected | Moved | Direction | Mean move |
    |---|---|---|---|---|---|
    | Prior-close | common (engine err_m) | 146 | 125 | **56.8%** | +0.462 |
    | Prior-close | own (|gap| ≥ 1) | 574 | 492 | 53.0% | +0.159 |
    | Engine | common | 126 | 113 | **70.8%** | +1.528 |
    | Ridge OOF | common | 169 | 149 | 55.7% | +0.604 |

    **Pre-registration: HELD** (56.8% within the ~55% expectation).

    Paired on engine-selected games (N=126, 113 movers):
    Engine 70.8%, Ridge 60.2%, Prior-close 60.2%. The engine retains all its
    selected games within the common eligible population.

4b. **Ridge baseline** copied from `origin/eng/gl1:nfl/data/sim/outputs/gl1/
    baseline_2021_23.parquet`. Training: LOSO 2021-23 — NOT strictly as-of across
    seasons (stated). Common threshold used (engine's err_m); labelled.

    The engine's margin over trivial comparators (70.8% vs ~56%) is the one thing
    worth testing forward. In-sample mechanics remain a possible channel — only
    forward can distinguish.

## ON-D9 — Data commit omission fix (2026-10-12)

**Omission:** Item 2's commit (f41140449, ON-D6) did not `git add` the rebuilt
parquet files. The committed `monday_numbers_2021_23.parquet` remained the ON-1
(leaky) file — SHA `c0aadb4f...` — which scores 139 selected / 125 moving / 73.6%,
not the 126 / 113 / 70.8% recorded in ON-D6. The code changes were correct; only
the data was missing.

**SHAs:**
- Before (leaky, ON-1): `c0aadb4f65f0b862dc96a230fcea45ba35b2c76a07e829f8d2672173213323b5`
- After (rebuilt, ON-D6): `d2b46220ea39578014b23bd06bb588467391c6ce565e3eb0101b10896f0b15f1`

**Verification:** `score_monday_numbers.py` run on the worktree file reproduces
the ON-D6 table exactly: 126 / 113 / 80 of 113 / +1.528 / 65W-60L-1P / 56W-63L-7P.

**ON-D8 re-check:** `comparator_prior_close.py` re-run against the rebuilt file
reproduces the same numbers (prior-close 56.8%, ridge 55.7%, engine 70.8%, paired
60.2%/60.2%). No re-statement needed.

**Manifest integrity gate:** `FROZEN_MANIFEST_v2.json` now includes all files
under `nfl/data/own/`. `score_monday_numbers.py` and `run_monday.py` HALT when
the parquet they read is not in the manifest with a matching SHA. Tested: altered
file → SHA mismatch HALT; unregistered file → not-in-manifest HALT.

**Known residual:** the MNF team ratings correction uses standard (non-filtered)
tendencies, situational PROE, and kicker tables. These still include the prior
Monday Night game. The effect of removing one game from ~15 per week on
league-level tendency/kicker tables is negligible but not measured. Plan: close
this in ON-1c by verifying the magnitude.
