# FWD1 verification — Cowork, 2026-09-29 (19:10Z)

Branch `eng/fwd1` @ `4c9802c93` (D210 pre-registration; D211 harness and tests; D212 pilot "blocked"; log). Read from
the committed files. The tape checks were run on the Mac, read-only.
**Verdict: not merged. The harness would crash on its first live run, and it would freeze wrong opinions for about 3%
of the lines it matches. The pilot "blocker" is a wrong week number, not a pipeline defect. FWD1b fixes these before
the week-4 TNF kick (Fri 2026-10-02 00:15Z).**

## What stands
- **D210, the pre-registration.** It was written before any sim opinion existed and is correct as text.
- **D211's reading of run_week.py:997.** The printed margin is the anchored one. Anchoring works on the current
  engine: the committed `nfl/data/sim/outputs/week=2026_02/anchoring_log.parquet` has 15 of 15 games converged, with
  a best |err_m| of at most 0.31 and |err_t| of at most 0.34. My worry about the week-2 run log ("16 of 17 NOT
  CONVERGED") was misplaced. That log came from an older run and is not the committed anchoring log.
- **The additions to log_ai_opinions.py.** The `sim_v1` tag is added, and `--as-of` is refused unless `--pilot` is
  also set.

## What does not
1. **The pilot used the wrong week.**
   - The nflverse weeks are: week 1 = 09-09 to 09-14 and week 2 = 09-17 to 09-21 (`pbp_2026` game dates). So week 3 =
     09-24 to 09-28, which is the TNF ATL@GB, the Sunday slate and the MNF PHI@CHI. Week 4 = 10-01 to 10-05.
   - `--week 4 --as-of 2026-09-27T16:30Z` asked for next week's games at a time when Hard Rock had not quoted them.
     `get_lines_from_history(as_of=2026-09-27T16:30Z)`, run on the Mac, returns the 15 Sep 27–28 games normally.
     There is nothing wrong in run_week.py.
   - A second reason the pilot cannot work: the harness never passes `--pilot` or `--as-of` to the `sheet` step. The
     sheet is therefore built at the real "now", and holds only future games.
2. **The project's own week label is off by one** (Cowork's error, carried from 09-27). The Sep 27 blind log and the
   MNF SGP files sit in `nfl/data/board/week=2026_04/`, but that slate is nflverse week 3. The real week 4 (Oct 1–5)
   would land in the same folder. From now on nflverse week numbers are the only ones used, and FWD1b moves the files.
3. **The anchor sidecar would crash on the first live run.**
   - It reads `anch_log["game_id"]`, `iteration`, `spread` and `total_line`. The real `anchoring_log.parquet` has
     `game`, `iter`, `margin`, `total`, `err_m`, `err_t` and `converged`.
   - The first access raises a KeyError, after run_week has finished and before the fill.
   - The other fields fall back silently (`spread` defaults to 0), so even with the key fixed the sidecar would label
     games wrongly.
4. **The fill matches on player and line only.** It ignores the market (the "also match on family" comment has no
   code), takes the first row if more than one matches, and never reads `picks_log.side`.
   - I replayed the rule on week 2: the newest pre-kick Hard Rock pull against the committed picks_log. **5 of 160
     matched rows got another market's probability.** Four were `player_reception_yds` rows priced by a rush-attempts
     or receptions rung.
   - The picks_log prices rush attempts at fixed rungs, so a QB's pass_tds 1.5 or interceptions 0.5 can collide with
     his rush-attempts rung. Those opinions would be frozen for good.
5. **The tests do not test the harness.** `test_forward_v1.py` copies the fill logic into `_fill()` instead of calling
   run_forward_v1. The under-side test exercises a `_under` market_key that the sheet never produces, because the
   first side of a prop is always Over. The "halts" test calls test_freeze_v1's function, not the harness. The order's
   rule was: call the real function, and show it fails first.
6. **There is no kick window.**
   - The harness builds the sheet from every pre-kick line on the tape. A Thursday run therefore freezes Sunday's and
     Monday's lines too, at Thursday prices and with Thursday's news. The Sunday run's rows for those lines become
     revision 1, and revision 1 is never scored.
   - The runbook's "if only TNF is pre-kick, it covers that one game" is false. `--window-hours` and `--events`
     exist in the logger but are not passed through.
7. **In a pilot, props are not capped at `--as-of`.** `newest_inputs` keeps pulls before each game's kick, not before
   `now`, so a pilot can read props pulled after its as-of. This affects pilots only.
8. **Expected coverage (week 2 replay).** Correct matches are 143 receptions and 12 rush attempts out of about 674
   two-way Hard Rock prop rows. Anytime TD is one-way, so it is outside the D210 scope. The pass, rush-yards and
   receiving-yards markets have no sim number. That is about 150 scored legs a week, which puts the 500-leg checkpoint
   about 3–4 weeks out.

### D213 — Cowork verification of FWD1: pre-registration stands; harness not merged (crash, market collisions, no window); pilot blocker was the week number (2026-09-29)

FWD1 (eng/fwd1 @ 4c9802c93) is not merged.

What stands:
- D210 stands as written.
- D211 is right that run_week prints the anchored margin. The committed week-2 anchoring log converges on 15 of 15
  games.

Defects, measured:
- The anchor sidecar reads columns that do not exist (game_id, iteration, spread, total_line), so it raises a KeyError
  on the first live run. Its other fields default silently.
- The fill ignores the market and picks_log.side. On the week-2 replay, 5 of 160 matches take another market's
  probability.
- The tests copy the fill logic instead of calling the harness.
- The sheet has no kick window, so a Thursday run freezes the whole week at Thursday prices as revision 0.
- In a pilot, props are not capped at as-of.

D212's blocker is wrong. The Sep 27–28 slate is nflverse week 3, not week 4, and the harness also never passed
--pilot/--as-of to the sheet. get_lines_from_history returns all 15 games at 2026-09-27T16:30Z.

The project's week label was off by one from 09-27 on. nflverse weeks are canonical from now on, and the week-3 files
in week=2026_04 are moved by FWD1b. FWD1b must be verified before the week-4 TNF kick (2026-10-02 00:15Z).
