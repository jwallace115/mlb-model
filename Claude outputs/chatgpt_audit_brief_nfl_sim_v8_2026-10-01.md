# ChatGPT audit brief #9 (v8) — audit of FWD6, which Cowork implemented itself (2026-10-01)

This is a read-only audit, and a follow-up to your audit #8 on `e0fc3d2d6`. Your reply is saved verbatim as
`research/cross_ai/chatgpt_audit8_reply_2026-09-30.md`, and Cowork adjudicated it in
`chatgpt_audit8_adjudication_2026-09-30.md` (D255).

**This time the implementer is Cowork, not Claude Code.** Cowork wrote FWD6 itself, after Jeff asked for it fixed
properly. So there is no independent verifier between the code and you: **you are the verification.** Posture: guilty
until proven innocent. Cowork's own acceptance notes have been wrong three times (D238, D245, D254).

**Repo:** `jwallace115/mlb-model` (public). **Pin: branch `eng/fwd6` @ `e826a30ae`.** It is origin/main plus three commits:
- D255, the adjudication and scoring amendment;
- FWD6 items 0-2 (D256-D258);
- item 3 (D259).

**Deadline.** The first live freeze of `nfl_fwd_v1` is **Thu 2026-10-01 23:30Z** (TNF PIT@CLE, kick 10-02 00:15Z).
Hashed code must be merged by about **Thu 15:00Z**; otherwise TNF runs as a pilot.

## 1. What FWD6 claims (decisions D256-D259 in `research/nfl_sim/NFL_SIM_DECISION_v1.md`) — verify each

1. **The prediction consumes exactly its bundle.**
   - run_week has `--input-dir`, `--props-file` and `--run-id`.
   - `nfl/sim/read_set.py:route_inputs` repoints these module constants at `<run-dir>/inputs` without editing FREEZE_v1
     files: `engine.RATINGS_DIR`, `calibration.RATINGS_DIR`, `calibration.USAGE_PATH`, `names.ROSTER_PATH` and
     `usage.PBP_DIR`.
   - Props come only from the bundle, and completed-game counts from `inputs/team_game_counts.json`.
   - `ReadSetRecorder` wraps pandas `read_parquet`, `read_csv` and `read_json`, pyarrow `read_table`, and builtins
     `open`. Each file is read once, hashed, and the parser is given those bytes.
   - An audit hook refuses socket connect and getaddrinfo.
   - The harness (`classify_read_set`) HALTs unless every read is either a run-directory file matching the bundle
     manifest, or a repo file matching `FWD_EXPERIMENT_v1.json`; and unless every required input was read from the run
     directory.
2. **Freshness is per participating team, on the copies** (`_team_freshness`, `_last_played_weeks`).
3. **Every run-directory file is archived**, content-addressed, in `<repo parent>/mlb-model-archive/nfl_fwd_v1`.
   `nfl/sim/restore_run.py` rebuilds and verifies.
4. **Quotes are judged row by row.** Lines: a snapshot file is usable only if every row <= T, and a mixed file HALTs.
   Props and lines are re-checked per row for <= T and at most 3 h old. Event metadata must be consistent.
5. **anchor_returned is mandatory**, with exactly one row per simulated game; the fallback is removed. Outputs carry
   season, week and run_id, and are checked.
6. **The shared logger refuses any reserved canonical reader.** Publication receipts are appended to
   `research/nfl_sim/fwd_v1_receipts.jsonl`. `verify_bundle` checks publication.json against its receipt and flags
   unlisted files.
7. **Tests.** 43 new; the full forward list gives 131 passed, 0 failed on Linux. Every freeze-side survivor from your
   audit-#8 (D) table, plus 8 mutations of the new protections, is claimed caught (table in D259).
8. **Manifest.** It now also hashes the files your audit #8 found on the import path, plus the new modules:
   - conftest.py;
   - nfl/__init__.py;
   - nfl/sim/__init__.py;
   - pricer.py;
   - nfl/sim/tests/__init__.py;
   - test_freeze_v1.py;
   - read_set.py;
   - restore_run.py.

   The pinned logger is unchanged (cf100675bd385ca5).

Real runs on Jeff's Mac are NOT at the pin (they are being run now); Cowork will append them to `research/nfl_sim/fwd6_acceptance_2026-10-01.md`:
- a week-4 dry run with the read-set summary;
- a week-3 pilot freeze, then its refused re-run;
- a restore demonstration.

## 2. What we need from you

**R1 — Re-run every audit-#8 (A) counterexample and every (D) freeze-side mutation at the pin.** Mark each FIXED,
PARTIAL or NOT FIXED with file:line.

**R2 — Attack the read-set proof.** Find any way a prediction-affecting input can reach the solver without appearing in
`read_set.json` with the hash of the bytes used. For example:
- reads through APIs that are not wrapped (`Path.read_bytes`/`read_text`, `io.open`, `os.open`, numpy, pyarrow
  datasets, memory maps);
- modules imported after the recorder;
- import-time reads;
- caches (`engine._CACHE`);
- values computed in the harness process and passed on the command line;
- environment variables;
- the clock.

Also:
- Does anything in the subprocess still read the shared PBP, the props archive or the line tape?
- Is a class-(ii) repo file ever a prediction input that should instead be per-run?

**R3 — Walk Thursday's live run end to end at the pin.** Command: `python3 nfl/sim/run_forward_v1.py --week 4
--window-hours 2`, at 23:30Z, with the VM props pull at about 22:00Z and line snapshots every 30 min. Find anything that
would halt when it should not, or not halt when it should. Include the per-team freshness rule on real week-4 data (it
is in the repo).

**R4 — Restore.** From a clean clone plus the archive, can the complete record of a run be rebuilt and verified? What is
not recoverable?

**R5 — One surviving mutation per new test file** (test_fwd6_item0-3, test_fwd5_pin), and per changed harness function.

**R6 — Verdict.** Can TNF be the first primary window on this pin? If not, give the minimum ranked fixes with file:line
that can be verified before Thu 15:00Z.

## 3. Known limits (Cowork's own list — confirm, size, or refute)

- The recorder sees only wrapped Python-level reads. Code files are covered by the manifest hash check at the start of
  the run, not by the read set. A code change between that check and the subprocess import would not be seen.
- `engine_fingerprint()` reads code and table bytes via `Path.read_bytes` to hash them. Those reads are not recorded;
  they are integrity checks, not inputs.
- Depth charts and injuries are copied as record only; the traced prediction does not read them.
- Scoring-side survivors (game_snap None, the below-500 branch, the bundle-digest rejection, the seed) and the scoring
  amendment S1-S4 are FWD7. They are declared, not implemented. Nothing has been scored.
- The items were committed as one code commit plus one stamp commit, not one per item, because they share
  `run_forward_v1.py`.
- The Sunday runbook (FWD2d) is still open.

A reply is most useful as:
- **(A)** the must-fix list before Thu 15:00Z, ranked, with a counterexample for each;
- **(B)** the audit-#8 re-test table;
- **(C)** read-set bypasses found;
- **(D)** surviving mutations;
- **(E)** start Thursday or not.
