# Phase 5R verification (Cowork, 2026-09-25T11:58Z)

Branch `eng/5r` @ `43b380f` (D138-D141 + log), base `ea174f6` (main after D137). Engine fingerprint
`02fbcab6e6ed042e` -> `5ee4b1009301783d`, usage `3638769c89030de0`, on `fit_5r`. `git merge-tree` vs main: clean.

## Verdict: MERGE. The tendency fix is the right design and is measured; its pre-registered board and K1
targets mostly FAILED and were reported as failed. One side effect Claude Code did not see explains why the
overall K1 plays number went UP; item 4 found a one-line engine bug that is the next fix.

## Item 1 (D138) - accepted. 194 default team-weeks (32 x 6 seasons + 2 in 2026 wk2); K1 weeks 1-2 +15.7
plays vs +5.1 later; anchored Week 2 board +6.1 pass attempts per team over the book's QB lines; the
team_volume log is behaviour-neutral (1,353/1,353 bit-identical). Cowork had derived the same numbers.

## Item 2 (D139) - the fix, read line by line
- Week 1 now carries the team's own prior-season pace and PROE (league mean of the prior season if none;
  34.0 / 0.0 only when there is no prior season in the data). Pace is shrunk `(n*obs + k*prior)/(n+k)`
  with n = valid play-to-play diffs; PROE's shrink target moves from 0 to the team's prior-season PROE.
- k measured through the builder on 2021-24, holdout 2025 (`phase5r_tendency_k_results.parquet`,
  re-read here): pace MAE 2.405/2.386/2.374/2.373/2.384/2.401 at k = 25..800 (discovery); PROE
  5.98/5.93/5.89/5.88/5.92/6.01. Both minima at 200 - honestly, though the pace curve is flat between 100
  and 200 (0.0005) and the holdout prefers 100 (2.320 vs 2.333). Not a leak; a flat curve. Week-1 pace MAE
  falls 69% on the holdout. `test_ratings_5r.py` 2/2 pass here.
- Provenance: the prior is the prior season's full-season value, known before week 1 (1b clean); the live
  builder is the same function (identity). Leakage: k picked on 2021-24, applied once to 2025.

## Item 3 (D140) - what the re-fit moved, and the side effect
- Weeks 1-2 K1 plays 139.7 -> 129.5 HELD; pts/team 22.90 and the four K1 nulls HELD; board pass attempts
  +6.1 -> +3.7 and SD(raw sim_p - q) 0.149 -> 0.134 FAILED their targets (< 2, < 0.12) and were reported as
  failed. Overall K1 plays 130.3 -> 131.1, drives 23.8 -> 23.9, punts 8.84 -> 8.89: FAILED, direction wrong.
- **Why the overall number rose (not in D140):** by week bucket, 5M -> 5R plays are 139.7 -> 129.5 (wks 1-2)
  but 126.9 -> 131.4 (3-4), 128.6 -> 131.3 (5-8), 129.4 -> 131.2 (9-12), 129.8 -> 131.2 (13+). The engine
  uses pace as a RATIO, team_pace / lg_pace (engine.py:705, 1602, 2450, 2715), where lg_pace is the mean of
  the prior-season and season-to-date tendency rows. Before 5R that mean included 32 rows of 28.0 per season
  and one-game raw values, which pulled it down; after 5R those rows sit at ~34.5, lg_pace rises, every
  team's ratio falls ~2%, and the whole season runs ~2% more plays. The ABSOLUTE number of plays comes from
  the clock-runoff tables, not from pace; pace only redistributes between teams. So the tendency fix was
  never going to move the season-long +5 plays - that residual is the engine's short drives (5P/5Q: short
  fields from the INT spot, item 4), which is the right next fix. Recorded so the next K1 is read correctly.
- Suite 206/211 on the Mac. Reds: fd_pen, tied_drives (5I); like_for_like_go (K1 0.0102 vs 0.0100, red
  since 5L - relabelled "pre-existing" without investigation, noted); `player_off_hash` re-recorded for the
  new fingerprint (passes here); `test_score_vs_book` universe 146 -> 182 - that test pins a row COUNT that
  legitimately moves with the calibration maps: rewrite to assert structure (5S item 0). Cross-machine
  bit-identity of the 5R boards NOT checked: the ratings tables are gitignored and Cowork's clone holds
  the old ones. UNVERIFIED.

## Item 4 (D141) - the interception spot: a real bug, clean diagnosis
engine.py:2331-2332 places an interception at the line of scrimmage: `yl_new = 100 - (yl_LOS + return)`.
The ball is caught `air_yards` downfield, so the defence should take over at `100 - (yl_LOS - air_yards +
return)`. Expected error = mean air yards on picks = 15.5; observed sim post-INT start 39.9 vs real 56.0 =
-16.2. INT rate itself is close (1.62 vs 1.54 per game). This is the +0.52 short fields per game from D135,
the shorter TD drives from D132, and a good part of the punt/drive excess. 5S item 1 fixes it (one formula,
with the sim's own air-yards draw) and re-fits once.

## Checks
Provenance clean (prior season known at week 1; k on 2021-24 only). Identity: the tables the board reads
are the ones the builder writes; the board's post-anchoring volume is now logged. Economics: none.
Aggregates: by week bucket - the breakdown that exposed the ratio side effect. Sim gates nothing (N54).
