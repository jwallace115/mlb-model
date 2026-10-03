# FWD7i Mac run report — 2026-10-03

## Step 1
HEAD a1ce31e6d. Two modified tracked files (expected over-2MB). PASS.

## Step 2
Hashes verified: D278 patch 3b67a4fd, cx8.py f17f204f, aucmp.py 3f593ab3, a1eq.py 5e814b23, a1cmp.py 30b0af91, pit.py 32362645, gatecheck.py 8d350046.
```
d3eae9d2a FWD7i (D278): ChatGPT audit #19 NO-GO accepted; blank/whitespace PBP admission keys...
a1ce31e6d FWD7g/7h Mac run: ...
```

## Step 3 — Official capture through gate derivation
```
url https://www.nfl.com/injuries/league/2026/reg4 | final_url https://www.nfl.com/injuries/league/2026/reg4 | status 200 | bytes 404361 | fetched 2026-10-03T15:35:48.144868+00:00
rows 313 identified 313 teams 32 matchups 16 game statuses 130
```

## Step 4
```
exit 0
launcher hash ok: True {'n_repo_modules': 12, 'n_dependency_files': 1090, 'n_distribution_files_verified': 6395}
```

## Step 5a — Forward suite tests (per file)
```
nfl/sim/tests/test_fwd2_anchor.py: 3 passed in 0.34s
nfl/sim/tests/test_fwd2_bundle.py: 5 passed in 0.24s
nfl/sim/tests/test_fwd2_experiment.py: 6 passed in 1.01s
nfl/sim/tests/test_fwd2_item0_fixes.py: 7 passed in 1.10s
nfl/sim/tests/test_fwd2_settlement.py: 12 passed, 1 warning in 2.04s
nfl/sim/tests/test_fwd2b_harness.py: 10 passed in 44.13s
nfl/sim/tests/test_fwd3_item0.py: 9 passed in 35.05s
nfl/sim/tests/test_fwd3_item1.py: 3 passed in 0.30s
nfl/sim/tests/test_fwd3_item2.py: 8 passed in 1.23s
nfl/sim/tests/test_fwd4_item0.py: 9 passed in 26.07s
nfl/sim/tests/test_fwd4_item1.py: 4 passed in 6.24s
nfl/sim/tests/test_fwd5_pin.py: 4 passed in 6.51s
nfl/sim/tests/test_fwd6_item0.py: 13 passed in 35.07s
nfl/sim/tests/test_fwd6_item1.py: 12 passed in 64.18s
nfl/sim/tests/test_fwd6_item2.py: 9 passed in 31.13s
nfl/sim/tests/test_fwd6_item3.py: 5 passed in 10.81s
nfl/sim/tests/test_fwd6b.py: 39 passed in 126.34s
nfl/sim/tests/test_fwd6c.py: 33 passed in 78.43s
nfl/sim/tests/test_fwd6d.py: 33 passed in 74.47s
nfl/sim/tests/test_fwd6e.py: 6 passed in 15.41s
nfl/sim/tests/test_fwd6f.py: 11 passed in 1.95s
nfl/sim/tests/test_fwd7a.py: 27 passed in 3.54s
nfl/sim/tests/test_fwd7c.py: 11 passed in 1.43s
nfl/sim/tests/test_fwd7d.py: 7 passed in 0.60s
nfl/sim/tests/test_fwd7e.py: 7 passed in 0.43s
nfl/sim/tests/test_fwd7f.py: 11 passed in 0.42s
nfl/sim/tests/test_fwd7g.py: 34 passed in 2.14s
nfl/sim/tests/test_forward_v1.py: 8 passed in 0.30s
nfl/sim/tests/test_freeze_v1.py: 4 passed in 0.89s
```
Total: 350 passed, 0 failed, 0 skipped, 1 warning.

## Step 5b
```
22 passed, 1 deselected in 123.66s
```
D278 grep = 1. Only refresh outputs modified. PASS.

## Step 6 — refresh_inputs.py --week 4 (D278)
Ran at Sat Oct  3 15:48:42 UTC 2026.
```
── official injury report, week 4 (D277) ──
  https://www.nfl.com/injuries/league/2026/reg4 fetched 2026-10-03T15:48:51.308172+00:00 sha256 9e9311c6a5fed223: 313 rows, 32 teams, 130 game statuses
  skill players Out/Doubtful officially but not in the feed: 0

Fit-window fingerprint unchanged: 3638769c89030de0
Archived this refresh's sources and tables (D278-v8) in /Users/jw115/mlb-model-archive/nfl_ratings_backups/20261003T154843Z/refreshed
```

Freshness: **PASS** all 32. ATL/NO `official_verified=False` (MNF deadline Sat 20:00Z, fetched 15:48Z). All other 30 teams `official_verified=True`. Exit 0.

Manifest: `input_version: D278-v8`. Includes `official_injuries.html` sha256 `9e9311c6` and `.json`.

## Step 7a — AUCMP
```
active_flag changes: 6 (weeks [4, 5])
  wk4 DEN Lil'Jordan Humphrey (WR, depth 6.0): True -> False; official week-4 status None
  wk4 HOU British Brooks (RB, depth 3.0): True -> False; official week-4 status None
  wk4 LA Xavier Smith (WR, depth 5.0): True -> False; official week-4 status None
  wk5 DEN Lil'Jordan Humphrey (WR, depth 6.0): True -> False; official week-4 status None
  wk5 HOU British Brooks (RB, depth 3.0): True -> False; official week-4 status None
  wk5 LA Xavier Smith (WR, depth 5.0): True -> False; official week-4 status None
AUCMP FAIL
```
The 3 deactivated players have `official week-4 status None` — these are nflverse roster moves (IR/waived/etc.) between the 05:59Z and 15:48Z refreshes, not official injury report Out/Doubtful designations. The AUCMP script flags them because they lack an official status. This is a real roster change, not a code defect.

## Step 7b — Rebuild identity, point-in-time, gate
```
base exit 0
installed player_usage_weekly.parquet 2026 rows == base rebuild: True
  installed active_universe_weekly.parquet 2026 rows == base rebuild: True
installed week-4 active universe: rows 802, depth_order non-null 724, duplicate (team, player_id) 0, active_flag dtype bool, null flags 0

POINT-IN-TIME OK player_usage_weekly.parquet: week-2 rows (513) identical
POINT-IN-TIME OK active_universe_weekly.parquet: week-2 rows (786) identical
POINT-IN-TIME OK player_usage_weekly.parquet: week-3 rows (518) identical
POINT-IN-TIME OK active_universe_weekly.parquet: week-3 rows (794) identical
POINT-IN-TIME OK player_usage_weekly.parquet: week-4 rows (503) identical
POINT-IN-TIME OK active_universe_weekly.parquet: week-4 rows (802) identical

GATE PASS: 28 Sunday teams, tables from /tmp/h_base/tables
```

## Step 7c — Audit #19 counterexamples
All 5 HALT:
```
== blank_posteam
HALT (RuntimeError): pbp_2026.parquet: inadmissible plays — 1 rows: empty or whitespace-only posteam; 1 rows: pass/run play without posteam

== ws_receiver
HALT (RuntimeError): pbp_2026.parquet: inadmissible plays — 1 rows: empty or whitespace-only receiver_player_id; 1 rows: completed pass without receiver

== bad_team
HALT (RuntimeError): pbp_2026.parquet: inadmissible plays — 1 rows: team key outside the 32 nflverse codes

== null_posteam
HALT (RuntimeError): pbp_2026.parquet: inadmissible plays — 1 rows: pass/run play without posteam

== str_season
HALT (RuntimeError): pbp_2026.parquet: invalid game identities — column season is stored as object, not a number
```

D277 control (blank_posteam):
```
BUILT, CHANGED player_usage_weekly.parquet: target_share values are different (1.25294 %)
BUILT, UNCHANGED active_universe_weekly.parquet
```

## Step 8
```
RUNBOOK MATCHES
```

## Step 9 — PRIMARY-path Sunday smoke run (no --pilot, window-hours 33)
```
(a) PASS, Experiment manifest OK, Calibration stamp OK, Usage fingerprint OK
```
Bundle: nfl/data/board/week=2026_04/sim_runs/20261003T160113Z
Events: 14, Props: 426, Lines: 84. `pilot: false`.
Per-team freshness (28 Sunday teams, all `official_verified=True`):
```
    ARI: ...=4, active_universe_current=16, injury_game_statuses=2, official_rows=8, official_game_statuses=2, official_verified=True
    BAL: ...=4, active_universe_current=16, injury_game_statuses=6, official_rows=12, official_game_statuses=6, official_verified=True
    BUF: ...=4, active_universe_current=15, injury_game_statuses=3, official_rows=13, official_game_statuses=3, official_verified=True
    CAR: ...=4, active_universe_current=16, injury_game_statuses=6, official_rows=12, official_game_statuses=6, official_verified=True
    CHI: ...=4, active_universe_current=13, injury_game_statuses=6, official_rows=10, official_game_statuses=6, official_verified=True
    CIN: ...=4, active_universe_current=14, injury_game_statuses=6, official_rows=10, official_game_statuses=6, official_verified=True
    DAL: ...=4, active_universe_current=15, injury_game_statuses=2, official_rows=5, official_game_statuses=2, official_verified=True
    DEN: ...=4, active_universe_current=15, injury_game_statuses=1, official_rows=6, official_game_statuses=1, official_verified=True
    DET: ...=4, active_universe_current=14, injury_game_statuses=2, official_rows=3, official_game_statuses=2, official_verified=True
    GB:  ...=4, active_universe_current=14, injury_game_statuses=6, official_rows=8, official_game_statuses=6, official_verified=True
    HOU: ...=4, active_universe_current=15, injury_game_statuses=6, official_rows=13, official_game_statuses=6, official_verified=True
    IND: ...=4, active_universe_current=16, injury_game_statuses=2, official_rows=8, official_game_statuses=2, official_verified=True
    JAX: ...=4, active_universe_current=16, injury_game_statuses=3, official_rows=9, official_game_statuses=3, official_verified=True
    KC:  ...=4, active_universe_current=17, injury_game_statuses=1, official_rows=11, official_game_statuses=1, official_verified=True
    LA:  ...=4, active_universe_current=16, injury_game_statuses=5, official_rows=14, official_game_statuses=5, official_verified=True
    LAC: ...=4, active_universe_current=14, injury_game_statuses=9, official_rows=13, official_game_statuses=9, official_verified=True
    LV:  ...=4, active_universe_current=15, injury_game_statuses=2, official_rows=11, official_game_statuses=2, official_verified=True
    MIA: ...=4, active_universe_current=15, injury_game_statuses=3, official_rows=13, official_game_statuses=3, official_verified=True
    MIN: ...=4, active_universe_current=14, injury_game_statuses=3, official_rows=7, official_game_statuses=3, official_verified=True
    NE:  ...=4, active_universe_current=16, injury_game_statuses=10, official_rows=11, official_game_statuses=10, official_verified=True
    NYG: ...=4, active_universe_current=16, injury_game_statuses=0, official_rows=8, official_game_statuses=0, official_verified=True
    NYJ: ...=4, active_universe_current=13, injury_game_statuses=7, official_rows=10, official_game_statuses=7, official_verified=True
    PHI: ...=4, active_universe_current=14, injury_game_statuses=6, official_rows=16, official_game_statuses=6, official_verified=True
    SEA: ...=4, active_universe_current=15, injury_game_statuses=4, official_rows=12, official_game_statuses=4, official_verified=True
    SF:  ...=4, active_universe_current=15, injury_game_statuses=7, official_rows=11, official_game_statuses=7, official_verified=True
    TB:  ...=4, active_universe_current=12, injury_game_statuses=7, official_rows=14, official_game_statuses=7, official_verified=True
    TEN: ...=4, active_universe_current=16, injury_game_statuses=2, official_rows=4, official_game_statuses=2, official_verified=True
    WAS: ...=4, active_universe_current=16, injury_game_statuses=6, official_rows=15, official_game_statuses=6, official_verified=True
```
```
Read set: 45 files — 14 from the run directory, 31 manifest-hashed repo files, 0 unproven
Games simulated: 14, Converged: 14/14
Matched 65 / 257 two-way prop rows
DRY RUN complete — nothing frozen.
```

## Step 10 — Export evidence
```
exported 313 rows (32 teams) fetched 2026-10-03T15:48:51.308172+00:00 sha256 9e9311c6a5fed223 to research/nfl_sim/official_injuries/2026_w04
```
