# ChatGPT audit #15 — FWD7b / D272
a7bd0c62a7827b1c31f43a0e6fb3692ff9a76598

COMPLETE — October 2, 2026. **NO-GO for either primary Sunday window at this pin.** The previous counterexamples are repaired on the supplied valid inputs. One new malformed-input counterexample recreates the missing-depth defect and reaches the real bootstrap worker, changing its probabilities.

D272 was read in full before testing. Code came from the pinned Git tree, with 52/52 experiment hashes verified. Executions and mutations used temporary copies. The Mac data checks used the immutable refresh archive `/Users/jw115/mlb-model-archive/nfl_ratings_backups/20261002T041239Z/refreshed`, not an assumption that every large local input was committed. All 13 archived source/table hashes matched the recorded manifest, and all eight installed ratings-table hashes matched that archive. No source, real data, real receipt or bet was changed; this reply is the only repository file written.

## (A) Must-fix before a primary Sunday, ranked

**1. Treat an invalid week cutoff as invalid, rather than as a successfully populated dictionary key.** [usage.py:409](/Users/jw115/mlb-model-fwd6/nfl/sim/usage.py:409), [usage.py:415](/Users/jw115/mlb-model-fwd6/nfl/sim/usage.py:415), [usage.py:339](/Users/jw115/mlb-model-fwd6/nfl/sim/usage.py:339), [usage.py:470](/Users/jw115/mlb-model-fwd6/nfl/sim/usage.py:470).

**Executed counterexample, unmodified pinned code:** start with the archived valid week-4 schedule and PBP through week 3. Add one outcome-free PBP row containing `season=2026`, `week=4`, `game_id=2026_04_PIT_CLE`, and `game_date=None`. Rebuild using the pinned usage functions and frozen parameters. The PBP branch records `(2026,4): NaT`; the schedule fallback tests only whether that key exists, so it never uses the valid archived October 1 date. The depth and layer-3 loops skip the invalid cutoff instead of halting.

The resulting week-4 universe has **0 non-null depth ranks instead of 722/800**. The rebuilt player-usage table's hash is the old D271 hash, `c1b6592960d62bad8b621e0d1717a8e3b2fa09543517ad6b298c993549909050`, instead of the D272 installed hash `c865d5f9b1d6959d9ee079d782867f369bb951567705bfbaf59c76817863b3cd`.

I then ran IND@WAS through the **actual bootstrap harness**, first with the clean archived inputs, then with these rebuilt inputs and the same valid schedule/quotes. Both runs passed input freshness, completed simulation, converged, returned `verify_bundle=[]`, and recorded 45 proven reads with zero violations. The clean run produced 82 pick-log rows; the bad-input run produced 81. Across 78 shared contracts, **43 calibrated probabilities changed**, with maximum absolute difference **0.0596**; maximum raw simulation-probability difference was **0.0396**. Example: Chig Okonkwo receptions over 2.5 changed from **0.4596 to 0.4000**.

These were isolated **dry runs** using archived quotes with the stale-quote allowance explicitly enabled. Nothing was frozen. They prove bad constructed inputs reach the real worker past the input gate; they do not constitute a demonstrated primary publication or a fresh-quote Sunday run. The defect is in date/input validation, not an unrecorded input: the wrong table bytes are faithfully recorded.

**Required repair:** validate cutoff values, not just key/file existence. Use the valid archived schedule date when a PBP-derived cutoff is missing/unparseable, or halt explicitly. Require a valid cutoff for the intended run's needed weeks; a present but incomplete schedule must not count as coverage. Keep the same midnight convention in both layers. Add the null-date case and an incomplete-snapshot case to the tests, then repeat the clean/null-date rebuild comparison and production-command smoke. A missing date must either leave the clean result unchanged or halt before the worker.

This is a synthetic malformed-input case. **The supplied D272 archive itself has the expected ranks and passes the original equivalence checks.** The reason for the blocker is that the next refresh can silently reconstruct the previously rejected input version and the forward gate accepts it.

No additional must-fix is assigned to roster timing, the revised input-version declaration, or the unused legacy tendencies column discussed below. They should not be conflated with this executed worker-input defect.

## (B) P1 table

| Requested check | Verdict | Evidence |
|---|---|---|
| 1. Full baseline | **PASS** | 24 files, **280 passed, 0 failed, 0 skipped**, one warning; every final line below. |
| 2. Audit-14 A2 on real week-4 inputs | **FIXED** | Both duplicate orders, nullable `<NA>`, and persisted string/object flags halt. Valid single rows agree with the actual context builder. |
| 3. Audit-14 A1 date-only equivalence | **FIXED for the original case; PARTIAL overall** | Full 2026 usage/universe frames are exactly equal with and without a valid week-4 date row. Null-date extension fails as A1 above. |
| 3. W=2/3 point-in-time identity | **HOLDS on the tested archived inputs** | Exact equality for both tables; both full starting-QB maps and isolated layer-3 maps agree at each tested week. |
| 3. Other builders | **Consumed features pass the tested comparisons** | Team ratings, situational tendencies, kicker rows and consumed prior-season league means match. One legacy tendencies field differs; no downstream numerical read found. |
| 4. Saved 14-game smoke | **Reported counts HOLD** | 28 teams pass, 14/14 final iterations converge, 45 proven reads, 66/257 matches, 722 non-null week-4 depths. |
| 4. Independent one-game bootstrap smoke | **PASS on clean archived inputs** | IND@WAS completes and converges; the malformed-input variant also completes, exposing A1. |
| 5. Sunday runbook | **Original A3 FIXED for week 4** | Four windows; IND@WAS separate, 13-game main+SNF, correct manual MNF capture. Generator matches after normalizing only its generation timestamp. |
| 5. Roster cutoff and D272-v2 declaration | **Acceptable prospective definitions, committed before Sunday** | Both declarations are in the pinned decision at commit `714da08d0`, dated October 2 04:02:10Z. They do not assert final-roster or historical-information parity. |

### B1. Every baseline file

Files are under `nfl/sim/tests/`. Each ran separately in a bounded background group, with its own log and exit status. The authoritative index is `/private/tmp/a15-valid-index.jsonl`. The warning is the existing pandas regular-expression capture-group warning in the suffix-name settlement fixture. There were no skips, so there are no skip reasons. I did not independently execute Linux 3.11 or standalone Python 3.13.7; these results are from the Mac's Python 3.13.1.

| File | Exit | Exact final line |
|---|---:|---|
| test_forward_v1.py | 0 | 8 passed in 0.32s |
| test_freeze_v1.py | 0 | 4 passed in 0.89s |
| test_fwd2_anchor.py | 0 | 3 passed in 0.30s |
| test_fwd2_bundle.py | 0 | 5 passed in 0.27s |
| test_fwd2_experiment.py | 0 | 6 passed in 1.02s |
| test_fwd2_item0_fixes.py | 0 | 7 passed in 1.25s |
| test_fwd2_settlement.py | 0 | 12 passed, 1 warning in 1.05s |
| test_fwd2b_harness.py | 0 | 10 passed in 49.70s |
| test_fwd3_item0.py | 0 | 9 passed in 40.32s |
| test_fwd3_item1.py | 0 | 3 passed in 0.27s |
| test_fwd3_item2.py | 0 | 8 passed in 1.33s |
| test_fwd4_item0.py | 0 | 9 passed in 28.96s |
| test_fwd4_item1.py | 0 | 4 passed in 6.90s |
| test_fwd5_pin.py | 0 | 4 passed in 7.18s |
| test_fwd6_item0.py | 0 | 13 passed in 40.32s |
| test_fwd6_item1.py | 0 | 12 passed in 71.50s (0:01:11) |
| test_fwd6_item2.py | 0 | 9 passed in 33.73s |
| test_fwd6_item3.py | 0 | 5 passed in 11.43s |
| test_fwd6b.py | 0 | 39 passed in 141.04s (0:02:21) |
| test_fwd6c.py | 0 | 33 passed in 85.87s (0:01:25) |
| test_fwd6d.py | 0 | 33 passed in 77.84s (0:01:17) |
| test_fwd6e.py | 0 | 6 passed in 15.58s |
| test_fwd6f.py | 0 | 11 passed in 1.98s |
| test_fwd7a.py | 0 | 27 passed in 3.52s |

Audit execution correction: the first temporary extraction omitted `nfl/__init__.py`, causing manifest-related failures. Those runs are **discarded**, not called repository regressions. I restored that file from the exact Git pin, verified all 52 hashes, and reran **all 24 files**. The table above contains only that complete valid run.

### B2. Duplicate/flag counterexamples on actual week-4 inputs

The archived report has two Out/Doubtful entries and **zero skill-player matches**, so I injected an OUT designation for IND skill player `00-0030279` in a temporary copy; I did not pretend the original report supplied a positive skill-player example.

| Input variant | Gate | Actual player context |
|---|---|---|
| One inactive row, synthetic OUT | PASS | Player excluded |
| Active duplicate before inactive row | HALT: duplicate | Worker not required to establish rejection |
| Active duplicate after inactive row | HALT: duplicate | Same |
| Nullable Boolean flag containing `<NA>` | HALT: missing/non-boolean flags | Same |
| Object column containing strings `True`/`False` | HALT: missing/non-boolean flags | Same |
| One valid active row, report changed to Questionable | PASS | Player included |

An in-memory object column containing only actual Python booleans serializes through Parquet and reads back as `bool`; it passes. That is correct for the persisted input and does not refute the dtype guard. The string-valued object column remains non-boolean and is rejected. Source: [run_forward_v1.py:261](/Users/jw115/mlb-model-fwd6/nfl/sim/run_forward_v1.py:261).

### B3. Independent rebuilds and point-in-time checks

My scripts loaded all seven available historical/current PBP seasons, held the archived roster/depth/injury/schedule bytes and frozen parameters fixed, and rebuilt with pinned functions. The older D271 module served as a negative control; its network-schedule call was replaced with the same archived schedule for a deterministic comparison. No live data download was used.

| Comparison | Active universe | Player usage | Starting QBs |
|---|---|---|---|
| D272 installed 2026 rows versus fresh rebuild | **4,102 rows exactly equal** | **2,056 rows exactly equal** | — |
| D272, valid date-only week-4 row versus no row | **4,102 rows exactly equal** | **2,056 rows exactly equal** | Full and isolated layer-3 maps equal |
| D272, W=2 full PBP versus PBP through W=1 | **786 week-2 rows exactly equal** | **513 week-2 rows exactly equal** | 32 full-map and 32 layer-3 entries equal |
| D272, W=3 full PBP versus PBP through W=2 | **794 week-3 rows exactly equal** | **518 week-3 rows exactly equal** | 32 full-map and 32 layer-3 entries equal |
| D271, date-only week-4 negative control | **1,444/4,102 depth values differ: 35.202340%** | **505/2,056 target shares differ: 24.562257%** | Not used to claim repaired layer-3 behavior |
| D271, W=3 truncated-PBP negative control | **720/794 depth values differ: 90.680101%** | **518/518 target shares differ: 100%** | — |

The Mac's 24.6%, 35.2%, 100% and approximately 91% claims therefore **HOLD**. In the week-4 negative control, maximum target/carry-share changes are **0.0362897391 / 0.0600314339**. In the week-3 negative control they are **0.0418646079 / 0.0793826702**. These are share changes; the worker probability changes in A1 were measured separately.

These tests establish construction identity while holding the other source bytes equal. They do **not** establish that today's historical rosters/injuries are the snapshots an actual past live run possessed. Nor did I re-execute every historical pilot. The evidence supports the identified pre-D272 construction defect and the measured negative controls, not an exhaustive claim about every past pilot row.

For the remaining builders, I separately rebuilt full and W=2/W=3-truncated current-season PBP using unchanged 2025 priors and the frozen fourth-down table:

| Builder / consumed input | W=2 | W=3 |
|---|---|---|
| Team ratings | 128 rows exactly equal | 128 rows exactly equal |
| Situational tendencies | 579 rows exactly equal | 861 rows exactly equal |
| Kickers | 28 rows exactly equal | 32 rows exactly equal |
| Overall tendencies: PROE, pace, GOE, play counts | Exactly equal | Exactly equal |
| 2025 league means, consumed for 2026 | Exactly equal | Exactly equal |

**One stored field fails point-in-time identity:** `fourth_down_go_rate` differs by up to **0.21875** at W=2 and **0.0381944444** at W=3. [ratings.py:477](/Users/jw115/mlb-model-fwd6/nfl/sim/ratings.py:477) derives its shrink target from all available current-season plays, including the target/later weeks in a historical build. This is real future-information dependence in a legacy column. In the pinned engine it is assigned into `t*_4th_go`/`lg_4th_go` context fields but has no downstream load; the live decision path loads `t*_4th_goe`, whose input passed the comparison. This conclusion comes from source/AST tracing, not a separate full-simulation ablation. Quarantine or remove the misleading legacy field in a later declared cleanup; do not describe the entire tendencies table as point-in-time identical.

The stored 2026 league aggregates also change when PBP is truncated, as season aggregates naturally do. The selector reads 2025 for season 2026 ([engine.py:633](/Users/jw115/mlb-model-fwd6/nfl/sim/engine.py:633)); that consumed prior is unchanged. I found no additional consumed-feature construction mismatch in these tested paths. This is bounded evidence, not a proof for every team/week/season or fallback.

### B4. Recomputed verifier claims and smoke

| Claim | Independent result |
|---|---|
| 280 tests, zero skips | **HOLDS on Mac:** 280/0/0 across 24 files. Other platform claims remain unexecuted here. |
| Selftest launcher hash, 1090 / 6395 files | **HOLDS:** exit 0; 12 repo modules, 1,090 dependency files, 6,395 verified distribution files; launcher full hash recomputed. |
| Schedule snapshot: 272 games, weeks 1–18 | **HOLDS:** recounted from archived bytes. |
| PBP 2026 weeks 1–3 | **HOLDS:** 8,311 rows; unique weeks `[1,2,3]`. |
| Fingerprint `3638769c89030de0` | **HOLDS:** independently recomputed from archived refreshed tables. |
| Historical splice preserved | **HOLDS:** all eight pre-2026 table slices exactly equal their pre-refresh backups. |
| D272-v2 archive contains sources/tables | **HOLDS for this refresh:** 5 source files plus 8 tables, all 13 hashes verified; installed tables match the archive. |
| Week-4 depth 722/800; duplicates/null flags zero | **HOLDS:** 800 rows, 722 non-null ranks, zero duplicate team/player keys, bool dtype, zero null flags. D272's earlier cloud denominator 792 is not this Mac snapshot's count. |
| Five player count pairs match PBP | **HOLDS:** Metcalf **24/0**, Concepcion **20/4**, Jeudy **5/0**, Warren **14/38**, Judkins **9/42**, independently counted from weeks 1–3. |
| Two Out/Doubtful entries, no skill-player entries | **HOLDS:** 2 report rows, 0 skill-universe joins. This cannot itself demonstrate positive skill-player exclusion; B2 supplies that test. |
| Runbook equals generator | **HOLDS except generation timestamp:** all other text matches when generated against the archived schedule. |
| Sunday dry run has 14 games, all converged | **HOLDS on saved artifact:** 14 events, 14 converged final iterations. |
| Saved smoke has fresh per-team rows/universe | **HOLDS:** all 28 teams pass; selected weekly tables are 4, last played is 3, active-universe comparison passes. |
| 45 reads, 0 unproven | **HOLDS on saved artifact:** 45 entries, zero violations, `verify_bundle=[]`. |
| 66/257 props matched | **HOLDS:** independently rebuilt the sheet/matching count, obtaining 66/257. |
| Game-status counts zero except WAS=2 | **HOLDS:** confirms the early report snapshot, not final-report completeness. |

Saved smoke inspected: `/Users/jw115/mlb-model-fwd6/nfl/data/board/week=2026_04/sim_runs/20261002T042334Z`. Last-played weeks were recomputed from the separate archived PBP; the bundle does not contain a raw `pbp_2026.parquet` file. Bundle depth values were read directly, not inferred from the refreshed table elsewhere.

The independent clean one-game bootstrap harness replay of IND@WAS exited 0 in **58.23 seconds**, converged, verified the bundle, and recorded 45 inputs with zero violations. It used the real archived game/quote/input bytes and a temporary repository. The malformed-date variant exited 0 in **58.73 seconds**. Both explicitly used `--dry-run --allow-stale-quotes`; neither was a primary freeze or evidence that Sunday's not-yet-captured quotes are fresh.

The D271 corrections are supported: added QB-rating rows are inert in the identified fit/live feature path, and an earlier-input full-rebuild fingerprint must not be presented as a result on these newer bytes. I did not reconstruct the unavailable older cloud snapshot or independently rerun that full eight-table historical rebuild.

### B5. Sunday windows, quote ages and refresh timing

The committed runbook matches the archived week-4 schedule:

| Window | Pull and harness | Props age at cutoff | Refresh completion deadline |
|---|---|---:|---|
| PIT@CLE, already past | Thu Oct 1 22:00Z VM pull; 23:30Z harness; kickoff Fri 00:15Z | 1 h 30 min | Before the harness; this audit does not authorize retroactive inclusion |
| **IND@WAS** | **Sun Oct 4 12:15Z manual pull; 12:45Z harness; `--window-hours 1.5`** | **30 min**, if capture actually succeeds | **12:15Z**, at least 30 min before harness |
| **Main + SNF, 13 games** | **Sun Oct 4 16:00Z VM pull; 16:15Z harness; `--window-hours 9`** | **15 min**, if capture actually arrives | **15:45Z**, at least 30 min before harness |
| ATL@NO, Monday night | Mon Oct 5 23:00Z manual pull; 23:30Z harness; kickoff Tue 00:15Z | 30 min | 23:00Z |

The London window ends at 14:15Z and excludes the 17:00Z slate. Main ends at Monday 01:15Z and includes the 00:20Z SNF kickoff while excluding Monday-night ATL@NO. The Monday 23:45Z VM pull is after the 23:30Z harness; no Monday 22:00Z slot is invented. The code's weekday-slot logic was executed; I did not inspect the remote VM's actual deployed cron state.

Game lines must separately satisfy the three-hour rule. For IND@WAS at 12:45Z, accept timestamps in **[09:45Z,12:45Z]**; a 12:30Z tape snapshot is 15 minutes old. For main at 16:15Z, accept **[13:15Z,16:15Z]**; a 16:00Z snapshot is 15 minutes old. For Monday 23:30Z, accept **[20:30Z,23:30Z]**. Actual arrival, event/book coverage and timestamps must be checked, not inferred from the schedule. These are age calculations, not passed future captures. No paid or live pull was made in this audit.

Run `refresh_inputs.py --week 4` after Friday's final reports and again before each Sunday window, allowing its rebuild to finish by the deadlines above. Exit 1 means the refreshed tables remain installed and some named teams are not ready; the run's selected teams still must pass. The saved run note mislabels ATL/NO as TNF: they are the Monday-night game according to the archived schedule. Their absent report need not block the Sunday-only windows. Missing report rows alone do not prove the report was unpublished rather than absent from the local feed.

**Roster-cutoff judgment:** the declared last-refresh rule is acceptable for a **primary prospective experiment of that operational policy**. Main+SNF need not move after each game's inactives merely to become primary. The resulting claim must be about early roster information, not final-roster parity or validation of the backtest's exact information set. Follow the precommitted timing and exclusions; do not add/move windows after results. Friday-final-report coverage and the actual refresh time still need documenting; a zero `injury_game_statuses` count alone cannot distinguish a genuinely empty report from an incomplete feed.

**Input-version judgment:** D272-v2 is an acceptable prospective definition: rebuilt 2026 rows, frozen prior-year output rows, and archived source/output bytes. All archive hashes hold for the inspected refresh. This does not excuse the invalid-cutoff path in A1. Both declarations are present in commit `714da08d0b382a5c9fb385981bea36fbd139b281`, recorded at **2026-10-02 04:02:10Z**, and the audit pin is recorded at **04:33:26Z**. They were committed and read before the first Sunday kickoff, **2026-10-04 13:30Z**.

## (C) P2 and remaining bypasses

**All R1–R18 were independently killed.** Each mutation was isolated in a temporary copy, and a changed file already listed in the experiment manifest was re-stamped. The unchanged focused control passed **41 tests**: test_fwd6f, test_fwd7a, the two relevant static-reader tests from test_fwd6d, and test_fwd6b's real default-worker-path test. Changed files not listed in the manifest were not silently added to it. Runs stopped at the first test failure; killed does not mean every downstream branch was examined.

| Mutations | Result and distinction |
|---|---|
| R1 schedule fallback; R2 schedule season filter; R3 PBP-only depth; R4 missing-snapshot refusal | **4/4 KILLED**. Valid-date and absent-file cases are covered; invalid values inside existing coverage are not covered by those tests. |
| R5 duplicates; R6 flag guard; R7 nullable flags | **3/3 KILLED**. The independent B2 cases also exercise actual persisted week-4 inputs. |
| R8 runtime keys; R9 baseline count; R10 last-primary baseline; R11 self-baselining | **4/4 KILLED**. Missing current mapping returns three missing-key violations; a two-runtime baseline returns a count violation. |
| R12 omit dependency fields from receipt | **KILLED** by the real default-worker-path integration test. |
| R13 omit schedule snapshot call; R14 omit archive; R15 omit schedule from archive | **3/3 KILLED**. These do not prove the real snapshot writer or every archive-copy branch is behaviorally covered; see survivors. |
| R16 merge morning/main; R17 invent Monday 22:00Z; R18 report success when not ready | **3/3 KILLED**. |

**All eight audit-14 survivors are now killed:** missing baseline-runtime handling; choosing the last baseline (same operator as R10); bare-name native references; missing situational-tendency gate; ignoring Doubtful; cap 21 rather than 22; dropping pre-2021 splice rows; restoring only usage. The nullable/duplicate bug is fixed in unmodified code. The old baseline-key helper gap is fixed too.

**Refresh exit semantics are repaired for the tested boundary.** The tests separately verify rebuild exceptions restoring all eight tables and a final False readiness result returning 1 with installed tables/archive. The source's leading “any failure restores” wording is still too broad if read without its later qualifications: an exception raised *inside the final report itself* is outside the restore block. I did not execute that additional exception case. Treat restoration as a rebuild-phase guarantee, not a universal transaction guarantee.

**Missing schedule coverage:** deleting all week-4 rows from the snapshot lets the builders complete with zero week-4 depth ranks; the isolated freshness predicate passes IND/WAS. However, the forward event mapper also requires those games in the schedule, so this isolated gate result is **not evidence of a complete harness bypass with that same incomplete snapshot**. A1 uses an unchanged valid schedule and was therefore tested all the way through the real worker. This distinction is material.

No new route from a value other than the worker's into a primary frozen probability was demonstrated. The identified path supplies bad materialized inputs to the worker and records them correctly. I did not perform a new primary freeze in this audit. The accepted RECORD-matched native-I/O trust boundary remained out of scope.

## (D) New surviving mutations

Each of the seven following isolated mutants returned **41 passed, exit 0** in the focused selection. They were not run against all 280 tests. These are test-coverage findings, not claims that the original source contains the mutations.

| Mutant | Surviving behavior | Needed distinguishing test |
|---|---|---|
| `_week_cutoffs`: choose maximum PBP date instead of minimum | Existing fixtures have one date per week | Put Thursday and Sunday dates in the same week; require Thursday midnight |
| Layer-3 QB eligibility: `dt <= cutoff` instead of `<` | No fixture lies exactly on the boundary | Snapshot exactly at cutoff must be excluded |
| `_active_universe_matches`: remove dtype check, retain null check | Existing non-boolean fixture also contains null; null check still rejects it | All-non-null string/object flags; the independent B2 test would kill this mutant |
| `dependency_fields`: use `not r.get("pilot")` instead of explicit `is False` | Registry test has explicit booleans only | A receipt without the field must not become the first primary |
| `archive_refresh`: omit every output-table copy but retain its manifest hash | Test verifies copied source bytes and table manifest hashes, not archived table bytes | Require all eight archived table files and hash those copies |
| `snapshot_schedule`: write `wrong.parquet` instead of `schedules_2026.parquet` | Refresh integration substitutes a mock snapshot function | Execute the real writer with a controlled nflreadpy result and verify path/content |
| Runbook morning boundary: 16:00Z instead of 16:30Z | Tests use 13:30Z and 17:00Z, which do not distinguish the boundaries | Include a 16:15Z Sunday kickoff and require the early window |

The cutoff/null-date regression should be added alongside these coverage repairs. The actual archived output tables exist and their hashes match; the archive-copy survivor does not mean this Mac archive is missing its tables.

## (E) Per-window verdict

| Sunday window | Verdict at this pin | Reason |
|---|---|---|
| **IND@WAS, 12:45Z harness** | **NO-GO as primary** | The malformed-date counterexample reaches this exact game's worker and changes probabilities despite passing the input gates. |
| **Main + SNF, 16:15Z harness** | **NO-GO as primary** | The same cutoff path constructs every week-4 team's usage/universe; it is not London-specific. The declared early roster cutoff is acceptable and is not the reason for refusal. |

The repair can be narrow: reject or correctly fall back from invalid/missing cutoff values, prove the null-date case cannot reach a changed worker result, and rerun the affected checks plus the full baseline on the repaired pin. The valid archived-input equivalence, duplicate-row protection, input archive and week-4 runbook checks already hold. Fresh Sunday quote and final-report checks remain operational prerequisites that cannot be completed on Friday. A primary label must not be assigned retroactively after outcomes.

Evidence retained outside the repository: [archived-input and saved-smoke recomputation](/private/tmp/a15-inputs.json), [independent usage/QB comparisons](/private/tmp/a15-pit.json), [real-input gate cases](/private/tmp/a15-gates.json), [other-builder comparisons](/private/tmp/a15-ratings-pit.json), [bootstrap smoke results](/private/tmp/a15-smoke.json), [worker probability deltas](/private/tmp/a15-smoke-deltas.json), [runbook/selftest](/private/tmp/a15-misc.json), [mutation operators](/private/tmp/a15_mutations.py), and [per-mutation results](/private/tmp/a15-mutations.txt). The snapshot/fixture scripts and logs are under `/private/tmp/a15*` for reproduction. No external schedule site, live VM, live feed, Sunday final report or future quote capture was independently accessed.
