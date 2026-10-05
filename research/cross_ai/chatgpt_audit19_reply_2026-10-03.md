# Audit #19 — FWD7g/FWD7h: NO-GO for primary windows at this pin
a1ce31e6d053c247ca497713b40a3ad50b404c6b

COMPLETE — 2026-10-03. Read D276 and D277, including the FWD7h addendum, before testing. All reviewed source came from the pinned Git archive, extracted to `/private/tmp/nfl-audit19-a1ce31e6d`; no source was read from the moving `~/mlb-model` checkout. All 53 experiment-manifest file hashes matched. Source inputs came from the 05:59 refresh archive and the installed input checkout; mutations used copies. The only repository write is this reply. No branch checkout, commit, live refresh, wager, or primary freeze was performed. The simulation engine, anchor, calibration, pricer, K1 and fits were not audited.

**Executed** below means I ran the pinned code or an explicitly identified mutant. **Read/judgment** identifies conclusions from code or research design. Passing examples establish only the tested cases.

## (A) Must-fix before a primary, ranked

### A1 — Blank PBP team identifiers still change predictions without rejection

**Location:** [`nfl/sim/usage.py:422`](https://github.com/jwallace115/mlb-model/blob/a1ce31e6d053c247ca497713b40a3ad50b404c6b/nfl/sim/usage.py#L422), and the adjacent admission rules at 423–429.

**Executed counterexample:** In a copy of `pbp_2026.parquet`, set `posteam=""` on row 6404: game `2026_03_HOU_IND`, play 173, a completed nine-yard Tyler Warren reception. Run the actual usage builder. It succeeds and writes both output tables. Against the clean rebuild, **16 of 506 week-4 target shares change**, maximum absolute difference **0.006473825450496601**.

Then supply those rebuilt tables and the changed raw PBP to the actual isolated bootstrap, with the authentic official-report capture. The non-pilot IND@WAS dry run completes: **both teams officially verified, one converged game, 45 recorded reads, zero read-set violations, and bundle verification returns no errors**. Among 86 matched prediction rows, **18 `cal_p` values change, maximum 0.0452; 39 `sim_p` values change, maximum 0.0290**. Three filled-sheet probabilities change, maximum **0.0287**. Separate one-game timestamp-only controls exactly reproduce the clean IND@WAS probabilities, ruling out the full-slate versus one-game run as the explanation.

The prior `None` cases are fixed; `isna()` does not reject empty strings. This is a reproducible malformed-input admission defect, not evidence that the authentic PBP currently contains blank teams. I checked all **303,486** available 2020–2026 raw rows: they pass the pinned admission function; no blank/whitespace team strings occur on pass/run plays in that corpus.

**Required repair:** On fields required by each play's context, reject null, empty and whitespace-only identifiers; validate team identifiers against the supported team domain. Keep legitimate keyless administrative plays and receiverless sacks/throwaways admissible. Add this actual completed-pass case, require rejection before either table write, and repeat the eight-table rollback check. Do not silently drop or coerce the bad row.

Evidence: [builder results](/private/tmp/a19-cases.json), [worker result](/private/tmp/a19-gate-blank-posteam.json), [numerical comparisons](/private/tmp/a19-final-evidence.json). Reproduction drivers: `/private/tmp/a19_cases.py`, `/private/tmp/a19_gate_runs.py`, `/private/tmp/a19_final_evidence.py`.

### A2 — “Verified after the deadline and before the cutoff” accepts NaT and year 2099

**Locations:** [`official_injuries.py:277`](https://github.com/jwallace115/mlb-model/blob/a1ce31e6d053c247ca497713b40a3ad50b404c6b/nfl/sim/official_injuries.py#L277), comparison at 290; [`run_forward_v1.py:519`](https://github.com/jwallace115/mlb-model/blob/a1ce31e6d053c247ca497713b40a3ad50b404c6b/nfl/sim/run_forward_v1.py#L519).

**Executed counterexamples:** Change only the copied capture record's `fetched_utc`, first to `"NaT"`, then to `"2099-01-01T00:00:00+00:00"`. Each actual non-pilot IND@WAS bootstrap dry run exits **0**, marks both teams **`official_verified=True`**, converges and records **45 reads / zero violations**. The authentic HTML hash and injury rows are unchanged.

`pd.Timestamp("NaT") < deadline` is false, so missing time passes. A future timestamp also passes because the gate has no upper bound and does not receive bundle cutoff `T`. D277's research claim that nothing after the cutoff enters is therefore not enforced here. The existing positive test actually supplies **2099** and expects acceptance: [`test_fwd7g.py:379`](https://github.com/jwallace115/mlb-model/blob/a1ce31e6d053c247ca497713b40a3ad50b404c6b/nfl/sim/tests/test_fwd7g.py#L379).

**Required repair:** Require a finite, timezone-aware timestamp, normalize to UTC, and enforce **final-report deadline ≤ retrieval time ≤ bundle cutoff T**. Pass `T` to the gate. Reject missing/NaT/naive/unparseable times and future-relative-to-T records. The normal fetch function records the present time; these tests expose unsafe admission of a bad record, not a claim that the committed record has a false timestamp.

Evidence: [NaT run](/private/tmp/a19-gate-nat.json), [2099 run](/private/tmp/a19-gate-future.json). Driver: `/private/tmp/a19_gate_runs.py`.

### A3 — The gate does not bind the page's season or matchups to the requested report

**Locations:** [`official_injuries.py:96`](https://github.com/jwallace115/mlb-model/blob/a1ce31e6d053c247ca497713b40a3ad50b404c6b/nfl/sim/official_injuries.py#L96), `derive` at 238–251, and team reconciliation at 281–300.

**Executed direct-gate counterexamples, using copies of the real capture:**

- Relabel the page's season title, H1, canonical URL and Open Graph URL from 2026 to 2025, preserve its week-4 heading and rows, and recompute the record hash while leaving its declared season 2026. **IND and WAS both verify.** The record is checked against the requested season, but the page is not checked against that record.
- Rebuild the two real matchup sections as **IND–CHI and NYJ–WAS**, keeping each team's original player/status rows and matching table titles. Rehash the page. The gate verifies **all four teams**, although the schedule says IND–WAS and NYJ–CHI. Parsed `opp` is never reconciled with the schedule.
- Independently set record URL to `https://example.invalid/unrelated`, HTTP status to `500`, or byte count to `1`. Each still verifies. Only the record's hash and season/week are enforced.

These are direct `OI.check(..., require=True)` executions, not completed worker runs. They demonstrate an unproved source/game identity claim; they do not establish changed probabilities or an error in the authentic 05:59 capture.

**Required repair:** Bind the capture to the expected official season/week URL and the page's own season/week identifiers. Record and validate the final response URL and successful response metadata. Reconcile each participating team's parsed opponent with its unique season/week schedule game. Keep exact injury-row reconciliation. Add these rehashed wrong-context cases; ordinary hash-corruption tests cannot cover them.

Evidence and reproduction: [bypass results](/private/tmp/a19-bypasses.json), `/private/tmp/a19_bypasses.py`.

## (B) P1 results

| P1 check | Independent result | Verdict and limit |
|---|---|---|
| 1. Baseline | Ran all 29 forward files separately: **338 passed, zero skipped**. Four usage files: **22 passed, one tune test deselected**. `test_fwd7g.py`: **23 passed**. Bootstrap selftest exits 0; launcher hash matches. | **HOLDS.** Runtime here: Python 3.13.1, pandas 2.3.3, pyarrow 23.0.1. This does not imply the new counterexamples are covered. |
| 2. Check 3, historical variable identity | Fetched 2025 weeks 3, 4 and 5 with the pinned SSL fetcher; parsed with pinned code and an independent parser; compared with freshly loaded nflreadpy 2025 injuries. **281/281, 290/290, 286/286 statuses agree**, respectively, after the explicit identity resolutions below: **857/857**, zero final status or Out/Doubtful decision disagreements. | **HOLDS for this sample.** No systematic injury-status variable difference found. Historical final-state agreement does not establish historical publication timing or eliminate D272's late-inactive difference. |
| 3. Independent current re-derivation | Independent BeautifulSoup parser and separate name/ID matching recover **313 rows / 32 teams / 313 identified**, equal to the committed CSV and installed week-4 `(team, gsis_id, report_status)` rows. **70 Out, 2 Doubtful, 58 Questionable = 130 designations.** | **HOLDS.** All 15 archived input files match their manifest hashes; committed capture record and refresh manifest equal the local archive. |
| 3. Live re-fetch | At **2026-10-03 06:28:17.818201Z**, HTTP 200, **404,361 bytes**, SHA256 `d473f4ca958e2d0fb4695f8c8988a690d210217cc33a16e0389247f684174fe9`. Compared with the 05:59 capture, **zero added or removed parsed rows, all seven parsed fields equal**. HTML bytes differ. | **HOLDS for 05:59→06:28**. No injury-row update observed. I did not locate/read the 01:29 HTML, so Cowork's specific 01:29→05:59 equality claim remains **UNVERIFIED**. |
| 4. Real primary negatives and clean run | All five requested negative cases halt the actual non-pilot dry run. Clean all-Sunday run: **28/28 verified, 14/14 converged, 45 reads, zero violations**, valid bundle. Four pilot cases proceed and record false for affected teams; changed-byte pilot also halts. | **PARTIAL against the brief's wording**: primary negatives hold; “pilot always proceeds” is false for hash corruption. A2 shows other admitted bad records. |
| 4. SSL enforcement | Pinned fetcher fails against actual self-signed and wrong-host HTTPS endpoints with certificate-verification errors; normal NFL fetches succeed. | **HOLDS.** Verification is enforced in these real requests. |
| 5. Active universe and rebuild | **38 active_flag changes = 19 players × weeks 4 and 5**, all true→false and official Out. **Zero** depth, position or roster-status changes; **72 injury_status label changes**. CHI **Case Keenum**, TB **Jalon Daniels**, WAS **Marcus Mariota** flagged starting QBs. **Zero of 22 official Out/Doubtful skill rows active**, including every Sunday team's such rows. | **HOLDS.** 20 official-Out skill players absent/non-Out in the old feed; Zach Charbonnet was already inactive/RES, explaining 20 versus 19. |
| 5. Independent rebuild/PIT | Installed 2026 slices equal fresh pinned rebuilds: active **4,106 rows**, usage **2,561**. W2/W3/W4 point-in-time active slices **786/794/802** and usage **513/518/506** match, including QB and depth-layer mappings. Week-4 non-null depth **724/802**. | **HOLDS.** Historical table rows remain unchanged; input fingerprint **`3638769c89030de0`**, D277-v7. |
| 6. Procedure/finality | Runbook regenerates identically apart from generation time. Sunday deadline computes **Fri Oct 2 20:00Z**; MNF **Sat Oct 3 20:00Z**. Current archive verifies all 28 Sunday teams; ATL/NO fail as early. | **CONDITIONAL design judgment; NO-GO implementation.** Detailed finality rule and window prerequisites below. |

Historical identity disagreements were **name/roster representation**, not different injury decisions:

- **C.J. West / CJ West**, SF, weeks 4 and 5: same GSIS **00-0040711**; roster alternate name resolves it. A literal normalized-name join initially creates an apparent missing pair; resolving by that ID removes it.
- **Zach Bako-Bewele / Zach Tom**, GB: official page and injury feed use Zach Bako-Bewele; weekly roster still uses Zach Tom, GSIS **00-0037817**. Same official/feed status in weeks 3 and 4. Pinned mapper leaves this non-skill tackle unidentified and omits him.
- **Rob Beal Jr. / Robert Beal Jr.**, SF, week 5: GSIS **00-0038603**. Resolved explicitly; the official player's link is `/players/robert-beal-jr/`. The pinned mapper omits this unmatched non-skill DE.

After these disclosed resolutions: **zero genuinely missing players, zero status differences, zero conflicting resolved IDs**, and no skill-player ID omissions in the sampled weeks. Pinned mapping alone identifies **280/281, 289/290, 285/286**; it does not achieve 857/857 roster identification. All **6,068** freshly downloaded 2025 injury ID/status rows also equal the archived historical feed after canonicalizing numeric season/week fields. An initial full-string comparison differed on numeric representation; that is not an injury disagreement.

Primary sources fetched: [2025 week 3](https://www.nfl.com/injuries/league/2025/reg3), [week 4](https://www.nfl.com/injuries/league/2025/reg4), [week 5](https://www.nfl.com/injuries/league/2025/reg5), [2026 week 4](https://www.nfl.com/injuries/league/2026/reg4). Reproductions/results: `/private/tmp/a19_parse_independent.py`, `/private/tmp/a19_history_resolve.py`, [resolved comparison](/private/tmp/a19-history-resolved.json), [active effects](/private/tmp/a19-effects.json), [PIT/rebuild](/private/tmp/a19-pit.json).

The requested real gate matrix was:

| Copied-input change | Non-pilot dry run | Pilot dry run |
|---|---|---|
| Append one byte to HTML; leave recorded hash unchanged | HALT | **HALT**, hash mismatch |
| Retrieval `2026-10-02T19:59:59Z` | HALT | Completes; IND/WAS false |
| Flip one consumed IND report status | HALT | Completes; IND false, WAS true |
| Remove IND–WAS matchup section and rehash | HALT | Completes; IND/WAS false |
| Remove HTML and capture record | HALT | Completes; IND/WAS false |
| Authentic capture, all Sunday games | Completes; 28/28 verified | Not needed |

Removing that real HTML section removes both teams; it is a stricter missing-section test, not a claim that only one table was removed. The bad-byte pilot failure is appropriate integrity enforcement and is explicitly tested in the committed suite. Correct the blanket pilot claim; **do not weaken hashing to make the pilot proceed**.

These used the real bootstrap/worker with `--dry-run --allow-stale-quotes`, archived quotes, and copied inputs. The clean run selected all 14 Sunday games; negative cases selected IND@WAS to bound runtime. They test primary input-admission logic without placing bets or creating a primary freeze. The stale-quote exception means this is not approval of Sunday's eventual quotes. Longest clean run: **473.56 seconds**, below the ten-minute limit. [Clean result](/private/tmp/a19-gate-clean.json); other cases are `/private/tmp/a19-gate-{byte,early,flip,section,missing}.json` and the corresponding `-pilot.json` files.

D276/audit-18 regressions: null `posteam`, null `play_type`, null completed-pass receiver, and string-typed season **all reject before either table write**. Both season loaders reject the string type. Executing the actual refresh exception/restore path with offline acquisition stubs and the real usage builder restores **all eight original table hashes** in each case. Thus the specific null/type fixes are **FIXED**; the broader missing-key admission claim is **PARTIAL**, because A1 survives. [Rollback evidence](/private/tmp/a19-restore.json).

For completeness, the brief's eight FWD7g claims are adjudicated individually:

| Claim | Verdict |
|---|---|
| 1. Parser accepts only the expected week's page | **PARTIAL.** Listed structural, week-heading, header and status checks exist and pass tested rejects; season and scheduled matchup identity are absent (A3). |
| 2. Team/week name mapping | **HOLDS as stated for current data:** 313/313. Unmatched skill rows, ambiguous names and duplicate IDs reject; unmatched non-skill rows may remain unidentified. Position is not an identity constraint; see C. |
| 3. Overlay scope/dtypes | **HOLDS on actual inputs and tests.** Rows outside the specified season/week/page teams have equal values, column order and dtypes. Whole-parquet byte identity is not the claim: the file is rewritten. |
| 4. Refresh sequencing and “nothing written unless every row identified” | **PARTIAL.** Fetch/parse/map/overlay/capture/archive sequencing and stale-capture removal are implemented and tested. The quoted absolute statement is false: unresolved non-skill rows are allowed and excluded by design (`official_injuries.py:190`; `refresh_inputs.py:137`). |
| 5. Per-team gate | **PARTIAL.** Hash, declared season/week, team rows and status reconciliation reject the requested negatives. Time and page context have A2/A3 holes; a pilot cannot bypass malformed-byte integrity. |
| 6. Exact active effect/QBs | **HOLDS**, with the independently recomputed numbers above. |
| 7. Conditional declaration/runbook | **HOLDS as a written prospective rule.** The default commands omit `--pilot`; the operator must apply the stated condition. This audit gives no primary GO. |
| 8. Tests and W1–W24 all killed | **23 tests HOLDS. Full mutation claim UNVERIFIED.** W21/W24 re-created and killed; the other 22 operators are not specified in pinned D277. Independent survivors follow. |

Baseline per-file evidence: [index with exit codes, counts and log paths](/private/tmp/a19-valid-index.jsonl). No test file failed. Per-file counts follow to make the 338/22 totals reviewable:

| Test file (under `nfl/sim/tests/`) | Result |
|---|---|
| `test_board_5j2.py` | 4 passed |
| `test_forward_v1.py` | 8 passed |
| `test_freeze_v1.py` | 4 passed |
| `test_fwd2_anchor.py` | 3 passed |
| `test_fwd2_bundle.py` | 5 passed |
| `test_fwd2_experiment.py` | 6 passed |
| `test_fwd2_item0_fixes.py` | 7 passed |
| `test_fwd2_settlement.py` | 12 passed, 1 warning |
| `test_fwd2b_harness.py` | 10 passed |
| `test_fwd3_item0.py` | 9 passed |
| `test_fwd3_item1.py` | 3 passed |
| `test_fwd3_item2.py` | 8 passed |
| `test_fwd4_item0.py` | 9 passed |
| `test_fwd4_item1.py` | 4 passed |
| `test_fwd5_pin.py` | 4 passed |
| `test_fwd6_item0.py` | 13 passed |
| `test_fwd6_item1.py` | 12 passed |
| `test_fwd6_item2.py` | 9 passed |
| `test_fwd6_item3.py` | 5 passed |
| `test_fwd6b.py` | 39 passed |
| `test_fwd6c.py` | 33 passed |
| `test_fwd6d.py` | 33 passed |
| `test_fwd6e.py` | 6 passed |
| `test_fwd6f.py` | 11 passed |
| `test_fwd7a.py` | 27 passed |
| `test_fwd7c.py` | 11 passed |
| `test_fwd7d.py` | 7 passed |
| `test_fwd7e.py` | 7 passed |
| `test_fwd7f.py` | 10 passed |
| `test_fwd7g.py` | 23 passed |
| `test_usage_5b.py` | 13 passed, 1 deselected, 2303 warnings |
| `test_usage_pit_5f.py` | 3 passed, 1432 warnings |
| `test_usage_pit_5j.py` | 2 passed |

## (C) P2 and bypasses

**Wrong week / wrong section — executed:** a record declaring week 3 and a page heading declaring week 3 both reject when week 4 is requested. Internally inconsistent matchup/table titles reject. But a wrong page season or wrong *internally consistent* matchup passes as described in A3. The latter distinguishes checking HTML self-consistency from checking the real game's identity.

**Name collision / trade — executed:** adding a second same-normalized-name player with a different ID and different position produces an ambiguous-name HALT. Moving the report's skill-player roster entry to another team also HALTs as unmatched; it is not silently joined across teams. However, changing the lone Travis Kelce roster candidate's position to CB still maps the report's TE row to that ID: `map_ids` drops roster position at line 150. I have not demonstrated such a wrong-position match in the actual current capture. Add a compatible-position check or explicit documented exception procedure; do not resolve collisions merely by taking the first ID.

**Section-present versus zero rows — read:** `check` uses `mapped[team].empty` as “no section.” A genuine empty table is therefore not represented separately from an absent section. Current NYG is **eight named rows with blank designations**, so it is not that zero-row edge case.

**MNF — executed plus explicit uncertainty:** current ATL/NO sections contain **5/10 rows**, zero designations, retrieved before Saturday 20:00Z; both fail. Merely changing the record to Saturday **20:01Z**, with identical HTML and injury rows, makes both pass the direct gate. That is a synthetic timestamp test, not evidence that their actual final reports were published. No code can establish today that a future Monday-morning fetch will carry the final report. It fetches the then-current page; the same season/week, cutoff and reconciliation checks must apply. The material calendar difference is Saturday's final-report deadline, rather than Friday's.

**Finality / verified-empty — judgment:** retrieval after the report deadline is a defensible *declared snapshot rule*, but it is not proof of a publication time or that a delayed page has become final. D277 must describe that limitation accurately. I would admit an empty designation set only when (1) a successful authenticated fetch identifies the correct season/week and scheduled matchup, (2) retrieval is within `[deadline,T]`, (3) an independently parsed, structurally present team report reconciles exactly, and (4) the evidence record is committed before the harness. If the page still appears to be an earlier practice report, cross-check the team's dated final report; unresolved timing means pilot. Do not substitute a quota of positive statuses for completeness.

The actual NYG capture has eight identified report rows and no game statuses; under that prospective snapshot definition, **NYG can be verified empty**, rather than failing because it has zero designations. That is conditional on source/time validation being repaired, not an assertion that nfl.com exposes a final-publication timestamp. The current all-blank ATL/NO report taken before its deadline cannot receive the same designation.

**Mutation reproducibility limit:** pinned D277 says W1–W23 were killed and names W21's schedule-count operator; the addendum names W24's missing-SSL-context operator. It does **not** list W1–W20/W22–W23 operations. I searched the pinned material and requested the missing script/list; none was supplied during this audit. I therefore do not claim to have rerun those 22 exact mutations or substitute my own numbering for Cowork's.

## (D) Surviving mutations

I ran **26 independent single-change mutations** in separate copied trees, updating the copied experiment hash where necessary. The focused selection contains **103 tests**, including all 23 FWD7g tests and relevant admission, refresh and isolation regressions. The unchanged control passes **103/103**. Results: **23 killed, three survived**. W21's relaxed duplicate-game count and W24's omitted SSL context were both killed. These results describe this explicit 103-test selection, not an unexecuted full-suite mutation campaign.

| Survivor | Exact mutation and location | Executed proof it is non-equivalent |
|---|---|---|
| M02_section_shape | Disable the two-teams/two-tables guard, `official_injuries.py:109` | Delete the KC table but retain both team headers and titles. Original rejects counts; mutant accepts three CAR rows and silently omits KC. **103 tests still pass.** |
| N01_ignore_record_season | At line 246, compare only record week instead of `(season,week)` | Give the actual capture a record declaring 2025 while deriving 2026 week 4. Original rejects; mutant accepts and maps **313 rows**. **103 tests still pass.** |
| N02_unknown_blank_names | Delete `or not td[0]` from line 131 | Add a five-cell row with empty player name, position G, game status Out. Original rejects malformed row; mutant accepts **six rows including the blank player**. **103 tests still pass.** |

Each survivor is a coverage gap in a guard that the unmodified code currently contains. It is not an additional claim that all three malformed examples pass the unmodified production gate. Tests must exercise these distinct cases; the current malformed-row test only removes a cell, so it cannot kill removal of the blank-name condition alone.

Complete operators and test selection: `/private/tmp/a19_mutations.py`. [Mutation log](/private/tmp/a19-mutations.log), [non-equivalence proofs](/private/tmp/a19-survivor-proofs.json), [unchanged control](/private/tmp/a19-focused-control.json). I did not modify repository tests. An initial mutation-copy attempt exhausted temporary disk space before running tests; incomplete copies were removed and the isolated campaign above completed. A process-inventory command was sandbox-blocked; all tracked audit job sessions were separately polled and completed, so that blocked command does not leave a substantive audit check pending.

## (E) Window decisions, D277 and Check 3

| Window | Primary verdict at this exact pin | Required operational disposition |
|---|---|---|
| IND@WAS, Sun Oct 4 12:45Z harness | **NO-GO** | Declare/run pilot unless a repaired pin is independently cleared before 12:45Z. Finish game-morning refresh by **12:15Z**, make the manual props pull at **12:15Z**, export and commit evidence of the actual capture before harness. |
| Sunday main + SNF, 16:15Z harness | **NO-GO** | Same A1–A3 defects. Preserve the declared game-morning refresh; if refreshed again for this window, finish by **15:45Z** and commit that capture's evidence. Confirm the **16:00Z** quote pull arrived. |
| ATL@NO, Mon Oct 5 23:30Z harness | **NO-GO** | Same defects plus no admissible final MNF capture yet. Fetch after **Sat Oct 3 20:00Z**, refresh on game morning, reconcile both teams and commit the capture before harness. Any last refresh must finish by **23:00Z**; manual props pull is **23:00Z**. Actual kickoff is Tue Oct 6 **00:15Z**. |

These future refreshes, quote arrivals and evidence commits are **prerequisites, not completed actions**. The existing Saturday capture does not fulfill the Sunday game-morning requirement, and the committed Saturday evidence cannot stand in for a later refresh. The runbook's generic “Friday afternoon” final-report wording should explicitly distinguish MNF's Saturday deadline. At this pin its primary-looking commands require the operator to add `--pilot` under the printed condition.

**D277 judgment:** superseding D276 before the affected windows' outcomes and before their harnesses is a legitimate prospective amendment, provided the change, source, verification definition and primary/pilot classification are fixed in advance. TNF remains pilot; a pilot window is never promoted after outcomes. D277 expressly requires this audit's GO, which it has not obtained. The correction of 19 actually inactive skill players is independently supported, but it does not excuse the remaining admission failures.

**Check 3 judgment:** the sampled evidence supports the official page supplying the same final injury-status variable: **857/857 resolved status agreements**, with no skill-player inactive-decision disagreement. It is a changed acquisition source for that variable, with separate source/timing obligations. It does not prove publication-time equivalence or erase D272's known difference between a morning live roster and historical final game-day rosters. The reason for NO-GO is the executed A1/A2 admission counterexamples and A3's missing context binding—not a demonstrated systematic difference in the injury-status variable.
