# Phase 6D verification — Cowork, 2026-09-29 (14:00Z)

Branch `eng/6d` @ `b480e0c25` (D199 append; items 0-2 in one commit a0895aec4; cal maps; D203; log). Read from the
committed files. The K1 rows file was not produced, so K1 is read from `phase6d_k1_after.txt`, not recomputed.
**Verdict: accepted as the base for the last time-boxed order (6E); not merged.**

## What stands
- **D200 — measured whole-game timeout table** (532 rows, every quarter and seconds bucket, real quarter looked up).
  The D196 proxy is gone. Sim timeouts 5.24 a game vs 7.70 real (pre-reg 6.5-8.5 FAILED); the explanation offered —
  the engine only calls timeouts after scrimmage snaps, and ~16% of real team timeouts follow punts, field goals,
  kickoffs or no-play penalties — is consistent with Cowork's 5.54 real timeouts a game after scrimmage plays.
- **D201 — kneels.** With the proxy gone, Q4 first kneel 56.5 s (real 55.5) and final kneel 27.3 s (real 29.0); Q2
  over-kneeling fixed by splitting the 0-40 s bucket at 15 s (real: 89% of Q2 kneels come inside 15 s). Good work:
  the root cause (6C's proxy) was found rather than papered over. test_engine_6a kneel still fails (19.7 vs 25.9 s).
- **D202 — punt fallback** uses the nearest landing bucket; the two dead-table tests now perturb the live tables.
- **K1 (text file):** plays 126.6 (gap +0.8, HELD), drives 22.9 (+1.2), **pts/team 21.04 (gap -1.35)** — first rise in
  four orders — safeties 0.031, go_rate / penalties / FG attempts PASS. Suite 8 red (from 13).

## What does not
- The K1 header reads `6da3aa90e-dirty`; D203 calls it clean. The rows parquet is missing ("OOM crash"; the same
  script wrote rows on 6A-6C). Both are owed.
- Items 0-2 were committed together; the W2/W3 boards were skipped ("needs live-week data" — they were produced on
  every earlier fit from archived data).
- D203's attribution is off: the own-1 pile-up was removed by D195 (6C), not D202; the points split was compared
  with fit_6a instead of fit_6c (eng/6c is fetchable).
- Points split (6D sample): gap -1.81 = START MIX +2.09 + EFFICIENCY -3.48 + interaction -0.42. The deficit is still
  efficiency on long fields (own 21-40 points/drive 1.67 vs 1.90). The largest known contributor not yet addressed is
  first downs by penalty: 1.27 vs 1.73 per team (-0.46), which removes ~0.9 drive-extending first downs a game.
- Six late-game reds remain: OT structure, late-half snaps, timeouts/kneels, tied-offence kicks, kneels & late snaps,
  kneel measured table.

### D204 — Cowork verification of 6D: measured timeouts and kneel timing accepted; points still short (2026-09-29)

6D (eng/6d @ b480e0c25) accepted as the base of the final time-boxed order; not merged. D200's whole-game timeout
table replaces the D196 proxy (5.24 timeouts a game vs 7.70 real; the remainder follows non-scrimmage events). D201
found that 6C's proxy caused the late kneels; Q4 first kneel 56.5 s vs 55.5 real. K1 (text only; rows file missing;
header `-dirty` despite D203): plays 126.6, drives 22.9, pts/team 21.04 (gap -1.35, first rise in four orders),
safeties 0.031, 8 reds (6 late-game). Points gap on the sample -1.81 = START MIX +2.09 + EFFICIENCY -3.48 +
interaction -0.42; first downs by penalty 1.27 vs 1.73 a team is the largest unaddressed efficiency input. Next: 6E,
the last order before the freeze.
