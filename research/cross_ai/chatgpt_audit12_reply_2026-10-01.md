# ChatGPT audit #12 reply — FWD6d on eng/fwd6 (2026-10-01)
876e61463e312db52f006287cc1126e8d406afec

**INCOMPLETE AUDIT / HANDOFF. No independent GO has been issued.** This file preserves completed work and identifies the uncompleted checks. It is not a completed answer to all R1–R6. The delay was in my execution of this audit; I cannot establish that a desktop warning caused a particular test to be blocked. I did not execute the full dependency/HOME counterexample I discussed, and it must not be represented as a finding.

I read the pinned source and tested a commit-derived extraction at `/private/tmp/nfl-audit12-876e61463`. The worktree `/Users/jw115/mlb-model-fwd6` was verified at the full SHA above. All fixtures, altered copies, test outputs and restore destinations were outside both repositories; the actual archive was read-only. This reply is the only repository write. Simulation physics, fitting and calibration quality were not audited.

The new deadline is acknowledged: merge before the **23:30Z live start**, not the superseded 15:00Z cutoff.

## (A) Must-fix / conditions still needed for independent sign-off

**I have not established a new production corruption counterexample at this pin.** The old startup and source-cache routes were blocked in the completed full-command tests. The three substantive new mutation survivors below are coverage findings, not evidence that the unmodified implementation contains those mutations.

The following remain necessary to complete this audit. They are ranked verification obligations; they should not be misquoted as three demonstrated production defects.

1. **Resolve the dependency execution boundary before declaring executed code attested.** At [fwd_bootstrap.py:193](/Users/jw115/mlb-model-fwd6/nfl/sim/fwd_bootstrap.py:193), dependency paths include the HOME-dependent user site. Dependency modules execute under ordinary import machinery; [verify_loaded_modules:120](/Users/jw115/mlb-model-fwd6/nfl/sim/fwd_bootstrap.py:120) subsequently hashes their current files and compares them with current RECORD entries. Unlike repository source, their compiled bytes are not captured and checked by `VerifiedSourceFinder` before execution. The RECORD files are not independently pinned. These are verified source facts. I did **not** finish the separate altered-dependency experiment or demonstrate a changed frozen probability through this route. A clean, fixed dependency environment with user-site imports disabled or explicitly pinned is a concrete way to reduce this ambiguity; it needs verification on the actual launch environment.
2. **Finish the requested native-reader re-tests under the bootstrap.** The normal suite exercises URI/bytes/keyword paths, guarded filesystems, opaque native handles and swallowed refusals successfully. It does not make saved native aliases or `pa.OSFile` observable. These remain explicitly outside the recorder's interception boundary. See [read_set.py:275](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:275), [289](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:289), [356](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:356), [403](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:403). I did not execute every requested old native counterexample independently through the production launcher, so I cannot certify universal closure.
3. **Test the new runtime-verification failure cases before relying on the receipt fingerprint as enforcement evidence.** The suite passes if worker verification is omitted, if native extension files are exempted, or if recorded repository hashes are all zeros. Concrete additional tests: make the worker reach its terminal verification with a mismatching dependency record; require a loaded extension hash mismatch to halt; and recompute the receipt's repository-code contribution from the actually verified source bytes. Locations: [fwd_bootstrap.py:101](/Users/jw115/mlb-model-fwd6/nfl/sim/fwd_bootstrap.py:101), [128](/Users/jw115/mlb-model-fwd6/nfl/sim/fwd_bootstrap.py:128), [232](/Users/jw115/mlb-model-fwd6/nfl/sim/fwd_bootstrap.py:232). These are missing discriminating tests, not proof that today's checks fail.

Do not infer a GO from the successful regressions below. Conversely, do not describe my incomplete verification as proof that tonight's unmodified prediction is corrupted.

## (B) Re-test table and recomputed verifier claims

### Baselines and full production-command freezes

Both UTF-8 modes completed with **233 passed, 2 skipped, zero failed**, each in approximately 473 seconds. The two skips are external 2026 snap-count and GSIS/PFR crosswalk tests at `test_fwd2_settlement.py:162` and `:243`. I did not reproduce 235 actual passes, and did not independently run Linux or standalone Python 3.13.7.

I ran the exact command shape:

```text
python3 -I -S -B nfl/sim/fwd_bootstrap.py harness --week 4 --window-hours 2
```

These runs used external fixture repositories, real pinned worker/harness/logger code, and PIT/CLE prediction inputs. Only fixture kickoff, schedule and quote timestamps were adjusted to create a synthetic pre-kick primary window. They are not actual TNF primary publications.

| Full-command run | Result |
|---|---|
| Clean launch | Exit 0 in **45.71 s**; **70 frozen rows, 11 matched**, `pilot=False`; **45 wrapper reads**, no violations; bundle verification empty; receipt complete. |
| Planted startup files and timestamp-valid cached logger | Exit 0 in **46.64 s**; same row/match/read counts; **none of the planted markers executed**; `pilot=False`; bundle verification empty; receipt complete. |
| Worker-to-frozen comparison | Rebuilt expected opinions from actual worker picks and bundle sheet; maximum probability difference **0.0** in each run. |
| Runtime receipt | Both before/after fingerprints present; **15 repository modules and 1,105 dependency files**, flags `-I -S -B`, Python **3.13.1**. |

The planted files covered `sitecustomize`, `usercustomize`, fake `pytest`, a `.pth` in the interpreter-reported user-site layout, and a timestamp-valid logger cache. `PYTHONPATH` and `PYTHONHOME` pointed to the planted directory. These probes used execution markers rather than reproducing the old 0.62→0.97 payload verbatim; actual worker/frozen equality was checked separately.

### Audit #11 counterexamples

| Requested route | Status supported by completed evidence | Current source |
|---|---|---|
| `sitecustomize` alters parent | **FIXED for the exercised startup route.** Planted module did not execute in the full launch; frozen probabilities matched actual worker picks. Exact old numerical payload was not rerun verbatim. | [fwd_bootstrap.py:169](/Users/jw115/mlb-model-fwd6/nfl/sim/fwd_bootstrap.py:169) |
| Fake pytest on PYTHONPATH | **FIXED for the exercised route.** Planted module never executed; full gate succeeded using installed pytest. The committed fake-report regression also passes. | [fwd_bootstrap.py:216](/Users/jw115/mlb-model-fwd6/nfl/sim/fwd_bootstrap.py:216) |
| `.pth` execution | **FIXED for the exercised route.** Planted `.pth` marker absent through full launch. Importing `site` under `-S` to query paths does occur; automatic site initialization/`.pth` processing does not. | [fwd_bootstrap.py:178](/Users/jw115/mlb-model-fwd6/nfl/sim/fwd_bootstrap.py:178) |
| Timestamp-valid logger cache | **FIXED for the exercised cache.** Marker absent despite valid source timestamp/size header; frozen probabilities matched worker. | [fwd_bootstrap.py:184](/Users/jw115/mlb-model-fwd6/nfl/sim/fwd_bootstrap.py:184), [VerifiedSourceFinder:78](/Users/jw115/mlb-model-fwd6/nfl/sim/fwd_bootstrap.py:78) |
| Dataset URI, memory-map bytes, ParquetFile URI | **FIXED in the committed regression tests; independent launcher-specific counterexamples incomplete.** Tests returned the required refusal; source implements the path-form handling. | [read_set.py:214](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:214), [289](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:289), [356](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:356) |
| LocalFileSystem input methods, native handle into pandas | **FIXED in the committed regression tests; independent launcher-specific re-test incomplete.** Guarded classes and NativeFile rejection are present. | [read_set.py:295](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:295), [403](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:403) |
| Pre-captured native alias; OSFile | **NOT FIXED by runtime interception.** The code and D266 acknowledge this. Whether the now-enforced code/dependency boundary is sufficient for primary operation is part of the unfinished judgment. No new execution result is claimed. | [read_set.py:275](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:275) |
| Hidden read in a complete proof | **PARTIAL evidence.** The committed swallowed-refusal test passes, but its proof is not a separately executed complete mandatory-read-set/native-alias counterexample. | [test_fwd6d.py:451](/Users/jw115/mlb-model-fwd6/nfl/sim/tests/test_fwd6d.py:451) |

### All 15 prior mutation operators

Each was applied separately in an external copy and the changed source's experiment hash re-stamped. The full forward list was invoked with `test_fwd6d.py` first and stop-on-first-failure. **All 15 were killed by behavioral tests.** No generic manifest mismatch was counted as a kill.

| Operator | Verdict | First failing test |
|---|---|---|
| Old user-site-prefix omission | **FIXED** | `test_user_site_is_an_installation_prefix` |
| Old CSV first-row loss | **FIXED** | `test_csv_parsed_while_recording_is_complete` |
| Old restore SHA limited to 16 MiB | **FIXED** | `test_restore_hashes_whole_large_objects` |
| Old first duplicate receipt accepted | **FIXED** | `test_find_receipt_refuses_duplicates` |
| Old restore CLI assumes complete | **FIXED** | `test_restore_cli_reports_status_mismatch` |
| N1 omit usage.py from allowlist | **FIXED** | `test_hashed_code_paths_is_exactly_the_manifest_py_set` |
| N2 bytecode/source mapping | **RETIRED; regression guarded** | Reintroducing the old mapping fails `test_repository_bytecode_is_data_not_code`. The old removal operator is now intended behavior. |
| N3 drop later read mechanisms | **FIXED** | `test_every_read_mechanism_is_kept` |
| N4 ignore native keyword arguments | **FIXED** | `test_uri_bytes_and_keyword_sources_are_refused` |
| N5 deduplicate gate testcase names | **FIXED** | `test_gate_report_rejects_a_duplicated_test_name` |
| N6 gate timeout becomes ten hours | **FIXED** | `test_gate_timeout_is_600_seconds` |
| N7 ignore nonzero gate exit | **FIXED** | `test_gate_halts_on_nonzero_exit_even_with_a_valid_report` |
| N8 compare cutoff dates only | **FIXED** | `test_claimed_cutoff_same_day_other_time_halts` |
| N9 compare bundle basenames only | **FIXED** | `test_claimed_bundle_with_same_basename_halts` |
| N10 last-played weeks from shared PBP | **FIXED** | `test_last_played_weeks_come_from_the_snapshot` |

The claims about Cowork's B01–B16/C1–C2 matrix were not independently rerun as a separate complete matrix. Do not substitute the 15 operators above for that claim.

### Committed pilot: independent recomputation

| Claim | Result |
|---|---|
| Experiment source/data stamps | **HOLDS: 52/52 match**, zero mismatches. |
| Input hashes equal preceding FWD6c pilot | **HOLDS: 15/15** `inputs/*`, props and lines hashes match. |
| Read set | **HOLDS as committed record: 45 entries**, all `['wrapper']`; zero conflicts, violations and network attempts. |
| Frozen rows and sim coverage | **HOLDS: 989 rows, 162 sim_v1.** |
| One-to-one frozen probability comparison | **HOLDS: 989 one-to-one keys**, max absolute difference **0.0**, bit-identical probability arrays after key sorting. |
| Tag, side, source time and prices | **HOLDS: 0 differences** in `tag`, `side`, `source_utc`, `price_first`, `price_second`. |
| Source ages differ | **HOLDS: 989 source_age_min values differ.** This comparison does not assert that no run-identity/publication metadata column changed. |
| Frozen hash | **HOLDS:** `1cc611fe39fc3c8789aed09d7f7cf0b3ef04300947017832107573e8e4cbfc16`, matching the receipt. |
| Stored runtime counts | **HOLDS as receipt contents:** 15 repository modules; **1,494 before / 1,495 after** dependency files; `-I -S -B`; pilot true. These historical counts were read, not recreated identically. |
| Full archive restore | **HOLDS in independent execution:** **31 components**, unavailable 0, verification errors 0, receipt complete, identical full frozen SHA. |
| Mac dependency checking active | **HOLDS:** independent bootstrapped `selftest pandas pyarrow.parquet` reported **430 dependency files**, greater than zero. Different imports explain why this is not the claimed 1,479. The synthetic full harness reported 1,105. |
| 235 passed on three platforms | **Not independently reproduced:** local result **233 passed, 2 skipped**; no independent Linux/3.13.7 run. |

## (C) Bypasses, limits, and tonight's procedure

### L1–L6 judgment, with unfinished evidence explicit

- **L1 — self-attesting RECORD: confirmed by source.** `_record_index` reads current installed RECORD files; they have no independent approved digest in the experiment. `verify_loaded_modules` inspects current files after imports, not the dependency source bytes actually compiled. It does not establish resistance to concurrent dependency replacement or code that modifies process state while importing. I did not execute that adversarial counterexample. Treating the installed dependency environment as trusted can be a valid boundary, but then the receipt must not be described as independent attestation of arbitrary dependency behavior. Final primary-blocker judgment remains incomplete.
- **L2 — HOME selects user site: confirmed by source and interpreter layout query.** The framework interpreter's user-site path is under `HOME/Library/Python/3.13/lib/python/site-packages`; the bootstrap deliberately appends it if present. `-I` does not prevent this later explicit addition. The full planted `.pth` test shows no `.pth` execution; it does not prove ordinary packages from that directory cannot import. Disable this path or explicitly fix and approve its contents if environment independence is required. Automatic optional-dependency execution through a changed HOME was not tested.
- **L3 — 16-hex prefixes: confirmed.** These are 64-bit hash prefixes. They are useful accidental-change checks, not full collision-resistant artifact identities. Full SHA-256 stamps are a straightforward improvement. I have no collision counterexample and would not make this alone a primary blocker for the stated accidental-regression threat model.
- **L4 — trusted native dependencies: confirmed.** Python-level wrappers do not observe arbitrary native I/O. RECORD checks cover Python module files with `__file__`, not an exhaustive trace of every transitive shared library, resource file or runtime behavior. The native-extension-skip mutation surviving shows missing test coverage, not that today's source skips those files. Independent OSFile/saved-alias and platform-extension probes remain unfinished.
- **L5 — unbootstrapped pilot versus primary: partially resolved.** The live guard is present, its regression test passes, and my full synthetic primary receipts contain runtime data and `pilot=False`. The direct pilot fixture test confirms `runtime=None` is allowed. A dry run does not publish a receipt. I did not verify a scorer rejecting primary rows associated with null runtime. That eligibility predicate must be specified and tested before grading: require pilot false, matching receipt/publication/frozen identities, valid runtime fields, and successful verification. This is not established by the current pilot test.
- **L6 — test conftest disables launcher requirement: production separation supported by code and runs.** The gate uses `--noconftest`; the bootstrap's repository finder rejects unlisted imports; harness/worker do not invoke pytest. My synthetic primary runs used no test-process override. The test conftest is outside the experiment allowlist. I did not find a normal production route that imports it. This does not cure L1's general dependence on trusted in-process dependency code.

D268's Mac-path ordering fix is present and active: dependency directories take precedence over the containing stdlib directory. `Path.resolve()` is used for origins and record entries. I did not complete the requested case-insensitivity, `/private/var` alias and `.so`/`.dylib` platform probes. Do not infer those checks passed from the 430/1,105 counts.

### Tonight's live path

The correct command at this pin is the bootstrap command shown above. Source requires the bootstrap for a primary, starts gate and worker through it, limits gate execution to 600 seconds and performs runtime verification before freezing and again before writing the receipt. The full command completed locally in approximately 46 seconds with synthetic pre-kick data; a separate gate-only timing was not retained in this audit.

At a **23:30Z** cutoff, **22:00Z props are 90 minutes old** and **23:00Z lines are 30 minutes old**, within the configured three-hour quote threshold. Future pulls were not available to verify. A primary must use actual fresh rows without `--allow-stale-quotes`.

The copied local FWD6d dry-run bundle `20261001T150653Z` passed `verify_bundle`. In the synthetic full runs, both CLE and PIT had last-played week **3**; team ratings/tendencies/situational tendencies week **4**; usage/active universe/kicker/QB week **3**. The real worker emitted 45 wrapper reads and 11 matched opinions. The synthetic fixtures replaced kickoff/schedule timestamps; they therefore do not independently re-verify the actual **PIT@CLE 00:15Z** schedule mapping for tonight. That remaining check should use the untouched dry-run schedule/event files and then repeat on the actual live bundle.

The historical pilot is not a primary: its receipt explicitly says pilot true. The synthetic primary runs prove the non-pilot runtime-receipt path is reachable and coherent; they do not establish that all requested provenance counterexamples have been closed.

## (D) New surviving mutations

Each mutation was isolated in an external copy and its experiment source hash re-stamped. Survivors each completed **233 passed, 2 skipped, exit 0** against the full forward list. These are test observations, not claims that the pin contains the altered behavior.

| Mutation | Result | Meaning |
|---|---|---|
| Remove final `verify_loaded_modules()` from `_worker`, [fwd_bootstrap.py:232](/Users/jw115/mlb-model-fwd6/nfl/sim/fwd_bootstrap.py:232) | **SURVIVES** | A successful worker/read-set test does not prove the worker executes its runtime-verification failure path. |
| Skip files ending `.so` or `.dylib` in verification, [fwd_bootstrap.py:129](/Users/jw115/mlb-model-fwd6/nfl/sim/fwd_bootstrap.py:129) | **SURVIVES** | Tests checking a pandas Python file and a positive dependency count do not ensure native-extension files are checked. |
| Record all repository source hashes as 64 zeros, [fwd_bootstrap.py:101](/Users/jw115/mlb-model-fwd6/nfl/sim/fwd_bootstrap.py:101) | **SURVIVES** | Runtime provenance contents are not independently recomputed by tests. Actual source verification still occurs in this mutant. |
| Remove bytearray normalization in `_as_local_path`, [read_set.py:218](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:218) | **SURVIVES as a branch/contract test gap** | No discriminating bytearray-source fixture. I did not establish a successful unrecorded native parse from this change. |
| Remove recognition of `file:` without `://`, [read_set.py:226](/Users/jw115/mlb-model-fwd6/nfl/sim/read_set.py:226) | **SURVIVES as a branch test gap** | Existing URI fixtures use `file://`. Other guards may still reject the altered case; this is not independently proven to weaken end-to-end rejection. |
| Leave LocalFileSystem patched after uninstall | **KILLED** | `test_native_filesystem_and_handles_are_refused` fails. |

The first three are substantive missing enforcement/provenance assertions. The last two surviving operators should not be inflated into demonstrated production corruption.

### Reproduction evidence / handoff

- Extracted pin: `/private/tmp/nfl-audit12-876e61463`.
- Baseline runner/results: `/private/tmp/audit12_baseline.py`, `/private/tmp/audit12-baselines.txt`, `/private/tmp/audit12-baseline-0.txt`, `/private/tmp/audit12-baseline-1.txt`.
- Prior 15 mutations: `/private/tmp/audit12_mutations.py`, `/private/tmp/audit12-mutations.txt`.
- New six mutation attempts: `/private/tmp/audit12_new_mutations.py`, `/private/tmp/audit12-new-mutations.txt`; individual outputs `/private/tmp/audit12-mut-<operator>.txt`.
- Full-command probes: `/private/tmp/audit12_production.py`, `/private/tmp/audit12-production.txt`; fixture roots and child logs at `/private/tmp/audit12-production-b7mn1dsd`.
- Committed comparisons/restore: `/private/tmp/audit12_recompute.py`, `/private/tmp/audit12-recompute.txt`; recovered record `/private/tmp/audit12-restore-iqrcwzm6`.

Remaining work to finish R1–R6: independent launcher-based native counterexamples; actual altered-dependency/HOME execution experiment; requested platform-path/extension probes; scorer/null-runtime rejection; untouched tonight schedule validation; final judgment on L1/L2/L4 with that evidence. Cowork's separate B01–B16/C1–C2 mutation matrix also remains unverified as a whole.

## (E) Verdict

**NO-GO for independent sign-off from this incomplete audit — the completed regressions support specific fixes, but the remaining provenance checks were not completed; this is withheld approval, not a demonstrated new corruption defect at 876e61463.**
