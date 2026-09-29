# Work order FWD1c — revisions per reader, no_view at the floor, week-4 dry run (2026-09-29)

Written by Cowork after verifying FWD1b (`fwd1b_verification_2026-09-29.md`, D218). This continues on eng/fwd1, which
is not merged. **It must be verified and merged before the TNF run at 23:30Z Thu 10-01.** No engine change.

Pre-check (Cowork):
- **Runtime.** Items 0 and 1 are two small edits to `nfl/pipeline/log_ai_opinions.py` and `nfl/sim/run_forward_v1.py`
  plus tests: minutes. Item 2 is one run_week for week 4, about 3.5 min for 15-16 games at N=10,000 (the week-2 log:
  209 s for 17 games), and writes no frozen file.
- **Credits.** Zero; everything reads the tape.
- **Files.** `log_ai_opinions.py` (the `prior_revisions` and `freeze` validation, at the lines D215/D216 cite),
  `run_forward_v1.py`, `nfl/sim/tests/test_forward_v1.py`, and a new
  `nfl/pipeline/tests/test_log_ai_opinions_fwd1c.py` in the directory where the logger's own tests live (find it and
  cite it).
- **Facts.** The manifest entries carry `reader_model` (from N62 on) and `pilot`. The 09-24 file has no
  `reader_model` key.

```
Work order FWD1c (research/nfl_sim/workorder_FWD1c_2026-09-29.md). Continue on branch eng/fwd1 in a worktree from
origin/eng/fwd1. Gates (git fetch origin first): `git rev-parse --short=9 origin/eng/fwd1` prints 54efc5878, and
`git show origin/main:research/nfl_sim/fwd1b_verification_2026-09-29.md | grep -c "^### D218"` prints 1; if either
fails, STOP and print both. FIRST COMMIT: append the D218 block from that file VERBATIM at the end of
research/nfl_sim/NFL_SIM_DECISION_v1.md. Then items 0-2, ONE COMMIT PER ITEM, push each before the next; decisions
D219-D221 appended in the same commit as their code. Session log appended to logs/_log_fwd1.txt (git add -f),
timestamps from `date -u`. When done, remove this order's worktree.

HARD RULES: (1) Do NOT modify any file FREEZE_v1 hashes; test_freeze_v1 before every commit, paste the line.
(2) Every code claim cites file:line. (3) Every new test calls the real function and FAILS on origin/eng/fwd1 @
54efc5878 — run it there first and paste the failure. (4) Never edit or re-hash an existing frozen file or manifest
entry; the stored revision values in existing files stay as they are. (5) nflverse week numbers only.

Item 0 (D219) — revisions per reader. log_ai_opinions.prior_revisions counts earlier files of ANY reader, so the
  second reader to freeze a line gets revision 1 and is never scored (pilot: 158 of the sim's 178 opinions). Change it
  so a new file's revision counts only earlier files with the SAME reader_model AND the SAME pilot flag (read both
  from the manifest entry; an entry with no reader_model counts as reader "legacy", which matches nothing new).
  Scoring is unchanged: it still scores revision 0, now meaning each reader's first opinion on a line. Tests, through
  freeze() on a temp week directory: (a) reader A freezes a line, then reader B freezes it -> B's row is revision 0;
  (b) reader B freezes it again -> revision 1; (c) a pilot file of reader B, then a live file of reader B -> the live
  row is revision 0. Add one sentence to the module docstring's scoring block recording the change and its date, and
  state in D219 that the pre-registered rule "only revision 0 is scored" now reads per reader.

Item 1 (D220) — no_view at the floor. fill_sheet (run_forward_v1.py) tags one-way lines whose book probability is
  outside [0.02, 0.98] as "sim_v1 ... no signal book_p", because freeze() rejects a no_view whose p differs from the
  book by more than 0.005. Fix the validator: a no_view line must carry clip(book, P_MIN, P_MAX) within NO_VIEW_TOL.
  Delete the sim_v1 fallback branch in fill_sheet. After the change, sim_v1 rows == matched two-way prop rows
  exactly; assert that inside fill_sheet. Tests: a +7500 anytime-TD row gets tag no_view and freeze() accepts it;
  on a fixture sheet the count of sim_v1 rows equals the matched count.

Item 2 (D221) — week-4 dry run, live path. Add --dry-run to run_forward_v1.py: steps (a)-(d) and (f) as normal, then
  print the matched count by market, the tag counts, and the sidecar table, and STOP before freeze. It writes nothing
  under nfl/data/board/ (test it: the ai_opinions directory is unchanged byte for byte). Run it now:
  `run_forward_v1.py --week 4 --dry-run --window-hours 60` (real now; TNF PIT@CLE kicks 10-02 00:15Z, so it is
  inside 60 h from 09-29 12:15Z on, and no Sunday game is — check that and say so). Deliver:
  - the schedule's week-4 matchups (print them, and state that nflreadpy returned them);
  - the lines found and the sidecar;
  - matched rows by market, and the newest Hard Rock props pull time for PIT@CLE.
  Then run the full forward and logger test files plus test_freeze_v1, and paste the pass counts.

Every item's report separates what the command RETURNED from what it MEANS and ends with NOT DONE and UNVERIFIED.
```
