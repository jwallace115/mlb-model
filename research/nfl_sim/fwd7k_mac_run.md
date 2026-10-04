# FWD7k Mac run report — 2026-10-04

## Step 1
HEAD 5b5714c7b. Two modified tracked files (expected). 26 GB free. PASS.

## Step 2
Hash verified: D279b patch a9ceb5b7.
```
cf2982d9d FWD7k (D279b): HTML comments stripped from the official report sections before parsing and counting; script/template/style/noscript or an unclosed comment inside a section HALTs; the independent row count is case-insensitive; Z11-Z13 mutations killed
5b5714c7b FWD7j Mac run: ...
```

## Step 3 — Live page + structural cases
```
status 200 fetched 2026-10-04T00:16:33.799702+00:00 | rows 318 teams 32 game statuses 138
split rows 318 identical to clean: True
attr rows 318 identical to clean: True
comment rows 318 identical to clean: True
stray HALT: official injury page WAS: unsupported table body structure (15 row tags, 1
template HALT: official injury page section 1: unsupported element (script/template/style
```

## Step 4
```
exit 0
launcher hash ok: True {'n_repo_modules': 12, 'n_dependency_files': 1090, 'n_distribution_files_verified': 6395}
```

## Step 5 — Forward suite tests (per file)
```
nfl/sim/tests/test_fwd2_anchor.py: 3 passed in 0.33s
nfl/sim/tests/test_fwd2_bundle.py: 5 passed in 0.24s
nfl/sim/tests/test_fwd2_experiment.py: 6 passed in 1.01s
nfl/sim/tests/test_fwd2_item0_fixes.py: 7 passed in 1.08s
nfl/sim/tests/test_fwd2_settlement.py: 12 passed, 1 warning in 1.05s
nfl/sim/tests/test_fwd2b_harness.py: 10 passed in 43.62s
nfl/sim/tests/test_fwd3_item0.py: 9 passed in 34.84s
nfl/sim/tests/test_fwd3_item1.py: 3 passed in 0.29s
nfl/sim/tests/test_fwd3_item2.py: 8 passed in 1.22s
nfl/sim/tests/test_fwd4_item0.py: 9 passed in 25.31s
nfl/sim/tests/test_fwd4_item1.py: 4 passed in 6.40s
nfl/sim/tests/test_fwd5_pin.py: 4 passed in 6.46s
nfl/sim/tests/test_fwd6_item0.py: 13 passed in 34.93s
nfl/sim/tests/test_fwd6_item1.py: 12 passed in 64.54s
nfl/sim/tests/test_fwd6_item2.py: 9 passed in 31.27s
nfl/sim/tests/test_fwd6_item3.py: 5 passed in 10.66s
nfl/sim/tests/test_fwd6b.py: 39 passed in 124.35s
nfl/sim/tests/test_fwd6c.py: 33 passed in 75.79s
nfl/sim/tests/test_fwd6d.py: 33 passed in 73.62s
nfl/sim/tests/test_fwd6e.py: 6 passed in 14.86s
nfl/sim/tests/test_fwd6f.py: 11 passed in 1.90s
nfl/sim/tests/test_fwd7a.py: 27 passed in 3.35s
nfl/sim/tests/test_fwd7c.py: 11 passed in 1.38s
nfl/sim/tests/test_fwd7d.py: 7 passed in 0.57s
nfl/sim/tests/test_fwd7e.py: 7 passed in 0.39s
nfl/sim/tests/test_fwd7f.py: 12 passed in 0.43s
nfl/sim/tests/test_fwd7g.py: 45 passed in 2.22s
nfl/sim/tests/test_forward_v1.py: 8 passed in 0.29s
nfl/sim/tests/test_freeze_v1.py: 4 passed in 0.86s
```
Total: 362 passed, 0 failed, 0 skipped, 1 warning. 26 GB free after tests.

## Step 6 — PRIMARY-path Sunday dry run (no --pilot, window-hours 25)
```
(a) PASS, Experiment manifest OK, Calibration stamp OK, Usage fingerprint OK
```
Bundle: nfl/data/board/week=2026_04/sim_runs/20261004T002659Z. Events: 14, `pilot: false`.
Per-team freshness (28 Sunday teams, all `official_verified=True`):
```
    ARI: ...=4, auc=16, igs=2, official_rows=8, ogs=2, fetched 2026-10-03T23:10:55Z, verified=True
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

freshness.json per-team official fields:
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
