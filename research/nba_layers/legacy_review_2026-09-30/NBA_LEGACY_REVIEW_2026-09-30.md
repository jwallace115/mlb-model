# NBA — what was built before the Layers/sim work, and what it means now (Cowork NBA chat, 2026-09-30)

Read from the repo (nba/, research/recovery/nba_*, research/nba_*, research/discovery/nba_autonomous_engine_v1,
nba/props, nba/model_b, nba/model_c), the project master doc v39 and memory. NBA work ran 2026-03-13 .. ~2026-07.

## Timeline of the old NBA program (March-July 2026)
- Mar 13-14: Phase 1 canonical game table 2022-23..2024-25 (3,690 games); Phase 2 rolling features (ORtg/DRtg/pace,
  rest); Phase 3 Ridge totals model (15 features); Phase 4 backtest; 4B 2025-26 OOS predictions (994 games).
- Phase 5 MC simulation layer (`nba/modules/simulate.py`) wrapping the Ridge mean; small-edge filter (|edge| <= 1)
  "+5.6% on 2024-25" -> postmortem: -9.9% / -17.2% in 2022-24, -3.8% on a 2025-26 point-in-time replay. Not validated.
- Phase 6 H1 (first-half) Ridge + shadow; Phase 7/7B tier audit (HIGH tier inverted) + 29 hypotheses — all failed.
- Phases 9-12: edge size, line movement, pace shock, variance regimes — ALL NULL. Conclusion then: "NBA pregame totals
  are efficient on mean AND distribution." Model B (player-level pace): null -> "close pregame totals research".
- Model C + props P2-P5: 155,909 player-prop lines (2023-26, 13 books, points/rebounds/assists/threes), a minutes sim
  (corr 0.58 with actual minutes). P3 badly over-confident; P4/P5 no prop type production-ready; threes UNDER a
  near-miss that failed OOS (-4.7%). Model C's own note: minutes allocation is the main edge vector for props.
- Signal boards (Mar 20-23): shot profile, OREB, pace, ELITE_DEF2 UNDER, venue ROAD_WARRIOR @ STRONG_HOME (Board 4),
  referee crew (Board 5), high-line UNDER shadow; playoff boards (P1/P2/P4; elimination OVER p 0.028, n 52).
- Apr 10-13 recovery: archetype team sets had discovery-validation leakage; keep/kill: ELITE_DEF2 COLLAPSES (killed),
  BALANCED_OFF and ELITE_OREB DIMINISHED, ROAD_WARRIOR "SURVIVES (226 OOS, 63.2%, +20.7%)". Parity audit: live Ridge
  fed overall (not home/away-split) features — fixed; injury adjustment applied live but never in training — open.
- Apr 24: autonomous engine V1 — "ROAD_WARRIOR confirmed, everything else quality proxies"; master doc: "public-data
  prediction edge is exhausted across MLB, NBA, NHL". Schedule-fatigue domain closed (0/7).
- Live 2026 (Mar 24 - May 30): signal log 92 rows; ROAD_WARRIOR 9 graded +2.32 u; REF_UNDER 23 graded +0.68 u.

## Audit of the one surviving signal (done today)
The April "SURVIVES" number is NOT clean: on 2026-03-22 the list was pruned (-BKN, -LAL, -NOP; 58704cd42) and
expanded (+ATL both, +BOS home; 7868c748e) using 2022-23..2024-25 results — the same seasons the April memo called
"true OOS". CHECK 2 fails; it was also priced at flat -110 (CHECK 4 triage). The 2025-26 regular season was used by
no selection step on disk, and NBA-D1 bought its closing prices. Pre-registered (`PREREG_rw_sh_2025_26.md`, sha256
90fc1d6e…) before computing; script `run_rw_sh_2025_26.py`; output `rw_sh_2025_26_results.txt`.
- **Result (OVER at the last pre-tip price):** Pinnacle n 101, 60.4%, ROI +16.3% (SE 9.4, one-sided 90% lower bound
  +4.3%); Hard Rock n 99, 61.6%, +16.4%; DraftKings n 101, 59.4%, +14.0%.
- **Prediction (50-57%, ROI -6..+8%) DID NOT HOLD** — the signal did better than predicted. By the pre-registered rule
  (ROI > 0 and 90% lower bound > 0) it is ALIVE on 2025-26.
- Null control: non-signal games over 48.3% (in range), ROI -6.4% at Pinnacle (outside the stated -1..-4% band: overs
  lost more than the vig league-wide in 2025-26). So the signal's gap vs its own base rate is ~+22 points.
- CHECK 5: uneven by month (Oct-Dec 50 games +34%, Jan -36.5%, Feb +52%, Mar -16%); by team (CHI, UTA away and BOS,
  ATL home negative; OKC home 10/11). Line band: <225 +34%, 225-235 +15%, >235 +3%.
- Caveats: one season, n ~100; 16 signal games lack an outcome in the stored files (fill with the ESPN loader);
  the Board 4 idea was conceived mid-2025-26 (files show only 2022-25 used, but informal influence cannot be ruled
  out); the lists are now two seasons old for 2026-27. Do NOT re-tune the lists on this result.
- Meaning for the Layers System: this is the only NBA model output with clean forward evidence at real prices. It
  becomes an L4 vote with its n and SE stated; 2026-27 is the next out-of-sample test, logged like every other layer.

## What carries into the sim
- Evidence says full-game pregame totals are hard (five null phases + D1-era sharp closes). The sim should not be
  judged mainly on beating Pinnacle's full-game total; target props (minutes on late news), H1/Q1/team totals, SGP
  correlation, price vs Pinnacle fair.
- Reusable data: player game logs 2022-10-18..2026-03-18 (101,083 rows, `nba/model_c/player_game_logs.parquet`);
  prop features (100,713); props market view 2023-26 (`nba/props/processed/`); minutes-sim baseline corr 0.58 to beat;
  2023-24 official injury reports at 5 pm; referee scraper (`nba/ref_scrape.py`); outcomes loader (nba/wo1).
- Known traps: team-set/list selection on the test window (happened twice); train/live identity (location splits,
  injury adjustment); flat -110 pricing; `predictions_4b` point-in-time unverified.
