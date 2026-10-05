# Audit #23 — FWD7m / D281
b842af34355c0646a811f6353cbfb3015d4091e0
(E) IND@WAS: NO-GO; main + SNF: NO-GO; MNF: NO-GO for a PRIMARY at this pin.

The audit-#22 encoded-style defect is fixed, as is the audit-#21 six-cell defect. A new counterexample removes a visible Out status before D281's attribute validation runs. The real refresh and usage builder then make Daniels active; both injury-gate modes verify that changed input. This is a defect demonstrated on an edited copy, not evidence that the installed capture is contaminated. Data-only commits cannot repair it. Decide pilot status before each harness unless a subsequent code pin receives its own timely GO.

D281 and D280 were read; the diff from a7e2d7683 contains exactly the six files identified in the brief. Work used one extracted copy of the full pin above. Engine, anchor, calibration, pricer and fit internals were not reviewed; the clean worker was executed as a black box. Unchanged findings from audits #21/#22 carry forward; newly executed checks and their limits follow. Supporting checks are incomplete: repeated time limits prevented a full fresh baseline and mutation replay. The NO-GO is decided by the brief's executed changed-input criterion, not by treating those unfinished checks as successes.

## (A) Must fix before a primary

**1. Remove only actual HTML comment tokens, preserving quoted attribute values.** [nfl/sim/official_injuries.py:112](https://github.com/jwallace115/mlb-model/blob/b842af34355c0646a811f6353cbfb3015d4091e0/nfl/sim/official_injuries.py#L112), before the validation call at line 154.

In the archived Jayden Daniels row (WAS, GSIS `00-0039910`), replace:

```html
<td>Out</td>
```

with:

```html
<td><a aria-label="<!--">Out</a><a aria-label="-->"></a></td>
```

Both attributes are permitted on `a` by D281. They contain quoted values, not HTML comments. The unchanged pin nevertheless applies the whole-document `<!--.*?-->` substitution before parsing. It removes the text spanning those two attribute values, turning this into:

```html
<td><a aria-label=""></a></td>
```

**Executed:** the stdlib HTML parser sees text Out and zero comments. Parsing the full edited capture with html5lib 1.1 yields five cells and Out in the fifth cell, again with zero comments there. The pinned parser/mapper admits 318 rows but changes `(WAS, 00-0039910, Out)` to `(WAS, 00-0039910, blank)`. The same construction with `href` also admits the changed status.

Actual `official_step` → actual usage builder → historical-row splice changes Daniels's active flag false→true in weeks 4 and 5. WAS's current active count rises **16→17**, nonblank official statuses fall **6→5**, and `_active_universe_matches` reports no mismatch. Both `OI.check(require=True)` and `OI.check(require=False)` verify IND and WAS. The edited capture record's byte count and SHA-256 were recomputed, so this is semantic misinterpretation of correctly recorded bytes.

**Worker limit:** the altered non-pilot dry run passes the freeze-test gate, experiment checks and freshness checks, marks both teams officially verified, and enters the simulation. It then reaches the **450-second worker limit**. I do not claim convergence, completed predictions, a successful full run, or probability deltas for that case. The blocker rests on the changed consumed status and executed refresh/gate acceptance, as the brief's P1 criterion specifies.

**Required repair:** tokenize original HTML with quote-aware handling before removing comments; remove only actual comment nodes, or fail closed on unsupported comment-delimiter placement. Run structural and attribute checks on the same token stream used for status extraction. Do not feed validation a string whose meaningful content has already been deleted by a context-free substitution. Add the two quoted-attribute cases above to parse, refresh/no-write, and both gate-mode tests; retain the actual commented-out-row control, the two old counterexamples, and the clean 86-prediction replay.

**Quote path:** the brief now includes a fetch before restoring origin/main's quote paths into the harness worktree. That resolves audit #22's stale-remote-reference concern as a procedure. The loader/output-directory findings carry forward because those code paths are unchanged. I did not read the external window-prompt file or execute live fetches/pulls/restores; its implementation and the forthcoming selected timestamps remain operational checks. No stale-quote override should be used for a primary.

## (B) P1 and D281 claims

| Check | Verdict | Evidence |
|---|---|---|
| Audit #22 encoded hidden status | FIXED | Parser HALTs on unsupported style; real refresh writes nothing and never calls the usage builder or creates a bundle; both injury-gate modes HALT. |
| Audit #21 six-cell status | FIXED | Same parse/refresh/no-write result; both gate modes HALT on TH outside a cell. |
| Previous 52 probes | HOLDS | 39 HALT, 13 identical consumed sets, zero admitted changes. Earlier benign attributes now fail closed as declared. |
| New attribute/quoting probes | FAILS | 23 cases: 5 HALT, 16 identical, 2 admitted changed sets. The two changed cases are A1. |
| Clean full replay | HOLDS | Actual refresh/build/bootstrap exits 0; 1 game converges, bundle verification returns no errors, 45 reads and zero recorded violations. All 86 prediction rows match audit #22 exactly except run_id and board_generated_utc. Both rebuilt usage/active tables equal the archive. |
| Full forward baseline | PARTIAL | **189 passed, 2 skipped across 18/29 completed files.** The remaining files were not fully rerun before this report; the earlier unchanged-code results carry forward only as prior evidence. The current-pin claim of 369 passing forward tests is **not independently reproduced**. The two settlement skips require unavailable 2026 snap-count / GSIS–PFR data; they are not passes. |
| Committed 77-operator campaign | PARTIAL | **17/77 completed; 17 killed by named failing tests; 0 survived.** Survivors: none observed. |

D281 claim 1 is **PARTIAL**: the allowlists and decoding operate as stated on the post-substitution sections, but they do not validate all original section content. A1 is erased before `_section_markup` runs. The declared outside-section stylesheet/wrapper boundary is **acceptable as an explicit source assumption for this narrow P1 audit**; it is not proof of visual equivalence to a browser. A1 lies inside a supported team-table cell and requires no CSS or outside wrapper change, so that boundary does not excuse it.

Claims 2 and 3 **HOLD for the executed old counterexamples and controls**: style/hidden/unsupported attributes are rejected by name; formerly benign unsupported structures fail closed; permitted encoded class and quoting variants preserve the consumed set. The old M1 mutation no longer has a matching raw-style-regex target.

Claim 4 **HOLDS on both available archived pages**. The newly located Oct 2 capture has **313 rows, 32 teams, 130 nonblank statuses**, SHA-256 `b8e53c975e29b78dd7f13e450e7d0678bc49abae0af8441698eda1a47fe76da2`; it is frame-equal under D279b, D280 and this pin. The installed 23:10Z capture has **318 rows, 32 teams, 138 nonblank statuses**, SHA-256 `2711f526d7a38581ba1a6a7a7ea79a2244ae7e457cf88c393c51bd35cefcb83f`, also frame-equal across those versions. Clean `official_step` reproduces all **35,864** installed injury rows. The exact historical 05:22Z live-page bytes were not independently retrieved; those time-specific observations are not separately verified.

Claim 5: the test inventory is **52 injury tests / 369 expected forward tests**. Executed baseline and mutation outcomes are reported separately below rather than treating expected totals as passes.

**Recomputed Mac bundle:** `20261004T061542Z` has **28/28 verified teams, 14 events, 14/14 converged games, 45 read-set entries = 14 bundled + 31 pinned**, **0 unproven, 0 hash mismatches, 0 recorded violations/conflicts**; bundle verification returns no errors. These numerical claims **HOLD**. It records `pilot=false` and `allow_stale_quotes=true`, so it demonstrates a dry-run path, not fresh production quotes. The separate selftest attempt timed out at 120 seconds; I have not reproduced its reported success or exact module/dependency counts in this audit. The clean non-pilot bootstrap itself completed, as reported above.

Per-file results for this audit:

| File | Passed | Skipped | Coverage |
|---|---:|---:|---|
| `test_forward_v1.py` | 8 | 0 | Complete |
| `test_freeze_v1.py` | 4 | 0 | Complete |
| `test_fwd2_anchor.py` | 3 | 0 | Complete |
| `test_fwd2_bundle.py` | 5 | 0 | Complete |
| `test_fwd2_experiment.py` | 6 | 0 | Complete |
| `test_fwd2_item0_fixes.py` | 7 | 0 | Complete |
| `test_fwd2_settlement.py` | 10 | 2 | Complete |
| `test_fwd2b_harness.py` | 0 | 0 | Incomplete: bounded attempt timed out |
| `test_fwd3_item0.py` | 0 | 0 | Not rerun in this audit |
| `test_fwd3_item1.py` | 3 | 0 | Complete |
| `test_fwd3_item2.py` | 8 | 0 | Complete |
| `test_fwd4_item0.py` | 0 | 0 | Not rerun in this audit |
| `test_fwd4_item1.py` | 4 | 0 | Complete |
| `test_fwd5_pin.py` | 4 | 0 | Complete |
| `test_fwd6_item0.py` | 0 | 0 | Not rerun in this audit |
| `test_fwd6_item1.py` | 0 | 0 | Not rerun in this audit |
| `test_fwd6_item2.py` | 0 | 0 | Not rerun in this audit |
| `test_fwd6_item3.py` | 0 | 0 | Not rerun in this audit |
| `test_fwd6b.py` | 0 | 0 | Not rerun in this audit |
| `test_fwd6c.py` | 0 | 0 | Not rerun in this audit |
| `test_fwd6d.py` | 0 | 0 | Not rerun in this audit |
| `test_fwd6e.py` | 0 | 0 | Not rerun in this audit |
| `test_fwd6f.py` | 11 | 0 | Complete |
| `test_fwd7a.py` | 27 | 0 | Complete |
| `test_fwd7c.py` | 11 | 0 | Complete |
| `test_fwd7d.py` | 7 | 0 | Complete |
| `test_fwd7e.py` | 7 | 0 | Complete |
| `test_fwd7f.py` | 12 | 0 | Complete |
| `test_fwd7g.py` | 52 | 0 | Complete |

## (C) P2 and bypasses

The 52 prior cases cover TH/extra/missing cells, stray text, nested markup, row/cell attributes, entities, whitespace/newlines, uppercase tags and quoted angle brackets. Every case now halts or preserves the consumed set.

The 23 new cases cover allowed aria-label/href values, empty and valueless permitted attributes, duplicate class/aria-label attributes, entity-encoded attribute names, single/unquoted/backtick quoting, uppercase attribute names, encoded allowed classes, and scope/tabindex. Unknown names and disallowed classes halt; the admitted controls preserve the status. Duplicate attributes with a disallowed class halt regardless of order. Attribute-name entities are rejected rather than treated as a valid style/class name. The two A1 cases survive; they are one underlying defect.

A1 is CSS-free. HTML attribute values containing comment delimiters must not become comment tokens. The independent HTML5 parse and the pinned parser disagree on the same archived edited bytes. No unexecuted possibility is promoted to an additional blocker.

## (D) Surviving mutations

**17/77 completed; 17 killed by named failing tests; 0 survived.** Survivors: none observed. The exact registered operators and focused tests from the pinned script were executed in bounded batches on the same extracted tree; changed operators were prioritized after the first batch. An interrupted or timed-out operator is not counted as killed. Every mutation was restored and final source hashes were checked. **Not completed:** W18–W24, X1–X23 and Z1–Z30. Z17 was attempted twice and timed out without a named failing test; that is not a kill. Cowork’s reported 75/77 result and two full-suite survivors are not independently reproduced here.

**X2** leaves the earlier rejection of blank PBP values intact. **Z21** removes the cell-local stray-angle-bracket check but leaves the section-wide check. Independent in-memory execution of the exact Z21 edit on the archived stray-angle-bracket probe HALTs under both versions. The shared diagnostic substring is `unparseable markup`; the full messages differ (row-content error versus section-markup error). Thus the admission result is unchanged for this counterexample, but “same message” is only true of the test’s matched substring, not the complete error.

The old M1 raw-visibility-regex mutation has no target at this pin. The old encoded/literal style probes now HALT by attribute name. No new survivor is needed to establish A1: its counterexample runs on the unmodified pin, despite the changed-file tests passing.

## (F) Disk, cleanup and limits

Before:

```text
Filesystem        Size    Used   Avail Capacity iused ifree %iused  Mounted on
/dev/disk3s1s1   460Gi    13Gi    20Gi    40%    484k  214M    0%   /
```

After:

```text
Filesystem        Size    Used   Avail Capacity iused ifree %iused  Mounted on
/dev/disk3s1s1   460Gi    13Gi    18Gi    42%    484k  191M    0%   /
```

Deleted the single extracted root `/private/tmp/audit23-work` and its 49 remaining directories, including its tree, archived inputs, probes, chain inputs, runtime-temp directories, generated run/archive artifacts and pytest fixtures. Removed 239.4 MiB of files. No per-mutant repository extraction was made. The final-cleanup directory inventory is in `/private/tmp/a23-cleanup.json`; only small flat evidence/helper files remain. All 53 source-manifest hashes matched before deletion. The process check found no remaining audit jobs. Earlier runner cleanup removed `pytest-00` through `pytest-18`, `mut-tests`, and generated run directories `20261004T071624Z`, `20261004T105018Z`, all beneath that same root. Internal fixture children were not separately inventoried before those earlier removals; root absence confirms none remain there. Volume-wide free space fell from 20 GiB to 18 GiB during the audit interval; I have not established the cause of that system-wide change.

One procedural miss: the altered replay's worker was capped at 450 seconds, but its preceding rebuild brought the outer wrapper to **606.22 seconds** (measured from job-log creation to result write), six seconds over the requested ten-minute command limit. Subsequent baseline and mutation batches have a total batch cap.

Only this requested reply was written in the repository. No branch checkout, commit, production refresh, quote pull, freeze or bet was performed. The initial process-list check was blocked by the sandbox; the approved read-only retry completed and found no remaining audit processes. The fresh baseline remains limited as stated above. Mutation completion is 17/77. The altered worker timed out; no altered prediction comparison is claimed. No production execution or external window-prompt file was verified.

Small flat evidence files under `/private/tmp` include `a23-deep-probes.json`, `a23-new-probes.json`, `a23-html5-dom.json`, the three `a23-chain-*.json` records, `a23-real-pages.json`, `a23-independent.json`, `a23-prediction-comparison.json`, and baseline/mutation results. The clean replay used the same old quote fixture and dry-run stale-quote override as audit #22; this does not validate production quote freshness.
