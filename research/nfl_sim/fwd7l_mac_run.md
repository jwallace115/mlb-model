# FWD7l Mac run report — 2026-10-04

## Step 1
HEAD b7d4a9916. Two modified tracked files (expected). 26 GB free. PASS.

## Step 2
Hashes verified: D280 patch 7009e933, a21replay.py a4256b0e.
```
97956aef1 FWD7l (D280): ...
b7d4a9916 FWD7k Mac run: ...
```

## Step 3 — Live page + audit #21 counterexample
```
status 200 fetched 2026-10-04T02:10:39.676245+00:00 | rows 318 teams 32 game statuses 138
Jayden Daniels [['WAS', 'Out']]
Rachaad White [['WAS', 'Out']]
split rows 318 identical to clean: True
attr rows 318 identical to clean: True
comment rows 318 identical to clean: True
six-cell (audit #21 A) HALT: official injury page WAS: unsupported row content (<th> outside a cell) in 'Jayden Daniels QBElbowLimite
text in a row HALT: official injury page WAS: unsupported row content (unclosed cell or trailing content) in 'Nick Allegrett
stray HALT: official injury page WAS: unsupported table body structure (15 row tags, 15 complete rows, stray content
template HALT: official injury page section 1: unsupported element (script/template/style/noscript or an unclosed comme
```

## Step 4 — Audit #21 chain on installed 23:10Z capture
```
installed capture 2026-10-03T23:10:55.062576+00:00 2711f526d7a38581 405289 bytes
Jayden Daniels [['WAS', 'Out']]
Rachaad White [['WAS', 'Out']]
  https://www.nfl.com/injuries/league/2026/reg4 fetched 2026-10-03T23:10:55.062576+00:00 sha256 2711f526d7a38581: 318 rows, 32 teams, 138 game statuses
  skill players Out/Doubtful officially but not in the feed: 0
clean: ADMITTED | equals installed injuries.parquet: True | rows 35864
six-cell (audit #21 A): HALT "HALT: official injury page WAS: unsupported row content (<th> outside a cell) in 'Jayden Daniels QBElbowLimited Participation in PracticeOut'" | wrote anything: False
```
git status: only refresh outputs modified.

## Step 5
```
exit 0
launcher hash ok: True {'n_repo_modules': 12, 'n_dependency_files': 1090, 'n_distribution_files_verified': 6395}
```

## Step 6 — Forward suite tests (per file)
```
nfl/sim/tests/test_fwd2_anchor.py: 3 passed in 0.32s
nfl/sim/tests/test_fwd2_bundle.py: 5 passed in 0.23s
nfl/sim/tests/test_fwd2_experiment.py: 6 passed in 0.99s
nfl/sim/tests/test_fwd2_item0_fixes.py: 7 passed in 1.06s
nfl/sim/tests/test_fwd2_settlement.py: 12 passed, 1 warning in 1.06s
nfl/sim/tests/test_fwd2b_harness.py: 10 passed in 43.50s
nfl/sim/tests/test_fwd3_item0.py: 9 passed in 35.54s
nfl/sim/tests/test_fwd3_item1.py: 3 passed in 0.32s
nfl/sim/tests/test_fwd3_item2.py: 8 passed in 1.28s
nfl/sim/tests/test_fwd4_item0.py: 9 passed in 25.88s
nfl/sim/tests/test_fwd4_item1.py: 4 passed in 5.98s
nfl/sim/tests/test_fwd5_pin.py: 4 passed in 6.33s
nfl/sim/tests/test_fwd6_item0.py: 13 passed in 34.61s
nfl/sim/tests/test_fwd6_item1.py: 12 passed in 63.39s
nfl/sim/tests/test_fwd6_item2.py: 9 passed in 30.13s
nfl/sim/tests/test_fwd6_item3.py: 5 passed in 10.41s
nfl/sim/tests/test_fwd6b.py: 39 passed in 123.43s
nfl/sim/tests/test_fwd6c.py: 33 passed in 76.00s
nfl/sim/tests/test_fwd6d.py: 33 passed in 76.59s
nfl/sim/tests/test_fwd6e.py: 6 passed in 15.54s
nfl/sim/tests/test_fwd6f.py: 11 passed in 2.13s
nfl/sim/tests/test_fwd7a.py: 27 passed in 3.53s
nfl/sim/tests/test_fwd7c.py: 11 passed in 1.44s
nfl/sim/tests/test_fwd7d.py: 7 passed in 0.60s
nfl/sim/tests/test_fwd7e.py: 7 passed in 0.41s
nfl/sim/tests/test_fwd7f.py: 12 passed in 0.43s
nfl/sim/tests/test_fwd7g.py: 49 passed in 2.34s
nfl/sim/tests/test_forward_v1.py: 8 passed in 0.30s
nfl/sim/tests/test_freeze_v1.py: 4 passed in 0.88s
```
Total: 366 passed, 0 failed, 0 skipped, 1 warning. 26 GB free after cleanup.

## Step 7 — PRIMARY-path Sunday dry run (no --pilot, window-hours 23)
```
(a) PASS, Experiment manifest OK, Calibration stamp OK, Usage fingerprint OK
```
Bundle: nfl/data/board/week=2026_04/sim_runs/20261004T022121Z. Events: 14, `pilot: false`.
All 28 Sunday teams `official_verified=True` (fetched 2026-10-03T23:10:55Z).
```
Games simulated: 14, Converged: 14/14
Read set: 45 files — 14 from the run directory, 31 manifest-hashed repo files, 0 unproven
Matched 65 / 257 two-way prop rows
DRY RUN complete — nothing frozen.
```

freshness.json per-team official fields (run dir 20261004T022121Z):
```
ARI 8 2 True 2026-10-03T23:10:55.062576+00:00
BAL 12 6 True 2026-10-03T23:10:55.062576+00:00
BUF 13 3 True 2026-10-03T23:10:55.062576+00:00
CAR 12 6 True 2026-10-03T23:10:55.062576+00:00
CHI 10 6 True 2026-10-03T23:10:55.062576+00:00
CIN 10 6 True 2026-10-03T23:10:55.062576+00:00
DAL 5 2 True 2026-10-03T23:10:55.062576+00:00
DEN 6 1 True 2026-10-03T23:10:55.062576+00:00
DET 3 2 True 2026-10-03T23:10:55.062576+00:00
GB 8 6 True 2026-10-03T23:10:55.062576+00:00
HOU 13 6 True 2026-10-03T23:10:55.062576+00:00
IND 8 2 True 2026-10-03T23:10:55.062576+00:00
JAX 9 3 True 2026-10-03T23:10:55.062576+00:00
KC 11 1 True 2026-10-03T23:10:55.062576+00:00
LA 14 5 True 2026-10-03T23:10:55.062576+00:00
LAC 13 9 True 2026-10-03T23:10:55.062576+00:00
LV 11 2 True 2026-10-03T23:10:55.062576+00:00
MIA 13 3 True 2026-10-03T23:10:55.062576+00:00
MIN 7 3 True 2026-10-03T23:10:55.062576+00:00
NE 11 10 True 2026-10-03T23:10:55.062576+00:00
NYG 8 0 True 2026-10-03T23:10:55.062576+00:00
NYJ 10 7 True 2026-10-03T23:10:55.062576+00:00
PHI 16 6 True 2026-10-03T23:10:55.062576+00:00
SEA 12 4 True 2026-10-03T23:10:55.062576+00:00
SF 11 7 True 2026-10-03T23:10:55.062576+00:00
TB 14 7 True 2026-10-03T23:10:55.062576+00:00
TEN 4 2 True 2026-10-03T23:10:55.062576+00:00
WAS 15 6 True 2026-10-03T23:10:55.062576+00:00
```

## Step 8 — Quote source check
- `data/odds_archive` is a regular directory (not a symlink).
- Worktree newest line snapshot: `snap_20260930T210010Z.parquet` (Sep 30 — stale in the worktree).
- Worktree props: `mac_close_20260927T1323Z.parquet`, `mac_mid_20260928T1850Z.parquet`, `data_2026_10.parquet` (62 KB).
- origin/main newest line snapshot: `snap_20261004T013006Z.parquet` (Oct 4 01:30Z — the VM's 30-min tape is current).
- origin/main props: `data_2026_10.parquet` (294 KB — includes the VM's regular pulls).
- `.env` absent from the worktree (no direct API access from here).

The Sunday production runs will read quotes from `~/mlb-model` (main checkout on the Mac), which has current data from the VM's auto-pulls. The worktree's stale quotes are only used with `--allow-stale-quotes` in dry runs.
