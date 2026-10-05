# ChatGPT audit #11 reply — FWD6c on eng/fwd6 (2026-10-01)
aba96dfc39cfe2446e7eab96669a5b981ee2f8a6

This pin is **NO-GO for primary TNF**. The exact five audit-#10 A counterexamples are blocked, but three broader failures remain: startup code can change the frozen prediction, a cached Python module can execute different code from the hashed source, and native readers still deliver unrecorded inputs through ordinary argument forms. The tests also miss five of the 28 old mutations and ten new ones.

I read the pinned worktree and ran code extracted from that commit under `/private/tmp/nfl-audit11-aba96dfc3`. Tests, mutated copies, fixtures, freezes and restore destinations were outside both repositories. The real archive was read-only. Source links below point to `/Users/jw115/mlb-model-fwd6`, which was at the audited pin when inspected; they do not point to main's different implementation. This reply is the sole authorized repository write. Simulation physics, fitting and calibration quality remain out of scope: executing the frozen worker and observing imports is not a review of those algorithms.

Independent environment: macOS arm64, Python 3.13.1, executable `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3`. The clean forward suite returned **201 passed, 2 skipped, zero failed in each UTF-8 mode**, with plugin autoload disabled. The skipped settlement tests require external 2026 snap/crosswalk data. I did not independently run Linux. Executed counterexamples, source-based conclusions and remaining uncertainties are distinguished below. A surviving mutation establishes a coverage gap, not that its deliberately introduced behavior exists in the unmodified code.

## (A) Must fix before Thu 2026-10-01 15:00Z, ranked

### A1. Control startup and import paths before the parent, gate and worker execute project code — P1

**Locations:** [run_forward_v1.py:886](/Users/jw115/mlb-model-fwd6/nfl/sim/run_forward_v1.py:886), gate command at [920](/Users/jw115/mlb-model-fwd6/nfl/sim/run_forward_v1.py:920), worker launch at [938](/Users/jw115/mlb-model-fwd6/nfl/sim/run_forward_v1.py:938), and the logger import at [1149](/Users/jw115/mlb-model-fwd6/nfl/sim/run_forward_v1.py:1149). The parent also needs a controlled external launcher: cleaning its environment inside `main` is too late for Python startup imports.

**Executed counterexample 1 — altered freeze with unchanged source.** An external `sitecustomize.py`, found through inherited `PYTHONPATH`, imported the pinned logger and wrapped `freeze` to replace the matched probability with 0.97. The real harness, four-test gate, source-hash check and pinned logger's remaining checks ran. The fixture worker emitted **0.62**, the frozen `sim_v1` row contained **0.97**, `verify_bundle=[]`, `receipt_status='complete'`, exit 0. No source file changed. Startup ran in both parent and gate child. This is the old failure through a different execution route; removing `PYTEST_PLUGINS` does not close it.

**Executed counterexample 2 — a gate that ran no tests.** I put a stand-in `pytest.py` on inherited `PYTHONPATH`. It wrote a JUnit document containing the four expected testcase names and exited successfully. `run_freeze_gate()` accepted it; its marker said **“No tests ran.”** The current report validator checks report contents, not which module produced them. The intact source's nonzero-exit and missing-report checks do not establish module provenance.

**Executed `.pth` check.** In a temporary virtual environment, an executable `.pth` entry ran under `python -I -B`; the child reported `isolated=1`, `no_site=0`. Thus adding `-I` alone is insufficient. I did not modify the installed interpreter or its site files. This `.pth` probe demonstrates startup execution; the full altered-freeze demonstration used `sitecustomize`.

**Minimum change:** use a reviewed, hashed launcher that establishes the trusted interpreter and approved dependency/repository paths before any project import, for all three processes. One concrete approach is `-I -S` with explicit paths and no processing of arbitrary `.pth`, `sitecustomize`, user-site, `PYTHONPATH` or `PYTHONHOME`. Keep the pytest-variable removal and plugin-autoload disablement. Load the known pytest installation and the intended pinned test file in that controlled child. Record the interpreter/dependency environment used. Merely changing the child environment leaves the parent exposed; merely validating XML more strictly leaves the fake-module route exposed.

**Feasibility checked, not an implemented fix:** a temporary `-I -S -B` gate bootstrap with explicit repository and installation directories, and a fresh bytecode-cache prefix, ran the real four tests successfully in **3.54 seconds**, despite a fake pytest module on inherited `PYTHONPATH`. I did not implement or validate a complete replacement launcher for parent and worker.

**Acceptance before primary:** launch through the actual proposed production command with the hostile startup module, a hostile `.pth` in an otherwise unapproved installation path, and fake pytest module present. They must not execute. The worker's 0.62 must remain 0.62 in the frozen file. Real assertion failure, skipped/missing/duplicate gate test, malformed/missing report and nonzero gate exit must stop publication. Repeat the real week-4 worker under the same startup profile.

### A2. Bind executed project code to the checked source; do not trust existing bytecode caches — P1

**Locations:** source-only validation at [run_forward_v1.py:614](/Users/jw115/mlb-model-fwd6/nfl/sim/run_forward_v1.py:614); source-name mapping at [read_set.py:144](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:144) and exemption at [160](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:160); code-path membership at [91](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:91).

**Executed counterexample.** In an external copy, I kept every `.py` byte unchanged and installed a timestamp-valid `__pycache__/fwd_v1_logger.cpython-313.pyc`. Its code was the original logger plus a wrapper changing the frozen probability to 0.97; its header matched the original source's size and modification time. The child ran with both `-B` and `PYTHONDONTWRITEBYTECODE=1`. Results:

- Worker `cal_p`: **0.62**; frozen `p_first`: **0.97**.
- All source-hash checks and gate tests passed; bundle verification was empty; receipt was complete; exit 0.
- Source logger SHA remained **`cf100675bd385ca5db3c36b25ff9c890e20aae0457f674fc9a2205c7b0557cbc`**.
- `sys.dont_write_bytecode` was true. It prevents writing caches, not reading them.

`_code_source` associates a cache filename with a source filename; it does not establish that the cache's code was compiled from those source bytes. The parent logger import precedes no recorder capable of making that proof either. Hashing the source and then allowing Python's ordinary cache selection is not an execution identity check.

**Minimum change:** compile/import project code from the checked source in a controlled, unchanged snapshot. A practical implementation can give every parent/gate/worker process a fresh, empty, privately created `-X pycache_prefix=...`, combined with `-B`, so existing project caches cannot be selected. An explicit verified-source loader is another option. Propagate the policy to children; interpreter flags on the parent do not automatically appear in the current child command. Treat dependencies as an explicit trusted environment, not as project-source hashes. Do not claim `-B` alone fixes this.

**Acceptance before primary:** rerun the timestamp-valid cached-logger counterexample and assert both the loaded code origin and frozen 0.62. Also exercise an ordinary stale cache. This must pass through the same production launcher used for A1 and the same source snapshot the gate validates.

### A3. Reject unsupported native file sources regardless of path representation — P2

**Locations:** [read_set.py:266](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:266), pass-through at [277](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:277), ParquetFile pass-through at [303](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:303), refusal predicate at [305](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:305). Static check: [test_fwd6c.py:599](/Users/jw115/mlb-model-fwd6/nfl/sim/tests/test_fwd6c.py:599).

**Executed counterexamples with the unmodified recorder installed:**

```python
pyarrow.dataset.dataset(parquet_path.as_uri()).to_table()  # returned 0.99
pyarrow.memory_map(os.fsencode(text_path)).read()           # returned b'0.10'
pyarrow.parquet.ParquetFile(parquet_path.as_uri()).read()    # returned 0.99
```

Each returned data with **zero read-set entries and zero violations**. Ordinary string filesystem paths to `dataset` and `memory_map` were correctly refused. The URI fails the local `os.path.exists`/`isfile` predicate; the byte-string path fails the recognized-type predicate. Neither failure means the native reader cannot open it.

I then read all **14 mandatory bundle inputs** normally and consumed the hidden `file://` dataset value in the same recording interval. The persisted proof had 14 wrapper entries, no violations, and **`classify_read_set` returned PASS**. This is an executed false-completeness result, not just an unused API on a list. I did not replace the real solver with a native dataset reader or demonstrate that the committed pilot used one.

**Minimum change:** make accepted source types explicit. Normalize supported byte/path/URI representations into the byte-serving path, or reject them with a persisted violation. Do not use local existence as permission to pass an unknown source through to a native reader. Native filesystem handles must also be refused or accepted only through a mechanism that proves their bytes were recorded. Close the demonstrated `LocalFileSystem().open_input_file` path described in C; retain only deliberately supported in-memory sources. Test positional and keyword forms.

**Acceptance before primary:** each example above, a native filesystem handle passed into pandas, and an otherwise complete read set containing one hidden read must either produce the correct hash of delivered bytes or halt classification. Then rerun the real worker: its current 45 wrapper reads provide a concrete compatibility target. A larger regular-expression blacklist alone cannot establish this property.

These fixes are bounded launch/provenance changes. They do not require changing the simulation. All three need implementation, re-stamping and independent verification of the resulting commit before 15:00Z. If that does not happen, keep TNF explicitly pilot; do not promote it retrospectively after outcomes. The coverage work in D and recovery-status cleanup can follow before those paths are relied on for scoring; they are not additional reasons to discard an otherwise valid pre-kick capture.

## (B) Audit-#10 re-test table and verifier claims

### The five A counterexamples and recovery findings

“FIXED” below means the named old counterexample is fixed. It does not expand into a universal guarantee about startup or I/O.

| Audit #10 item | Verdict at this pin | Independent evidence and current location |
|---|---|---|
| A1: hostile `PYTEST_PLUGINS` changes 0.62 to 0.97 | **FIXED for that injection; PARTIAL overall isolation** | Plugin never loaded; frozen value remained 0.62; verification empty and receipt complete. Gate is outside parent. New startup/fake-pytest bypasses are A1 above. [run_forward_v1.py:886](/Users/jw115/mlb-model-fwd6/nfl/sim/run_forward_v1.py:886). |
| A2: update-mode read consumes 0.99 but certifies 0.10 | **FIXED for both old mechanisms; PARTIAL overall capture** | `r+b` raised PermissionError before consuming the changed value. `os.open(O_RDWR)` still opened and consumed 0.99, but persisted a violation and audit provenance; classification halted. New native bypasses are A3 above. [read_set.py:199](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:199), [283](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:283), [407](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:407). |
| A3: shared PBP refresh mixes counts and source hash | **FIXED** | Injected refresh after counting: bundled KC/CAR counts were 1 each, archived source recomputed 1 each, refreshed shared source recomputed 2 each. Archived SHA matched. The strengthened before-count refresh test also kills the shared-count mutation. [run_forward_v1.py:419](/Users/jw115/mlb-model-fwd6/nfl/sim/run_forward_v1.py:419). |
| A4: incorrect/missing cutoff, wrong bundle, omitted freshness read | **FIXED** | Cutoff 1900 and `/wrong/bundle` now halt. Missing cutoff and missing mandatory freshness read are covered by passing tests. A real fresh worker's outputs also passed the actual parent validator. [read_set.py:45](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:45), [run_forward_v1.py:855](/Users/jw115/mlb-model-fwd6/nfl/sim/run_forward_v1.py:855). |
| A5: four arbitrary unit names substitute for required units | **FIXED** | Replacing CLE `pass_off` with `junk_unit` returned team-ratings week −1 and halted. Tests exercise each required label and one stale unit among fresh units; worst→best mutation now fails. [run_forward_v1.py:152](/Users/jw115/mlb-model-fwd6/nfl/sim/run_forward_v1.py:152), [180](/Users/jw115/mlb-model-fwd6/nfl/sim/run_forward_v1.py:180). |
| Restore accepts an archive index for a different run | **FIXED** | A `wrong.json` payload naming `20260927T165500Z` halted with the explicit identity mismatch. [restore_run.py:61](/Users/jw115/mlb-model-fwd6/nfl/sim/restore_run.py:61). |
| Restore silently accepts existing bad opinions metadata | **FIXED through restore CLI; PARTIAL status API** | Changing the existing entry's SHA produced `UNAVAILABLE … differs from the receipt` and exit 1. Yet output still said `verify_bundle: clean; receipt_status: complete`. The helper never checks that opinions entry. [restore_run.py:94](/Users/jw115/mlb-model-fwd6/nfl/sim/restore_run.py:94), [148](/Users/jw115/mlb-model-fwd6/nfl/sim/restore_run.py:148); [run_forward_v1.py:547](/Users/jw115/mlb-model-fwd6/nfl/sim/run_forward_v1.py:547). Do not use that helper alone as a grading eligibility predicate. |

### Audit #10 C bypasses

| Mechanism | Verdict | Evidence at this pin |
|---|---|---|
| `Path.read_text`, `Path.read_bytes`, `io.open` | **FIXED for exercised ordinary path reads** | Returned bytes/text with matching wrapper SHA. Both UTF-8 baselines pass. [read_set.py:280](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:280), [339](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:339). |
| Ordinary `ParquetFile(path)` | **FIXED; URI case NOT FIXED** | Ordinary path returned 0.99 with the correct hash; wrong-hash mutation is killed. URI returned 0.99 with no entry. [read_set.py:298](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:298). |
| Previously captured pandas `read_parquet` alias | **FIXED for the exercised alias** | Underlying wrapped I/O recorded the bytes. Previously captured native memory-map alias still bypasses; these are different readers. [read_set.py:333](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:333). |
| Raw `os.open`, FileIO and mmap after `os.open` | **FIXED as an acceptance bypass** | Entries carry `via=['audit']`; classifier refuses them. These APIs are not all prevented from returning bytes. [read_set.py:182](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:182), [407](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:407). |
| `r+` transient-byte example | **FIXED** | PermissionError plus violation; classifier halt. [read_set.py:283](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:283). |
| Native Arrow dataset/memory-map readers | **PARTIAL** | The exact old string-path examples are refused; URI and bytes-path variants bypass. [read_set.py:305](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:305). |
| Arbitrary external data named `prediction.py` | **FIXED for the old suffix exemption** | Reading numeric 0.99 now produced a wrapper entry. Membership still does not attest loaded bytecode. [read_set.py:144](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:144). |
| `site-packages` lookalike name | **FIXED for the old substring bypass** | Real-prefix check remains; fixture test passes. True installation directories remain explicitly trusted/exempt. [read_set.py:121](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:121), [158](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:158). |
| Warm engine cache hides table reads | **FIXED for the exercised cache** | Cache-clearing test passes; real fresh subprocess emitted the 45 reads. [read_set.py:61](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:61). |
| `usage` imported after routing escapes bundle paths | **FIXED for the old escape** | Import/routing test and full restoration test pass. Fresh child import audit is described in C. [read_set.py:70](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:70). |
| Arbitrary zero hash for an `outputs/` read | **FIXED through the harness** | Output-hash checks, final read-set reconciliation and pre-freeze verification remain; tests pass. [read_set.py:412](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:412), [run_forward_v1.py:1125](/Users/jw115/mlb-model-fwd6/nfl/sim/run_forward_v1.py:1125). |
| Missing mandatory QB input | **FIXED** | Required-input checks pass; freshness is now required too, for 14 mandatory bundle files total. [read_set.py:45](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:45). |

The earlier NumPy `fromfile` call that raised `UnsupportedOperation('fileno')` was never a successful bypass and remains excluded from the claimed successes.

### All 28 audit-#10 D operators

Each operator ran alone in an external copy, with the altered source's experiment hash re-stamped. Tests used the full forward list, `test_fwd6c.py` first, isolated temporary directories, plugin autoload disabled and stop-on-first-failure. **23 were killed; five survived.** Every survivor completed **201 passed, 2 skipped, exit 0**. “FIXED” here is a verdict on detection of that operator, not all behavior of the function.

| # | Operator and current file:line | Verdict | First distinguishing test / result |
|---|---|---|---|
| 1 | Omit restoration of `usage.PBP_DIR`; [read_set.py:61](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:61) | **FIXED** | `test_route_inputs_restores_every_routed_path` |
| 2 | Default decoding to replacement; [read_set.py:100](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:100) | **FIXED** | `test_text_reads_without_errors_policy_raise_like_open` |
| 3 | Omit user-site prefix; [read_set.py:121](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:121) | **NOT FIXED** | Survives; acknowledged exception. |
| 4 | Exempt all CSV files; [read_set.py:154](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:154) | **FIXED** | `test_csv_files_are_data` |
| 5 | Ignore string-mode audit opens; [read_set.py:182](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:182) | **FIXED** | `test_os_open_rdwr_is_a_violation_and_audit_reads_are_unproven` |
| 6 | Never record changed-read conflict; [read_set.py:219](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:219) | **FIXED** | `test_conflicting_rereads_and_network_attempts_are_rejected` |
| 7 | Load only first 16 MiB; [read_set.py:231](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:231) | **FIXED** | `test_parquetfile_and_large_reads_hash_the_delivered_bytes` |
| 8 | Wrapped CSV reader drops first row; [read_set.py:334](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:334) | **NOT FIXED** | Survives. Test checks row count after uninstalling wrapper. |
| 9 | Wrong hash for update-mode open; [read_set.py:280](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:280) | **FIXED, adapted site** | Old allowed-update branch is gone. Restoring the real handle plus wrong recorded bytes fails `test_update_mode_open_is_refused_and_rejected`. |
| 10 | Wrong hash for ParquetFile; [read_set.py:298](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:298) | **FIXED** | `test_parquetfile_and_large_reads_hash_the_delivered_bytes` |
| 11 | Leave `io.open` patched; [read_set.py:349](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:349) | **FIXED** | `test_uninstall_restores_every_api_even_after_an_exception` |
| 12 | Ignore network attempts; [read_set.py:381](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:381) | **FIXED** | `test_conflicting_rereads_and_network_attempts_are_rejected` |
| 13 | Worker identity week+1; [run_week.py:931](/Users/jw115/mlb-model-fwd6/nfl/sim/run_week.py:931) | **FIXED** | `test_real_worker_outputs_pass_parent_validation` |
| 14 | Worker cutoff 1900; [run_week.py:986](/Users/jw115/mlb-model-fwd6/nfl/sim/run_week.py:986) | **FIXED** | Same real-worker/parent test. |
| 15 | Worst unit becomes best unit; [run_forward_v1.py:155](/Users/jw115/mlb-model-fwd6/nfl/sim/run_forward_v1.py:155) | **FIXED** | `test_required_rating_units_by_name_and_worst_unit` |
| 16 | Omit schedule-season filter; [run_forward_v1.py:215](/Users/jw115/mlb-model-fwd6/nfl/sim/run_forward_v1.py:215) | **FIXED** | `test_schedule_from_other_seasons_is_filtered` |
| 17 | Permit 120-minute schedule discrepancy; [run_forward_v1.py:236](/Users/jw115/mlb-model-fwd6/nfl/sim/run_forward_v1.py:236) | **FIXED** | `test_schedule_tolerance_is_exactly_sixty_minutes` |
| 18 | Completed counts become `{}`; [run_forward_v1.py:421](/Users/jw115/mlb-model-fwd6/nfl/sim/run_forward_v1.py:421) | **FIXED** | `test_pbp_replaced_mid_build_cannot_mix_versions` |
| 19 | Finalize despite vanished original file; [run_forward_v1.py:488](/Users/jw115/mlb-model-fwd6/nfl/sim/run_forward_v1.py:488) | **FIXED** | `test_finalisation_halts_on_a_vanished_listed_file` |
| 20 | Overwrite conflicting archived receipt; [run_forward_v1.py:529](/Users/jw115/mlb-model-fwd6/nfl/sim/run_forward_v1.py:529) | **FIXED** | `test_conflicting_archived_receipt_is_refused_and_kept` |
| 21 | Ignore invocation season; [run_forward_v1.py:806](/Users/jw115/mlb-model-fwd6/nfl/sim/run_forward_v1.py:806) | **FIXED** | `test_invocation_cutoff_or_bundle_not_the_bundles_halts` |
| 22 | Worker timeout 7200→1 second; [run_forward_v1.py:946](/Users/jw115/mlb-model-fwd6/nfl/sim/run_forward_v1.py:946) | **FIXED** | `test_default_worker_timeout_is_two_hours` |
| 23 | Mark live receipt pilot; [run_forward_v1.py:952](/Users/jw115/mlb-model-fwd6/nfl/sim/run_forward_v1.py:952) | **FIXED** | `test_live_freeze_records_pilot_false_everywhere` |
| 24 | Restore SHA covers only 16 MiB; [restore_run.py:29](/Users/jw115/mlb-model-fwd6/nfl/sim/restore_run.py:29) | **NOT FIXED** | Survives; recorder's large-read test does not test recovery hashing. |
| 25 | Install corrupt archive object; [restore_run.py:33](/Users/jw115/mlb-model-fwd6/nfl/sim/restore_run.py:33) | **FIXED** | `test_corrupt_archive_object_is_not_installed` |
| 26 | `find_receipt` accepts first duplicate; [restore_run.py:49](/Users/jw115/mlb-model-fwd6/nfl/sim/restore_run.py:49) | **NOT FIXED** | Survives; later CLI status check still rejects duplicates. |
| 27 | Omit restored opinions entry; [restore_run.py:68](/Users/jw115/mlb-model-fwd6/nfl/sim/restore_run.py:68) | **FIXED** | `test_restore_reports_a_tampered_manifest_entry_and_exits_nonzero` catches this operator first. Exact rebuilt-entry test also exists. |
| 28 | CLI assumes status complete; [restore_run.py:139](/Users/jw115/mlb-model-fwd6/nfl/sim/restore_run.py:139) | **NOT FIXED** | Survives; current duplicate fixture exits in `find_receipt` before reaching this check. |

The two duplicate/status mutants illustrate a real test problem: either guard can fail while the other makes the same fixture raise. A broad `raises(SystemExit)` does not establish which contract was exercised. Likewise, [test_fwd6c.py:282](/Users/jw115/mlb-model-fwd6/nfl/sim/tests/test_fwd6c.py:282) discards the wrapped CSV result, then line 284 checks a fresh read after `_recorded` uninstalls the recorder. Capture and assert the result obtained while recording.

### D263–D265 and committed acceptance evidence, independently checked

| Claim | Verdict | My result / limit |
|---|---|---|
| Parent `main` no longer imports/runs pytest; child environment removes the two pytest variables | **HOLDS narrowly** | Source inspection plus hostile-plugin execution. It does not imply controlled Python startup; A1 refutes that larger claim. |
| Report requires exactly the four named passing cases | **HOLDS as a parser predicate** | Current code rejects missing, skipped, errored, failed and extra cases; an independently added duplicate name also halted. Fake trusted-looking report is still accepted because its producer is uncontrolled. |
| `r+` and `os.open(O_RDWR)` are both immediately refused | **FAILS as written in D263** | `r+` raises. `O_RDWR` returns a handle and consumed 0.99; its violation/audit entry causes eventual classification failure. The brief's narrower “O_RDWR is a violation” holds. |
| `via` is the union of mechanisms; missing/audit/mixed provenance and violations are rejected | **HOLDS for recorded events** | Persisted values and classifier verified. Wrapper followed by raw FileIO becomes `['audit','wrapper']` and halts. Dropping union updates is nevertheless a new survivor in D. |
| Listed native path readers are refused | **PARTIAL** | Ordinary paths are refused; supported native URI/bytes forms escape. A3. |
| Static scan covers EVERY hashed non-test module and closes native gaps | **FAILS literally / insufficient as a proof** | It expressly excludes `read_set.py` at test line 610. Its regex misses `LocalFileSystem().open_input_file`, aliases and dynamic lookup. Excluding the implementation of the guards is understandable; claiming exhaustive coverage is not. |
| Arbitrary `.py` data is no longer excluded | **HOLDS for the former suffix bypass** | Numeric external `.py` was recorded. Source-path membership is not loaded-code attestation; A2. Installation/pseudo-file exemptions still exist. |
| PBP counts, last-played weeks and source SHA use one snapshot | **HOLDS at this pin** | Source and replacement probes agree; actual archived PBP was **3,727,049 bytes**, hash-valid, and independently reproduced both committed derived fields. New last-played mutation survives tests, but unmodified code uses the snapshot correctly. |
| Cutoff/bundle validation, mandatory freshness, real worker→parent test | **HOLDS for current code** | Executed bad-invocation halts and actual-worker validation; wrong-week/wrong-cutoff mutations killed. Weaker comparisons survive in D. |
| Rating-unit names and worst required week | **HOLDS** | Substitution and stale-unit checks, plus killed best-unit mutation. Extras are ignored rather than allowed to replace a required unit. |
| Recovery index and bad-entry fixes | **HOLDS through those entry points** | Wrong ID halted; tampered existing entry gave exit 1. Status helper remains narrower than “all metadata complete.” |
| Every old freeze-side mutation except user-site is killed | **FAILS** | **23/28** old operators killed overall; **5 survive**, including the freeze-side CSV-row-loss operator in addition to the acknowledged user-site case. The three remaining recovery survivors are separately identified above. |
| All 51 manifest hashes match; logger/physics freeze unchanged | **HOLDS for file identity** | **51/51**, zero mismatches. Logger SHA above. Production `nfl/sim` files and experiment manifest are byte-identical between this pin and its immediate parent; the pin adds pilot records. This proves source identity, not execution identity. |
| Mac forward suite: 203 passed | **NOT REPRODUCED as 203 passes** | My result is **201 passed + 2 skipped**, zero failed, in each UTF-8 mode. External-data availability explains the difference; it does not falsify a past run that had those files. Linux history is unverified here. |
| Committed read set: 45 wrapper entries, no violations/conflicts/network, freshness included | **HOLDS as a record** | **45**, all `['wrapper']`; each of the three problem lists empty; freshness present. An empty list alone cannot prove absence of invisible reads. |
| Invocation cutoff equals bundle cutoff | **HOLDS** | Both normalize to **2026-09-27T16:55:00+00:00**. |
| Old/new pilot inputs are identical | **HOLDS for common prediction-input snapshots** | **15/15** common `inputs/*`, props and lines hashes match, including schedule. Run metadata intentionally differs and is not counted as identical input content. |
| Picks probabilities unchanged over 1,218 legs | **HOLDS** | One-to-one key match, **1,218 vs 1,218**, max absolute difference **0.0**, identical NaN masks and identical probability bytes after key sorting. |
| Frozen probabilities unchanged over 989 rows; zero tag/side changes | **HOLDS** | One-to-one keys, **989 vs 989**, max difference **0.0**, identical probability bytes; **0 tag differences and 0 `side` differences**. This is probability/label identity, not whole-file identity with changed run metadata. |
| Frozen SHA matches receipt | **HOLDS** | Full SHA **`5fd23d390003ff967ca7a5fcddb30f46840b4ea8b7f9bacd8e2021fcd6f08a24`**. |
| Refused rerun and archive restore | **HOLDS in independent re-execution** | Existing `20260927T165500Z` refused immediately. Restoring that run from the actual archive into an empty external tree restored **31 components**, unavailable **0**, verification errors **0**, complete receipt and the same frozen SHA. All **26** bundle-manifest CAS objects existed and hashed correctly. |

The committed tree alone lacks three listed pilot inputs: `depth_charts.parquet`, `player_usage_weekly.parquet`, and `rosters_weekly.parquet`. I retrieved them by hash from the actual read-only local archive during the external restore; I did not infer their contents. A user possessing only the public checkout still needs those archive objects to reproduce the whole pilot.

The acceptance note's M01–M17 protection-removal claims were also rerun as behavioral equivalents in re-stamped external copies. **All 17 were killed by the corresponding FWD6c tests**, including counts-from-shared after the strengthened refresh test. That narrower matrix can hold while the old CSV mutation and the new mutations survive. Two initial patch attempts used obsolete source text and did not apply; corrected executed runs, not those setup errors, are counted. D265's account of the 08:45Z auto-job/rebase incident is operational history I did not independently establish from logs or reflogs; it is not evidence for the integrity of a future launch.

## (C) Remaining bypasses and Thursday's run

### What can reach the solver or frozen file without the claimed byte evidence

| Executed route | Result | What it establishes |
|---|---|---|
| `sitecustomize` changes parent logger | Worker 0.62 → frozen 0.97; checks and receipt pass | The read set cannot certify the downstream writer; uncontrolled parent startup defeats source-only checks. |
| Timestamp-valid modified logger `.pyc` | Same 0.62 → 0.97 with unchanged hashed source and `-B` | File hashes do not identify executed project code under ordinary cache loading. |
| `dataset(file_uri)` | 0.99, no entry/violation; complete mandatory proof still passes | A supposedly refused native reader remains an invisible input route. |
| `memory_map(bytes_path)` | Bytes returned, no entry/violation | Recognized source-type check is incomplete. |
| `ParquetFile(file_uri)` | 0.99, no entry/violation | Wrapper silently hands unsupported path form to native code. |
| `pyarrow.fs.LocalFileSystem().open_input_file(path)` | Bytes returned, no entry/violation | A native filesystem reader is absent from both runtime refusal list and regex. |
| `pd.read_parquet(native_filesystem_handle)` | 0.99, no entry/violation | A permitted high-level reader does not establish provenance for an opaque native source. |
| `orig_map = pa.memory_map` captured before install, then `orig_map(path)` | Bytes returned, no entry/violation | Replacing a module attribute does not replace saved native aliases. |
| `pa.OSFile(path, 'r').read()` | Bytes returned, no entry/violation | The explicitly acknowledged native limit is real; it requires a trusted-code boundary, not an empty read-set list. |

`ParquetDataset(file_uri)` was **not** a successful bypass in my environment: it eventually passed a normalized local path into the guarded dataset function and raised PermissionError. Do not generalize every URI test into a success. Likewise, ordinary native string paths and external numeric `.py` data were correctly blocked/recorded as described in B.

I found no evidence that the unchanged worker used these native routes in the replay. The conclusion is narrower: the current claim that accepted records certify all input bytes is false for these supported calls, and the current code-origin checks cannot exclude altered code using them. Arbitrary native extensions remain beyond a Python interception layer. A scoped trusted-dependency boundary is necessary even after fixing the demonstrated argument forms.

### `hashed_code_paths` versus actual imports

I ran a fresh worker subprocess on the copied Thursday bundle and inspected its loaded repository modules after execution. **14 repository module entries** were observed, including package initializers, `run_week`, `read_set`, `usage`, `run_forward_v1`, and the frozen simulation modules. **All 14 file paths were listed by the manifest; zero observed repository module paths were unlisted.** This is an observation of that execution, not proof that every possible dynamic import is listed or that source equals loaded bytecode.

`run_week.py` imports modules before recorder installation at [run_week.py:968](/Users/jw115/mlb-model-fwd6/nfl/sim/run_week.py:968). `hashed_code_paths` constructs a set from manifest names; hash validation is separate. The recorder exempts those names and installation paths, rather than measuring Python's loaded code objects. In a fresh child with `usage.py` deliberately omitted from the allowed set, importing it while routing produced an audit-only entry for `usage.py`; in the full in-process test suite, the omission mutation survived because import state can already be warm. Test fresh process startup when testing import coverage.

My ordinary audit environment had no `PYTHON*` environment overrides and no loaded `sitecustomize`/`usercustomize` at the inspection point. Installed `.pth` files included an executable distutils setup line and an editable-project path entry. I do not claim either currently changes predictions. The controlled fault injections establish capability and missing isolation, not a diagnosis that the Mac is compromised.

### Thursday walkthrough at the pin

1. **Cutoff and quotes.** A live run sets T from the current UTC clock before the gate. At the proposed 23:30Z start, a 22:00Z props pull would be 90 minutes old and a 23:00Z lines pull 30 minutes old. Independent no-override fixtures accepted **90 and 180 minutes**, and rejected **181 minutes**. Thus the stated pull schedule fits the three-hour rule if the actual event-level rows arrive. I cannot verify a future VM pull. A stale-quote override is permitted only with pilot/dry-run; it must not be used to qualify a primary freeze. [run_forward_v1.py:975](/Users/jw115/mlb-model-fwd6/nfl/sim/run_forward_v1.py:975).
2. **Schedule identity.** I copied the Mac's local, uncommitted FWD6c dry-run bundle `20261001T120840Z` into `/private/tmp` and executed only pinned source against it. Its events/schedule map PIT@CLE to **`2026_04_PIT_CLE`**, with Thursday **20:15 America/New_York = Friday 2026-10-02 00:15Z**. It contained **1 event, 67 props rows and 6 game-line rows**. This verifies the bundle's mapping, not an independent external league schedule. The 60/61-minute and mixed-season tests pass.
3. **Consumed freshness.** For both CLE and PIT, last played was **week 3**; team ratings, tendencies and situational tendencies were **week 4**; usage, active universe, kicker and QB were **week 3**. The copied consumed inputs passed the per-team thresholds. This does not pre-certify refreshed inputs at 23:30Z; the real run must repeat the same validation.
4. **Gate on this Mac.** The unmodified subprocess gate passed in **1.40 seconds** using the same Python 3.13.1 executable as the harness. Pytest was importable by that executable. Source sets **600 seconds**; a timeout aborts before bundle construction, rather than authorizing publication. I did not wait 600 seconds or prove the OS/interpreter can never hang or fail. A future missing pytest, startup side effect or dependency change can still fail; A1 controls the preventable import ambiguity. The gate's ten-hour-timeout mutation survives tests, so its configured bound lacks a regression assertion.
5. **Real worker and parent validation.** The fresh subprocess completed in about **34 seconds**, exit 0, **one game converged**. It emitted **45 wrapper-only read entries: 14 bundle files plus 31 manifest-listed repository data files**; violations, conflicts and network attempts were all zero. The classifier and real output validator passed. Its **90 pick rows** had identical keys and bit-identical `cal_p` to the copied Mac dry-run output, max difference **0.0**. Sheet construction produced **70 rows, 43 two-way rows, 11 matched `sim_v1`, 59 `no_view`**. These are dry-run counts, not promises about tonight's quotes.
6. **Freeze and receipt.** The logger's source SHA remains unchanged, but A1/A2 show why that alone is insufficient. Current source checks pre-write time, verifies the finalized bundle and quarantines a write completed after kickoff. A primary must finish with `pilot=False`, a matching frozen SHA/publication record/receipt, archived objects and no unavailable or mismatching components. The restored historical pilot had the expected 989 rows and full SHA above; its receipt correctly says `pilot=True`, with actual publication on October 1, not a retroactive September primary.

This is a viable path to another **pilot** at the current pin. Primary requires the three A fixes and their acceptance evidence before the stated merge cutoff. Scoring definitions and S1–S4/FWD7 remain separate pre-outcome work; a clean freeze neither implements those rules nor resolves a false completeness claim.

## (D) Surviving mutations

### The five old survivors

These remain **NOT FIXED as test gaps**: user-site prefix omission, CSV first-row loss, recovery SHA truncation at 16 MiB, duplicate acceptance in `find_receipt`, and unconditional complete status in the recovery CLI. Their exact locations/results are B rows 3, 8, 24, 26 and 28. Replacing CSV parsing with first-row loss is substantive; I did not count redundant removal of one wrapper as a coverage failure.

### Ten new FWD6c survivors

Each ran separately against the full forward suite with its source manifest re-stamped and completed **201 passed, 2 skipped, exit 0**. These are additional to the 28 old operators. Several deliberately weaken currently correct guards; they must not be presented as existing defects in those guards.

| Operator / location | Surviving change | Concrete missing test |
|---|---|---|
| N1 — [read_set.py:91](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:91), `hashed_code_paths` | Omit `usage.py` from allowed code | Fresh child must import routed modules after constructing its allowlist, and assert the actual import boundary. The fresh-child probe produced an audit-only `usage.py` entry when omitted. |
| N2 — [read_set.py:149](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:149), `_code_source` | Remove `.pyc`→source mapping | Exercise a legitimate existing project cache as well as A2's altered cache. Current clean/no-cache tests do not distinguish the branch. If A2's fix deliberately makes caches unreachable, remove or explicitly retire this branch instead of preserving unneeded trust. |
| N3 — [read_set.py:227](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:227), `_record` | Stop adding later mechanisms to `via` | Record a file through wrapper, then raw read-only FileIO with identical bytes. Executed: current code records wrapper+audit and halts; mutant retains wrapper only and **accepts** the otherwise complete proof. |
| N4 — [read_set.py:306](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:306), `_refuse_paths` | Inspect only positional arguments, ignore keywords | Call native readers with `source=`, `path=`, `where=` where supported, and require the same refusal as positional calls. Existing exercised cases are positional. |
| N5 — [run_forward_v1.py:906](/Users/jw115/mlb-model-fwd6/nfl/sim/run_forward_v1.py:906), `check_gate_report` | Deduplicate testcase names before comparison | Add a fifth case repeating one expected name. Executed: current parser halts; mutant accepts. Existing extra-case fixture uses a different name. |
| N6 — [run_forward_v1.py:923](/Users/jw115/mlb-model-fwd6/nfl/sim/run_forward_v1.py:923), `run_freeze_gate` | Timeout 600→36,000 seconds | Assert the configured gate timeout and inject timeout failure before any bundle/publication side effect. The existing test observes command/environment but not the bound. |
| N7 — [run_forward_v1.py:924](/Users/jw115/mlb-model-fwd6/nfl/sim/run_forward_v1.py:924), `run_freeze_gate` | Ignore nonzero subprocess status when XML exists | Return valid-looking four-pass XML alongside nonzero exit. Require halt even though the report parses. |
| N8 — [run_forward_v1.py:863](/Users/jw115/mlb-model-fwd6/nfl/sim/run_forward_v1.py:863), `_validate_outputs` | Compare cutoff dates only | Executed same-day 00:00Z claim against bundle **12:08:40.026256Z**: current code halts; mutant accepts. Existing 1900 fixture cannot distinguish date-only comparison. |
| N9 — [run_forward_v1.py:866](/Users/jw115/mlb-model-fwd6/nfl/sim/run_forward_v1.py:866), `_validate_outputs` | Compare bundle basename only | Executed two different absolute paths ending in `bundle`: current code halts; mutant accepts. Existing `/wrong/bundle` fixture also changes the basename. |
| N10 — [run_forward_v1.py:422](/Users/jw115/mlb-model-fwd6/nfl/sim/run_forward_v1.py:422), `build_bundle` | Compute last-played weeks from shared PBP, while counts/SHA use snapshot | Refresh must change the last-played week, not only add game IDs within the same week. Current test's duplicate games change counts but leave the latest week unchanged, so its last-week assertion cannot detect this mutant. Executed with another completed preceding-week game retained: current code stored KC/CAR last week **2**, matching the archive; the mutant stored **1** for both while its archived source still recomputed **2**, and bundle construction passed. The first probe removed every week-2 game and correctly hit the global completion guard; it was not counted as a mixed-source success. |

Close the acceptance-counterexample coverage with the production repairs. The remaining coverage work can be prioritized by exercised paths: provenance mechanism union and same-day/same-name invocation cases first; recovery large-object and status cases before recovery is used for scoring. Killing these particular operators will still not establish exhaustive coverage.

### Reproduction records

All scripts and outputs below are outside the repositories and were retained in the local temporary directory. They are audit evidence, not committed production artifacts.

- Baselines: `/private/tmp/audit11-baseline-0.txt`, `/private/tmp/audit11-baseline-1.txt`.
- Old counterexamples/recovery: `/private/tmp/audit11_retests.py`, `/private/tmp/audit11-retests.txt`.
- Startup/fake gate: `/private/tmp/audit11_startup_probe.py`, `/private/tmp/audit11-startup.txt`; `.pth`: `/private/tmp/audit11_pth_probe.py`, `/private/tmp/audit11-pth.txt`.
- Bytecode: `/private/tmp/audit11_bytecode_probe.py`, `/private/tmp/audit11-bytecode.txt`.
- Native readers/classification: `/private/tmp/audit11_native_probe.py`, `/private/tmp/audit11-native.txt`.
- Committed evidence: `/private/tmp/audit11_recompute.py`, `/private/tmp/audit11-recompute.txt`; the side comparison used the actual `side` column separately from the initial script's column-name inspection.
- Real Thursday worker: `/private/tmp/audit11_live_probe.py`, `/private/tmp/audit11-live.txt`; import observation: `/private/tmp/audit11_import_probe.py`, `/private/tmp/audit11-imports.txt`.
- Feasible controlled gate: `/private/tmp/audit11_clean_gate.py`, `/private/tmp/audit11-clean-gate.txt`.
- Old 28 mutations: `/private/tmp/audit11_mutations.py`, `/private/tmp/audit11-mutations.txt`.
- New ten: `/private/tmp/audit11_new_mutations.py`, `/private/tmp/audit11-new-mutations.txt`.
- Acceptance M01–M17 equivalents: `/private/tmp/audit11_verifier_mutations.py`, `/private/tmp/audit11-verifier-mutations.txt`, corrected M12/M13 runs in `/private/tmp/audit11_verifier_corrections.py` and `/private/tmp/audit11-verifier-corrections.txt`.
- Additional discriminating examples and existing-run refusal: `/private/tmp/audit11_final_probes.py`, `/private/tmp/audit11-final-probes.txt`.
- Per-operator pytest output: `/private/tmp/audit11-mut-<operator>.txt`. Prefixes `S_`, `N_` and `V` identify old, new and acceptance-equivalent operators respectively.

## (E) Verdict

**NO-GO — TNF on aba96dfc3 must remain a pilot; primary requires A1–A3 fixed, re-stamped, independently verified and merged by Thu 2026-10-01 15:00Z.**
