# FWD3 acceptance — 2026-09-30

## Tests

75 tests passed, 0 failed (test_freeze_v1 + all FWD test files):

```
75 passed, 65 warnings in 7.81s
```

New tests by item:
- test_fwd3_item0.py: 9 tests (D241 — run record)
- test_fwd3_item1.py: 3 tests (D242 — anchor returned)
- test_fwd3_item2.py: 8 tests (D243 — scoring integrity)

## Real runs

### (i) Week-4 dry run

```
python3 nfl/sim/run_forward_v1.py --week 4 --dry-run --window-hours 40 --allow-stale-quotes
```

Completed. 1 game (PIT@CLE), 11 sim_v1 matches, 59 no_view.
Bundle at `nfl/data/board/week=2026_04/sim_runs/20260930T142206Z/`.
Anchor: PIT@CLE converged in 3 iterations, miss_m=0.092, miss_t=0.137, anchored=True.
Manifest hashes 23 files including inputs/ and outputs/.

### (ii) Week-3 pilot freeze

```
python3 nfl/sim/run_forward_v1.py --week 3 --pilot --as-of 2026-09-27T17:00:00+00:00 --window-hours 9 --allow-stale-quotes
```

Completed. 14 games, all converged and anchored. 162/625 two-way matches, 357 total lines.
Frozen to `nfl/data/board/week=2026_03/ai_opinions/ai_opinions_20260927T170000Z.parquet`.
sha256: d683f73ef933cc934051e9247fbc9f998a68eced0165cc7a41fd0252694edf1c
publication_utc: 2026-09-30T14:32:15.570179+00:00

Same command again -> refused:
```
HALT: run directory already exists: .../sim_runs/20260927T170000Z
A run_id can only be used once.
```

Files > 2MB (NOT committed):
- inputs/depth_charts.parquet (7.4M)
- inputs/player_usage_weekly.parquet (2.9M)
- inputs/rosters_weekly.parquet (3.9M)

All other files < 2MB. The frozen opinion file (47K) and non-input bundle files are committed.

### (iii) score-experiment

```
python3 nfl/pipeline/log_ai_opinions.py score-experiment --experiment nfl_fwd_v1
```

Output:
```
  week 2: 0 eligible rows (all pilot or non-canonical), skipping
  week 3: 0 eligible rows (all pilot or non-canonical), skipping
  week 4: no frozen files, skipping

0 eligible legs -- descriptive only, no verdict.
```

Skips the week-2 pilot-only directory. Reports 0 eligible legs with no verdict.

Diagnostic `--file` on the week-3 pilot:
```
python3 nfl/pipeline/log_ai_opinions.py score-experiment --experiment nfl_fwd_v1 --file nfl/data/board/week=2026_03/ai_opinions/ai_opinions_20260927T170000Z.parquet
```

Output:
```
[DIAGNOSTIC -- NOT THE RECORD: ai_opinions_20260927T170000Z.parquet]
  Total rows: 357, graded: 347
  sim_v1 settled: 57 legs, 5 games
  Delta = 0.011770
  95% CI: [-0.018911, 0.050775]
  Verdict: inconclusive
  P2 (|p-q|>0.08): 35 legs, units = -1.22
```

Cohort excludes all 357 rows (all pilot), 0 eligible -> descriptive only, no verdict.

## NOT DONE

- The week-3 pilot's `inputs/` directory (3 files > 2MB) is NOT committed. The bundle
  manifest hashes them. They can be verified from the shared ratings files at the same
  commit.

## UNVERIFIED

- The week-4 dry run used `--allow-stale-quotes`. A live TNF run must use fresh quotes.
- The diagnostic Delta (+0.012) is from 57 legs / 5 games. It is a pilot log entry, not
  evidence.
