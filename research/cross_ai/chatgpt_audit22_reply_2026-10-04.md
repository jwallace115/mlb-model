# Audit #22 — FWD7l / D280
a7e2d7683b501ee797fcc4706bf74814f16613c4
(E) IND@WAS: NO-GO; main + SNF: NO-GO; MNF: NO-GO for a PRIMARY at this pin.

The audit-#21 six-cell defect is fixed. A different, executed counterexample changes the consumed status set and passes both injury-gate modes. This is an admission defect demonstrated on a modified copy of the capture; it is not a claim that the installed capture contains the defect. Decide `--pilot` before each harness unless a subsequent code pin earns its own timely GO. Data-only commits above this pin do not repair this defect. The deadlines remain Sunday 12:30Z, Sunday 16:00Z and Monday 23:15Z, respectively.

D280 was read first. The comparison with b7d4a9916 touches exactly the six files listed in the brief. Source and execution used one extracted copy of the full SHA above. Prior audit-#21 findings outside that diff carry forward as requested. The unchanged usage/PIT suite was not rerun; its previous 22 passes are carried forward, not included in the 366 forward tests. The simulation engine and its fits were executed as a black box, not re-reviewed.

## (A) Must fix before a primary

**1. Decode and validate attributes before admitting row text.** [nfl/sim/official_injuries.py:219](https://github.com/jwallace115/mlb-model/blob/a7e2d7683b501ee797fcc4706bf74814f16613c4/nfl/sim/official_injuries.py#L219) (raw attributes at 218; text-only decoding at 230); missing regression coverage at [nfl/sim/tests/test_fwd7g.py:802](https://github.com/jwallace115/mlb-model/blob/a7e2d7683b501ee797fcc4706bf74814f16613c4/nfl/sim/tests/test_fwd7g.py#L802).

Counterexample: in the archived Chig Okonkwo row (WAS TE, `00-0037809`), replace the empty final cell:

```html
<td></td>
```

with:

```html
<td><span style="display:n&#111;ne">Out</span></td>
```

HTML attribute decoding makes the style `display:none`. The pinned guard searches the **raw** attribute string, misses this spelling, and adds the hidden `Out` to the cell text. Python's independent standard-library HTML parser confirmed the decoded attribute value. Literal `display:none` HALTs; the encoded equivalent is admitted. The copied capture record was updated with the edited page's byte count and SHA-256, so this tests semantic validation of correctly recorded bytes.

Executed result: `(WAS, 00-0037809, blank)` becomes `(WAS, 00-0037809, Out)`; 318 rows still parse. Actual `official_step` → actual usage builder → historical-row splice changes that player's active flag from true to false in weeks 4 and 5. Both `OI.check(require=True)` and `OI.check(require=False)` return verified for IND and WAS. WAS has 7 nonblank official statuses instead of 6; its active count is 15 instead of 16, with no active-universe mismatch reasons.

The **non-pilot bootstrap dry run also exits 0**, verifies both teams, converges its one game, and records 45 reads with 0 violations. The clean and altered runs contain **86 and 86 prediction rows**, respectively; 5 clean-only rows disappear and 5 different rows appear. Across 81 common rows, **80 sim_p and 42 cal_p values change**, with maximum absolute changes of **4.820000 and 10.040000 percentage points**, respectively. These are measured output changes, not a review of the simulation algorithm. Both replay runs used `--dry-run --allow-stale-quotes`, as in audit #21, solely to hold the old quote fixture constant; `--pilot` was absent.

**Required repair:** parse attribute names/values and normalize HTML character references before validation. The small fail-closed option is to reject any `style` attribute inside a player/header row, alongside the existing `hidden` rejection; the archived 32 injury tables have zero such styles. That option also requires changing the `style="x"` control at `test_fwd7g.py:834` to expect HALT, explicitly documenting the narrower grammar. If styles remain allowed, use a defined CSS grammar that handles comments and escapes rather than extending the raw-text regex one spelling at a time. Add tests requiring encoded `display:none` and encoded `visibility:hidden` to HALT during parse, refresh without writes, and both gate modes. Retain a clean replay and exact prediction comparison. A passing hash check does not establish that hidden text was interpreted correctly.

**Quote-path assessment: the destination paths check out; the actual external prompt and refreshed quotes remain unverified.** `run_forward_v1.py:30–31, 81–133` reads the running worktree's archive and its `season=2026/manual/*.parquet`; `pull_hardrock_props.py:147, 246–253` honors an absolute output directory. A synthetic local loader check selected the manual scratch file and restored newer line snapshot, with 30-minute props and 15-minute lines at the chosen cutoff. No live pull or restore was performed.

Before each window, update the `origin/main` remote-tracking reference, restore the stated data paths **in the harness worktree**, send the manual pull to that worktree's absolute manual directory, and inspect the actual selected timestamps for every expected game. Restoring from a cached remote-tracking reference does not fetch newer quotes. A copied 01:30:06Z snapshot at the London 12:45Z cutoff is over eleven hours old; the synthetic bundle check HALTs on that case. Treat updating the reference as an execution prerequisite, not a newly demonstrated admitted-input bypass. Use no stale-quote override. The pinned code rejects consumed quotes older than three hours (`run_forward_v1.py:427–449`). The Mac record's claim that the worktree reads quotes directly from `~/mlb-model` is false, as the brief acknowledges. I could not locate/read `claude/window_prompts_nfl_w4_2026-10-04.md`; only the supplied recipe is assessed here.

## (B) P1 and D280 claim checks

| Check | Verdict | Executed evidence |
|---|---|---|
| Forward files separately | HOLDS | **366 passed across 29 files; no unfinished cases.** Four files were completed in bounded segments after time limits; no assertion failure was observed. See the file totals below. |
| Audit-#21 six-cell edit in Daniels and White | FIXED | Parsing HALTs. Actual `official_step` HALTs before changing any copied input; usage builder is not reached and no bundle is created. |
| Same bad page carried into the injury gate | FIXED | Both primary and pilot `OI.check` HALT on `<th> outside a cell`. |
| Clean refresh replay | HOLDS | All **35,864** overlaid injury rows are frame-equal to the installed archived table. |
| Clean full chain / previous 86 predictions | HOLDS | The actual refresh → usage builder → non-pilot bootstrap produces **86 predictions, exactly equal to audit #21 in every field except `run_id` and `board_generated_utc`**. Both rebuilt usage/active tables equal the archived tables. One game converges; bundle verification is clean; 45 recorded reads, 0 violations. |
| Prior P2 structural/benign variants | PARTIAL | Six-cell/body-TH, missing/extra cells, stray text and unsupported structure now HALT. Benign controls are identical; encoded hidden statuses remain admitted with changed sets. Full breakdown below. |
| Committed mutation campaign | HOLDS | **70/70 operators completed: 69 killed by failing tests; X2 alone survives.** All anchors matched. The original script reached the 540-second cap after 48 completed operators; the exact remaining registered operators and focused tests were then run on the same tree. Every file was restored; all 53 manifest hashes match afterward. |

**D280's individual assertions:**

1. **PARTIAL:** full cell-sequence validation and the listed ordinary malformed-row checks hold in the executed cases. Raw style matching does not enforce the claimed rejection of hidden content under equivalent attribute encodings. Quoted `>` in an inline/cell attribute does not leak into cell text in the admitted controls. A quoted `>` on a row itself HALTs; this is allowed by the brief's P1 criterion.
2. **HOLDS for the archived 23:10Z counterexample and replay:** six-cell parse/refresh/gates all HALT; clean overlay is identical. I did not re-fetch or independently reproduce the exact historical **02:10Z live capture**; the reported live-time observations are not independently verified from those original bytes.
3. **HOLDS for the available 318-row capture.** The available clean capture reproduces the archived overlay and both rebuilt usage tables; the full 86-row prediction comparison is exact as described above. The separate claim of a frame-equal **313-row Oct 2** comparison is not independently recomputed: that capture was not found in the inspected local archive/run directories. It must not be substituted with the 318-row capture when describing evidence.
4. **Test inventory HOLDS:** 49 tests in `test_fwd7g`, including four added D280 tests containing 14 HALT cases and seven benign controls. **70/70 operators completed: 69 killed by failing tests; X2 alone survives.** All anchors matched. The original script reached the 540-second cap after 48 completed operators; the exact remaining registered operators and focused tests were then run on the same tree. Every file was restored; all 53 manifest hashes match afterward.

**Recomputed Mac-run numbers:** the saved bundle `20261004T022121Z` has **28/28 verified teams**, **14 events and 14/14 converged games**, and **45 read-set entries**: **14 bundled files + 31 pinned files**, **0 unproven**, **0 hash mismatches**, **0 recorded violations/conflicts**. Bundle verification returns no errors. These claims **HOLD**. It records `pilot=false` **and `allow_stale_quotes=true`**: it demonstrates the dry-run path, not fresh Sunday production quotes. **Selftest success HOLDS:** importing `nfl.sim.run_forward_v1` and `nfl.sim.run_week` through the pinned bootstrap exits 0, with isolation flags and launcher hash verified. My counts are **13 repository modules, 1081 dependency files, 6395 distribution files**. The Mac note's exact 12/1090 counts were **not reproduced by this invocation**; its original import arguments are not recorded, so I do not equate these different module sets or call the historical counts independently verified.

The archived 23:10:55Z capture recomputes to **318 rows, 32 teams, 16 matchups, 138 nonblank game statuses**, with Daniels and White both Out. Its SHA-256 is `2711f526d7a38581ba1a6a7a7ea79a2244ae7e457cf88c393c51bd35cefcb83f`. Those archive counts **HOLD**.

Per-file totals (all under `nfl/sim/tests/` at the pin):

| File | Passed | Execution |
|---|---:|---|
| `test_forward_v1.py` | 8 | Complete file |
| `test_freeze_v1.py` | 4 | Complete file |
| `test_fwd2_anchor.py` | 3 | Complete file |
| `test_fwd2_bundle.py` | 5 | Complete file |
| `test_fwd2_experiment.py` | 6 | Complete file |
| `test_fwd2_item0_fixes.py` | 7 | Complete file |
| `test_fwd2_settlement.py` | 12 | Complete file |
| `test_fwd2b_harness.py` | 10 | Complete file |
| `test_fwd3_item0.py` | 9 | Complete file |
| `test_fwd3_item1.py` | 3 | Complete file |
| `test_fwd3_item2.py` | 8 | Complete file |
| `test_fwd4_item0.py` | 9 | Complete file |
| `test_fwd4_item1.py` | 4 | Complete file |
| `test_fwd5_pin.py` | 4 | Complete file |
| `test_fwd6_item0.py` | 13 | 11 + 2 bounded segments |
| `test_fwd6_item1.py` | 12 | Complete file |
| `test_fwd6_item2.py` | 9 | Complete file |
| `test_fwd6_item3.py` | 5 | Complete file |
| `test_fwd6b.py` | 39 | 17 + 22 bounded segments |
| `test_fwd6c.py` | 33 | 27 + 6 bounded segments |
| `test_fwd6d.py` | 33 | 29 + 4 bounded segments |
| `test_fwd6e.py` | 6 | Complete file |
| `test_fwd6f.py` | 11 | Complete file |
| `test_fwd7a.py` | 27 | Complete file |
| `test_fwd7c.py` | 11 | Complete file |
| `test_fwd7d.py` | 7 | Complete file |
| `test_fwd7e.py` | 7 | Complete file |
| `test_fwd7f.py` | 12 | Complete file |
| `test_fwd7g.py` | 49 | Complete file |

## (C) P2 and admitted-input bypasses

**52 parser/mapper cases executed: 30 HALT, 19 identical consumed sets (including clean), 3 admitted changed sets.**

| Family | Result |
|---|---|
| TH status with/without extra TD; extra/missing cell; stray text in row/body; nested TD/table; template; unbalanced/unclosed tags; literal stray `<`; colspan/rowspan; second header | HALT |
| Row/cell attributes; balanced nested inline tags; ordinary entities; edge whitespace/newlines; uppercase TD; quoted `>` or `<` on inline attributes; split/attributed bodies; commented-out row | ADMITTED, identical consumed set |
| Uppercase TR; quoted `>` on TR | HALT; these are false rejections, not P1 blockers under the specified criterion |
| Split `O` / `ut` with a space or newline; internal NBSP; zero-width literal/entity; two status values | HALT as an unknown status |
| Adjacent inline `O` + `ut`, including `<br>`; edge NBSP | ADMITTED, identical consumed set |
| Empty status replaced by hidden Out using `display:n&#111;ne` | ADMITTED, blank → Out; actual refresh/builder/gate chain executed |
| Same using `visibility:h&#105;dden` | ADMITTED, blank → Out; parser/mapper executed |
| Same using `display:/**/none` | ADMITTED, blank → Out; parser/mapper executed |

The last three are one normalization/visibility defect, not three independent must-fix items. Plain `display:none` and `visibility:hidden` controls HALT. Counts alone do not catch the defect: the source still contains all 318 player rows.

## (D) Surviving mutations

**70/70 operators completed: 69 killed by failing tests; X2 alone survives.** All anchors matched. The original script reached the 540-second cap after 48 completed operators; the exact remaining registered operators and focused tests were then run on the same tree. Every file was restored; all 53 manifest hashes match afterward.

**X2:** removing blank-to-missing conversion leaves the earlier blank-value rejection intact. It remains admission-equivalent for those invalid PBP keys, consistent with the unchanged source and this replay. This is not evidence of a new input bypass.

**Additional independent survivor M1:** removing only `|visibility\s*:\s*hidden` from the visibility guard leaves **62 passed in 12.56s**. Under that mutant, literal `<span style="visibility:hidden">Out</span>` in the empty Chig status cell is admitted as Out. This is a real parser-admission change in the mutant and a missing regression, beyond Cowork's registered 70 operators. The unmodified pin rejects this literal spelling; its encoded equivalent is the actual A1 defect. The file was restored after this check.

Z10's detection must be interpreted narrowly: `test_d279_unsupported_table_structures_halt` fails because it expects a `columns` error, while the retained `_cells` validation still HALTs on `</tr> outside a cell`. It is a message-sensitive kill, not an admitted second-header bypass. A test that insists on one error message can kill a mutant even when another check still rejects the input. Mutation counts are not proof that all admissible markup preserves the consumed set; the A1 counterexample runs against the **unmodified pin**.

## (F) Disk, temporary work and scope

Before:

```text
Filesystem        Size    Used   Avail Capacity iused ifree %iused  Mounted on
/dev/disk3s1s1   460Gi    13Gi    26Gi    34%    484k  269M    0%   /
```

After:

```text
Filesystem        Size    Used   Avail Capacity iused ifree %iused  Mounted on
/dev/disk3s1s1   460Gi    13Gi    24Gi    36%    484k  254M    0%   /
```

Created and deleted one extracted working root, `/private/tmp/audit22-work`, including its `tree`, `inputs`, `chain-inputs`, `probes`, quote fixture, archive, runtime-temp and test-fixture subdirectories. 490 directories under that root were removed (403.4 MiB of files at cleanup). No per-mutant repository extraction was made. The full deleted-directory inventory is retained in `/private/tmp/a22-cleanup.json`. Four empty directories left by the early capped tests were also removed: `/private/var/folders/1q/gtd8wq1569d6y2q95qtbpjsr0000gn/T/tmp5h6j_b3d`, `/private/var/folders/1q/gtd8wq1569d6y2q95qtbpjsr0000gn/T/fwd_pyc_0c5nkttz`, `/private/var/folders/1q/gtd8wq1569d6y2q95qtbpjsr0000gn/T/tmp3t4vjw2p`, `/private/var/folders/1q/gtd8wq1569d6y2q95qtbpjsr0000gn/T/fwd_pyc_91s1msg_`. Older, pre-existing temporary directories were left alone. Only small flat audit evidence/helper files remain; all directory removals above were verified. The volume-wide free-space reading fell from 26 GiB to 24 GiB over the audit interval despite removal of the audit tree; I have not established the cause of that system-wide change. Retained flat audit files total under 2 MiB.

Only the requested reply was written in the repository. No branch checkout, commit, production refresh, quote pull, freeze or bet was performed. Baseline and probe helpers ran against copied data; worker runs were dry runs. Engine/anchor/calibration/pricer/fits internals were not reviewed. A sandbox restriction blocked the final helper report append after the altered worker completed; its JSON and predictions were already saved, and the final report write used the authorized file-write path. No substantive check remained blocked. The exact historical 02:10Z live-capture bytes, the separate 313-row Oct 2 capture, and the external window-prompt file were not located/read; claims specific to those artifacts remain unverified.

Evidence is retained as small flat files under `/private/tmp`, including `a22-deep-probes.json`, `a22-chain-th-two-statuses.json`, `a22-chain-blank-hidden-entity.json`, `a22-independent.json`, `a22-base-index.jsonl`, `a22-cowork-mutations.json`, `a22-mutation-summary.json`, `a22-extra-mutation.json`, `a22-prediction-comparison.json` and `a22-prediction-rows.json`. Test logs distinguish the initial bounded-batch interruptions from completed test runs.
