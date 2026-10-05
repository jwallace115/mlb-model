# NBA Layers — work order 1b: fix the injury-report URL bug, re-measure cadence, live Hard Rock key (2026-09-30)

Written by Cowork after verifying WO1 (`research/nba_layers/wo1_verification_2026-09-30.md`). Same branch nba/wo1.

Pre-check (Cowork): runtime — re-probe 4 dates x 56 quarter-hours x 1 format (new, 12-hour) = 224 HEADs x ~0.8 s
~= 3 min per host, 2 hosts ~= 6 min; tests seconds. Credits: live Hard Rock key probe = sport-level live odds,
h2h/spreads/totals, 1 book = 3 credits per call; at most 4 calls (basketball_nba x {hardrockbet, hardrockbet_fl},
americanfootball_nfl x {hardrockbet, hardrockbet_fl}) = 12 credits. Paths: all exist on nba/wo1. Parameter from Jeff:
freeze after the 5:30 pm ET injury report (B1) — this order measures whether that report exists; it does not change
the rule.

```
NBA WO1b. Read ~/mlb-model/research/nba_layers/wo1_verification_2026-09-30.md and this file (both UNTRACKED in the main
checkout — copy both into the worktree's research/nba_layers/ in your first commit). Use the EXISTING worktree/branch
nba/wo1 (git worktree list; if the worktree is gone, create ~/mlb-model-nba1 from origin/nba/wo1). Never switch the main
checkout's branch. Commit AND push each item before the next (`git pull --rebase --autostash && git push`). Decisions
B6, B7 APPENDED at the END of research/nba_layers/NBA_LAYERS_DECISION_v1.md in the same commit. Never edit B2/B3 text —
corrections are new entries. Tests import production code; each new test must FAIL on the current code (run it
against c715f643a and paste the failure). Install no cron. Do not merge.

Item 1 (B6) — Fix the report URL and re-measure the cadence.
  a) One function, `official_report_url(date, hour24, minute)` in nba/pipeline/capture_nba_availability.py, building
     `Injury-Report_{YYYY-MM-DD}_{hh:02d}_{mm:02d}{AM|PM}.pdf` with a 12-HOUR hour (1 pm -> 01, 12 pm -> 12,
     5:30 pm -> 05_30PM). probe_nba_sources.py imports it (no second copy). If nbainjuries is importable on the Mac,
     assert its gen_url agrees for 10:00, 12:45, 13:00, 17:30, 19:15 on 2026-03-16 and print both.
  b) TEST test_report_url_b6.py: 13:00 -> "_01_00PM", 17:30 -> "_05_30PM", 12:45 -> "_12_45PM", 10:15 -> "_10_15AM".
     Must FAIL on c715f643a's builder.
  c) Re-run ONLY the official-report part of the probe for 2025-10-10, 2025-12-25, 2026-01-14, 2026-03-16, every
     quarter-hour 10:00-23:45 ET, new format, on the Mac AND the VM. Report every timestamp that exists per date, the
     cadence, whether a 5:30 pm ET report exists, and the latest report before each date's first tip.
  PRE-REGISTER: reports exist after 12:45 pm on all three regular-season dates, including one at or near 5:00-5:30
  pm; 2025-12-25 has reports before its noon tip; the preseason date has none. VM: report exactly what it returns
  (200 vs 404 vs 403) — do not call it "blocked" unless a URL that returns 200 on the Mac fails on the VM.
  NULL CONTROL: the 10:00-12:45 timestamps found by WO1 are found again, unchanged.
  B6 records the corrected cadence and host, and states that B2's "no 5:30 pm report" was a URL bug.

Item 2 (B7) — Capture cadence and the live Hard Rock key.
  a) `_report_urls_for_now` covers every quarter-hour from 10:00 ET through the day's last tip (from the ESPN
     scoreboard / schedule), using official_report_url. TEST: on a fixture day with a 22:00 ET tip the list includes
     17:30 and 21:45 slots — must FAIL on c715f643a. Proposed cron lines in B7 from item 1's measured cadence (not
     installed).
  b) Live Odds API, one call each (3 credits): /v4/sports/basketball_nba/odds bookmakers=hardrockbet; bookmakers=
     hardrockbet_fl; same two for americanfootball_nfl. Print books returned, events with Hard Rock, x-requests-last,
     remaining. PRE-REGISTER: NFL returns hardrockbet_fl (the tape does); NBA returns Hard Rock under at least one key
     once regular-season lines are posted. If neither key returns NBA Hard Rock today, say so and name what would
     change it (posting time) — do not conclude "unavailable".
  c) Settle the PHX-HOU 2026-04-07 4-point gap with nba_api on the Mac (final score from stats.nba.com) and state
     which source is right.
  B7 records the capture cadence, the live Hard Rock key per sport, and the PHX-HOU answer.

Closing: session log to logs/agent_sessions.md (git add -f) — RETURNED vs MEANS, NOT DONE, UNVERIFIED. Push. Stop.
```
