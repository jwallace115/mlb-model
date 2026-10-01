# FWD6b acceptance (2026-10-01)

FWD6b (D260-D262) is Cowork's own fix for ChatGPT audit #9 on `e826a30ae`. There is no independent verifier between
this code and audit #10. Part 1 below is Cowork's run on Linux; part 2 (the real runs on Jeff's Mac) is still to come.

**Commit.** A single commit on top of `eng/fwd6` @ `d9b4b272c`, delivered as a `git am` patch. In the cloud it is
`5d2f258d4`; the SHA changes when Jeff applies it.

**Manifest stamps:**

| File | Stamp |
|---|---|
| read_set.py | eb0fbc1802fbfb5a |
| restore_run.py | 489e32caa5187111 |
| run_forward_v1.py | 17b34e1f4757770e |
| run_week.py | ac9529de6a6013a3 |
| fwd_v1_logger.py | cf100675bd385ca5 (unchanged) |

All 51 manifest hashes match the files.

## Part 1 — Linux (Cowork, 2026-10-01 01:15Z-02:18Z)

### RETURNED

- **Forward list on the final tree.** Run in a fresh worktree of the commit, which holds no gitignored data (`nfl/data/pbp/`
  has only the committed depth_charts.parquet), with `test_experiment_file_hashes` included:

  | Run | Result | Exit |
  |---|---|---|
  | UTF-8 mode ON (C locale, `sys.flags.utf8_mode` 1) | 170 passed, 0 failed | 0 |
  | UTF-8 mode OFF (`PYTHONUTF8=0 LC_ALL=C.UTF-8`, utf8_mode 0, the Mac's condition) | 170 passed, 0 failed | 0 |

  The 170 tests are the 131 from before, plus 39 in `test_fwd6b.py`.

- **New tests against the old code.** The 39 `test_fwd6b.py` tests were run with read_set, restore_run, run_forward_v1
  and run_week taken from `e826a30ae`: 32 failed and 7 passed. The 7 that pass are survivor-killing tests, where the
  old code was already right but nothing tested it:
  - archive location;
  - archive corruption;
  - a snapshot exactly at the cutoff;
  - END GAME case;
  - kicker freshness;
  - the anchor boundary at exactly 1.0;
  - the static scan that the worker modules use only recorded read APIs.
- **Mutation run.** Every mutation was applied in a COPIED tree (never the working tree), with an isolated pytest
  basetemp. Each runs the full forward list with `-x`, minus the manifest-hash test (every mutation changes a hashed
  file, so that test would catch them all).

  | # | Mutation | Result | First failing test |
  |---|---|---|---|
  | D01 | archive default dir renamed | caught | test_default_archive_location |
  | D02 | archive corruption check removed | caught | test_corrupt_archive_object_halts |
  | D03 | lines cutoff `<=` → `<` | caught | test_snapshot_exactly_at_cutoff_is_usable |
  | D04 | END GAME case-sensitive | caught | test_end_game_matching_is_case_insensitive |
  | D05 | kicker freshness omitted | caught | test_stale_kicker_halts |
  | D06 | PBP source hash zeros | caught | test_pbp_source_hash_recorded |
  | D07 | receipt registry overwritten | caught | test_two_freezes_append_two_receipts_and_duplicates_mismatch |
  | D08 | load_receipts returns the last only | caught | (same) |
  | D09 | duplicate receipt accepted | caught | (same) |
  | D10 | anchor boundary strict | caught | test_anchor_miss_exactly_one_is_anchored |
  | D11 | receipt rows 999999 | caught | test_receipt_rows_equal_frozen_rows |
  | N01 | finalisation re-authorises changed files | caught | test_input_changed_after_the_worker_read_it_halts |
  | N02 | verify before freeze removed | caught | test_change_between_finalisation_and_freeze_halts |
  | N03 | invocation check removed | caught | test_invocation_not_matching_bundle_halts |
  | N04 | returned-target check removed | caught | test_returned_target_differing_from_bundle_halts |
  | N05 | anchoring_log identity unchecked | caught | test_anchoring_log_identity_checked |
  | N06 | schedule exactly-one check removed | caught | test_two_schedule_matches_halt |
  | N07 | freshness uses the unrestricted max | caught | test_freshness_uses_the_selected_week_not_the_max |
  | N08 | io.open not wrapped | **SURVIVED → test strengthened → caught** | test_reads_through_other_apis_are_recorded (now asserts `via == "wrapper"`) |
  | N09 | audit-hook open backstop removed | caught | test_reads_through_other_apis_are_recorded |
  | N10 | engine cache not cleared | caught | test_engine_cache_is_cleared_so_tables_are_recorded_every_run |
  | N11 | usage not routed | caught | test_late_imported_usage_module_is_routed |
  | N12 | output hash unchecked | caught | test_output_entry_with_wrong_hash_halts |
  | N13 | qb not a mandatory read | caught | test_qb_ratings_is_a_mandatory_read |
  | N14 | receipt not archived | caught | test_complete_run_record_restored_from_archive_alone |
  | N15 | manifest not bootstrapped from the receipt | caught | (same) |
  | N16 | worker shifts the total by +0.5 | caught | test_real_worker_reads_targets_from_bundle |
  | N17 | text reads decoded as utf-8 StringIO (the old bug) | caught | test_recorded_text_reads_decode_exactly_like_open_with_utf8_mode_off |

- **The re-kill of N08 was checked in a copied tree.** The strengthened test fails with
  `read_text: recorded via audit`.
- **The first mutation run was invalid and was discarded.** Every mutation was reported "caught" by the same test. That
  run shared pytest's default basetemp with a concurrent suite run, and, more importantly, ran as a child process with
  UTF-8 mode off. That exposed the real defect below.

### MEANS

- **The defect the mutation run found.** With UTF-8 mode off, the new `io.open` wrapper raised `LookupError` on any
  `Path.read_text`, and it skipped newline translation.
  - UTF-8 mode is off on the Mac, so any library read through `read_text` inside the worker would have crashed a Mac
    run.
  - The earlier "167 passed" (D262 draft) passed only because the cloud shell runs in the C locale, where UTF-8 mode is
    on.
  - It is fixed and tested, and the suite now passes in both modes.
- **Every listed freeze-side protection fails a test when it is removed.**
- **Two Mac-path defects were found by reading, not by testing:**
  - the `/private/etc` exclusion;
  - a pre-D262 receipt crashing `restore_run.py --run-id`.

  Both are fixed and tested.

### NOT DONE / UNVERIFIED

- **Part 2, the real runs on Jeff's Mac on the new commit:**
  - a week-4 dry run;
  - a week-3 pilot at a new as-of, then its refused re-run;
  - a restore by `--run-id` with the run directory and frozen file moved aside.
- **macOS itself.** Linux with UTF-8 mode off is the closest Cowork can get. Paths under `/private`, the Mac's Python
  install prefixes, and any file the worker's libraries open on macOS are unverified until part 2.
- **The schedule source on the Mac.** It is nflreadpy unless `nfl/data/pbp/schedules_2026.parquet` exists. A local
  snapshot is used as-is, so if a kickoff later moves, a stale local file would HALT the mapping (the 60-min check);
  that is the safe direction.
- **The audit #9 reply was not saved verbatim** (it lives only in the chat). D260-D262 restate each item it raised.
- ChatGPT audit #10.
- FWD7 (S1-S4 and the scoring-side survivors).
- FWD2d (the Sunday runbook).

## Part 2 — Jeff's Mac (in progress)

### 2a. Forward list on the Mac (eng/fwd6 @ f84bcbbd2; macOS, Python 3.13, UTF-8 mode off)

**RETURNED:** 169 passed, 1 failed (45 s). The failure was
`test_real_default_worker_path_never_imports_shared_logger`, with `KeyError: '--bundle-dir'` inside the test's fake
`subprocess.run`.

**MEANS: a defect in the test, not in the hashed code.**
- The test patched `subprocess.run` for the whole child process. The harness runs `test_freeze_v1` in-process via
  `pytest.main`, and on the Mac that loads the installed `seleniumbase` pytest plugin.
- At import, that plugin calls `platform.architecture()`, which shells out to `file`. That call reached the fake,
  which assumed every call was the worker.
- The cloud has no such plugin, which is why it passed there.

**Fix (test only; tests other than test_freeze_v1 are unhashed, so the manifest is unchanged).** The fake stubs only
the worker invocation (a command containing `--bundle-dir`) and passes every other call to the real
`subprocess.run`.
- Reproduced in the cloud with a stand-in plugin (`PYTEST_PLUGINS`, a module that shells out at import): it failed
  identically before the fix and passes after.
- The test still catches its mutation (an import of the shared logger inside `_default_run_week` gives
  `SHARED_LOADED True`, and the test fails).
- Full forward list with the stand-in plugin and UTF-8 mode off: 170 passed, 0 failed.

**For audit #10.** The live freeze gate runs `test_freeze_v1` with whatever pytest plugins are installed on the Mac
(`plugins=[]` does not stop entry-point autoload). It worked in every Mac run so far. It is noted as a robustness
question, not changed: run_forward_v1.py is hashed, and this is not a correctness defect.
