# Phase 6B verification — Cowork, 2026-09-29 (01:45Z)

Branch `eng/6b` @ `e432be7d6` (D185 append; D186; D187-D189 "NOT DONE"; D190-D193 superseding them; log). Read from
the committed files; K1 recomputed from the rows file; the source of the own-1 pile-up traced in the 6A sample drive
logs (`research/nfl_sim/phase6a_cowork/`). **Verdict: do not merge yet; 6C continues on eng/6b.**

## What stands
- **K1 reproduces** from `phase6b_k1_after_rows.parquet`: plays **126.89** (gap +1.1; pre-reg 125.8 +- 1.5 HELD),
  drives 23.047, pts/team 21.277. Header `3358be6a9`, clean — first clean K1 header in five orders.
- **D190**: same-period pooled fallback (`ap_all`) is right; timeout_followed now excludes incompletes and
  out-of-bounds plays; its main cells look right (last two minutes 12-18 s, normal play 35-40 s = play-clock
  timeouts). The "4,446 plays, mean 29.1 s" quoted is the legacy all/all row, not the table. The null was "NOT SCORED
  (6A table not on this branch)" — false (eng/6b descends from eng/6a); minor.
- **Kneel finding (D190)** is useful: the gap is WHEN the sim kneels — the final kneel of a half comes with 6.7 s
  left in the sim vs 22.1 s real — not the per-kneel runoff.

## What does not
- **D192's cause is wrong, and so was my hypothesis in D185.** The own 1-2 pile-up is not mainly in-play losses:
  in the 6A sample the sim starts **0.83 drives a game at own 1-2 vs 0.255 real**, and **74% of them follow a punt**
  from the opponent's 40-50. Cause (engine.py:1809, eng/6b): the punt's net yards come from a table pooled over LOS
  zones (`midfield` = yl 21-60); a draw that carries past the goal line is clipped to 99 (own 1) instead of being a
  touchback. Real punts from the opponent's 35-50 are touchbacks 14-26% of the time. D192's change moved almost
  nothing: K1 safeties 0.071 vs 0.072.
- **The half-distance rule is coded wrong** (engine.py:1963): it applies only when the full penalty would pass the
  1 (`full_yl > 99`); the rule applies whenever the penalty exceeds half the distance to the goal (own 8 with 10
  yards -> own 4, and own 15 with 10 yards -> own 7.5, not own 5). Applying "half the distance" to sack/rush/pass
  LOSSES is not a football rule; it is an approximation of "a loss that did not produce the (already rolled)
  safety stays in the field" — acceptable only if the decision calls it that.
- **test_offensive_penalty_half_distance is not a test**: it re-implements the formula with numpy and never calls
  the engine; it passes on eng/6a (the order required both 6B tests to fail on eng/6a, shown). 
- **D191 extends the timeout window to 300 s using the 121-180 s rates as a proxy for 181-300 s** — rates the data
  was never measured for. TO/game 3.4 -> 4.19 (pre-reg >= 5.5 FAILED). The measured fix is a policy table that
  covers every period. The sim-vs-real timeout table the order asked for was not delivered (listed under NOT DONE).
- The "what put the ball at 98-100" table and the points-per-drive split were not delivered.
- `test_dead_clock_runoff` red is a test-selection artefact: it doubles the largest-n primary cell, which is now an
  `ap_all` fallback row the engine rarely reads. Excluding `ap_all` from the selection (as `p_*` and `all` already
  are) keeps the test's meaning.

## Reds on eng/6b (8) vs main (fd_pen, safety_share, tied expiry; + the cloud-only props archive test)
fd_pen (known), tied expiry (known), dead_clock (selection artefact), OT structure, 5a7 timeouts/kneels, tied FG late,
6A kneel (kneel timing), 6B 98-100 snaps (punt clip). Tie rate and |m|=3 pass again. Three late-game reds from 6A
remain; they share the kneel-timing and timeout-coverage causes.

### D194 — Cowork verification of 6B: not merged; own-1 pile-up traced to punts clipped at the 1 (2026-09-29)

6B (eng/6b @ e432be7d6) not merged. K1 reproduces: plays 126.89 (+1.1, HELD), drives 23.047, pts/team 21.277, clean
header. D192's and D185's cause for the own 1-2 pile-up are both wrong: 74% of the sim's 0.83 own-1/2 drive starts a
game (real 0.255) follow punts from the opponent's 40-50 whose net-yard draw (pooled `midfield` zone) carries past the
goal line and is clipped to 99 (engine.py:1809) instead of becoming a touchback (real touchback rate 14-26% from the
opponent's 35-50). The half-distance penalty rule is coded only for penalties that would pass the 1 (engine.py:1963);
the rule applies whenever the penalty exceeds half the distance. Half-distance on losses is an approximation, not a
rule. test_offensive_penalty_half_distance never calls the engine. D191's 181-300 s timeouts reuse 121-180 s rates
(unmeasured); TO/game 4.19 vs 7.7. D190's kneel finding stands: the sim's final kneel comes with 6.7 s left vs 22.1 s
real. test_dead_clock_runoff fails because it now perturbs an ap_all fallback row. Next: order 6C on eng/6c from eng/6b.
