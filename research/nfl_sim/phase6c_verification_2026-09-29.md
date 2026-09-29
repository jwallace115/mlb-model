# Phase 6C verification — Cowork, 2026-09-29 (08:00Z)

Branch `eng/6c` @ `db2de2582` (D194 append, D195-D198, fit_6c artefacts, log). K1 recomputed from
`phase6c_k1_after_rows.parquet`; engine diff read line by line. **Verdict: keep item 0, reverse item 1, item 2 not
done; not merged. 6D is order 2 of the 3-order time box.**

## Item 0 (D195) — accepted, one fallback bug
- The punt landing table replaces "LOS minus net, clipped at the 1" (engine.py:1806). Own-1/2 drive starts 0.83 ->
  0.199 (real 0.255) and safeties 0.069 -> 0.030 (K1 0.031; real 0.041 on all pass/run plays, 0.032 zone-only):
  both pre-registrations HELD. The punt clip found in D194 is fixed.
- Half-distance penalty rule is now the real rule (penalty > half the distance -> half the distance).
- Bug: the fallback for LOS buckets missing from the table sets any landing deeper than the receiving team's 20 to
  the 20 (`if recv_yl > 80: yl = 80`) — a punt downed at the 8 is not a touchback. Only reached for buckets absent
  from the table; fix, and report how often it fires.

## Item 1 (D196) — reverse it
The order said: rebuild `timeout_policy.parquet` from PBP so it covers every quarter and seconds bucket, and deliver
the sim-vs-real timeout table. Instead the engine now calls timeouts at every snap using the Q2/Q4 table, with Q1
mapped to Q2, Q3 to Q4, and every snap with more than 2:00 left mapped to the 2:00-3:00 bucket — i.e. rates measured
in the last three minutes of a half are applied to the whole game. No sim-vs-real timeout table was delivered and
timeouts per game were not reported. The suite went from 8 to 13 reds, most of them late-game (tie rate, OT
structure, late-half snaps, timeout policy live, tied offence kicks, kneels and late snaps) — consistent with teams
spending timeouts early and having none left late.

## Item 2 (D197) — not done
The finding (the sim starts kneeling too late: final kneel with 6.7 s left vs 22.1 s) is the one D190 already made.
The order asked for the first-kneel clock sim vs real, the keys of `kneel_decision.parquet` and a fix. "Fix deferred"
is not one of the allowed outcomes.

## Item 3 (D198) — numbers reproduce; the headline is not what it looks like
- K1 rows: plays **125.88** (gap +0.1), drives **22.825**, pts/team **20.834**, punts 8.76, FG att 3.80. Clean header.
- Plays are on target, but with a timeout rule that is not measured, so the +0.1 cannot be credited to the engine.
- **Points per team fell again: 21.55 (5Y) -> 21.28 (6B) -> 20.83 (6C) vs 22.39 real (gap -1.56).** Fewer own-1
  starts should have RAISED points. Not reported as a problem in D198; the points split the order asked for was not
  delivered.
- 13 reds (listed in D198): fd_pen and tied expiry known; dead_punt_net and dead_clock_runoff are test-selection
  issues after table changes; the rest are late-game and follow from D196 and the kneel timing.

### D199 — Cowork verification of 6C: punt fix kept, whole-game timeout proxy reversed, kneel fix still owed (2026-09-29)

6C (eng/6c @ db2de2582) not merged. D195 stands: punt landing table, own-1/2 starts 0.199, safeties 0.031, real
half-distance rule; its fallback wrongly converts any landing inside the receiving 20 to a touchback. D196 is
reversed: it applies last-3-minutes timeout rates (Q1->Q2, Q3->Q4, >2:00 -> the 2:00-3:00 bucket) to every snap of
the game instead of measuring a whole-game table; reds went 8 -> 13, mostly late-game. D197 repeats D190's finding
without the ordered fix. K1 on fit_6c: plays 125.88, drives 22.825, pts/team 20.83 (gap -1.56, the third fall in a
row, unexplained). Next: 6D (order 2 of the 3-order time box): measured whole-game timeout table, kneel decision fix,
punt fallback fix, one re-fit with the points split.
