# NBA-S0e work order — finish S0d (2026-10-06, NBA chat)

Source: claude/nba_s0d_verification_2026-10-06.md (D1–D4). Same branch nba/s0d, same worktree ~/mlb-model-nbaS0d.

## Pre-checks
- **Runtime.**
  - Parse ≤ ~130 PDFs with both parsers at ~3 s each ≈ 6.5 min.
  - Fetch the 5:30 report for 5 dates: ≤10 fetches ≈ 10 s.
  - Rebuild game_asof: seconds.
  - Total ≈ 10 min.
- **Credits.** 0. No ESPN calls are needed; tips are already stored.
- **Paths.**
  - Parsed files: `data/injury_archive/nba/history_parsed/season=<yr>/<name>.parquet` (existing convention).
  - Manifest: `history_parsed/manifest.parquet`.
  - Per-game file: `history_parsed/game_asof.parquet`.
  - Raw PDFs stay in the git-excluded main-checkout history dir.
- **Jeff's values.** The per-game cap with the 5:30 report (2026-10-05). Tip source: Odds API commence_time primary
  (D3); Cowork recommends accepting it.

## Prompt for Claude Code (Mac)
```
NBA lane, work order NBA-S0e (fixes to S0d). Read research/nba_layers/NBA_LAYERS_DECISION_v1.md (B24-B26) and
claude/nba_s0d_verification_2026-10-06.md (or the copy in research/nba_layers/).
GIT_OPTIONAL_LOCKS=0 on every git command. Work in the existing worktree ~/mlb-model-nbaS0d on branch nba/s0d.
~/mlb-model stays on main. No package installs. No Odds API calls. Expected runtime ~10 min. If over 1 hour, stop.

ITEM 1 (B27) - every referenced report is parsed and in the manifest.
 - For every filename in roles.parquet and game_asof.parquet that has no history_parsed parquet:
   - parse it with the B14 two-parser path;
   - write history_parsed/season=<yr>/<name>.parquet;
   - append a manifest row (same columns as today). Status must be ok.
   - If any file is not ok: report it, keep its manifest row with the real status, and do not let roles or
     game_asof point to it (re-select the next-earlier ok report).
 - PRE-REGISTERED:
   - referenced files without a parsed parquet: 0 (today 40 roles + 87 game_asof, overlapping; state the union);
   - manifest rows = 642 + that union;
   - NULL: the existing 642 manifest rows are byte-identical in filename, sha256, published_utc, status, n_rows, n_nys.

ITEM 2 (B28) - Jeff's rule on every date, including dates missing from the schedule file.
 - For every game in game_asof, the freeze report is that date's 5:30pm ET report (new: _05_30PM, legacy: _05PM).
   Fetch it if it is missing, and parse it per ITEM 1.
 - Apply the rule:
   - asof = freeze if published_utc <= tip_utc - 30 min;
   - otherwise asof = the latest ok report published <= tip_utc - 30 min.
 - Remove the fallback that skipped the freeze when a date had no roles freeze row.
 - Add a column date_in_schedule (bool).
 - Add roles rows for the 5 missing dates (2024-12-17, 2025-04-15, 2025-04-16, 2025-04-19, 2026-03-28).
 - Set 2026-04-11 status to not_game_date: its report lists only 04/12 games and no events exist.
 - PRE-REGISTERED:
   - games with tip >= 18:30 ET and asof_role != freeze: 0 (today 7);
   - these 7 games change to the 5:30 report: OKC-MIL 2024-12-17, ORL-ATL and GSW-MEM 2025-04-15,
     CHI-MIA and SAC-DAL 2025-04-16, MEM-CHI and PHX-UTA 2026-03-28;
   - asof published > tip - 30 min: 0;
   - NULL: every game on the 328 schedule dates keeps the same asof_filename and sha256 as at 9beb9125d.

ITEM 3 - decision doc.
 Append B27-B29 to NBA_LAYERS_DECISION_v1.md:
 - B27/B28 as above.
 - B29 corrects the S0d report: B25 NULL DID NOT HOLD (2,153/2,160). The 7 were not all non-regular-season
   (2026-03-28 is regular season); the cause was the missing-freeze fallback.
 - B29 also records the tip source: Odds API commence_time primary, ESPN cross-check only. This differs from the S0d
   work order text and is accepted because the live pilot reads Odds API events (CHECK 3 identity).
 - B29 adds a rule: report rows can belong to a different game_date than the file date (2026-04-11 lists 04/12 games).
   Consumers must filter rows by game_date + matchup.
 - B29 records: dates_2025.json contains the non-game date 2026-04-11 and omits 2026-03-28.

ITEM 4 - tests (extend nba/pipeline/tests/test_b24_asof_before_tip.py):
 (i)   every filename in roles and game_asof has a parquet in history_parsed and a manifest row with status ok.
       Show it FAILS at 9beb9125d.
 (ii)  for every game whose date's 5:30 report was published <= tip - 30 min, asof_role == freeze and the sha matches.
       Show it FAILS at 9beb9125d (7 games).
 Run the new tests as scripts if pytest is unavailable; report the output.

Commit each item separately on nba/s0d, append the session log, push, DO NOT MERGE.
Report every PRE-REGISTERED line as HELD / DID NOT HOLD with counts, the parse-status table for newly parsed files,
the fetch count, runtime, and commit SHAs.
```
