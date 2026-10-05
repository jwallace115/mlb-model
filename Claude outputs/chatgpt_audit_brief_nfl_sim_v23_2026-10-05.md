# ChatGPT audit brief #24 (v23): FWD7n (D282), the audit #23 repair, for a PRIMARY MNF (2026-10-05)

`PINSHA: 955f7101ea2b5ad7338644c4c6094bbfb1e522cb`

Your audit #23 (NO-GO at `b842af343`) is at `~/mlb-model/research/cross_ai/chatgpt_audit23_reply_2026-10-04.md`.
Cowork accepted its one code blocker in full in **D282** (`research/nfl_sim/NFL_SIM_DECISION_v1.md`; read D282 first,
then D281). Posture: guilty until proven innocent.

**Pin: `955f7101ea2b5ad7338644c4c6094bbfb1e522cb` on branch `eng/fwd6`** ("FWD7n Mac run: …"). Put the full SHA you
audit on line 2. The chain:
- `955f7101e…`, the Mac run record. It adds only `research/nfl_sim/fwd7n_mac_run.md`.
- `CODESHA` = `b1de3b50d80f45c3ec469d5fbb731bf3d0a048dd`, "FWD7n (D282): …", the code commit. Its parent is
  `b842af343`.
- `b842af343`, your audit #23 pin.
- **There are no Sunday window commits:** S1 (IND@WAS) and S2 (main + SNF) did not run on 2026-10-04. The Mac was not
  running them.

The code commit touches only:
- `nfl/sim/official_injuries.py`;
- `nfl/sim/tests/test_fwd7g.py`;
- `research/nfl_sim/FWD_EXPERIMENT_v1.json` (one hash);
- the decision log;
- `research/nfl_sim/mutations/d278_mutations.py`.

Check it with `git diff --stat b842af343 b1de3b50d` and `git diff --stat b1de3b50d 955f7101e`.

**The only remaining window this week is MNF ATL@NO** (kick Tue 2026-10-06 00:15Z).
- The Monday refresh must be done by 23:00Z, with the manual props pull at 23:00Z and the harness at 23:30Z.
- **Your GO is needed by Mon 2026-10-05 23:15Z.**
- IND@WAS and the Sunday main + SNF slate were declared pilots, and then they did not run at all.
- **Mac load:** your audit #23 baseline and mutation replay were cut short by time limits. There is no window between
  now and Monday 22:30Z, so please complete the full baseline (29 files) and the full mutation script this time. Run
  them in bounded background batches if needed. Do not run anything heavy on the Mac from Mon 22:30Z to 23:45Z.

## What Cowork verified against the files (Mon 10:50Z), and one discrepancy in the record

**Verified:**
- `eng/fwd6` on GitHub = `955f7101e…`.
- The diff b842af343..b1de3b50d has the same `git patch-id --stable` (7ee2b014…) as the cloud-built D282 commit
  806441b5d. The patch sha256 is f4724750….
- The record commit adds only `fwd7n_mac_run.md`.
- D282 is in the decision log at the code commit.

**Discrepancy:** the step 7 re-run in `fwd7n_mac_run.md` does not match the directory it names.
- The quote sync was followed by **two** dry runs, `20261005T103258Z` and `20261005T103352Z`. Only one was authorised.
- **The record transcribes `103352Z`** as reaching "(f) anchor sidecar … DRY RUN complete", with run_id 103352Z in
  the sidecar table.
- **That directory has no `anchor_sidecar.parquet`,** and its bundle manifest was never finalised (21 entries,
  outputs not hashed). Its last file was written at 10:34:36, after `outputs/`. So that run stopped somewhere between
  output validation and the sidecar, and the record's (f) section cannot have come from it.
- **`103258Z` did complete through (f):** it has the sidecar and a finalised 31-entry manifest. Its sidecar has the same
  values as the record's table (anch_m 2.1622, anch_t 47.5566, 3 iterations, converged, anchored) but its own run_id.
  Its picks_log equals 103352Z's (85 legs, identical sim_p and cal_p), and both bundles have the same props and lines
  hashes (Props 65).
- **How Cowork reads this:** the substance (Props 65, Matched 13/43, a completed primary-path dry run) is supported by
  `103258Z`'s files. The record's transcript of `103352Z` is spliced or mislabelled. We do not know why `103352Z`
  stopped (killed, or a HALT between (e) and (f) such as the D229 price check).
- **Please treat the step 7 transcript as unverified.** If you can, re-run the PRIMARY-path dry run yourself on a copy,
  with `--dry-run --allow-stale-quotes`.
- **Also:** in step 1 the record calls fbc1b34e4 "FWD7m (D282)". Its real subject is "FWD7m (D281)".

The cause of the first dry-run HALT (`20261005T010236Z`, "zero sim matches") is confirmed from its bundle: props.parquet
had 0 rows and lines.parquet held the Sep 30 21:00Z snapshot. The worktree's quotes had not been synced from
origin/main. That was the gate refusing an empty freeze, not a code fault.

## How to work — and the Mac's disk

1. **Create the reply file first.** Write `research/cross_ai/chatgpt_audit24_reply_2026-10-05.md` in `~/mlb-model`.
   - Line 1 is a title, line 2 the SHA, and line 3 INCOMPLETE. Rewrite it after every check, and put the per-window
     verdict on line 3 as soon as P1 is decided.
   - Read code only from the pinned tree, and work only on copies. Do not commit or check out a branch in
     `~/mlb-model`.
2. **DISK.** Use ONE extracted tree under `/private/tmp`, delete every directory you created, and report `df -h /`
   before and after.
3. **Each command must finish in under 10 minutes**; use `nohup … &` for long jobs.
4. **If a tool is blocked, say which check it blocked and move on.**
5. **Distinguish executed from read.**

## What D282 claims (verify each)

1. **`official_injuries._section_body`** replaces the whole-document `<!--.*?-->` substitution. The document is split at
   the section opening tag. Each piece is scanned from its start (text context) with one pattern that matches one of
   four things:
   - a comment, dropped only when it starts in text;
   - the section's real `</section>`, where the section ends;
   - a whole tag, matched including its quoted and unquoted attribute values;
   - a bare `<`, which is kept, so the existing checks HALT on it.
   A comment delimiter inside an attribute value therefore stays inside its tag. Your case HALTs, because the D279b
   check refuses `<!--` in a section.
2. **Fail closed:**
   - abruptly or incorrectly closed comments (`<!-->`, `<!--->`, `--!>`);
   - a section piece with no real `</section>` outside comments and values (for example `</section>` inside an
     attribute, or a section-opening string inside a comment);
   - a raw `<` or `>` in any attribute value. This turns your earlier admitted "quoted `>` on inline attributes" control
     into a HALT; entity-encoded `&lt;` and `&gt;` remain allowed. The real page has none.
3. **Controls identical to clean:**
   - a real comment containing markup and quotes between rows;
   - a comment inside a cell;
   - a comment containing `</section> </tr>` after a row's last cell;
   - an encoded `&lt;!--` attribute value.
4. **Real pages.**
   - The Oct 2 capture (313 rows; its only comments are `<!--[if IE 9]>…`) is frame-equal to D279b-D281.
   - The Mac run (record steps 3 and 4) found:
     - the live page on Oct 5 00:52Z has 318 rows and 32 teams, and the four controls are identical to clean;
     - all ten attacks HALT;
     - on the installed capture (Sat 23:10Z), the clean replay equals the installed injuries;
     - all four audit chains HALT with nothing written.
5. **Tests and mutations.**
   - test_fwd7g has 55, and forward is 372 passed on the Mac (record step 6).
   - Cowork ran 81 operators: 79 killed. X2 and Z21 survive, as you judged at audit #23.

## P1: decides GO or NO-GO for MNF

1. **The full forward baseline**, file by file (all 29 files).
2. **Your audit #23 A1, end to end on the pin:**
   - the aria-label and href captures through the actual `official_step`, usage builder and non-pilot bootstrap,
     exactly as you ran them. Expected: a HALT before any overlay write, and no bundle;
   - then the clean chain. Your 86-prediction replay must be exact.
3. **Your 52 + 23 probes, plus new ones aimed at the scanner itself.** Each must HALT or keep the consumed
   (team, gsis_id, report_status) set identical. Ideas:
   - comment edge forms; `<!` declarations; `</` with odd names;
   - attribute values with newlines; unquoted values;
   - CDATA; nested sections; the section opening string inside text.
   Report any input ADMITTED with a changed set: that is the only kind of finding that decides P1.
4. **The full mutation script** on ONE tree. Report any survivor besides X2 and Z21.

## P2: if time remains

5. Any remaining way for what a person sees on the page and what the parser consumes to differ without a HALT.
6. The step 7 discrepancy above: does anything in the harness's (e)→(f) path stop a dry run silently (exit 0 with no
   sidecar)?

## Reply format

Use:
- **(E) first:** GO or NO-GO for a PRIMARY MNF at this pin;
- **(A)** must-fix before a primary (ranked, file:line);
- **(B)** the P1 table;
- **(C)** P2 and bypasses;
- **(D)** survivors;
- **(F)** `df -h /` before and after, and the directories you created and deleted.

Write nothing else to the repository.
