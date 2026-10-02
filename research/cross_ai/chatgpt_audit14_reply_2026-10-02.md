# ChatGPT audit #14 — FWD6f + FWD7a
7429e9dbfdf6909746b934a5bdf0259efb67995d

COMPLETE — audited October 2, 2026 UTC. **NO-GO for a primary Sunday at this pin.**

I read D270/D271 and executed the pinned code extracted from `eng/fwd6`. All 52 experiment-manifest hashes matched. The full baseline passes; the new refusal rests on demonstrated input defects, not the previous audit's baseline failure. Source references below point to the pinned `/Users/jw115/mlb-model-fwd6` checkout. Engine inspection was limited to the input-selection paths explicitly requested by this brief; this is not a review of simulation physics, calibration quality or betting profitability.

Data provenance matters: the refreshed Mac inputs and historical PBP were read from the local checkout and copied into temporary directories. They are not all committed at the pin. In particular, the local refreshed `player_usage_weekly.parquet` differs from the committed file; the other seven ratings tables match. The dry-run artifact is local, too. Results below distinguish those local-data checks from committed-code checks. No source, real input, receipt registry or bet was changed. This report is the only repository file written.

## (A) Must-fix before a primary Sunday, ranked

**A1 — Live future-week depth construction differs from the backtest and materially changes usage.** [usage.py:476](/Users/jw115/mlb-model-fwd6/nfl/sim/usage.py:476), [usage.py:494](/Users/jw115/mlb-model-fwd6/nfl/sim/usage.py:494), [usage.py:850](/Users/jw115/mlb-model-fwd6/nfl/sim/usage.py:850).

Executed counterexample: using the same current rosters, injuries and depth-chart bytes, `build_active_universe` produced 800 week-4 rows with **zero non-null depth ranks** when PBP contained only weeks 1–3. Adding only a week-4 date to the PBP cutoff lookup produced **722 non-null ranks**, **192 different depth groups**, and **zero changed active flags**. No future play outcome or statistic was supplied. The code skips new-schema depth charts when that week's date is absent from PBP; a completed historical week has that date, while the upcoming live week does not.

I then rebuilt usage using all seven available PBP seasons, frozen parameters and the archived schedule. The control reproduced the current 2026 target shares exactly: maximum absolute difference **0.0**. Holding the historical inputs and priors fixed and changing only the current-season depth frame changed **505 week-4 target shares**. Maximum absolute change was **0.0362897391** in target share and **0.0600314339** in carry share—3.629 and 6.003 percentage points. For example, Caleb Douglas changed from 0.166950319 to 0.203240058; Denzel Boston from 0.166178158 to 0.195142118. These are input-share differences, not measured probability or ROI differences.

The freshness gate still passed IND/WAS after substituting the depth frame: it checks week labels, membership and active flags, not depth construction. Fix the builder to take an explicit archived schedule/cutoff for both live and historical construction. Test that adding an outcome-free target-week date to PBP cannot change inputs when the pre-kickoff information is unchanged. Regenerate 2026 rows under a declared input-version amendment, preserve frozen historical rows, and recheck the fingerprint. Simply relabeling the current rows as week 4 does not fix this.

**A2 — Duplicate active-universe rows let an OUT player pass the gate and enter the actual player context.** [run_forward_v1.py:261](/Users/jw115/mlb-model-fwd6/nfl/sim/run_forward_v1.py:261); consuming selector [engine.py:481](/Users/jw115/mlb-model-fwd6/nfl/sim/engine.py:481).

Executed counterexample: in the pinned KC/CAR fixture, mark player `00-0030506` OUT and give him one inactive universe row. The gate passes and the actual `_build_player_context` excludes him. Prepend a duplicate row for that player with `active_flag=True`, leaving the inactive row last. **The gate still passes; the actual context now includes him.** The gate's dictionary keeps the last row, while the consumer includes any True row. This is a demonstrated input-validation bypass, not a claim that the present production table already contains duplicates.

Reject duplicate `(season, week, team, player_id)` universe keys before comparison; also validate flags as non-null booleans. Use the same canonical rows in validation and consumption. Test both duplicate orders and assert rejection before the worker starts.

**A3 — Replace the stale Sunday runbook and declare the roster-information cutoff.** [make_runbook.py:79](/Users/jw115/mlb-model-fwd6/research/nfl_sim/make_runbook.py:79), [make_runbook.py:124](/Users/jw115/mlb-model-fwd6/research/nfl_sim/make_runbook.py:124), [make_runbook.py:169](/Users/jw115/mlb-model-fwd6/research/nfl_sim/make_runbook.py:169); [fwd1_runbook.md:33](/Users/jw115/mlb-model-fwd6/research/nfl_sim/fwd1_runbook.md:33).

Executed counterexample: `group_windows` joins the 13:30Z IND@WAS game to the 17:00Z games and then through SNF, returning one **14-game Sunday window**. The committed runbook therefore starts before the Sunday 16:00Z pull, advertises a 12-hour window, refreshes without `usage.py`, and invokes the old unbootstrapped entry point. Regeneration reproduces the bad grouping.

Replace both generator and generated instructions with the two-window procedure in B4, the current bootstrap and `refresh_inputs.py`. Separately, choose and record whether late games use the 16:15Z roster snapshot or separate post-inactives windows. A 16:15Z freeze cannot contain the much later inactive announcements for afternoon games and SNF. Calling that population identical to a final-roster backtest would be false. This declaration can be made before outcomes without changing the frozen simulation.

## (B) P1 results and verifier claims

| P1 check | Verdict | Independent evidence |
|---|---|---|
| 1. Full baseline | **PASS** | 24 distinct files; 263 passed, 0 failed, 0 skipped. Per-file results below. |
| 2. Audit-13 extra-distribution counterexample | **FIXED** | Clean three-runtime baseline/current identity returns `[]`; replacing the worker with the saved temporary-HOME identity returns `runtime_worker: bottleneck 0.0.0 is not in the baseline`. |
| 3. Three production-command primaries in one registry | **PASS for requested checks** | First is its own baseline; second has no drift; third identifies the extra distribution. All have three runtimes, matching worker-derived probabilities and recomputable launcher hashes. |
| 4. Sunday operating procedure | **NOT READY as committed** | Generator combines the morning game and main slate. Corrected timing and conditional quote-age checks below. |
| 5b(i). Backtest/live input identity | **FAIL** | A1 is a numerical construction mismatch. Active universe is current-week roster state, not a statistic from games before W. QB-rating consumption claim is also incorrect. |
| 5b(ii). Current usage counts / OUT | **Counts HOLD; OUT evidence incomplete** | All five count pairs reproduce. Present OUT rows contain no skill-position universe member; a synthetic skill-player control passes exclusion, but A2 bypasses it. |
| 5b(iii). Splice | **Preservation HOLDS; acceptance conditional** | All eight pre-2026 table slices equal their backups. Fingerprint matches. Revised priors need a declared prospective input version. |
| 5b(iv). Inactives / schedule | **Residuals remain** | Early roster snapshots differ from final-roster backtests; builder schedule retrieval is not an archived explicit input. A1 makes the cutoff problem material. |

### B1. Completed baseline

Each file ran separately with a per-file log and no pytest cache. Every command completed within the brief's ten-minute limit. The initial detached launch did not produce a complete run; bounded tracked jobs completed it. Only the 24 distinct completed results below count. The sole warning is a pandas regular-expression capture-group warning in the suffix-name settlement fixture. There are no skip reasons because there were no skips. Linux 3.11 and standalone 3.13.7 were **not independently rerun**; the Mac execution used Python 3.13.1.

| File under `nfl/sim/tests/` | Exit | Exact final line |
|---|---:|---|
| test_forward_v1.py | 0 | 8 passed in 0.32s |
| test_freeze_v1.py | 0 | 4 passed in 0.95s |
| test_fwd2_anchor.py | 0 | 3 passed in 0.51s |
| test_fwd2_bundle.py | 0 | 5 passed in 0.26s |
| test_fwd2_experiment.py | 0 | 6 passed in 1.13s |
| test_fwd2_item0_fixes.py | 0 | 7 passed in 1.22s |
| test_fwd2_settlement.py | 0 | 12 passed, 1 warning in 1.23s |
| test_fwd2b_harness.py | 0 | 10 passed in 47.34s |
| test_fwd3_item0.py | 0 | 9 passed in 38.65s |
| test_fwd3_item1.py | 0 | 3 passed in 0.26s |
| test_fwd3_item2.py | 0 | 8 passed in 1.31s |
| test_fwd4_item0.py | 0 | 9 passed in 28.46s |
| test_fwd4_item1.py | 0 | 4 passed in 6.65s |
| test_fwd5_pin.py | 0 | 4 passed in 6.86s |
| test_fwd6_item0.py | 0 | 13 passed in 37.69s |
| test_fwd6_item1.py | 0 | 12 passed in 69.34s (0:01:09) |
| test_fwd6_item2.py | 0 | 9 passed in 32.14s |
| test_fwd6_item3.py | 0 | 5 passed in 10.82s |
| test_fwd6b.py | 0 | 39 passed in 128.31s (0:02:08) |
| test_fwd6c.py | 0 | 33 passed in 81.87s (0:01:21) |
| test_fwd6d.py | 0 | 33 passed in 77.18s (0:01:17) |
| test_fwd6e.py | 0 | 6 passed in 14.93s |
| test_fwd6f.py | 0 | 9 passed in 1.93s |
| test_fwd7a.py | 0 | 12 passed in 2.11s |

Logs: `/private/tmp/a14-index.jsonl` and `/private/tmp/a14-test_*.txt`.

### B2–B3. Dependency rule and production freeze

The union/comparison logic at [run_forward_v1.py:610](/Users/jw115/mlb-model-fwd6/nfl/sim/run_forward_v1.py:610) compares the recorded distribution identities, including version, location and RECORD hash, and requires consistent baseline interpreters. The normal receipt caller supplies all three runtime keys at [run_forward_v1.py:1383](/Users/jw115/mlb-model-fwd6/nfl/sim/run_forward_v1.py:1383).

I ran the actual `python3 -I -S -B .../fwd_bootstrap.py harness --week 4 --window-hours 2` command against synthetic pre-kickoff inputs in one temporary repository/registry. Fixtures used separate event IDs to avoid the duplicate-contract guard; source hashes were unchanged. No real primary was created.

| Run | Receipt run ID | `pilot` | Baseline run ID | Drift |
|---|---|---|---|---|
| First | `20261002T024029Z` | False | `20261002T024029Z` | `[]` |
| Second | `20261002T024243Z` | False | `20261002T024029Z` | `[]` |
| Third, extra temporary-HOME distribution | `20261002T024332Z` | False | `20261002T024029Z` | `bottleneck 0.0.0 is not in the baseline` for all three runtimes |

Each exited 0. Each emitted a 70-row sheet with 11 worker-matched probabilities; comparison with the sheet rebuilt from worker output gave maximum absolute probability difference **0.0**. Each had all three runtime objects, recomputable repository hashes and dependency-identity digest, the correct full launcher hash, a complete receipt, 45 wrapper-recorded input entries, no recorded violations and `verify_bundle=[]`. Planted startup/cache markers were absent. The third run is published **with drift recorded**, not halted: primary scoring must apply the declared dependency exclusion. This audit did not implement or validate a future scorer.

Launcher hash independently recomputed: `60f2b264d9fa60bfe41eb0ff2006330150bea76e861f4862670701485c2260bf`. The separately repeated bootstrap selftest loaded pandas, pyarrow.parquet and nfl.sim.run_week: **1090 dependency files, 6395 distribution files verified, 12 repo modules, exit 0**. Those verifier counts HOLD. Actual production processes load additional dependency files, so 1090 is a selftest count, not a universal run count.

There is one narrower contract gap: `dependency_drift(clean_baseline, {})` returns `[]`, as does deleting the `runtime_worker` key from an otherwise clean current mapping. It detects a present key whose value is missing, but does not require the key set itself. The normal caller constructs all three keys, so this is **not a reproduced publication bypass**. Make the helper validate both the three-key current mapping and three-runtime baseline; add tests independently of the caller.

### B4. Concrete Sunday procedure

The archived week-4 schedule contains IND@WAS on **Sunday October 4 at 13:30Z**, 13 later Sunday games starting at 17:00Z and ending with DET@CAR at **Monday October 5 00:20Z**, and ATL@NO at **Tuesday October 6 00:15Z**. PIT@CLE was the Thursday-night game at Friday October 2 00:15Z. Calling ATL/NO TNF is **refuted** by the saved schedule. Their absent injury rows do not, by themselves, prove whether a report was unpublished or missing from the local feed.

| Window | Concrete capture/run times | Three-hour rule at cutoff | Current numeric freshness |
|---|---|---|---|
| IND@WAS only | Manual props pull October 4 **12:15Z**; bootstrap harness **12:45Z**, `--week 4 --window-hours 1` | 30-minute props age if that capture succeeds. Game-line snapshot must be no earlier than **09:45Z**, no later than cutoff; preferably capture it at 12:15Z too. | IND and WAS both pass: last played 3, all seven selected weekly tables 4; current universe check passes. |
| Main + SNF, 13 games | Confirm the VM's actual **16:00Z** props capture arrived; harness **16:15Z**, `--week 4 --window-hours 9` | 15-minute props age if the actual capture is 16:00Z. Game lines must be no earlier than **13:15Z**, no later than cutoff; a 16:00Z capture is 15 minutes old. | All 26 participating teams pass the same `selected week >= 3 + 1` threshold and current-universe check. |

For the morning manual props capture, the existing documented CLI is `python3 nfl/pipeline/pull_hardrock_props.py --window-hours 2 --tag close --out-dir data/odds_archive/nfl/props/season=2026/manual`. Execute from the selected repository. This audit did not make that paid/live pull. Run each harness through `python3 -I -S -B nfl/sim/fwd_bootstrap.py harness`, not the runbook's direct Python entry point. Complete input refresh before these launch times; do not start the roughly eight-minute ratings rebuild at the last moment.

These are conditional age calculations, **not a claim that future Sunday quotes have already passed**. Check the actual accepted snapshots for every selected event, book and market; a scheduled pull is not evidence of a successful pull. A morning-only props pull does not supply the later slate. Exclude ATL/NO from both Sunday windows; their current missing injury reports need not block a Sunday-only bundle.

Refresh after final reports and again on game morning. If the experiment claims final-inactive parity, use separate later windows after those announcements and recapture quotes; otherwise declare that main/SNF use an early roster snapshot. Record feed retrieval time and status coverage. `injury_game_statuses=0` is recorded, not rejected; changing that to an unconditional `>0` requirement would wrongly reject teams genuinely reporting no game statuses. The numeric freshness gate passing is insufficient evidence of final-report completeness.

### B5. Recomputed Mac claims and input identity

| Verifier claim | Result from independent execution |
|---|---|
| PBP 2026 contains weeks 1–3 | **HOLDS:** 8,311 rows, unique weeks `[1,2,3]`. |
| Fit fingerprint remains `3638769c89030de0` | **HOLDS:** backup, refreshed inputs and FREEZE agree. |
| Historical splice preserved the fitted data | **HOLDS, with wider direct check:** pre-2026 slices of all eight tables equal the backup slices. The fingerprint itself covers 2021–2024, not 2025. |
| Only 53 QB / 32 kicker rows added | **HOLDS:** 53 and 32 new rows, all `(2026,4)`; every shared row equals its backup counterpart. |
| Metcalf targets/carries 24/0 | **HOLDS:** table 24/0, PBP 24/0. |
| Concepcion 20/4 | **HOLDS:** table 20/4, PBP 20/4. |
| Jeudy 5/0 | **HOLDS:** table 5/0, PBP 5/0. |
| Warren 14/38 | **HOLDS:** table 14/38, PBP 14/38. |
| Judkins 9/42 | **HOLDS:** table 9/42, PBP 9/42. |
| No week-4 OUT player active | **Numerically true but vacuous for skill players:** two report rows, Sam Cosmi (G) and Nick Cross (S), neither joins the skill universe. Zero skill OUT examples were available. A synthetic skill OUT control is excluded, but A2 defeats that exclusion with a duplicate. |
| Current freshness fails only ATL/NO | **HOLDS:** both fail missing week-4 injury report. All 28 Sunday teams plus CLE/PIT pass; weekly selections are 4. |
| Dry run: 14 games / 14 converged | **HOLDS on the saved artifact:** 14 events; final iteration for each of 14 games converged, across 43 iteration rows. I did not rerun that full 14-game simulation. |
| Dry run: 45 read files / 0 unproven | **HOLDS on the saved artifact:** 45 entries, zero violations, bundle verification `[]`. |
| Dry run: 66 of 257 two-way props matched | **HOLDS:** recounted 66/257. |
| Dry run: statuses 0 except WAS 2 | **HOLDS:** recomputed; confirms an incomplete final-status snapshot rather than final-roster parity. |
| Full rebuild fingerprint `a59adeafe48f62e6`; 2025 target-share difference 0.0004 | **NOT REPRODUCED for the current Mac inputs.** My full usage rebuild had 47,446 rows and maximum target-share difference **0.0** across 9,117 shared 2025 rows. Rebuilding usage and active universe while retaining the other six tables still gave `3638769c89030de0`. That is not a full eight-table ratings rebuild, nor the older cloud snapshot; it cannot refute a claim about unavailable earlier bytes. |
| Every old pilot HALTs with exactly 160 problems | **PARTIALLY VERIFIED:** an available old pilot bundle HALTs; CLE/PIT have respectively 3 and 7 current-universe mismatches. I did not reproduce the specific earlier 160-problem cloud run or enumerate every historical pilot. |

PBP target counts use pass plays and receiver IDs; carries use run plays excluding QB scrambles, matching the builder's definitions. The six historical PBP SHA prefixes independently matched the Mac note: 2020 `4126188fda860f3f`; 2021 `a9741a722a22dde8`; 2022 `6809039bb075367d`; 2023 `81984d68970d50a9`; 2024 `35d5a2e28e4f3873`; 2025 `cc0dd69de7cd91f0`.

**Row semantics, read in source and selectively executed:** usage and team/tendency/kicker estimators select plays with week `< W`; consumers select row W where present, otherwise the latest eligible earlier row. The new gate at [run_forward_v1.py:209](/Users/jw115/mlb-model-fwd6/nfl/sim/run_forward_v1.py:209) requires the selected weekly row to include the last played game. `_entering_weeks` adds the next row and caps at 22. The current counts and kicker table support the intended repair. Active universe is different: it is **week-W roster/injury state**, including information unavailable at an early live freeze. A1 additionally breaks depth construction before consumption.

**The QB claim needs correction.** In the actual fit initializer, [run_fit.py:39](/Users/jw115/mlb-model-fwd6/nfl/sim/run_fit.py:39), and live path, [run_week.py:1071](/Users/jw115/mlb-model-fwd6/nfl/sim/run_week.py:1071), no QB-rating table is supplied to the simulation. Instrumenting the real fit initializer recorded no read of `qb_ratings_weekly.parquet`; its keyword arguments were active_uni, kicker, league, player_usage, sit, team_r and tend. The player-context function's `qb_ratings` argument has zero load references. The added QB rows are real, but the claim that this numerical feature previously fell back to W−1 in the active fit/live path is **refuted**. Do not wire in a new QB feature as a silent audit fix.

**Splice judgment:** keeping frozen historical rows while generating 2026 inputs from information available before prediction is acceptable as a declared prospective input version. It does not establish exact historical information parity, and fingerprint equality does not establish correctness of 2026 construction. Archive the actual prior-source roster, depth, injury, PBP and schedule bytes with the refresh and record the version before outcomes. Do not tune the choice after seeing Sunday results. The prior-size assertion from the older cloud snapshot remains unverified as stated.

**Schedule residual:** [usage.py:357](/Users/jw115/mlb-model-fwd6/nfl/sim/usage.py:357) fetches the schedule inside QB assignment. Source inspection also shows different cutoff precision: historical PBP dates are midnight UTC, while the future schedule fallback uses actual Eastern kickoff converted to UTC. The numerical depth counterexample is executed; this separate QB cutoff observation is source reasoning, not a measured QB-output difference. Make schedule bytes and cutoff convention explicit and common to both builders. The forward bundle's later schedule snapshot does not retrospectively document the schedule fetched during input generation.

## (C) P2, additional defects and publication bypasses

I ran each N/Q mutation in a separate temporary copy, re-stamping a changed experiment-listed file. Files absent from the experiment manifest were not silently added to it. The unchanged focused control passed **24 tests**: all of test_fwd6f and test_fwd7a, two native-reader scan tests from test_fwd6d, and test_fwd6b's actual default-worker integration test. Mutation runs stop on the first failure. “Killed” means an assertion failed, not that all downstream behavior was exercised.

| Mutation | Status | Killing check |
|---|---|---|
| N1: ignore new distribution | KILLED | New-distribution drift test |
| N2: omit mtime from hash cache | KILLED | Same-size, same-inode rewrite |
| N3: omit executable comparison | KILLED | Alternate executable |
| N4: compare only RECORD hash | KILLED | Worker-identity test's additional identity variants |
| N5: fail to restore FileSystem | KILLED | Restore after uninstall/error |
| N6: recognize only file URI | KILLED | Non-file URI refusal |
| N7: ignore PathLike | KILLED | Native-reader PathLike refusal |
| N8: omit launcher hash | KILLED | Full launcher hash assertion |
| N9: omit receipt drift field | KILLED | Actual default-worker receipt integration |
| N10: skip baseline self-consistency | KILLED | Inconsistent baseline identities |
| Q1: return to last-played threshold | KILLED | Usage without latest game |
| Q2: skip universe check | KILLED | Refreshed fixture expects positive active count |
| Q3: make injuries record-only | KILLED | Required-input membership assertion |
| Q4: ignore Out/Doubtful | KILLED | Changed OUT status |
| Q5: skip missing roster rejection | KILLED | Missing roster/report fixture |
| Q6: skip missing injury rejection | KILLED | Missing roster/report fixture |
| Q7: QB loop observed weeks only | KILLED | AST assertion that both loops call the helper |
| Q8: remove cap | KILLED | Entering-weeks boundary assertion |
| Q9: keep rebuilt historical rows | KILLED | Splice fixture |
| Q10: remove restoration | KILLED | Rebuild-step failure fixture |

**The six audit-13 focused survivors, N2–N7, are now killed.** The saved `pa.OSFile` alias is rejected by the unmodified reference scanner, and its dedicated test passes. This is a finite static check, not a proof covering arbitrary Python indirection. The accepted RECORD-matched native-code trust boundary was not expanded or attacked.

**Refresh rollback claim is too broad.** At [refresh_inputs.py:155](/Users/jw115/mlb-model-fwd6/nfl/sim/refresh_inputs.py:155), the final freshness report is outside the rollback `try/except`. I executed a controlled refresh fixture whose rebuild and fingerprint checks succeed and final freshness returns False: **exit 1, eight tables changed, none restored**. Failures within the protected rebuild do restore, as the existing test and Q10 show. This does not by itself bypass the later bundle freshness gate. Before operational reliance, either publish a validated generation atomically or explicitly document that final-readiness failure leaves refreshed tables installed. Do not interpret exit 1 as “old inputs restored.” This can be repaired after A1/A2 if the Sunday procedure explicitly handles this outcome.

**Values reaching a primary:** the three unmodified production-command experiments did not show a non-worker probability reaching a primary frozen value. Their reconstructed worker-derived probability values matched exactly. A2 is instead a bad-input acceptance path **into the worker**, and A1 supplies inconsistent precomputed inputs **to the worker**. Correct output provenance cannot repair either. No absolute claim of absence of further bypasses follows from these checks.

## (D) New surviving mutations

All eight below produced **24 passed, exit 0** in the stated focused control. They were **not rerun against all 263 tests**, and they are not assertions that the unmodified code contains each mutation. They identify missing distinctions in the current focused acceptance tests.

| Operator / location | Why it survives; required distinguishing case |
|---|---|
| Delete `baseline: a runtime is missing` in dependency_drift | Tests do not remove one baseline runtime while the other two remain valid. |
| Choose the last primary receipt rather than the first in the drift block | A one-primary integration fixture cannot distinguish registry order. Add three runs and assert both later baseline IDs equal the first. My independent unmodified three-run check did pass. |
| Remove the `ast.Name` branch of `_references` in test_fwd6d | Attribute/import cases still pass. Add a bare banned-reader-name reference case. |
| Remove situational tendencies from `_team_freshness` | Existing stale-table fixtures do not isolate this table. Keep all others fresh and make only situational tendencies stale. |
| Exclude only Out, not Doubtful | Existing status counterexample uses Out. Add a Doubtful skill player with otherwise matching rows. |
| Cap `_entering_weeks` at 21, not 22 | Current low-week and already-observed-week-22 examples cannot distinguish it. Input whose highest observed week is 21 must add 22. |
| Drop pre-2021 rows from splice | Fixture covers 2025/2026 only. Include 2020 and assert exact preservation too. |
| Restore only player_usage_weekly | Failure fixture changes only that table. Corrupt a second table, then verify all eight original byte hashes after failure. |

The mutation runner and exact operators are preserved at `/private/tmp/a14_mutations.py`; per-case output is `/private/tmp/a14-mut-<operator>.txt`. A killed Q2 via a positive-count assertion, or Q7 via AST structure, should not be presented as comprehensive behavioral coverage; A2 and the QB-consumption finding show the distinction.

## (E) Sunday verdict

**NO-GO for a primary Sunday at `7429e9dbfdf6909746b934a5bdf0259efb67995d`.** The 263-test baseline, dependency-drift repair and production provenance checks hold, but the live depth pipeline changes the model's current-week usage inputs relative to historical construction, and duplicate universe rows defeat the new OUT gate. Fix A1 and A2, replace the stale runbook, and declare the roster cutoff before the first window. A new GO would require the repaired pin to reject the duplicate fixture, preserve depth/usage under the truncated-PBP equivalence check, pass its baseline, and pass a production-command smoke run with actual fresh inputs. If those conditions are not met, any Sunday run must remain a declared pilot and must not be promoted to primary after its results are known.

Execution evidence is retained outside the repository: [input recomputation](/private/tmp/a14-inputs.json), [depth counts](/private/tmp/a14-depth-probe.json), [usage counterfactual](/private/tmp/a14-usage-rebuild.json), [OUT duplicate probe](/private/tmp/a14-gate-probes.json), [refresh rollback probe](/private/tmp/a14-refresh-probe.json), [selftest](/private/tmp/a14-selftest.json), and [additional checks](/private/tmp/a14-more-checks.json). Current copied input hashes are in the input recomputation file. The copied local usage SHA256 is `c1b6592960d62bad8b621e0d1717a8e3b2fa09543517ad6b298c993549909050`.

Limits and discarded attempts: process-list access was blocked, so job completion was established from logs and returned exits. The official NFL schedule page could not be opened; schedule claims above are from the archived local schedule, not independently confirmed against that website. An initial usage-rebuild attempt pointed to missing historical PBP files and was discarded; all reported numeric deltas use the corrected seven-season rebuild, which reproduced the live control exactly. A fixture-directory collision interrupted the production driver after the first success; resumption retained the same registry and completed the second and third runs. No result from an incomplete attempt was counted.
