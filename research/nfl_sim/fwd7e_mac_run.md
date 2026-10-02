# FWD7e Mac run report — 2026-10-02

## Step 1
HEAD 2afe33878. Two modified tracked files (expected over-2MB refresh outputs): depth_charts.parquet, player_usage_weekly.parquet. PASS.

## Step 2
Hashes verified: patch 1d07f68c, a1cmp.py 30b0af91, a1eq.py 5e814b23, cx.py d5d4994b, gatecheck.py 8d350046, pit.py 32362645.
```
Applying: FWD7e (D275): ChatGPT audit #17 NO-GO accepted; PBP identity fields (game_id, season, week) validated on every raw row before any grouping, in every season usage.py and ratings.py aggregate; requirement tests for postseason and older seasons; input version D275-v5; audit #17 survivors killed
fcff24ce6 FWD7e (D275): ...
2afe33878 FWD7d Mac run: ...
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
nfl/sim/tests/test_fwd2_anchor.py: 3 passed in 0.34s
nfl/sim/tests/test_fwd2_bundle.py: 5 passed in 0.25s
nfl/sim/tests/test_fwd2_experiment.py: 6 passed in 1.07s
nfl/sim/tests/test_fwd2_item0_fixes.py: 7 passed in 1.11s
nfl/sim/tests/test_fwd2_settlement.py: 12 passed, 1 warning in 2.17s
nfl/sim/tests/test_fwd2b_harness.py: 10 passed in 44.72s
nfl/sim/tests/test_fwd3_item0.py: 9 passed in 35.61s
nfl/sim/tests/test_fwd3_item1.py: 3 passed in 0.30s
nfl/sim/tests/test_fwd3_item2.py: 8 passed in 1.24s
nfl/sim/tests/test_fwd4_item0.py: 9 passed in 25.78s
nfl/sim/tests/test_fwd4_item1.py: 4 passed in 6.23s
nfl/sim/tests/test_fwd5_pin.py: 4 passed in 6.48s
nfl/sim/tests/test_fwd6_item0.py: 13 passed in 35.25s
nfl/sim/tests/test_fwd6_item1.py: 12 passed in 64.72s
nfl/sim/tests/test_fwd6_item2.py: 9 passed in 30.84s
nfl/sim/tests/test_fwd6_item3.py: 5 passed in 10.78s
nfl/sim/tests/test_fwd6b.py: 39 passed in 125.48s
nfl/sim/tests/test_fwd6c.py: 33 passed in 77.59s
nfl/sim/tests/test_fwd6d.py: 33 passed in 74.53s
nfl/sim/tests/test_fwd6e.py: 6 passed in 15.12s
nfl/sim/tests/test_fwd6f.py: 11 passed in 2.01s
nfl/sim/tests/test_fwd7a.py: 27 passed in 3.51s
nfl/sim/tests/test_fwd7c.py: 11 passed in 1.52s
nfl/sim/tests/test_fwd7d.py: 7 passed in 0.59s
nfl/sim/tests/test_fwd7e.py: 7 passed in 0.40s
nfl/sim/tests/test_forward_v1.py: 8 passed in 0.30s
nfl/sim/tests/test_freeze_v1.py: 4 passed in 0.85s
```
Total: 305 passed, 0 failed, 0 skipped, 1 warning.

## Step 5b — Usage tests
```
22 passed, 1 deselected in 29.42s
```
git status: only two expected large files modified. PASS.

## Step 6 — refresh_inputs.py --week 4 (D275 builders)
Ran at Fri Oct  2 21:29:47 UTC 2026 (after Friday final reports).
```
Backed up 8 tables to /Users/jw115/mlb-model-archive/nfl_ratings_backups/20261002T212948Z
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
Archived this refresh's sources and tables (D275-v5) in /Users/jw115/mlb-model-archive/nfl_ratings_backups/20261002T212948Z/refreshed
```

Freshness: **PASS** all 32 teams. Exit 0. 3 of 28 Sunday teams with injury_game_statuses > 0: CLE (3), PIT (4), WAS (2).

Manifest:
```json
{
 "files": {
  "sources/depth_charts.parquet": "6622e4201cfccedcb015c07084321a9697d4ffd515cbf3399314142800a0cbe2",
  "sources/injuries.parquet": "c3f34711dcfa060015ee75c3cdd1faa50664e02799b662a68ff9de77cbbb26d7",
  "sources/pbp_2026.parquet": "0182083eb191aa66c6069b57ea126e6eac3cac2c7d9aaaf525ebbee155de6124",
  "sources/rosters_weekly.parquet": "c6910b7ef83be397da5d30fe47ba289919d2781ef8c3c8309c23230637304a06",
  "sources/schedules_2026.parquet": "5ffd583bb835fa9ceb788e54c7b2d0e4da832f91ccef15fe19bbbb2e9f68f5f4",
  "tables/active_universe_weekly.parquet": "7df1f253d018ea6ba16da34db5622ba6760d7ec77189a219e4cc51f35c1bb045",
  "tables/kicker_weekly.parquet": "984ec6669947b058b82c709014c47e64fba2d28f4103c35d94ee860856aa7ea6",
  "tables/league_baselines.parquet": "b372c1f8d48c2c276ba4bec760b94e9efef5a904fd62a2b9b0f1862f43e4d119",
  "tables/player_usage_weekly.parquet": "9662ab93327f94b650db2a8a1558ba389b68189ccb5d83d902028733ca135fa4",
  "tables/qb_ratings_weekly.parquet": "5ff4957a6b3826e8f866c901f3a6710d84537b884c83c3e4eaacf7cf4d740585",
  "tables/team_ratings_weekly.parquet": "d3a3224546418e6b14197af6f1b23aa2b29937a3bc93b232b85fa3dee1898f29",
  "tables/tendencies_situational_weekly.parquet": "ca670545df86ff3622e418e4cf5d6285deedf04600f3de463157f8f6cbea5a21",
  "tables/tendencies_weekly.parquet": "f10670cb5e389b1b7754c2ffc48ecc3aecc663701e5693a94ecb9d314b7a8a3e"
 },
 "input_version": "D275-v5",
 "refreshed_utc": "2026-10-02T21:37:42.515376+00:00",
 "season": 2026,
 "week": 4
}
```

## Step 7 — Audit #16/#17 counterexamples

### Clean build identity
```
base exit 0
  installed player_usage_weekly.parquet 2026 rows == base rebuild: True
  installed active_universe_weekly.parquet 2026 rows == base rebuild: True
installed week-4 active universe: rows 802, depth_order non-null 724, duplicate (team, player_id) 0, active_flag dtype bool, null flags 0
```

### D275 counterexamples — all 6 HALT
```
== null_week
null_week: pbp_2026 row 5492 altered
HALT (RuntimeError): pbp_2026.parquet: invalid game identities — 1 rows with week missing or not an integer in 1-22 (row index [5492])

== na_season
na_season: pbp_2026 row 5492 altered
HALT (RuntimeError): pbp_2026.parquet: invalid game identities — 1 rows with season missing or != 2026 (row index [5492])

== hist_null_gid
hist_null_gid: pbp_2025 row 5529 altered
HALT (RuntimeError): pbp_2025.parquet: invalid game identities — 1 rows with missing game_id (row index [5529])

== hist_null
hist_null: 2025 week-3 game_date set to null on 2746 rows
HALT (RuntimeError): pbp_2025.parquet: invalid game dates/identities — null/unparseable game_date in games ['2025_03_ARI_SF', '2025_03_ATL_CAR', '2025_03_CIN_MIN', '2025_03_DAL_CHI']

== conflict_early
conflict_early: added outcome-free week-5 row 2026_05_TB_DAL dated 2026-10-01 (snapshot gameday 2026-10-08)
HALT (RuntimeError): pbp_2026.parquet contradicts the archived schedule snapshot for 1 games ... [('2026_05_TB_DAL', 5, '2026-10-01', 5, '2026-10-08')]

== conflict_late
conflict_late: added outcome-free week-5 row 2026_05_TB_DAL dated 2026-10-09 (snapshot gameday 2026-10-08)
HALT (RuntimeError): pbp_2026.parquet contradicts the archived schedule snapshot for 1 games ... [('2026_05_TB_DAL', 5, '2026-10-09', 5, '2026-10-08')]
```

### D274 controls on audit #17's three (build without HALT)
```
== D274 null_week
BUILT, CHANGED player_usage_weekly.parquet: target_share values are different (1.24951 %)
BUILT, UNCHANGED active_universe_weekly.parquet

== D274 na_season
BUILT, CHANGED player_usage_weekly.parquet: target_share values are different (1.24951 %)
BUILT, UNCHANGED active_universe_weekly.parquet

== D274 hist_null_gid
BUILT, CHANGED player_usage_weekly.parquet: target_share values are different (100.0 %)
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
GATE PASS: 28 Sunday teams, tables from /tmp/e_base/tables
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

## Step 10 — Sunday smoke run (window-hours 51)
```
(a) PASS, Experiment manifest OK, Calibration stamp OK, Usage fingerprint OK
```
Bundle: nfl/data/board/week=2026_04/sim_runs/20261002T214025Z
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
