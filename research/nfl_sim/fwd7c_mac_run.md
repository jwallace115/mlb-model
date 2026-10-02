# FWD7c Mac run report — 2026-10-02

## Step 1 — State check
HEAD a7bd0c62a. Two modified tracked files (expected over-2MB): depth_charts.parquet, player_usage_weekly.parquet. PASS.

## Step 2 — Hash check, apply, push
Hashes verified: patch 0374be66, a1cmp.py 30b0af91, a1eq.py 5e814b23, gatecheck.py 8d350046, pit.py 32362645.
```
Applying: FWD7c (D273): ChatGPT audit #15 NO-GO accepted; week cutoffs use valid dates only (earliest of schedule and PBP) and HALT when a needed week has none; schedule snapshot must cover weeks 1-18; forward gate HALTs when a team's week has no depth ranks; stale 5J-2 live-kickoff test rewritten for the D272 convention; input version D273-v3; audit #15 survivors killed
8803102d8 FWD7c (D273): ...
a7bd0c62a FWD7b Mac run: ...
```

## Step 3 — Selftest
```
exit 0
launcher hash ok: True {'n_repo_modules': 12, 'n_dependency_files': 1090, 'n_distribution_files_verified': 6395}
```

## Step 4 — PBP history hashes
```
2020 4126188fda860f3f
2021 a9741a722a22dde8
2022 6809039bb075367d
2023 81984d68970d50a9
2024 35d5a2e28e4f3873
2025 cc0dd69de7cd91f0
```

## Step 5a — Forward suite tests (per file)
```
nfl/sim/tests/test_fwd2_anchor.py: 3 passed in 0.42s
nfl/sim/tests/test_fwd2_bundle.py: 5 passed in 0.23s
nfl/sim/tests/test_fwd2_experiment.py: 6 passed in 1.01s
nfl/sim/tests/test_fwd2_item0_fixes.py: 7 passed in 1.08s
nfl/sim/tests/test_fwd2_settlement.py: 12 passed, 1 warning in 2.11s
nfl/sim/tests/test_fwd2b_harness.py: 10 passed in 43.98s
nfl/sim/tests/test_fwd3_item0.py: 9 passed in 35.05s
nfl/sim/tests/test_fwd3_item1.py: 3 passed in 0.29s
nfl/sim/tests/test_fwd3_item2.py: 8 passed in 1.25s
nfl/sim/tests/test_fwd4_item0.py: 9 passed in 25.59s
nfl/sim/tests/test_fwd4_item1.py: 4 passed in 6.57s
nfl/sim/tests/test_fwd5_pin.py: 4 passed in 6.59s
nfl/sim/tests/test_fwd6_item0.py: 13 passed in 36.36s
nfl/sim/tests/test_fwd6_item1.py: 12 passed in 64.29s
nfl/sim/tests/test_fwd6_item2.py: 9 passed in 30.77s
nfl/sim/tests/test_fwd6_item3.py: 5 passed in 10.65s
nfl/sim/tests/test_fwd6b.py: 39 passed in 124.91s
nfl/sim/tests/test_fwd6c.py: 33 passed in 77.67s
nfl/sim/tests/test_fwd6d.py: 33 passed in 74.77s
nfl/sim/tests/test_fwd6e.py: 6 passed in 16.33s
nfl/sim/tests/test_fwd6f.py: 11 passed in 2.21s
nfl/sim/tests/test_fwd7a.py: 27 passed in 3.85s
nfl/sim/tests/test_fwd7c.py: 11 passed in 1.47s
nfl/sim/tests/test_forward_v1.py: 8 passed in 0.30s
nfl/sim/tests/test_freeze_v1.py: 4 passed in 0.92s
```
Total: 291 passed, 0 failed, 0 skipped, 1 warning.

## Step 5b — Usage tests
```
22 passed, 1 deselected in 29.98s
```
git status --short --untracked-files=no: only two expected large files modified. PASS.

## Step 6 — refresh_inputs.py --week 4 (D273 builders)
```
Backed up 8 tables to /Users/jw115/mlb-model-archive/nfl_ratings_backups/20261002T122158Z
  schedules_2026: 272 games, weeks 1-18
  pbp_2026: 8,497 rows, weeks [np.int32(1), np.int32(2), np.int32(3), np.int32(4)]
```

Splice:
```
  player_usage_weekly.parquet: 2026 weeks [np.int64(1), np.int64(2), np.int64(3), np.int64(4), np.int64(5)]
  active_universe_weekly.parquet: 2026 weeks [np.int64(1), np.int64(2), np.int64(3), np.int64(4), np.int64(5)]
  team_ratings_weekly.parquet: 2026 weeks [np.int64(1), np.int64(2), np.int64(3), np.int64(4), np.int64(5)]
  tendencies_weekly.parquet: 2026 weeks [np.int64(1), np.int64(2), np.int64(3), np.int64(4), np.int64(5)]
  tendencies_situational_weekly.parquet: 2026 weeks [np.int64(1), np.int64(2), np.int64(3), np.int64(4), np.int64(5)]
  qb_ratings_weekly.parquet: 2026 weeks [np.int32(2), np.int32(3), np.int32(4), np.int32(5)]
  kicker_weekly.parquet: 2026 weeks [np.int32(2), np.int32(3), np.int32(4), np.int32(5)]
  league_baselines.parquet: 2026 weeks -
```

```
Fit-window fingerprint unchanged: 3638769c89030de0
Archived this refresh's sources and tables (D273-v3) in /Users/jw115/mlb-model-archive/nfl_ratings_backups/20261002T122158Z/refreshed
```

Freshness: **PASS** (all 32 teams). Exit 0. Key injury counts: CLE 3, PIT 4, WAS 2; rest 0.

Manifest (`refresh_manifest.json`):
```json
{
 "files": {
  "sources/depth_charts.parquet": "284d92d3e40fc26ce2f68afe62fc4cb3bcdba444fb63783e211e6dd977c8df5c",
  "sources/injuries.parquet": "c3f34711dcfa060015ee75c3cdd1faa50664e02799b662a68ff9de77cbbb26d7",
  "sources/pbp_2026.parquet": "3a8714c834c6d31959c88c8685845d2b60e8f10602c366013d45018a77fd2519",
  "sources/rosters_weekly.parquet": "f3453d078efb6d0012abcf72b98559b1e8a62fe64f7898b07a00587c5fb65b49",
  "sources/schedules_2026.parquet": "43946df928a63eedb49203777514779023edc79a7facfac31eff6e1e09bacbff",
  "tables/active_universe_weekly.parquet": "f6110f72789a30a39c6dbaf0bd09b6d40dba1210819e087778970e665abc59fa",
  "tables/kicker_weekly.parquet": "984ec6669947b058b82c709014c47e64fba2d28f4103c35d94ee860856aa7ea6",
  "tables/league_baselines.parquet": "53bad7d1d7441f19568f6d6a3e4f0bb9d43e0dc66d83816b09d35613dae19f3c",
  "tables/player_usage_weekly.parquet": "5dc1914d65cc8f3417f1519d4b8d722fd17eca7c76694f3fff6101cb27e4fb80",
  "tables/qb_ratings_weekly.parquet": "fda72abbb65dd1be91662776f6c71cf887d01ba19d85b37a72eaf6ebd4616c57",
  "tables/team_ratings_weekly.parquet": "6bc3969bda9448ae31f466d1df7dcc66376338b38cfda3f1a8432c7f70b72a7a",
  "tables/tendencies_situational_weekly.parquet": "ca670545df86ff3622e418e4cf5d6285deedf04600f3de463157f8f6cbea5a21",
  "tables/tendencies_weekly.parquet": "f10670cb5e389b1b7754c2ffc48ecc3aecc663701e5693a94ecb9d314b7a8a3e"
 },
 "input_version": "D273-v3",
 "refreshed_utc": "2026-10-02T12:29:49.209132+00:00",
 "season": 2026,
 "week": 4
}
```

## Step 7 — Audit #15 A1

### Equivalence (D273)
```
base exit 0
plus exit 0
null exit 0
plus: added one outcome-free row 2026_04_PIT_CLE 2026-10-01
null: added one outcome-free row 2026_04_PIT_CLE None
```

Base vs plus:
```
EQUIVALENT player_usage_weekly.parquet: 2561 2026 rows identical with and without the extra outcome-free week-4 PBP row
  installed player_usage_weekly.parquet 2026 rows == base rebuild: True
EQUIVALENT active_universe_weekly.parquet: 4102 2026 rows identical with and without the extra outcome-free week-4 PBP row
  installed active_universe_weekly.parquet 2026 rows == base rebuild: True
installed week-4 active universe: rows 800, depth_order non-null 723, duplicate (team, player_id) 0, active_flag dtype bool, null flags 0
```

Base vs null:
```
EQUIVALENT player_usage_weekly.parquet: 2561 2026 rows identical
  installed player_usage_weekly.parquet 2026 rows == base rebuild: True
EQUIVALENT active_universe_weekly.parquet: 4102 2026 rows identical
  installed active_universe_weekly.parquet 2026 rows == base rebuild: True
installed week-4 active universe: rows 800, depth_order non-null 723, duplicate (team, player_id) 0, active_flag dtype bool, null flags 0
```

### D272 control with null-date
```
EQUIVALENT player_usage_weekly.parquet: 2561 2026 rows identical
EQUIVALENT active_universe_weekly.parquet: 4102 2026 rows identical
```
(The D272 builder also handles the null-date row correctly on this data — the null-date fix guards against a different PBP shape.)

### Forward gate check
```
=== c_base ===
GATE PASS: 28 Sunday teams, tables from /tmp/c_base/tables
=== o_null ===
GATE PASS: 28 Sunday teams, tables from /tmp/o_null/tables
=== c_null ===
GATE PASS: 28 Sunday teams, tables from /tmp/c_null/tables
```

### Point-in-time identity (D273)
```
POINT-IN-TIME OK player_usage_weekly.parquet: week-2 rows (513) identical when built with PBP through week 1 only
POINT-IN-TIME OK active_universe_weekly.parquet: week-2 rows (786) identical when built with PBP through week 1 only
POINT-IN-TIME OK player_usage_weekly.parquet: week-3 rows (518) identical when built with PBP through week 2 only
POINT-IN-TIME OK active_universe_weekly.parquet: week-3 rows (794) identical when built with PBP through week 2 only
```

## Step 8 — Usage spot-check
```
DK Metcalf usage wk4 n_targets 24 pbp wk1-3 targets 24 | n_carries 0 pbp carries 0
KC Concepcion usage wk4 n_targets 20 pbp wk1-3 targets 20 | n_carries 4 pbp carries 4
Jerry Jeudy usage wk4 n_targets 5 pbp wk1-3 targets 5 | n_carries 0 pbp carries 0
Jaylen Warren usage wk4 n_targets 14 pbp wk1-3 targets 14 | n_carries 38 pbp carries 38
Quinshon Judkins usage wk4 n_targets 9 pbp wk1-3 targets 9 | n_carries 42 pbp carries 42
week-4 injury report rows 291 | Out/Doubtful 7 | of them in the skill universe 2 | any still active: False
```

## Step 9 — Runbook check
```
RUNBOOK MATCHES
```

## Step 10 — Sunday smoke run (window-hours 60)
```
(a) PASS, Experiment manifest OK, Calibration stamp OK, Usage fingerprint OK
```
Bundle: nfl/data/board/week=2026_04/sim_runs/20261002T123229Z
Events: 14, Props: 426, Lines: 84.
Per-team freshness (all 28 Sunday teams at week 4, verbatim):
```
    ARI: last_played_week=3, team_ratings=4, tendencies=4, tendencies_situational=4, usage=4, active_universe=4, kickers=4, qb_ratings=4, active_universe_current=16, injury_game_statuses=0
    BAL: ...=4, active_universe_current=16, injury_game_statuses=0
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
```
Read set: 45 files — 14 from the run directory, 31 manifest-hashed repo files, 0 unproven
Games simulated: 14, Converged: 14/14
Matched 66 / 257 two-way prop rows
DRY RUN complete — nothing frozen.
```
No freshness HALT.
