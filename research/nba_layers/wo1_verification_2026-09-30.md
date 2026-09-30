# NBA WO1 verification — Cowork (NBA chat), 2026-09-30 ~20:10Z

Read from origin/nba/wo1 (4 commits 3823ebc90..c715f643a, 14 files) and the Mac's files. The branch is NOT merged.

## The headline finding of B2 is a URL bug, not a fact about the NBA
B2 says official injury reports are published 10:00-12:45 ET only and "no 5:30 PM report exists", and calls B1's
freeze rule wrong. The probe built the new-format URL with the 24-hour hour and an AM/PM suffix:
`probe_nba_sources.py` line ~154: `new_tag = f"{hour:02d}_{minute:02d}{ampm}"` -> 1:00 pm becomes `13_00PM`, 5:30 pm
becomes `17_30PM`. The real format is 12-hour (`01_00PM`, `05_30PM`; the committed fixture
`Injury-Report_2026-03-16_12_45PM.pdf` shows it). 10:00-12:45 is exactly the window where 24-hour and 12-hour
agree, so every afternoon and evening report was requested at a URL that cannot exist.
Independent evidence: `nba/data/injury_reports/2026-03-16_1700.parquet` (119 rows, pulled earlier with the
nbainjuries library) is a 5:00 pm ET report for the same date B2 says had nothing after 12:45 pm.
Consequences:
- B2 "no 5:30 PM report" and "freeze assumption in B1 is wrong" — WITHDRAWN. B1's freeze rule stands.
- B2 "CDN blocks the VM (404)" — UNPROVEN: 404 is also what a nonexistent URL returns; the VM result must be
  re-measured with correct URLs before calling it a block.
- B3's capture script (`_report_urls_for_now`) polls 10:00-12:45 ET only and would miss every afternoon/evening
  report — the ones that matter for a 5:30 pm freeze. Its tests never exercise URL generation, so they pass.
- B3's proposed cron (10:00-13:00 ET) — WITHDRAWN.

## Hard Rock live key never tried
B2 reports `hardrockbet_fl` absent for basketball_nba and concludes Hard Rock is unavailable on the live tape. The
probe only requested `hardrockbet_fl`. D1 found the historical NBA key is `hardrockbet`. Nobody has requested
`hardrockbet` on the LIVE endpoint. Open, cheap to settle (3 credits per call).

## Holds (from the files)
- Pinnacle returned live; `basketball_nba_preseason` is a separate key (inactive today); dry-run 3 credits.
- ESPN injuries carry a per-item `date` (pre-registration "no timestamp" did not hold — stated honestly).
- Outcomes loader: ESPN scoreboard, 30-name map test, OT-total test with a real game (269 vs 250). 191/194 vs the
  results log; the 3 misses are attributed to the log — plausible for the two OT flags; the PHX-HOU 4-point gap
  is unexplained and should be settled with the nba_api cross-check on the Mac, not asserted.
- B5 audit tables are reasonable; the claim that `predictions_4b` (994 rows, 2025-26) may not be point-in-time is
  correctly left UNVERIFIED — treat those rows as not evidence.
- Settlement rules NOT VERIFIED (404/403) — Jeff can read Hard Rock's house rules in the app.

## Action
Work order 1b (`research/nba_layers/workorder_1b_2026-09-30.md`): fix the URL builder with a test that fails on
the current code, re-probe the report cadence on both hosts, fix the capture cadence, probe the live Hard Rock key.
Do not merge nba/wo1 until 1b lands on the same branch.
