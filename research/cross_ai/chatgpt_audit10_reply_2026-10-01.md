# ChatGPT audit #10 reply — FWD6b on eng/fwd6 (2026-10-01)
cf7c89909611337baaf80c2d5af776d0225d19e3

Audited the commit above, obtained with `git rev-parse HEAD` on `eng/fwd6`. Production code and the experiment manifest are identical to `b7d482a57`. All 51 experiment-manifest file hashes match. Tests, fault injections, mutations, freezes and recoveries ran in copies under `/private/tmp`; the actual checkout and actual archive were read-only. This reply is the sole authorized checkout write.

The independent runtime was macOS arm64, Python 3.13.1, pandas 2.3.3, NumPy 2.4.3. The clean commit-derived copy produced **168 passed, 2 skipped, zero failed in each UTF-8 mode**, with plugin autoload disabled. The two settlement tests need external 2026 snap/crosswalk data; they skipped. That is not 170 passes, and I have not independently run Linux. Physics, fitting and calibration quality remain outside this audit. I inspected dependency reads and executed the frozen worker, without reviewing or changing those algorithms.

The labels below distinguish executed counterexamples, source inspection and judgments about launch readiness. A mutation surviving tests is a coverage finding; it is not evidence that the unmodified function already contains that mutation.

## (A) Must fix before Thu 2026-10-01 15:00Z, ranked

### 1. Isolate the pytest gate from the process that constructs and freezes predictions — P1

**Location:** [run_forward_v1.py:911](/Users/jw115/mlb-model/nfl/sim/run_forward_v1.py:911), particularly `pytest.main(test_args, plugins=[])` at line 915; prediction filling at [line 1009](/Users/jw115/mlb-model/nfl/sim/run_forward_v1.py:1009).

**Executed counterexample.** I supplied a stand-in plugin through `PYTEST_PLUGINS`. Its `pytest_sessionfinish` hook replaced the already-imported harness's `fill_sheet` with a wrapper that changed matched `p_first` to 0.97. The four gate tests passed, the experiment hashes passed, and the real harness/pinned logger froze a fixture whose worker output said `cal_p=0.62` and whose frozen `sim_v1` row said `p_first=0.97`. `verify_bundle=[]`; `receipt_status='complete'`. No source file was altered. A first probe using 0.99 correctly hit the logger's probability-range guard; 0.97 passed it.

This directly refutes the acceptance note's “not a correctness defect.” It does **not** establish that seleniumbase or pytest_asyncio currently corrupt predictions. It establishes an uncontrolled execution path into the live writer; `plugins=[]` is not isolation, and file hashes do not validate in-memory function replacements. The probe used an explicit plugin, while ordinary entry-point plugins have the same in-process execution privilege.

**Minimum change:** run the gate in a fresh subprocess, with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, `PYTEST_PLUGINS` and `PYTEST_ADDOPTS` removed, controlled import paths, and only the four named freeze tests. Require all four to execute and pass; an exit code of zero alone can also describe skipped tests. Keep plugin code out of the parent. Re-stamp the changed harness and manifest before merging.

**Acceptance:** run the hostile plugin above through the normal launch environment; it must neither load into the parent nor change the frozen 0.62. Separately force a gate assertion failure and a skipped/deselected gate test: both must stop publication.

### 2. Stop certifying open-time hashes as hashes of consumed bytes — P1

**Locations:** [read_set.py:159](/Users/jw115/mlb-model/nfl/sim/read_set.py:159), [232](/Users/jw115/mlb-model/nfl/sim/read_set.py:232), [284](/Users/jw115/mlb-model/nfl/sim/read_set.py:284), [296](/Users/jw115/mlb-model/nfl/sim/read_set.py:296).

**Executed counterexample.** In an otherwise complete valid bundle/read set, a file initially contained `0.10`. Inside the installed recorder:

```python
with open(path, 'r+b', buffering=0) as f:
    f.write(b'0.99'); f.seek(0)
    used = f.read()
    f.seek(0); f.write(b'0.10')
```

The consumer got **`0.99`**. The recorded hash was SHA256 of **`0.10`**, `b4af9cbcd052a654a1a0298bffe1abc80d2ccd211031e89c4ee23d84bacd1d42`; the final file again contained `0.10`; conflicts were empty; **`classify_read_set` passed**. Worse, the in-memory entry said `via='wrapper'`. The `r+` branch hashes a separate snapshot and returns a real mutable file handle. Its test checks presence and the `wrapper` label, not byte identity.

The analogous `os.open(O_RDWR)` experiment also consumed 0.99 while recording 0.10. Native Arrow dataset and Arrow memory-map reads produced **zero entries**, and reading numeric data from an arbitrary external `.py` file also produced zero entries. Details are in C.

**Minimum change for this frozen pipeline:** reject update-mode input opens; fail closed on data reads that reach only the audit backstop; persist the actual provenance mechanism and require a byte-serving wrapper for accepted data reads. Explicitly reject or implement the demonstrated Arrow dataset/memory-map entry points. Restrict code exemptions to the pinned code/dependency boundary, rather than accepting any data file ending in `.py`. Do not describe the remaining Python interception layer as a sandbox against arbitrary native extensions.

**Acceptance:** the transient-byte examples and native/excluded-path examples must halt or record exactly the bytes delivered. Then rerun the real week-4 worker with persisted provenance: all 45 observed inputs must still classify. My independent unmodified-worker trace found **45 wrapper reads, zero audit-only entries**; these restrictions need not force the current workload onto an untested reader. Persisting `via` alone is insufficient because `r+` is currently mislabeled.

**Scope:** these are executed failures of the recorder's advertised guarantee. I did not find the unmodified solver currently using a native dataset reader or an `r+` prediction input, and I am not claiming that the saved pilot probabilities were corrupted through them.

### 3. Derive parent-process PBP metadata and its hash from one immutable snapshot — P2

**Location:** [run_forward_v1.py:409](/Users/jw115/mlb-model/nfl/sim/run_forward_v1.py:409), through line 415.

**Executed counterexample.** The harness reads the shared PBP separately for game counts, last-played weeks and the recorded SHA. I injected a source-file replacement immediately after `count_team_completed_games` returned. The bundled JSON contained `counts={'CAR':1,'KC':1}`; the source bytes matching its recorded SHA recomputed to `{'CAR':2,'KC':2}`. `verify_bundle=[]`. Both versions retained a completed preceding week, so freshness passed.

The worker does read the derived `team_game_counts.json` through the recorder; this is not a renewed CLI target bypass. The false statement is that the recorded PBP hash identifies the source used to derive that JSON. A concurrent source refresh can make the parent combine different versions. Counts feed board status; last-played weeks govern freshness eligibility.

**Minimum change:** read/copy the PBP bytes once, hash that snapshot, and compute both products from it. Archive the source snapshot or a content-addressed reference that recovery can actually retrieve. Use the same snapshot for both computations.

**Acceptance:** replace the shared PBP between the two computations. Both derived outputs and the recorded SHA must remain tied to the captured version, or the run must halt. Recomputing from the archived source must reproduce both fields.

### 4. Validate the cutoff actually claimed by the worker, and require its source read — P2

**Locations:** [run_forward_v1.py:830](/Users/jw115/mlb-model/nfl/sim/run_forward_v1.py:830); [read_set.py:45](/Users/jw115/mlb-model/nfl/sim/read_set.py:45); producer [run_week.py:991](/Users/jw115/mlb-model/nfl/sim/run_week.py:991).

**Executed counterexample.** After a stub worker produced valid outputs, I changed only `invocation.json` to claim cutoff `1900-01-01T00:00:00+00:00` and bundle `/wrong/bundle`. The real harness froze it, `verify_bundle=[]`, receipt complete. The parent's predicate checks lines, games, run ID, week and season, but neither cutoff nor bundle location. The accepted stub read set also omits `freshness.json`: it is not in `MUST_READ_BUNDLE`.

The real worker correctly reads the cutoff and rejects a conflicting `--as-of`; the defect is in independent validation of that behavior. The brief's broader claim “unless the invocation matches the bundle” is false.

**Minimum change:** require the `freshness.json` read and compare normalized cutoff to the immutable bundle cutoff. Validate bundle identity at execution time, using a portable run identity/digest as well as the resolved path; do not make restoring to another directory invalidate a historical record merely because its old absolute path differs.

**Acceptance:** wrong/missing cutoff, wrong live bundle identity and missing cutoff-source read must each halt. Include an end-to-end test using the real worker; the mutation that changes its emitted cutoff to 1900 currently passes the entire suite.

### 5. Test the required rating-unit names, not just a count of four — P2

**Location:** [run_forward_v1.py:174](/Users/jw115/mlb-model/nfl/sim/run_forward_v1.py:174), especially lines 175–178.

**Executed counterexample.** In a copy of the actual week-4 inputs, I renamed every CLE `pass_off` unit to `junk_unit`. `_team_freshness(..., 2026, 4, ['CLE'], {'CLE':3})` still returned `team_ratings=4` and passed, despite the required unit being absent. There are still four distinct strings, which is all the missing-unit check requires.

**Minimum change:** require `{pass_off, pass_def, rush_off, rush_def}` for each participating team, select the latest eligible row for each required unit, then take the worst selected week. Define whether extra labels are rejected or ignored; they cannot substitute for a required label.

**Acceptance:** replace each required label with an unknown label in turn, and test one stale unit alongside three fresh units. Both cases must halt. The actual untouched CLE/PIT inputs passed the correct week-4 thresholds; this is a demonstrated acceptance gap, not evidence that today's files contain `junk_unit`.

Recovery's false “complete” status also needs correction, described below. It can be repaired before recovery is relied on or any grading occurs: the correct metadata is already retained in the receipt. I do not make that repair alone a reason to lose an otherwise valid pre-kick capture.

## (B) Audit-#9 re-tests and verification of the brief

### Previous A counterexamples

| Audit #9 item | Verdict | Evidence at this pin |
|---|---|---|
| A1: changed consumed input was re-authorized by finalization | **FIXED for the original counterexample** | Changed input, direct finalization and tamper-between-finalization-and-freeze tests pass. Finalization preserves old hashes at [run_forward_v1.py:491](/Users/jw115/mlb-model/nfl/sim/run_forward_v1.py:491); final read-set classification at 1054 and pre-freeze verification at 1089 are present. Removing either new protection fails a targeted test. This does not cure C's transient-byte recorder failures. |
| A2: CLI total 38.0→38.5; inconsistent anchoring-log identity | **PARTIAL** | CLI lines/games are refused, real worker reads bundle targets, returned targets are checked, wrong/fractional identities halt. The +0.5 worker mutation is killed by `test_real_worker_reads_targets_from_bundle`. Relevant code: [run_week.py:961](/Users/jw115/mlb-model/nfl/sim/run_week.py:961), [run_forward_v1.py:810](/Users/jw115/mlb-model/nfl/sim/run_forward_v1.py:810), [845](/Users/jw115/mlb-model/nfl/sim/run_forward_v1.py:845). New cutoff/bundle-identity counterexample in A4 still freezes. |
| A3: only individual inputs recovered; missing manifest/publication/frozen file/receipt | **PARTIAL; original deletion scenario fixed** | Actual archive-only recovery of the new committed pilot into an empty tree restored 31 components, no unavailable objects or verification errors, correct frozen SHA, complete receipt. Existing bad opinions metadata is silently retained; see recovery subsection. [restore_run.py:62](/Users/jw115/mlb-model/nfl/sim/restore_run.py:62). |
| A4: no frozen schedule mapping | **FIXED for the original absence** | Schedule is snapshotted and mapped by week/home/away with a 60-minute check. Zero/duplicate matches halt. Actual PIT@CLE maps to `2026_04_PIT_CLE`, including the Thursday-ET/Friday-UTC conversion. [run_forward_v1.py:209](/Users/jw115/mlb-model/nfl/sim/run_forward_v1.py:209), [230](/Users/jw115/mlb-model/nfl/sim/run_forward_v1.py:230), [378](/Users/jw115/mlb-model/nfl/sim/run_forward_v1.py:378). Scorer-side S2 remains unimplemented. |
| A5: a future week concealed the stale row actually selected | **PARTIAL** | Eligible weeks are now restricted to `<= W`; stale-selected-week and genuinely missing-unit tests halt. Removing that restriction fails the new test. Required-label substitution still passes, and replacing worst-unit `min` with `max` survives the suite. [run_forward_v1.py:173](/Users/jw115/mlb-model/nfl/sim/run_forward_v1.py:173). |
| A6: missing gitignored roster broke a clean checkout's tests | **FIXED for forward fixtures** | Committed roster fixture is used by [_fwd_stub.py:20](/Users/jw115/mlb-model/nfl/sim/tests/_fwd_stub.py:20). Clean-source forward suite: 168 pass, two external-data settlement skips, no missing-roster failure. The broader wording “no test reads a gitignored file” is not a guarantee of self-contained tests: two still consult external snap/crosswalk sources. |

The original audit-#9 answer was not saved verbatim, and no verbatim answer is present in the supplied files. I cannot independently certify that Cowork's restatement is exhaustive or word-for-word faithful. I re-tested the six A items, the stated C mechanisms and all 17 D operators available in the audit record. D262's illustrative survivor list omits the separate injuries-copy operator; I explicitly tested it below. Its “among them” wording is not itself a false claim.

### Previous C bypasses

| Mechanism | Verdict | Executed/source evidence |
|---|---|---|
| `Path.read_text`, `Path.read_bytes`, `io.open` | **FIXED** | Reads appeared through byte-serving wrappers. UTF-8-on/off suites and decoding/newline comparison test pass. [read_set.py:239](/Users/jw115/mlb-model/nfl/sim/read_set.py:239), [259](/Users/jw115/mlb-model/nfl/sim/read_set.py:259). |
| `pyarrow.parquet.ParquetFile` | **FIXED for ordinary path reads** | It receives `BytesIO` of the recorded bytes. Independent read returned 0.99 with a matching entry. [read_set.py:246](/Users/jw115/mlb-model/nfl/sim/read_set.py:246). Its tests still miss a deliberately wrong hash, D below. |
| Previously captured pandas alias | **FIXED for the exercised `read_parquet` alias** | Underlying wrapped I/O recorded it. This is not a claim that every previously captured native reader is safe. |
| `os.open`, raw FileIO/captured file-open handles | **PARTIAL** | Audit hook records an open-time snapshot, not necessarily bytes subsequently read. Executed `os.open` transient-byte failure; raw handles share that source-level mechanism. [read_set.py:159](/Users/jw115/mlb-model/nfl/sim/read_set.py:159). |
| `r+` | **PARTIAL** | Ordinary read is recorded, but A2 proves the consumed-byte claim false even with `via='wrapper'`. [read_set.py:236](/Users/jw115/mlb-model/nfl/sim/read_set.py:236). |
| Arrow dataset/native mapping | **NOT FIXED** | `pyarrow.dataset.dataset(path).to_table()` and `pyarrow.memory_map(path).read()` returned data with no entry. |
| `site-packages-lookalike` path exclusion | **FIXED for the original substring bypass** | Real installation prefixes replace substring matching; fixture test passes. New unrestricted code-suffix exemption remains a separate hole. [read_set.py:111](/Users/jw115/mlb-model/nfl/sim/read_set.py:111), [130](/Users/jw115/mlb-model/nfl/sim/read_set.py:130). |
| Warm engine cache hid input reads | **FIXED for the exercised engine cache** | Cache is cleared; removing the clear fails `test_engine_cache_is_cleared_so_tables_are_recorded_every_run`. [read_set.py:72](/Users/jw115/mlb-model/nfl/sim/read_set.py:72). |
| `usage` imported after routing | **FIXED for the original path escape** | Imported before routing; removing routing fails its test. [read_set.py:70](/Users/jw115/mlb-model/nfl/sim/read_set.py:70), [82](/Users/jw115/mlb-model/nfl/sim/read_set.py:82). Undoing that route on exit is insufficiently tested. |
| Arbitrary zero hash under `outputs/` was accepted | **FIXED through the harness** | Wrong output SHA fails; final classification and final disk verification close the normal path. The classifier alone relies on a provided final manifest when present. [read_set.py:319](/Users/jw115/mlb-model/nfl/sim/read_set.py:319). |
| Missing mandatory QB read | **FIXED** | Ten required input reads, including QB; QB-removal mutation fails. [read_set.py:47](/Users/jw115/mlb-model/nfl/sim/read_set.py:47). Three other mandatory bundle reads exclude freshness, as A4 explains. |

The prior NumPy `fromfile` experiment that raised `UnsupportedOperation('fileno')` was not a successful bypass; I do not count it as one here.

### All 17 old D survivors re-tested

Each operator was applied alone in an external copy. A changed production file's experiment-manifest hash was re-stamped in that copy so a trivial hash rejection could not count as a kill. Tests ran with isolated temporary directories and plugin autoload disabled. Every row below is **FIXED as a test gap for that operator**. Labels follow this audit's operator order, not Cowork's shorter D01–D11 numbering.

| # | Old surviving operator | First failing test |
|---|---|---|
| 1 | Rename default archive directory | `test_default_archive_location` |
| 2 | Omit existing archive-object corruption check | `test_corrupt_archive_object_halts` |
| 3 | Line cutoff `<= T` becomes `< T` | `test_snapshot_exactly_at_cutoff_is_usable` |
| 4 | END GAME matching becomes case sensitive | `test_end_game_matching_is_case_insensitive` |
| 5 | Omit kicker freshness | `test_stale_kicker_halts` |
| 6 | Write a zero PBP source hash | `test_pbp_source_hash_recorded` |
| 7 | Skip final archive pass | `test_complete_run_record_restored_from_archive_alone` |
| 8 | Overwrite receipt registry instead of append | `test_two_freezes_append_two_receipts_and_duplicates_mismatch` |
| 9 | Load only the last receipt | Same test |
| 10 | Accept duplicate receipts | Same test |
| 11 | Skip `freshness.json` in bundle verification | `test_every_listed_bundle_file_is_verified` |
| 12 | Anchor boundary becomes strict `< 1` | `test_anchor_miss_exactly_one_is_anchored` |
| 13 | Coerce fractional output identity to integers | `test_fractional_identity_halts` |
| 14 | Shift worker total by +0.5 | `test_real_worker_reads_targets_from_bundle` |
| 15 | Write receipt row count 999999 | `test_receipt_rows_equal_frozen_rows` |
| 16 | Omit injuries from record-only copies | `test_depth_charts_and_injuries_are_copied_as_record` |
| 17 | Import shared logger on default-worker path | `test_real_default_worker_path_never_imports_shared_logger` |

For #14 the old CLI-only site no longer exists; I moved the same numerical perturbation to the real worker's conversion of bundle lines. Source locations are [run_forward_v1.py:49](/Users/jw115/mlb-model/nfl/sim/run_forward_v1.py:49), 56, 101, 130, 152, 415, 476, 509, 528, 535, 558, 743, 794, 856 and 1142; [run_week.py:1024](/Users/jw115/mlb-model/nfl/sim/run_week.py:1024); record-only file list at [run_forward_v1.py:46](/Users/jw115/mlb-model/nfl/sim/run_forward_v1.py:46).

### Recomputed verifier claims

These results come from files/code, not from accepting D260–D262 or the acceptance prose.

| Claim | Verdict and independent number |
|---|---|
| Code under test equals `b7d482a57`; experiment hashes match | **HOLDS:** no difference in `nfl/sim` or the experiment manifest; **51/51** listed hashes match. |
| Clean forward list is 170 passes in both UTF-8 modes | **NOT REPRODUCED:** **168 passed, 2 skipped, 0 failed** in both modes. Skips are `test_fwd2_settlement.py:162` and `:243`, external snap/crosswalk availability. The historical Linux/Mac 170-pass runs are not falsified by different data availability, but must not be reported as my result. |
| 32 of 39 new tests fail on old code | **HOLDS:** **32 failed, 7 passed** with the four production modules from `e826a30ae` and current tests/fixtures in an external copy. Some failures are missing-interface failures; this count does not establish depth of numerical coverage. |
| Cowork's 28 listed mutation protections are killed | **HOLDS for equivalent stated operators:** the 11 listed old operators plus 17 new ones fail tests. I ran the additional old operators too. My N16 is the +0.5 worker operator above. Exact unpublished mutation patches cannot be compared byte-for-byte. New survivors remain in D. |
| New pilot dimensions and matching | **HOLDS:** **14 events, 947 props, 84 line rows; 989 frozen rows, 625 two-way, 162 `sim_v1`, 827 `no_view`**. |
| New pilot read set | **HOLDS as recorded:** **45 entries, 0 conflicts, 0 network attempts**; **0 entries persist `via`**. “0 unproven” is a classifier result, not proof that no bypass exists. |
| Pilot anchors: all 14 anchored, largest miss about .37, 2–5 iterations | **HOLDS:** **14/14**, maximum absolute miss **0.3696**, iteration range **2–5**. |
| Old/new pilot inputs identical | **HOLDS for all 14 common input/props/lines manifest entries:** **0 mismatches**. New schedule, event identity and run metadata are separate. |
| 1,218 `cal_p` values unchanged | **HOLDS:** **1,218 one-to-one keys**, **0 maximum absolute difference**, matching NaN masks and **identical floating-point bytes after key sorting**. Key: game/player/family/line/side. |
| 989 frozen `p_first` values unchanged | **HOLDS:** **989 matching contract keys**, **0 maximum absolute difference**, matching NaN masks and **identical floating-point bytes after key sorting**; **0 tag differences, 0 side differences**. |
| Frozen SHA `a05a81fa…` | **HOLDS:** `a05a81fa9448aeada9e2252cadb70fbeb48f365a9ec65573765e06ddf38a1307`. Same after independent archive recovery. |
| A repeat pilot run ID is refused | **HOLDS:** `build_bundle` rejects the existing `20260927T165000Z` directory before rewriting it. Fixture suite also exercises repeated runs. |
| Full new-pilot recovery | **HOLDS for missing files:** actual Mac archive restored **31 components** into an empty destination, unavailable **0**, bundle mismatches **0**, receipt complete. Cowork's **29** counts manifest + 26 listed files + publication + frozen file; my extra two were the missing opinions-manifest entry and registry line. No numerical contradiction. Existing corrupted metadata is a separate failure below. |
| Real week-4 read set is 45 files | **HOLDS in independent worker replay:** **45 = 14 bundle files + 31 pinned repository files**, all observed via wrappers; classification passes. Replayed **90** pick rows match the saved dry-run `cal_p` bit-for-bit after key sorting. |
| The omitted `via` is cosmetic; plugins cannot affect correctness | **FAILS:** recorder and plugin counterexamples in A/C. |

The week-4 replay used a copied **local, uncommitted** dry-run bundle named `20261001T024812Z`, explicitly identified in the acceptance note. I verified its listed hashes and ran the worker from the pinned audit source. It is additional runtime evidence, not a claim that this bundle was committed. The week-3 comparisons used committed files. Three large new-pilot inputs were supplied by the actual archive using their pinned hashes.

### Thursday path at this pin — R4

1. **Cutoff and quote ages.** The live command captures wall-clock T when it starts. At 23:30Z, a 22:00Z props pull is **90 minutes** old; a 23:00Z line snapshot is **30 minutes** old. Both are below the per-row three-hour cap. Executed no-override bundle tests accept **90 and 180 minutes**, reject **181 minutes**. Exactly-T line snapshots are accepted. Live mode refuses `--allow-stale-quotes`; using it to compensate for a missed pull would require a pilot/dry run. I cannot verify a future 22:00Z pull. The saved dry run used stale-quote permission and is not evidence that the live freshness gate will pass. Locations: [run_forward_v1.py:339](/Users/jw115/mlb-model/nfl/sim/run_forward_v1.py:339), [902](/Users/jw115/mlb-model/nfl/sim/run_forward_v1.py:902).
2. **Event/time mapping.** The actual snapshot says gameday `2026-10-01`, gametime `20:15`, ET. `_map_events_to_schedule` maps it to `2026-10-02T00:15Z`, and returns **`2026_04_PIT_CLE`**. The event is 45 minutes after a 23:30Z cutoff, within the two-hour window. There is no Thursday/Friday off-by-one in the exercised code. A missing local schedule invokes nflreadpy before the worker; a fetch failure halts. A local snapshot takes precedence, even if old; a mismatch exceeding 60 minutes halts.
3. **Actual week-4 freshness.** Independently recomputed on the consumed copies: both CLE and PIT last played week **3**; team ratings, tendencies and situational tendencies select week **4**; usage, active universe, kickers and QB select week **3**. These pass the declared thresholds. Required-unit naming is the remaining defect in A5.
4. **Worker and matching.** Default execution supplies bundle paths/identity, and the worker reads its own targets. The replay recorded all ten required inputs, props, lines, events and freshness, plus 31 static files. It reproduced the saved dry-run probabilities. Its observed provenance does not cure the unrestricted plugin/reader paths demonstrated elsewhere.
5. **Logger/publication.** The harness calls `nfl.sim.fwd_v1_logger`, not the shared logger. Its SHA is `cf100675bd385ca5db3c36b25ff9c890e20aae0457f674fc9a2205c7b0557cbc`. Shared-import mutations are killed. Live pre-write and post-write kickoff checks remain: a late completion is quarantined and does not get a receipt. Then publication JSON, frozen file, registry line, per-run receipt index and registry snapshot are written/archived. A crash can leave a partial record; scoring must require completion and must not treat mere parquet existence as a primary freeze. [run_forward_v1.py:1083](/Users/jw115/mlb-model/nfl/sim/run_forward_v1.py:1083), [1098](/Users/jw115/mlb-model/nfl/sim/run_forward_v1.py:1098), [1149](/Users/jw115/mlb-model/nfl/sim/run_forward_v1.py:1149).

### Recovery boundaries — R5

**Verified recovery:** with neither a run directory nor a frozen file, opinions manifest or registry in the destination, `find_receipt` found the actual archive index for `20260927T165000Z`; `restore` rebuilt the new record, including all three uncommitted large inputs. All **26** listed run-file objects existed in the actual archive and matched their hashes. Thus “clean clone plus this intact archive cannot recover those three files” is false.

**Verified false success:** after that restore, I changed the copied opinions-manifest entry's SHA to 64 zeros and reran the actual restore CLI function. It restored nothing, printed `verify_bundle: clean` and `receipt_status: complete`, and returned normally (exit 0). The wrong entry remained. [restore_run.py:84](/Users/jw115/mlb-model/nfl/sim/restore_run.py:84) skips an existing filename without comparing the entry; [run_forward_v1.py:535](/Users/jw115/mlb-model/nfl/sim/run_forward_v1.py:535) never checks it. Compare the existing entry to the receipt's authoritative entry and halt on a discrepancy; do not silently overwrite evidence.

**Identity gap:** putting a valid receipt for `20260927T165000Z` under archive index `another-run.json` makes `find_receipt('another-run', ...)` return the other run's receipt. It does not check the requested ID against the payload. Validate that identity and its run-directory identity before recovery. This was a helper-level executed counterexample, not a claim that the actual archive index is wrong.

**Still outside recovery:** the archive does not replace the pinned source checkout, Python/library environment, or raw PBP source behind the derived metadata. It is not a full backup of all shared data. Unpublished dry runs have no per-run receipt index, so loss of both their directory/manifest and knowledge of the correct manifest hash prevents automatic `--run-id` bootstrap. Pre-D262 receipts without `run_dir` halt explicitly; they do not become new-format primary records by restoration. The Mac archive's lack of an independently verified second copy remains a loss risk; I could inspect the named archive, not establish whether another backup exists elsewhere.

### Brief §3 known limits

| Stated limit | Finding |
|---|---|
| Code is checked at run start, outside the read set | **CONFIRMED, with an overstated boundary.** Pinned repository files are checked; `.py`/`.pyc` and installation paths are omitted from recording. This does not cover arbitrary external plugins, arbitrary `.py` data files or in-memory replacement. A1 is a concrete counterexample. |
| Depth charts, injuries and schedule are record only | **CONFIRMED for worker consumption; qualify schedule.** None appeared among the real worker's 45 reads. The harness does consume schedule before simulation to admit events and write the ID mapping, so schedule is not irrelevant to experiment eligibility. |
| FWD7/S1–S4 are declared, not implemented; nothing scored | **Implementation claim confirmed at this pin.** D255 declares the separate scorer; the freeze harness does not implement its scoring contract. I found no pinned FWD7 confirmatory record. I cannot certify “nothing has been scored anywhere” from this checkout; the code contains older scoring facilities. S1–S4 must be implemented and tested before grading, using the pre-outcome declaration rather than outcomes to choose rules. |
| Old FWD3 `20260927T170000Z` has no inputs and cannot be restored | **PARTLY REFUTED.** At this exact commit it has **11 committed input files**, all matching the manifest; all 11 input hashes also exist in the archive. Source-tree `verify_bundle` is clean. Starting with only its committed manifest, archive restore recovered those **11 inputs** but lacked **11 other listed run files**. It also wrongly treated legacy `experiment_digest` and `bundle_digest` metadata as files, adding two spurious unavailable entries. There is no receipt for this run. Full archive-only new-format recovery is not available, but “no inputs” is false. It remains pilot/non-receipted evidence, excluded under declared S1; the presence of copied inputs does not prove the old worker consumed them. |
| Week-3 pilots are plumbing evidence, not out of sample | **CONFIRMED.** The committed new frozen rows are pilot; the later publication and retrospective inputs cannot establish prospective predictive performance. Identical probabilities validate a plumbing comparison only. |

## (C) Read-set bypasses and what the record proves

**Executed bypasses in the unmodified recorder:**

- **Native Arrow dataset:** a parquet containing 0.99 was read with `pyarrow.dataset.dataset(path).to_table()`; the recorder had **no entries**. This audit-#9 bypass remains.
- **Native Arrow memory map:** `pyarrow.memory_map(path).read()` returned the file bytes; **no entries**. A Python `mmap` constructed after `os.open` had only the earlier audit-open snapshot, which does not bind subsequent mapped reads.
- **Update/raw-handle timing:** the A2 `r+` probe passed full classification with a SHA for bytes different from `used`. The `os.open` version has the same open-time limitation. Raw FileIO and captured aliases can reach the audit hook too, so “only os.open should ever reach it” is not an enforced invariant.
- **Suffix exclusion:** `float(Path('/private/tmp/.../prediction_input.py').read_text())` returned **0.99**, with **no record**. No import happened. [read_set.py:138](/Users/jw115/mlb-model/nfl/sim/read_set.py:138) assumes the suffix implies pinned code; it never checks manifest membership.
- **Parent transformations:** A3 recorded a PBP SHA that cannot reproduce the stored counts. A1 showed an unpinned parent-process plugin altering the final probability outside the worker recorder altogether. The latter changes the frozen record after the solver; it is not a hidden numerical solver argument.

The old parent-supplied total/games route is closed in the default worker. No numerical line argument now bypasses the worker's file reads. Week/run identity still travels by CLI and is checked against the parent's expected identity. The cutoff comes from `freshness.json`, but is not independently required/validated at the proof boundary.

**`via` is consequential, not cosmetic.** [read_set.py:284](/Users/jw115/mlb-model/nfl/sim/read_set.py:284) strips it from persisted entries. The same path/hash/read-count tuple can represent either a parser served those exact bytes or an audit hook that took a separate snapshot. The transient-byte probe demonstrates why those cases cannot be treated as equivalent. Additionally, `_record` retains the first mechanism rather than an exhaustive history; persisting only that first label would still be too weak for mixed mechanisms. Record all mechanisms or a conservative “every read byte-bound” property, and enforce it.

**The four newly visible static tables.** I traced their actual read stacks during the independent full worker replay. For all four, the path was `build_board → _check_calibration_stamp → engine_fingerprint → Path.read_bytes`:

- `actual_close_games_2021_2024.parquet`
- `actual_late_drives_2021_2024.parquet`
- `actual_scoring_composition_2021_2024.parquet`
- `fourth_down_meta.json`

They were hashed for the calibration/engine-stamp check; they were not parsed into prediction parameters on this run. The fingerprint enumerates all files in the static tables directory ([calibration.py:389](/Users/jw115/mlb-model/nfl/sim/calibration.py:389)); the explicit table-loading paths do not consume these four numerically. They are provenance/gate dependencies. Keeping them immutable and repository-hashed is appropriate; they do not need weekly copies merely because the stronger recorder now sees the reads. If their role changes to current-week data, that would require a new input contract and re-stamp. I did not audit their statistical construction.

**Limit of the conclusion:** a read set proves properties of the reads it intercepts. It is not an independent proof that arbitrary native code, pre-existing descriptors or unpinned plugins did nothing else. The static API-string scan is a regression guard, not a proof about transitive C-extension behavior. The real workload replay supports the narrower observation “these 45 reads were byte-served by wrappers”; the broad claim “every possible input is proven” fails the executed counterexamples.

## (D) Surviving mutations

I found a surviving behavioral mutation for **each of 28 new/changed functions**, including the changed nested wrappers. Each row below was run against the full forward list: **168 passed, 2 skipped, exit 0**. The two skips were the same external-data skips as baseline. Each mutation was isolated in a copy and the affected experiment hash re-stamped, so this measures behavioral coverage rather than the fact that source hashes detect edits.

This does not mean each function is wrong today. Some mutations require a different input size, mixed-season data, a failed restore, or a real child process to exhibit their effect. Where another downstream guard can still reject the damage, I say so. A first candidate that merely removed the pandas CSV wrapper was redundant with lower-level recording; I replaced it with actual CSV row loss, rather than count redundant wrapping as a substantive defect.

### `read_set.py` — 12 functions

| Function / location | Surviving change | Missing assertion or scenario |
|---|---|---|
| [`route_inputs`:60](/Users/jw115/mlb-model/nfl/sim/read_set.py:60) | Do not save `usage.PBP_DIR` for restoration | Assert every routed module's original path returns after success and exceptions. |
| [`_text_like_open`:90](/Users/jw115/mlb-model/nfl/sim/read_set.py:90) | Default undecodable input to `errors='replace'` | Invalid bytes with no explicit error policy must raise just as ordinary `open` does. Existing test requests replacement explicitly. |
| [`_install_prefixes`:111](/Users/jw115/mlb-model/nfl/sim/read_set.py:111) | Omit the user-site installation directory | Exercise a real user-site path outside the remaining prefixes; otherwise this exclusion change is dormant. |
| [`_excluded`:130](/Users/jw115/mlb-model/nfl/sim/read_set.py:130) | Also exclude all `.csv` files | A data suffix must not create an exemption; test actual CSV input outside install directories. |
| [`_audit_open`:159](/Users/jw115/mlb-model/nfl/sim/read_set.py:159) | Ignore string-mode audit events; retain raw `os.open` flags | Exercise FileIO/captured open aliases, not only `os.open`. |
| [`_record`:190](/Users/jw115/mlb-model/nfl/sim/read_set.py:190) | Never append a changed-read conflict | Read two different byte strings through the same path and require conflict plus classifier rejection. |
| [`_load`:201](/Users/jw115/mlb-model/nfl/sim/read_set.py:201) | Read at most 16 MiB | Hash and parse an input larger than the cap, including a changed tail. |
| [`install`:209](/Users/jw115/mlb-model/nfl/sim/read_set.py:209) | Make wrapped `pd.read_csv` drop its first data row | Compare parsed CSV values/row count to ordinary parsing, not merely recording installation. |
| [`open_wrapper`:232](/Users/jw115/mlb-model/nfl/sim/read_set.py:232) | Record `b'wrong'` for `r+` opens | Existing test checks entry presence/`via`, not the SHA or subsequent bytes. |
| [`parquetfile_wrapper`:246](/Users/jw115/mlb-model/nfl/sim/read_set.py:246) | Record `b'wrong'` while parsing the actual parquet | Assert recorded SHA equals the delivered parquet bytes and test classification. |
| [`uninstall`:269](/Users/jw115/mlb-model/nfl/sim/read_set.py:269) | Leave `io.open` patched | Assert identity of all restored APIs, including after an exception. |
| [`classify_read_set`:296](/Users/jw115/mlb-model/nfl/sim/read_set.py:296) | Ignore nonempty `network_attempts` | Feed an otherwise valid read set with a captured/handled network attempt; it must reject even if execution continued. |

### `run_week.py`, forward mode — 2 functions

| Function / location | Surviving change | Missing assertion or scenario |
|---|---|---|
| [`main`:931](/Users/jw115/mlb-model/nfl/sim/run_week.py:931) | Emit `RUN_IDENTITY.week = requested_week + 1` | Real-worker tests stop at the solver or inspect targets/paths; stub-driven parent tests supply correct identities. Run the two together and inspect actual output rows. The intact parent should reject this mutation if exercised. |
| [`_main_body`:985](/Users/jw115/mlb-model/nfl/sim/run_week.py:985) | Write invocation cutoff `1900-01-01T00:00:00+00:00` | Validate the real worker's cutoff and parent rejection of an incorrect claim. A4 shows parent acceptance today. |

### `run_forward_v1.py` — 9 functions

| Function / location | Surviving change | Missing assertion or scenario |
|---|---|---|
| [`_team_freshness`:152](/Users/jw115/mlb-model/nfl/sim/run_forward_v1.py:152) | Worst-unit `min` becomes best-unit `max` | Keep three units fresh and one stale; entire run must halt. |
| [`_load_schedule`:209](/Users/jw115/mlb-model/nfl/sim/run_forward_v1.py:209) | Do not filter the requested season | Mixed-season snapshot with repeated matchup/week must not admit or obstruct the wrong season. |
| [`_map_events_to_schedule`:230](/Users/jw115/mlb-model/nfl/sim/run_forward_v1.py:230) | Permit 120 minutes instead of 60 | Test 60 minutes accepted and 61 minutes rejected; existing mismatch is too large to discriminate. |
| [`build_bundle`:257](/Users/jw115/mlb-model/nfl/sim/run_forward_v1.py:257) | Store `counts={}` instead of computing completed-game counts | Check actual count values, not just the source hash and freshness. |
| [`_finalize_bundle_manifest`:476](/Users/jw115/mlb-model/nfl/sim/run_forward_v1.py:476) | Do not halt on missing original files | Directly remove a listed file before finalization. Subsequent full verification may still reject; that redundancy does not test this function's promised behavior. |
| [`archive_receipt`:517](/Users/jw115/mlb-model/nfl/sim/run_forward_v1.py:517) | Overwrite a conflicting per-run index | Archive one receipt, try a different one with the same run ID, and verify refusal plus unchanged original bytes. |
| [`_validate_outputs`:794](/Users/jw115/mlb-model/nfl/sim/run_forward_v1.py:794) | Stop checking invocation season | Correct output-table identities with a wrong invocation season must halt. |
| [`_default_run_week`:856](/Users/jw115/mlb-model/nfl/sim/run_forward_v1.py:856) | Child timeout 7200 seconds becomes 1 second | Stub subprocess tests do not exercise realistic worker duration; my real replay took approximately 35 seconds. |
| [`main`:876](/Users/jw115/mlb-model/nfl/sim/run_forward_v1.py:876) | Every receipt says `pilot=True`, including a live freeze | End-to-end live success must assert consistency among CLI mode, frozen rows, bundle metadata and receipt. Most success fixtures are pilots. |

### `restore_run.py` — 5 functions

| Function / location | Surviving change | Missing assertion or scenario |
|---|---|---|
| [`_sha`:29](/Users/jw115/mlb-model/nfl/sim/restore_run.py:29) | Hash only the first 16 MiB | Large archive object with altered tail; valid large object must not be falsely rejected either. |
| [`_from_archive`:33](/Users/jw115/mlb-model/nfl/sim/restore_run.py:33) | Copy a corrupt archive object without checking its SHA | Assert corrupt source is not installed and is reported unavailable. Later bundle verification can detect many resulting corruptions; it does not test the copy guard. |
| [`find_receipt`:49](/Users/jw115/mlb-model/nfl/sim/restore_run.py:49) | Accept the first of duplicate registry receipts | Test duplicate receipts through this recovery entry point, not only `receipt_status`. |
| [`restore`:62](/Users/jw115/mlb-model/nfl/sim/restore_run.py:62) | Never restore the opinions-manifest entry | Inspect reconstructed entry equality. Existing “full record” test does not assert it, and “complete” does not imply it. |
| [`main`:100](/Users/jw115/mlb-model/nfl/sim/restore_run.py:100) | Print/assume `receipt_status='complete'` without checking | Exercise a restored record with a mismatching frozen publication/receipt; assert nonzero exit. Happy-path recovery cannot distinguish this mutant. |

The original 17 survivors and Cowork's 28 listed mutation protections being killed can therefore both be true while these **28 other operators** survive. Pass counts alone are not evidence of coverage of the functions' remaining failure modes.

### Reproduction records

All paths below are outside the checkout and contain the probes/results used above:

- Baselines: `/private/tmp/audit10-clean-0.txt`, `/private/tmp/audit10-clean-1.txt`.
- Old-code comparison: `/private/tmp/audit10-oldcode.txt`, `/private/tmp/audit10-oldcode-detail.txt`.
- Recorder and actual-archive restore: `/private/tmp/audit10_io_restore.py`, `/private/tmp/audit10-io-restore.txt`.
- Plugin counterexample: `/private/tmp/audit10_plugin_probe.py`, `/private/tmp/audit10-plugin.txt`.
- Cutoff, quote-age, CLI restore and bit comparisons: `/private/tmp/audit10_extra_probe.py`, `/private/tmp/audit10-extra.txt`.
- Parent PBP replacement: `/private/tmp/audit10_parent_probe.py`, `/private/tmp/audit10-parent.txt`.
- Real worker replay/provenance trace: `/private/tmp/audit10_live_probe.py`, `/private/tmp/audit10-live.txt`.
- Recomputed committed evidence: `/private/tmp/audit10_recompute.py`, `/private/tmp/audit10-recompute.txt`.
- Mutations: `/private/tmp/audit10_mutations.py`, `/private/tmp/audit10-mutations.txt`; supplemental CSV case `/private/tmp/audit10-mutation-extra.txt`; verifier operators `/private/tmp/audit10-verifier-mutations.txt` and corrected QB operator `/private/tmp/audit10-verifier-N13.txt`. Per-operator logs are `/private/tmp/audit10-mut-<operator>.txt`.

An initial baseline attempt wrongly shared a single test archive across concurrent fixtures and caused receipt-index collisions; it was discarded and is not counted as a repository failure. The retained baseline and mutation runs use isolated fixture archives. The first QB mutation patch failed to apply; only the corrected, executed operator counts. These controls matter because both setup failures and generic manifest rejection can masquerade as successful mutation detection.

## (E) Verdict

**NO-GO — TNF on this pin must be a pilot; primary status requires the ranked freeze-side fixes above, their counterexamples passing, and the re-stamped code independently verified and merged by Thu 2026-10-01 15:00Z.**
