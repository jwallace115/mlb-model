# Audit #21 — FWD7j/FWD7k, D279/D279b
b7d4a9916a87074bed17e09d0c0a5d5942359c3f

COMPLETE — 2026-10-04. **NO-GO for PRIMARY at this pin in all three windows.** The audit #20 counterexamples are repaired, but a different cell-parsing error reaches the actual primary worker and changes predictions.

I read D277–D279/D279b and both committed Mac run records, then executed the pinned code from one temporary extraction. No engine, anchor, calibration, pricer, K1 or fit review was performed; the frozen prediction path was exercised as a black box. The only repository file written is this reply. No checkout, commit, live refresh or primary freeze was performed.

## (A) Must-fix before a primary, ranked

**1. [P1] Validate the complete contents of each player row, rather than counting only matching TD cells.** [nfl/sim/official_injuries.py:143–146](https://github.com/jwallace115/mlb-model/blob/b7d4a9916a87074bed17e09d0c0a5d5942359c3f/nfl/sim/official_injuries.py#L143); the row-level stripping at [179–184](https://github.com/jwallace115/mlb-model/blob/b7d4a9916a87074bed17e09d0c0a5d5942359c3f/nfl/sim/official_injuries.py#L179) does not inspect the contents it removes.

Counterexample, executed on a copy of the real 23:10Z capture: in the Jayden Daniels and Rachaad White rows, replace the fifth cell:

~~~html
<td>Out</td>
~~~

with:

~~~html
<th>Out</th><td></td>
~~~

These are six-cell rows under a five-column header. Their fifth cell still says Out; their sixth is blank. They must HALT as unsupported structure. Instead, the parser ignores TH, finds five TDs, and treats the final blank TD as Game Status. The independent TR count cannot detect this: there are still 318 player rows, including all 15 WAS rows.

**Executed chain:** actual official_step with the altered capture supplied in place of network acquisition → actual usage.main → actual refresh splice preserving historical rows → actual non-pilot IND@WAS bootstrap. The synthetic capture record has the correct byte count and SHA for the supplied bytes.

| Measurement | Clean capture | Six-cell counterexample |
|---|---:|---:|
| Parsed rows / WAS rows | 318 / 15 | 318 / 15 |
| Daniels / White status | Out / Out | blank / blank |
| WAS week-4 active count in freshness | 16 | 18 |
| Active flags changed across weeks 4–5 | — | 4, all false→true |
| Bootstrap exit / pilot flag | 0 / false | 0 / false |
| IND and WAS official_verified | both true | both true |
| Converged games | 1 | 1 |
| Read-set entries / violations | 45 / 0 | 45 / 0 |
| Prediction rows | 86 | 82 |

There are 75 common prediction keys. **All 75 sim_p values and 43 cal_p values change; maximum absolute change is 0.1392, or 13.92 percentage points.** Eleven clean prediction rows disappear and seven appear. Bundle verification reports no mismatches.

This is an admission failure, not a missing-read allegation: the recorded inputs themselves are incorrectly interpreted. The actual clean archive has exactly five cells in each of its 318 rows; I did not find this defect already present in that archive.

**Required repair:** validate every direct cell and all remaining content within a player TR. Require exactly five supported cells in the declared order; either explicitly support TH or reject it. Reject extra cells and unconsumed sibling text/tags before overlay writes. Add this exact counterexample as a regression, including the real refresh-to-primary path, while retaining the passing split-body, attributed-body, entity and nested-span controls.

Evidence: [counterexample result](/private/tmp/a21-e2e-th-two-statuses.json), [worker log](/private/tmp/a21-worker-th-two-statuses.log), [prediction comparison](/private/tmp/a21-prediction-comparison.json), [reproduction script](/private/tmp/a21-th-counterexample.py). This is the sole demonstrated code blocker from this audit.

## (B) P1 re-tests and verifier claims

| P1 check | Verdict | Executed evidence |
|---|---|---|
| 1. Forward and usage baselines | HOLDS | 29 forward files separately: **362 passed**. Four usage files separately: **22 passed, 1 tuning test deselected**. No failed or skipped baseline tests. test_fwd7g: 45; test_fwd7f: 12. |
| 2. Audit #20 A1: split tbody, end to end | FIXED | Actual refresh step, usage builder/splice and non-pilot bootstrap: 318 rows, WAS 15, Daniels and White Out. Both derived tables equal the archived tables. All **86 predictions equal clean**, across every field except run ID and generation timestamp; zero sim_p or cal_p changes. |
| 2. Attributed tbody and unsupported structure | FIXED for these cases | Attributed body also completed the actual non-pilot worker with the same 86 predictions and unchanged tables. Stray content caused actual official_step to HALT before changing any copied input. Nested table, second header and unclosed row also HALTed in direct parser probes. See A for the distinct within-row failure. |
| 3. Bad raw PBP with clean prebuilt tables | FIXED | Blank posteam at row 6404, game 2026_03_HOU_IND, play_id 173: bootstrap **exit 1 at build_bundle**, naming that row and the empty-posteam violation. No worker read set/output was produced. [run_forward_v1.py:507–513](https://github.com/jwallace115/mlb-model/blob/b7d4a9916a87074bed17e09d0c0a5d5942359c3f/nfl/sim/run_forward_v1.py#L507). |
| 4. Y1–Y3 and committed campaign | FIXED / claim HOLDS | Each old survivor now fails its new test. The pinned W/X/Z script executed all 60 operators: **59 killed, X2 alone survived**. No anchor misses or collection-error “kills.” Details in D. |
| 5. Real archive, rebuild and point-in-time | HOLDS for measured claims | Independent HTML count 318; identified 318; 32 teams, 16 matchups, 138 game statuses. Installed 2026 tables exactly match rebuild. Weeks 2–4 exactly match truncated-PBP rebuilds, including starting-QB and layer-3 maps. Details below. |
| 6. Operating procedure and MNF finality | Text fixed; future actions still required | Current-pin GO and skill-only unmatched-row language are present in the pinned runbook. The 23:10Z capture meets the declared MNF final-report deadline. Game-morning refreshes and each window’s evidence commit have not happened as part of this audit. A still prevents GO. |

Baseline evidence: [per-file results](/private/tmp/a21-base-index.jsonl). End-to-end controls: [clean](/private/tmp/a21-e2e-clean.json), [split](/private/tmp/a21-e2e-split.json), [attribute](/private/tmp/a21-e2e-attribute.json), [stray](/private/tmp/a21-e2e-stray.json), [raw PBP](/private/tmp/a21-e2e-blank-posteam.json).

All four prediction runs used the real isolated bootstrap with **pilot=false**, dry-run mode and an archived quote snapshot with allow-stale-quotes enabled. They test the primary data/worker path; they are not live quote-freshness checks or primary freezes.

**Independent numerical recomputations — not acceptance-note repetitions:**

- **HOLDS — archive identity.** All **16/16** refresh-manifest file hashes match the 20261003T231047Z archive. Its capture is 405,289 bytes, retrieved **2026-10-03T23:10:55.062576Z**, SHA256 **2711f526d7a38581ba1a6a7a7ea79a2244ae7e457cf88c393c51bd35cefcb83f**. The committed capture record and refresh manifest match the archive.
- **HOLDS — identification and coverage.** Independent BeautifulSoup count and pinned parser both give **318** rows; **318** map to IDs. The skill-boundary comparison is **92 skill / 226 non-skill / 0 cross-boundary matches**. The official check returns verified for all **32** teams. ATL: **7 rows, 3 statuses**; NO: **13 rows, 5 statuses**.
- **HOLDS, with a narrower meaning — pre-overlay feed.** The retained feed is **598,708 bytes**, with **313** week-4 rows and **130** nonblank game statuses. Installed injuries have **318** week-4 rows and **138** statuses. There are **313 shared IDs, 5 additions, 0 removals**, and **7 status changes on shared IDs**. Thus the feed was not identical to the final official report. The particular claim “zero skill players Out/Doubtful officially but not in the feed” does hold: **0**.
- The five additions are ATL Jake Matthews and Yasir Abdullah; NO Nathan Shepherd, Treyton Welch and Jayden Price. Shared-ID changes are Samson Ebukam and Divine Deablo to Questionable; Kaden Elliss, Carl Granderson and Anfernee Jennings to Out; Noah Fant and Pete Werner to Questionable. The overlay exactly reproduces installed injuries; all other season/week rows are unchanged. [Feed comparison](/private/tmp/a21-inputs.json), [clean counts](/private/tmp/a21-clean-cell-feed-counts.json).
- **HOLDS — Noah Fant comparison.** Directly comparing the committed active tables at 9d747c96a and 2c696a9e1 yields **only two changed cells**: Noah Fant’s injury_status, Active→Questionable, in weeks 4 and 5. **Zero active_flag changes; all non-2026 rows identical.**
- **HOLDS — depth and fingerprint.** Week 4 has **802** active-universe rows, **724** with depth_order; the recomputed fit-window fingerprint is **3638769c89030de0**.
- **HOLDS — rebuild/PIT.** Installed versus rebuilt 2026 active/usage tables: **4,106 / 2,554 rows**, exactly equal. Week-specific active/usage counts are **786 / 513** for W2, **794 / 518** for W3, **802 / 503** for W4. Every compared field and both QB-map comparisons match when PBP is truncated to weeks strictly before W. This is the tested PBP point-in-time property; it does not establish live/backtest final-roster parity. [PIT evidence](/private/tmp/a21-pit.json).
- **HOLDS — saved full-slate artifacts.** I inspected both 20261003T232031Z and 20261004T002659Z: **28/28 verified teams, 14/14 final-iteration convergences, 45 reads = 14 run files + 31 repository files, zero violations**. Both bundles verify; corresponding input hashes match the archive. All 31 repository-read hashes in each match the pinned bytes. These are independently inspected saved runs, not two new full-slate runs by me. [Read-hash check](/private/tmp/a21-saved-read-hashes.json).

**Other D279/D279b claims:**

- **Feed retention HOLDS:** actual official_step writes the pre-overlay copy at [refresh_inputs.py:137](https://github.com/jwallace115/mlb-model/blob/b7d4a9916a87074bed17e09d0c0a5d5942359c3f/nfl/sim/refresh_inputs.py#L137); the archive contains it and its manifest hash verifies.
- **Empty-injury refusal HOLDS:** executing the retained freshness helper with WAS’s consumed injury set empty returns “WAS: no week-4 injury report in the bundle.” Keep that declared refusal for week 4. A truly empty table parses as zero rows in the passing regression. [run_forward_v1.py:252](https://github.com/jwallace115/mlb-model/blob/b7d4a9916a87074bed17e09d0c0a5d5942359c3f/nfl/sim/run_forward_v1.py#L252), [executed refusal](/private/tmp/a21-empty-refusal.json).
- **Runbook correction HOLDS as text:** [fwd1_runbook.md:12–18](https://github.com/jwallace115/mlb-model/blob/b7d4a9916a87074bed17e09d0c0a5d5942359c3f/research/nfl_sim/fwd1_runbook.md#L12) requires game-morning refresh and evidence commit; [line 47](https://github.com/jwallace115/mlb-model/blob/b7d4a9916a87074bed17e09d0c0a5d5942359c3f/research/nfl_sim/fwd1_runbook.md#L47) requires GO at the CURRENT pin. Input version is D279-v9.
- **Roster-move correction HOLDS:** comparing 3635e300c→9d747c96a independently gives **6 active_flag, 6 status and 6 injury_status changes**. The latter are Active→CUT/RES for the three roster moves across weeks 4–5. [Evidence](/private/tmp/a21-roster-correction.json).
- **D279b HOLDS for its tested guards:** a commented-out row leaves the real parse unchanged; template content HALTs; the expanded committed tests cover the other prohibited elements, unclosed comment and uppercase TR case. Z11–Z13 are killed. This does not cure the cell-content failure in A.
- Earlier live-page counts of 313 and reports of the previous disk-full incident are historical observations. I did not replay those live requests or independently reconstruct that disk incident.

## (C) P2 and other bypasses

**Confirmed:** the within-row TH/extra-TD case in A silently changes a consumed status and passes the real primary worker. Stray text inside a TR is also silently ignored; it belongs to the same incomplete row-content validation problem, not a second demonstrated prediction-changing chain.

**Passing controls, executed against copied real HTML:** numeric space entities, line-break/tab whitespace in the player name, attributes on TR/TD, nested spans around visible name text, split/attributed bodies and a commented-out row preserve the clean parsed table. A five-cell row whose status TD alone is changed to TH HALTs; adding the blank TD is what makes the malformed six-cell row pass. Stray inter-row content, nested tables, second headers and unclosed rows HALT.

The current archive independently has **318/318 five-cell player rows**. Consequently, A demonstrates what the gate admits under a structural source change; it is not a claim that the current capture contains the malformed rows.

No additional prediction-changing bypass was demonstrated in these probes. This is a bounded parser/admission re-audit, not an exhaustive proof over arbitrary HTML or a renewed frozen-engine audit. [Probe results](/private/tmp/a21-probes.json).

## (D) Surviving mutations

| Set | Result |
|---|---|
| W1–W24 | **24 killed** |
| X1–X23 | **22 killed; X2 survived** |
| Z1–Z13 | **13 killed** |
| Independent reruns of Y1, Y2, Y3 | **All killed** by their named new tests |
| Additional mutation removing HTML entity decoding | **Killed** by the first parser-content test |

The unmutated focused control passes **58 tests**. Each committed kill has an actual failed test, not a collection/import failure. The campaign uses the committed operators and test selection; its temporary-test destination was redirected inside the one managed audit directory.

**X2 remains admission-equivalent for this rule:** removing blank→None normalization at [usage.py:433](https://github.com/jwallace115/mlb-model/blob/b7d4a9916a87074bed17e09d0c0a5d5942359c3f/nfl/sim/usage.py#L433) does not remove the independent blank rejection at [line 438](https://github.com/jwallace115/mlb-model/blob/b7d4a9916a87074bed17e09d0c0a5d5942359c3f/nfl/sim/usage.py#L438). Blank inputs still HALT; nonblank inputs are unchanged by that assignment. X2 passes all 58 focused tests. It is not a demonstrated admitted-input bypass.

The six-cell source-input counterexample survives the current production guards; it is not counted as an additional code mutation. A passing mutation campaign therefore does not close A.

[Campaign results](/private/tmp/a21-cowork-mutations.json), [campaign log](/private/tmp/a21-mutations.log), [independent mutations](/private/tmp/a21-own-mutations.json). After restoration, all **361 checked extracted Python/JSON/Markdown blobs** match Git, and all **53 pinned manifest hashes** match.

## (E) PRIMARY decision at this pin, per window

| Window | Verdict at b7d4a9916 | Required procedure after the code blocker is repaired and the resulting pin receives GO |
|---|---|---|
| IND@WAS, Sun Oct 4, 13:30Z kickoff | **NO-GO** | Game-morning refresh finished by **12:15Z**; manual props **12:15Z**; commit/push the capture evidence before the **12:45Z** harness; all gates pass. |
| Sunday main + SNF, 13 games from 17:00Z | **NO-GO** | Use the declared morning refresh; if refreshed again, finish by **15:45Z**. Evidence must describe the capture actually used and be committed before the harness. VM props **16:00Z**, harness **16:15Z**. |
| MNF ATL@NO, Tue Oct 6, 00:15Z kickoff | **NO-GO** | Monday game-day refresh, completed by **Mon Oct 5 23:00Z**; manual props **23:00Z**; capture evidence committed before the **23:30Z** harness; all gates pass. |

**MNF finality specifically:** YES, the archived Saturday **23:10:55.062576Z** capture satisfies the declared **Saturday Oct 3 20:00Z** final-report threshold, by 3h 10m 55.062576s. ATL and NO both verify when checked against a later cutoff. It does not replace the required Monday refresh.

At the audited pin, declare each window pilot before its harness. A passing runtime gate cannot override this NO-GO. TNF remains pilot; there is no retrospective promotion.

## (F) Disk and cleanup

Before, actual df -h / output:

~~~text
Filesystem        Size    Used   Avail Capacity iused ifree %iused  Mounted on
/dev/disk3s1s1   460Gi    13Gi    26Gi    34%    484k  272M    0%   /
~~~

After deletion, actual df -h / output:

~~~text
Filesystem        Size    Used   Avail Capacity iused ifree %iused  Mounted on
/dev/disk3s1s1   460Gi    13Gi    26Gi    34%    484k  272M    0%   /
~~~

**Created and deleted:** /private/tmp/audit21-work, including tree, inputs, pit, probes, empty-probe, archive, runtime-tmp, all per-file pytest directories, own-tests and mut-tests. The root no longer exists. There was one extracted source tree, no per-mutant full-tree copies. The committed tests’ temporary fixture directories stayed inside the managed root and were removed after each file.

The managed root contained **231,365,163 regular-file bytes** immediately before final deletion. Only **226 small flat evidence files, 1,650,888 bytes total** remained at the cleanup measurement; the cleanup JSON itself was written afterward. My a21util bytecode file was removed from the pre-existing /private/tmp/__pycache__; that directory and other audits’ files were preserved.

All bounded jobs completed without a timeout. The longest baseline file took 126.93 seconds; the longest baseline batch was about 404 seconds. No tool block prevented a required audit check. An incidental process-inventory command was sandbox-blocked; completion was established through the job handles and result files.

[Cleanup inventory and disk readings](/private/tmp/a21-cleanup.json), [source-restoration check](/private/tmp/a21-source-restoration.json). No temporary audit directory is being left for another session to clean up.
