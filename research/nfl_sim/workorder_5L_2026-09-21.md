# Phase 5L work order — player shares are drawn ONCE per chunk, not once per sim (engine defect), + one re-fit

Date: 2026-09-21 (UTC). Repo: jwallace115/mlb-model. Scope: `nfl/sim/`, `research/nfl_sim/` only.
Read first: `research/nfl_sim/phase5j2_verification_2026-09-21.md` (Cowork), D112 and
`research/nfl_sim/phase5j2_reproducibility.md`. Runs BEFORE 5K; 5K stays queued behind it.

## Why this order exists — measured, not guessed

D112 found that the ORDER of tied players changes the board (unstable `sort_values`, engine ~line 473) and
proposed a stable sort. That is a symptom. The cause, which D112 did not ask: **why can re-ordering players
move Ashton Jeanty from 16.6 to 23.7 mean carries at N=5,000?** Random draws cannot do that — unless there
are almost no draws. There are almost none:

`engine.py::_build_player_context::_disperse` (~lines 504-519) is documented "per-sim Beta-dispersed shares"
and "Draw (N, n_pl) dispersed shares", but the draw is `out[:, j] = rng_obj.beta(a, b)` — **no `size=N`**.
That is ONE scalar per player, broadcast to every sim in the call. Cowork, Linux, branch `eng/5j`:
- `_build_player_context('LAC','LV',2026,2, n_sims=2500)`: Jeanty's carry share over 2,500 sims has
  **1 unique value** (0.7721; std 0).
- `simulate_game(... n_sims=1000)`, seeds 1-6, LV: Jeanty mean carries 21.19 / 21.64 / 19.28 / **10.47** /
  17.30 / 20.77 (SD 4.2); Mike Washington 5.55 / 2.01 / 7.61 / **14.55** / 8.86 / 1.38; team carries
  28.7-29.4 (stable).
The weekly board runs 2 chunks of 2,500, so every player's share on the board is fixed by TWO random draws.
Consequences: player probabilities are over-confident around a random centre (Week 2 board vs Hard Rock's
de-vigged number: SD 0.147 on receptions; Kaelon Black O9.5 0.905 while McCaffrey O14.5 0.151); the board
differs between machines whenever tie-order differs; and every player-level artefact fitted on this engine
— `calibration_v1.json` maps, K4, the TRUSTED/WATCH tiers — was fitted on output with this defect.
Team-level results (score, plays, anchoring) are NOT affected: anchoring offsets agree to 3 dp across
machines and across sort orders.

## HARD RULES
1. Branch `eng/5l` from main AFTER `eng/5j` is merged (Cowork will say when); worktree `~/mlb-model-5l`.
   `main` untouched; Cowork verifies and merges. Link gitignored inputs as in 5I/5J Setup.
   `engine_fingerprint()` must print `7f3d96900218c014` at the start; it WILL change in item 1 — expected.
2. No existing test/target/tolerance edited. New tests in `nfl/sim/tests/test_engine_5l.py`, each shown
   FAILING on main's engine. No constant tuned: `PHI_TARGET` / `PHI_CARRY` are not changed in this order.
3. 4 items; commit AND push each before the next; each writes its `### DNN` entry (grep for the next free
   number) in the same commit. Every git command `GIT_OPTIONAL_LOCKS=0`. Zero API credits.
4. Never reduce N, subsample, shorten or skip a run. Evidence is pasted execution output.
5. Nothing is tuned on 2026. Week 2 2026 numbers below are DIAGNOSTICS on an already-logged board.

## Item 0 (inside item 1's commit) — provenance of PHI
Before editing: report where `PHI_TARGET = {WR 42.9, TE 85.0, RB 71.3}` and `PHI_CARRY = {RB 7.9, ...}` came
from (decision number, script, data). Specifically: were they MEASURED from real game-to-game share
dispersion in PBP, or tuned until sim output matched something? If measured from PBP they stand. If they
were tuned against sim output produced by the one-draw bug, say so in the first line of the D-entry and
STOP after item 1 — re-deriving them is a decision for Jeff/Cowork, not this order.

## Item 1 — draw shares per sim; total order on players
- `_disperse`: `rng_obj.beta(a, b, size=N)` (per-sim column), renormalise per sim as documented.
- Player order: `sort_values(["target_share","player_id"], ascending=[False, True], kind="stable")`.
- Tests (`test_engine_5l.py`), all FAIL on main:
  a. per-sim: for LV 2026 wk2, Jeanty's carry share over n_sims=2500 has > 100 unique values and its mean
     is within 0.03 of his renormalised `carry_share`.
  b. seed stability: `simulate_game('LAC','LV',2026,2,n_sims=1000)` seeds 1-6 -> SD of Jeanty mean carries
     < 0.6 (main: 4.2).
  c. order invariance: shuffle the rows of the usage frame passed in (3 shuffles) -> every LV player's mean
     carries and mean targets identical to the unshuffled run (exact equality; same seed).
- PRE-REGISTERED: (P1) b and c hold as stated. (P2) K1 team-level lines do not move: run
  `run_k1_table.py` -> `phase5l_k1_item1.txt`; vs `phase5j_k1_before.txt`: pts/team |d| < 0.10, plays/game
  < 0.3, drives/game < 0.1, go rate < 0.002, off/def penalties < 0.06 / 0.03 (5H seed SDs). This is the
  NULL CONTROL: if team-level moves, the change did something it should not — report, do not explain away.

## Item 2 — what it does to the player distribution (2021-24, no tuning)
Committed script `nfl/sim/run_player_dispersion_5l.py`: for a fixed sample of 200 games 2021-24 (seeded,
listed in the output), main engine vs item-1 engine, same seeds, N=5,000 via `run_anchored_chunked`:
per position (RB/WR/TE) and family (receptions, rush attempts): mean and SD of the simulated count, the
share of player-games whose sim probability at the actual closing-style rung (rec >= 3/4/5; carries >=
10/15) is < 0.05 or > 0.95, and Brier of raw `sim_p` against actual outcomes at those rungs.
PRE-REGISTERED: extreme-probability share falls by more than half; raw Brier improves (falls) in every
position x family cell with n >= 300. If Brier does NOT improve, say so first — it would mean the
dispersion model itself (PHI) is wrong, which is a finding, not a failure of this item.

## Item 3 — ONE re-fit, re-stamp, K4, suite
As 5I item 4, in this order, pasting each trace: full suite (every red: is it red at the parent with the same
value? run it there); board `--week 2 --as-of 2026-09-20T15:30:00Z` BEFORE the re-fit must show SIM PRICES
SUPPRESSED and no ranked leg (if it ranks, STOP); `run_fit.py --seasons 2021 2022 2023 2024 --out-dir fit_5l`
(5C-2b: ~90 min on 10 workers — measure); `run_cal_maps.py --fit-dir fit_5l`; board again, ranks;
`run_k1_table.py` -> `phase5l_k1_after.txt`; `run_k4.py` on `fit_5l`, rows committed. K4 is a measurement,
not validation. Do not commit `nfl/data/sim/outputs/week=2026_02/`; write boards to
`research/nfl_sim/phase5l_boards/`.

## Item 4 — the two diagnostics that started this
- Cross-machine: commit `phase5l_boards/picks_log_mac.parquet` from the item-3 board. Cowork re-runs it on
  Linux. PRE-REGISTERED (Cowork): >= 99% of legs within 0.02.
- Sim vs book on the logged Week 2 board (diagnostic only): with
  `nfl/data/board/week=2026_02/nfl_prop_candidates_20260920T1614Z.parquet`, SD of (raw sim_p - book q_over)
  on receptions rows. Main: 0.171 raw / 0.147 calibrated (n=138 on the 1424Z table). PRE-REGISTERED: raw SD
  falls below 0.12. If it does not, the week-1 share estimates are the larger problem — say so.

## What this order does NOT do
No merge. No PHI change. No share-shrinkage change. No Q4_mid split (5K, next). No claim that the sim can
price a ticket: the calibration-transfer gate stays open, and under the standing rule (N54) the sim is one
input to the reader's opinion.

## Closing
`logs/agent_sessions.md` (`git add -f`), `date -u` timestamps: RETURNED vs MEANS; NOT DONE; UNVERIFIED —
facts you checked, not guesses.
