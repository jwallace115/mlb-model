# ChatGPT audit #8: adjudication by Cowork (2026-09-30, 21:55Z)

The audit was run on `main` @ `e0fc3d2d6` (brief v7). The auditor's text is saved as `chatgpt_audit8_reply_2026-09-30.md`.
Cowork spot-checked the central claims against the code at the pin before accepting them. **Every item checked holds.**

## Checked by Cowork

**run_week reads the shared inputs.**
- `run_week.py:979-981` loads `_load_ratings()` (engine `RATINGS_DIR`), `player_usage_weekly` and
  `active_universe_weekly` from `nfl/data/sim/ratings/`.
- `--run-dir` only overrides the output directory (`:1058-1060`).
- usage reads rosters, depth charts and injuries from `PBP_DIR` (`usage.py:95-97`). If a file is missing, it fetches
  them from nflreadpy over the network (`:105-110`).

**The freshness of a line snapshot is decided from its first row.** `_load_lines_at_T` uses
`df["snapshot_utc"].iloc[0]` (`run_forward_v1.py:81`).

**`anchor_returned.parquet` is optional.** When it is missing the sidecar falls back
(`run_forward_v1.py:722-726`).

**Ordinary scoring grades by team pair.**
- `score()` calls `_game_actuals(pbp, home, away)` (`fwd_v1_logger.py:596`).
- The game_id path, `_game_actuals_by_id`, runs only in the `--file` diagnostic branch (`:960`).

**The committed week-3 run directory has no `inputs/`** (git ls-tree at the pin).

The auditor's executed counterexamples are accepted as evidence, and Cowork did not re-run them:
- a changed shared rating reaches the solver;
- a shared-logger canonical freeze is admitted;
- a future line row hidden behind a valid first row;
- a missing anchor_returned;
- a 2025/week-2 output frozen as week 4;
- the two-game sidecar-deletion example;
- 13 surviving mutations.

## Cowork's errors, withdrawn

**D245 accepted three things that were not built:**
- (a) "inputs copied and hashed" as if run_week consumed them. It does not; FWD3 item 0(b) required it.
- (b) "exact-event grading". It exists only in the diagnostic branch.
- (c) "the checkpoint policy". Only the below-500 rule exists.

Cowork verified the copies and the outputs, and never checked what the subprocess actually read.

**D254 said Cowork's three executed checks "stand in" for the missing FWD5 tests.** They missed the reverse order: the
shared logger can make the first canonical freeze.

**The brief said "weeks 2-3 hold pilot rows only".** Week 3 has 1,081 non-pilot AI-reader rows; its canonical rows are
all pilots.

**Size, in practice.** The NFL regular season never repeats a (home, away) pair, so wrong-week grading by team pair
cannot occur inside one regular season from real data. It is still not the pre-registered rule, and the fix is declared
below.

## Decision

### D255 — ChatGPT audit #8 adjudicated: the freeze side is still not valid (run_week does not consume the bundle); FWD6 fixes the freeze side; scoring amendments S1-S4 are declared now, before any primary outcome; TNF runs as a pilot unless FWD6 is verified by Thu 15:00Z (2026-09-30)

**Confirmed at e0fc3d2d6:**
- run_week reads shared ratings, usage, active universe and rosters, and the shared props archive. The bundle copies are
  not what the prediction consumed.
- The committed week-3 bundle cannot be restored: rosters and injuries exist nowhere else.
- Canonical-reader rows can be written through the shared logger. `publication.json` can be deleted without detection.
- Line freshness is judged from a snapshot's first row.
- A missing anchor_returned silently falls back.
- The prediction output's season, week and run are not checked against the bundle.
- Ordinary scoring grades by team pair.
- The 1,500 verdict is not frozen.
- A missing sidecar biases the result by exclusion.
- Unlisted files, null digests and all-zero experiment digests are accepted.
- Unrelated readers' rows can crash scoring.
- Thirteen mutations survive, one per test file.

**Freeze side: fixed by FWD6 before any primary freeze.**
- run_week consumes `<run-dir>/inputs` and the bundle's props, and never fetches.
- Freshness is checked per participating team, on the consumed files.
- Inputs are archived with a demonstrated restore.
- Line and prop timestamps are checked on every row.
- anchor_returned is mandatory, with one record per simulated event.
- Output identity is validated.
- The canonical reader is reserved against the shared logger.
- A publication receipt registry.
- The FWD5 tests; tests that kill the freeze-side survivors; hashes for the unhashed import files.

**Scoring side: declared now, as scoring amendment S1-S4.**
- The prediction manifest and frozen records are unchanged.
- FWD7 implements it in a separate, separately hashed scorer, before the first primary grading.
- The rules are fixed here, before any primary outcome exists:
  - **S1 — scoring set.**
    - The experiment scores only rows in files named by a publication receipt.
    - Each row must have: a listed file; non-null digests matching its run's bundle and the experiment; a unique
      contract; exactly one (run_id, event_id) sidecar row.
    - A canonical, non-pilot, revision-0 row that fails any of these BLOCKS scoring (HALT) until it is resolved. It is
      never quietly excluded.
    - Other readers' files are never read.
  - **S2 — exact event.**
    - Each frozen event_id maps to the nflverse game_id through the schedule for its season and week, recorded in the
      bundle at freeze time. Only that game_id's PBP and snap rows grade it.
    - Participation: the GSIS→PFR id has offense + special-teams snaps > 0.
    - No name fallback: an id that is missing or ambiguous → unresolved.
    - A push → unresolved.
    - Every grading run archives the hashes of its PBP, roster, crosswalk and snap inputs.
  - **S3 — one confirmatory checkpoint.**
    - Windows are ordered by first kick. The confirmatory dataset is every eligible leg from the windows up to and
      including the first window whose cumulative settled eligible count reaches 1,500.
    - It is computed once, when every leg in those windows is settled or 14 days have passed since the last kick (then
      still-unresolved legs are reported as unresolved).
    - It is saved to `research/nfl_sim/fwd_v1_confirmatory.json`: contract ids, source hashes, exclusions, scorer
      version and hash, seed, Δ, CI and verdict.
    - It is never recomputed on more data. A correction is a versioned correction record.
    - The 500 descriptive report is frozen the same way, at 500.
  - **S4 — accounting.** Every report shows, by run and event: frozen candidates, anchored, settled, VOID, unresolved and
    excluded (with reasons). P2 units are reported descriptively at every report.

**Start window.** It stays the first window after FWD6 is verified and merged.
- TNF (run 23:30Z Thu) is primary only if that happens by **Thu 10-01 15:00Z**. Otherwise TNF runs `--pilot`.
- Cowork's recommendation is to run TNF as a pilot regardless. It is one game, about 11 legs, and a real rehearsal of the
  new live path.
- The Sunday windows also need FWD2d, the runbook.
- v1's physics (FREEZE_v1) are unchanged throughout.
