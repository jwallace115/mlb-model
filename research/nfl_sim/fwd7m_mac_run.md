# FWD7m Mac run report — 2026-10-04

## Step 1
HEAD a7e2d7683. Two modified tracked files (expected). 23 GB free. PASS.

## Step 2
Hashes verified: D281 patch 529cfcb3, a22replay.py ea44430d.
```
fbc1b34e4 FWD7m (D281): ...
a7e2d7683 FWD7l Mac run: ...
```

## Step 3 — Live page + audit #21/#22 counterexamples
```
status 200 fetched 2026-10-04T05:22:50.577052+00:00 | rows 318 teams 32 game statuses 138
Jayden Daniels [['WAS', 'Out']]
Rachaad White [['WAS', 'Out']]
Chig Okonkwo [['WAS', None]]
split rows 318 identical to clean: True
comment rows 318 identical to clean: True
encoded allowed class rows 318 identical to clean: True
six-cell (audit #21 A) HALT: official injury page WAS: unsupported row content (<th> outside a cell) in 'Jayden Daniels QBElbowLimite
encoded hidden Out (audit #22 A1) HALT: official injury page section 1: unsupported attribute 'style' on <span>
encoded visibility HALT: official injury page section 1: unsupported attribute 'style' on <span>
comment in style HALT: official injury page section 1: unsupported attribute 'style' on <span>
unknown class HALT: official injury page section 1: unknown class ['hidden'] on <a>
tbody class HALT: official injury page section 1: unsupported attribute 'class' on <tbody>
text in a row HALT: official injury page WAS: unsupported row content (unclosed cell or trailing content) in 'Nick Allegrett
stray HALT: official injury page WAS: unsupported table body structure (15 row tags, 15 complete rows, stray content
```

## Step 4 — Audit #21/#22 chains on installed 23:10Z capture
```
installed capture 2026-10-03T23:10:55.062576+00:00 2711f526d7a38581 405289 bytes
Jayden Daniels [['WAS', 'Out']]
Rachaad White [['WAS', 'Out']]
  https://www.nfl.com/injuries/league/2026/reg4 fetched 2026-10-03T23:10:55.062576+00:00 sha256 2711f526d7a38581: 318 rows, 32 teams, 138 game statuses
  skill players Out/Doubtful officially but not in the feed: 0
clean: ADMITTED | equals installed injuries.parquet: True | rows 35864
six-cell (audit #21 A): HALT "HALT: official injury page WAS: unsupported row content (<th> outside a cell) in 'Jayden Daniels QBElbowLimited Participation in PracticeOut'" | wrote anything: False
Chig Okonkwo [['WAS', None]]
encoded hidden Out (audit #22 A1): HALT "HALT: official injury page section 1: unsupported attribute 'style' on <span>" | wrote anything: False
```
git status: only refresh outputs modified.

## Step 5
```
exit 0
launcher hash ok: True {'n_repo_modules': 12, 'n_dependency_files': 1090, 'n_distribution_files_verified': 6395}
```

## Step 6 — Forward suite tests (per file)
```
nfl/sim/tests/test_fwd2_anchor.py: 3 passed in 1.32s
nfl/sim/tests/test_fwd2_bundle.py: 5 passed in 0.60s
nfl/sim/tests/test_fwd2_experiment.py: 6 passed in 3.03s
nfl/sim/tests/test_fwd2_item0_fixes.py: 7 passed in 3.51s
nfl/sim/tests/test_fwd2_settlement.py: 12 passed, 1 warning in 3.78s
nfl/sim/tests/test_fwd2b_harness.py: 10 passed in 161.52s
nfl/sim/tests/test_fwd3_item0.py: 9 passed in 165.11s
nfl/sim/tests/test_fwd3_item1.py: 3 passed in 1.30s
nfl/sim/tests/test_fwd3_item2.py: 8 passed in 8.93s
nfl/sim/tests/test_fwd4_item0.py: 9 passed in 122.01s
nfl/sim/tests/test_fwd4_item1.py: 4 passed in 25.44s
nfl/sim/tests/test_fwd5_pin.py: 4 passed in 22.96s
nfl/sim/tests/test_fwd6_item0.py: 13 passed in 216.86s
nfl/sim/tests/test_fwd6_item1.py: 12 passed in 316.20s
nfl/sim/tests/test_fwd6_item2.py: 9 passed in 112.73s
nfl/sim/tests/test_fwd6_item3.py: 5 passed in 49.06s
nfl/sim/tests/test_fwd6b.py: 39 passed in 410.93s
nfl/sim/tests/test_fwd6c.py: 33 passed in 273.03s
nfl/sim/tests/test_fwd6d.py: 33 passed in 605.33s
nfl/sim/tests/test_fwd6e.py: 6 passed in 123.08s
nfl/sim/tests/test_fwd6f.py: 11 passed in 9.93s
nfl/sim/tests/test_fwd7a.py: 27 passed in 16.89s
nfl/sim/tests/test_fwd7c.py: 11 passed in 6.71s
nfl/sim/tests/test_fwd7d.py: 7 passed in 2.65s
nfl/sim/tests/test_fwd7e.py: 7 passed in 6.40s
nfl/sim/tests/test_fwd7f.py: 12 passed in 2.66s
nfl/sim/tests/test_fwd7g.py: 52 passed in 26.15s
nfl/sim/tests/test_forward_v1.py: 8 passed in 1.78s
nfl/sim/tests/test_freeze_v1.py: 4 passed in 3.62s
```
Total: 369 passed, 0 failed, 0 skipped, 1 warning. (Slow: Mac under Sunday pipeline load.)
22 GB free after cleanup.

## Step 7 — PRIMARY-path Sunday dry run (no --pilot, window-hours 19)
```
(a) PASS, Experiment manifest OK, Calibration stamp OK, Usage fingerprint OK
```
Bundle: nfl/data/board/week=2026_04/sim_runs/20261004T061542Z. Events: 14, `pilot: false`.
All 28 Sunday teams `official_verified=True` (fetched 2026-10-03T23:10:55Z).
Per-team freshness (verbatim):
```
ARI: ...=4, auc=16, igs=2, official_rows=8, ogs=2, verified=True
BAL: ...=4, auc=16, igs=6, official_rows=12, ogs=6, verified=True
BUF: ...=4, auc=15, igs=3, official_rows=13, ogs=3, verified=True
CAR: ...=4, auc=16, igs=6, official_rows=12, ogs=6, verified=True
CHI: ...=4, auc=13, igs=6, official_rows=10, ogs=6, verified=True
CIN: ...=4, auc=14, igs=6, official_rows=10, ogs=6, verified=True
DAL: ...=4, auc=15, igs=2, official_rows=5, ogs=2, verified=True
DEN: ...=4, auc=15, igs=1, official_rows=6, ogs=1, verified=True
DET: ...=4, auc=14, igs=2, official_rows=3, ogs=2, verified=True
GB:  ...=4, auc=14, igs=6, official_rows=8, ogs=6, verified=True
HOU: ...=4, auc=15, igs=6, official_rows=13, ogs=6, verified=True
IND: ...=4, auc=16, igs=2, official_rows=8, ogs=2, verified=True
JAX: ...=4, auc=16, igs=3, official_rows=9, ogs=3, verified=True
KC:  ...=4, auc=17, igs=1, official_rows=11, ogs=1, verified=True
LA:  ...=4, auc=16, igs=5, official_rows=14, ogs=5, verified=True
LAC: ...=4, auc=14, igs=9, official_rows=13, ogs=9, verified=True
LV:  ...=4, auc=15, igs=2, official_rows=11, ogs=2, verified=True
MIA: ...=4, auc=15, igs=3, official_rows=13, ogs=3, verified=True
MIN: ...=4, auc=14, igs=3, official_rows=7, ogs=3, verified=True
NE:  ...=4, auc=16, igs=10, official_rows=11, ogs=10, verified=True
NYG: ...=4, auc=16, igs=0, official_rows=8, ogs=0, verified=True
NYJ: ...=4, auc=13, igs=7, official_rows=10, ogs=7, verified=True
PHI: ...=4, auc=14, igs=6, official_rows=16, ogs=6, verified=True
SEA: ...=4, auc=15, igs=4, official_rows=12, ogs=4, verified=True
SF:  ...=4, auc=15, igs=7, official_rows=11, ogs=7, verified=True
TB:  ...=4, auc=12, igs=7, official_rows=14, ogs=7, verified=True
TEN: ...=4, auc=16, igs=2, official_rows=4, ogs=2, verified=True
WAS: ...=4, auc=16, igs=6, official_rows=15, ogs=6, verified=True
```
```
Games simulated: 14, Converged: 14/14
Read set: 45 files — 14 from the run directory, 31 manifest-hashed repo files, 0 unproven
Matched 65 / 257 two-way prop rows
DRY RUN complete — nothing frozen.
```
Total runtime: 2346s (39.1 min) — Mac under heavy Sunday pipeline load.

freshness.json per-team official fields (run dir 20261004T061542Z):
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
