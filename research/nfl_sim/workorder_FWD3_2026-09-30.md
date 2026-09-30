# Work order FWD3 — record integrity and scoring integrity (audit #7) (2026-09-30)

Written by Cowork after adjudicating ChatGPT audit #7 (`research/cross_ai/chatgpt_audit7_adjudication_2026-09-30.md`,
D240). **No physics change:** every FREEZE_v1 file stays byte-identical. **Gate:** Cowork verifies before
**Thu 10-01 15:00Z**, or TNF runs `--pilot` and the count starts on Sunday.

Pre-check (Cowork):
- **Runtime.**
  - The code and tests take an agent a few hours.
  - Item 3's real runs:
    - one week-4 live dry run (1 game, about 30 s + the bundle);
    - one week-3 pilot freeze through the REAL CLI entry point (14 games at about 30 s ≈ 7 min);
    - one re-run of the same run_id (it must be refused);
    - `score-experiment` on the committed weeks (seconds, plus a nflreadpy fetch).
  - Total under 20 min of compute.
- **Credits.** Zero.
- **Paths.**
  - Code: `nfl/sim/run_forward_v1.py`, `nfl/sim/run_week.py`, `nfl/sim/anchor.py` (read only; FREEZE-hashed),
    `nfl/pipeline/log_ai_opinions.py`, `nfl/sim/actuals.py`.
  - Records: `research/nfl_sim/FWD_EXPERIMENT_v1.json`; run directories under
    `nfl/data/board/week=2026_WW/sim_runs/<run_id>/`.
  - run_week currently writes to `nfl/data/sim/outputs/week=…/` (run_week.py:31, :496, :1042).

```
Work order FWD3 (research/nfl_sim/workorder_FWD3_2026-09-30.md). Branch eng/fwd3 from origin/main in a worktree.
Gate: `git show origin/main:research/cross_ai/chatgpt_audit7_adjudication_2026-09-30.md | grep -c "^### D240"` prints
1. FIRST COMMIT: append D240 verbatim to research/nfl_sim/NFL_SIM_DECISION_v1.md. Items 0-3 = D241-D244, one commit
each, pushed before the next. Keep context lean (grep for functions). Remove the worktree when done.

HARD RULES: (1) FREEZE_v1 files (engine.py, anchor.py, params_v1.json, calibration_v1.json, tables) byte-identical;
test_freeze_v1 before every commit. (2) file:line for code claims. (3) Every ChatGPT audit-#7 counterexample and every
surviving mutation (listed in research/cross_ai/chatgpt_audit7_reply_2026-09-30.md, sections A and D) becomes a test that FAILS on 0792fd122 — paste each failure. No test may substitute a
helper for the real entry point where the property lives in main() or score_experiment(). (4) Real runs in item 3 are
executed and pasted; a missing deliverable = NOT DONE, stop. (5) FWD_EXPERIMENT_v1.json is re-stamped ONCE, last.

Item 0 (D241) — the run record is complete, exclusive and immutable (freeze side).
  (a) build_bundle REFUSES an existing run directory (no exist_ok). Test: the same run_id twice -> HALT, and the first
      bundle is unchanged byte for byte.
  (b) Before the sim, copy into the run directory, and hash, every prediction input the sim reads:
      - team_ratings, tendencies, tendencies_situational, qb, kicker, league_baselines, player_usage and
        active_universe (nfl/data/sim/ratings/);
      - rosters_weekly, depth_charts and injuries (the files run_week and usage read — cite them).
      run_week gets a --run-dir: it reads those copies (and the bundle's props, lines and games), and writes
      picks_log, anchoring_log, layer_log, team_volume and board into <run-dir>/outputs/, never into the shared weekly
      directory.
      Test: main() on a fixture — after the run, changing the shared ratings file does not change what the run
      directory holds, and the outputs exist only under the run directory.
  (c) Game-line freshness: the anchoring line snapshot must be at most 3 h old at T (the same rule as props; the
      --allow-stale-quotes exception applies to --dry-run and --pilot only). Test: fresh props + 5-day-old lines ->
      HALT.
  (d) The sidecar is written into the run directory and hashed. The weekly anchor_sidecar_sim_v1.parquet is no longer
      written.
  (e) Publication is atomic inside freeze():
      - take the wall clock immediately before the write and refuse if it is >= the first kick in the sheet
        (live only);
      - write publication_utc into every frozen row and into the manifest entry;
      - the harness never re-stamps publication afterwards;
      - a write that completes after the kick is quarantined (moved to ai_opinions/quarantine/ and marked excluded in
        the manifest), not left in the record.
      Test with a controlled clock: the pre-write check at kick−1 s and the write at kick+1 s -> quarantined.
  (f) The bundle manifest is finalized BEFORE the freeze. It hashes every file in the run directory, and records the
      experiment-manifest sha256, the cutoff T and the run_id. Its sha256 (bundle_digest) and the experiment digest go
      on every frozen row. Nothing in the run directory changes after the freeze.
      Test: altering any run-directory file afterwards is detected by `verify`.

Item 1 (D242) — the anchor state the solver returned. run_week writes, per game, the values run_anchored_chunked
  RETURNS — iterations, converged, the anchored mean margin and total (run_week.py:~990-1002) — plus the target spread
  and total from the lines used, to <run-dir>/outputs/anchor_returned.parquet. The sidecar reads that file. Never
  minimise over the log.
  Test: the auditor's controlled-batch counterexample — the solver returns iteration 2, converged, −0.7 / 39.3 against
  0 / 40. The sidecar must record iteration 2, anchored = True.

Item 2 (D243) — scoring integrity (applies before any outcome is scored). In log_ai_opinions.py:
  (a) score-experiment validates the experiment name against FWD_EXPERIMENT_v1.json (unknown -> HALT). It runs
      verify() on every frozen file and bundle it reads (mismatch -> HALT). It selects canonical, non-pilot,
      revision-0 rows for the season BEFORE grading. It skips weeks with no eligible rows, and does not abort on
      them.
  (b) The anchor join is exactly one sidecar row per (run_id, event_id); missing or conflicting -> HALT. The anchored
      flag comes only from the row's own run.
  (c) Exact-event grading: map the frozen event_id to the nflverse game_id through the schedule for that season and
      week, and use it for PBP, snap counts and the bootstrap cluster. Never use a team pair. Test: a week-4 opinion
      with a week-3 same-pair final -> unresolved (not graded).
  (d) Crosswalk missing or ambiguous identity -> UNRESOLVED, never VOID. Only "id resolved and absent from that game's
      snap counts" is VOID. Test: remove the crosswalk entry for a player present in the snaps -> unresolved.
  (e) The bootstrap clusters by event_id. Checkpoint policy:
      - below 500 eligible legs -> "descriptive only — no verdict";
      - at 500 -> the descriptive report;
      - at 1,500 -> the one confirmatory verdict, computed on the dataset through the game or window that crossed 1,500
        and saved as a named checkpoint file.
      Test: one leg -> no verdict.
  (f) Add nfl/sim/actuals.py, and every module grading imports, to FWD_EXPERIMENT_v1.json (the "grading" section).
      Correct the manifest's seed description to what anchor.py:175 actually does.
  (g) The CLI works as `python3 nfl/pipeline/log_ai_opinions.py score-experiment ...` from the repo root (fix the
      package import).

Item 3 (D244) — tests, stamp, and REAL acceptance (paste everything).
  Every audit-#7 surviving mutation now fails at least one test. Show each by applying it and pasting the failing test
  name. Re-stamp FWD_EXPERIMENT_v1.json once, then run the full forward test list and test_freeze_v1.
  Real runs:
  - (i) `python3 nfl/sim/run_forward_v1.py --week 4 --dry-run --window-hours 40 --allow-stale-quotes` completes.
    Paste the run-directory listing with its hashes.
  - (ii) The week-3 pilot through the real CLI: `python3 nfl/sim/run_forward_v1.py --week 3 --pilot --as-of
    2026-09-27T16:30:00+00:00 --window-hours 9 --allow-stale-quotes` completes a freeze. Then the same command again
    -> refused (run directory exists). Commit this pilot's run directory and frozen file (each file < 2 MB; if not,
    say which).
  - (iii) `python3 nfl/pipeline/log_ai_opinions.py score-experiment --experiment nfl_fwd_v1` on main's committed weeks.
    It must skip the week-2 pilot-only directory and report 0 eligible legs with no verdict. Then the diagnostic
    `--file` on (ii): paste Δ, CI and P2.
  Then write research/nfl_sim/fwd3_acceptance_2026-09-30.md with all the pasted outputs.

Every item's report separates what the command RETURNED from what it MEANS and ends with NOT DONE and UNVERIFIED.
```
