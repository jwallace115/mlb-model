# FWD7d Mac run report — 2026-10-02

## Step 1
HEAD 9c7bf9dfa. Two modified tracked files (expected over-2MB): depth_charts.parquet, player_usage_weekly.parquet. PASS.

## Step 2
Hashes verified: patch 195f05be, a1cmp.py 30b0af91, a1eq.py 5e814b23, cx.py 463333cf, gatecheck.py 8d350046, pit.py 32362645.
```
Applying: FWD7d (D274): ChatGPT audit #16 NO-GO accepted; PBP game dates validated in every season (one valid date and week per game) and every built season-week needs a cutoff; PBP games must agree with the archived schedule snapshot (contradictions HALT, cutoff from the snapshot); 5J-2 QB-cutoff test owns its fixture; input version D274-v4; audit #16 survivors killed
b9bae4830 FWD7d (D274): ...
9c7bf9dfa FWD7c Mac run: ...
```

## Step 3
```
exit 0
launcher hash ok: True {'n_repo_modules': 12, 'n_dependency_files': 1090, 'n_distribution_files_verified': 6395}
```

## Step 4
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
nfl/sim/tests/test_fwd2_anchor.py: 3 passed in 0.50s
nfl/sim/tests/test_fwd2_bundle.py: 5 passed in 0.23s
nfl/sim/tests/test_fwd2_experiment.py: 6 passed in 1.06s
nfl/sim/tests/test_fwd2_item0_fixes.py: 7 passed in 1.08s
nfl/sim/tests/test_fwd2_settlement.py: 12 passed, 1 warning in 1.98s
nfl/sim/tests/test_fwd2b_harness.py: 10 passed in 43.77s
nfl/sim/tests/test_fwd3_item0.py: 9 passed in 34.71s
nfl/sim/tests/test_fwd3_item1.py: 3 passed in 0.29s
nfl/sim/tests/test_fwd3_item2.py: 8 passed in 1.22s
nfl/sim/tests/test_fwd4_item0.py: 9 passed in 25.62s
nfl/sim/tests/test_fwd4_item1.py: 4 passed in 6.19s
nfl/sim/tests/test_fwd5_pin.py: 4 passed in 6.41s
nfl/sim/tests/test_fwd6_item0.py: 13 passed in 35.11s
nfl/sim/tests/test_fwd6_item1.py: 12 passed in 64.03s
nfl/sim/tests/test_fwd6_item2.py: 9 passed in 30.62s
nfl/sim/tests/test_fwd6_item3.py: 5 passed in 10.62s
nfl/sim/tests/test_fwd6b.py: 39 passed in 125.20s
nfl/sim/tests/test_fwd6c.py: 33 passed in 77.95s
nfl/sim/tests/test_fwd6d.py: 33 passed in 74.15s
nfl/sim/tests/test_fwd6e.py: 6 passed in 15.12s
nfl/sim/tests/test_fwd6f.py: 11 passed in 1.97s
nfl/sim/tests/test_fwd7a.py: 27 passed in 3.36s
nfl/sim/tests/test_fwd7c.py: 11 passed in 1.40s
nfl/sim/tests/test_fwd7d.py: 7 passed in 0.59s
nfl/sim/tests/test_forward_v1.py: 8 passed in 0.39s
nfl/sim/tests/test_freeze_v1.py: 4 passed in 0.88s
```
Total: 298 passed, 0 failed, 0 skipped, 1 warning.

## Step 5b — Usage tests
```
22 passed, 1 deselected in 28.86s
```
git status: only two expected large files modified. PASS.

## Step 6 — refresh_inputs.py --week 4 (D274 builders)
Ran at Fri Oct  2 18:31:43 UTC 2026.
```
Backed up 8 tables to /Users/jw115/mlb-model-archive/nfl_ratings_backups/20261002T183144Z
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
Archived this refresh's sources and tables (D274-v4) in /Users/jw115/mlb-model-archive/nfl_ratings_backups/20261002T183144Z/refreshed
```

Freshness: **PASS** all 32 teams. Exit 0. CLE injury_game_statuses=3, PIT=4, WAS=2; rest 0.

Manifest:
```json
{
 "files": {
  "sources/depth_charts.parquet": "6622e4201cfccedcb015c07084321a9697d4ffd515cbf3399314142800a0cbe2",
  "sources/injuries.parquet": "c3f34711dcfa060015ee75c3cdd1faa50664e02799b662a68ff9de77cbbb26d7",
  "sources/pbp_2026.parquet": "0182083eb191aa66c6069b57ea126e6eac3cac2c7d9aaaf525ebbee155de6124",
  "sources/rosters_weekly.parquet": "c6910b7ef83be397da5d30fe47ba289919d2781ef8c3c8309c23230637304a06",
  "sources/schedules_2026.parquet": "30c7914eb942f400164ea2cb999aa8c9fd2aa53ef03d1792d1a36c6694fa1a1b",
  "tables/active_universe_weekly.parquet": "7df1f253d018ea6ba16da34db5622ba6760d7ec77189a219e4cc51f35c1bb045",
  "tables/kicker_weekly.parquet": "984ec6669947b058b82c709014c47e64fba2d28f4103c35d94ee860856aa7ea6",
  "tables/league_baselines.parquet": "b372c1f8d48c2c276ba4bec760b94e9efef5a904fd62a2b9b0f1862f43e4d119",
  "tables/player_usage_weekly.parquet": "9662ab93327f94b650db2a8a1558ba389b68189ccb5d83d902028733ca135fa4",
  "tables/qb_ratings_weekly.parquet": "5ff4957a6b3826e8f866c901f3a6710d84537b884c83c3e4eaacf7cf4d740585",
  "tables/team_ratings_weekly.parquet": "d3a3224546418e6b14197af6f1b23aa2b29937a3bc93b232b85fa3dee1898f29",
  "tables/tendencies_situational_weekly.parquet": "ca670545df86ff3622e418e4cf5d6285deedf04600f3de463157f8f6cbea5a21",
  "tables/tendencies_weekly.parquet": "f10670cb5e389b1b7754c2ffc48ecc3aecc663701e5693a94ecb9d314b7a8a3e"
 },
 "input_version": "D274-v4",
 "refreshed_utc": "2026-10-02T18:39:41.983980+00:00",
 "season": 2026,
 "week": 4
}
```

## Step 7 — Audit #16 counterexamples

### Clean build identity
```
base exit 0
  installed player_usage_weekly.parquet 2026 rows == base rebuild: True
  installed active_universe_weekly.parquet 2026 rows == base rebuild: True
installed week-4 active universe: rows 802, depth_order non-null 724, duplicate (team, player_id) 0, active_flag dtype bool, null flags 0
```

### D274 counterexamples (all three HALT)
```
hist_null: 2025 week-3 game_date set to null on 2746 rows
HALT (RuntimeError): pbp_2025.parquet: invalid game dates/identities — null/unparseable game_date in games ['2025_03_ARI_SF', '2025_03_ATL_CAR', '2025_03_CIN_MIN', '2025_03_DAL_CHI']

conflict_early: added outcome-free week-5 row 2026_05_TB_DAL dated 2026-10-01 (snapshot gameday 2026-10-08)
HALT (RuntimeError): pbp_2026.parquet contradicts the archived schedule snapshot for 1 games (game_id, pbp week, pbp date, snapshot week, snapshot date): [('2026_05_TB_DAL', 5, '2026-10-01', 5, '2026-10-08')]

conflict_late: added outcome-free week-5 row 2026_05_TB_DAL dated 2026-10-09 (snapshot gameday 2026-10-08)
HALT (RuntimeError): pbp_2026.parquet contradicts the archived schedule snapshot for 1 games (game_id, pbp week, pbp date, snapshot week, snapshot date): [('2026_05_TB_DAL', 5, '2026-10-09', 5, '2026-10-08')]
```

### D273 controls (build without HALT — the defect the patch closes)
```
hist_null:
BUILT, CHANGED player_usage_weekly.parquet: target_share 100% different
BUILT, UNCHANGED active_universe_weekly.parquet

conflict_early:
BUILT, UNCHANGED player_usage_weekly.parquet
BUILT, UNCHANGED active_universe_weekly.parquet
```

### Point-in-time identity W=2,3,4
```
POINT-IN-TIME OK player_usage_weekly.parquet: week-2 rows (513) identical when built with PBP through week 1 only
POINT-IN-TIME OK active_universe_weekly.parquet: week-2 rows (786) identical when built with PBP through week 1 only
POINT-IN-TIME OK player_usage_weekly.parquet: week-3 rows (518) identical when built with PBP through week 2 only
POINT-IN-TIME OK active_universe_weekly.parquet: week-3 rows (794) identical when built with PBP through week 2 only
POINT-IN-TIME OK player_usage_weekly.parquet: week-4 rows (506) identical when built with PBP through week 3 only
POINT-IN-TIME OK active_universe_weekly.parquet: week-4 rows (802) identical when built with PBP through week 3 only
```

### Forward gate
```
GATE PASS: 28 Sunday teams, tables from /tmp/d_base/tables
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

## Step 9
```
RUNBOOK MATCHES
```

## Step 10 — Sunday smoke run (window-hours 54)
```
(a) PASS, Experiment manifest OK, Calibration stamp OK, Usage fingerprint OK
```
Bundle: nfl/data/board/week=2026_04/sim_runs/20261002T184232Z
Events: 14, Props: 426, Lines: 84.
Per-team freshness (all 28 Sunday teams, verbatim):
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
