# FWD7a Mac run report — 2026-10-02

## Step 2 — Apply and push

```
Applying: FWD6f (D270): ChatGPT audit #13 NO-GO accepted (TNF = pilot); dependency rule as one predicate (union baseline, new distributions are drift) recorded on every primary receipt; launcher hash in repo_modules; static scan refuses native-reader references; audit #13 survivors killed
Applying: FWD7a (D271): forward-run inputs must include each team's last game; active universe must be this week's rosters + injury report; QB/kicker ratings get the entering-week row; refresh_inputs.py rebuilds 2026 rows and splices frozen history (FREEZE fingerprint checked)
13236ed0e FWD7a (D271): ...
cdefcbc73 FWD6f (D270): ...
5fabce877 FWD6e Mac run: ...
```

## Step 3 — Selftest

```
exit 0
launcher hash ok: True {'n_repo_modules': 12, 'n_dependency_files': 1090, 'n_distribution_files_verified': 6395}
```

## Step 4 — PBP hashes

```
2020 4126188fda860f3f
2021 a9741a722a22dde8
2022 6809039bb075367d
2023 81984d68970d50a9
2024 35d5a2e28e4f3873
2025 cc0dd69de7cd91f0
```

## Step 5 — Tests (per file)

```
nfl/sim/tests/test_fwd2_anchor.py: 3 passed in 0.42s
nfl/sim/tests/test_fwd2_bundle.py: 5 passed in 0.24s
nfl/sim/tests/test_fwd2_experiment.py: 6 passed in 1.06s
nfl/sim/tests/test_fwd2_item0_fixes.py: 7 passed in 1.07s
nfl/sim/tests/test_fwd2_settlement.py: 12 passed, 1 warning in 2.04s
nfl/sim/tests/test_fwd2b_harness.py: 10 passed in 44.87s
nfl/sim/tests/test_fwd3_item0.py: 9 passed in 35.77s
nfl/sim/tests/test_fwd3_item1.py: 3 passed in 0.29s
nfl/sim/tests/test_fwd3_item2.py: 8 passed in 1.23s
nfl/sim/tests/test_fwd4_item0.py: 9 passed in 26.19s
nfl/sim/tests/test_fwd4_item1.py: 4 passed in 6.11s
nfl/sim/tests/test_fwd5_pin.py: 4 passed in 6.33s
nfl/sim/tests/test_fwd6_item0.py: 13 passed in 34.71s
nfl/sim/tests/test_fwd6_item1.py: 12 passed in 63.66s
nfl/sim/tests/test_fwd6_item2.py: 9 passed in 30.55s
nfl/sim/tests/test_fwd6_item3.py: 5 passed in 11.45s
nfl/sim/tests/test_fwd6b.py: 39 passed in 127.10s
nfl/sim/tests/test_fwd6c.py: 33 passed in 77.47s
nfl/sim/tests/test_fwd6d.py: 33 passed in 74.78s
nfl/sim/tests/test_fwd6e.py: 6 passed in 14.94s
nfl/sim/tests/test_fwd6f.py: 9 passed in 1.91s
nfl/sim/tests/test_fwd7a.py: 12 passed in 2.11s
nfl/sim/tests/test_forward_v1.py: 8 passed in 0.29s
nfl/sim/tests/test_freeze_v1.py: 4 passed in 0.86s
```

Total: 263 passed, 0 failed, 0 skipped, 1 warning.

## Step 6 — refresh_inputs.py --week 4

```
Backed up 8 tables to /Users/jw115/mlb-model-archive/nfl_ratings_backups/20261002T015809Z
  pbp_2026: 8,311 rows, weeks [np.int32(1), np.int32(2), np.int32(3)]
```

Splice lines:
```
  player_usage_weekly.parquet: 2026 weeks [np.int64(1), np.int64(2), np.int64(3), np.int64(4)]
  active_universe_weekly.parquet: 2026 weeks [np.int64(1), np.int64(2), np.int64(3), np.int64(4), np.int64(5)]
  team_ratings_weekly.parquet: 2026 weeks [np.int64(1), np.int64(2), np.int64(3), np.int64(4)]
  tendencies_weekly.parquet: 2026 weeks [np.int64(1), np.int64(2), np.int64(3), np.int64(4)]
  tendencies_situational_weekly.parquet: 2026 weeks [np.int64(1), np.int64(2), np.int64(3), np.int64(4)]
  qb_ratings_weekly.parquet: 2026 weeks [np.int32(2), np.int32(3), np.int32(4)]
  kicker_weekly.parquet: 2026 weeks [np.int32(2), np.int32(3), np.int32(4)]
  league_baselines.parquet: 2026 weeks -
```

```
Fit-window fingerprint unchanged: 3638769c89030de0

FRESHNESS FAILED for week 4 (schedule: nflreadpy):
HALT: per-team input freshness failed:
  ATL: no week-4 injury report in the bundle
  NO: no week-4 injury report in the bundle
```

ATL and NO are the TNF teams; their injury reports are missing.

## Step 7 — Usage spot-check

```
DK Metcalf usage wk4 n_targets 24 pbp wk1-3 targets 24 | n_carries 0 pbp carries 0
KC Concepcion usage wk4 n_targets 20 pbp wk1-3 targets 20 | n_carries 4 pbp carries 4
Jerry Jeudy usage wk4 n_targets 5 pbp wk1-3 targets 5 | n_carries 0 pbp carries 0
Jaylen Warren usage wk4 n_targets 14 pbp wk1-3 targets 14 | n_carries 38 pbp carries 38
Quinshon Judkins usage wk4 n_targets 9 pbp wk1-3 targets 9 | n_carries 42 pbp carries 42
week-4 OUT players in the active universe: 0  any still active: False
```

All counts match exactly. No week-4 Out players remain in the active universe.

## Step 8 — Week-4 dry run through bootstrap

```
(a) Running test_freeze_v1...
    PASS
    Experiment manifest: OK
    Calibration stamp: OK
    Usage fingerprint: OK
```

Events: 14, Props: 426, Lines: 84. Games simulated: 14, Converged: 14/14.

Per-team freshness (all at week 4):
```
    ARI: team_ratings=4, tendencies=4, tendencies_situational=4, usage=4, active_universe=4, kickers=4, qb_ratings=4, active_universe_current=16, injury_game_statuses=0
    BAL: team_ratings=4, tendencies=4, tendencies_situational=4, usage=4, active_universe=4, kickers=4, qb_ratings=4, active_universe_current=16, injury_game_statuses=0
    BUF: ...=4, active_universe_current=15, injury_game_statuses=0
    CAR: ...=4, active_universe_current=17, injury_game_statuses=0
    CHI: ...=4, active_universe_current=14, injury_game_statuses=0
    CIN: ...=4, active_universe_current=15, injury_game_statuses=0
    DAL: ...=4, active_universe_current=15, injury_game_statuses=0
    DEN: ...=4, active_universe_current=16, injury_game_statuses=0
    DET: ...=4, active_universe_current=14, injury_game_statuses=0
    GB:  ...=4, active_universe_current=14, injury_game_statuses=0
    HOU: ...=4, active_universe_current=16, injury_game_statuses=0
    IND: ...=4, active_universe_current=16, injury_game_statuses=0
    JAX: ...=4, active_universe_current=16, injury_game_statuses=0
    KC:  ...=4, active_universe_current=17, injury_game_statuses=0
    LA:  ...=4, active_universe_current=18, injury_game_statuses=0
    LAC: ...=4, active_universe_current=16, injury_game_statuses=0
    LV:  ...=4, active_universe_current=15, injury_game_statuses=0
    MIA: ...=4, active_universe_current=16, injury_game_statuses=0
    MIN: ...=4, active_universe_current=15, injury_game_statuses=0
    NE:  ...=4, active_universe_current=16, injury_game_statuses=0
    NYG: ...=4, active_universe_current=16, injury_game_statuses=0
    NYJ: ...=4, active_universe_current=16, injury_game_statuses=0
    PHI: ...=4, active_universe_current=17, injury_game_statuses=0
    SEA: ...=4, active_universe_current=16, injury_game_statuses=0
    SF:  ...=4, active_universe_current=15, injury_game_statuses=0
    TB:  ...=4, active_universe_current=14, injury_game_statuses=0
    TEN: ...=4, active_universe_current=16, injury_game_statuses=0
    WAS: ...=4, active_universe_current=18, injury_game_statuses=2
```

All ratings tables at week 4. WAS has 2 injury game statuses; all others 0.

```
    Read set: 45 files — 14 from the run directory, 31 manifest-hashed repo files, 0 unproven
    Matched 66 / 257 two-way prop rows (51 player_receptions, 15 player_rush_attempts)
```

14 games anchored, all converged. `DRY RUN complete — nothing frozen.`

No freshness HALT on the dry run (ATL and NO excluded from the 14-game slate —
they played TNF and have no Sunday props).
