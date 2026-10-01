# FWD6 acceptance — real runs on the owner's Mac (2026-10-01, 00:21Z)

Branch `eng/fwd6` @ `e826a30ae` (pushed 00:07Z; tree identical to the branch Cowork tested on Linux, 131 passed /
0 failed). Jeff ran the commands; Cowork read the outputs and the run directories (read_set.json, freshness.json,
receipts) through the bridge.

## RETURNED

### (i) Week-4 live dry run — `run_forward_v1.py --week 4 --dry-run --window-hours 40 --allow-stale-quotes`

- Run `20261001T001023Z`, PIT@CLE.
- Sheet and coverage: 70 lines; 11 `sim_v1` matches (9 receptions, 2 rush attempts); 59 `no_view`.
- Anchor:

  | | Target | Anchored | Miss |
  |---|---|---|---|
  | Spread | −3.0 | −2.8602 | 0.14 |
  | Total | 38.0 | 38.065 | 0.07 |

  The solver took 3 iterations and returned converged; the game is anchored. The spread target was −2.5 at Wednesday's
  dry run; the line has moved since.
- **Read set:** 39 files, 0 conflicts, 0 network attempts.
  - 11 from the run directory: 10 `inputs/` files and the bundle's `props.parquet`.
  - 25 engine tables, all experiment-hashed.
  - `calibration_v1.json` and `params_v1.json`.
  - No shared ratings, rosters, PBP, props archive or line tape.
- **Per-team freshness, on the consumed copies:**

  | Team | Last played | team_ratings | tendencies | situational | usage | active universe | kickers | qb_ratings |
  |---|---|---|---|---|---|---|---|---|
  | CLE | 3 | 4 | 4 | 4 | 3 | 3 | 3 | 3 |
  | PIT | 3 | 4 | 4 | 4 | 3 | 3 | 3 | 3 |

- The bundle manifest lists 24 files, including `outputs/read_set.json`. Nothing was frozen.

### (ii) Week-3 pilot freeze — `--week 3 --pilot --as-of 2026-09-27T16:45:00+00:00 --window-hours 9 --allow-stale-quotes`

- Run `20260927T164500Z`: 14 games, 0 unanchored. Each anchor missed by at most 0.37, and every solver returned
  converged in 2–5 iterations.
- Sheet: 989 lines / 625 two-way / 162 `sim_v1` matched (130 receptions, 32 rush attempts). This equals FWD2b's
  162-match pilot.
- Read set: same composition as (i) (11 run-directory files, 25 tables, 2 configs, nothing else).
- Frozen: `nfl/data/board/week=2026_03/ai_opinions/ai_opinions_20260927T164500Z.parquet`
  - sha256 `59b840f2d7d292437456e5efca4a08957af661e116d65819c94cec2f66761d87`
  - publication_utc 2026-10-01T00:18:09Z
- One receipt line in `research/nfl_sim/fwd_v1_receipts.jsonl`, with `pilot: true` and `rows: 989`. Its bundle digest,
  experiment digest, frozen sha256 and publication.json sha256 are recorded.
- **The same command again:** `HALT: run directory already exists: .../sim_runs/20260927T164500Z`.

### (iii) Restore

- Moved `inputs/` of the pilot run aside, then ran `nfl/sim/restore_run.py --run-dir …/20260927T164500Z`.
- Result: archive `/Users/jw115/mlb-model-archive/nfl_fwd_v1`; restored 12 files; `verify_bundle: clean`.

## MEANS

- The live prediction path on the real data reads only its bundle plus hashed repo files. This is the property audit #8
  (A1) showed was false at e0fc3d2d6.
- Per-team freshness passes for the TNF teams on the copies.
- Run-directory exclusivity holds.
- A run directory whose inputs are lost can be rebuilt from the archive and verified.
- The week-3 pilot is plumbing evidence only. It is NOT out-of-sample: it used today's inputs, which include week-3
  usage, for a week-3 as-of. Its rows are `pilot` and are never pooled.

## NOT DONE

- ChatGPT audit #9 of e826a30ae (sent by Jeff).
- The merge to main (gate: Thu 15:00Z).
- FWD7: implementing scoring amendment S1–S4.
- FWD2d: the Sunday runbook.

## UNVERIFIED

- Anything audit #9 finds.
- Behaviour at the real TNF time: the 22:00Z VM props pull must exist and be at most 3 h old at 23:30Z, and the line
  snapshots must be at most 3 h old.
- The old FWD3 pilot run directory `week=2026_03/sim_runs/20260927T170000Z` is committed without `inputs/` and predates
  the archive, so it cannot be restored. The pinned scorer verifies every bundle and will HALT on it. FWD7's S1 (score
  only receipt-registered runs) removes that dependency.
