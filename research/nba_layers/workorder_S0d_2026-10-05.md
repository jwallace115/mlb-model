# NBA-S0d work order — report as-of must be before tip (2026-10-05, NBA chat)

Status: APPROVED by Jeff 2026-10-05: per-game cap with the 5:30 report. NOT RUN yet.
It changes roles.parquet, a reported B21 result; Jeff approved that change.
Source: claude/nba_s0c_verification_2026-10-05.md, findings F1–F4.

## Pre-checks
- **Runtime.**
  - ESPN scoreboard: 328 dates × (1 call + 0.5 s sleep) ≈ 5.5 min.
  - Legacy hourly re-fetch: ≤300 files × ~1 s ≈ 5 min.
  - Re-parse of new files with both parsers: ≤300 × ~2 s ≈ 10 min.
  - Total ≈ 20 min on the Mac, well under 2 h.
- **Credits.** 0. Odds API tip times come from the local `data/odds_archive/nba/history/events/events_{2024,2025}.parquet`.
- **Paths.** All in the lane.
  - Updated: `data/injury_archive/nba/history_parsed/roles.parquet`.
  - New: `data/injury_archive/nba/history_parsed/game_asof.parquet`.
  - Raw PDFs: same git-excluded `data/injury_archive/nba/history/season=<yr>/` in the main checkout (as in B21).
- **Branch.** `nba/s0d` from origin/main AFTER nba/s0 merges. Worktree `~/mlb-model-nbaS0d`. ~/mlb-model stays on main.
- **Prefix.** `GIT_OPTIONAL_LOCKS=0` on every git command. No package installs.

## Prompt for Claude Code (Mac)
```
NBA lane, work order NBA-S0d. Read claude/SESSIONS_RULES.md, research/nba_sim/NBA_SIM_DECISION_v1.md (NS1),
research/nba_layers/NBA_LAYERS_DECISION_v1.md (B21-B23), and research/nba_layers/nbaS0c_verification_2026-10-05.md.

Setup: GIT_OPTIONAL_LOCKS=0 on every git command. git -C ~/mlb-model fetch origin; create worktree
~/mlb-model-nbaS0d on new branch nba/s0d from origin/main (nba/s0 must already be merged). Never switch
~/mlb-model off main. No package installs. No Odds API calls (tip times come from the local events parquets).
Expected runtime ~20 min. If any step will exceed 1 hour, stop and report.

ITEM 1 (B24) - pre_tip chosen on PUBLISHED time, tip stored, no silent default.
 - For each game date in roles.parquet:
   - first_tip_utc = ESPN scoreboard min(event date).
   - If ESPN fails, use min(commence_time) from data/odds_archive/nba/history/events/events_{2024,2025}.parquet.
   - If both fail, set status no_tip. NEVER default to 19:00 ET.
   - Store first_tip_utc, tip_source in {espn, odds_events}, published_utc (from the manifest) on every roles row.
 - pre_tip = latest report whose published_utc <= first_tip_utc - 30 min.
   - Legacy: published_utc is the PDF header time, not the slot.
   - Fetch an earlier legacy hourly file if needed; zero-padded URLs (B21).
   - Parse new files with both parsers. Status must be ok.
 - Report the number of dates where |ESPN first tip - Odds API first tip| > 15 min, and list them.
 - PRE-REGISTERED:
   - roles pre_tip rows with published_utc > first_tip - 30 min: 0 after the fix.
     Against Odds API tips, c19ce5371 has 42 legacy rows and 1 new-format row.
   - Legacy dates whose pre_tip file changes: between 30 and 50.
   - NULL: every date whose c19ce5371 pre_tip already had published_utc <= first_tip - 30 min keeps the same filename
     and sha256. State the count.

ITEM 2 (B25) - per-game as-of: data/injury_archive/nba/history_parsed/game_asof.parquet.
 - One row per game. Columns:
   - event_id (Odds API events), game_date, home_team, away_team, tip_utc, tip_source;
   - asof_role in {freeze, pre_game};
   - asof_filename, asof_sha256, asof_published_utc.
 - RULE (Jeff's decision, 2026-10-05: "per game cap with the 530 report"):
   - The freeze report is the date's 5:30pm ET report: the _05_30PM file in the new format, the _05PM file in the
     legacy format. This is the same file as roles.parquet freeze (224/224 legacy dates were 05PM).
   - asof = the freeze report if its published_utc <= tip_utc - 30 min (asof_role = freeze).
   - Otherwise asof = the latest report with published_utc <= tip_utc - 30 min (asof_role = pre_game).
   - Use published_utc (PDF header time), never the slot. Legacy headers run 30-45 min after the slot.
   - Fetch missing legacy hourly files as needed. Cap: 300 fetches. Stop and report if the cap is hit.
 - PRE-REGISTERED:
   - rows with asof_published_utc > tip_utc - 30 min: 0;
   - share of games with asof_role = pre_game: 4%-15%. Odds API events show 194/2,467 = 7.9% tipping before 18:00 ET.
   - NULL: every game with tip_utc >= 18:30 ET has asof_role = freeze and the same sha256 as that date's roles freeze row.
     (The latest freeze header is 17:45 ET, so 18:15 + margin.)
   - Append B25 to NBA_LAYERS_DECISION_v1.md with the rule, quoting "Jeff decision 2026-10-05: per-game cap with the
     5:30 report". Add: "the live pilot packet uses the identical rule (CHECK 3); WO2-D must implement it, not a
     date-level freeze." 

ITEM 3 (B26) - hygiene and doc corrections.
 - roles.status is filled from the manifest for every row. No blank status. Test asserts it.
 - Append B26 to NBA_LAYERS_DECISION_v1.md. It corrects B23 to 213 removed / 222 unchanged / 420 added = 642.
   It also corrects B21/B22 to 206 new-format manifest files (208 role rows) and B22 to 2 legacy context_mismatch.
 - State: "roles.parquet is a per-date index; per-game as-of MUST come from game_asof.parquet."

ITEM 4 - tests: nba/pipeline/tests/test_b24_asof_before_tip.py
 (i)   every roles pre_tip row and every game_asof row has published_utc <= tip - 30 min.
       Show that it FAILS against c19ce5371's roles.parquet.
 (ii)  mutation: move one game's tip 2 hours earlier in a copy; its asof changes to an earlier report.
 (iii) a date with ESPN unavailable takes tip_source = odds_events, never 19:00 ET.

Commit each item separately on nba/s0d, append the session log, push nba/s0d, DO NOT MERGE.
Report: counts for every PRE-REGISTERED line (HELD / DID NOT HOLD), the ESPN-vs-Odds tip mismatch list,
the fetch count, runtime, and the commit SHAs.
```
