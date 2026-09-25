# Phase 5S verification — Cowork, 2026-09-25T16:41Z

Branch `eng/5s` @ `e2cc5bb` (5 commits on top of main; D142 on main = 1, so the branch's gate ran
against the merged 5R). Verified from the files in a Linux worktree, not from the report. Every
number below was recomputed here unless marked "read".

## Commits and decision records
Four item commits each carry their `### D14x` entry in `NFL_SIM_DECISION_v1.md` in the same commit
(D143 e018972, D144 afc8565, D145 563bcfb, D146 33d566b) plus the session log (e2cc5bb). Nothing
lives only in a commit message. `int_spot.parquet` is TRACKED (4,142 bytes) — the engine falls back
silently to LOS spotting if it is absent (`if _int_spot_q:`), so a clone without the table would run
the 5R behaviour under the 5S fingerprint; the fingerprint hashes source, not tables. Noted, not a
defect today because the table ships in the same commit as the code.

## Item 0 (D143) — test rewrite and the go_rate reading
- `test_score_vs_book.py`: 6 tests, all pass here. Structural (columns, no placed rows, size >= 50,
  injected placed rows do not enter, bootstrap finite). One docstring is wrong: `test_universe_fails_
  on_broken_input` says "removing cal_p" and the body drops receptions instead. Cosmetic.
- D143's reading of the two go-rate rows is REPRODUCED from `phase5s_k1_after_rows.parquet`:
  like_for_like_go = go / (go + punts + 4th-down FG) = 0.2070; go_rate = go / (go + punts + ALL FG) =
  0.2038; real 4th-down rate 0.1980. Both compare against the same 4th-down-only actual, so `go_rate`
  is the mis-denominated one. Queue item is right; nothing changed.

## Item 1 (D144) — INT spotted at the catch point
- Diff read line by line. Draw `u_int_air` added to the play-loop stream (so every 5S sim differs from
  5R everywhere downstream of the first INT — expected, and why fingerprints and the hash fixture
  moved). Bucket by LOS (5 buckets), 101-point quantile lookup, `catch = yl - air`, end zone (catch
  <= 0) -> new offence at 80, else `100 - (catch + ret)` clipped 1..99. Pick-six branch unchanged.
- Table: 1,675 INTs 2021-24 REG, 0 missing air yards, n by bucket 214/287/475/551/148 (sum 1,675),
  medians 8/15/16/14/17. Builder `build_int_spot_table` is committed code, wired into `build_all`.
  Negative air yards clipped to 0 (screens): fine.
- **Real-side check of the formula (mine, PBP 2021-24):** real INTs decompose as pick-six 9.1% (next
  drive after the kickoff starts 73.7), end-zone catch 11.0% (next start 79.9 — 52% exact
  touchbacks, the rest returned out ~6 yds; the engine's flat 80 matches the mean), other 79.9%
  (next start 50.9; `100 - catch - ret` gives 51.3). Weighted: 56.2 vs D141's 56.0. The formula is
  right stage by stage on real data.
- **Test can fail:** `test_engine_5s.py` on the 5R engine (main's `engine.py` swapped in) FAILS with
  41.6 < 52; on 5S passes. Docstring of `test_int_count_unchanged` says "within 0.05", the assert
  uses 0.3 — the docstring is wrong, the tolerance is loose but the check is real.
- **D144's 200-game numbers REPRODUCED EXACTLY** (first 200 K1 games by game_id = 2021 wks 1-14,
  N=100, drive_log, 356 s on Linux): post-INT start 52.68 (n=32,715), inside-40 starts/game 1.556,
  TD 1-3-play share 0.1518, INT/game 1.637. Same games on the 5R engine: 39.90 / 1.872 / 0.1777 /
  1.624 (D144 wrote 1.86 / 0.180 for the "before" — read from D141's run, close enough).
  Extra: TD drives/game 4.95 -> 4.78 (real 4.73), drives/game 23.63 -> 23.47.
- Pre-registrations 1 and 4 HELD, 2 and 3 FAILED and were reported failed. Nothing tuned.
- **The 3.3-yard residual (52.7 vs 56.0) is real and is NOT the pick-six asymmetry** I suspected:
  the drive log labels a pick-six drive `turnover_int` too (`_dl_result` is set before the branch
  and `_handle_td` does not relabel), so both sides include them. Where it sits cannot be read from
  the current drive log because `_dl_end_yl` is NOT written on the INT play: for a first-play INT
  (14.7% of sim INTs in `phase5r_int_spot.parquet`) `end_yardline` is stale (min 0.0, mean 39.0
  vs 49.7 for the rest). D141's "sim LOS" is therefore contaminated. The chain has to be logged at
  the play (LOS, air, catch, EZ flag, ret, six) to place the residual. -> 5T item 1.

## Item 2 (D145) — fit_5s, K1, board
- K1 header reads `afc856534-dirty`: the fit ran at the D144 commit with the regenerated
  `calibration_v1.json` uncommitted — normal for a fit, and the engine source hashed to the committed
  fingerprint. K1 table REPRODUCED from rows: plays 130.93, drives 23.78, punts 8.96, pts/team 22.23,
  fd_pen 1.409, lfl go 0.2070, go_rate 0.2038.
- By week bucket, 5R -> 5S plays: 129.5->129.4 (wks 1-2), 131.4->131.2 (3-6), 131.2->131.1 (7-12),
  131.3->131.2 (13+). Pts/team fell 0.66 in EVERY bucket and every season (2021 23.00->22.30, 2022
  22.71->22.08, 2023 22.03->21.36, 2024 23.85->23.20). No regime hiding.
- pts/team null (within 0.5 of 22.90) FAILED at 22.23 and was reported failed. Two things D145 does
  not say: (a) the move is TOWARD reality — actual is 22.39, 5R was +0.51 over, 5S is -0.15 under;
  (b) the size is what the mechanism predicts: 1.64 INT/game x ~13 yards of lost field position x
  ~0.065 pts/yard ~ 1.4 pts/game = 0.7/team.
- D145's explanation for the unchanged volume — "the ANCHORING constrains game-level totals" — is
  contradicted by its own table: points moved 1.3/game while plays did not. The anchor is soft. The
  honest reading is simpler: field position does not change the play count; the clock does.
- like_for_like_go 0.2083 -> 0.2070, i.e. FAIL -> PASS by 0.0010 against a 0.0100 tolerance. A
  knife-edge pass, not a resolution; D145 should not call it "resolved".
- "TD drives/game within 0.15 of 4.73 — need to check from rows": the rows have no TD-drive column, so
  it could not be checked from rows. From my 200-game drive run: 4.78. HELD on that sample.
- Board: SD(sim_p - book_implied) on the 191 two-sided Week 2 legs 0.1376 (5R) -> 0.1379 (5S); D140/
  D145's de-vigged recipe gives 0.134 -> 0.135 — same +0.0003. Pass attempts vs the 26 starting-QB
  lines in `nfl_prop_candidates_20260920T1614Z.parquet`: +3.68 -> +3.57 (reported +3.7 -> +3.6).
  Team sim pass att 34.79 -> 34.68. As stated: no target, direction flat.
- Suite on Linux at e2cc5bb, clean worktree, 49.7 min: **2 failed, 213 passed** — `test_first_downs_by_
  penalty` (5a4) and `test_t3_tied_drives_that_reach_range_get_the_kick_off` (5a9). Matches D145
  exactly; no wrapper, exit non-zero. `like_for_like_go` and `player_off_hash` green.

## Item 3 (D146) — reproducibility
- Cloud fingerprints at the worktree: engine `06caa0cbb12bbe6e`, usage `3638769c89030de0` (the copied
  ratings tables). `ratings.py --check` rebuild on Linux (2-core cloud, ~40 min, 3.7 GB RSS): prints `3638769c89030de0`;
  the rebuilt `tendencies_weekly` (3,616 x 8) and `tendencies_situational_weekly` (177,283 x 6) are
  VALUE-IDENTICAL to the committed tables (max |diff| 0.0 on every numeric column, all string columns
  equal); the parquet bytes differ (writer metadata), which is why the fingerprint hashes values, not
  files. Cross-machine usage reproducibility HELD. PBP sha256[:8] printed here match
  D146's list (2025 cc0dd69d, 2026 511a47d0, ...).

## Cross-machine board identity (unverified since 5M; 5R's was never run)
Linux Week 2 board at e2cc5bb (`run_week.py --week 2 --as-of 2026-09-20T15:30:00Z`, 24.8 min, 15/15
converged, 1,333 legs) vs `phase5s_boards/picks_log_mac.parquet`: **1,333/1,333 legs bit-identical on
sim_p and cal_p (max diff 0.0)**; `team_volume` 30/30 rows identical on all five columns. HELD at 100%.

## Standing reds, read once instead of relabelled
- `tied_expiry_broad` 0.0959 vs 0/56 real (D94 definition, derivation in `derive_engine_targets.py::
  derive_tied_drive_expiry_matched`): a tied Q4 drive that reaches the 35 with <= 300 s left expires
  without a kick 9.6% of the time in the sim and never in four real seasons. Red since 5I, never
  diagnosed. -> 5T item 2.
- `fd_pen/team` 1.409 vs 1.728 (tol 0.30): the sim awards 0.32 fewer first downs by penalty per team.
  Red since 5I, never diagnosed. -> 5T item 3.

## Verdict
5S is accepted for merge. D143-D146 are what the files say, the headline numbers reproduce exactly,
the tests fail on the old engine, and every failed pre-registration was reported failed. Corrections
to carry: the anchoring explanation in D145 is wrong; the like_for_like_go "PASS" is by 0.001; the
3.3-yard INT residual is unplaced because the drive log does not record the INT play's LOS.
