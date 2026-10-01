# NBA WO2 verification — Cowork (NBA chat), 2026-10-01 ~00:55Z

Read from origin/nba/wo2 (686ffb0ae, 770bdf5a0, cbeb7a0d4; 14 files, +1,052/-15). NOT merged.

## Holds (from the code and the decision doc)
- B8: `basketball_nba_preseason -> nba` + July season rule; 12 tests, existing capture tests unchanged. Tape dry-run:
  basketball_nba 44 events, 9 books, Pinnacle yes, Hard Rock no (both keys), 3 credits; preseason key 0 events, 0
  credits (pre-registration "preseason events exist" did not hold — not posted as of 09-30 20:26Z; stated honestly).
- B9: SPORTS["nba"] as specified; date_season with alias; espn_nba actuals with on-disk cache, finals only, OT in;
  preseason rows halt freeze without --pilot; 10 tests on real fixtures (ATL-ORL, DEN-POR OT 269); NFL/NCAAF/NHL tests
  56 pass, 1 known red (test_score_first_side_and_units — same at origin/main; football chat's).
- B10: packet builder on shared/layers/packet.py; L2 post-built_utc filter test fails with the filter removed;
  deterministic sha; RW@SH lists imported from run_nba.py (identity test).

## Defects (must fix before the pilot)
1. **No player props will be captured.** `pull_event_markets.py` pulls the union of markets offered by `hardrockbet_fl`
   and `pinnacle` only (`compute_market_set`, lines ~111-113). Hard Rock is not posting NBA yet and Pinnacle hangs no
   NBA props through the API, so B8's discovery found 3 markets (alternate_spreads, alternate_totals, team_totals) while
   it saw FanDuel offering "extensive player props". Jeff chose game lines + props; the sim and the minutes-on-news
   thesis need them.
2. **L3 history walks ESPN day by day, per game, uncached, and swallows failures.** `_history_layer` loops every date
   from Oct 15 to the slate date for EACH game (a 10-game March slate ~1,500 HTTP calls), and `except (Exception,
   SystemExit): continue` drops a failed date silently, so a record can be wrong with no trace (CHECK 1 provenance).
3. **Preseason games leak into L3.** The walk starts Oct 15 and `fetch_scoreboard` has no season-type filter; preseason
   games on Oct 15-16 count toward the regular-season record and rest days.
4. **Proposed cron is wrong.** Tape line `*/30 * * * *` (24 h, 48 calls) instead of the existing football cadence
   (`*/30 14-23,0-5`); and the comment calls 16:00Z "after the 5:30 pm ET report" — 16:00Z is noon ET; 21:40Z is the
   post-report slot.

## Not verified
L2 with real archive data (none for the test date); event-market summary in a real packet; a full freeze -> verify ->
score run on NBA (WO2-D pipe test).

Action: work order 2b (`research/nba_layers/workorder_2b_2026-10-01.md`) on the same branch; then merge; then WO2-D.
