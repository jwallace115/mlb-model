# Work order FWD6 — the prediction consumes its bundle; quotes, outputs and publication are provable (audit #8) (2026-09-30)

Written by Cowork after adjudicating ChatGPT audit #8 (`research/cross_ai/chatgpt_audit8_adjudication_2026-09-30.md`,
D255). It covers the freeze side only; the scoring amendment S1-S4 is FWD7. **No physics change:** FREEZE_v1 files
(engine.py, anchor.py, params_v1.json, calibration_v1.json, tables) stay byte-identical, and so does
`nfl/sim/fwd_v1_logger.py`.

**Gate:** TNF is primary only if Cowork verifies FWD6 and it is merged by **Thu 10-01 15:00Z**; otherwise TNF runs
`--pilot`.

Pre-check (Cowork):
- **Runtime.**
  - Code and tests take an agent a few hours.
  - Real runs:
    - a week-4 live dry run (1 game, about 3 min);
    - a week-3 pilot freeze through the real CLI (14 games at about 30 s ≈ 7 min, plus the bundle);
    - a re-run that must be refused;
    - a restore demonstration (seconds).
  - Mutation runs: about 10, at 15-50 s each.
  - Total under 30 min of compute.
- **Credits.** Zero.
- **Paths (verified at e0fc3d2d6).**
  - Shared reads in run_week:
    - `run_week.py:979-981` (`_load_ratings()` via `engine.RATINGS_DIR`; player_usage; active_universe);
    - `:64`, `:224` (pbp_2026);
    - `:121` (line_history);
    - `:349`, `:612`, `:994` (props archive).
  - usage: `usage.py:37` `PBP_DIR`, `:95-110`. It fetches from nflreadpy when a file is missing.
  - anchor (FREEZE_v1, read-only): `anchor.py:237` (pbp) and `:252` (line_history).
  - Harness: `run_forward_v1.py:81` (line snapshot), `:228-246` (input copies), `:722-726` (anchor_returned optional),
    `:417` (fill matching), `:799` (publication).
  - New paths:
    - `nfl/sim/restore_run.py`;
    - the input archive `~/mlb-model-archive/nfl_fwd_v1/sha256/<hash>` (outside git);
    - the receipts registry `research/nfl_sim/fwd_v1_receipts.jsonl`.

```
Work order FWD6 (research/nfl_sim/workorder_FWD6_2026-09-30.md). New branch eng/fwd6 from origin/main, in a worktree
(git worktree add /tmp/eng-fwd6 -b eng/fwd6 origin/main). Gate: `git show
origin/main:research/cross_ai/chatgpt_audit8_adjudication_2026-09-30.md | grep -c "^### D255"` prints 1. FIRST COMMIT:
append D255 verbatim to research/nfl_sim/NFL_SIM_DECISION_v1.md. Items 0-3 = D256-D259, one commit each, pushed before
the next. Update from main ONLY with `git merge origin/main` — never rebase, cherry-pick or replay. Keep context lean
(grep). Remove the worktree when done.

HARD RULES:
(1) FREEZE_v1 files and nfl/sim/fwd_v1_logger.py are byte-identical; run test_freeze_v1 before every commit.
(2) Give file:line for every code claim.
(3) Every audit-#8 counterexample in research/cross_ai/chatgpt_audit8_reply_2026-09-30.md sections (A) and (C) that is
    on the freeze side becomes a test that FAILS on e0fc3d2d6. Paste each failure. Tests go through the real entry point
    (main(), or run_week.main() / its subprocess) where the property lives there.
(4) Real runs are executed and their output pasted; a missing deliverable = NOT DONE, and you stop. The final report may
    not say "NOT DONE: nothing" unless every numbered deliverable below is pasted.
(5) FWD_EXPERIMENT_v1.json is re-stamped ONCE, last.

Item 0 (D256) — the prediction consumes exactly the bundle.
  (a) run_week gets --input-dir (the harness passes <run-dir>/inputs). Before any load it points every prediction data
      path at that directory by setting module constants, without editing FREEZE_v1 files:
      - engine.RATINGS_DIR;
      - usage.PBP_DIR;
      - player_usage and active_universe (:980-981);
      - rosters, depth charts and injuries.
      Props come only from the bundle's props.parquet, never the archive (:349, :612, :994). Game lines come only from
      --lines-json. If a needed input file is missing: HALT. Never fetch from the network.
  (b) Read-set proof.
      - Under --run-dir, run_week installs sys.addaudithook. It records every file opened for reading outside the Python
        installation and site-packages, with its sha256 computed at open time, into <run-dir>/outputs/read_set.json.
      - Any socket connect is a HALT.
      - Before the freeze, the harness requires each read-set entry to be one of:
        - (i) under the run directory;
        - (ii) a FREEZE_v1- or experiment-manifest-hashed file whose hash matches;
        - (iii) copied into inputs/ with an identical hash.
      - Anything else HALTs. That includes a shared file read directly by FREEZE_v1 code (anchor.py:237/:252): copy it
        into inputs/ at bundle time and require the same hash.
      - read_set.json is hashed in the bundle manifest.
  (c) Freshness is computed on the consumed copies, per participating team: team ratings and tendencies >= W−1; usage,
      active universe and kicker rows >= W−1 for each team in the window. A season-wide maximum is not enough.
  (d) Restore.
      - build_bundle also writes every inputs/ file to ~/mlb-model-archive/nfl_fwd_v1/sha256/<hash> (configurable),
        content-addressed.
      - Files under 2 MB are committed in the run directory.
      - New nfl/sim/restore_run.py --run-dir X rebuilds inputs/ from git plus the archive and runs verify_bundle.
  Tests:
    - The auditor's counterexample: change the shared CLE week-4 rating after build_bundle. The value the real
      run_week.main() solver receives equals the bundle copy (0.4334993874), or the run HALTs on the read-set check.
    - A missing input file → HALT, with no network call.
    - A read of an unlisted shared file → HALT.

Item 1 (D257) — quotes, returned anchor, output identity.
  (a) Every selected game-line row and prop row satisfies T−3h <= its own source timestamp <= T, and belongs to the
      event, kickoff and market of the bundle. A mixed or inconsistent snapshot → HALT (run_forward_v1.py:81; the props
      loader). Test: a 23:40Z totals row behind a valid first row with T = 23:30Z → HALT (the auditor's case).
  (b) anchor_returned.parquet is mandatory on live and pilot runs, with exactly one record per simulated event. It is
      missing or incomplete → HALT. The minimum-error fallback is removed from the harness path.
  (c) run_week's outputs carry season, week, run_id and event_id, and the harness HALTs unless they equal the bundle's
      before fill_sheet. Test: outputs labelled 2025 / week 2 / run "previous-experiment" → HALT (the auditor's case).

Item 2 (D258) — publication ownership, and the FWD5 tests.
  (a) The shared nfl/pipeline/log_ai_opinions.py freeze REFUSES any reader_model equal to a canonical_reader declared in
      research/nfl_sim/FWD_EXPERIMENT_*.json (a guard only; no other change to the shared file). Test: the auditor's
      shared-logger canonical freeze → HALT, including the reverse order (the shared logger first).
  (b) Receipts.
      - After a successful, non-quarantined freeze, the harness appends one line to
        research/nfl_sim/fwd_v1_receipts.jsonl: experiment digest, run_id, bundle_digest, frozen file name and sha256,
        rows, publication_utc, first kick, pilot flag and the sha256 of publication.json.
      - verify_bundle fails if a receipt names the run and publication.json is missing or has a different hash.
      - A new receipt_status(run_id) returns "complete", "no receipt" or "mismatch".
      Tests:
        - deleting publication.json after a fixture freeze → verify fails;
        - a freeze whose receipt append is skipped → "no receipt".
  (c) Write nfl/sim/tests/test_fwd5_pin.py, the FWD5 item-1 tests that were never delivered:
      - decoupling;
      - the live path never imports nfl.pipeline.log_ai_opinions (checked in a subprocess);
      - interop in both orders.

Item 3 (D259) — survivors, hashes, stamp, real acceptance.
  (a) Each freeze-side mutation that survived audit #8 must fail at least one behavioural test (not the manifest-hash
      test). Apply each alone with a temporarily re-stamped manifest, run the full forward list, paste the failing test
      names, and revert:
      - H anchor tolerance 1.0 → 1.05;
      - H props pull_timestamp <= T filter removed;
      - H experiment digest written as 64 zeros;
      - L freeze() already-kicked rejection removed;
      - H post-write quarantine disabled;
      - H rosters, depth and injuries not copied;
      - H returned sidecar forced converged=True;
      - H duplicate prediction-key rejection removed;
      - H live manifest check removed.
      The scoring-side survivors are FWD7; list them as NOT DONE here.
  (b) Add to the experiment manifest's hashes: conftest.py, nfl/__init__.py, nfl/sim/__init__.py, nfl/sim/pricer.py,
      nfl/sim/tests/__init__.py, nfl/sim/tests/test_freeze_v1.py, nfl/sim/restore_run.py. Re-stamp once, and paste the
      manifest diff with every changed line explained.
  (c) Suites: the full forward list (all test_fwd*.py + test_forward_v1.py + test_freeze_v1.py), with the count; 0 failed.
  (d) REAL — paste:
      (i) `python3 nfl/sim/run_forward_v1.py --week 4 --dry-run --window-hours 40 --allow-stale-quotes` completes.
          Paste the read_set.json summary (every path and its class i, ii or iii) and the per-team freshness table.
      (ii) `python3 nfl/sim/run_forward_v1.py --week 3 --pilot --as-of 2026-09-27T16:45:00+00:00 --window-hours 9
           --allow-stale-quotes` completes a freeze and writes a pilot receipt. Run the same command again → refused.
      (iii) Move (do not delete) (ii)'s inputs/ aside, then run `python3 nfl/sim/restore_run.py --run-dir <that dir>`
            → restored, and verify_bundle is clean.
      Commit (ii)'s run directory, its files under 2 MB and the receipt. Leave the dry-run directory untracked.

Every item's report separates what the command RETURNED from what it MEANS, and ends with NOT DONE and UNVERIFIED.
```
