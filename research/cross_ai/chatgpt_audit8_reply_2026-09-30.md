# ChatGPT audit #8: the reply's findings (as pasted by Jeff, 2026-09-30), for the FWD6/FWD7 tests

Pin audited: `e0fc3d2d6283ea8d0191138471421a2b30e588d5`. The audit ran in isolated copies. In the auditor's environment
the full forward list gave **86 passed, 2 skipped**; the skips need 2026 snap/crosswalk data it did not have.

**Verdict: do not start the primary experiment on `e0fc3d2d6` as it stands.** The inputs preserved in the bundle are not
necessarily the inputs the subprocess consumes.

## (A) Must fix before Thu 15:00Z, ranked

### 1. The simulation must consume its frozen input bundle, and the bundle must be recoverable

Files: `run_week.py:979`, `run_forward_v1.py:228`.

`build_bundle()` copies inputs, but run_week still loads ratings, usage, active universe and rosters from the shared
paths. `--run-dir` redirects outputs only, not input reads. The board builder also rereads the shared props archive.

**Executed counterexample.** After the bundle was built, the auditor changed Cleveland's shared week-4 passing-success
rating:
- the preserved bundle held 0.4334993874;
- the real `run_week.main()` solver call received 0.99;
- `verify_bundle()` reported no mismatches.

**Minimum repair.**
- Pass an explicit input directory into the subprocess and route every prediction-affecting read through it.
- Check freshness on the files actually consumed, per participating team, not as a season-wide maximum.
- Provide a working restore procedure. The committed week-3 bundle lacks all 11 `inputs/` files, not only the three over
  2 MB. Nine have byte-identical counterparts elsewhere at this commit; rosters and injuries do not. The pinned scorer
  therefore halts before it can report zero eligible legs.
- A content-addressed archive outside git is acceptable for oversized inputs, provided restoring them and verifying the
  hashes is demonstrated before the first primary freeze.

### 2. The experiment needs an exclusive publication record, and its canonical reader must be reserved

Files: `fwd_v1_logger.py:295`, `run_forward_v1.py:799`.

The logger code is pinned, but its records can still be written through the shared logger.

**Executed counterexample.**
- The shared logger created a fresh canonical-reader, revision-0 opinion, and pinned verification accepted it.
- With matching fixture bundle metadata, the pinned experiment scorer admitted it: Cohort 1 leg, Δ +0.240000.
- There was no `publication.json`.
- Separately, deleting `publication.json` after a genuine harness fixture freeze left `verify_bundle()` clean.

**Minimum repair.**
- Use an experiment-owned directory or registry, and reject canonical-reader freezes through the shared entry point.
- Each successful publication must durably bind the experiment digest, the run/bundle identity, the frozen-file hash and
  the actual publication time.
- A file still awaiting that receipt does not count as a completed primary freeze.
- Capture this evidence now. Strict enforcement on the grading side can follow under the amendment in (E).

### 3. Validate the timestamp of every selected line row

File: `run_forward_v1.py:81`.

Whether a snapshot is eligible is decided from its first row's timestamp. Freshness then uses the first timestamp per
event. Neither shows that every consumed quote existed at the cutoff.

**Executed counterexample.** One snapshot held ordinary pre-cutoff rows plus a totals market timestamped 23:40Z, ten
minutes after the 23:30Z cutoff. The full live harness fixture froze total 99.0 with `source_age_min = -10.0`.

**Minimum repair.** Either reject mixed or inconsistent snapshots, or validate every selected row against
`T−3h ≤ source_timestamp ≤ T`, with consistent event, kickoff and market metadata. Test a future row hidden behind a
valid first row.

### 4. Reject missing returned-anchor evidence and mismatched prediction identity

Files: `run_forward_v1.py:724`, `run_forward_v1.py:417`.

Two full-harness fixture counterexamples succeeded:
- with `anchor_returned.parquet` deleted, the run still froze, using the legacy minimum-error fallback;
- predictions labelled season 2025, week 2, run `previous-experiment` produced one sim_v1 match, frozen as season 2026,
  week 4.

**Minimum repair.**
- Require returned-anchor evidence on the live path.
- Validate the output's season, week, run and event against the bundle before filling opinions.
- Require exactly one returned-anchor record for each simulated event.
- The current team-pair/name/market/line match does not establish those identities.

**Thursday specifically.**
- A successful 22:00Z props pull is 90 min old at 23:30Z, inside the limit.
- Game lines need their own valid timestamps, no earlier than 20:30Z.
- The committed PIT/CLE team ratings and tendencies reach week 4; usage, active universe and kickers reach week 3.
- None of that resolves the shared-input race above.

## (B) Audit-#7 findings and mutations, re-tested

| Audit-#7 A item | Verdict | Evidence at the pin |
|---|---|---|
| 1. Scoring integrity | PARTIAL | Tampering with a listed file now HALTs; unknown experiments are rejected; run-specific anchor joins work; one eligible leg gets no verdict. But unlisted files are accepted, the canonical preselection is thrown away before grading, and old pilot bundles can abort the report (scorer :1023). |
| 2. Immutable, complete bundle | PARTIAL | Reusing a run directory HALTs, and copies, sidecars and outputs are hashed. But the subprocess still consumes the shared inputs, and committed bundles cannot all be restored. |
| 3. Grading identity and seed description | FIXED | actuals.py is hashed, and its original mutation fails the manifest test. The seed description now matches `(home, away, season, week, 42)` (manifest :18). |
| 4. Exact event and participation | PARTIAL | A missing crosswalk is unresolved on the ordinary scoring path. **Wrong-week grading survives:** a week-3 final settled a week-4 opinion, and score_experiment admitted it with Δ +0.24 (logger :597). The ordinary `score_experiment()` calls `score()`, which still uses `_game_actuals(pbp, home, away)`. The schedule/game_id implementation exists only in the diagnostic `--file` branch. |
| 5. Returned anchor iteration | PARTIAL | With returned evidence supplied, the original controlled-solver case now gives iteration 2, −0.7 / 39.3, anchored=True. Missing evidence silently brings back the defective fallback. |
| 6. Freshness and publication | FIXED for the original cases | Five-day-old lines HALT; a write that finishes at kick+1 s is quarantined. The remaining timestamp and publication-record defects are in (A). |

| Audit-#7 surviving mutation | Re-test |
|---|---|
| Every sidecar forced anchored | FIXED: FWD3 anchor tests fail |
| Line cutoff removed | FIXED: FWD4 cutoff test fails |
| Incomplete targets counted as receptions, no restamp | FIXED: the manifest test fails |
| Zero-match halt removed | FIXED: the harness test fails |
| Bootstrap by individual legs | FIXED: the whole-game bootstrap test fails |
| Pre-write deadline check removed | FIXED: the controlled-clock test fails |
| Duplicate-pick rejection removed | **NOT FIXED**: the whole list stays green |
| A historical target share changed | FIXED across the whole list: 23 failures, including the fingerprint checks |
| Subprocess line/game arguments dropped | FIXED: the argument test fails |
| `score()` finds no snap data for any game | **NOT FIXED**: the whole list stays green |

## (C) The brief's §3

1. **The 1,500-leg checkpoint is not frozen: CONFIRMED.**
   - Logger :1137 prints a confirmatory verdict whenever the current cohort reaches 1,500. It saves neither the cohort
     checkpoint nor the first verdict.
   - D245's acceptance of the checkpoint policy was too broad.
   - This can be a declared scoring amendment; it does not change Thursday's probabilities.
2. **FWD5's missing tests: CONFIRMED, and Cowork's ad hoc checks are not sufficient.**
   - There is no `test_fwd5_pin.py` and no D252.
   - The auditor reproduced Cowork's interop sequence. It misses the reverse order: **the shared logger can write the
     first canonical freeze**, which would then block the harness's freeze.
   - Other executed failures:
     - an unrelated reader's validly hashed row with an unsupported market made experiment scoring raise `KeyError`,
       because the canonical preselection does not isolate grading;
     - an opinion file removed from the manifest stayed eligible: `unlisted` is returned but ignored;
     - an all-zero `experiment_digest` was accepted;
     - a null `bundle_digest` was accepted, because nulls are dropped before the comparison.
   - The runbook still directs scoring through the shared logger (runbook :105).
   - Revision counting and dedup trust the shared manifest. `_reader_models()` can attribute older files through the
     mutable `reader_attribution.json`, which is not a fit source of canonical experiment membership.
3. **Missing sidecar → exclusion: CONFIRMED; a smaller cohort is not a safety argument** (logger :786).
   - Two-game example: with complete evidence Δ +0.04. Removing the losing game's sidecar match gives Δ −0.16, with one
     counted exclusion.
   - The count makes the omission visible; it does not prevent selection bias.
   - Deleting a listed sidecar correctly fails verification when the manifest is unchanged. The remaining problem is
     evidence that was never properly registered. Such rows must block primary scoring until resolved.
4. **Unhashed import closure: PARTLY CONFIRMED; Cowork's static list was incomplete.**

   | Path | Unhashed repo code on it |
   |---|---|
   | Harness, including its pytest gate | `conftest.py`, `nfl/__init__.py`, `nfl/sim/__init__.py`, `nfl/sim/pricer.py`, `nfl/sim/tests/__init__.py`, `nfl/sim/tests/test_freeze_v1.py` |
   | run_week subprocess | `nfl/__init__.py`, `nfl/sim/__init__.py`, `nfl/sim/pricer.py` |
   | Ordinary pinned scoring | `nfl/__init__.py`, `nfl/sim/__init__.py` |

   - The package initializers are empty. `conftest.py` modifies the import path. The test module runs the launch gate.
   - pricer.py's module initialization runs (via calibration and run_week), but its pricing functions are not called.
   - actuals_k1.py does not execute.
   - No other production module appeared through the subprocess or data dispatch, and the shared logger was absent from
     the traced harness process.
   - The fix is to record these hashes.
5. **History: CONFIRMED, with no demonstrated effect on predictions.** The H3 commits share a patch ID. The "WNBA season
   updater" commit changes three MLB prop files and `shared/last_updated.json`. Do not rewrite history again.
6. **Carried items.**
   - The Sunday runbook is confirmed wrong:
     - it groups London, the Sunday afternoon games and SNF into one 14-game window;
     - it models VM slots without weekday limits;
     - its Thursday recommendation assumes a Thursday 23:45 pull, although that slot is labelled MNF-only.
   - The kicker label: partly refuted. The filename is now right, and PIT and CLE have week-3 rows. It describes season
     presence, not per-team freshness.
   - The shared scoring test: confirmed. It fails at the pin and at 82c38aef8, because its prop calls supply no
     snap-participation evidence.

**Numbers:**
- the pinned logger's sha matches ffc3e67dc (cf100675bd385ca5db3c36b25ff9c890e20aae0457f674fc9a2205c7b0557cbc);
- the forward list gives 86 passed + 2 skipped in the auditor's environment;
- the freeze suite gives 4 passed;
- the PIT@CLE anchor reproduced in a real 10,000-sim run: −2.408 / 38.1368, 3 iterations;
- 70 lines / 43 two-way reproduced;
- the 11 matches were not verified (the subprocess stopped on the missing committed roster);
- the pinned scoring command HALTs on the committed checkout (11 missing bundle inputs);
- canonical non-pilot rows counted independently: 0;
- week 3 holds 2,487 rows, 1,081 of them non-pilot; its 1,406 canonical rows are all pilots.

**Rules partly implemented.**
- Implemented: tag, market, two-way, the final cohort reader/revision filters, the Δ formula and the event-cluster
  bootstrap.
- Not implemented: exact-event grading and mandatory provenance.
- Decisions the code makes that need registering: the name-based participation fallback, offense-plus-special-teams
  participation, pushes treated as unresolved, missing-sidecar exclusion, and suppressing P2 below 500 legs.

## (D) One surviving mutation per forward test file

Each was applied alone, with the manifest temporarily re-stamped, and the whole 13-file list gave 86 passed, 2 skipped,
0 failed. H = run_forward_v1.py; L = fwd_v1_logger.py.

| Test file | Surviving mutation |
|---|---|
| test_fwd2_anchor.py | H: anchor tolerance 1.0 → 1.05 |
| test_fwd2_bundle.py | H: the props `pull_timestamp ≤ T` filter removed |
| test_fwd2_experiment.py | H: 64 zeros written as every row's experiment digest |
| test_fwd2_item0_fixes.py | L: freeze()'s rejection of already-kicked games removed |
| test_fwd2_settlement.py | L: ordinary scoring's `game_snap = None` |
| test_fwd2b_harness.py | H: the post-write late-publication quarantine disabled |
| test_fwd3_item0.py | H: rosters, depth charts and injuries no longer copied |
| test_fwd3_item1.py | H: the returned sidecar forced to converged=True |
| test_fwd3_item2.py | L: the below-500 branch changed to `n_legs < 0` |
| test_fwd4_item0.py | L: the bundle-digest mismatch rejection disabled |
| test_fwd4_item1.py | L: the default bootstrap seed changed to 7 |
| test_forward_v1.py | H: the duplicate prediction-key rejection removed |
| test_freeze_v1.py | H: the live experiment-manifest check removed |

## (E) What can wait as declared, pre-outcome scoring amendments

These must be declared before Thursday's outcomes exist; the implementation may follow before grading. Keep the
original prediction manifest and frozen records, and use a separately versioned scoring amendment rather than silently
re-stamping their identity.

1. **One scoring path for verified canonical rows.**
   - Pass the selected rows into the grader instead of rereading every reader's files.
   - Require listed files, non-null matching digests, valid publication receipts, unique contracts and exactly one
     run/event sidecar.
   - Verify only the experiment's registered records. Unrelated pilots, failed dry runs and AI files must not control
     whether it can score.
2. **Exact-event settlement.**
   - Archive the event-to-schedule mapping (season, week, teams, kickoff) and grade only that game_id.
   - Archive the PBP, roster, crosswalk and snap inputs used by each grading run.
   - Fix the diagnostic branch's remaining missing-crosswalk → VOID path, and state whether the name fallback is
     allowed.
3. **One immutable confirmatory checkpoint.**
   - Declare the ordered freeze windows in advance.
   - Select the earliest window boundary that reaches 1,500 eligible legs, after the earlier grading it depends on is
     resolved.
   - Save once: the contract IDs, source hashes, exclusions, scorer version, seed, statistic and verdict.
   - Later windows never enlarge that dataset. A correction takes a versioned correction record, not another
     confirmatory look.
4. **Explicit missingness and settlement accounting.**
   - Missing provenance blocks primary scoring; missing outcome data stays unresolved.
   - Report, by run and event: frozen candidates, anchored candidates, settled, VOID, unresolved and exclusions.
   - State the participation and push rules.
   - Report P2 descriptively even below the threshold.
5. **Regression and operational work.**
   - Add the missing FWD5 tests, real scorer integration tests, and tests that kill the survivors above.
   - Fix the Sunday runbook before Sunday, and its shared-logger scoring command before grading.
   - Hash the currently unhashed import dependencies without changing the frozen prediction behaviour.

## (F) Verdict

Not with this pin. Thursday can start as primary only after (A)'s repairs are implemented — input consumption,
publication ownership, timestamps and output identity — and their counterexamples fail on the final commit, with a
successful restore of the complete run record. Declare (E)'s amendments before outcomes exist. Otherwise, run Thursday
as pilot/diagnostic only and keep the primary count at zero.
