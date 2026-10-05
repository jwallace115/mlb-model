# NBA-S0c — legacy report URL zero-padding, re-fetch the legacy era, per-date roles (2026-10-05)

Pre-check: runtime — legacy-era dates 2024-10-22..2025-12-21 (~224) x ~3 requests (backward hourly search from the
cutoff usually hits in 1-2; plus the <= 5 PM report) ~= 700 requests x (0.5 s sleep + ~0.5 s) ~= 12 min; two parsers on
~450 new PDFs ~= 25 min; total ~40 min, under 2 h (STOP if the measured projection exceeds 2 h). Credits 0. NBA-owned
paths only. Same worktree ~/mlb-model-nbaS0, branch nba/s0.

```
NBA-S0c. Fresh Claude Code session. `git -C ~/mlb-model branch --show-current` must print main, else STOP. Read CLAUDE.md
(WORK ORDERS, ENVIRONMENT TRAPS), ~/mlb-model/research/nba_layers/nbaS0_verification_2026-10-05.md (read the S0b section)
and this file ~/mlb-model/research/nba_layers/workorder_S0c_2026-10-05.md (both UNTRACKED in the main checkout — copy
both into the worktree's research/nba_layers/ in your first commit). Existing worktree ~/mlb-model-nbaS0, branch nba/s0.
Commit AND push each item; B21-B23 APPENDED at the END of the decision doc in the same commit (never edit B14-B20).
New tests must FAIL on 01c7ca076 running that commit's code — paste the failure. Pre-register before computing. No
installs, 0 credits. Do not merge.

Item 1 (B21) — zero-padded legacy URLs and a re-fetch of the legacy era.
  a) legacy_report_url builds `_{h12:02d}{AM|PM}`. TEST: 17 -> "_05PM", 9 -> "_09AM", 12 -> "_12PM" (FAILS on
     01c7ca076). Cross-check: nba/data/injury_reports/2023-10-24_1700.parquet came from `..._05PM.pdf` (old
     nba/scripts/pull_injury_reports.py uses %I%p) — print that URL form.
  b) For every legacy-era game date (format change date as in the code), re-run the pre-tip search (latest hourly
     report <= first tip - 30 min) and the freeze search (latest hourly report <= 5 PM ET). Raw PDFs into the main
     checkout's excluded history/season=<yr>/ as before.
  c) New committed table data/injury_archive/nba/history_parsed/roles.parquet: one row per (game_date, role in {pre_tip,
     freeze}) -> url, sha256, slot_et, published_utc, status. Built for ALL dates (legacy and new format).
  PRE-REGISTER: >= 95% of legacy-era dates get a pre_tip report with slot >= 17:00 ET; >= 95% get a freeze report at
  05PM; the share of legacy pre_tip files equal to the 12PM file falls from ~100% to <= 5%. NULL: every new-format date
  (>= the change date) has roles rows identical to what 01c7ca076's files imply (same url and sha256).

Item 2 (B22) — legacy context window, pre-registered.
  Legacy reports are hourly, so the binding window [slot, slot+30 min] cannot hold for them (B18: 12PM header 12:45).
  Rule: legacy-format files use [slot, slot+60 min]; new-format files keep [slot, slot+30 min]. PRE-REGISTER the count of
  legacy files that change status under the new rule BEFORE re-parsing (expected: the B18 context_mismatch files become
  ok; no new-format file changes). Re-parse every legacy-era file with both parsers; report status counts by season and
  role; A==B rate by season (a shortfall is stated, not explained away).
  TEST: a legacy file with header 45 min after its slot is ok; a new-format file 45 min after its slot is context_mismatch
  (both against real files from the archive).

Item 3 (B23) — regenerate the committed parsed history.
  Rebuild history_parsed/season=<yr>/ and manifest.parquet from the re-fetched + re-parsed files; the superseded noon-only
  parsed files for legacy dates are removed from the tree (git history keeps them). Print: files added / removed /
  unchanged, total MB (< 20 MB). B23 states that B16/B19 rows for legacy-era dates are superseded and why.

Closing: session log (git add -f logs/agent_sessions.md): RETURNED vs MEANS, NOT DONE, UNVERIFIED. Push. STOP.
```
