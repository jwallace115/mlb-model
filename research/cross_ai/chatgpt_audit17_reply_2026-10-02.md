# ChatGPT audit #17 — FWD7d / D274
2afe33878f54548821c6e8ec4521d8d6b48dcdbe

**COMPLETE — NO-GO as primary for both Sunday windows at this pin.** Both audit-16 blockers are fixed. One remaining blocker is reproduced in unmodified D274: missing PBP identity fields survive validation, silently remove plays from aggregation, and change worker probabilities. This is a fault-injection result; the clean archive's identity/date fields passed the independent checks.

D274 was read in full before execution. Code was extracted from the exact pin; all **52 manifest hashes** matched. The `nfl/sim` tree is unchanged between the implementation commit `b9bae4830` and the audited pin. Tests, mutations, rebuilds and worker runs used temporary copies. Original historical PBP and archived-input hashes were rechecked unchanged. No source, real inputs, receipts, primary freeze or bet was changed. This report is the only repository write.

## (A) Must-fix before a primary Sunday, ranked

### 1. Validate missing identity fields on every PBP row before grouping or deduplication

**Priority 1. Location:** [usage.py:400](https://github.com/jwallace115/mlb-model/blob/2afe33878f54548821c6e8ec4521d8d6b48dcdbe/nfl/sim/usage.py#L400), especially lines 400–408 in `_pbp_game_dates`. The downstream aggregation that drops these plays is at [usage.py:140](https://github.com/jwallace115/mlb-model/blob/2afe33878f54548821c6e8ec4521d8d6b48dcdbe/nfl/sim/usage.py#L140).

**Executed counterexamples on the D274-v4 archive:** Find `game_id=2026_03_HOU_IND`, `play_id=173.0`, an IND pass with receiver `00-0040128`. Preserve its game ID, date, outcome and all other play values. In separate cases:

1. Replace that single row's `week` with null, using the ordinary float representation of an integer column containing a missing value.
2. Represent `season` as pandas nullable `Int64` and replace that single row's season with `<NA>`; all other season values remain 2026.

Both builds succeed. The week-4 active universe remains identical, but **16/506 week-4 target shares change**, maximum absolute delta **0.00647382545**. The IND/WAS gate passes.

Both were then executed through the genuine bootstrap and worker. Each succeeds, converges, produces a valid bundle and records **45 reads, zero violations**. Compared with the clean current-input IND@WAS run:

- Clean/changed outputs contain **82/83 rows**, with **82 shared proposition keys**.
- **17 calibrated probabilities change**, maximum **0.0503**.
- **39 raw probabilities change**, maximum **0.0242**.
- There is also one added proposition key, outside those paired comparisons.

**Why the validator misses them — verified source behavior:** `nunique` ignores missing weeks, so the game still appears to have one week. The first row retained by `drop_duplicates("game_id")` has a valid week. For nullable seasons, `p["season"] != s` produces `<NA>` for the missing value, and `.any()` skips it. Later grouping by season/week/game ID drops the affected play. Thus the validated, deduplicated view conceals missing fields in the raw rows actually aggregated.

**Historical form of the same defect:** Set only the `game_id` of one IND receiving play in historical `2025_03_IND_TEN` to null. The history has no schedule snapshot. `groupby("game_id")` skips the missing ID; the build succeeds. All **506 current week-4 target shares change**, maximum **0.000269032135**, and the gate passes all **28 Sunday teams**. Current active-universe rows remain identical. This variant was executed through rebuilding and the gate; I did **not** run its own worker comparison. By contrast, the same null-ID probe in 2026 is caught by the schedule join.

**Required repair:** Explicitly reject missing `season`, `week` and `game_id` on the raw rows, independently of pandas dtype and row order, before grouping/deduplication. Require every row's season to equal the file season, every week to be a valid integer week, and every game ID to be present. Then enforce exactly one date/week per game. Do not “repair” this by filtering bad rows: that would preserve the silent loss of plays. A normalized alternative must feed the actual aggregation and demonstrably preserve the clean result.

Add regressions for a missing field on a later row of an otherwise valid game, nullable integer season, and historical missing game ID. Require a HALT before table writes and verify rollback. The broader 40-row missing-week/season probes happened to halt later with a pandas `ValueError`; that accidental halt does not cover the one-row cases that reach the worker.

## (B) P1 results

| Check | Verdict | Independent evidence |
|---|---|---|
| P1.1 — forward files separately | **PASS** | **26 files, 298 passed**, zero final failures/skips. |
| P1.1 — four usage files | **PASS** | `test_usage_5b`: 13 passed/1 deselected; `test_usage_pit_5f`: 3; `test_usage_pit_5j`: 2; `test_board_5j2`: 4. Total **22 passed, 1 deselected**; tune was not run. |
| P1.2 — audit-16 A1, historical null dates | **FIXED** | On the original multi-season shape, the actual `usage.main()` halts for invalid 2025 game dates. **Zero parquet-write calls**; pre-existing output bytes remain unchanged. |
| P1.2 — audit-16 A2, PIT@CLE dated September 30 | **FIXED** | On the named D272-v2 weeks-1–3 archive, `usage.main()` halts for the game-specific schedule contradiction. **Zero parquet-write calls**; existing output bytes unchanged. |
| P1.2 — refresh rollback | **PASS** | Actual refresh controller plus actual failing usage step, with feeds replaced by offline inputs: both original counterexamples restore **all eight tables** byte-for-byte. Pre-failure partial writes were deliberately injected, so restoration was not vacuous. No ratings step ran after the usage exception. |
| P1.2 — D273 real-worker negative controls | **REPRODUCED** | Historical-null IND/WAS: **40/78 shared calibrated probabilities change**, max **0.1038**. Early-date DEN/SF: **35/81 change**, max **0.0578**. Old code was executed again, rather than importing the previous verdict. |
| P1.3 — partially null historical game date | **PASS** | One invalid date inside an otherwise valid game halts the actual usage entry point before writes. |
| P1.3 — two dates / two weeks / wrong non-null season | **PASS** | Each halts before output writes. A missing rostered historical week is also rejected by the committed regression. Missing identity values are a separate failure: A1. |
| P1.3 — snapshot week mismatch / PBP game missing from snapshot | **PASS** | Both halt the actual usage entry point before writes. |
| P1.3 — only later games present in PBP | **PASS** | Synthetic week 4 with only the Sunday game observed retains the live **October 1 00:00Z** cutoff; universe bytes and QB map are identical. It does not halt. |
| P1.3/4 — current week-4 schedule-only to schedule-plus-TNF-PBP | **PASS** | All **802 universe / 506 usage rows** are identical, including complete and isolated layer-3 QB maps. |
| P1.4 — installed current-season rows versus rebuild | **PASS** | **4,106 universe / 2,561 usage rows**, exact equality. |
| P1.4 — D274 versus D273 full clean tables | **PASS** | Independently rebuilt/serialized full tables are byte-identical: **89,757 universe / 47,951 usage rows** on the D274-v4 archive. |
| P1.4 — W=2–4 point-in-time | **PASS** | W2: **786/513** universe/usage rows; W3: **794/518**; W4: **802/506**. All values and both QB-map variants match after removing PBP at or after W. |
| P1.5 — saved smoke | **PASS as a dry-run artifact** | `20261002T184232Z`: **14 events, 28 teams, 14/14 converged, 45 reads, zero violations, 66/257 matched**; bundle verification reports no errors. |
| P1.5 — independent current IND/WAS bootstrap | **PASS as a dry run** | Exit 0, converged, valid bundle, **45 reads/zero violations**. Used archived quotes and `--dry-run --allow-stale-quotes`; it establishes neither fresh Sunday capture nor primary publication. |
| P1.5 — procedure | **PASS for the pinned runbook** | Regeneration matches except generation timestamp. Timing and remaining operational prerequisites below. |

Temporary storage exhaustion interrupted mutation startup and the last four forward files. Disposable test directories were removed; the affected files and mutation jobs were rerun. The per-file index distinguishes the initial interrupted results from the final passing invocations. No production-code change was made to obtain the baseline. All completed jobs stayed within the requested command limits.

**Verifier claims recomputed:**

| Claim | Result |
|---|---|
| D274-v4 archive | **HOLDS:** all **13 file hashes** match. All eight installed ratings tables match the archive; pre-2026 rows match the pre-refresh backup. Manifest completion time is **18:39:41.983980Z**, under the backup directory named `20261002T183144Z`. |
| Fingerprint | **HOLDS:** `3638769c89030de0`. |
| Real PBP dates/identities | **HOLDS for the actual files checked:** 2020–2026 have zero invalid dates, multi-date games, multi-week games, wrong seasons, null weeks or null game IDs. Game counts are **269, 285, 284, 285, 285, 285, 49**. Current PBP contains **8,497 rows**; all **49 games** agree with the snapshot. These clean-data counts do not establish rejection of malformed identity fields. |
| Week-4 universe | **HOLDS:** **802 rows, 724 non-null depth ranks, zero duplicate player/team keys, boolean flags, zero null flags**. |
| Mac's three counterexamples | **HOLDS:** historical-null case halts. The current-archive week-5 TB@DAL row dated **October 1** or **October 9**, against scheduled **October 8**, also halts before an output directory is created. |
| Full-table equality | **HOLDS on the available archive:** usage SHA `9662ab93327f94b650db2a8a1558ba389b68189ccb5d83d902028733ca135fa4`; rebuilt universe SHA `8a4005308ae58ce80220356535f3f11ca3288eb22a4e88029862ccdecad501c4`. Both versions give the same bytes. The cloud's older **47,446/89,737** counts concern different staged inputs, not this archive. I did not independently recover those staged files or verify the claimed 16-row roster explanation. |
| All-team freshness | **HOLDS:** the independent report returns True for **32 teams**. This is input-row freshness, not proof of final injury-report availability. |
| Five player counts | **HOLDS:** targets/carries before week 4: Metcalf **24/0**, Concepcion **20/4**, Jeudy **5/0**, Warren **14/38**, Judkins **9/42**. |
| Injury exclusions | **HOLDS:** **291 rows**, **7 Out/Doubtful**, **2 matching skill players**, **0 active** among those two. |
| Selftest | **HOLDS:** launcher hash matches; **1,090 dependency files, 6,395 distribution files, 12 repository modules**. |
| Owned QB regression | **HOLDS:** the exact rewritten test passes D274 and fails an assertion on D271 using its own weeks-1–3 PBP and full snapshot, with an offline schedule response for the old implementation. |
| Version and refresh wording | **HOLDS:** `D274-v4` is in code/manifest. The final docstring sentence now correctly says a step-7 readiness exception leaves refreshed tables installed. |

D274's statement that the earliest snapshot gameday is “equal to any PBP game's date” is imprecise: a Sunday game's date differs from Thursday's cutoff. The implemented rule correctly uses the **week's earliest snapshot date**, and the later-game-only test passes. Correct the wording; it is not a second blocker.

**Operational prerequisites:** The 18:31Z refresh was **not post-final-report**. Its injury source hash is unchanged from the earlier D273 archive. The all-team report has nonzero injury-status counts only for CLE, PIT and WAS; the Sunday smoke has only WAS=2. Calling that run “post-report” is unsupported.

| Window | Refresh completed by | Props capture | Harness and arithmetic |
|---|---|---|---|
| IND@WAS | **Sun October 4, 12:15Z** | Manual **12:15Z** | **12:45Z**, 1.5-hour horizon. Props age 30 minutes; game-line three-hour range **09:45–12:45Z**. Horizon ends 14:15Z, containing the 13:30Z kickoff. |
| Main + SNF | **Sun October 4, 15:45Z** | VM **16:00Z**, arrival confirmed | **16:15Z**, 9-hour horizon. Props age 15 minutes; game-line range **13:15–16:15Z**. Horizon ends Monday 01:15Z, containing SNF at 00:20Z. |

A refresh after Friday's final reports and the Sunday refreshes remain required. Their execution and future quote arrival were not observed here. PIT/CLE are absent from both Sunday windows. `_last_played_weeks(pbp, 4)` returns 3 for them; with target week 5 it returns 4. The earlier correction is confirmed.

## (C) P2 and bypasses

**Demonstrated bypass:** A1 supplies altered, correctly recorded usage to the genuine worker. The read set proves which materialized table was read; it does not validate the upstream raw rows that produced it. Missing week/season values discard one actual pass during aggregation while leaving the game's deduplicated calendar identity apparently valid. Historical missing IDs similarly alter priors without changing the current active universe.

**No new route from a non-worker value to a primary frozen probability was demonstrated.** The full forward suite and focused real-worker/publication checks passed. Production worker/publication code is unchanged from the prior pin. No new primary freeze was made. This is a bounded finding; the accepted D269 native-I/O boundary was not reopened, and frozen engine/calibration mechanics were not reviewed.

**T7 equivalence:** Removing the explicit `week_s.isna()` arm still rejects a PBP game absent from the snapshot. I tested both ordinary integer and nullable `Int64` snapshot weeks. The missing join produces `sdate=NaT`; a validated non-null PBP date compares unequal to it, making the remaining date arm true. Both implementations halt with the same contradiction. Thus **T7 is redundant for this missing-game branch**, given the separate date validator. It is not the cause of A1: that defect hides a bad raw row behind a valid retained game row.

The snapshot writer's season/REG filters and active-only depth gate are retained and now have distinguishing regressions. The every-season cutoff loop is before explicit carry-forward row creation, as claimed. The original historical-null and calendar-contradiction repairs do not need to be undone.

## (D) Mutations and survivors

Each mutant was isolated; modified manifest-listed files were re-stamped. The unchanged focused control passed **63 tests**: FWD7d, board 5J2, FWD7c, FWD6f, FWD7a, two FWD6d static-reader tests and FWD6b's real default-worker-path test. These are focused-suite results, not full-298-test mutation runs.

| Operators | Result |
|---|---|
| T1 allow null dates; T2 allow multi-date/week games; T3 allow wrong-season rows | **3/3 KILLED** |
| T4 ignore contradictions; T5 omit date comparison; T6 omit week comparison | **3/3 KILLED** |
| T7 omit explicit missing-snapshot-game arm | **SURVIVES, 63 passed; equivalent under the stated preconditions**, as examined in C |
| T8 newest-season-only requirement; T9 take snapshot-season cutoffs from PBP | **2/2 KILLED** |
| T10/N1 omit snapshot season filter; T11/N2 omit REG filter; T12/N3 count inactive ranks; T13/N4 omit NaT arm | **4/4 KILLED** — all four audit-16 survivors are covered |
| T14 maximum cutoff | **KILLED** |
| Additional D274 claims: S5, S6, S7, S9, S10, S15 | **6/6 KILLED** |

Cowork's claimed **13 of 14 T kills** is reproduced.

**New probes:**

| Probe | Result / missing test |
|---|---|
| Validate only the first row of each PBP game | **KILLED** by the multi-date/week regression. |
| Require cutoffs only for weeks ≤18 | **SURVIVES, 63 passed.** Add a rostered historical postseason week with no PBP cutoff; the unmodified contract requires it too. |
| Skip cutoff requirements for seasons before 2025 | **SURVIVES, 63 passed.** Current requirement tests use 2025+2026; add an older rostered season/week lacking coverage. |
| Compare only the first PBP game with the snapshot | **KILLED**. |
| Allow one contradictory game | **KILLED**. |

The two new survivors expose requirement-test gaps, not mutations present in production. The more consequential omission is the unmutated missing-identity failure in A1. Add raw-row null-identity cases alongside the existing wrong-non-null-season and multi-week tests.

## (E) Per-window verdict

| Sunday window | Verdict at this pin | Reason |
|---|---|---|
| **IND@WAS, 12:45Z harness** | **NO-GO as primary** | One missing identity value reaches this exact game's worker and changes 17 calibrated probabilities, with no gate/read-set failure. |
| **Main + SNF, 16:15Z harness** | **NO-GO as primary** | The validator/aggregation path is shared. The historical missing-ID case changes every week-4 usage row and passes all 28 Sunday teams; this is not confined to the early game. Its own worker comparison was not run. |

Both audit-16 fixes, the clean rebuild, the ordinary TNF transition and the complete baseline pass. The remaining repair is narrow: validate raw identity fields before any grouping can skip them, with explicit handling of nullable values. Preserve clean bytes, reject the three missing-identity variants before output writes, verify restoration and rerun the worker comparison/baseline at the repaired pin. Final-report refreshes and timely Sunday quotes remain operational prerequisites independently of that repair. No retrospective primary designation after outcomes.

Evidence outside the repository: [forward per-file index](/private/tmp/a17-valid-index.jsonl), [usage index](/private/tmp/a17-usagevalid-index.jsonl), [archive and saved smoke](/private/tmp/a17-inputs.json), [PIT/full-byte rebuilds](/private/tmp/a17-pit.json), [original cases and raw-file counts](/private/tmp/a17-cases.json), [rollback](/private/tmp/a17-restore.json), [D273 negative-control deltas](/private/tmp/a17-negativecontrols.json), [recreated negative-control fixture equality](/private/tmp/a17-negative-rebuilds.json), [missing identity rebuilds](/private/tmp/a17-nullidentity-one.json), [missing identity worker deltas](/private/tmp/a17-nullidentity-probs.json), [historical missing ID](/private/tmp/a17-histidentity.json), [edge cases/T7/QB fixture](/private/tmp/a17-edges.json), [week-5 contradictions](/private/tmp/a17-week5.json), [runbook/selftest](/private/tmp/a17-misc.json), [mutation operators](/private/tmp/a17_mutations.py), [mutation results](/private/tmp/a17-mutations.log), [additional S operators](/private/tmp/a17_mutations_extra.py), [additional S results](/private/tmp/a17-mutations-extra.log). Scripts and detailed subprocess logs remain under `/private/tmp/a17*`.
