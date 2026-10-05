# ChatGPT audit brief #8 (v7) — re-audit of the forward experiment the night before its first live freeze (2026-09-30)

This is a read-only audit, and a follow-up to your audit #7 on `0792fd122` (saved verbatim as
`research/cross_ai/chatgpt_audit7_reply_2026-09-30.md`). Cowork accepted every item (D240). Four fix orders followed,
FWD3, FWD4, FWD4b and FWD5, and Cowork verified each one:

| Order | Decision |
|---|---|
| FWD3 | D245, rejected in part |
| FWD4 | D248 |
| FWD4b | D250 |
| FWD5 | D254 |

**Posture: guilty until proven innocent, including for the verifier.** Your audit #7 showed that Cowork's D238 accepted
fixes that were not there. Assume the same may be true of D245-D254. §3 lists what Cowork already knows is wrong or
weak; find what it missed.

**Repo:** `jwallace115/mlb-model` (public). **Pin: `main` @ `e0fc3d2d6`** (the merge of eng/fwd3). Later "auto:" commits
do not touch `nfl/` or `research/nfl_sim/`.

**Deadline.** The first live freeze of experiment `nfl_fwd_v1` (reader `nfl_sim_v1_156cd057`) is **Thu 2026-10-01
23:30Z**: week-4 TNF, PIT@CLE, kick 10-02 00:15Z. The command is
`python3 nfl/sim/run_forward_v1.py --week 4 --window-hours 2`.
- Every file the experiment manifest hashes is locked from that freeze until the experiment ends.
- A finding that needs a hashed file changed is only actionable **before about Thu 15:00Z**. After that it becomes a
  declared amendment, or the experiment restarts.

## 1. What changed since your audit #7 (claims — verify them)

The decisions are D240-D254 in `research/nfl_sim/NFL_SIM_DECISION_v1.md`, and the verification notes are in
`research/nfl_sim/`:
- `fwd3_verification_2026-09-30.md`;
- `fwd3_acceptance_2026-09-30.md`;
- `fwd4_verification_…`;
- `fwd4b_verification_…`;
- `fwd5_verification_…`.

**Freeze side** (`nfl/sim/run_forward_v1.py`):
- A run directory `nfl/data/board/week=2026_WW/sim_runs/<run_id>/` cannot be reused.
- The prediction inputs (ratings, tendencies, usage, active universe, rosters, depth charts, injuries) are copied into
  `inputs/` and hashed.
- run_week gets `--run-dir`, and its outputs go to `<run-dir>/outputs/`.
- Game lines have the same 3 h age limit as props.
- The anchor sidecar is written from `anchor_returned.parquet` (what the solver returned) and hashed in the bundle.
- `bundle_manifest.json` is finalized before the freeze.
- `bundle_digest` and `experiment_digest` are on every frozen row.
- Publication: a pre-write kick check; a write that lands after the kick is quarantined; the result is recorded in
  `publication.json`.

**Scoring side** (`score_experiment`, `primary_cohort`, `primary_statistic` in the pinned logger, below):
- The experiment name is validated against the manifest.
- verify() runs on every frozen file and bundle, and each row's bundle_digest is checked.
- Canonical, non-pilot, revision-0 rows are selected before grading.
- Pilot-only weeks are skipped.
- The anchor join is on (run_id, event_id): a duplicate HALTs; a missing row is EXCLUDED and counted (not HALT; see
  §3.3).
- Exact-event grading goes through the schedule's game_id.
- A missing crosswalk entry is unresolved, not VOID.
- The bootstrap clusters by event_id.
- Below 500 legs: no verdict.

**FWD5, the pin (D251-D254).** Main's NHL work (H3-H6) had changed the shared logger `nfl/pipeline/log_ai_opinions.py`
by +558/−67, and that file was experiment-hashed. So:
- `nfl/sim/fwd_v1_logger.py` is now a byte-identical copy of the logger verified at `ffc3e67dc` (sha256
  `cf100675bd385ca5…`);
- `run_forward_v1.py:663` and `:759` import it;
- the forward tests import it;
- the manifest hashes it instead of the shared file;
- the shared logger is left to NHL and the AI readers.

**Tests:**
- the forward list, `nfl/sim/tests/test_fwd*.py` + `test_forward_v1.py` + `test_freeze_v1.py` (13 files): 88 passed,
  0 failed;
- `test_freeze_v1`: 4 passed;
- Cowork reproduced both on Linux, at 2d44e38a2 and on a trial merge.

**Real runs (on the owner's Mac):**
- a week-4 live dry run: PIT@CLE, 70 lines / 43 two-way / 11 matched, anchored in 3 iterations;
- `score-experiment`: 0 eligible legs, no verdict.

## 2. What we need from you

**R1 — Re-test audit #7.** For each of your (A) items 1-6 and each surviving mutation in your (D) table, rerun the
original counterexample, or a stronger one, on `e0fc3d2d6`. Mark each FIXED, PARTIAL or NOT FIXED, with file:line.

**R2 — The pin.**
- Is `fwd_v1_logger.py` really the object that runs live and the object that scores?
- Can the shared `log_ai_opinions.py` still influence the experiment through any path? For example:
  - the same `ai_opinions/` week directories and `manifest.json`;
  - cross-week dedup across files written by either logger;
  - a canonical-reader freeze through the shared CLI;
  - revision counting;
  - `_reader_models()` attribution of older files.
- Compute the runtime import closure of `run_forward_v1.main()`, `run_week.py` (it runs as a subprocess) and
  `score-experiment`. List every repo module in it that the manifest does NOT hash (Cowork's own finding is in §3.4).

**R3 — Walk Thursday's live run end to end at the pin.** List anything that would:
- freeze a wrong or stale price;
- freeze a probability from the wrong game or market;
- let later information in;
- fail to halt when it should;
- halt when it should not;
- leave a record that cannot be reproduced later.

Pay particular attention to:
- the props slot (the VM pulls about 22:00Z, and the run is 23:30Z);
- the line snapshots;
- ratings freshness;
- the run_id/bundle linkage;
- `publication.json`;
- what must be committed afterwards: there is a 2 MB limit, and three inputs over 2 MB are kept on the Mac only.

**R4 — Scoring before the first grading.** Read these in `nfl/sim/fwd_v1_logger.py`:
- `score_experiment` (:882);
- `primary_cohort`;
- `primary_statistic` (:826);
- `score`;
- `_load_snap_participants`;
- the GSIS→PFR crosswalk;
- `_first_side_won`;
- the bundle-digest check (~:1080-1102).

Does every pre-registered rule in `FWD_EXPERIMENT_v1.json` ("eligibility", "settlement", "scoring") have a faithful
implementation? Where does the code decide something the rules do not state?

**R5 — Tests.** For each forward test file, give one mutation to the pinned logger or the harness that survives the
whole forward list.

**R6 — Verdict.** Is the experiment valid to start at Thursday's TNF window? If not, give the minimum ranked changes, with
file:line, that can be done and verified before Thu 15:00Z. Say which can instead wait as declared, pre-outcome amendments
to scoring. Nothing has been scored yet.

## 3. Defects the verifier already knows about (confirm, size, or refute)

1. **The 1,500-leg confirmatory verdict is not frozen.**
   - FWD3 item 2(e) required: "at 1,500 -> the one confirmatory verdict, computed on the dataset through the game or
     window that crossed 1,500 and saved as a named checkpoint file".
   - `score_experiment` (~:1124-1139) prints a verdict whenever n ≥ 1,500 on all data up to the run. Nothing is saved,
     and every later call gives a new "confirmatory" verdict on more data: repeated looks.
   - **D245 accepted "the checkpoint policy" without noticing.**
   - No outcome has been scored, and 1,500 is about 8-10 weeks away. Is this a pre-TNF fix, or a declared scoring
     amendment?
2. **FWD5 item 1's tests were never written** (`test_fwd5_pin.py`: decoupling, live path never importing the shared
   module, interop). D252 is missing from the decision doc, and the session reported "NOT DONE: nothing".
   - Cowork ran the three checks itself (D254): a subprocess run of the harness tests never loads
     `nfl.pipeline.log_ai_opinions`; shared and pinned freezes coexist in one week directory, both verifies are clean,
     and canonical dedup HALTs through either logger.
   - Are those checks sufficient?
3. **A missing sidecar row excludes rather than HALTs.** FWD3 item 2(b) said HALT, and D248 accepted exclusion with a
   count. Is that safe? Could a run's rows be silently dropped in a way that correlates with outcome?
4. **Unhashed modules in the prediction path.** Cowork's static import scan from `run_forward_v1.py`,
   `fwd_v1_logger.py` and `run_week.py` reaches two repo modules the manifest does not hash:
   - `nfl/sim/pricer.py`: imported at `run_week.py:28`; Cowork found no call to `price_game` or
     `sgp_probability_raked` in run_week;
   - `nfl/sim/actuals_k1.py`: imported inside a K1 report function in `engine.py:~3317`.

   Confirm whether either executes on the live path, and whether the scan missed anything, for example via
   subprocesses, `importlib` or data-driven dispatch.
5. **History.** FWD5 replayed main's commits onto eng/fwd3 instead of merging (duplicate SHAs), and a Mac cron commit
   ("auto: WNBA season updater", MLB props files) rode along on the branch. Cowork believes neither affects the
   experiment. Confirm or refute.
6. **Carried from audit #7 §3.**
   - The Sunday runbook (`research/nfl_sim/make_runbook.py`, not hashed) is still wrong; order FWD2d is pending.
   - The kicker freshness label is cosmetic.
   - A shared-logger test, `test_score_first_side_and_units`, fails on main. It has failed since before the NHL work,
     and belongs to the AI log, not the experiment.

## 4. Numbers you can check

- The forward list: 88 passed, 0 failed.
- `sha256(nfl/sim/fwd_v1_logger.py)` = `cf100675bd385ca5…`, equal to
  `git show ffc3e67dc:nfl/pipeline/log_ai_opinions.py | sha256sum`.
- The week-4 dry-run anchor: target −2.5 / 38.0; anchored in 3 iterations.
- `score-experiment --experiment nfl_fwd_v1` on the pin: 0 eligible legs, no verdict. Weeks 2-3 hold pilot rows only.

A reply is most useful as:
- **(A)** the must-fix list before Thu 15:00Z, ranked, with file:line and an executed counterexample for each;
- **(B)** R1 as a table: your audit-#7 items and mutations, each FIXED, PARTIAL or NOT FIXED;
- **(C)** §3 items confirmed, sized or refuted;
- **(D)** surviving mutations, one per test file;
- **(E)** what can wait as declared pre-outcome scoring amendments;
- **(F)** one paragraph: start Thursday or not.
