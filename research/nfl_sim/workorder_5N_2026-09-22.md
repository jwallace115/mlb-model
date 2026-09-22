# Phase 5N work order — two test rewrites, share-shrinkage re-measured honestly, the drives-per-game excess diagnosed

Date: 2026-09-22 (UTC). Repo: jwallace115/mlb-model. Scope: `nfl/sim/` and `research/nfl_sim/` only.
Read first: `research/nfl_sim/phase5m_verification_2026-09-22.md`, D119-D123.
Prerequisite on main: `grep -c "^### D123" research/nfl_sim/NFL_SIM_DECISION_v1.md` = 1. If 0, STOP and report.

## Why this order exists

5M merged with two of its own tests red: `test_player_off_hash_stable` hardcodes a hash that item 2
legitimately changed, and 5J's `test_prekick_line_chosen_for_kicked_game` asserts behaviour 5M replaced.
A red that stays red gets ignored (CLAUDE.md). Item 4 of 5M found a large shrinkage gain but on a sample
conditioned on the future (>= 8 games played) and only against week-1-only shares. And K1 shows the sim
running ~2 more drives per game than real (23.8 vs 21.9; 130 vs 124.5 plays), which is where the punt
excess (8.84 vs 7.90) comes from - not from Q4 pace. Nothing here changes the fingerprint. No re-fit.

## HARD RULES (as 5M) with ONE explicit exception

1. Branch `eng/5n`, worktree `~/mlb-model-5n`, from origin/main after D123. `main` untouched. Cowork verifies.
2. **Exception, this order only:** item 1 MAY edit exactly two existing test functions, named below, because
   the behaviour they assert no longer exists. No other existing test, tolerance, threshold, `MIN_CELL`, `N`
   or filter is edited. New tests in NEW files `test_engine_5n.py`, `test_usage_5n.py`.
3. Nothing is tuned to hit a test. No engine or usage-layer change in this order (items 2 and 3 MEASURE).
4. Never reduce N, subsample, skip a test or kill a run. Measure runtimes and report them.
5. `GIT_OPTIONAL_LOCKS=0` on every git command. Commit AND push each item before the next
   (`git push -u origin eng/5n`). Each item writes its `### DNN` entry (grep for the next free number,
   D124+) in the same commit.
6. A diff is not evidence. Paste execution output; a test that is claimed to fail on the old behaviour is
   shown failing.
7. Zero API credits. Do not touch `bets/`, `nfl/pipeline/`, `ncaaf/`, `shared/`.

## Setup

```
cd ~/mlb-model && GIT_OPTIONAL_LOCKS=0 git pull --no-rebase --no-edit --autostash
GIT_OPTIONAL_LOCKS=0 git worktree add ~/mlb-model-5n -b eng/5n
cd ~/mlb-model-5n
for f in ~/mlb-model/nfl/data/pbp/*.parquet; do [ -e "nfl/data/pbp/$(basename $f)" ] || ln -s "$f" "nfl/data/pbp/$(basename $f)"; done
python3 -c "from nfl.sim.calibration import engine_fingerprint as f; print(f())"   # must print 02fbcab6e6ed042e
```
Anything else: STOP and report.

---

## Item 1 — the two tests assert what the engine does now; the suite count is the whole suite

1a. `nfl/sim/tests/test_engine_5m.py::test_player_off_hash_stable`: replace the hardcoded hash with the
    invariant it was standing in for. The durable null control is "player-ON scores == player-OFF scores at
    the same seed" (already `test_player_on_scores_identical_to_off`). The hash test becomes: the
    player-OFF hash at seed `T4_test`, N=4000, equals the value stored in a committed JSON
    `nfl/sim/tests/fixtures/player_off_hash.json` keyed by `engine_fingerprint()`; if the current
    fingerprint has no entry the test FAILS with the message "record the hash for fingerprint X with
    `python3 nfl/sim/tests/record_player_off_hash.py`" - that recorder is committed code and is the ONLY
    way an entry gets written. Record the entry for `02fbcab6e6ed042e`. Show the test failing with the
    entry removed and passing with it.
1b. `nfl/sim/tests/test_board_5j2.py::test_prekick_line_chosen_for_kicked_game`: rewrite to assert the 5M
    behaviour on the same fixture: a game with `commence_time <= as_of` is ABSENT from the game set, and a
    game with `commence_time > as_of` still gets its last pre-`as_of` snapshot (the part of 5J that still
    holds). Show it failing against the 5L version of `get_lines_from_history` (git show it into a temp
    module) and passing at HEAD.
1c. Run the FULL `nfl/sim/tests` suite once, from the worktree, and report the exact count and every red by
    name. Expected: 2 reds remain (`test_first_downs_by_penalty`, `test_t3_tied_drives_...`), known since
    5I. If any other test is red, investigate it in this item and report - do not label it known.

## Item 2 — share shrinkage re-measured without survivorship, at weeks 1..k, by prior-team status

Script `nfl/sim/run_share_shrinkage_5n.py` (new; 5M's stays as the record of what was measured). Changes:
- Sample: every player with a week-1 share row AND at least one row in weeks 2-8. No games-played filter.
  Weight each player's error by his number of weeks in 2-8 (report unweighted too).
- Predictor at week k (k = 1, 2, 3, 4): s_k = the player's cumulative share over weeks 1..k (team-total
  weighted), p_w = w*s0 + (1-w)*s_k, outcome = share over weeks k+1..8. Same 11-point w grid, discovery
  2021-24, holdout 2025, by position x share type. Report best w and holdout reduction for each k.
- s0 = the prior season's FULL-season share (weeks 1-18), not weeks 2-8. Players without s0: reported as
  their own group with p = s_k (no shrinkage possible) - their share of the 2026 Week 3 board stated.
- Split the holdout by "same team as prior season" vs "changed team".
PRE-REGISTERED, write before looking: (a) WR target holdout reduction at k=1 without the filter is
BELOW 5M's 47.3% but above 15%; (b) the reduction falls with k and is under 10% by k=4 for every
position; (c) changed-team players gain less than same-team. If any fails, say so and tune nothing.
Write `research/nfl_sim/phase5n_share_shrinkage.md` with every table. NO weight applied anywhere.

## Item 3 — where do the extra 2 drives per game come from? (DIAGNOSIS ONLY, no engine change)

Script `nfl/sim/run_drive_diag_5n.py` (new). On the K1 sample (same games and N as `run_k1_table.py`),
compare sim vs real, 2021-24, with the derivation stated for every real number:
- drives per game split by how the drive ended (punt, TD, FG, turnover, downs, end of half/game, safety);
- plays per drive and seconds per play by (quarter, score state) over the WHOLE game, not just Q4;
- seconds of clock consumed per drive by ending type; time of possession per game;
- the number of drives that start in the final 2:00 of each half.
PRE-REGISTERED: the excess is in plays-per-drive being too LOW (drives end faster than real, so more of
them fit) rather than in seconds-per-play; specifically punt-ending drives have fewer plays in the sim
than real. State it, then look. Write `research/nfl_sim/phase5n_drive_diag.md` with the tables and ONE
paragraph naming the single largest contributor. No fix in this order; the fix is 5O with a re-fit.

## Closing

`logs/agent_sessions.md` entry (`git add -f`): RETURNED vs MEANS; runtimes measured; NOT DONE;
UNVERIFIED (at minimum: Cowork's Linux re-run of item 1's suite count).
