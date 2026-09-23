# Phase 5O work order — honest shrinkage script, drive-ending counters, the drive decomposition, k_share measured with the live formula

Date: 2026-09-22 (UTC). Repo: jwallace115/mlb-model. Scope: `nfl/sim/` and `research/nfl_sim/` only.
Read first: `research/nfl_sim/phase5n_verification_2026-09-22.md` INCLUDING its addendum, D124-D127.
Prerequisite on main: `grep -c "^### D127" research/nfl_sim/NFL_SIM_DECISION_v1.md` = 1. If 0, STOP and report.

## Why this order exists

(1) `run_share_shrinkage_5n.py` picks its weight inside the holdout season; its holdout numbers are not
holdout numbers. (2) Both shrinkage scripts measured against raw week-1 shares, which the live usage layer
does not use - it already shrinks toward the prior season with `k_share = 20` team opportunities. The
honest weights (~0.8 at week 1 -> ~0.45 at week 4) correspond to a `k_share` near 120-140. That has to be
measured with the layer's OWN formula (identity), not a stand-in. (3) D126 could not decompose the sim's
drives because the sim emits no TD / turnover / downs / end-of-half counters.
Items 1-3 change no behaviour. Item 4 changes the usage layer and needs ONE re-fit.

## HARD RULES (as 5N)

1. Branch `eng/5o`, worktree `~/mlb-model-5o`, from origin/main after D127. `main` untouched. Cowork verifies.
2. No existing test, tolerance, threshold, `MIN_CELL`, `N` or filter is edited. New tests in NEW files
   `test_engine_5o.py`, `test_usage_5o.py`. `k_share` is a PARAMETER and may change only in item 4, only
   to the value item 4's discovery picks, recorded in `### DNN` with the table that picked it.
3. Nothing is tuned to hit a test. Never reduce N, subsample, skip a test or kill a run. Measure runtimes.
4. `GIT_OPTIONAL_LOCKS=0` on every git command. Commit AND push each item before the next
   (`git push -u origin eng/5o`). Each item writes its `### DNN` entry (grep for the next free number,
   D128+) in the same commit.
5. A diff is not evidence. Paste execution output; every null control is shown.
6. Zero API credits. Do not touch `bets/`, `nfl/pipeline/`, `ncaaf/`, `shared/`.

## Setup

```
cd ~/mlb-model && GIT_OPTIONAL_LOCKS=0 git pull --no-rebase --no-edit --autostash
GIT_OPTIONAL_LOCKS=0 git worktree add ~/mlb-model-5o -b eng/5o
cd ~/mlb-model-5o
for f in ~/mlb-model/nfl/data/pbp/*.parquet; do [ -e "nfl/data/pbp/$(basename $f)" ] || ln -s "$f" "nfl/data/pbp/$(basename $f)"; done
python3 -c "from nfl.sim.calibration import engine_fingerprint as f; print(f())"   # must print 02fbcab6e6ed042e
```
Anything else: STOP and report.

---

## Item 1 — the shrinkage script picks w on discovery only, and says so

Rewrite `run_share_shrinkage_5n.py` in place (it is a measurement script, not a test): for each
(position, share, k) pick ONE w on POOLED 2021-24, apply it ONCE to 2025; report discovery MAE at that w,
holdout MAE at that w vs w=0, and the same-team / changed-team split. Print, next to each holdout row,
the leaky number the old version produced, so the record shows both. Regenerate
`research/nfl_sim/phase5n_share_shrinkage.md` from the new output and mark the old table superseded.
NULL: Cowork's table in the verification note is the target - every honest cell must match it to 0.1
point (same data, same weighting). If any cell differs, find out why before committing.

## Item 2 — the sim emits drive-ending counters (fingerprint changes, behaviour must not)

In `simulate_game`'s per-sim output add `ev_td_drives`, `ev_turnovers` (INT + lost fumble on
offence), `ev_downs`, `ev_eoh` (drives ended by end of half or game), `ev_safeties`, each counted where
the existing `ev_punts` / `ev_fg_att` are counted, so that
`ev_punts + ev_fg_att + ev_td_drives + ev_turnovers + ev_downs + ev_eoh + ev_safeties == drives`
holds per sim - write that identity as a test on 3 games x 2 seeds. `run_k1_table.py` carries the new
columns into its rows parquet and prints their per-game means. Record the new fingerprint.
NULL CONTROL (the whole point): the Week 2 board `--week 2 --as-of 2026-09-20T15:30:00Z` re-run on the
new engine is BIT-IDENTICAL on `sim_p` and `cal_p` to `research/nfl_sim/phase5m_boards/picks_log_mac.parquet`
(1,353/1,353). If a single leg differs the counters changed behaviour: STOP and report. Because the
fingerprint changed, the calibration stamp will go red and the board will be SUPPRESSED - for this null
control run the board with the suppression bypassed ONLY for the comparison (state exactly how) and do
NOT re-stamp; item 4's re-fit re-stamps.

## Item 3 — the drive decomposition D126 owed (DIAGNOSIS ONLY)

`run_drive_diag_5o.py` (new): `run_k1_table.py`'s sample and N on the item-2 engine, sim vs real per game
by ending type (punt, TD, FG attempt, turnover, downs, end-of-half, safety), plays per drive by ending
(sim: add a per-drive play count to the same output if needed, in item 2), and seconds consumed per
drive by ending. Real side from PBP 2021-24 with the derivation stated (D126's real numbers are the
reference; if they change, say why). PRE-REGISTERED, write before looking: punt-ending drives are the
largest excess (+0.9 to +1.1 per game) and FG-attempt drives the second (+0.4 to +0.8); TD drives
within 0.3 of real; sim punt drives have FEWER plays than real punt drives (< 4.18). Write
`research/nfl_sim/phase5o_drive_diag.md`. Name the single largest contributor. No fix here.

## Item 4 — `k_share` measured with the live formula, applied once, ONE re-fit (Jeff's call is recorded in D127)

`run_kshare_5o.py` (new): call the usage layer's OWN share builder (`build_player_usage` path, no
re-implementation) for `k_share` in {20, 40, 80, 120, 160, 240}, seasons 2021-24 (discovery) and 2025
(holdout), every week 2..9. Score each week's projected target/carry share against the realised share
that week, MAE weighted by team opportunities, by position. Pick the k_share on POOLED 2021-24; report
the 2025 holdout at that k vs k=20. PRE-REGISTERED: the discovery pick is >= 80; the 2025 holdout MAE at
the pick is below k=20's by 8-20% for WR/TE/RB targets at weeks 2-3 and by < 5% by week 8; RB carries
gain < 8% at any week. If it does not hold, say so, tune nothing, and STOP before applying.
If it holds: set `k_share` in `params_v1.json` to the pick (one number, all positions - no per-position
values in this order), regenerate the usage tables, report `usage_fingerprint()`, re-fit `fit_5o` (N per
D51), `run_cal_maps.py`, re-stamp, K1 (`phase5o_k1_after.txt` - engine unchanged from item 2, so K1
must equal item 2's table to 4dp: NULL), K4, full suite (name every red), Week 2 board
`--as-of 2026-09-20T15:30:00Z` saved to `research/nfl_sim/phase5o_boards/picks_log_mac.parquet`.
PRE-REGISTERED on the Week 2 board: SD(raw sim_p - q_over) on the 1614Z receptions candidates falls
from 0.149 to below 0.13; the coverage of 5J's P4 (rush-att lines priced) is unchanged.

## Closing

`logs/agent_sessions.md` entry (`git add -f`): RETURNED vs MEANS; runtimes; NOT DONE; UNVERIFIED
(at minimum: Cowork's Linux bit-identity check of the item-2 and item-4 boards).
