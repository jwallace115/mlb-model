# ChatGPT audit #13 — FWD6e, completed assessment
5fabce877d465bc0096dbc9d7067c7a25a990b9e

**NO-GO for primary TNF at this pin.** The full-suite baseline is INCOMPLETE, and the registered dependency-drift rule has an ambiguity demonstrated by the HOME experiment. The requested audit attempts and the additional mutation checks are finished. This is not a finding that the unmodified simulation produced corrupted probabilities.

I read and executed a commit-derived extraction at `/private/tmp/nfl-audit13-5fabce877`, checked against the pinned worktree. All 52 experiment hashes match. Production `nfl/sim` files and the experiment manifest are unchanged between the code commit and this pin. Tests, mutations, dependency copies and restores were outside both repositories; the installed environment and real archive were read-only. This reply is the only repository file I wrote. Simulation physics, fitting, calibration quality and predictive merit were not audited.

## (A) Must resolve before a primary TNF, ranked

1. **Close the new-distribution gap in the registered rule.** [NFL_SIM_DECISION_v1.md:5412](/Users/jw115/mlb-model-fwd6/research/nfl_sim/NFL_SIM_DECISION_v1.md:5412) requires equality for distributions *in the first identity* that a later run loads. It does not explicitly reject a newly loaded distribution. The brief states the stronger rule “for any distribution it loads.”

   **Executed counterexample:** the temporary-HOME worker used the same Python version and executable as the synthetic primary. All 12 baseline distribution identities remained equal, but an additional `bottleneck` fixture loaded. The complete identity changed while the literal baseline-intersection predicate remained true. This demonstrates the rule gap, not a changed numerical result. D269's general sentence “a run that differs” could be intended to reject this; the operative predicate must make that unambiguous before implementation.

   **Concrete amendment:** define the baseline as the consistent union of `dependency_distributions` from all three first-primary runtimes. For every distribution loaded by any later runtime, require baseline membership and exact version/location/RECORD equality; also require matching Python and executable. A new name or mismatch excludes that run unless a decision recorded before its first kickoff accepts the change and names the accepted identity. Do not compare whole process identity hashes blindly: legitimate import sets differ between harness and worker. Evidence: `/private/tmp/audit13-L1-check.txt`.

2. **Obtain a completed full-forward-suite result before treating the baseline as independently cleared.** This is an audit evidence failure, not a located production defect. The relevant fault is in my runner: [audit13_baseline.py:8](/private/tmp/audit13_baseline.py:8) times out after 560 seconds, while [line 9](/private/tmp/audit13_baseline.py:9) saves output only after successful return. The attempt timed out; no final pass/fail/skip count was retained. I therefore cannot reproduce Cowork's “241 passed, zero skipped.”

   I did not rerun the full suite, honoring the one-attempt limit. A subsequent verification should stream output and finish bounded, nonoverlapping test groups with explicit totals and skip reasons. The 11-test control and successful production probe below do not replace that full baseline. Until this evidence exists, keep TNF pilot. Log: `/private/tmp/audit13-baselines.txt`.

These are the grounds for withholding primary clearance. The P2 coverage findings below are not additional demonstrated failures of tonight's unmodified computation.

## (B) P1 results

| Check, in requested order | Result and executed evidence |
|---|---|
| 1. Full baseline, once | **INCONCLUSIVE:** timeout at 560 seconds; final counts unavailable. No second full-suite attempt. Linux and standalone 3.13.7 were not independently run. |
| 2. Production-command primary | **PASS for the exercised fixture:** exact bootstrap command, exit 0 in **53.41 s**; `pilot=False`; **70 frozen rows, 11 matched**; reconstructed worker-to-frozen max probability difference **0.0**; all planted markers absent; **45 wrapper reads**, zero violations, bundle verification clean, receipt complete. |
| 3. Altered dependency | **PASS:** in a temporary venv with read-only base packages and isolated HOME, clean worker exit 0; one-byte Python change without RECORD update exit 1; one-byte copied vendored `.dylib` change exit 1; rewritten RECORD exit 0 with changed recorded identity. Rejected runs wrote no worker runtime. |
| 4. HOME/user site | **Detection PASS; exclusion rule needs A1.** An extra optional distribution loaded from the temporary user site. Its location, version and RECORD hash appear in the worker identity; the user-site path appears in `dependency_paths`. HOME is not neutralized. |
| 5. Tonight | **PASS for the available untouched local dry bundle:** PIT@CLE maps to **2026_04_PIT_CLE**, kickoff **2026-10-02 00:15Z**. Planned quotes are **90 minutes** old for 22:00Z props and **30 minutes** for 23:00Z lines at a 23:30Z start. Bootstrap gate: **4 passed**, **5.664 s** total wall time / 2.36 s pytest. Future live quote arrivals remain unverified. |

The production fixture used pinned code and copied PIT/CLE data, with kickoff/schedule/quote timestamps adjusted to create a synthetic pre-kick primary. It was not a real TNF publication. Planted probes covered `sitecustomize`, `usercustomize`, fake `pytest`, a user-site `.pth`, and timestamp-valid logger bytecode, with `PYTHONPATH`/`PYTHONHOME` pointing at the planted directory. These were execution-marker probes; worker/frozen equality was checked separately.

All three production receipt runtimes—`runtime`, `runtime_before_freeze`, `runtime_worker`—contain `-I -S -B` and fresh-cache indicators. Loaded dependency counts were **1105 / 1105 / 1106**; distribution-file counts **6395 / 6395 / 6395**. Every recorded repository hash and dependency-identity digest recomputed, and all **12** shared distribution identities agreed. Evidence: `/private/tmp/audit13-production.txt` and `/private/tmp/audit13-production-_ftc3w3m`.

The dependency fixture was `bottleneck` version `0.0.0`, which pandas imports while evaluating an optional dependency; it was not enabled as a computational backend. Its RECORD included Python source and a copied real pyarrow vendored dylib. The dylib was **verified as a distribution file, not dynamically loaded**. The clean RECORD hash was `7cbb57f0c87e390405c4f3386b46c507ed373b74d1e2dbde8e3b217658f4167b`; after the library change and RECORD rewrite it was `a96373fd2e53d1e26d3b22f3c5046754260156070a66586d268e0b5227a568cd`. Both the initial isolated user-site experiment and the venv repeat gave the expected outcomes. Logs: `/private/tmp/audit13-dependencies.txt` and `/private/tmp/audit13-dependencies-venv.txt`.

Tonight's untouched bundle is the **local, untracked** worktree artifact `20261001T184559Z`, not a committed artifact at the pin. Its bundle verification returned no errors. Both CLE and PIT have last-played week **3**; team ratings, tendencies and situational tendencies are week **4**; usage, active universe, kickers and QB ratings are week **3**. Evidence: `/private/tmp/audit13-tonight.txt`. The live bundle still must satisfy the actual pre-kick and freshness checks.

### Recomputed verifier claims

| Claim | Independent result |
|---|---|
| Experiment stamps | **HOLDS: 52/52**, no mismatches. |
| Week-3 pilot rows / sim coverage | **HOLDS: 989 rows / 162 `sim_v1`.** |
| Frozen hash equals receipt | **HOLDS:** `e23a883117ddc6e2424eae0751dcc95013021fa6c6575b8c6b2b5ac9bf8baa6b`. |
| Same inputs as pilot `165800Z` | **HOLDS: 15/15 input/props/lines manifest identities match.** The complete new run was separately restored and verified against those identities. |
| Probability and tag equality | **HOLDS: 989 one-to-one keys; max absolute probability difference 0.0; probability arrays byte-identical; 0 tag differences.** All 989 source-age values differ with the six-minute cutoff shift. |
| Read-set contents | **HOLDS as committed record: 45 entries**, all wrapper-only, **0** conflicts, violations or network attempts. This is not a universal native-I/O proof. |
| Repository hashes in the three runtimes | **HOLDS: 15 / 15 / 14 entries recomputed**, no mismatches. See C for the launcher omission. |
| Worker file equals receipt | **HOLDS:** exact JSON equality; all three dependency-identity digests also recompute. |
| Harness/worker shared identities | **HOLDS: 12 shared distributions**, no differences; same Python **3.13.1** and framework executable. |
| Package versions | **HOLDS as stored identities:** pandas **2.3.3**, pyarrow **23.0.1**, numpy **2.4.3**, scipy **1.17.1**, scikit-learn **1.8.0**, polars **1.39.2**. |
| Historical runtime counts | **HOLDS as recorded values:** **15/1495/7035**, **15/1494/7035**, **14/1106/6395**. Historical import counts were not independently replayed identically. |
| Restore of 30 files, frozen-identical | **HOLDS with a precise definition:** **30 archived files** = 27 manifest objects + bundle manifest + publication + frozen output. Rebuilding the opinions manifest and receipt registry yields **32 components/physical files**. Unavailable objects **0**, verification errors **0**, receipt complete, identical full frozen hash. |
| Refused re-run | **HOLDS for the actual early guard:** `build_bundle` against the restored existing `165200Z` directory HALTs with “run_id can only be used once.” I did not rerun the historical simulation. |
| 241 passes on three platforms; exact Mac selftest 1479/7035 | **NOT INDEPENDENTLY REPRODUCED.** The full baseline timed out. No identical selftest import list or three-platform execution was reproduced; different-import probes cannot validate those exact counts. |

Evidence: `/private/tmp/audit13-recompute.txt`, `/private/tmp/audit13-receipt-check.txt`; independent restore: `/private/tmp/audit13-restore-x4x4e6_1`.

## (C) P2, bypasses and D269 claim boundaries

The native probes ran through the real launcher using a RECORD-listed auditor dependency fixture and unchanged pinned repository code.

| Input route | Executed result |
|---|---|
| `pa.OSFile` | Read `b'0.10'`; **0 entries, 0 violations**. |
| Pre-captured `memory_map` alias | Read `b'0.10'`; **0 entries, 0 violations**. |
| `dataset(file URI)` | PermissionError; violation recorded. |
| `memory_map(bytes)` | PermissionError; violation recorded. |
| `ParquetFile(file URI)` | PermissionError; violation recorded. |
| `LocalFileSystem().open_input_file` | PermissionError; violation recorded. |
| `read_parquet(native handle)` | PermissionError; violation recorded. |

A synthetic complete set of **14 mandatory input entries**, plus a hidden OSFile read, still classified **PASS**. Thus the recorder does not establish complete input capture for arbitrary trusted dependency code. This is the native boundary D269 explicitly accepts, not a newly found use by the pinned solver. Log: `/private/tmp/audit13-native.txt`.

The committed static scan passed. My broader reference scan of **19 hashed non-test Python files** found no direct imports or attribute references to OSFile, memory_map, dataset, from_uri or the native input-opening methods. However, the claim that the static scan generally bans saved aliases is **too strong**: a separately re-stamped fixture containing `saved_reader = pa.OSFile; saved_reader(...)` passes the actual scanner because it examines call names. See [test_fwd6d.py:505](/Users/jw115/mlb-model-fwd6/nfl/sim/tests/test_fwd6d.py:505). No such alias was found at the pin.

Platform probes confirmed `/var` and `/private/var` resolve to the same file; recorded paths use resolved `/private/var`. The filesystem is case-insensitive, but differently cased spellings produce **two recorded path strings** with the same hash. This is a normalization/duplication limit, not an unrecorded read in this probe. Framework `sys.path` retained the interpreter's stdlib, lib-dynload and site-packages plus the selected temporary user site. Loaded `.so` checking was exercised by M2b and its control; a copied actual `.dylib` was exercised by P1.3.

**D269 source/claim assessment:**

- **Whole-distribution verification: supported within its stated scope.** [fwd_bootstrap.py:202](/Users/jw115/mlb-model-fwd6/nfl/sim/fwd_bootstrap.py:202) checks SHA-256 RECORD entries of distributions owning loaded module files, with the declared bytecode exclusions. The Python/library corruption probes and missing-file mutation discriminate this behavior. Installed RECORDs and dependency execution remain trusted, as D269 now says.
- **Runtime full hashes: partly overstated.** Every recorded hash matched, but `fwd_bootstrap.py` itself is absent from all three `repo_modules` maps. It checks its manifest prefix at [line 276](/Users/jw115/mlb-model-fwd6/nfl/sim/fwd_bootstrap.py:276) and is skipped at [line 175](/Users/jw115/mlb-model-fwd6/nfl/sim/fwd_bootstrap.py:175). The map covers finder-loaded modules, not literally every repository file that executed. Add a full launcher hash or narrow the claim; this does not bypass its existing manifest check.
- **Worker runtime requirement and cross-process comparison: supported for the tested contracts.** Missing/empty records and mismatches are rejected. I additionally checked the unmodified parent against executable-only, version-only and location-only mismatches; all HALTed. [run_forward_v1.py:947](/Users/jw115/mlb-model-fwd6/nfl/sim/run_forward_v1.py:947).
- **L1/L2:** environment changes are recorded, including HOME-dependent imports; the baseline-membership issue is A1. RECORD rewriting is intentionally accepted and changes the identity—it is not independent attestation.
- **L3/L4:** 16-hex manifest prefixes remain; stored finder-module hashes are full SHA-256. Distribution libraries are checked; native I/O and saved aliases remain a trusted-code boundary. The static-alias claim needs qualification above.
- **L5:** eligibility is a registered requirement for future FWD7, **not a scorer rejection I have executed at this pin**. Before grading, implement pilot exclusion, three runtime requirements, frozen-publication hash matching and the clarified L1 rule. Deferring that implementation does not itself prevent recording a prospective run.
- **L6:** source and executed gate support the separation: gate uses `--noconftest`, and the synthetic production launch did not use test-process overrides.

## (D) Mutation results

Each requested mutation was isolated in an external copy and its changed source hash re-stamped. The **unmodified focused control passed 11 tests in 50.41 seconds**. The same focused selection—not the full suite—was used for mutation testing. Manifest mismatches, timeouts and setup errors were not counted as kills.

| Requested operator | Verdict | Discriminating test |
|---|---|---|
| M1: worker runtime becomes `{}` | **KILLED / FIXED** | `test_bootstrapped_worker_reads_only_wrapper_bytes` |
| M1b: no worker runtime file | **KILLED / FIXED** | Same test |
| M2b: skip `.so`/`.dylib` in both checks | **KILLED / FIXED** | `test_native_extension_module_mismatch_halts` |
| M3: repository hashes zeroed | **KILLED / FIXED** | `test_runtime_pins_full_repo_hashes_and_dependency_identity` |
| M4: omit bytearray normalization | **KILLED / FIXED as contract coverage** | `test_bytearray_and_scheme_only_file_uris_are_refused` |
| M5: omit scheme-only `file:` detection | **KILLED / FIXED as contract coverage** | Same test; mutant still refuses the path, but with the wrong refusal reason |
| M6: remove whole-distribution loop | **KILLED / FIXED** | Runtime identity test: verified distribution count becomes zero |
| M7: ignore missing RECORD file | **KILLED / FIXED** | `test_every_file_of_a_loaded_distribution_is_verified` |
| M8: parent skips worker check | **KILLED / FIXED** | `test_real_default_worker_path_never_imports_shared_logger` |
| M9: ignore shared-distribution mismatch | **KILLED / FIXED** | `test_worker_on_another_interpreter_or_dependency_halts` |
| M10: omit RECORD hash from identity | **KILLED / FIXED** | Runtime identity test |

These include all five audit-#12 survivors. M2 alone was not separately rerun; removing only the module-native check is redundant while whole-distribution verification remains. The requested joint M2b was killed.

**Six new survivors, each 11/11 focused tests passing:**

| Mutation / source | Missing discriminating case |
|---|---|
| Remove mtime from cache key — [fwd_bootstrap.py:113](/Users/jw115/mlb-model-fwd6/nfl/sim/fwd_bootstrap.py:113) | Hash a file, change same-size contents on the same inode with a new mtime, hash again. Executed: pin returns the new hash; mutant returns the old hash. |
| Remove executable comparison — [run_forward_v1.py:963](/Users/jw115/mlb-model-fwd6/nfl/sim/run_forward_v1.py:963) | Same Python version, different executable. Existing test changes the version instead. |
| Compare only RECORD hash — [run_forward_v1.py:967](/Users/jw115/mlb-model-fwd6/nfl/sim/run_forward_v1.py:967) | Independently change version or location while retaining RECORD hash. |
| Do not restore `FileSystem` — [read_set.py:448](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:448) | Assert both filesystem class objects regain their original identities after uninstall, including exceptional exit. |
| Recognize only `file:` URIs — [read_set.py:226](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:226) | Non-file schemes must reach the URI-specific refusal; no successful remote read demonstrated. |
| Ignore PathLike normalization — [read_set.py:220](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:220) | Native reader with a PathLike source. Executed `memory_map(Path(...))`: pin raises PermissionError with violation; mutant reaches Arrow and raises TypeError without one. No successful hidden parse demonstrated. |

These are **focused-suite survivors, not full-suite survivors and not six defects present in the unmodified pin**. The separate saved-OSFile alias survived the static scan, not a full execution suite. Add discriminating tests before relying on those regression claims; the unmodified executable/version/location branches already reject my direct controls.

Mutation runner: `/private/tmp/audit13_p2_mutations.py`; batch results: `/private/tmp/audit13-mutations-batch{0,3,6,9,12,15}.txt`; individual logs: `/private/tmp/audit13-mut-<operator>.txt`. Concrete additional controls: `/private/tmp/audit13-cache-probe.txt`, `/private/tmp/audit13-pathlike-probe.txt`, `/private/tmp/audit13-worker-check.txt`.

## (E) Verdict

**NO-GO for primary TNF at `5fabce877`; use `--pilot` for Thursday.** P1 supplies the reasons: the full baseline did not finish, and the HOME evidence exposes an ambiguity in the promised drift-exclusion rule. The successful production run, dependency-corruption checks, schedule check and mutation kills do not erase those limits. Resolve A1 and obtain a completed baseline before promoting a subsequent window; Sunday is not automatically cleared by this report. Keep the prospective artifacts and implement the declared eligibility rules before any scoring. No live run, repository source change or bet was initiated by this audit.
