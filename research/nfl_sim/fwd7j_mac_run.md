# FWD7j Mac run report — 2026-10-03

## First attempt (d3c8fbbed) — steps 1-4 passed, step 5a disk-full stop

Steps 1-4 all passed (D279 applied, selftest OK, PBP history unchanged). Step 3 (audit #20 on real page):
```
url https://www.nfl.com/injuries/league/2026/reg4 | final_url https://www.nfl.com/injuries/league/2026/reg4 | status 200 | bytes 404361 | fetched 2026-10-03T22:46:32.998690+00:00
rows 313 identified 313 teams 32 matchups 16 game statuses 130
split rows 313 WAS 15 identical to clean: True
attr rows 313 WAS 15 identical to clean: True
stray: HALT: official injury page WAS: unsupported table body structure (15 row tags, 15 complete
```

Step 5a: 164 tests passed through test_fwd6_item3.py, then test_fwd6b.py 3 failed/36 passed (disk exhaustion), remaining files `FileNotFoundError: No usable temporary directory found`. `zsh:1: no space left on device`.

## Disk cleanup (steps A-D)

df before: 127 MB free. /private/tmp: 37 GB, $TMPDIR: 1.4 GB.

Deleted (categories):
1. Audit worktree copies: eng-fwd2 (7.0 GB), 13 nfl-audit* dirs (~5.7 GB), 15 audit*-base/clean/pytest/bytecode dirs (~15 GB)
2. Build scratch: 31 /tmp directories (f_*, g_*, h_*, k_*, fpit*, gpit*, hpit*)
3. Pytest temp roots ($TMPDIR/pytest-of-jw115, 689 MB), $TMPDIR audit dirs (~500 MB)

df after: **28 GB free**. git status unchanged (same two refresh outputs).

## Resume — steps 5-10

### Step 5a — Forward suite tests (per file)
```
nfl/sim/tests/test_fwd2_anchor.py: 3 passed in 1.42s
nfl/sim/tests/test_fwd2_bundle.py: 5 passed in 0.24s
nfl/sim/tests/test_fwd2_experiment.py: 6 passed in 1.84s
nfl/sim/tests/test_fwd2_item0_fixes.py: 7 passed in 1.08s
nfl/sim/tests/test_fwd2_settlement.py: 12 passed, 1 warning in 2.22s
nfl/sim/tests/test_fwd2b_harness.py: 10 passed in 44.17s
nfl/sim/tests/test_fwd3_item0.py: 9 passed in 34.67s
nfl/sim/tests/test_fwd3_item1.py: 3 passed in 0.29s
nfl/sim/tests/test_fwd3_item2.py: 8 passed in 1.24s
nfl/sim/tests/test_fwd4_item0.py: 9 passed in 25.13s
nfl/sim/tests/test_fwd4_item1.py: 4 passed in 6.11s
nfl/sim/tests/test_fwd5_pin.py: 4 passed in 6.32s
nfl/sim/tests/test_fwd6_item0.py: 13 passed in 34.86s
nfl/sim/tests/test_fwd6_item1.py: 12 passed in 63.23s
nfl/sim/tests/test_fwd6_item2.py: 9 passed in 30.18s
nfl/sim/tests/test_fwd6_item3.py: 5 passed in 10.51s
nfl/sim/tests/test_fwd6b.py: 39 passed in 123.58s
nfl/sim/tests/test_fwd6c.py: 33 passed in 76.30s
nfl/sim/tests/test_fwd6d.py: 33 passed in 73.60s
nfl/sim/tests/test_fwd6e.py: 6 passed in 14.78s
nfl/sim/tests/test_fwd6f.py: 11 passed in 1.87s
nfl/sim/tests/test_fwd7a.py: 27 passed in 3.34s
nfl/sim/tests/test_fwd7c.py: 11 passed in 1.38s
nfl/sim/tests/test_fwd7d.py: 7 passed in 0.58s
nfl/sim/tests/test_fwd7e.py: 7 passed in 0.39s
nfl/sim/tests/test_fwd7f.py: 12 passed in 0.42s
nfl/sim/tests/test_fwd7g.py: 43 passed in 2.25s
nfl/sim/tests/test_forward_v1.py: 8 passed in 0.30s
nfl/sim/tests/test_freeze_v1.py: 4 passed in 0.85s
```
Total: 360 passed, 0 failed, 0 skipped, 1 warning.

### Step 5b
```
22 passed, 1 deselected in 33.71s
```
D279 grep = 1. PASS.

### Step 6 — refresh_inputs.py --week 4 (D279)
Ran at Sat Oct  3 23:10:46 UTC 2026.
```
── official injury report, week 4 (D277) ──
  https://www.nfl.com/injuries/league/2026/reg4 fetched 2026-10-03T23:10:55.062576+00:00 sha256 2711f526d7a38581: 318 rows, 32 teams, 138 game statuses
  skill players Out/Doubtful officially but not in the feed: 0
```

```
Fit-window fingerprint unchanged: 3638769c89030de0
Archived this refresh's sources and tables (D279-v9) in /Users/jw115/mlb-model-archive/nfl_ratings_backups/20261003T231047Z/refreshed
```

Freshness: **PASS** all 32 teams. **ATL and NO now `official_verified=True`** (fetched at 23:10Z, after Sat 20:00Z MNF deadline). Exit 0. Manifest: `D279-v9`, includes `injuries_feed.parquet`.

### Step 7a — AUCMP
```
active_flag changes: 0 (weeks [])
AUCMP OK
```
Pre-overlay feed archived: injuries_feed.parquet 598 KB.

### Step 7b — Rebuild identity, point-in-time, gate
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

GATE PASS: 28 Sunday teams, tables from /tmp/j_base/tables
```

### Step 7c — Audit #19 regression
```
== blank_posteam
HALT (RuntimeError): pbp_2026.parquet: inadmissible plays — 1 rows: empty or whitespace-only posteam; 1 rows: pass/run play without posteam

== bad_team
HALT (RuntimeError): pbp_2026.parquet: inadmissible plays — 1 rows: team key outside the 32 nflverse codes
```

### Step 8
```
RUNBOOK MATCHES
```

### Step 9 — PRIMARY-path Sunday smoke (no --pilot, window-hours 26)
```
(a) PASS, Experiment manifest OK, Calibration stamp OK, Usage fingerprint OK
```
Bundle: nfl/data/board/week=2026_04/sim_runs/20261003T232031Z. Events: 14, `pilot: false`.
All 28 Sunday teams `official_verified=True`. 14/14 converged.
```
Read set: 45 files — 14 from the run directory, 31 manifest-hashed repo files, 0 unproven
Matched 65 / 257 two-way prop rows
DRY RUN complete — nothing frozen.
```

### Step 10
```
exported 318 rows (32 teams) fetched 2026-10-03T23:10:55.062576+00:00 sha256 2711f526d7a38581 to research/nfl_sim/official_injuries/2026_w04
```
