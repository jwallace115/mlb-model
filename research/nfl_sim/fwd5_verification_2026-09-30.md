# Cowork verification of FWD5 — the experiment's logger is pinned; eng/fwd3 merges (2026-09-30, 19:42Z)

`eng/fwd3` @ `2d44e38a2`. Cowork re-ran everything below on Linux, from a clean checkout of that commit and from a trial
merge into `origin/main` @ `8512ca13e`.

## What holds (reproduced)

**The pin.**
- `nfl/sim/fwd_v1_logger.py` sha256 = `cf100675bd385ca5…`, which is the verified ffc3e67dc logger byte for byte.
- `run_forward_v1.py:663` and `:759` import it.
- None of the 12 hashed .py files imports `nfl.pipeline.log_ai_opinions`.
- The tests under `nfl/sim/tests/` have 0 references to it.
- The manifest hashes `nfl/sim/fwd_v1_logger.py` and no longer lists the shared file.

**The forward list:**
- 88 passed, 0 failed on 2d44e38a2;
- 88 passed, 0 failed on the trial merge with current main;
- test_freeze_v1: 4 passed.

**The live path never loads the shared module.** Cowork ran the two harness test files (19 tests, including the true
live test through `main()` on the fixture root) in a subprocess. `nfl.pipeline.log_ai_opinions` was not in
`sys.modules` at exit, and importing run_forward_v1, fwd_v1_logger, run_week and actuals does not load it either.

**Interop in one week directory** (Cowork's script, on the n59 fixtures), in order:
1. A shared-logger freeze by an AI reader.
2. A pinned freeze by the canonical reader: revision 0.
3. Pinned verify() and shared verify(): both 0 bad and 0 unlisted. The manifest entries have identical keys.
4. A second AI reader through the shared logger: freezes, revision 0.
5. A second canonical freeze through the pinned logger: HALT on dedup.
6. The shared logger's attempt to freeze the canonical reader: also HALT.

**Mutations** (D253, as reported): an event_id-only join, the reader filter removed, and the dedup removed from the pinned
freeze are each caught by named behavioural tests. The dedup removed from the shared module leaves the forward list
green.

**The shared-logger suite** (`nfl/pipeline/tests`, excluding the NHL H4 file, which needs the `nhl` package absent from
Cowork's sparse clone): 76 passed, 1 failed, identical on main and on the merged tree.
- The failure is `test_score_first_side_and_units`. It fails at 82c38aef8 too, before any NHL commit.
- It is a stale AI-log test (a fixture with no snap data now settles as unresolved). It is not part of the experiment.

**The real dry run and score-experiment** (as reported): PIT@CLE, 11 matched, anchored in 3 iterations; 0 eligible legs,
no verdict.

## What is wrong

1. **Item 1 (D252) was not delivered.**
   - There is no `test_fwd5_pin.py` and no D252 section.
   - The report says "NOT DONE: nothing", which is false. It is the same failure class as before: a missing deliverable
     reported as done.
   - Cowork executed the three checks the tests were meant to encode (above). All hold.
   - Tests are not experiment-hashed, so writing them later changes nothing in the experiment.
2. **The branch history was rewritten, not merged.** Main's commits since 82c38aef8 were replayed onto eng/fwd3 with new
   SHAs:
   - for example, H3 is 1075895bb on main and dc75896e6 on the branch;
   - there is no merge commit.
   - Nothing was lost. The branch's files are a superset of main's, and its `_log_fwd1_cowork.txt` holds every main
     line plus FWD's.
   - The effect is that main's history will show those commits twice. Fixing that would take another rewrite, so it
     stays.
   - Rule for later orders: `git merge`, never rebase or replay.

## Decision

### D254 — FWD5 accepted on Cowork's executed checks; eng/fwd3 (D240-D253) merges to main; the primary count of nfl_fwd_v1 starts at week-4 TNF (2026-09-30)

Accepted:
- `nfl/sim/fwd_v1_logger.py` is the verified logger byte for byte (cf100675bd385ca5). The harness and the forward tests
  use it, and the manifest hashes it.
- The shared `nfl/pipeline/log_ai_opinions.py` is no longer part of the experiment.
- Cowork reproduced:
  - the forward list at 88/0, on the branch and on the trial merge;
  - the live path never loading the shared module;
  - pinned and shared freezes coexisting in one week directory, with both verifies clean and canonical dedup holding
    through either logger.

Not delivered: item 1's test file and D252. Cowork's executed checks stand in for them. The test file follows after TNF,
and is not hashed.

The branch replayed main's commits instead of merging. That is kept, and orders merge from now on.

From the first primary freeze until nfl_fwd_v1 ends, `nfl/sim/fwd_v1_logger.py` and every hashed file are locked. NHL
and AI-reader work continues in the shared logger.

The first primary window is week-4 TNF:
- PIT@CLE;
- run at 23:30Z Thu 10-01: `python3 nfl/sim/run_forward_v1.py --week 4 --window-hours 2`;
- no --pilot.
