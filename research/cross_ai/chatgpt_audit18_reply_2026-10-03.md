# ChatGPT audit #18 — FWD7e / D275
e875c0f6273242b3ffb7db31fa8fe1cf17487a7a

**COMPLETE. NO-GO for either primary Sunday window at this pin.** Audit #17's three counterexamples are fixed. A different missing-field counterexample still reaches the actual worker and changes predictions. The archived injury data also do not establish the final-report coverage required by D272. Proposed D276 does not cure that evidence gap.

Read-only audit. I read D275 before testing and extracted code from the exact pin, independently checking all 52 experiment-manifest file hashes. Tests, mutations, rebuilds and worker runs used disposable directories. The only repository write is this reply; nothing was committed, checked out, refreshed in production, or frozen. Execution used Python 3.13.1, pandas 2.3.3 and PyArrow 23.0.1 on this Mac, including the real bootstrap's `-I -S -B` path. I did not independently reproduce the claimed Linux 3.11 or standalone 3.13.7 environments. Engine mathematics, calibration, pricing and the accepted D269 native-I/O boundary were not re-audited.

## (A) Must-fix before a primary Sunday, ranked

### A1 — Validate the other consumed aggregation keys before filtering or grouping

**[nfl/sim/usage.py:89](https://github.com/jwallace115/mlb-model/blob/e875c0f6273242b3ffb7db31fa8fe1cf17487a7a/nfl/sim/usage.py#L89), [usage.py:140](https://github.com/jwallace115/mlb-model/blob/e875c0f6273242b3ffb7db31fa8fe1cf17487a7a/nfl/sim/usage.py#L140), [usage.py:144](https://github.com/jwallace115/mlb-model/blob/e875c0f6273242b3ffb7db31fa8fe1cf17487a7a/nfl/sim/usage.py#L144), [usage.py:1327](https://github.com/jwallace115/mlb-model/blob/e875c0f6273242b3ffb7db31fa8fe1cf17487a7a/nfl/sim/usage.py#L1327); also [ratings.py:50](https://github.com/jwallace115/mlb-model/blob/e875c0f6273242b3ffb7db31fa8fe1cf17487a7a/nfl/sim/ratings.py#L50) and [ratings.py:70](https://github.com/jwallace115/mlb-model/blob/e875c0f6273242b3ffb7db31fa8fe1cf17487a7a/nfl/sim/ratings.py#L70).**

**Executed counterexample:** in the archived `pbp_2026.parquet`, row 6404 is game `2026_03_HOU_IND`, play 173: Daniel Jones completes a nine-yard pass to Tyler Warren (`00-0040128`). Set **only `posteam = None`**. The new identity/date validator accepts it. The production usage-builder functions finish; all 802 week-4 active-universe rows remain identical, but 16/506 week-4 target shares change, maximum absolute change **0.00647382545**. Across 2026's 2,561 usage rows, 32 change (**1.2495119%**). The ratings loader also accepts the bad row.

I installed the rebuilt current-year usage/active-universe rows into a disposable copy with the other archived inputs, then ran the **actual pinned IND@WAS bootstrap worker**. It exits 0, converges, passes bundle verification, and reports **45 reads, zero violations**. Against the clean run, there are 82 shared prediction rows, with **17 calibrated probabilities changed, max 0.0503**, and **39 raw probabilities changed, max 0.0242**. Output cardinality changes from 82 to 83. One matched opinion-sheet probability changes by **0.0132**. All 28 Sunday teams also pass the freshness gate with these changed usage tables.

Separate executed edits of the same completed pass's `play_type = None` and `receiver_player_id = None` also build and produce the same 16 week-4 target-share changes. Only the `posteam` form was run through the worker. I did not run an eight-table production refresh or publish a primary file for these new cases.

**Required repair:** add a shared, context-dependent raw-PBP admission check in both loaders, before exclusions/groupbys. Require team keys for scrimmage plays, a play type consistent with recorded play-event flags, a receiver for a completed pass, and the applicable passer/rusher identity for attributed pass/run events. Reject contradictions with season/file/row/game/play diagnostics. Preserve legitimate administrative rows, sacks, throwaways and explicit special-play exclusions. Do not blanket-ban every missing player ID or silently discard contradictions. Cover current and prior seasons, assert failure before writes and eight-table restoration, and rerun this worker comparison after the repair. Correct D275's broader “cannot drop a play on a null key” claim: it is false at this pin.

### A2 — Establish final-report completeness per window; do not equate status counts with it

**[nfl/sim/run_forward_v1.py:217](https://github.com/jwallace115/mlb-model/blob/e875c0f6273242b3ffb7db31fa8fe1cf17487a7a/nfl/sim/run_forward_v1.py#L217), [fwd1_runbook.md:12](https://github.com/jwallace115/mlb-model/blob/e875c0f6273242b3ffb7db31fa8fe1cf17487a7a/research/nfl_sim/fwd1_runbook.md#L12), [fwd1_runbook.md:18](https://github.com/jwallace115/mlb-model/blob/e875c0f6273242b3ffb7db31fa8fe1cf17487a7a/research/nfl_sim/fwd1_runbook.md#L18); incorrect acceptance count at [fwd7e_mac_run.md:93](https://github.com/jwallace115/mlb-model/blob/e875c0f6273242b3ffb7db31fa8fe1cf17487a7a/research/nfl_sim/fwd7e_mac_run.md#L93).**

**Executed counterexample:** the real archive passes freshness for all 32 teams and the saved smoke passes for all 28 Sunday teams. Yet game-status coverage is **IND@WAS 1/2; main + SNF 0/26**. The Mac report's “3 of 28 Sunday teams” is wrong: CLE and PIT played Thursday. Sunday's count is **1/28**, WAS. All **291 week-4 `date_modified` values are null**. The injury-file hash is identical across the 12:21-start/12:29-completion, 18:31-start and 21:29-start refresh archives. A later refresh timestamp therefore supplies no proof that final reports arrived.

**D276 judgment:** per-window classification is preferable; the proposed 75% threshold is not a sound primary-admission criterion. As a logical counterexample, 20 main-window teams can each have one status while all six other teams' reports are missing; D276 passes. Even 26/26 can pass while an omitted Out player is absent from an otherwise populated team's report. Conversely, a complete report may have no designations: the Chargers did in 2023 week 10. [NFL report](https://www.nfl.com/news/week-10-nfl-injury-report-for-2023-season).

Use this concrete pre-outcome rule instead:

1. Before each harness start, archive the latest official final game-status report and subsequent updates available at that refresh cutoff for **each participating team**, including explicit reports with zero designations. Record game/team, report stage, source URL, source publication/update time when available, retrieval UTC, and content hash.
2. Reconcile its game statuses, particularly every Out/Doubtful player, against the exact injury-file bytes and active flags to be bundled. Classify each team `verified complete`, `verified empty`, or `unverified/mismatch`. Absence of rows alone never establishes `verified empty`.
3. Primary requires **2/2** verified teams for IND@WAS and **26/26** for main + SNF, plus the code repair in A1. Commit the per-window classification, source hashes and refresh-manifest hash before the harness; bind that decision to the inputs actually consumed. Any unverified team makes that whole predeclared window **pilot**, permanently. If inputs change, redo the decision before the harness. No retrospective promotion.

This is 100% **verified completeness**, not 100% of teams having a designated player. The official reports are evidence for the admission decision; silently substituting them as new model inputs would be a separate change requiring a declaration and provenance.

Feed timestamps can supplement this procedure, but cannot replace it. The nflverse dictionary defines `date_modified` as when injury information was updated, not a final-report completeness certificate; here that field is entirely unavailable anyway. [nflverse dictionary](https://nflreadr.nflverse.com/articles/dictionary_injuries.html). The proposed 75% rule is defensible only as a coarse **pilot trigger**, or as an explicitly different “feed as available” experiment—not proof of the existing final-report claim.

## (B) P1 results

| Required check | Verdict | Executed evidence / limit |
|---|---|---|
| Forward baseline, each file separately | **HOLDS** | **305 passed**, 27 files, zero failed/skipped. |
| Four usage files, tune excluded | **HOLDS** | **22 passed, 1 deselected**: 13 + 3 + 2 + 4. |
| Original one-row null week | **FIXED** | Actual `usage.main()` rejects row 6404; zero parquet writes; existing tables unchanged. Refresh controller restores **8/8** deliberately disturbed temporary tables. |
| Original nullable-Int64 missing season | **FIXED** | Same pre-write rejection and **8/8** restoration. |
| Original historical null game ID | **FIXED** | Exact audit-17 historical row **6911** rejects before writes and restores **8/8**. Mac verifier's row **5529** also rejects. |
| Negative controls on `2afe33878` | **HOLDS** | Fresh old-code rebuilds succeed; their output bytes equal the earlier counterexample outputs. Each null-week/null-season case changes **32/2,561** current-year target shares and **16/506** week-4 shares. Historical null-ID changes **2,561/2,561**, including **506/506** week-4 shares. |
| Repeat IND@WAS old-worker comparisons | **HOLDS** | Both malformed controls pass the old worker: **17** calibrated changes (max **0.0503**), **39** raw changes (max **0.0242**), 82 shared rows; clean D274 and clean D275 worker probabilities are identical. |
| Blank/empty game ID; week 2.5, 0, 23 | **FIXED** | Each rejects before any table write. Empty ID was placed inside an otherwise valid existing game. |
| Season stored as numeric string | **PARTIAL** | `usage.main()` stops before writes, but with **TypeError**, not the new identity diagnostic. Both loaders accept all **8,497** string-season rows, leaving zero rows equal to integer 2026. There is no demonstrated forward-output bypass from this variant. Enforce or normalize types consistently at admission; do not claim that the row validator rejects this representation. |
| Bad 2020 row, both loaders | **FIXED** | Both reject real 2020 row 5778 with null game ID. Ratings is tested with usage's directory deliberately different. |
| Clean Int64 season / float week | **HOLDS** | Build succeeds; both current-year output files and both **full** output files are byte-identical to clean output. |
| Archive / installed / independent rebuild | **HOLDS** | All **13** archived source/table hashes match. All **8** installed tables match archive bytes and preserve pre-2026 rows. Independently rebuilt full active-universe **89,757** rows and usage **47,951** rows exactly match installed values after canonical key sorting. Six other rating builders were not independently rebuilt. |
| Full D275 versus full D274 | **HOLDS** | Both serialized full tables byte-identical. Active SHA256 `8a4005308ae58ce80220356535f3f11ca3288eb22a4e88029862ccdecad501c4`; usage `9662ab93327f94b650db2a8a1558ba389b68189ccb5d83d902028733ca135fa4`. |
| Point-in-time W=2–4 | **HOLDS** | Truncating PBP to weeks < W preserves every tested active/usage value and starting-QB map, including layer 3. Active rows **786/794/802**; usage rows **513/518/506**. |
| Other three reported failure shapes | **HOLDS** | Historical null dates, one-week-early date and one-day-late date reject. Also replayed all six exact Mac-run input shapes at the admission/cutoff functions, including its outcome-free week-5 TB@DAL rows; all reject. |
| Saved smoke | **HOLDS, limited** | Bundle verifies; **14/14** final convergence states true, **45** read entries, zero violations, **66/257** two-way sheet matches. This does not establish injury completeness or primary readiness. |
| Independent current IND@WAS smoke | **HOLDS, limited** | Actual isolated bootstrap, exit 0, convergence, **45** reads, zero violations; bundle verifies. Lab run deliberately allowed archived stale quotes and used dry-run. No live quote-freshness or primary publication claim. |
| Runtime / runbook | **HOLDS** | Selftest verifies **12** repo modules, **1,090** dependency files, **6,395** distribution files. Generated runbook matches apart from generation timestamp. |
| Final reports and Sunday refresh prerequisites | **NOT MET / future** | This archive cannot prove final-report completeness. Refresh once completeness is evidenced, then finish the Sunday-morning refresh by **12:15Z** for the **12:45Z** harness. Main-window refresh must finish by **15:45Z** for **16:15Z**. These future actions were not performed by this audit. |

Rollback checks used the actual refresh controller and actual usage builder, with feed acquisition stubbed to local archived inputs. I deliberately changed all eight temporary table files before the builder failed, then compared all eight restored hashes. This tests restoration without a network pull or writes to installed tables.

Additional verifier claims recomputed: fingerprint **`3638769c89030de0` HOLDS**; week-4 depth **724/802 HOLDS**; injury rows **291**, Out/Doubtful **7**, overlapping skill players **2**, still active **0**, all **HOLD**. All five published player-count checks hold: Metcalf **24/0**, Concepcion **20/4**, Jeudy **5/0**, Warren **14/38**, Judkins **9/42** targets/carries. **“3 of 28 Sunday teams” FAILS: 1/28.** D275's cloud-specific 303,300-row / 0.8% claims cannot be reproduced from that unavailable staged dataset; this Mac's seven seasons total **303,486** and the executed single-play controls change **1.2495119%** of 2026 target shares. Do not conflate those datasets.

## (C) P2 and remaining bypasses

**Confirmed:** A1 is a semantic input-admission bypass, not an unrecorded-read exploit. The altered raw source and derived table are present and hashed; an accurately recorded bad value still produces a bad prediction. The new worker comparison demonstrates that distinction. The source's freshness gate checks selected weeks, roster/active-flag identity and presence of depth ranks; it does not reconstruct usage counts/shares from PBP.

I counted missing fields in all **303,486** real PBP rows before prescribing checks:

| Condition | Observed count | Interpretation |
|---|---:|---|
| Missing `posteam`, all rows | 16,536 | Missingness exists in non-scrimmage rows; blanket rejection is wrong. |
| Missing `posteam` or `defteam`, pass/run rows | **0 each** | The executed completed-pass counterexample contradicts this observed invariant. |
| Missing `play_type`, all rows | 8,863 | Administrative/non-play rows need explicit allowance. |
| Missing `play_type` with completed-pass or rush-attempt flag | **0** | Check the flags before dropping an untyped row. |
| Missing receiver on a pass | 12,853 | Receiver-less sacks/throwaways must remain admissible. |
| Missing receiver on a **completed** pass | **0** | The edited Warren reception is not a legitimate receiver-less pass. |
| Missing rusher on a designed run | **0** | Validate only plays included in that attribution rule. |
| Missing passer on a pass | **0** | Another applicable identity invariant, rather than requiring passers on every row. |

These are empirical counts and proposed admission predicates, not a claim that every future special play is impossible. If a genuine exception appears, identify its type and explicit treatment before consuming it; do not make `groupby`'s null-dropping behavior the policy.

**No additional non-worker primary-value substitution demonstrated.** I read the current worker-output validation, `fill_sheet` and freeze path and ran the forward tests covering them. Matched `sim_v1` probabilities derive from worker `cal_p`, with declared side inversion, clipping and rounding; no-view rows retain their declared book-based value. Bundle/read-set reconciliation and pre-publication verification remain present. The independent counterexamples used dry runs and never created a primary file. This is a bounded negative result, not proof of every possible Python/native-I/O path; the accepted D269 boundary remained out of scope.

## (D) Mutations and survivors

Each mutation was isolated in a copied pinned tree and the changed source hash was re-stamped. The focused control is **70 passing tests**: FWD7e, FWD7d, board 5j2, FWD7c, FWD6f, FWD7a, both FWD6d static-reader checks and the FWD6b real-default-worker isolation check. This is the stated mutation scope, not a claim that every mutation was run against all 327 baseline tests.

| Mutation | Result | Evidence |
|---|---|---|
| V1 null game ID allowed | **KILLED** | Missing/blank historical identity test fails. |
| V2 blank game ID allowed | **KILLED** | Same test's whitespace case fails. |
| V3 raw `season != s` | **KILLED** | Nullable-Int64 missing-season test fails. |
| V4 remove `wk.isna()` arm | **SURVIVES; equivalent** | 70 tests pass; explanation below. |
| V5 remove integral-week check | **KILLED** | Fractional-week case fails. |
| V6 remove range checks | **KILLED** | Out-of-range historical case fails. |
| V7 omit first identity raise | **KILLED** | Later-row null-week test fails. |
| V8 usage loader skips validation | **KILLED** | Loader half of later-row test fails. |
| V9 ratings loader skips validation | **KILLED** | Bad-2020 loader test fails. |
| V10 ratings validates usage's directory | **KILLED** | Separated-directory bad-2020 test fails. |
| V11 require only weeks ≤18 | **KILLED** | Postseason week-19 test fails. |
| V12 require only seasons ≥2025 | **KILLED** | Older-season cutoff test fails. |
| Prior T1 / T2 / T4 / T8 | **ALL KILLED** | Historical missing dates, conflicting dates/weeks, snapshot contradictions and historical requirements. |
| New N1: change `wk < 1` to `wk < 0` | **SURVIVES; non-equivalent** | All 70 tests pass; original rejects a validly dated 2020 game labeled week 0, mutant accepts and returns week 0. |
| New N2: deduplicate games before raw identity checks | **KILLED** | Later-row null-week test fails. |

**V4 HOLDS as equivalent under this implementation.** `wk` is explicitly converted to ordinary float64. A missing value is NaN, and `NaN != round(NaN)` is true. I compared the two predicates on **31 values across object, Int64, Float64 and float64 inputs**, including missing values, infinities, fractions, range edges and numeric/non-numeric strings: identical masks. This conclusion depends on the float64 conversion remaining intact.

**N1 is a real test gap**, at [test_fwd7e.py:69](https://github.com/jwallace115/mlb-model/blob/e875c0f6273242b3ffb7db31fa8fe1cf17487a7a/nfl/sim/tests/test_fwd7e.py#L69): committed cases cover 2.5 and 23, not 0. Add an isolated week-zero game/season test so a separate multi-week conflict cannot accidentally kill it. The current unmutated code rejects zero correctly, so this survivor is not itself an active production defect. Add the A1 context-dependent missing-key counterexamples as regression tests with the repair. The string-season diagnostic and full-output clean-dtype checks also need stronger committed coverage.

## (E) Per-window decision and operating procedure

| Window | Primary at this pin/archive? | Reason |
|---|---|---|
| IND@WAS, Sunday 2026-10-04 12:45Z | **NO-GO** | A1 reaches this exact worker; status coverage is only **1/2**, with no final-report completeness evidence. |
| Main + SNF, Sunday 2026-10-04 16:15Z | **NO-GO** | Shared admission defect remains; status coverage is **0/26**, with no final-report completeness evidence. |

**Both windows are pilot-only on the present evidence.** For a future primary decision, repair A1, verify the regression cases, and commit the per-window completeness rule and its actual evidence before either window starts. D276's per-window approach and irrevocable pilot classification are appropriate; its 75% count cannot establish the existing D272 final-report promise. A scoring declaration alone does not repair the code defect.

After the feed demonstrably carries the relevant final statuses, refresh and retain the source/table manifests. On Sunday finish the early-window refresh by **12:15Z**, make the manual props pull at **12:15Z**, verify the exact final injury evidence and fresh game lines, and launch at **12:45Z** with the declared 1.5-hour window. For main + SNF, finish its refresh by **15:45Z**, confirm the **16:00Z** props pull arrived, verify that window's final injury evidence and game lines, and launch at **16:15Z** with the declared 9-hour window. Quote age must satisfy the live three-hour limit. Declare a failed/unverified window pilot before its harness and never promote it after outcomes. These times and the runbook generation were verified; future feed arrival, pulls and successful refreshes remain unverified.

### Reproduction evidence retained outside the repository

- [Per-file baseline results](/private/tmp/a18-valid-index.jsonl) and [baseline driver](/private/tmp/a18_baseline.py).
- [Original/variant failures](/private/tmp/a18-cases.json), [exact old historical failure](/private/tmp/a18-original-hist.json), [rollback results](/private/tmp/a18-restore.json), [exact historical rollback](/private/tmp/a18-restore-original.json).
- [Clean rebuild/PIT results](/private/tmp/a18-pit.json), [dtype and missing-key results](/private/tmp/a18-more.json), [fresh old-code rebuilds](/private/tmp/a18-old-builds.json).
- [Archive/smoke recomputations](/private/tmp/a18-inputs.json), [additional verifier checks](/private/tmp/a18-evidence.json), [new worker and exact Mac-shape results](/private/tmp/a18-finish-checks.json).
- [Mutation results](/private/tmp/a18-mutations.log), [mutation operators/runner](/private/tmp/a18_mutations.py), [new worker run](/private/tmp/a18-smoke-null-posteam.json).

The experiment code snapshot remains at `/private/tmp/nfl-audit18-e875c0f62`. Counterexample construction is in [a18_cases.py](/private/tmp/a18_cases.py), [a18_more.py](/private/tmp/a18_more.py), [a18_smoke.py](/private/tmp/a18_smoke.py) and [a18_finish_checks.py](/private/tmp/a18_finish_checks.py). No unread required file or blocked audit check is being presented as verified.
