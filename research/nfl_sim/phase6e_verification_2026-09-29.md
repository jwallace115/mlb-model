# Phase 6E verification — Cowork, 2026-09-29 (18:42Z)

Branch `eng/6e` @ `8d282dd42` (D204 append; D205, D206, D207 one commit each; `_pl_log` fix; cal maps; D208 + FREEZE_v1;
log). Checked against the committed files, in a clean worktree on Linux. The worktree has the PBP parquets symlinked in
and nothing else changed. Scripts are in `research/nfl_sim/phase6e_cowork/`.
**Verdict: FREEZE_v1 is accepted as the frozen NFL sim v1 and is merged to main. That ends the three-order time box.**
The freeze is a snapshot, not a validation. It carries the defects listed below, and they are written down rather than
fixed.

## What stands
- **The freeze mechanism works.** `test_freeze_v1.py` passes on the committed tree (4/4). I changed one line of
  engine.py in a copy, and the test failed (`Engine FP e9ae1eaa9777c467 != frozen 156cd057a3b39e48`). The test fails
  when it should.
- **K1 reproduces exactly.** From `phase6e_k1_after_rows.parquet` (1,087 rows) I rebuilt the K1 numbers:
  - pts/team 21.056 against a real 22.386;
  - plays 126.37 and drives 22.66;
  - fd_pen 1.740 a team; fg_att 3.766; 3rd-and-11+ share 0.189.

  Every number matches the text table. I then re-ran 12 random K1 games at N=500 on the clean committed tree with the
  same seeds. The maximum difference from the committed rows was **0.0** on home and away points, plays and fd_pen.
  The `-dirty` header therefore did not touch the numbers. It is still a breach of the order, but a harmless one.
- **D205, the rows OOM fix:** the rows file exists, 78 KB.
- **D206 (first downs by penalty):** the diagnosis is right. The whole shortfall is live-play penalties:
  1,036 / 135,336 scrimmage plays = 0.00766, or 0.477 a team. I reproduced that exactly. K1 fd_pen now PASSES.
- **Pre-registrations (D208):**

  | Metric | Result | Pre-registered | Outcome |
  |---|---|---|---|
  | plays | 126.4 | 125.8 ± 1.5 | HELD |
  | safeties | 0.030 | 0.028-0.040 | HELD |
  | fd_pen | PASS | PASS | HELD |
  | drives | 22.7 | 22.0-22.6 | **FAILED** |
  | pts/team | 21.06 | 21.6-22.4 | **FAILED** |
  | D207 timeouts a game | 5.54 | 6.8-8.5 | **FAILED** |
  | D207 late-game reds passing | 0 of 6 | at least 4 | **FAILED** |

  D208 calls the drives result "borderline", but that is not one of the allowed outcomes; it FAILED.

## What does not (measured by Cowork; each is a known defect of v1)
1. **D206 moves the ball 8 yards; the real advance is 19.4.** The "measured mean" of 8 is the play's `yards_gained`
   (8.44). It leaves out the enforced `penalty_yards` (10.96).
   - In reality the ball advances 19.3 yards to the next snap (median 19; 10th to 90th percentile 8 to 32).
   - The design is also wrong. D206 *replaces* the play with the penalty, but in reality the play happens and the
     penalty yards are added on top of it.
   - The cost is measured. Setting the advance to 19 as a magnitude check, on the 100 sample games at N=500 with
     paired seeds, raises the total by **+0.685 points a game (±0.026)**, about +0.34 a team. That is roughly a
     quarter of the -1.33 points gap.
2. **D206 and D207 together moved points by zero.** On the same 100 games and seeds, the 6E engine minus the 6D engine
   is a total of +0.005 ± 0.066 and a margin of +0.13 ± 0.08. D206 claimed pts/team +1.23 on its own 50-game sample,
   and that does not reproduce. The K1 figure agrees with Cowork: 21.04 on 6D, 21.06 on 6E. An 8-yard auto-first
   *instead of* the play is worth about what the play was worth.
3. **D206 runs the clock a fixed 35 s.** In reality the next row comes 23.5 s later in normal time. In the last two
   minutes of a half or the last five of Q4 it comes 6.5 s later (160 plays), because the clock starts on the snap.
   Late in a half the sim burns about 28 s of clock that the real game does not.
4. **D207 always charges the timeout to team 0.** The code is `side = int(u_arr[i] * 2) % 2`, and it only runs when
   `u < p`. The largest p is 0.166, so `int(2u)` is always 0 and the home team pays every time
   (engine.py `_apply_ns_timeout`). The effect is measured: fixing the side (a uniform draw given u < p, which
   consumes no extra randomness), with paired seeds on 100 games, changed the home margin by +0.005 ± 0.005 and home
   win probability by 0.0000. It is wrong, but its effect is immaterial.
5. **D207 is a proxy, which the order's NO PROXIES rule bans.** The rate table pools every non-scrimmage row: punts,
   FGs, kickoffs, extra points, and no_play rows including the timeout rows themselves. That pooled rate is applied only
   after punts, FGs and no-play penalties. The rates are hardcoded in engine.py, not built into a table.
   - The real figures are measured (script in `phase6e_cowork/`; 7.70 team timeouts a game):

     | What came before the timeout | Timeouts a game |
     |---|---|
     | a scrimmage play | 6.27 |
     | a no-play penalty | 0.39 |
     | a field goal | 0.38 |
     | a punt | 0.30 |
     | another timeout | 0.25 |
     | a kickoff | 0.07 |
     | an extra point | 0.01 |
     | quarter start or other | 0.04 |

   - Against the three event types D207 targets, real is **1.07 a game and the sim adds 0.30**.
   - The design also makes `test_t2_timeout_policy_live` red, correctly. That test zeroes the measured timeout table
     and still gets 921 timeouts in 2,000 sims, because the hardcoded dict sits outside it.
6. **D207's explanation of the remaining gap is false.** It says the gap is "TV timeouts, injury timeouts". The 7.70
   counts team-charged timeouts only (`timeout_team` set), so TV and injury stoppages are not in it. The real gap is
   about 1.0 a game after scrimmage plays (sim ≈ 5.24 against 6.27 by this classification) plus about 0.8 after
   non-scrimmage events.
7. **The reds.** Cowork ran the 11 named tests on both branches.
   - **eng/6e has 10 red, not 11.** `test_player_off_hash_stable` PASSES, because its fixture was re-recorded in the
     same commit. FREEZE_v1's red list is wrong on that line.
   - **New on 6E** (green on 6D):

     | Test | 6E value |
     |---|---|
     | overall tie rate | 0.0107 (limit 0.01) |
     | timeout_policy_live | see item 5 |
     | ez_share | 0.100 against 0.1215 (tolerance 0.02) |

   - **Worse on 6E:**

     | Test | 6D | 6E |
     |---|---|---|
     | kneel table | 19.7 s | 17.5 s (real 25.9) |
     | off TO | 2.44 | 2.58 |
     | Q2 late snaps | 8.32 | 8.15 |

   - Tied-offence kicks did not "regress from PASS", as D207 says. It was red on 6D (0.167 against 0.251) and is 0.150
     on 6E.
   - Unchanged-red: OT structure, kneels & late snaps, tied expiry (0.118 on 6D, 0.099 on 6E).
   - Cowork did not re-run the full suite: two cores, over 1.5 h. The other 224 tests are taken from the Mac report.
8. **Deliverables the order asked for that did not arrive:**
   - D206's breakdown by penalty category, auto-first vs yardage, and down/distance band. Only the live vs no-play
     split was given.
   - D206's sample was 50 games, not the 200.
   - D207's per-branch table of the six reds (main / 6C / 6D / after). It gave "value from test output" instead of
     numbers.
   - The points split for fit_6d vs fit_6e. The log admits it.
   - A test for D207. `test_engine_6e.py` holds one test, the fd_pen one.
   - The W3 board. There is no W3 candidates file (`nfl/data/board/week=2026_03` holds only TNF placements), so that
     is a named blocker and is accepted.
9. **Fingerprint coverage.** The fingerprint covers engine.py, anchor.py, params_v1.json and the tables directory. It
   does not cover `nfl/sim/tables.py` or `seed_util.py`, both of which the engine imports. A change to either would
   leave the freeze test green. Recorded here; not fixed.

## What v1 is, for the forward test
- The live sim is **anchored to the market** (`anchor.py`, D7). Additive EPA offsets make the mean margin and total
  equal the Hard Rock line. On game spreads and totals the sim's probability equals the book's by construction, so a
  forward test of v1 on game lines tests nothing. The forward test is on **player props**, where the sim's own
  distributions carry the opinion.
- K4 on the 6B engine already has the sim worse than the market in all 8 prop families. None of the defects above is
  large enough to change that. The forward test is therefore a pre-registered confirmation (P1: book Brier ≤ sim
  Brier; expected to HOLD), not a search for an edge.
- A v2 would fix items 1, 3, 4 and 5 and move the tables into a builder. Per the freeze rule that restarts the forward
  count. It is not ordered; Jeff decides.

### D209 — Cowork verification of 6E: FREEZE_v1 accepted and merged with its defects written down; the time box is closed (2026-09-29)

6E (eng/6e @ 8d282dd42, carrying 6A-6E) is merged to main as the frozen NFL sim v1: engine 156cd057a3b39e48, usage
3638769c89030de0, fit_6e.

What was verified:
- test_freeze_v1 passes on the committed tree and fails when one engine line changes.
- K1 recomputed from the rows matches: pts/team 21.056 against 22.386, plays 126.37, drives 22.66, fd_pen 1.740.
- Twelve K1 games re-run at N=500 on the clean tree reproduce the rows with a difference of 0.0, so the `-dirty` header
  changed no numbers.
- Pre-registrations: plays, safeties and fd_pen HELD; drives 22.7, pts/team 21.06, timeouts 5.54 and the four-of-six
  reds FAILED.

Defects of v1, all measured:
- D206 advances 8 yards; the real figure is 19.4, because D206 counted yards_gained and dropped 10.96 penalty yards.
  It also replaces the play instead of adding to it. Setting 19 moves the total +0.685 a game.
- D206+D207 changed the total by +0.005 ± 0.066 against 6D, so D206's claimed +1.23 a team does not reproduce.
- D206's clock is a fixed 35 s; real is 23.5 s in normal time and 6.5 s late.
- D207 always charges team 0. The margin effect is +0.005 ± 0.005: wrong but immaterial.
- D207 applies a rate pooled over punts, FGs, kickoffs, XPs and timeout rows only after punts, FGs and no-play
  penalties: 0.30 a game against a real 1.07. That breaks the no-proxy rule.
- D207's attribution of the remaining gap to TV and injury timeouts is false, because the 7.70 are team-charged.

Reds on 6E: 10, not 11 (player_off_hash passes).
- Green on 6D and red on 6E: tie rate 0.0107, timeout_policy_live (the hardcoded dict bypasses the measured table),
  ez_share 0.100.
- Worse on 6E: kneel table, 17.5 s against 25.9.
- The other six late-game reds were already red on 6D.

Not delivered: D206's breakdown tables, D207's per-branch table, the fit_6e points split, and a D207 test. W3 has a
named blocker: no candidates file.

The sim is market-anchored on sides and totals, so v1's forward test runs on player props (order FWD1). v2, which
would fix the listed defects and restart the count, is not ordered.
