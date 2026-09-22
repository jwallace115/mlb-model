# Phase 5M work order — player-layer RNG stream, Q4_mid split (5K), ONE re-fit, share-shrinkage measurement

Date: 2026-09-22 (UTC). Repo: jwallace115/mlb-model. Scope: `nfl/sim/` and `research/nfl_sim/` only.
Read first: `research/nfl_sim/phase5l_verification_2026-09-22.md` (Cowork), D114-D118, and
`research/nfl_sim/workorder_5K_2026-09-20.md` (its item 1 is this order's item 2, minus the re-fit).
Prerequisite on main: D118 present (`grep -c "^### D118" research/nfl_sim/NFL_SIM_DECISION_v1.md` = 1).
If 0, STOP and report: the 5L merge has not landed.

## Why this order exists

5L fixed the one-draw-per-player defect and the board is now bit-identical across machines. Two things
are left from 5L and one from 5I:
(a) `simulate_game` builds ONE `rng` (engine.py:727) and uses it for both the player context and every
    play draw, so with the player layer ON the team-level game is a different random realisation than
    with it OFF. T4 (`TestT4PlayerLayerNeutral`) is red at its fixed seed for that reason and green at
    five others. The player layer must not be able to touch team outcomes AT ALL, not just on average.
(b) Punts/game 8.84 vs 7.90 real and the tied-drive expiry: the queued 5K change (Q4_mid split at 180 s).
(c) Sim vs book SD(raw) 0.149 vs pre-registered < 0.12 did not hold. The stated explanation — week-1
    share estimates — is a hypothesis nobody has measured. Item 4 measures it and changes nothing.
Items 1 and 2 both change the engine fingerprint; they share ONE re-fit (item 3).

## HARD RULES (as 5K; binding)

1. Branch `eng/5m`, worktree `~/mlb-model-5m`, from origin/main after D118. `main` untouched. Cowork verifies.
2. No existing test, tolerance, threshold, `MIN_CELL`, `N`, or sample filter is edited. New tests in NEW
   files `nfl/sim/tests/test_engine_5m.py`, `test_usage_5m.py`.
3. Nothing is tuned to hit a test. Constants come from PBP by committed builder code.
4. Never reduce N, subsample, skip a test or kill a run to finish sooner. Measure runtimes and report them.
5. `GIT_OPTIONAL_LOCKS=0` on every git command. Commit AND push each item before the next
   (`git push -u origin eng/5m`). Each item writes its `### DNN` entry (grep for the next free number,
   D119+) in the same commit.
6. A diff is not evidence. Paste execution output from the production entry point; every guard is shown
   changing an outcome.
7. Zero API credits. Do not touch `bets/`, `nfl/pipeline/`, `ncaaf/`, `shared/`.

## Setup

```
cd ~/mlb-model && GIT_OPTIONAL_LOCKS=0 git pull --rebase --autostash
GIT_OPTIONAL_LOCKS=0 git worktree add ~/mlb-model-5m -b eng/5m
cd ~/mlb-model-5m
for f in ~/mlb-model/nfl/data/pbp/*.parquet; do [ -e "nfl/data/pbp/$(basename $f)" ] || ln -s "$f" "nfl/data/pbp/$(basename $f)"; done
python3 -c "from nfl.sim.calibration import engine_fingerprint as f; print(f())"   # must print c01d2af899c7e9f8
```
Anything else: STOP and report.

---

## Item 1 — a child generator for the player layer; the played game leaves the union set

1a. In `simulate_game`, derive `player_rng = np.random.default_rng(stable_seed((seed, "player")))` (use the
    repo's `seed_util.stable_seed`; state the exact tuple) and pass THAT to `_build_player_context`. The
    play-loop `rng` is untouched. No other engine change.
    PRE-REGISTERED: (i) with the player layer ON, `home_score`/`away_score` per sim are IDENTICAL
    (np.array_equal) to the player-OFF run at the same seed — write this as a test; (ii) T4 goes green
    at its fixed seed with no threshold edit; (iii) NULL CONTROL: the player-OFF run at seed `T4_test`,
    N=4000 produces the same score arrays as on main (hash them before and after — this is the proof the
    play stream did not move). Report the new fingerprint. Board will be SUPPRESSED until item 3; say so.
1b. `run_week.py`: a game whose `commence_time` is before `--as-of` is excluded from the union game set
    (5J left DET@BUF, already played, in the Week 2 board: 16 games, +76 legs). Test with a fixture.
    NULL: with `--as-of` before every kickoff, the game set is unchanged.
1c. `test_usage_pit_5j.py` must not reach the network: fixture or monkeypatch. State how you proved it
    (e.g. run with the network disabled and it still passes).

## Item 2 — Q4_mid split at 180 s, exactly as `workorder_5K_2026-09-20.md` item 1, steps up to and
including "engine + tables + tests" — NOT its re-fit step

Cell sizes FIRST (its Step 0), the fallback order as written there, the tests in `test_engine_5m.py`
(the 5K file name is superseded). Report the fingerprint after. The pre-registered predictions in 5K
(late-clock pace by sub-cell, tied-drive expiry direction) are graded in item 3 after the re-fit.

## Item 3 — ONE re-fit `fit_5m`, re-stamp, K1, K4, suite, board

`run_fit.py --seasons 2021 2022 2023 2024 --out-dir fit_5m` (N per D51, unchanged), then
`run_cal_maps.py --fit-dir fit_5m`, `run_k1_table.py` -> `research/nfl_sim/phase5m_k1_after.txt` (+rows),
`run_k4.py --fit-dir fit_5m --output research/nfl_sim/phase5m_k4.parquet`, the full suite, then the board
`--week 2 --as-of 2026-09-20T15:30:00Z`, saving `research/nfl_sim/phase5m_boards/picks_log_mac.parquet`
for Cowork's Linux cross-check. Measure the single-run re-fit wall time.
PRE-REGISTERED, write before looking: punts/game falls from 8.84 by at least 0.3 toward 7.90 (D108:
5I moved punts AWAY from real; 5K's cell is where that pace error lives); `tied_expiry_broad` moves toward
0.081 from 0.119. NULL CONTROLS: pts/team within 0.10 of `phase5l_k1_after.txt` (22.7487); go_rate,
off_pen, def_pen, fg_att within their K1 tolerances of the 5L values. If a prediction fails, say so and
tune nothing. Suite: state the count and name every red; T4 must be green (item 1). Board: 15 games now
(item 1b), no SUPPRESSED, ranked.

## Item 4 — MEASURE the week-1 share hypothesis (no engine or usage change)

Script `nfl/sim/run_share_shrinkage_5m.py`, committed. From PBP 2021-25 build, per player-season with
>= 8 games: target share and carry share in week 1 (s1), in the prior season (s0, if >= 8 games), and
the realised share over weeks 2-8 (s_out). For shrinkage weights w in {0, 0.1, ..., 1.0}, predictor
p_w = w*s0 + (1-w)*s1 (players with no s0: p = s1 for every w; report them separately).
DISCOVERY on 2021-24 only: the w minimising MAE(p_w, s_out) by position (WR/TE/RB). HOLDOUT 2025: MAE of
that w vs w=0 (raw week-1) vs w=1 (prior season only), by position, with n.
PRE-REGISTERED: on the 2025 holdout, the 2021-24 w reduces MAE vs raw week-1 by more than 15% for WR and
RB target share; if it does not, the week-1-share explanation for the sim-vs-book gap is weakened and the
report says so. Also report, for the Week 2 2026 board, what fraction of priced players have no s0.
DO NOT apply any weight to the usage layer in this order. Write the numbers into `### DNN` and
`research/nfl_sim/phase5m_share_shrinkage.md`. The decision to apply it is Jeff's/Cowork's, next order.

## Closing

`logs/agent_sessions.md` entry (`git add -f`): what each command RETURNED vs what it MEANS; runtimes
measured; what was NOT done; what remains UNVERIFIED (at minimum: the Linux cross-check of the 5M board).
