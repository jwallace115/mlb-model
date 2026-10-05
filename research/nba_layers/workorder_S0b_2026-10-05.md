# NBA-S0b — fix NOT-YET-SUBMITTED handling, commit the history, test the parser fix (2026-10-05)

Pre-check: runtime — re-parse 656 PDFs with both parsers (~2-3 s per tabula call) ~= 25-35 min, under 2 h; tests seconds.
Credits 0. Paths NBA-owned only. Same branch nba/s0, worktree ~/mlb-model-nbaS0.

```
NBA-S0b. Fresh Claude Code session on Jeff's Mac. `git -C ~/mlb-model branch --show-current` must print main, else STOP.
Read CLAUDE.md (WORK ORDERS, ENVIRONMENT TRAPS), ~/mlb-model/research/nba_layers/nbaS0_verification_2026-10-05.md and this
file ~/mlb-model/research/nba_layers/workorder_S0b_2026-10-05.md (both UNTRACKED in the main checkout — copy them into
the worktree's research/nba_layers/ in your first commit). Use the EXISTING worktree ~/mlb-model-nbaS0 on branch nba/s0.
Commit AND push each item; B17-B20 APPENDED at the END of research/nba_layers/NBA_LAYERS_DECISION_v1.md in the same commit
(never edit B14-B16 text). Every new test must FAIL on 771174b77 by running that commit's code — paste the failure.
Pre-register before computing; a failed prediction is reported, never tuned. NBA-owned paths only; no installs; 0 credits.
Do not merge.

Item 1 (B17) — NOT YET SUBMITTED is a status, never silence.
  Parser A and Parser B both emit a row (game_date, matchup, team, player="", status="NOT_YET_SUBMITTED") for every
  team line marked NOT YET SUBMITTED; the consumed set includes them; `verified_empty` only when the grammar matched and
  there are zero rows of ANY status. Print `pdftotext -layout` of both 2025-02-13 history PDFs (first 40 lines) and
  state what they contain. Re-parse all 656 history PDFs: per season, files with >= 1 NYS row, NYS rows total, files
  whose status changed vs B16.
  PRE-REGISTER: the 2025-02-13 files are not truly empty (they contain NYS rows or rows the grammar missed); >= 1% of
  pre-tip files carry at least one NYS team. NULL: every file with zero NYS rows keeps its B16 consumed set exactly.
  TEST (real PDF with NYS rows, chosen from the archive) — FAILS on 771174b77.

Item 2 (B18) — prove the pending_reason fix and the 2025-26 shortfall.
  a) Pick 3 of the 150 files that were parse_failed before the fix (from the first run's output or by re-running the
     079606ccf parser); copy them into nba/pipeline/tests/fixtures/ (< 2 MB total) and add tests that pass now and FAIL
     on 079606ccf's parser.
  b) For the 4 context_mismatch files (2025-12-20/21) print URL slot, header time, delta. State the cause from that
     evidence. If the binding rule is wrong for legacy hourly reports, say so and propose the rule — do not loosen it in
     this item.
  c) Write plainly: B16's "A == B >= 99%" did NOT hold for 2025-26 (98.8%).

Item 3 (B19) — data custody.
  Raw PDFs move to the MAIN checkout path ~/mlb-model/data/injury_archive/nba/history/season=<yr>/ (already excluded via
  the common .git/info/exclude; prove with `git -C ~/mlb-model check-ignore`). Committed, small: per-file parsed rows (ALL
  statuses incl. NOT_YET_SUBMITTED, with published_utc, slot_et, sha256 of the PDF) under
  data/injury_archive/nba/history_parsed/season=<yr>/, plus history_parsed/manifest.parquet (url, sha256, published_utc,
  status, n_rows, n_nys). Print sizes; commit only if the total is < 20 MB. `git ls-tree` must show the parsed files and 0
  PDFs. Do not delete the worktree copies.

Item 4 (B20) — RW@SH symmetry: record the verdict ONLY IF Jeff has written "accept symmetry" in this session; otherwise
  skip this item and list it under NOT DONE. If accepted: B20 records the recomputation in nbaS0_verification (sum -6.30%
  vs price-only -5.68%; null -5.71% vs -5.64%; same point 101/101), that the [-6.0, -2.0] band was Cowork's
  mis-specification (the sum is about two overrounds, not one), that no grader bug exists, and that the RW@SH numbers are
  unchanged.

Closing: session log (git add -f logs/agent_sessions.md): RETURNED vs MEANS, NOT DONE, UNVERIFIED. Push. STOP.
```
