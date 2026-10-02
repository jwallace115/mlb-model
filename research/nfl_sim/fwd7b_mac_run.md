# FWD7b Mac run report — 2026-10-02

## Step 1 — State check
HEAD 7429e9dbf. Two modified tracked files (expected over-2MB FWD7a leftovers):
`nfl/data/pbp/depth_charts.parquet`, `nfl/data/sim/ratings/player_usage_weekly.parquet`. PASS.

## Step 2 — Apply and push
```
Applying: FWD7b (D272): ChatGPT audit #14 NO-GO accepted; one week-cutoff convention for live and historical depth/QB layers (archived schedule snapshot); duplicate or non-boolean active-universe rows HALT; runbook split windows; input version D272-v2 and roster cutoff declared; refresh archives sources/tables with a manifest; dependency drift requires all runtimes; audit #14 survivors killed
714da08d0 FWD7b (D272): ...
7429e9dbf FWD7a Mac run: ...
```
Hashes verified: patch d15d4f97, a1eq.py 10275484, a1cmp.py e422ae85, pit.py 32362645.

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

## Step 5 — Tests (per file)
```
nfl/sim/tests/test_fwd2_anchor.py: 3 passed in 0.45s
nfl/sim/tests/test_fwd2_bundle.py: 5 passed in 0.25s
nfl/sim/tests/test_fwd2_experiment.py: 6 passed in 1.08s
nfl/sim/tests/test_fwd2_item0_fixes.py: 7 passed in 1.10s
nfl/sim/tests/test_fwd2_settlement.py: 12 passed, 1 warning in 1.93s
nfl/sim/tests/test_fwd2b_harness.py: 10 passed in 44.49s
nfl/sim/tests/test_fwd3_item0.py: 9 passed in 35.43s
nfl/sim/tests/test_fwd3_item1.py: 3 passed in 0.30s
nfl/sim/tests/test_fwd3_item2.py: 8 passed in 1.25s
nfl/sim/tests/test_fwd4_item0.py: 9 passed in 25.95s
nfl/sim/tests/test_fwd4_item1.py: 4 passed in 6.32s
nfl/sim/tests/test_fwd5_pin.py: 4 passed in 6.49s
nfl/sim/tests/test_fwd6_item0.py: 13 passed in 34.49s
nfl/sim/tests/test_fwd6_item1.py: 12 passed in 64.90s
nfl/sim/tests/test_fwd6_item2.py: 9 passed in 31.05s
nfl/sim/tests/test_fwd6_item3.py: 5 passed in 10.83s
nfl/sim/tests/test_fwd6b.py: 39 passed in 125.51s
nfl/sim/tests/test_fwd6c.py: 33 passed in 80.04s
nfl/sim/tests/test_fwd6d.py: 33 passed in 75.18s
nfl/sim/tests/test_fwd6e.py: 6 passed in 15.30s
nfl/sim/tests/test_fwd6f.py: 11 passed in 2.04s
nfl/sim/tests/test_fwd7a.py: 27 passed in 3.42s
nfl/sim/tests/test_forward_v1.py: 8 passed in 0.30s
nfl/sim/tests/test_freeze_v1.py: 4 passed in 0.91s
```
Total: 280 passed, 0 failed, 0 skipped, 1 warning. Matches Cowork (280 on Linux 3.11 and standalone 3.13.7).

## Step 6 — refresh_inputs.py --week 4 (D272 builders)
```
Backed up 8 tables to /Users/jw115/mlb-model-archive/nfl_ratings_backups/20261002T041239Z
  schedules_2026: 272 games, weeks 1-18
  pbp_2026: 8,311 rows, weeks [np.int32(1), np.int32(2), np.int32(3)]
```

Splice:
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
Archived this refresh's sources and tables (D272-v2) in /Users/jw115/mlb-model-archive/nfl_ratings_backups/20261002T041239Z/refreshed
```

```
FRESHNESS FAILED for week 4 (schedule: local schedules_2026.parquet):
HALT: per-team input freshness failed:
  ATL: no week-4 injury report in the bundle
  NO: no week-4 injury report in the bundle
```
Exit 1: tables refreshed and installed. ATL and NO not ready (TNF teams, missing injury reports).

Manifest (`refresh_manifest.json`):
```json
{
 "files": {
  "sources/depth_charts.parquet": "1129a35a2675407066563cc64714d321083f16c923b4f530c0fc20a21e7b50a5",
  "sources/injuries.parquet": "2812942ddb4953ea36129ac0411f1e55176542a9574602b0954a346a6eba32d6",
  "sources/pbp_2026.parquet": "888ef21836ae8f33df33d6e7e7a7038619ebd58e89c22507638bafbd9e8d70ef",
  "sources/rosters_weekly.parquet": "e7ca239b8221e5c48d10973451a9f8ce52662f58047885e202d0414f18136ccb",
  "sources/schedules_2026.parquet": "bbb0883ed2d67aa3b9eac5344113d8abf98b64b13fe19380f9a0c7480a8c1583",
  "tables/active_universe_weekly.parquet": "425aea6a9a7c271711113435343767df7fc97365e932665b1ddfdbedbebc47bf",
  "tables/kicker_weekly.parquet": "515dcfb4aca339787462e3a565b3b2cc7b7ffb71f9eb70a4c29702d4b0c155eb",
  "tables/league_baselines.parquet": "d48a119fd9d0cf6db18ff54e60dac32149cffbe0ad3e18e4cf7d54b8ae648853",
  "tables/player_usage_weekly.parquet": "c865d5f9b1d6959d9ee079d782867f369bb951567705bfbaf59c76817863b3cd",
  "tables/qb_ratings_weekly.parquet": "73097488deaef89ca8c6b856cfe43d0a85114f5acbca7b70945862c4deeb5618",
  "tables/team_ratings_weekly.parquet": "1f957aa23ffe4a425fa25883f6cc4d88b8767e6918bb779f3bb478928fbfeb43",
  "tables/tendencies_situational_weekly.parquet": "3e46f64a7e4bf352e15caee12b03db775e612c29054d104d67b715621328ee48",
  "tables/tendencies_weekly.parquet": "583e646bfd6893ce5d08cbdd5d00edbb2c3e27ad41cc851c4e985ee33c170a96"
 },
 "input_version": "D272-v2",
 "refreshed_utc": "2026-10-02T04:20:34.988693+00:00",
 "season": 2026,
 "week": 4
}
```

## Step 7 — Audit #14 A1 equivalence and point-in-time identity

### Equivalence (D272)
```
base exit 0
plus exit 0
plus: added one date-only row 2026_04_PIT_CLE 2026-10-01

EQUIVALENT player_usage_weekly.parquet: 2056 2026 rows identical with and without a date-only week-4 PBP row
  installed player_usage_weekly.parquet 2026 rows == base rebuild: True
EQUIVALENT active_universe_weekly.parquet: 4102 2026 rows identical with and without a date-only week-4 PBP row
  installed active_universe_weekly.parquet 2026 rows == base rebuild: True
installed week-4 active universe: rows 800, depth_order non-null 722, duplicate (team, player_id) 0, active_flag dtype bool, null flags 0
  week 1: rows 922, depth_order non-null 795
  week 2: rows 786, depth_order non-null 718
  week 3: rows 794, depth_order non-null 720
```

### Negative control (D271 builder)
```
DIFFERENT player_usage_weekly.parquet: DataFrame.iloc[:, 6] (column name="target_share") are different
DataFrame.iloc[:, 6] (column name="target_share") values are different (24.56226 %)
DIFFERENT active_universe_weekly.parquet: DataFrame.iloc[:, 5] (column name="depth_order") are different
DataFrame.iloc[:, 5] (column name="depth_order") values are different (35.20234 %)
```

### Point-in-time identity (D272)
```
POINT-IN-TIME OK player_usage_weekly.parquet: week-2 rows (513) identical when built with PBP through week 1 only
POINT-IN-TIME OK active_universe_weekly.parquet: week-2 rows (786) identical when built with PBP through week 1 only
POINT-IN-TIME OK player_usage_weekly.parquet: week-3 rows (518) identical when built with PBP through week 2 only
POINT-IN-TIME OK active_universe_weekly.parquet: week-3 rows (794) identical when built with PBP through week 2 only
```

### Point-in-time negative control (D271 builder)
```
POINT-IN-TIME DIFF player_usage_weekly.parquet: DataFrame.iloc[:, 6] (column name="target_share") are different
POINT-IN-TIME DIFF active_universe_weekly.parquet: DataFrame.iloc[:, 5] (column name="depth_order") are different
```

## Step 8 — Usage spot-check
```
DK Metcalf usage wk4 n_targets 24 pbp wk1-3 targets 24 | n_carries 0 pbp carries 0
KC Concepcion usage wk4 n_targets 20 pbp wk1-3 targets 20 | n_carries 4 pbp carries 4
Jerry Jeudy usage wk4 n_targets 5 pbp wk1-3 targets 5 | n_carries 0 pbp carries 0
Jaylen Warren usage wk4 n_targets 14 pbp wk1-3 targets 14 | n_carries 38 pbp carries 38
Quinshon Judkins usage wk4 n_targets 9 pbp wk1-3 targets 9 | n_carries 42 pbp carries 42
week-4 Out/Doubtful report rows 2 | of them in the skill universe 0 | any still active: False
```

## Step 9 — Runbook check
```
RUNBOOK MATCHES
```
Week-4 section: 4 windows — PIT@CLE (Thu TNF), IND@WAS (Sun London), Sunday main+SNF (13 games), ATL@NO (Mon).

## Step 10 — Production-command smoke run (window-hours 68)
```
(a) PASS, Experiment manifest OK, Calibration stamp OK, Usage fingerprint OK
Events: 14, Props: 426, Lines: 84
Games simulated: 14, Converged: 14/14
Read set: 45 files — 14 from the run directory, 31 manifest-hashed repo files, 0 unproven
Matched 66 / 257 two-way prop rows
DRY RUN complete — nothing frozen.
```
Per-team freshness: all 28 teams at week 4 across all tables. WAS: injury_game_statuses=2; all others 0.
No freshness HALT (ATL/NO excluded from 68h window — TNF already past).
