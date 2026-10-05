# ChatGPT audit #16 — FWD7c / D273
9c7bf9dfac0eff13ffc2477585cbb796f40f62c1

**COMPLETE. Verdict: NO-GO as primary for both Sunday windows at this pin.** The original audit-15 null-date counterexample is fixed, including the real-worker comparison. Two other cases explicitly requested in P1 still pass changed inputs to the worker: a missing historical cutoff and a valid-looking date contradicting the schedule. Neither defect is present in the clean archive I inspected; both are reproduced input-validation failures, not allegations that Sunday's outcomes have leaked into the saved smoke.

D273 was read in full before tests. Code was extracted from the exact pin into `/private/tmp/nfl-audit16-9c7bf9dfa`; all 52 manifest code hashes matched. The local checkout's HEAD was checked again at completion. Runtime: local Python 3.13. Tests, builders, mutations and bootstrap runs used disposable copies. No source, real input, receipt, primary freeze or bet was changed. The only repository write is this requested report. Frozen simulation/calibration mechanics and D269's accepted native-I/O boundary were not re-audited.

## (A) Must-fix before a primary Sunday, ranked

### 1. Missing historical cutoffs silently change the priors used for current predictions

**Location:** [usage.py:480–491](https://github.com/jwallace115/mlb-model/blob/9c7bf9dfac0eff13ffc2477585cbb796f40f62c1/nfl/sim/usage.py#L480). The validation at line 482 covers only `_newest`. The loop at line 491 silently skips an older season/week without a cutoff. That older active universe is used to compute depth-group priors at lines 538–621; current usage selects the preceding season's priors at lines 669–675.

**Executed counterexample:** Copy the current D273-v3 inputs and historical PBP into a temporary directory. In **2025 week 3 only**, replace `game_date` with null, leaving every play/outcome field unchanged; there is no 2025 schedule snapshot. Rebuild with the unmodified pinned builders. Preserve all installed pre-2026 table rows, exactly as the refresh splice does.

- The build **does not halt**. Current active-universe rows remain identical, so the new depth-rank gate sees no missing current layer.
- All **2,561 current-season usage rows** change target and carry shares. For week 4 specifically, **506/506** change; maximum target-share delta **0.0395420448**, carry-share delta **0.0722871148**.
- The forward freshness gate **passes all 28 Sunday teams**.
- A real bootstrap IND@WAS dry run succeeds, converges, verifies its bundle, and records **45 reads, zero violations**. Clean/changed outputs have **82/80 rows**, with **78 shared proposition keys**. **40/78 calibrated probabilities change**, maximum **0.1038**; all 78 raw probabilities change. The fitted-history fingerprint still passes because the stored historical table rows were preserved.

**Required repair:** Validate the historical season/week cutoffs needed to derive the current inputs and their priors, not just the newest roster season. A missing cutoff must halt or demonstrably leave the derived current result unchanged. Do not repair this by merely splicing the historical output rows back: that happens after historical information has already changed current priors. Add this multi-season regression and repeat the worker comparison. Intentional carry-forward rows need an explicit rule, not blanket missing-date tolerance.

**Boundary:** A historical-only fixture, where 2025 is the newest season, correctly halts. The failure requires the ordinary multi-season build containing 2026. All six original 2020–2025 PBP files retained their pre-audit hashes.

### 2. Taking the minimum of contradictory dates does not guarantee live/rebuild identity

**Location:** [usage.py:405–421](https://github.com/jwallace115/mlb-model/blob/9c7bf9dfac0eff13ffc2477585cbb796f40f62c1/nfl/sim/usage.py#L405). `min(ds)` accepts contradictory dates; `_require_cutoffs` checks existence, not consistency. [refresh_inputs.py:97–103](https://github.com/jwallace115/mlb-model/blob/9c7bf9dfac0eff13ffc2477585cbb796f40f62c1/nfl/sim/refresh_inputs.py#L97) checks weekly coverage but does not resolve this disagreement.

**Executed counterexample:** Start with the named D272-v2 archive, whose PBP has weeks 1–3. Keep its valid full schedule. Add one outcome-free row:

`season=2026, week=4, game_id=2026_04_PIT_CLE, game_date=2026-09-30`

The schedule places that game on **October 1**. The live cutoff is October 1; the added row moves it to September 30.

- Week-4 active-universe depth ranks change in **27/800 rows**.
- **50/505 target shares** and **49/505 carry shares** change; maximum target-share delta **0.0102700988**. Affected teams include DEN, LV, SF and TEN.
- All **28 Sunday teams pass** the gate.
- Real DEN@SF bootstrap runs both succeed and converge, with **45 reads, zero violations**, and valid bundles. Both produce 84 rows; **81 proposition keys are shared**. **35 calibrated probabilities change**, maximum **0.0578**; 79 raw probabilities change, maximum **0.0192**. Three keys on each side are unmatched, so the paired comparison does not describe the entire output difference.

**Required repair:** Before deriving cutoffs, reject contradictory valid dates/season/week identities for a PBP game versus the archived schedule, or enforce a declared immutable schedule cutoff. Compare by game identity; merely requiring equal weekly minima would wrongly reject a partial PBP week containing only later games. Test both directions of disagreement and the transition from schedule-only to schedule-plus-PBP.

**Reasoning:** `min(schedule_date, later_observed_pbp_date)` preserves the live cutoff only if the new date is not earlier. It cannot establish identity unconditionally. The actual current archive has **49 distinct PBP games, zero schedule-date mismatches, zero null dates, and zero wrong-season rows**. Thus this is a demonstrated validation gap, not a mismatch found in the clean Mac run.

## (B) P1 results

| Requested check | Verdict | Executed evidence |
|---|---|---|
| P1.1 — each forward file separately | **PASS** | **25 files, 291 passed, zero failures/skips**. Each file ran in a separate invocation; bounded groups stayed under ten minutes. |
| P1.1 — four usage files, tune deselected | **PASS** | `test_usage_5b`: 13 passed/1 deselected; `test_usage_pit_5f`: 3; `test_usage_pit_5j`: 2; `test_board_5j2`: 4. Total **22 passed, 1 deselected**. |
| P1.2 — audit-15 A1, null and unparseable dates before TNF | **FIXED** | With weeks-1–3 PBP, both malformed rows leave all **4,102 active-universe rows and 2,056 usage rows identical**. Complete and isolated layer-3 QB maps also remain identical. |
| P1.2 — real IND@WAS worker comparison | **FIXED** | D273 clean/null: **82/82 shared rows, zero raw or calibrated probability changes**. Both real bootstrap runs succeed. |
| P1.2 — discriminating D272 negative control | **REPRODUCED** | Same earlier archive and malformed row: **43/78 shared calibrated probabilities change**, maximum **0.0596**; 77 raw probabilities change, maximum **0.0396**. Output counts 82/81. This was re-executed, not copied from audit 15. |
| P1.3 — snapshot missing week 4 / null week-4 gameday | **PASS in the live-week case** | Each halts `build_active_universe` with missing week `[4]` before the worker. No week-4 PBP date was available to mask the missing snapshot coverage. |
| P1.3 — disagreeing valid dates | **FAIL** | A2: changed tables and changed real-worker probabilities pass. Choosing the earlier date is conservative about information timing but does not preserve identity. |
| P1.3 — all-null historical PBP week, no snapshot | **PARTIAL / BLOCKER** | Historical season alone halts. A normal multi-season build silently skips its historical depth layer and changes current priors: A1. |
| P1.3 — no active-player depth ranks | **PASS** | New gate: clean and D273-null tables pass **28/28** Sunday teams; D272-null tables halt **28/28** for no depth ranks. A separate case retaining ranks only on inactive players also halts. |
| P1.4 — actual TNF transition and W=4 identity | **PASS on the actual dates** | Current-input rebuild with PBP through week 3 versus through week 4: week-4 **800 universe / 506 usage rows identical**; complete and layer-3 QB maps identical. Sunday-only subset: **700 / 441 rows identical**. W=2 and W=3 also pass. |
| P1.5 — saved Mac smoke | **PASS as a dry-run artifact** | Recomputed **14 events, 28 teams, 14/14 converged, 45 reads, zero violations, 66/257 matched**. Bundle verification returns no errors. All selected weekly table rows are week 4; injury-status counts are zero except WAS=2. |
| P1.5 — independent current-input IND@WAS bootstrap | **PASS as a dry run** | Exit 0, converged, valid bundle, **45 reads/zero violations**, 723 week-4 depth ranks. Used archived quotes with `--dry-run --allow-stale-quotes`; this does not demonstrate fresh Sunday capture or a primary publication. |
| P1.5 — runbook and deadlines | **PASS** | Regenerated runbook equals the pinned file except generation timestamp; arithmetic below. |

The first usage-test attempt lacked the untracked PBP files in the Git-only temporary extraction and failed for missing data. Those setup failures were retained in the logs and superseded by the four complete reruns using verified local historical PBP and the D273 archive. No test or production parameter was edited to obtain the passing baseline. The initial offline D271 schedule stub also needed its expected `.to_pandas()` interface; the corrected negative control failed the intended assertion.

**Recomputed verifier claims:**

| Claim | Independent result |
|---|---|
| D273-v3 archive and installed inputs | **HOLDS:** all **13 archived file hashes** match; all eight installed ratings tables match that archive; all pre-2026 output rows equal the pre-refresh backup. |
| Fingerprint | **HOLDS:** `3638769c89030de0`. |
| PBP and schedule | **HOLDS:** **8,497 PBP rows**, weeks 1–4; **272 schedule games**, weeks 1–18. |
| Current universe | **HOLDS:** **800 week-4 rows, 723 non-null depth ranks, zero duplicate player/team keys, zero null flags**, boolean dtype. |
| Historical team-week coverage | **HOLDS:** **572 team-weeks in each of 2021–2025**, and **160 in 2026**, with zero groups lacking an active player's rank. |
| Current archive equals rebuild | **HOLDS:** current-season **4,102 universe / 2,561 usage rows** exactly equal their independent rebuilds. |
| D273 versus D272 clean full-table bytes | **HOLDS for equality:** independently serialized full tables are byte-identical: **47,446 usage rows and 89,753 universe rows**. The stated **89,737** universe count is **not reproduced** on the named earlier Mac archive. The cloud claim does not supply a separately identifiable input manifest that explains those 16 rows. |
| Cloud null-control percentages | Target-share claim **HOLDS rounded:** **505/2,056 = 24.5623%**. Depth percentage **not reproduced exactly:** **1,444/4,102 = 35.2023%**, rounding to **35.2%, not 35.3%**. The substantive lost-depth defect is reproduced. |
| Selftest | **HOLDS:** launcher hash matches; **1,090 dependency files, 6,395 distribution files, 12 repository modules**. |
| Freshness for all 32 teams | **HOLDS:** independently called report returns True and reports 32 teams. This is freshness relative to the code's entering-week definition. |
| Five player counts versus PBP before week 4 | **HOLDS:** targets/carries are Metcalf **24/0**, Concepcion **20/4**, Jeudy **5/0**, Warren **14/38**, Judkins **9/42**. |
| Injury exclusion | **HOLDS:** week-4 report has **291 rows**, **7 Out/Doubtful**, **2 matching skill players**, **0 active** among those two. |
| Revised QB test distinguishes D271 | **HOLDS with the required live-week fixture:** the exact new test body passes D273 and fails an assertion on D271 using archived weeks-1–3 PBP and an offline schedule. The checked-in test itself reads real PBP, so its “week 4 has no PBP” premise is now stale. It should own its PBP-free fixture. FWD7c's separate synthetic tests do own that condition. |

**Sunday procedure, unchanged:**

| Window | Refresh completed by | Props capture | Harness | Quote-age arithmetic / horizon |
|---|---|---|---|---|
| IND@WAS | **Sun Oct 4 12:15Z** | Manual **12:15Z** | **12:45Z**, `--window-hours 1.5` | Props age 30 minutes; three-hour game-line range **09:45–12:45Z**; horizon ends 14:15Z and includes the 13:30Z kickoff. |
| Main + SNF | **Sun Oct 4 15:45Z** | VM **16:00Z**, confirm arrival | **16:15Z**, `--window-hours 9` | Props age 15 minutes; game-line range **13:15–16:15Z**; horizon ends Mon 01:15Z and includes SNF at 00:20Z. |

The historical refresh deadlines remain operational prerequisites, not proof that the Friday injury file is Sunday's final file. Neither Sunday capture nor final-report refresh has happened in this audit.

**PIT/CLE correction:** their latest completed game is indeed week 4. But `_last_played_weeks(pbp, 4)` deliberately filters `week < 4` at [run_forward_v1.py:137](https://github.com/jwallace115/mlb-model/blob/9c7bf9dfac0eff13ffc2477585cbb796f40f62c1/nfl/sim/run_forward_v1.py#L137), so it returns **3**, not 4, for both. Calling it for week 5 returns 4. Neither Sunday window contains PIT/CLE. Their week-4 team rows are not selected for either window; the executed TNF transition also leaves Sunday's usage/universe rows unchanged.

## (C) P2: bypasses and remaining qualifications

**Executed bypasses are input-quality failures, not missing-read proofs.** A1 and A2 pass altered, properly recorded materialized inputs to the genuine worker. Their read sets and bundle hashes succeed. The historical raw PBP is used during rebuilding, upstream of the worker; its effect arrives inside `player_usage_weekly.parquet`. A hash proving which table the worker read does not prove that the table's historical derivation was valid.

**No new substitution of a non-worker value into a primary frozen probability was demonstrated.** The full forward suite, including the real-worker and publication checks, passed. I read the unchanged sequencing around copied-input fingerprints, worker execution, read-set classification, output validation, fill and pre-freeze verification. I did not publish a new primary freeze. This is a bounded negative finding, not proof against every possible bypass; RECORD-matched native I/O remains outside scope.

**Snapshot writer checks:** the real writer rejects a missing week, a null/unparseable date, a replacement from another season, and a non-REG replacement. Failed validation also leaves an existing snapshot unchanged. Weekly coverage is weaker than calendar consistency, hence A2.

**S4 equivalence challenge:** removing the schedule NaT filter changes the helper's result for an all-NaT schedule week with no valid PBP: the original has no key; the mutant has a key valued NaT. Both required-cutoff checks halt. With valid PBP for that week, both select the same valid date, because PBP candidates are appended before the schedule's NaT. Non-required missing historical cutoffs are skipped in both versions. Thus S4 violates the helper's literal “no NaT keys” contract but is **behaviorally equivalent at the current caller boundary for these cases**. It does not cause the earlier S1 poisoning behavior. A1's historical omission exists in both versions.

**Input version and declaration:** `D273-v3` is in code and the actual manifest. Clean D272/D273 byte equality is independently reproduced. The previously accepted prospective roster-cutoff policy is unchanged; it is not a reason for this NO-GO.

**Refresh wording is only partly corrected:** the lead docstring at lines 11–12 now limits restoration to steps 0–6, matching the source. Its final sentence at [refresh_inputs.py:33](https://github.com/jwallace115/mlb-model/blob/9c7bf9dfac0eff13ffc2477585cbb796f40f62c1/nfl/sim/refresh_inputs.py#L33) still says an exception means old tables were restored. A readiness-report exception at line 216 is outside the restore block. Fix that sentence; it is a documentation follow-up, not a third Sunday blocker.

**Legacy `fourth_down_go_rate`:** D273 explicitly declares its non-point-in-time status and defers quarantine. The relevant builder and engine files are unchanged from the prior pin; the limited field-reference check still finds legacy context assignments, with no new decision-path wiring. I did not rerun the earlier numerical tendencies study or reopen engine mechanics. Do not describe the entire tendencies table as point-in-time identical.

## (D) Mutations

All mutants were isolated and changed manifest-listed files were re-stamped. The unchanged focused control passed **52 tests**: FWD7c, FWD7a, FWD6f, two static-reader checks from FWD6d, and FWD6b's real default-worker-path test. These are focused-suite results, not claims that every mutant ran against all 291 tests. No mutant failed merely because its original manifest hash was left stale.

| Operators | Result |
|---|---|
| R5 duplicate guard; R6 flag guard; R10 last-primary baseline; R13 omit snapshot; R14 omit archive; R16 merge windows; R18 report success when not ready | **7/7 KILLED** |
| S1 keep NaT PBP; S2 maximum PBP date; S3 maximum combined date; S5 omit schedule season filter | **4/4 KILLED** |
| S6 inclusive layer-3 cutoff; S7 inclusive depth cutoff; S8 omit universe requirement; S9 omit layer-3 requirement; S10 omit depth gate | **5/5 KILLED** |
| S11 omit dtype check; S12 implicit `not pilot`; S13 omit archive table copies; S14 wrong snapshot path; S15 omit snapshot validation; S16 16:00Z boundary | **6/6 KILLED** |
| S4 omit schedule NaT filter | **SURVIVES, 52 passed**; caller-equivalence qualification above |

All **seven audit-15 survivors** are therefore killed: their corresponding operators are S2, S6, S11, S12, S13, S14 and S16.

**New mutation probes:**

| Mutant | Result and meaning |
|---|---|
| N1 — remove `season == SEASON` from snapshot validation | **SURVIVES, 52 passed.** Add a fixture whose missing 2026 week is supplied only by 2025. The independent writer probe above distinguishes this case. |
| N2 — remove `game_type == REG` from snapshot validation | **SURVIVES, 52 passed.** Add a non-REG row as the only coverage for a required week. |
| N3 — count any player's rank, including inactive players, in the depth gate | **SURVIVES, 52 passed.** Current test clears all ranks. Add active ranks all null with at least one inactive rank retained; the independent original-code probe correctly halts. |
| N4 — remove the NaT-value arm from `_require_cutoffs` | **SURVIVES, 52 passed.** Redundant on values produced by the unmodified filtered helper; not a demonstrated new production bypass. A direct helper-contract test can cover it. |
| N5 — always choose PBP over schedule when both exist | **KILLED** by the earlier-schedule cutoff test. |

These survivors are test gaps or equivalent operators, not assertions that the unmodified source contains those changes. More consequential than any survivor are the two unmutated failures in A: add multi-season missing-history and conflicting-game-date integration cases.

## (E) Per-window verdict

| Window | Verdict at this pin | Basis |
|---|---|---|
| **IND@WAS — Sun Oct 4, 12:45Z harness** | **NO-GO as primary** | A1 reaches this exact game's real worker and changes 40 calibrated probabilities despite passing the gate and fingerprint. |
| **Main + SNF — Sun Oct 4, 16:15Z harness** | **NO-GO as primary** | A1 affects every week-4 usage row; A2 additionally reaches DEN@SF's real worker and changes 35 calibrated probabilities. |

The clean archive, full baseline, original malformed-date repair and ordinary TNF identity checks pass. The refusal is specifically because the requested bad-input cases still produce changed, apparently admissible predictions. A narrow guard-only repair should preserve valid-input bytes: reject missing historical cutoffs needed for current priors and resolve/reject schedule/PBP contradictions. Re-run these counterexamples, clean byte identity, the affected worker comparisons and the baseline at the repaired pin. Fresh Sunday quotes, the scheduled refreshes and publication checks remain required; no primary designation should be assigned retrospectively after outcomes.

Evidence retained outside the repository: [baseline index](/private/tmp/a16-valid-index.jsonl), [completed usage reruns](/private/tmp/a16-usagevalid-index.jsonl), [archive/saved-smoke recomputation](/private/tmp/a16-inputs.json), [PIT and malformed-date rebuilds](/private/tmp/a16-pit.json), [bootstrap negative controls and 28-team gates](/private/tmp/a16-probabilities.json), [conflicting-date rebuild](/private/tmp/a16-conflict.json), [DEN/SF probability deltas](/private/tmp/a16-conflict-probs.json), [historical-null rebuild](/private/tmp/a16-history.json), [IND/WAS historical-null probability deltas](/private/tmp/a16-history-probs.json), [full-table byte checks](/private/tmp/a16-fullbytes.json), [edge cases and corrected D271 control](/private/tmp/a16-edgechecks-rerun.json), [runbook/selftest](/private/tmp/a16-misc.json), [mutation operators](/private/tmp/a16_mutations.py), [mutation results](/private/tmp/a16-mutations.log). Detailed scripts and subprocess logs are under `/private/tmp/a16*`. No live feed, external schedule website, VM state, future injury report or Sunday capture was accessed.
