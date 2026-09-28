# Phase 6A verification — Cowork, 2026-09-28 (18:15Z)

Branch `eng/6a` @ `fc3724115` (D181-D184 + session log; base = main with D180). Verified in Linux worktrees at 6A
and at main (5Z engine): diff read line by line, K1 recomputed from the rows file, full suite run on BOTH engines,
the 200-game phase5z sample re-simulated on both engines (N=100, drive + play logs), PBP 2021-24 REG for the real
side. Scripts and outputs: `research/nfl_sim/phase6a_cowork/`. Verdict at the end: **do not merge eng/6a; 6B
continues on it.**

## First, a correction to my own 5Z verification
The 5Z class table's "timeout_followed: sim 2.2 snaps a game at 8.9 s" was not the timeout path. The engine logs its
end-of-half / FG-setup runoff (`_eoh_runoff`, last 40 s inside the 50) under the label **`timeout_stopped`** — that
is the 2.2 / 8.9 s row. The plays a timeout actually stopped were logged as `incomplete` (their class became the stop
code). I carried the mislabel into the 6A order's pre-registration ("2.2 snaps x +9 s ~ 0.7 plays"). The miss is mine.
Measured now on the sample: the 5Z engine stops **2.8 plays a game** with a timeout (they are now visible as
`timeout_followed` on 6A); real games stop **4.0 running-clock plays a game** with a timeout (5.5 counting plays whose
clock was already stopped).

## Item 0 (D181) — right idea, two builder defects, the null failed and was not reported
- Engine routing is correct: only plays `_apply_timeouts` changed (`pre != stop & now == stop & ~eoh`) go to the new
  class, pass and rush sites. Test `test_timeout_followed_cell_used` fails on the 5Z engine and passes on 6A (checked).
- **Defect 1 — identity.** The table's `timeout_followed` includes plays whose clock was ALREADY stopped (incomplete
  1.08/game at 8.0 s, out of bounds 0.46/game) — the engine never routes those there. Running-clock-only real mean is
  21.7 s vs the table's 18.1.
- **Defect 2 — late cells lost.** Moving timeout-followed plays out of their origin cells pushed 11 late-game cells
  under MIN_CELL (100). Their fallback is the ALL-PERIOD parent, which runs about twice as long:

  | cell (outcome, state, period) | 5Z mean s | 6A falls back to | mean s |
  |---|---|---|---|
  | run, tied, Q4_late | 18.3 | run, p_tied, all | 38.2 |
  | run, tied, Q2_late | 21.1 | run, p_tied, all | 38.2 |
  | complete_inbounds, tied, Q4_late | 15.7 | p_tied, all | 39.1 |
  | first_down, tied, Q4_late / Q4_mid | 16.0 / 28.0 | p_tied, all | 36.3 |
  | first_down_rush, trail1-8, Q4_late | 17.7 | p_trail1-8, all | 35.7 |
  | first_down_rush, lead9+ / trail9+, Q2_late | 19.0 / 17.2 | p_ss, all | 38.5 / 33.7 |
  | complete_inbounds, lead9+, Q4_mid | 28.9 | p_lead9+, all | 38.0 |
  | first_down_pass, lead1-8, Q4_mid_a | 32.8 | p_lead1-8, all | 35.3 |
  | incomplete, lead1-8, Q4_mid_a | 8.3 | p_lead1-8, all | 8.1 |

  A tied offence in the last two minutes now burns ~38 s a snap instead of ~18. This is the mechanism of the five new
  late-game reds (below).
- **Null (every other class moves < 0.3 s): FAILED, not reported.** Sim on the sample, 5Z -> 6A: run +0.46 s,
  first_down_pass +0.39, complete_inbounds +0.37, first_down_rush +0.26; Q2_late run 17.6 -> 20.9, Q4_late complete
  17.0 -> 18.4.
- Where the -2.0 plays came from (sample: 129.04 -> 127.02): the timeout path itself +16 s a game (2.8 snaps, ~7 ->
  12.7 s); the other classes getting longer ~+37 s. About two thirds of the drop is the null failing.
- Pre-reg "sim timeout_followed mean within 1.5 s of real": sim **12.7 s** vs real 18.0 on the sample — FAILED (not
  reported). By period the sim is close (Q4_late 15.5 vs 15.6); the MIX is wrong: the sim calls these timeouts almost
  only in the last 2-3 minutes (normal period 0.06 a game), real teams ~2 a game outside them (defence in Q4 before
  the two-minute mark 0.91, offence in normal play 0.60 — mostly play-clock timeouts at ~40 s).
- The "timeouts called per game, sim vs real by team and half" diagnosis was not delivered. Measured here: sim
  **3.4 a game** (off 1.37, def 2.02) vs real **7.7** (H1 off 2.28 / def 1.47; H2 off 1.49 / def 2.35).

## Item 1 (D182) — the explanation for the failing test is wrong
- D182 says the kneel test fails because "the FGS kneel path still draws from the old cell". The FGS path logs as
  `fgs`, not `kneel`; the test's kneel events all come from the new code path, which does draw the new cell.
- The real cause: the builder measures only NON-FINAL kneels (a kneel that ends the half has no next snap and is
  dropped), but the engine applies that runoff to every kneel and the test averages every kneel. Like for like
  (final kneels included, elapsed capped at the end of the half): **real 25.9 s** (final 22.1, non-final 32.4); sim on
  the test game **20.6 s** (final 15.8, non-final 24.5). Kneels per game match (sim 1.53, real 1.51).
- Same bug class as item 0: a kneel followed by a defence timeout draws the `incomplete` cell (~8 s); real 22.8 s.
- Size: ~7.6 s of clock a game (~0.3 plays). Small next to item 0's defects.

## Item 2 (D183) — not done; both of its claims are wrong. Cowork measured both parts.
**(a) Safeties.** D183: "the roll fires on kneels/penalties/spikes" — false by the code: the roll uses `playing =
alive & ~punt & ~fg & ~no-play-penalty`, and `alive` already excludes kneels and spikes. D183: "excess from extra
drives" — also false. Measured (zone snaps per game; sim = sample, both engines alike):

| zone (own goal) | real snaps/g | sim snaps/g | real rate/snap | real saf/g |
|---|---|---|---|---|
| 90-94 | 2.26 | 2.04 | 0.0020 | 0.005 |
| 95-97 | 0.72 | 0.91 | 0.0166 | 0.012 |
| 98-100 | **0.385** | **1.31 (3.4x)** | 0.0406 | 0.016 |

Sim safeties 0.069-0.072 a game = exactly its zone snaps x the table rates (0.0724), all from the pre-snap roll.
The whole excess is the own 1-2: the sim takes 3.4x the real number of snaps there. Leading hypothesis (not yet
measured): after the roll says "no safety", a loss that would cross the goal line is clamped to the 1
(`min(yl, 99)`), so the loss tail piles onto the 1 instead of being the safety the rate already counted. Also: 10 of
the 45 real pass/run safeties start outside the 10; with real zone snaps the engine would make 0.032 a game, not
0.041 — reported, not a target to tune to.

**(b) Points per drive** (owed since 5Z; offensive points by start bucket, K1 drive definition; real = all 1,087 K1
games; sim = sample on the 6A engine):

| start | real drives/g | sim | real pts/drive | sim |
|---|---|---|---|---|
| own 1-20 | 5.59 | 4.55 | 1.40 | 1.20 |
| own 21-40 | 12.60 | 14.94 | 1.94 | 1.69 |
| mid 41-60 | 2.31 | 2.09 | 2.48 | 2.51 |
| opp 40-21 | 0.88 | 1.03 | 3.54 | 3.46 |
| opp 20-1 | 0.36 | 0.35 | 4.75 | 4.75 |

Offensive points a game: real 42.83, sim 41.14, gap **-1.69** = START MIX **+2.99** + EFFICIENCY **-4.28** +
interaction -0.40 (closes exactly). 5Z engine: -1.00 = +3.71 - 4.25 - 0.46. **Pre-registration (START MIX >= 50% of
the gap) FAILED**: the start mix ADDS points (more drives); the whole deficit is efficiency on long fields. Own 21-40:
TD rate sim 18.7% vs real 21.5%, FG 13.2% vs 14.8%, drives ending on the clock 8.6% vs 5.6%. Own 1-20: TD 13.1% vs
15.6%, safety 1.5% vs 0.8%. The midfield and short-field buckets are right. Candidate cause for 6C (unmeasured): the
known first-downs-by-penalty shortfall (1.27 vs 1.73 a team) removes ~0.9 drive-extending first downs a game.

## Item 3 (D184) — numbers reproduce; one label wrong; five new reds come from item 0
- From `phase6a_k1_after_rows.parquet`: plays **126.21**, drives **22.945**, pts/team **21.17**. vs 5Y K1 (128.29 /
  23.29 / 21.55): plays -2.08, drives -0.35, pts **-0.38**. Pre-regs: plays 127.2 +- 1.0 HELD (at the edge), drives
  fall 0.2-0.6 HELD, **pts moves < 0.4 HELD** — D184 labels it FAILED "-1.12", which compares to the wrong base.
- The K1 header says `a86ba74fc-dirty` (the order said: commit first). The fingerprint 554a8028dd14b3a1 matches the
  committed engine; the dirty file was the re-fit calibration map. Procedural, fourth time running.
- Suite, run by Cowork on both engines (Linux): main **4 red** (fd_pen, safety_share, tied-drives-expire, props
  clv_join_mnf — the last is a data-archive test that fails here and passes on the Mac); 6A **10 red**. New on 6A:

  | test | 6A value | limit |
  |---|---|---|
  | overall tie rate | 0.0119 | <= 0.010 |
  | P(|m|=3 given equal TDs, one FG apart) | 0.612 vs 0.713 | +- 0.10 |
  | P(tie given OT) | 0.167 vs 0.043 | <= 0.123 |
  | offence timeouts/game (5a7) | 1.37 vs 1.78 | +- 0.40 |
  | tied-drive FG rate late (5a8) | 0.130 vs 0.251 | +- 0.08 |
  | test_engine_5z hash | bc88... for the new fp | == 80848eefb5a45062 |
  | test_engine_6a kneel | 20.6 s | > 25 |

  The first five are late-game and tied-game dynamics — the signature of defect 2 (tied offences burning 38 s a snap
  in the last two minutes, so they run out of time before kicking). The 5Z hash test asserts the 5Z hash for ANY
  fingerprint: it can never pass again once the engine moves. It should assert the fixture's 5Z entry
  (`62320588f80d0593 -> 80848eefb5a45062`), which keeps its meaning. `safety_share` passes on 6A only because drives fell.

## Verdict
**Do not merge eng/6a.** The K1 plays gap of +0.4 is partly real (a timeout-stopped play no longer draws the
incomplete runoff) and partly compensating error (late cells falling back to twice their runoff), and it costs five
new late-game reds. The work is kept: order 6B branches from eng/6a, fixes the two builder defects and the kneel
measurement, fixes the timeout frequency (the sim calls under half of real timeouts), fixes the own-1 snap pile-up
behind the safety excess, and re-fits once. D185 (below) is appended by 6B's first commit so the decision doc stays
linear; D181-D184 reach main when 6B merges.

### D185 — Cowork verification of 6A: not merged; 5Z mislabel corrected; safety and points-per-drive measured (2026-09-28)

6A (eng/6a @ fc3724115) not merged. D181's routing is right but its table has two defects: timeout_followed includes
stopped-clock plays the engine never routes there (running-clock real mean 21.7 s vs 18.1), and removing those plays
from their origin cells dropped 11 late-game cells below MIN_CELL, which now fall back to all-period parents (~38 s vs
~18 s, e.g. run/tied/Q4_late 18.3 -> 38.2). Its null failed unreported (run +0.46 s, fd_pass +0.39, complete +0.37);
about two thirds of the -2.0 plays is that. Five new late-game reds (tie rate 0.0119, |m|=3 0.612, P(tie|OT) 0.167,
off TO 1.37, tied FG late 0.130) follow from it. D182's kneel table measures only non-final kneels; like for like real
25.9 s vs sim 20.6 s; a kneel followed by a timeout draws the incomplete cell. D183's two claims are false: the roll
never fires on kneels/spikes/no-play penalties, and the excess is not extra drives — sim snaps at own 1-2 are 1.31 a
game vs 0.385 real (3.4x); sim safeties equal zone snaps x table rates. Points per drive (owed since 5Z): offensive
points gap -1.69 a game = START MIX +2.99 + EFFICIENCY -4.28 + interaction -0.40; pre-registration FAILED — the deficit
is long-field efficiency (own 21-40 TD 18.7% vs 21.5%). K1: plays 126.21, drives 22.945, pts 21.17 (-0.38: D184's
"FAILED" is a wrong base; HELD). Correction to D180/5Z: the class table's "timeout_followed 2.2 at 8.9 s" was the
end-of-half runoff path, logged as `timeout_stopped`; the sim stops 2.8 plays a game with a timeout vs 4.0 real
(running clock) and calls 3.4 timeouts a game vs 7.7. Next: order 6B on eng/6b from eng/6a.
