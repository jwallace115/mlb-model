# FWD7g/7h Mac run report — 2026-10-03

## FWD7g attempt (055b8afde)

Steps 1-5 passed:
- 337 forward tests passed, 0 failed, 0 skipped.
- 22 usage tests passed, 1 deselected.
- D277 declaration grep = 1.

Step 6 FAILED:
```
ssl.SSLCertVerificationError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1018)
```
`official_injuries.py:71` called `urllib.request.urlopen` without an SSL context. macOS framework Python 3.13 does not configure the system cert store for Python's ssl module. The refresh RESTORED tables from backup and exited.

---

## FWD7h (SSL fix, 2d0eb9a32)

### Step 1
HEAD 055b8afde. Two modified tracked files (expected). PASS.

### Step 2
Hashes verified: D277 patch ff9bb2f3, SSL patch dd7763a2, aucmp.py 3f593ab3.
```
2d0eb9a32 FWD7h (D277 addendum): official report fetch uses an explicit verifying SSL context (certifi CA bundle when installed)
055b8afde FWD7g (D277): ...
```

### Step 3 — Official page fetch with cert verification
```
verify_mode 2 check_hostname True
200 404361 485ef7206f2f4712 2026-10-03T05:48:48.356210+00:00 | rows 313 teams 32 game statuses 130
```

### Step 4
```
exit 0
launcher hash ok: True {'n_repo_modules': 12, 'n_dependency_files': 1090, 'n_distribution_files_verified': 6395}
```

### Step 5 — Forward suite tests (per file)
```
nfl/sim/tests/test_fwd2_anchor.py: 3 passed in 0.27s
nfl/sim/tests/test_fwd2_bundle.py: 5 passed in 0.23s
nfl/sim/tests/test_fwd2_experiment.py: 6 passed in 1.01s
nfl/sim/tests/test_fwd2_item0_fixes.py: 7 passed in 1.07s
nfl/sim/tests/test_fwd2_settlement.py: 12 passed, 1 warning in 1.09s
nfl/sim/tests/test_fwd2b_harness.py: 10 passed in 43.38s
nfl/sim/tests/test_fwd3_item0.py: 9 passed in 34.64s
nfl/sim/tests/test_fwd3_item1.py: 3 passed in 0.29s
nfl/sim/tests/test_fwd3_item2.py: 8 passed in 1.23s
nfl/sim/tests/test_fwd4_item0.py: 9 passed in 25.31s
nfl/sim/tests/test_fwd4_item1.py: 4 passed in 6.16s
nfl/sim/tests/test_fwd5_pin.py: 4 passed in 6.38s
nfl/sim/tests/test_fwd6_item0.py: 13 passed in 34.73s
nfl/sim/tests/test_fwd6_item1.py: 12 passed in 63.65s
nfl/sim/tests/test_fwd6_item2.py: 9 passed in 30.34s
nfl/sim/tests/test_fwd6_item3.py: 5 passed in 10.85s
nfl/sim/tests/test_fwd6b.py: 39 passed in 123.59s
nfl/sim/tests/test_fwd6c.py: 33 passed in 76.19s
nfl/sim/tests/test_fwd6d.py: 33 passed in 72.12s
nfl/sim/tests/test_fwd6e.py: 6 passed in 16.06s
nfl/sim/tests/test_fwd6f.py: 11 passed in 1.89s
nfl/sim/tests/test_fwd7a.py: 27 passed in 3.30s
nfl/sim/tests/test_fwd7c.py: 11 passed in 1.38s
nfl/sim/tests/test_fwd7d.py: 7 passed in 0.58s
nfl/sim/tests/test_fwd7e.py: 7 passed in 0.43s
nfl/sim/tests/test_fwd7f.py: 10 passed in 0.35s
nfl/sim/tests/test_fwd7g.py: 23 passed in 1.74s
nfl/sim/tests/test_forward_v1.py: 8 passed in 0.29s
nfl/sim/tests/test_freeze_v1.py: 4 passed in 0.85s
```
Total: 338 passed, 0 failed, 0 skipped, 1 warning.

### Step 6 — refresh_inputs.py --week 4 (D277 with SSL fix)
Ran at Sat Oct  3 05:59:14 UTC 2026.

Official injury report section:
```
── official injury report, week 4 (D277) ──
  https://www.nfl.com/injuries/league/2026/reg4 fetched 2026-10-03T05:59:23.265859+00:00 sha256 cb68dcb44a797eba: 313 rows, 32 teams, 130 game statuses
  skill players Out/Doubtful officially but not in the feed: 20
    WAS Jayden Daniels (QB): feed - -> official Out
    WAS Rachaad White (RB): feed - -> official Out
    TB Ko Kieft (TE): feed - -> official Out
    TB Baker Mayfield (QB): feed - -> official Out
    NYJ Breece Hall (RB): feed - -> official Out
    NYJ Adonai Mitchell (WR): feed - -> official Out
    NYJ Mason Taylor (TE): feed - -> official Out
    CHI Caleb Williams (QB): feed - -> official Out
    CIN Colbie Young (WR): feed - -> official Out
    LA Terrance Ferguson (TE): feed - -> official Out
    PHI Marquise Brown (WR): feed - -> official Out
    PHI Dallas Goedert (TE): feed - -> official Out
    PHI DeVonta Smith (WR): feed - -> official Out
    MIA Caleb Douglas (WR): feed - -> official Out
    MIN Justin Jefferson (WR): feed - -> official Out
    LAC Charlie Kolar (TE): feed - -> official Out
    LAC Brenen Thompson (WR): feed - -> official Out
    SEA Zach Charbonnet (RB): feed (not listed) -> official Out
    SEA Jadarian Price (RB): feed - -> official Out
    CAR Xavier Legette (WR): feed - -> official Out
```

```
Fit-window fingerprint unchanged: 3638769c89030de0
Archived this refresh's sources and tables (D277-v7) in /Users/jw115/mlb-model-archive/nfl_ratings_backups/20261003T055915Z/refreshed
```

Freshness: **PASS** all 32 teams. Exit 0. ATL and NO `official_verified=False` (Monday game deadline Sat 20:00Z, fetched at 05:59Z). All Sunday teams `official_verified=True`.

Manifest: `input_version: D277-v7`. Includes `official_injuries.html` (sha256 cb68dcb4) and `official_injuries.json`.

### Step 7a — Active-universe changes (AUCMP)
```
active_flag changes: 38 (weeks [4, 5])
  wk4 CAR Xavier Legette (WR, depth 3.0): True -> False; official week-4 status Out
  wk4 CHI Caleb Williams (QB, depth 1.0): True -> False; official week-4 status Out
  wk4 CIN Colbie Young (WR, depth 3.0): True -> False; official week-4 status Out
  wk4 LA Terrance Ferguson (TE, depth 2.0): True -> False; official week-4 status Out
  wk4 LAC Charlie Kolar (TE, depth 1.0): True -> False; official week-4 status Out
  wk4 LAC Brenen Thompson (WR, depth 4.0): True -> False; official week-4 status Out
  wk4 MIA Caleb Douglas (WR, depth 2.0): True -> False; official week-4 status Out
  wk4 MIN Justin Jefferson (WR, depth 1.0): True -> False; official week-4 status Out
  wk4 NYJ Breece Hall (RB, depth 1.0): True -> False; official week-4 status Out
  wk4 NYJ Adonai Mitchell (WR, depth 2.0): True -> False; official week-4 status Out
  wk4 NYJ Mason Taylor (TE, depth 2.0): True -> False; official week-4 status Out
  wk4 PHI Dallas Goedert (TE, depth 1.0): True -> False; official week-4 status Out
  wk4 PHI Marquise Brown (WR, depth 4.0): True -> False; official week-4 status Out
  wk4 PHI DeVonta Smith (WR, depth 1.0): True -> False; official week-4 status Out
  wk4 SEA Jadarian Price (RB, depth 1.0): True -> False; official week-4 status Out
  wk4 TB Baker Mayfield (QB, depth 1.0): True -> False; official week-4 status Out
  wk4 TB Ko Kieft (TE, depth 3.0): True -> False; official week-4 status Out
  wk4 WAS Rachaad White (RB, depth 2.0): True -> False; official week-4 status Out
  wk4 WAS Jayden Daniels (QB, depth 1.0): True -> False; official week-4 status Out
  (same 19 players mirrored in wk5)
AUCMP OK
```

### Step 7b — Starting QBs for Out-starter teams
```
      team     player_name   player_id
47014  CHI     Case Keenum  00-0028986
47375   TB   Jalon Daniels  00-0041251
47392  WAS  Marcus Mariota  00-0032268
```

### Step 7c — Rebuild identity, point-in-time, gate
```
base exit 0
  installed player_usage_weekly.parquet 2026 rows == base rebuild: True
  installed active_universe_weekly.parquet 2026 rows == base rebuild: True
installed week-4 active universe: rows 802, depth_order non-null 724, duplicate (team, player_id) 0, active_flag dtype bool, null flags 0

POINT-IN-TIME OK player_usage_weekly.parquet: week-2 rows (513) identical
POINT-IN-TIME OK active_universe_weekly.parquet: week-2 rows (786) identical
POINT-IN-TIME OK player_usage_weekly.parquet: week-3 rows (518) identical
POINT-IN-TIME OK active_universe_weekly.parquet: week-3 rows (794) identical
POINT-IN-TIME OK player_usage_weekly.parquet: week-4 rows (506) identical
POINT-IN-TIME OK active_universe_weekly.parquet: week-4 rows (802) identical

GATE PASS: 28 Sunday teams, tables from /tmp/g_base/tables
```

### Step 8
```
RUNBOOK MATCHES
```

### Step 9 — PRIMARY-path Sunday smoke run (no --pilot, D277 gate enforced)
```
(a) PASS, Experiment manifest OK, Calibration stamp OK, Usage fingerprint OK
```
Bundle: nfl/data/board/week=2026_04/sim_runs/20261003T060858Z
Events: 14, Props: 426, Lines: 84. `pilot: false`.
All 28 Sunday teams `official_verified=True`. 14 games simulated, 14/14 converged.
```
Read set: 45 files — 14 from the run directory, 31 manifest-hashed repo files, 0 unproven
Matched 65 / 257 two-way prop rows
DRY RUN complete — nothing frozen.
```

### Step 10 — Export capture evidence
```
exported 313 rows (32 teams) fetched 2026-10-03T05:59:23.265859+00:00 sha256 cb68dcb44a797eba to research/nfl_sim/official_injuries/2026_w04
```
Files: official_injuries_rows.csv (26 KB), official_injuries.json (259 B), refresh_manifest.json (1.7 KB).
