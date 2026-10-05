# Audit #24 — FWD7n / D282
955f7101ea2b5ad7338644c4c6094bbfb1e522cb
(E) GO for a PRIMARY MNF ATL@NO at this pin, subject to the actual window passing the existing fresh-input and quote gates.

The audit-#23 counterexamples are fixed. I completed all **29 baseline files: 372 passed, zero failed, zero skipped**, and all **81 registered mutation operators: 79 killed, only X2 and Z21 survived**. No executed, in-scope case made the parser consume a different status from the visible HTML5 cell. My own non-pilot MNF bootstrap dry run completed, with a verified final manifest and sidecar. This verdict applies to this code pin; the dry run used archived quotes and `--allow-stale-quotes`, so it does not establish the readiness of tonight's production inputs.

This GO is recorded before the brief's Monday 23:15Z deadline. Follow the already-declared refresh/manual-pull/harness procedure for MNF. The actual primary must pass its gates without the stale-quote override. Sunday remains outside this primary authorization; I did not retroactively designate or freeze either Sunday window.

D282 was read before D281. The b842af343→b1de3b50d diff contains exactly the five named files; b1de3b50d→955f7101e adds only the Mac record. All source execution used one extracted tree at the full pin above. Engine, anchor, calibration, pricer and fit internals were not reviewed; their existing worker was executed as a black box. Findings below distinguish source reading, execution and unavailable evidence.

## (A) Must fix before a primary

**No remaining code blocker was demonstrated by P1.** Do not manufacture a new blocker from an interrupted run or a deliberately changed visible status.

**1. Correct the completion attribution before using the Mac transcript as evidence.** [research/nfl_sim/fwd7n_mac_run.md:191](https://github.com/jwallace115/mlb-model/blob/955f7101ea2b5ad7338644c4c6094bbfb1e522cb/research/nfl_sim/fwd7n_mac_run.md#L191), continuing through its sidecar and completion claims; the summary repeats the claim at [line 240](https://github.com/jwallace115/mlb-model/blob/955f7101ea2b5ad7338644c4c6094bbfb1e522cb/research/nfl_sim/fwd7n_mac_run.md#L240).

**Counterexample, read and recomputed from the named directories:** `20261005T103352Z` contains no `anchor_sidecar.parquet`, has only 21 manifest entries, and fails bundle verification with nine unlisted worker outputs. It cannot substantiate the sidecar/completion transcript bearing that run ID. `20261005T103258Z` has the sidecar, 31 manifest entries and zero bundle-verification errors. Preserve the former as an incomplete run with unknown stopping cause; attribute the supported result to the latter. Do not rewrite either run's artifacts to make them agree with the prose. The D282 label on commit fbc1b34e4 at [record line 19](https://github.com/jwallace115/mlb-model/blob/955f7101ea2b5ad7338644c4c6094bbfb1e522cb/research/nfl_sim/fwd7n_mac_run.md#L19) should also be D281.

This is a record correction, not a prerequisite code change: this reply records the correction, and the GO relies on independently executed evidence rather than that transcript. I changed neither the record nor production artifacts.

## (B) P1 results and D282 claims

| P1 check | Verdict | Executed evidence |
|---|---|---|
| Full baseline, separately by file | PASS | All 29 files complete; **372 passed / 0 failed / 0 skipped**. `test_fwd7g.py` has 55 passing tests. |
| Audit #23 aria-label/href cases | FIXED | Both halt in actual `official_step` before any persistent overlay/capture write. Both gate modes halt. Separately injected captures make the real isolated non-pilot bootstrap exit 1 before a bundle manifest or worker outputs exist. |
| Audit #21 TH/extra-cell and #22 encoded hidden-status cases | FIXED | Same refresh/no-write, both gate-mode and actual bootstrap rejection results. |
| Clean refresh and usage chain | PASS | Reproduces **35,864 injury rows** exactly. Actual usage builder plus historical splice reproduces **47,944 usage rows** and **89,757 active-universe rows** exactly. |
| Clean 86-prediction replay | PASS with reference limitation below | Real historical bundle builder, `pilot=false`, then unchanged isolated bootstrap worker exits 0. **86/86 prediction rows match exactly**, except `run_id` and `board_generated_utc`. |
| Prior 52 probes | PASS | **39 HALT / 13 identical consumed sets / 0 changed sets.** |
| Prior 23 attribute probes | PASS | **7 HALT / 16 identical / 0 changed**; the two former admitted changes now halt. |
| New scanner probes | No demonstrated bypass | 33 cases: **17 HALT / 15 identical / 1 admitted changed set**. The last case also changes the HTML5-visible status to blank; see C rather than counting it as a parser defect. |
| Full registered mutation campaign | PASS | **81/81 completed; 79 killed; only X2 and Z21 survive.** No timeout, anchor-count miss or collection error counted as a kill. |

For the old A1, the cell remains the exact construction under test:

```html
<td><a aria-label="<!--">Out</a><a aria-label="-->"></a></td>
```

The href variant replaces both `aria-label` attribute names with `href`. D282 keeps the quoted delimiters inside their tags; the subsequent section check rejects them. On the archived page both report `HALT: official injury page section 1: unsupported element (script/template/style/noscript or an unclosed comment)`. Directory hashes around actual `official_step` are unchanged; the usage builder and bundle creation are not reached in that chain. Independently attempting to install those capture bytes and launch the harness leaves **partial input directories**, because `build_bundle` creates/copies files before the injury check. It writes no accepted manifest or solver outputs. Thus “no bundle” means no admitted bundle, not that a directly attempted harness creates no directory.

**Replay reference limitation:** the original audit-#23 temporary 86-row JSON is gone. I cannot compare against that absent file. I instead used the retained IND@WAS subset of `~/mlb-model-fwd6/nfl/data/board/week=2026_04/sim_runs/20261004T002659Z/outputs/picks_log.parquet`: 86 rows. Every prediction column matches after sorting by game/player/family/line/side, with only the two run-identity columns excluded. Because Sunday has passed, the replay supplies historical T=`2026-10-04T07:00:00Z` to the real bundle builder, then invokes the unchanged `-I -S -B` worker. It is not a claim that the Monday CLI permits non-pilot `--as-of`; it expressly refuses that. The worker's returned IND@WAS anchor is **−3.4628 / 47.1096**, four iterations, converged; output validation passes, and all **45 reads = 14 bundled + 31 pinned** classify successfully.

**Independent MNF execution:** run `20261005T111500Z`, launched through the actual isolated bootstrap harness with `--week 4 --events Atlanta --dry-run --allow-stale-quotes`, exits **0**. It has 65 props, six lines, 68 sheet rows, 43 two-way rows and 13 matched rows. All 85 prediction rows exactly match saved completed run `103258Z` after the same two identity exclusions. Its sidecar records **anch_m 2.1622, anch_t 47.5566, three iterations, converged=true, anchored=true**. Its final manifest has 31 entries, verification returns zero errors, and its read set has 14 bundled plus 31 pinned reads, zero conflicts, zero violations and zero network attempts.

| D282/verifier claim | Verdict and independent result |
|---|---|
| Quote-aware section scan replaces global comment deletion | **HOLDS for the read implementation and executed cases.** `_read` splits sections, `_section_body` consumes whole tags/attributes and removes text-context comments. Both old A1 variants halt. This is not a proof that the regex implements every HTML parsing state. |
| Abrupt/incorrect comment ends, missing section close, raw attribute angle brackets fail closed | **HOLDS for the specified forms.** The new tests and independent probes reject `<!-->`, `<!--->`, `--!>`, quoted section endings, unsupported declarations and raw angle brackets. Encoded permitted values remain admitted. |
| Four permitted comment/encoded-value controls preserve clean parsing | **HOLDS.** The 55-test file executes all four controls; independent archived-page probes also cover comments in/between cells/rows, a comment containing section/row end tags, and encoded delimiters. |
| Oct 2 capture unchanged from prior parser | **HOLDS.** SHA-256 `b8e53c975e29b78dd7f13e450e7d0678bc49abae0af8441698eda1a47fe76da2`: **313 rows, 32 teams, 130 nonblank statuses**, frame-equal under this pin and the audit-#23 parser read from its commit. I did not re-execute every older parser version. |
| Installed capture unchanged; clean replay equals installed | **HOLDS.** SHA-256 `2711f526d7a38581ba1a6a7a7ea79a2244ae7e457cf88c393c51bd35cefcb83f`: **318 rows, 32 teams, 138 nonblank statuses**; prior/current parser frames equal; all 35,864 overlaid injury rows equal the archive. |
| Exact live Oct 5 00:52Z observation: 318/32/138, ten attacks, four controls | **NOT INDEPENDENTLY VERIFIED as a time-specific fetch.** I did not locate/read that live response's retained bytes. The corresponding transformations were executed against the installed capture; that does not establish what the endpoint returned at 00:52Z. |
| 55 injury tests and 372 forward tests | **HOLDS:** 55 and 372, actually executed; no skips. |
| 81 operators / 79 kills / X2 and Z21 survivors | **HOLDS:** 81 / 79 / exactly those two, actually executed. |
| 103352Z completed through sidecar/finalization | **FAILS:** no sidecar, **21 entries = 19 file hashes + two flags**, nine unlisted output files. Its latest file timestamp is **10:34:36.088175Z**. No original process exit status was available. |
| 103258Z supports the substantive MNF result | **HOLDS:** sidecar present, **31 entries = 29 file hashes + two flags**, zero verification errors; 65 props, six lines, 85 picks, 13/43 matches; anchor 2.1622/47.5566, three iterations. |
| Both later MNF bundles use identical quotes and predictions | **HOLDS:** props hashes equal, lines hashes equal, and all sorted prediction columns equal apart from run ID/generated timestamp. |
| First MNF run had zero props, stale lines and zero matches | **HOLDS:** **0 props / 6 lines / 84 picks / 0 of 3 matches**; line timestamp is Sep 30 21:00Z. Executing its saved data through the fill-to-sidecar checks raises the zero-match HALT. “Quote files were not synced” is consistent with those files, not independently proven shell history. |
| Patch identity | **HOLDS for the local code diff:** stable patch ID **7ee2b01460a5602a52d5947e38f49469588ba75a**. The original cloud patch file and its f4724750… SHA-256 were not independently read; matching a diff's patch ID does not verify that patch-file hash or the remote branch's present tip. |
| Selftest's 12 modules / 1,090 dependency files / 6,395 distribution files | **Historical counts not reproduced as stated.** My specified imports (`nfl.sim.run_forward_v1`, `nfl.sim.run_week`) exit 0 with **13 / 1,081 / 6,395**, isolation flags true and no sitecustomize/usercustomize. The record omits its import arguments, so differing import-dependent counts alone do not establish a defect. |

Baseline file results (each process exited 0; all counts are passed tests):

| Test file | Passed |
|---|---:|
| `test_fwd2_anchor.py` | 3 |
| `test_fwd2_bundle.py` | 5 |
| `test_fwd2_experiment.py` | 6 |
| `test_fwd2_item0_fixes.py` | 7 |
| `test_fwd2_settlement.py` | 12 |
| `test_fwd2b_harness.py` | 10 |
| `test_fwd3_item0.py` | 9 |
| `test_fwd3_item1.py` | 3 |
| `test_fwd3_item2.py` | 8 |
| `test_fwd4_item0.py` | 9 |
| `test_fwd4_item1.py` | 4 |
| `test_fwd5_pin.py` | 4 |
| `test_fwd6_item0.py` | 13 |
| `test_fwd6_item1.py` | 12 |
| `test_fwd6_item2.py` | 9 |
| `test_fwd6_item3.py` | 5 |
| `test_fwd6b.py` | 39 |
| `test_fwd6c.py` | 33 |
| `test_fwd6d.py` | 33 |
| `test_fwd6e.py` | 6 |
| `test_fwd6f.py` | 11 |
| `test_fwd7a.py` | 27 |
| `test_fwd7c.py` | 11 |
| `test_fwd7d.py` | 7 |
| `test_fwd7e.py` | 7 |
| `test_fwd7f.py` | 12 |
| `test_fwd7g.py` | 55 |
| `test_forward_v1.py` | 8 |
| `test_freeze_v1.py` | 4 |

## (C) P2 and bypasses

The new probes include nested/abrupt comment forms, bogus declarations, doctype/CDATA/processing instructions, odd end tags, quoted and unquoted newlines, raw/encoded section endings, null characters, nested sections and section-open strings in comments/text. No executed case preserves a visible Out while silently deleting it as audit #23 did.

I do report the one changed consumed set, rather than hiding it in an “all identical” total. Replacing Daniels's Out cell with:

```html
<td><!--x--!!>Out<!--tail--></td>
```

is admitted, changing `(WAS, 00-0039910, Out)` to `(WAS, 00-0039910, blank)`. An independent full-page **html5lib** parse finds five cells, **blank visible text in the fifth cell**, and one comment whose content is `x--!!>Out<!--tail`. `--!!>` does not terminate that comment. This probe itself comments out the status; both parsers agree. It is a changed-data control, not an in-scope semantic counterexample. Treating every deliberately changed source status as a blocker would also condemn correctly parsing an official Out→blank update. The other 32 scanner probes either halt or retain the clean set.

**Boundary:** this is not a proof of browser-rendered visibility under arbitrary CSS or changes outside the report sections. The prior declared assumptions about known class meanings and outside wrappers remain assumptions. The independent HTML5 checks establish cell text/comment structure, not a live-browser screenshot or unchanged external stylesheets. I found no additional bypass within the executed section/cell cases.

**No silent exit-0/no-sidecar branch was found in (e)→(f).** Source reading: [run_forward_v1.py:1289](https://github.com/jwallace115/mlb-model/blob/955f7101ea2b5ad7338644c4c6094bbfb1e522cb/nfl/sim/run_forward_v1.py#L1289) raises a string-valued `SystemExit` for price/source mismatches; [line 1309](https://github.com/jwallace115/mlb-model/blob/955f7101ea2b5ad7338644c4c6094bbfb1e522cb/nfl/sim/run_forward_v1.py#L1309) does so for zero matches; [line 1315](https://github.com/jwallace115/mlb-model/blob/955f7101ea2b5ad7338644c4c6094bbfb1e522cb/nfl/sim/run_forward_v1.py#L1315) does so for a missing anchor log. These are nonzero exits. The sidecar write at line 1321, finalization at line 1327 and final read-set check precede the dry-run return at line 1350. Bootstrap's `_harness` returns 0 only after `fwd.main` returns; it does not swallow those exceptions.

**Executed separately from the full MNF run:** I extracted the unchanged pinned statements from filling through the missing-anchor check and supplied the saved rows. Both `103258Z` and `103352Z` reach sidecar construction with **13 matches and no price mismatch**. A deliberately changed price raises `HALT: 1 price_first mismatch(es)…`; a missing anchor path raises the mandatory-sidecar HALT; the first run's data raises the zero-match HALT. This checks that segment, not a reconstruction of the incomplete process's original execution. There is no evidence here that D229 actually stopped `103352Z`, nor evidence that it exited 0. Its cause remains unknown.

## (D) Surviving mutations

**Full campaign completed: 81 operators, 79 killed, two survived.** I executed the exact pinned W/X/Z definitions and focused test list in a bounded driver, sequentially on the same extracted tree, restoring each changed file immediately. Each kill had exit 1 and a named failing test. Each survivor ran all **68 focused tests** successfully. This was the complete registered focused campaign, not 81 runs of the entire 372-test baseline.

| Group | Executed | Killed | Survived |
|---|---:|---:|---|
| W1–W24 | 24 | 24 | None |
| X1–X23 | 23 | 22 | X2 |
| Z1–Z34 | 34 | 33 | Z21 |

**X2, blank normalization removed:** the earlier-computed blank masks remain in the admission rules. They still reject blank/whitespace keys; removing their conversion to missing does not admit those rows. **Z21, cell-local stray-`<` check removed:** section-level markup validation remains. These are the same redundant-guard survivors identified previously; this audit independently confirms their test survival. That reasoning is narrower than a formal equivalence proof on every possible input.

The four new operators all die: **Z31** at `test_d282_comment_delimiters_in_attribute_values_halt_the_parse_refresh_and_gate`; **Z32, Z33 and Z34** at `test_d282_angle_brackets_and_section_delimiters_outside_text_halt`. **Z23** also dies at that latter test. Be precise about mutation strength: Z23's failure can be a changed HALT diagnostic, not evidence that its mutant admits the edited page. The 79/81 result measures this specified test campaign; it does not prove complete parser correctness.

All 53 manifest hash prefixes matched at extraction and after the campaign. Every file touched by operators was additionally compared byte-for-byte with its Git blob at the pin and restored exactly. The full baseline and operator/failing-test results remain in [a24-baseline.json](/private/tmp/a24-baseline.json) and [a24-mutation-results.json](/private/tmp/a24-mutation-results.json).

## (F) Disk, cleanup and execution limits

Before:

```text
Filesystem        Size    Used   Avail Capacity iused ifree %iused  Mounted on
/dev/disk3s1s1   460Gi    13Gi    52Gi    20%    484k  552M    0%   /
```

After:

```text
Filesystem        Size    Used   Avail Capacity iused ifree %iused  Mounted on
/dev/disk3s1s1   460Gi    13Gi    52Gi    20%    484k  552M    0%   /
```

Deleted the single extracted root `/private/tmp/audit24-work` and all **66 directories present at final cleanup**, removing **387,035,376 bytes (369.1 MiB)** in 855 regular files. This includes the extracted tree, archived inputs, probe captures, refresh-chain data and rebuilt tables, quote fixtures, generated bundles, copied-data archive and runtime temporary files. Earlier runner cleanup removed `pytest-00` through `pytest-28` and `mut-tests`, all below that same root; temporary fixture descendants were not individually inventoried before each earlier removal. Root absence confirms that none remain beneath it. The exact final directory inventory is retained in [a24-cleanup.json](/private/tmp/a24-cleanup.json). No second repository tree was created.

Only small flat helper/evidence files remain under `/private/tmp`. A process-list check found no remaining audit jobs. Long work used bounded background wrappers: baseline batches had a 530-second total cap; each replay had a 530-second cap; the complete mutation batch took about 169 seconds. The two baseline batches took about 587 seconds **combined**, not in one command. All were completed long before the prohibited 22:30Z–23:45Z load window. Some sandboxed parquet inspections printed denied hardware-information queries; the reads completed, and no required audit check remained tool-blocked.

Only this requested reply was written in the repository. No branch checkout, commit, production refresh, live odds pull, freeze or bet was performed. Unavailable evidence remains explicit: the deleted audit-#23 prediction JSON, the exact 00:52Z live response, the original patch-file bytes, the selftest's original import arguments and the incomplete MNF process's original exit record. None is silently counted as verified.
