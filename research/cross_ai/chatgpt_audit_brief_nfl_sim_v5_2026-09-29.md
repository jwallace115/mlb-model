# ChatGPT audit brief #6 (v5) — the frozen NFL sim, and the forward test that starts Thursday (2026-09-29)

This is a read-only audit. **Posture: guilty until proven innocent.** Every earlier audit found real defects, some of
them in work that had been marked "verified". This time the auditee is two parties:
- the engine and the harness, written by a terminal coding agent;
- **the verifier (Cowork, another Claude instance)**, which checked that work and wrote the D-decisions.

The owner expects errors in both. Do not trust a number because a verification note repeats it. Recompute from the
committed files wherever you can.

**Repo:** `jwallace115/mlb-model` (public). **Pin: `main` @ `145a1fee0`.** Everything below is on main at that
commit.
- **Decision log:** `research/nfl_sim/NFL_SIM_DECISION_v1.md`, D01-D222. Since the last brief the new entries are
  D195-D222.
- **Verification notes** (Cowork), all in `research/nfl_sim/`:
  - `phase6c_verification_2026-09-29.md`;
  - `phase6d_…`;
  - `phase6e_…` (D209);
  - `fwd1_…` (D213);
  - `fwd1b_…` (D218);
  - `fwd1c_…` (D222).
- **The previous brief** (v4, sent to nobody; pinned to eng/6b):
  `research/cross_ai/chatgpt_audit_brief_nfl_sim_v4_2026-09-29.md`. Its section 3 still describes the history
  correctly.

**Deadline.** The first live forward freeze is the week-4 TNF run, **Thu 2026-10-01 23:30Z** (PIT@CLE, 00:15Z). Anything
that invalidates the forward test is worth more before then than after.

---

## 1. What exists now

- **The engine is frozen as `FREEZE_v1`.** `research/nfl_sim/FREEZE_v1.json` holds:
  - engine fingerprint `156cd057a3b39e48`, usage fingerprint `3638769c89030de0`, fit `fit_6e`;
  - sha256 of 29 tables, `calibration_v1.json` and `params_v1.json`;
  - the K1 lines and a list of reds.

  `nfl/sim/tests/test_freeze_v1.py` recomputes the fingerprint and the hashes. A change to a hashed file is v2 and
  restarts the forward count.
- **K1** is in-sample: 1,087 REG games 2021-24 at N=500. The rows are in `research/nfl_sim/phase6e_k1_after_rows.parquet`.

  | Metric | Sim | Real |
  |---|---|---|
  | plays | 126.37 | 125.78 |
  | drives | 22.66 | 21.74 |
  | pts/team | 21.06 | 22.39 |
  | first downs by penalty (fd_pen) | 1.740 | 1.728 |
  | safeties | 0.030 | 0.041 |

  fg_att is -0.157 against a tolerance of 0.15. Ten engine tests are red, most of them late-game: kneel timing,
  timeouts (5.54/game against 7.70 real), OT structure, tied-drive expiry, tie rate 0.0107, ez_share and
  timeout_policy_live.
- **K4** is in-sample too (`research/nfl_sim/phase6e_k4.parquet`, 72,978 prop legs 2023-24 against the six-book
  consensus close). On the 6B engine, the calibrated sim had a worse Brier than the de-vigged market in all 8
  families. 6E's K4 was **not** re-checked by Cowork.
- **The defects of v1 are documented, not fixed** (D209, measured by Cowork). Two of them, D206's advance and clock, are
  shown in the second table below.

  | Where | What is wrong | Cowork's measurement |
  |---|---|---|
  | D206 live-play first down by penalty | advances 8 yards and replaces the play; real advance 19.4 (yards_gained 8.44 + penalty_yards 10.96) | setting 19 moves the total +0.685/game |
  | D206 clock | fixed 35 s | real 23.5 s normally, 6.5 s late |
  | D207 non-scrimmage timeouts | always charged to team 0 | margin effect +0.005 ± 0.005 |
  | D207 rates | a rate pooled across punts, FGs, kickoffs, XPs and timeout rows, applied only after punts, FGs and no-play penalties | 0.30/game against 1.07 real |
  | 6E against 6D | overall change on the same 100 games and seeds | total +0.005 ± 0.066 |

  Scripts: `research/nfl_sim/phase6e_cowork/`.
- **The forward-test harness** is `nfl/sim/run_forward_v1.py`. Its steps:
  1. run `test_freeze_v1`, and halt on failure;
  2. build the Hard Rock sheet (`nfl/pipeline/log_ai_opinions.py sheet`);
  3. run `nfl/sim/run_week.py` (anchor to the Hard Rock spread/total, then the calibrated player layer);
  4. `fill_sheet`: match on (player, market, line) for `player_receptions` and `player_rush_attempts` only;
  5. freeze with reader `nfl_sim_v1_156cd057`;
  6. write the anchor sidecar.

  `--window-hours` restricts each run to one kick window. `--dry-run` stops before the freeze. Tests are in
  `nfl/sim/tests/test_forward_v1.py` and `nfl/pipeline/tests/test_log_ai_opinions_fwd1c.py`. The runbook is
  `research/nfl_sim/fwd1_runbook.md`.
- **The pre-registration is D210.**
  - Scope: two-way props only.
  - P1: Brier(book de-vig at freeze) ≤ Brier(sim), expected to HOLD.
  - P2: the sim's sides with |p − q| > 0.08 lose units at the real Hard Rock price, expected to HOLD.
  - Checkpoints at 500 and 1,500 scored two-way legs; game-cluster bootstrap.
  - A game is "unanchored" if it misses by more than 1.0 point on margin or total; those games are reported apart.

  **Amended after D210 but before any live sim data: D219 counts revisions per reader and pilot flag.** Before D219,
  the AI blind log and the sim shared one revision counter, so whichever froze a line second was never scored.
- **The week-3 pilot** (`research/nfl_sim/fwd1_pilot_w3.parquet`; the frozen file is
  `nfl/data/board/week=2026_03/ai_opinions/ai_opinions_20260927T163000Z.parquet`) has 174 two-way sim opinions.
  Cowork rescored them against outcomes taken from the AI log's graded rows on the same keys (D218).

  | Measure | Value |
  |---|---|
  | Brier, sim vs book | 0.2673 vs 0.2517 (95% interval on the gap -0.002 to +0.034) |
  | Rush attempts | sim 0.298 vs book 0.246 |
  | All sides | -10.78 units |
  | Sides with \|gap\| > 0.08 | +3.73 units on 110 |

  It is a pilot and never pooled.
- **The week labels were off by one** from 09-27 (the verifier's error). Those files were moved to
  `week=2026_03` (D214), with the manifest entry unchanged.

## 2. Questions — answer in this order, cite file:line

**Q1 — Is the forward test valid as a test of the frozen object? (identity, Check 3)**

The freeze hashes `engine.py`, `anchor.py`, `params_v1.json`, `calibration_v1.json` and the tables directory
(`nfl/sim/calibration.py` `ENGINE_FINGERPRINT_FILES`, `engine_fingerprint`). It does **not** hash `run_week.py`,
`usage.py`, `pricer.py`, `ratings.py`, `names.py`, `calibration.py` (the code that applies the maps), `tables.py`,
`seed_util.py`, `run_forward_v1.py` or `log_ai_opinions.py`. Cowork noticed this while writing this brief and has not
fixed it.

- Which of those change what the sim writes into the log, so that an edit would change "v1" without failing the
  freeze test?
- What exactly should the manifest cover?

**Q2 — Point-in-time inputs for 2026 weeks (Checks 1a/1b).** Walk `run_week.py` for a live week-4 run:
- team ratings, tendencies and pace;
- player usage;
- depth charts and injuries;
- the line snapshot used for anchoring;
- the props pull.

Is any input built from data after the freeze time, or from an end-of-season or whole-season aggregate? The
calibration maps are fitted on 2021-24, so is anything in the 2026 path fitted on 2026 outcomes?

**Q3 — The metric changed; was that right?** The v4 finish line proposed probability CLV against the **Pinnacle
no-vig close**. D210 instead uses Brier against **Hard Rock's de-vig at freeze time**, plus outcomes. For a sim whose
game means are anchored to Hard Rock:
- Which metric can actually distinguish skill from noise at 500 and 1,500 legs, given many legs per game (the game
  is the cluster)?
- Is P1 as written almost certain to HOLD, and so uninformative?
- Is there a sharper pre-registration that is still honest?

**Q4 — The D219 amendment.** Revision 0 is now counted per reader_model and pilot flag.
- Does this open any way to score a later, better-informed opinion as "first", for example by changing the
  reader_model string, or by re-running a window with a new file?
- Should the forward count be locked to exactly one reader string, with any re-freeze of a line by that reader
  refused rather than recorded as revision 1?

**Q5 — Harness defects.** Read `fill_sheet`, `anchor_sidecar`, `main` and the flag pass-through in
`run_forward_v1.py`, and `newest_inputs`, `build_sheet`, `validate`, `prior_revisions`, `freeze` and `score` in
`log_ai_opinions.py`. List anything that could, on a live run:
- freeze an opinion for the wrong line or market;
- tag a non-sim number as `sim_v1`;
- drop sim rows from scoring;
- use a props pull after the freeze time;
- cross kick windows;
- or pass tests while wrong. (Twice already, the tests copied logic instead of calling the real function.)

**Q6 — Audit the verifier.** Pick at least three numeric claims in D209, D213, D218 or D222 and recompute them from
the committed files and scripts, for example:
- the 19.4-yard advance (`phase6e_cowork/real_live_pen_and_ns_timeouts.py`);
- the 7.70 team timeouts and their split by preceding event;
- the pilot Brier 0.2673/0.2517 from `fwd1_pilot_w3.parquet` plus the frozen file;
- the "10 reds, not 11" claim;
- the week-3/week-4 date boundaries.

Say which hold and which do not. Also check:
- the verifier's claim that anchoring converges (committed `nfl/data/sim/outputs/week=2026_02/anchoring_log.parquet`);
- its explanation of why D206+D207 moved points by about zero.

**Q7 — The runbook's timing.** `fwd1_runbook.md` runs:

| Window | Run at (UTC) | Window length |
|---|---|---|
| TNF | 23:30 Thu | 2 h |
| London | 12:45 Sun | 1.5 h |
| Sunday | 16:15 Sun | 9 h |
| MNF | 23:55 Mon | 2 h |

The VM props slots it relies on are: Thu 22:00, Sat 14:00, Sun 15:00/16:00, Mon 23:45. The London run reads a pull
about 23 h old.
- Is that acceptable for P1/P2, given that the sim and the book are compared at the same timestamp but outcomes
  happen after later news?
- Does any window double-count or miss a game? Check SNF 00:20Z Mon, and the MNF date.

**Q8 — Should the defects in D209 be fixed before the count starts?** The count has not started; the first freeze is
Thursday. Fixing them means a v2 (advance 19.4, clock by state, per-event timeout rates, side choice) and a re-fit
(about 90 minutes plus K1 and K4).
- Would a v2 change the forward test's expected outcome, given that K4 has the sim worse than the market in every
  family?
- Or is freezing a known-buggy v1 the right call because the question being asked is "does the sim beat the market
  at all"?

**Q9 — One paragraph: what would you stop doing?**

A reply is most useful as:
- **(A)** anything that must change before Thu 23:30Z, ranked, with file:line;
- **(B)** a verdict on each of Q1-Q8;
- **(C)** the verifier's claims you recomputed, each marked HOLDS or FAILS with your number.
