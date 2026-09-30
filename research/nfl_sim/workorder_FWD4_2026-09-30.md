# Work order FWD4 — the anchor join, the record written once, and the four surviving mutations (2026-09-30)

Written by Cowork with D245. It continues on eng/fwd3 (not merged). No FREEZE_v1 file changes. **Gate:** verified by
Thu 10-01 15:00Z, or TNF runs `--pilot`.

Pre-check (Cowork):
- **Runtime:** code and tests plus one real week-4 dry run (about 1 min). About an hour of agent time.
- **Credits:** zero.
- **Files:** `nfl/pipeline/log_ai_opinions.py` (`primary_cohort`, `score_experiment`), `nfl/sim/run_forward_v1.py`
  (the post-freeze block around :746-800; `_default_run_week`), and the tests in `nfl/sim/tests/`.

```
Work order FWD4 (research/nfl_sim/workorder_FWD4_2026-09-30.md). Continue on eng/fwd3 in its worktree (git pull;
head 735374bf1). Gate: `git show origin/main:research/nfl_sim/fwd3_verification_2026-09-30.md | grep -c "^### D245"`
prints 1. FIRST COMMIT: append D245 verbatim. Items 0-1 = D246-D247, one commit each, pushed. Keep context lean.

HARD RULES: FREEZE_v1 byte-identical; test_freeze_v1 before every commit. Every new test fails on 735374bf1 — paste
it. For each mutation named below, apply it, run the suite, and paste the failing test name; then revert it.
FWD_EXPERIMENT_v1.json re-stamped once, last.

Item 0 (D246) — the anchor join and the record written once.
  (a) The sidecar rows carry event_id (from the bundle's events) and run_id.
      primary_cohort(df, reader, sidecar):
      - joins each candidate row on (run_id, event_id);
      - exactly one sidecar row per pair: missing or duplicate -> HALT (SystemExit), never silently kept;
      - `anchored` comes only from that row.
      score_experiment:
      - loads the sidecar of each row's own run;
      - runs verify() on every week directory it reads (not only --file), and HALTs on a mismatch.
      Tests: run A anchored / run B unanchored, a run-B row -> excluded; no sidecar -> HALT; a duplicate sidecar row
      -> HALT; an altered frozen file in a week directory -> HALT (non --file path).
  (b) Written once:
      - The frozen parquet is written ONCE by freeze(). Do not rewrite it after.
      - Record publication in a new file, <run-dir>/publication.json {publication_utc, frozen_file, frozen_sha256},
        written after the freeze, and in the ai_opinions manifest entry.
      - bundle_manifest.json is finalized BEFORE the freeze and never rewritten.
      - Every frozen row gets bundle_digest = sha256(final bundle_manifest.json) and experiment_digest =
        sha256(FWD_EXPERIMENT_v1.json), computed before the freeze.
      - verify() checks that each frozen row's bundle_digest matches its run directory.
      Test: after a run, the bundle manifest's mtime and sha are unchanged since before the freeze, and row digests
      match.

Item 1 (D247) — the surviving mutations must die.
  - The line cutoff: a fixture tape with a line snapshot after T -> it must not be used.
    Mutation `if snap_utc <= T` -> `if True` must fail a test.
  - The pre-write publication halt: a controlled clock where event selection sees kick−5 min, and the wall clock at
    the pre-write check is kick+1 s -> HALT, with nothing frozen.
    Mutation: remove the pre-write check; it must fail.
  - run_week inputs: _default_run_week's command must include --lines-json, --games and --run-dir. Test by capturing
    the subprocess argv (monkeypatch subprocess.run).
    Mutation: drop --lines-json; it must fail.
  - Bootstrap: a fixture with fixed seeds where whole-game resampling gives a known interval.
    Mutation: no resampling / independent-leg resampling; it must fail.
  Then re-stamp FWD_EXPERIMENT_v1.json. Run the full forward suite and test_freeze_v1, and the REAL
  `python3 nfl/sim/run_forward_v1.py --week 4 --dry-run --window-hours 40 --allow-stale-quotes`. Paste the pass
  counts, the run-directory listing and the row digests.
```
