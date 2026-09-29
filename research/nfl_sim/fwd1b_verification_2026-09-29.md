# FWD1b verification — Cowork, 2026-09-29 (21:30Z)

Branch `eng/fwd1` @ `54efc5878` (D213 append; D214–D217 one commit each; log). Read from the committed files. Cowork
rescored the pilot from the committed frozen file (`week=2026_03/ai_opinions/ai_opinions_20260927T163000Z.parquet`)
and from the score output (`research/nfl_sim/fwd1_pilot_w3.parquet`).
**Verdict: items 0-3 are accepted and the harness now works, but it is not merged yet.** Two defects in how the
logger scores lines would throw away most of the sim's opinions and put the sim's label on a line it never priced.
FWD1c fixes both and adds a week-4 dry run. The merge follows Cowork's check, before the TNF run at 23:30Z Thursday.

## What stands
- **D214 (week labels).** The files moved with `git mv`. The manifest entry moved with its sha256 unchanged, and
  `verify` passes for week 3 (now 3 files) and week 4 (0 files).
- **D215 (harness).**
  - `fill_sheet` matches on player, market and line and honours `side`.
  - `anchor_sidecar` reads the real anchoring-log columns.
  - The `--pilot`, `--as-of`, `--window-hours` and `--events` flags reach both the sheet and the freeze.
  - Props are capped at `now`.
  - The 8 tests import the real functions.
- **D216 (pilot).** It ran end to end on week 3:
  - 15 games simulated, all anchored (maximum miss 0.34);
  - PBP refreshed to weeks 1-3;
  - `verify` clean.
- **D217 (runbook).** The windows are right:

  | Window | Run at (UTC) | Window length | Covers |
  |---|---|---|---|
  | TNF | 23:30 Thu | 2 h | kickoff 00:15 |
  | London game | 12:45 Sun | 1.5 h | kickoff 13:30 |
  | Sunday | 16:15 Sun | 9 h | through SNF 00:20; excludes MNF |
  | MNF | 23:30 Mon | 2 h | MNF only |

  The MNF props pull is flagged as 4 h stale.

## What does not
1. **Revision 0 is shared across readers, so 158 of the sim's 178 opinions were never scored.**
   - `prior_revisions` (log_ai_opinions.py) counts every earlier file in the week, whichever reader wrote it. The AI
     blind log froze the same lines at 15:58Z, so the sim's 16:30Z rows became revision 1, and revision 1 is never
     scored. The breakdown by tag:

     | Tag | revision 0 | revision 1 |
     |---|---|---|
     | sim_v1 | 20 | 158 |
     | no_view | 171 | 700 |

   - Live, whichever reader freezes second loses its lines, and the sim runs at 16:15Z on Sunday.
   - D216's "20 scored, +2.68 units" is therefore the 11% of lines the AI log happened not to hold.
2. **One of those 20 rows is not a sim opinion at all.**
   - `fill_sheet` tags one-way lines whose book price is outside [0.02, 0.98] as `sim_v1` ("sim v1 no signal
     book_p"). It does this because the validator will not accept `no_view` at a clipped probability.
   - The example is Zavion Thomas anytime TD at +7500, scored as a sim side.
   - This is the same floor problem noted in the handoff (Nick Muse, 09-24).
3. **D216's counts are wrong.**
   - The frozen file holds 139 receptions and 35 rush-attempts sim opinions, not 112 and 62.
   - The "662 two-way prop rows" includes 48 game-line rows; there are 614 two-way prop rows.
   - The Brier and units it reports are pooled over all readers; the order asked for the sim alone.
4. **Cowork's sim-only pilot numbers.** All 174 two-way sim opinions were matched to outcomes through the graded AI
   rows on the same (event, market, player, line). Every opinion comes from the sim at 16:30Z and uses the sim file's
   own prices:

   | Measure | Value |
   |---|---|
   | Brier, sim vs book | 0.2673 vs 0.2517 (sim worse by 0.0157) |
   | 95% interval on that gap (game-cluster bootstrap) | −0.0021 to +0.0339 |
   | Receptions (139) | sim 0.2597, book 0.2530 |
   | Rush attempts (35) | sim 0.2977, book 0.2463 |
   | All sides at real Hard Rock prices | 86 of 174 won, −10.78 units |
   | Sides with a gap over 0.08 (P2 subset) | 60 of 110 won, +3.73 units |

   This is a PILOT, never pooled, and it is evidence for nothing. Its direction matches K4: the book is better, and
   the gap is widest in rush attempts.

### D218 — Cowork verification of FWD1b: harness works end to end; revision sharing and one-way tagging must be fixed before week 4 (2026-09-29)

FWD1b (eng/fwd1 @ 54efc5878) is accepted for items 0-3. It is not merged until FWD1c is verified.

What was verified:
- The week-3 files moved to week=2026_03 with their hashes unchanged.
- The harness matches on player, market and line, and honours side.
- The anchor sidecar reads the real columns.
- Flags pass through to both the sheet and the freeze.
- Props are capped at now.
- The tests call the real functions.
- The pilot ran end to end with 15 of 15 games anchored.

Defects:
- log_ai_opinions.prior_revisions counts revisions across readers. The AI log frozen at 15:58Z pushed 158 of the
  sim's 178 opinions to revision 1, so they went unscored.
- fill_sheet tags one-way lines priced outside [0.02, 0.98] as sim_v1. In the pilot that meant a +7500 anytime TD was
  scored as a sim side.
- D216's market counts (112/62) and its 662 are wrong (139/35; 614 two-way prop rows).

Cowork's sim-only pilot scoring, all 174 two-way opinions, is a pilot and never pooled:
- Brier: sim 0.2673 vs book 0.2517, gap +0.0157 (95% interval −0.0021 to +0.0339).
- Rush attempts: sim 0.2977 vs book 0.2463.
- All sides: −10.78 units. P2 subset: +3.73 units on 110.

Next: FWD1c (revisions per reader and pilot flag; no_view at the clipped book price; a week-4 dry run), then the
merge before the TNF run (23:30Z, 10-01).
