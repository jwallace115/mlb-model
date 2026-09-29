# Work order FWD1 — the forward test of the frozen NFL sim v1 (2026-09-29)

Written by Cowork after verifying 6E (`phase6e_verification_2026-09-29.md`, D209). eng/6e is merged to main as
FREEZE_v1 (engine 156cd057a3b39e48). **This order does not touch the engine.** Any change to a file the freeze hashes
turns the sim into v2 and restarts the forward count.

Pre-check (Cowork):
- **Runtime.**
  - `run_week.py` took 209 s for 17 games at N=10,000 (the week-2 log `nfl/data/sim/outputs/week2_run.log`).
  - The sheet, fill and freeze steps take seconds each.
  - The item 2 pilot is one run_week plus scoring, about 5 minutes.
  - The tests take a few minutes.
- **Credits.** Zero; everything reads the archived tape.
- **Files.**
  - New: `nfl/sim/run_forward_v1.py`, `nfl/sim/tests/test_forward_v1.py`, `research/nfl_sim/fwd1_*.md` and summary
    parquets under 2 MB.
  - Edited: `nfl/pipeline/log_ai_opinions.py`, which gets one new tag and a pilot-only `--as-of`.
  - Outputs go where the logger already writes: `nfl/data/board/week=2026_WW/ai_opinions/`.
- **Known facts the order relies on.**
  - The live sim is anchored to the market (`nfl/sim/anchor.py`, D7). Game spreads and totals therefore carry no sim
    opinion.
  - The week-2 run log shows 16 of 17 games `[NOT CONVERGED]` after 5 iterations. Whether the printed margins are raw
    or anchored is not known; item 1 must establish it.

```
Work order FWD1 (research/nfl_sim/workorder_FWD1_2026-09-29.md). Branch eng/fwd1 from origin/main in a worktree; main
untouched until Cowork verifies. Gates (git fetch origin first): `git show origin/main:research/nfl_sim/FREEZE_v1.json
| grep -c 156cd057a3b39e48` prints at least 1, `git show origin/main:research/nfl_sim/NFL_SIM_DECISION_v1.md | grep -c
"^### D209"` prints 1, and `python3 -m pytest -q nfl/sim/tests/test_freeze_v1.py` passes in the new worktree (4
passed). If any gate fails, STOP and print all three. FIRST STEP: if the worktree /tmp/eng-6e still exists, `git
worktree remove /tmp/eng-6e` (6E is verified and merged) and print `git worktree list`. Items 0-2, ONE COMMIT PER
ITEM, push each before the next; decisions D210-D212 appended at the end of research/nfl_sim/NFL_SIM_DECISION_v1.md in
the same commit as their code. Session log appended to logs/_log_fwd1.txt (git add -f), timestamps from `date -u`.
No file > 2 MB. Never weaken a test.

HARD RULES: (1) Do NOT modify any file FREEZE_v1 hashes (nfl/sim/engine.py, anchor.py, params_v1.json,
calibration_v1.json, nfl/data/sim/tables/*). test_freeze_v1 must pass at every commit; run it and paste the line.
(2) Every code claim cites file:line. (3) A new test calls the real function and must FAIL before the code it tests
exists — run it first and paste the failure. (4) The repo is public: no slip IDs, no raw exports from bets/.

Item 0 (D210) — the pre-registration, written BEFORE any sim opinion exists. Decision text only, no code. Copy:
  "Forward test of NFL sim FREEZE_v1 (engine 156cd057a3b39e48, fit_6e). Reader model string
  nfl_sim_v1_156cd057. Scored with log_ai_opinions.py score exactly as pre-registered there (2026-09-21): revision 0
  only, pilot files never pooled, game-cluster bootstrap. Scope: two-way player props on the Hard Rock tape. Game
  spreads, totals and moneylines are logged as no_view (the sim is anchored to the market on them, D7) and never
  scored for the sim. P1: Brier(book de-vig) <= Brier(sim) on two-way props — expected to HOLD. P2: the sim's sides
  with |p - q| > 0.08 lose units at the real Hard Rock price of the side — expected to HOLD. Checkpoints at 500 and
  1,500 scored two-way legs; nothing is concluded before 500. Breakouts every checkpoint: family, trust tier, week,
  |p - q| bucket, and anchor status (item 1). Anchor rule, fixed now: a game whose final anchored mean misses the
  market by more than 1.0 point on margin OR total is 'unanchored'; its props are frozen and scored but reported
  separately and excluded from P1/P2. No engine change during the test; a change is v2 and restarts the count."

Item 1 (D211) — nfl/sim/run_forward_v1.py, the harness. For a week: (a) run test_freeze_v1 in-process (pytest.main
  on that file) and HALT if it fails; (b) build the sheet (log_ai_opinions.py `sheet`, newest pre-kick Hard Rock pull);
  (c) run nfl/sim/run_week.py for the week unchanged (same --as-of as the sheet's pull) and read its picks_log.parquet;
  (d) fill: a two-way prop sheet row whose (player, market, line) matches a picks_log row takes p_first = cal_p of the
  OVER side (convert if the picks_log row is the under), tag sim_v1, reason "sim v1 cal_p <tier>"; an unmatched prop
  row and every game-line row take tag no_view with p_first = q_first; (e) freeze with --reader-model
  nfl_sim_v1_156cd057; (f) write a per-game anchor sidecar next to the frozen file: game, market spread and total, the
  FINAL anchored mean margin and total, iterations, converged flag, and the item-0 anchored/unanchored label. First
  establish, with file:line, whether run_week's printed "margin X vs Y" is the raw or the anchored mean.
  Add "sim_v1" to TAGS in log_ai_opinions.py (nothing else changes there). Report the match rate of two-way prop rows.
  Tests (test_forward_v1.py): the harness halts when the freeze manifest disagrees (point it at a temp copy with one
  hash changed); a game-line row is always no_view with p_first == q_first; a matched OVER row gets cal_p exactly and
  a matched UNDER-only row gets 1 - cal_p; an unmatched prop row is no_view.

Item 2 (D212) — the pilot, end to end, on week 4 (already played). Add `--as-of` to log_ai_opinions.py freeze, allowed
  ONLY with --pilot (it errors without --pilot; test it). Run the harness for week 4 with --pilot and --as-of set to
  the last Hard Rock pull before each kick window, then `score --include-pilot` and `verify`. Deliver: rows, two-way
  prop rows, the sim's coverage, the anchor sidecar table (how many games are unanchored under the item-0 rule),
  Brier sim vs book with the bootstrap interval, and the P2 units. This is a PILOT: it is never pooled, and it is not
  evidence for or against P1/P2 — say so in D212. Then write research/nfl_sim/fwd1_runbook.md: the exact commands Jeff
  (or Cowork) runs before the TNF kick and before the Sunday 1 pm ET window each week, and the scoring command at each
  checkpoint.

Every item's report separates what the command RETURNED from what it MEANS and ends with NOT DONE and UNVERIFIED.
```
