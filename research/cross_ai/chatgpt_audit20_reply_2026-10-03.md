# Audit #20 — FWD7i / D278: NO-GO for primary windows
cd5cfeb8be7ce826c151bce65985fa2a2725ad08

COMPLETE — 2026-10-03. The full clean replay hit the execution bound; that verification limit is reported explicitly below.

Read D277 and D278 in full before execution. Source was extracted from this exact pin to `/private/tmp/nfl-audit20-cd5cfeb8b`; all **53** experiment-manifest hashes match. All **15** copied files from the `20261003T154843Z/refreshed` archive match their manifest. Testing used copies. No source changes, branch checkout, commit, live input refresh, wager or primary freeze were performed. The only repository write is this report. The simulation engine, anchor, calibration, pricer, K1 and fits were not audited.

“Executed” below identifies a running counterexample or test. “Read/judgment” identifies interpretation. A valid manifest proves which bytes were used; it does not prove that the parser retained their meaning.

## (A) Must-fix before a primary, ranked

### A1 — The parser silently omits additional table bodies; the refresh and primary gate agree on the same incomplete report

**Location:** [`nfl/sim/official_injuries.py:138`](https://github.com/jwallace115/mlb-model/blob/cd5cfeb8be7ce826c151bce65985fa2a2725ad08/nfl/sim/official_injuries.py#L138), especially `body[0] if body else ""` at line 139. The omitted rows then become authoritative through [`refresh_inputs.py:126`](https://github.com/jwallace115/mlb-model/blob/cd5cfeb8be7ce826c151bce65985fa2a2725ad08/nfl/sim/refresh_inputs.py#L126) and the same parser's reconciliation at [`official_injuries.py:377`](https://github.com/jwallace115/mlb-model/blob/cd5cfeb8be7ce826c151bce65985fa2a2725ad08/nfl/sim/official_injuries.py#L377).

**Executed counterexample on the real capture:** In Washington's existing table, insert `</tbody><tbody>` immediately after the first player's row (Nick Allegretti). No player, position, injury, practice status or game status is changed or removed. Multiple table bodies are valid HTML. Recompute the capture's byte count and SHA256; retain its authentic URL, final URL, season/week and retrieval time.

An independent HTML parser still counts **313 player rows**. The pinned parser returns **299**: Washington's **15 rows become one**, because only the first body is traversed. Its remaining row has no game designation. The discarded second body still visibly contains Jayden Daniels **Out**, Rachaad White **Out**, and the other 12 omitted rows.

Then run the **actual `official_step`**, substituting these bytes only for its network response, followed by the **actual usage builder**, and finally the **actual non-pilot bootstrap dry run** on the resulting inputs. It **exits 0**:

- IND and WAS both `official_verified=True`;
- WAS is recorded as **one official row / zero game statuses**;
- Daniels and White become active in **weeks 4 and 5: four false→true active flags**;
- one game converges; **45 recorded reads, zero read-set violations**; bundle verification finds no errors;
- against the independently verified saved clean Mac run, **75 common prediction rows change `sim_p`; 43 change `cal_p`; maximum absolute difference is 0.1392 (13.92 percentage points)**. The saved clean output has 86 rows, the bad output 82, with 75 matching prediction keys. The separate raw-PBP-only run retains clean tables and reproduces all 86 clean probabilities exactly, providing a same-session control.

The week-4 usage shares and starting-QB flag do not change in this example; the active-universe corruption is sufficient to change worker predictions. This is not just a hypothetical malformed record or a forged injury designation: a structural regrouping of unchanged report rows defeats the claimed completeness check. The authentic archived page itself has not been shown to contain this structure.

**Required repair:** Parse all supported table bodies/rows, or reject any unsupported body structure before overlay. Do not turn a missing/unrecognized body into a successful empty report, and do not ignore bodies after the first. Reconcile independently counted source player rows with emitted rows per team. Add end-to-end tests for multiple bodies, a body with attributes, missing bodies, and a genuinely empty supported table. Either all 313 rows must survive unchanged in this example, or refresh must HALT before writing installed inputs. Its primary run must never mark the truncated report verified.

**Related executed case:** replacing Washington's `<tbody>` with `<tbody class="report-body">` loses all 15 rows. Direct official verification can accept that as empty after overlay, but the actual bootstrap HALTs at the older “no injury report” freshness check. I do **not** claim this whole-team version completes a primary worker; the partial-loss version above does.

Evidence: [parser counts](/private/tmp/a20-tbody-split-parse.json), [actual refresh/build effects](/private/tmp/a20-tbody-split-builder.json), [completed worker](/private/tmp/a20-gate-tbody-split.json), [prediction comparison](/private/tmp/a20-worker-impact.json). Reproduction: `/private/tmp/a20_partial_body.py`, `/private/tmp/a20_tbody_split_build.py`, `/private/tmp/a20_gate_runs.py tbody-split`. All test capture changes are in temporary copies; this bypass executes the unmodified pinned source.

This is the primary-blocking finding. The narrower corrections and incomplete claims below should be fixed or explicitly qualified; they are not additional claims that every successful guard remains broken.

## (B) P1 table and audit #19 repairs

| P1 check | Independently executed result | Verdict |
|---|---|---|
| 1. Forward baseline, files separately | **350 passed across 29 files, zero skips.** `test_fwd7g`: **34**; `test_fwd7f`: **11**. | **HOLDS.** |
| 1. Four usage files, tune deselected | **22 passed, one deselected**, zero skips. Bootstrap selftest exits 0 and launcher hash matches; 12 repository modules, 1,090 dependency files, 6,395 distribution files. | **HOLDS.** Python 3.13.1 here, not a claim to have repeated Cowork's other runtime environments. |
| 2. Prior A1: row 6404 `posteam=""` | Actual usage builder rejects before either output write. Null team/type/receiver and string season also reject; both season loaders reject string season. | **FIXED at the builder; PARTIAL against the brief's demand for worker rejection.** See the precise distinction below. |
| 2. Prior A2: NaT and 2099 | Actual non-pilot IND@WAS bootstrap rejects **both**. Direct gate with the explicit Sunday cutoff `2026-10-04T12:45Z` also rejects both. | **FIXED.** |
| 2. Prior A3: page relabelled 2025, IND–CHI/NYJ–WAS, foreign URL, HTTP 500, bytes=1 | Each rehashed/copied case HALTs the actual non-pilot IND@WAS bootstrap for the corresponding context error. Wrong matchup direct test rejects all four participating teams. | **FIXED for the original counterexamples.** A new row-completeness bypass survives in A1 above. |
| 2. Clean all-Sunday dry run | Both audit attempts passed **28/28** official-team checks; full worker replay exceeded the bound (first 520 s, retry **500.04 s**). Independently inspecting the saved pinned Mac bundle verifies **14/14 converged, 45 reads, zero violations, matching archived inputs and no bundle-verification errors**. | **PARTIAL:** clean gate reproduced; saved full-run claim supported by artifacts; full-slate worker completion **not independently replayed** within the command limit. |
| 3. Blank/whitespace and team-domain variants | Whitespace-only team, receiver and play type; lowercase `ind`; and unknown `XYZ` each reject through the actual usage builder, with **zero output writes**. | **HOLDS.** |
| 3. Time/URL/page variants | Non-UTC offset normalizes and passes; naive and NaT cutoffs reject. `final_url` with and without `/` passes. Correct canonical/wrong title and wrong canonical/correct title each reject. Swapped home/away rejects. | **HOLDS** for these executed direct-gate cases. |
| 4. Three roster moves | Exact committed active tables differ on only **six rows**, three players in weeks 4/5. Re-pulled week-4 rosters independently show Humphrey **ACT→CUT**, Smith **ACT→CUT**, Brooks **ACT→RES**. | **HOLDS for the named moves; qualify “nothing else changed” as below.** |
| 5. Procedure | Generator reproduces the runbook apart from its generated timestamp. Saturday MNF deadline is now explicit. Future morning refreshes and evidence commits were not performed by this audit. | **Written procedure partly corrected; future execution remains required.** Runbook still names audit #19, which returned NO-GO. |

**A1 builder versus worker:** With the malformed raw PBP but the clean precomputed tables retained, the worker still produces one converged game, 45 reads/zero violations and a verified runtime record. Both teams verify. All **86** matched predictions equal the clean saved run. `_last_played_weeks` reads game/team/date-completion fields; it does not call `_pbp_admission` on the play fields ([`run_forward_v1.py:134`](https://github.com/jwallace115/mlb-model/blob/cd5cfeb8be7ce826c151bce65985fa2a2725ad08/nfl/sim/run_forward_v1.py#L134)). The launching audit wrapper timed out; the worker subsequently completed, so its artifacts establish execution, while the parent exit code is unavailable.

Thus the brief's literal “worker must now HALT” claim is **false**. It is also **not a reproduction of the old changed-prediction builder chain**: the repaired builder refuses to create those corrupt tables. If worker-level admission is required, run the same check on the copied raw PBP before dispatch. Otherwise explicitly state that this invariant is enforced at build time; do not present a builder rejection as an executed worker rejection. [Artifacts and limitations](/private/tmp/a20-partial-effects.json), [unchanged predictions](/private/tmp/a20-raw-only-impact.json).

**Real-data recomputation:** The archived capture has **313/313 identified rows, 32 teams, 16 matchups and 130 game statuses**; its recorded `final_url` equals its request URL. Cross-checking actual roster positions yields **91 skill/skill, 222 non-skill/non-skill, zero cross-boundary matches**. All **303,486** raw 2020–2026 PBP rows pass admission, with zero blank values across all six admission keys and zero unknown non-null team codes. The fit-window fingerprint is **`3638769c89030de0`**; all eight installed tables match the archive and their non-2026 rows match the previous archive. The committed capture record and refresh manifest match the archived evidence. [Recomputation](/private/tmp/a20-inputs.json).

**Roster-change sizing:** In `3635e300c` versus `9d747c96a`, the six changed active-universe rows have:

| Player | Team | Roster status | Active flag | Weeks |
|---|---|---|---|---|
| Lil'Jordan Humphrey | DEN | ACT→CUT | true→false | 4 and 5 |
| Xavier Smith | LA | ACT→CUT | true→false | 4 and 5 |
| British Brooks | HOU | ACT→RES | true→false | 4 and 5 |

There are **six `injury_status` column changes too**: `Active→CUT/RES` on those same rows. No other active-table columns change; depth and position are unchanged. These are derived roster-status labels, not new official injury designations. The committed tables support the roster explanation; “no injury-designation changes” must not be reported as “the injury_status column is unchanged.”

The independent clean rebuild equals the installed 2026 slices: **4,106 active rows and 2,554 usage rows**. Week-4 depth is **724/802**. Point-in-time checks for W2/W3/W4 pass: active slices **786/794/802**, usage slices **513/518/503**, with QB and depth-layer mappings equal. Starting QBs remain **Case Keenum / Jalon Daniels / Marcus Mariota** for CHI/TB/WAS. [Rebuild/PIT results](/private/tmp/a20-pit.json).

The feed's reported “zero official-Out skill players missing from the freshly pulled feed at 15:48” is **not independently established by the archived post-overlay injuries file**: that file has already had the official rows applied. The raw acquisition response before overlay is not among the 15 archived files. I do not infer its contents from the successful refresh log. Likewise, I did not rerun the old D277 builder to verify the brief's **1.25%** figure; the repaired builder's actual rejection is established directly.

D278's other claims, individually:

1. **Blank/domain admission — HOLDS at the builder**, with the worker qualification above.
2. **Retrieval time and cutoff — HOLDS** for the enumerated malformed/offset/cutoff tests. `build_bundle` supplies `T`; the refresh report supplies current UTC. NaT, null, empty, naive and garbage retrieval strings reject.
3. **Season/week/record/matchup identity — HOLDS for the repaired cases.** The implementation normalizes trailing slashes on canonical/final URLs; it is not byte-exact URL equality. It even accepts multiple trailing slashes; queries or foreign seasons tested here reject. Row completeness is separate and fails A1.
4. **Refresh derives before installation — HOLDS**, and the tests reject bad record/page cases before installed writes. This shared derivation is also why both refresh and gate share A1's parser error.
5. **Skill boundary — HOLDS.** TE→CB rejects. Duplicate normalized names with different IDs reject as ambiguous; moving the skill-player roster entry to another team rejects. Actual 91/222 counts hold.
6. **Section-keyed overlay — FIXED locally, PARTIAL end to end.** A genuine empty section clears feed rows and can pass `official_injuries.check`. The older primary freshness gate still rejects the resulting empty injury set; see C.
7. **Audit #19 survivors — FIXED.** M02/N01/N02's new killing tests are reached by the exact committed mutation campaign.
8. **Mutation campaign — HOLDS**, with X2's equivalence boundary described in D.
9. **Corrections — PARTIAL documentation consistency.** D278 adopts the skill-row exception, pilot integrity failures and snapshot-finality limitation. Input version is D278-v8 and Saturday is stated. The runbook still says any unidentified row HALTs and still requires audit #19 GO; those sentences lag D278.

Initial extraction omitted a committed week-2 test artifact and the usage checkout's historical PBP. Those omissions caused one skip and setup failures; the pinned artifact and copied historical inputs were supplied and the affected files rerun successfully. One baseline batch exhausted its wall-time allowance; its remaining files were rerun individually/in a smaller batch. The final 350/22 counts use the completed reruns, not the failed or skipped attempts. Full-slate replay timeouts are retained as limits, not counted as passes; the retry kills its process group at the bound. [Final per-file results](/private/tmp/a20-baseline-final.json); [attempt history](/private/tmp/a20-valid-index.jsonl).

## (C) P2 and remaining bypasses

**Partial table-body loss is the surviving primary bypass.** Its capture's hashes are correct, its recorded retrieval precedes the cutoff and follows the deadline, canonical/title and matchups are correct, and the consumed rows equal the rows re-derived by the same lossy parser. None of those checks establishes that every source row was parsed. The successful worker means this is reachable, not a merely present code branch.

**Verified-empty remains inconsistent across gates.** [`run_forward_v1.py:252`](https://github.com/jwallace115/mlb-model/blob/cd5cfeb8be7ce826c151bce65985fa2a2725ad08/nfl/sim/run_forward_v1.py#L252) unconditionally treats `inj.empty` as a freshness failure before the official verification runs. Direct tests accept an intentionally empty WAS section after overlay. Separately, the actual attribute-loss refresh/build produces an empty WAS injury set, and its actual bootstrap rejects that set as “no injury report.” Reading the unconditional guard shows why a genuinely empty report hits the same refusal. Direct official-gate acceptance therefore does not establish primary-path acceptance. Preserve the older refusal until source completeness is repaired, then distinguish **verified empty** from **unverified/missing** using the official result. Current NYG has eight named rows with blank designations and does not hit this zero-row case.

**Runbook inconsistency — read:** [`fwd1_runbook.md:47`](https://github.com/jwallace115/mlb-model/blob/cd5cfeb8be7ce826c151bce65985fa2a2725ad08/research/nfl_sim/fwd1_runbook.md#L47) and its other window blocks still say “audit #19 is GO.” Audit #19 is NO-GO. D278's broader “a ChatGPT audit is GO on a repaired pin” is the intended current condition. Update the generator as well as the runbook before using a later audit to authorize primary. The generic unidentified-row sentence at line 15 also needs the declared skill-row qualification.

**Finality — judgment:** no publication time was added. D278 correctly reclassifies finality as a prospective snapshot rule. Keep the stated deadline/cutoff bounds, complete source parsing, per-team reconciliation and pre-harness evidence commit; unresolved timing remains pilot. A majority of teams with nonblank statuses does not prove another team's completeness. This audit does not rerun audit #19's 857-row historical identity comparison; that prior result remains scoped to the weeks and identity resolutions in its report.

## (D) Mutations and survivors

Executed the exact pinned `research/nfl_sim/mutations/d278_mutations.py` on a copy and saved each pytest result, including the failed test name. **47 operators executed; no missing anchors; 46 killed; X2 survives.** The focused unchanged control is **46 passed**. W1–W24 and X1–X23 are now available to reproduce, unlike the previous brief's unspecified campaign.

**X2 judgment:** admission-equivalent, not necessarily diagnostic-text-equivalent. It removes the conversion of blank keys to null. X1's independent blank-key rule still rejects every such row; for a row without blanks, the removed assignments do nothing. Thus it does not change accepted versus rejected input on this function's normal supported inputs, although the list of additional error reasons can differ. Calling this an unclosed primary bypass would be incorrect.

I added three independent operators; **all three survive the same 46 tests**, and each has an executed non-equivalence example:

| Survivor | Mutation | Original versus mutant |
|---|---|---|
| Y1 | Reject timezone offsets other than UTC in `retrieval_time` | `2026-10-03T11:48:51.308172-04:00` correctly normalizes to 15:48:51Z in the original; mutant rejects it. |
| Y2 | Remove trailing-slash normalization from record `final_url` comparison | Authentic URL with one trailing `/` derives all 313 rows in the original; mutant rejects it. |
| Y3 | Uppercase `posteam` before its domain check | Real row 6404 with `posteam="ind"` rejects in the original; mutant accepts it. |

These are coverage gaps: Y1/Y2 would cause false rejections, Y3 would relax the declared domain. They are not claims that those three faulty behaviors exist in the unmodified code. Add the requested offset/slash/lowercase variants to the committed tests. A1 additionally needs independent source-row completeness tests; the current fixtures use one unadorned body per table and never expose the shared parser omission.

[Committed campaign results](/private/tmp/a20-cowork-mutations.json), [independent campaign](/private/tmp/a20-own-mutations.json), [non-equivalence evidence](/private/tmp/a20-more-evidence.json). Drivers: `/private/tmp/a20_mutation_campaign.py`, `/private/tmp/a20_own_mutations.py`, `/private/tmp/a20_more_evidence.py`. No repository tests were changed.

## (E) Per-window primary decision

| Window | At this pin | Required disposition |
|---|---|---|
| IND@WAS — Sun Oct 4 12:45Z harness | **NO-GO** | Declare pilot unless A1 is repaired and independently cleared before the harness. Game-morning refresh done by **12:15Z**, manual props pull **12:15Z**, evidence for the actual capture exported and committed before the harness. |
| Main + SNF — Sun Oct 4 16:15Z harness | **NO-GO** | Same parser admission defect. If re-refreshed, finish by **15:45Z** and commit that capture's evidence. Confirm the **16:00Z** quote pull arrived. |
| ATL@NO — Mon Oct 5 23:30Z harness | **NO-GO** | Same defect plus the current archive was fetched before the **Sat Oct 3 20:00Z** final-report deadline. A later admissible capture, game-morning refresh, evidence commit, and **23:00Z** manual props pull remain required. Finish any last refresh by **23:00Z**. Kickoff is Tue Oct 6 **00:15Z**. |

The 15:48 capture verifies **30 teams** under the current direct gate; ATL/NO are correctly false as too early. That is not proof of their future report's availability. Saturday's capture is not Sunday's game-morning refresh. The operational evidence commit must describe the capture the particular harness consumes.

D278's prospective amendment remains legitimate as a rule fixed before the affected outcomes, but its prerequisite of an independent GO is not met. TNF stays pilot, and no pilot is promoted after outcomes. The repaired original counterexamples, passing baseline, and exact historical-variable comparison do not overcome an executed path that drops unchanged official Out rows, declares the incomplete report verified and changes primary-path predictions.
