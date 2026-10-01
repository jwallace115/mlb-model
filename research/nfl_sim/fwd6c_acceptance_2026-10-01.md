# FWD6c acceptance (2026-10-01)

FWD6c (D263-D265) is Cowork's fix for ChatGPT audit #10 (NO-GO on cf7c89909). Cowork implemented it itself; audit #11
is the independent check.

**Commits**, on top of cf7c89909:
- the FWD6c code commit;
- a test-only commit that strengthens the PBP-snapshot test and adds this note.

**Manifest re-stamps:**

| File | Old stamp | New stamp |
|---|---|---|
| read_set.py | eb0fbc1802fbfb5a | 436eb29bd2a187b0 |
| run_forward_v1.py | 17b34e1f4757770e | 57f7bb53999c0d2b |
| restore_run.py | 489e32caa5187111 | aad1551fc5a58307 |
| run_week.py | ac9529de6a6013a3 | ff653aafacd6d554 |

fwd_v1_logger.py (cf100675bd385ca5) and the FREEZE_v1 files are unchanged. All 51 manifest hashes match.

## Part 1 — Linux (Cowork)

### RETURNED

- **Forward list** in the worktree at the FWD6c code commit (no gitignored data, `test_experiment_file_hashes`
  included): 203 passed, 0 failed with UTF-8 mode ON (exit 0), and 203 passed, 0 failed with UTF-8 mode OFF (exit 0).
  The 203 tests are 170 from before plus 33 in `test_fwd6c.py`.
- **Real worker as a subprocess** (fixture PIT@CLE inputs, `python3 nfl/sim/run_week.py … --bundle-dir`):
  - rc 0, with 45 read-set entries, all `via=["wrapper"]`;
  - 0 violations, 0 conflicts, 0 network attempts;
  - `classify_read_set` passes on all 45.
- **Mutations.** Each was applied to a COPIED tree with that file's manifest stamp re-computed, so a hash rejection
  cannot count as a kill. Each run used `test_fwd6c.py`, `test_fwd6b.py` and `test_fwd6_item0.py` with `-x` and an
  isolated basetemp. The baseline (no mutation) gave 85 passed.

  | # | Mutation | Result |
  |---|---|---|
  | M01 | gate back in-process (`pytest.main`) | caught: test_hostile_pytest_plugin_cannot_reach_the_freeze |
  | M02 | gate env keeps PYTEST_PLUGINS | caught: same test |
  | M03 | gate report ignores skipped | caught: test_gate_report_requires_all_four_named_tests_passed |
  | M04 | update-mode open allowed | caught: test_update_mode_open_is_refused_and_rejected |
  | M05 | classifier accepts audit-only `via` | caught: test_os_open_rdwr_is_a_violation_and_audit_reads_are_unproven |
  | M06 | O_RDWR not a violation | caught: same test |
  | M07 | native readers not refused | caught: test_native_arrow_readers_are_refused |
  | M08 | any `.py` excluded | caught: test_py_suffix_is_not_a_data_exemption |
  | M09 | PBP counts from the shared file | **SURVIVED → test strengthened → caught** (see below) |
  | M10 | claimed cutoff unchecked | caught: test_invocation_cutoff_or_bundle_not_the_bundles_halts |
  | M11 | claimed bundle unchecked | caught: same test |
  | M12 | freshness.json not a mandatory read | caught: test_freshness_json_is_a_mandatory_bundle_read |
  | M13 | rating units counted, not named | caught: test_required_rating_units_by_name_and_worst_unit |
  | M14 | worst unit → best unit | caught: same test |
  | M15 | archive receipt identity unchecked | caught: test_archive_receipt_index_must_hold_the_requested_run |
  | M16 | manifest-entry mismatch silent | caught: test_restore_reports_a_tampered_manifest_entry_and_exits_nonzero |
  | M17 | `via` not persisted | caught: test_os_open_rdwr_is_a_violation_and_audit_reads_are_unproven |

- **M09 detail.** The first test injected the PBP refresh only AFTER the counts, as in audit #10's probe. Counting from
  the shared file therefore still saw the original bytes, so the test could not tell the snapshot from the shared file.
  The test now also refreshes BEFORE counting. It passes on the fix and fails on M09 (checked in a copied tree).

### MEANS

- Each audit-#10 (A) item has a counterexample test that fails when its protection is removed.
- The real worker's reads are all byte-served wrapper reads, so the stricter classifier accepts the real workload.

### NOT DONE / UNVERIFIED

- The Mac runs on the new commit:
  - the forward list;
  - a week-4 dry run;
  - a week-3 pilot at 16:55Z, then its refused re-run;
  - a restore.
- Real macOS behaviour of the gate subprocess. It needs `python3 -m pytest` importable by the harness's own interpreter.
- ChatGPT audit #11, then the merge (by about 15:00Z, or TNF runs as a pilot).
- Not separately mutation-tested: `_install_prefixes`' user-site entry, and the re-stamp of the test-only commit (tests
  are unhashed).
- Remaining limit, stated plainly: the recorder is a Python-level layer, not a sandbox. Native code reading files outside
  the refused APIs is covered only by the code manifest and the static scan.
