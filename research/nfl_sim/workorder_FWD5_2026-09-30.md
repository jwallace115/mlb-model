# Work order FWD5 — pin the experiment's logger, then merge main into eng/fwd3 (2026-09-30)

Written by Cowork after D250 (`fwd4b_verification_2026-09-30.md`). **No physics change.** **Gate:** Cowork verifies,
and eng/fwd3 is merged, by **Thu 10-01 15:00Z**, or TNF runs `--pilot`.

Pre-check (Cowork):
- **Runtime.**
  - The merge takes seconds.
  - The forward list takes about 12 s on the Mac per run, and is run about 6 times (base, mutations, final).
  - The nfl/pipeline tests run twice.
  - One real week-4 dry run takes about 2 min.
  - Total under 15 min of compute.
- **Credits.** Zero.
- **Paths.**
  - The new file `nfl/sim/fwd_v1_logger.py` sits at the same depth as `nfl/pipeline/`, so `Path(__file__).parents[2]`
    (log_ai_opinions.py:46) is still the repo root.
  - Importers:
    - `run_forward_v1.py:663` and `:759`;
    - 16 test files under `nfl/sim/tests/`;
    - `research/nfl_sim/make_runbook.py` (not hashed; leave it).
  - The manifest key is `FWD_EXPERIMENT_v1.json:20`.
- **Identity check.** The pinned file's sha256 must equal the hash already in the manifest (`cf100675bd385ca5`), so
  the pinned object is the one FWD3/FWD4 verified.

```
Work order FWD5 (research/nfl_sim/workorder_FWD5_2026-09-30.md). eng/fwd3 in a worktree (git worktree add
/tmp/eng-fwd3 eng/fwd3; git pull; head ffc3e67dc). Gate: `git show origin/main:research/nfl_sim/fwd4b_verification_2026-09-30.md
| grep -c "^### D250"` prints 1. FIRST COMMIT: append D250 verbatim to research/nfl_sim/NFL_SIM_DECISION_v1.md. Items
0-2 = D251-D253, one commit each, pushed before the next. Keep context lean (grep). Remove the worktree when done.

HARD RULES: (1) FREEZE_v1 files byte-identical; test_freeze_v1 before every commit. (2) nfl/sim/fwd_v1_logger.py is a
byte-for-byte copy — never edit it. If it cannot run unmodified from its new path, STOP and report the exact error.
(3) Do not edit NHL code or nfl/pipeline/log_ai_opinions.py beyond what the merge produces. (4) Every command's output
is pasted; a missing deliverable = NOT DONE, stop. (5) FWD_EXPERIMENT_v1.json is re-stamped ONCE, in item 2. (6) Never
commit dry-run sim_runs directories.

Item 0 (D251) — pin before merging.
  (a) git show ffc3e67dc:nfl/pipeline/log_ai_opinions.py > nfl/sim/fwd_v1_logger.py. Paste
      `sha256sum nfl/sim/fwd_v1_logger.py`; it must start cf100675bd385ca5.
  (b) run_forward_v1.py:663 and :759 import from nfl.sim.fwd_v1_logger. grep every experiment-hashed file for
      "log_ai_opinions" and paste the result; after the change, only fwd_v1_logger.py itself may mention it.
  (c) Every file under nfl/sim/tests/ that imports or monkeypatches nfl.pipeline.log_ai_opinions (16 files, including
      string targets such as "nfl.pipeline.log_ai_opinions.x") switches to nfl.sim.fwd_v1_logger. Paste the grep count
      before and after; after must be 0.
  (d) FWD_EXPERIMENT_v1.json: rename the key "nfl/pipeline/log_ai_opinions.py" to "nfl/sim/fwd_v1_logger.py" (the hash
      is unchanged). Any rules text naming the scoring CLI becomes
      `python3 nfl/sim/fwd_v1_logger.py score-experiment --experiment nfl_fwd_v1`.
  Run the forward list (nfl/sim/tests/test_fwd*.py, test_forward_v1.py, test_freeze_v1.py): 88 passed, 0 failed.

Item 1 (D252) — merge origin/main into eng/fwd3.
  git merge origin/main. Conflicts:
    - shared/last_updated.json: take main's;
    - logs/_log_fwd1_cowork.txt: keep BOTH sides' lines, in time order.
  nfl/pipeline/log_ai_opinions.py takes whatever the merge produces. It is the shared logger for the AI readers and NHL,
  and no longer experiment-hashed.
  New tests (nfl/sim/tests/test_fwd5_pin.py):
    (i) decoupling. In a fixture root, append a comment line to nfl/pipeline/log_ai_opinions.py: the harness's manifest
        check passes. The same change to nfl/sim/fwd_v1_logger.py: HALT.
    (ii) The live path never loads the shared module. Run main() on the fixture root in a SUBPROCESS (no --pilot, the
         stub run_week); the subprocess prints "nfl.pipeline.log_ai_opinions" in sys.modules; it must print False.
    (iii) Interop on one fixture week directory, in order:
          - freeze a non-canonical reader with the SHARED (merged) freeze();
          - freeze the canonical reader with the PINNED freeze();
          - pinned verify() passes; shared verify() passes;
          - the pinned score_experiment's cohort selection contains only the pinned rows.
          If the shared freeze writes a manifest the pinned code cannot read, that is a finding: report it and stop. Do
          not edit the pinned file.
  Paste each new test failing on ffc3e67dc (or say why it cannot exist there), then passing.

Item 2 (D253) — proof, stamp, real run.
  (a) Mutations on the PINNED module, each applied then reverted. Paste which behavioural tests fail (other than
      test_experiment_file_hashes):
      - an event_id-only anchor join;
      - the reader filter removed;
      - the cross-week dedup removed from freeze().
      Then apply the dedup removal to the SHARED module only: the forward list must still pass in full — paste it.
  (b) Re-stamp FWD_EXPERIMENT_v1.json once. Paste `git diff origin/main -- research/nfl_sim/FWD_EXPERIMENT_v1.json` and
      explain every changed line.
  (c) Suites:
      - the forward list (count stated, 0 failed);
      - test_freeze_v1 (4 passed);
      - `python3 -m pytest nfl/pipeline/tests` on this branch AND on origin/main — paste both final lines; they must
        match.
  (d) REAL:
      - `python3 nfl/sim/run_forward_v1.py --week 4 --dry-run --window-hours 40 --allow-stale-quotes` completes; paste
        the run-directory listing, then leave that directory untracked;
      - `python3 nfl/sim/fwd_v1_logger.py score-experiment --experiment nfl_fwd_v1` gives 0 eligible legs, no verdict.
      Paste both.

Every item's report separates what the command RETURNED from what it MEANS and ends with NOT DONE and UNVERIFIED.
```

**Policy once FWD5 is merged (part of D251):** `nfl/sim/fwd_v1_logger.py` and every other hashed file are locked from
the first primary freeze until nfl_fwd_v1 ends. NHL and AI-reader work continues in `nfl/pipeline/log_ai_opinions.py`
without touching the experiment.
