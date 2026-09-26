# Phase 5U verification — Cowork, 2026-09-26

Branch `eng/5u` @ `f761963` (5 commits; D152 on main = 1). Verified from the files in Linux worktrees at the
item-0 commit (`1ed1b49`) and the branch head. Every number below was recomputed here unless marked "read".

## Commits and decision records
D153 1ed1b49, D154 9bbeeb5, D155 36f0a13, D156 b4667e0 each carry their decision entry in the same commit;
session log f761963. The fixture is re-recorded for every fingerprint (5a446b7aec4cc2d7, 4cde6c3abe3aa5b3).

## Item 0 (D153) — accepted; neutrality reproduced on Linux
- `_dl_new_drive` resets the end fields to the new drive's start: read in the diff.
- `record_player_off_hash.py` at 1ed1b49 on Linux: `5a446b7aec4cc2d7 -> 31de7e75f17b878b`, the required value
  and the same value the Mac recorded. The item is behaviour-neutral, as ordered.
- The fd counters are split and the tied metric requires plays >= 1 in both places it is computed (the 5a9
  test and `run_metric_noise_5h.compute_tied_expiry`, which K1 calls). Read in the diff.

## Item 1 (D154) — the fixes are right; two of its six verdicts are mislabelled
- `turnover_returns.json`: INT returns now built from the 1,523 non-TD interceptions (quantile mean 9.48;
  raw mean 9.13 — the 101-point table slightly over-weights the tail). `int_p_def_td` still over all 1,675,
  which is what the engine's pick-six branch needs. `int()` -> `round()` on both draws. `yds_fd` removed.
- "'other'-cell LOS 56.3 ± 0.5: HELD (53.4; the pre-reg cited 56.3 but 5T measured 53.5)" is wrong twice:
  5T's other-cell LOS was 56.34 (my 5T verification, from its parquet); 53.4 is the NON-SIX mean, a different
  cell. The null was checked on the wrong population.
- fd_pen 1.25 ± 0.03 FAILED at 1.29 (1.31 in K1): reported plainly. The residual over my 1.25 arithmetic is
  the pen_td award and a slightly higher simulated no-play rate — not investigated, small.

## Item 2 (D155) — the fix is right and works better than D155 says; two verdicts are mis-scored
- `int_ez.parquet` (P(ez | LOS bucket): 60.3% / 15.7% / 4.5% / 0 / 0) and the rebuilt non-ez `int_spot.parquet`
  both REPRODUCE exactly from the committed builders on PBP 2021-24.
- **Defect: `build_int_ez_table` is never called by `build_all`.** A table rebuild would not write
  `int_ez.parquet`, and the engine then falls back SILENTLY (`_int_ez_rate.get(bkt, 0.0)`): no end-zone
  interceptions at all, with air drawn from the non-ez quantiles — worse than 5S, under the same fingerprint
  (the fingerprint hashes source, not tables). Same silent fallback for `int_spot` since 5S. -> 5V item 0.
- `test_engine_5u.py` FAILS on the pre-fix engine (ez share 0.046 vs 0.1215) and passes at head.
- My reproduction on the D144 sample (first 200 K1 games, N=100, 5U engine):
  INT/game 1.619, pick-six 9.15%, non-six ez 10.80% (real 12.15%); other cell LOS 58.00 (real 56.31),
  **air 17.36 (real 17.19), return 9.25 (real 9.54)**, next start 50.28 (real 50.91); non-six next start
  53.48 (real 54.16); **D144-definition post-INT start (all INTs, pick-sixes included) 55.45 (real 56.05)**.
- So D155's "'other'-cell air 16.1 — FAILED" does not reproduce: the other-cell air is 17.36, inside ± 1.0 of
  17.2 — HELD. And "next start within 1.5 of 56.0 — FAILED (53.5)" scored the NON-SIX number against the
  all-INT target; on the pre-registered D144 definition it is 55.45 — HELD.
- What is left: the sim's non-six interceptions happen 2.3 yards deeper in the offence's own territory than
  real ones (LOS 53.99 vs 51.73), which is why its end-zone share is 10.8% rather than 12.2% even though the
  per-bucket rates are real. That is a pass-selection/field-position effect upstream of the interception, not
  the spot. The post-INT chain itself is now right within ~0.6 yd in every cell.

## Item 3 (D156) — K1 reproduced; plays and drives unmoved
K1 from `phase5u_k1_after_rows.parquet`: pts/team 22.036 (actual 22.386), plays 130.90, drives 23.74, punts
8.985, go_rate 0.2072 (PASS by 0.0008 — knife-edge again), fd_pen 1.312. Inside-40 1.469 and TD 1-3-play share
0.1433 reproduced on the D144 sample; both FAILED their targets narrowly and were reported so. On plays >= 1
drives (the definition item 0 adopted) inside-40 is 1.443, but the target was registered on all drives: it
stays FAILED. TD drives/game 4.72 (real 4.73). The tied row rose 0.0959 -> 0.1034 even with the plays >= 1
filter; D156's "expected ~7%" did not hold and its note about which function uses the filter is confused (both
do). Points moved down again (22.90 at 5R, 22.23 at 5S, 22.04 now; actual 22.39): the INT fixes took ~0.9
points a team out, plays did not move.

## Suite and cross-machine
Full suite on Linux at f761963 (40.4 min): **2 failed, 217 passed** — `test_first_downs_by_penalty` and
`test_t3_tied_drives_that_reach_range_get_the_kick_off`. Matches D156; exit non-zero, no wrapper.

Linux Week 2 board (`run_week.py --week 2 --as-of 2026-09-20T15:30:00Z`, 20.2 min, 15/15 converged) vs
`phase5u_boards/picks_log_mac.parquet`: **1,339/1,339 legs bit-identical (sim_p, cal_p; team_volume 30/30).** HELD at 100%.

## The plays target (found while reading K1)
The K1 `plays/game actual=124.5` is typed into four files and equals PBP pass + run per game exactly (72.01 +
52.49, 2021-24 REG). The sim's `n_plays` also counts kneels (engine ~1591) and spikes (~1675): 1.52 + 0.24 a
game in PBP. Like-for-like the target is ~126.3 and the gap ~+4.6, not +6.4. About 1.8 plays of the famous
excess is a counting mismatch. -> 5V item 1.

## Verdict
5U is accepted for merge. The interception chain is now right to within about half a yard in every cell, and
D155 under-reports its own success (two HELDs scored as FAILs). Carry: the ez table is not wired into
`build_all` and both INT tables fall back silently; the null in D154 was checked on the wrong cell. The
+6.4 plays / +1.8 drives per game gap — the oldest open defect, and the reason the board's QB pass-attempt
gap is still +3.5 — is untouched by five phases of field-position work. 5V goes after the clock.
