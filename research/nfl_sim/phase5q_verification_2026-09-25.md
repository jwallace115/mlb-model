# Phase 5Q verification (Cowork, 2026-09-25T03:39Z)

Branch `eng/5q` @ `5a7cac6` (D135-D136 + log), base `4c4985b` (main after D134). Diagnosis only; fingerprint
`02fbcab6e6ed042e`. Both items committed their parquet. `git merge-tree` vs main: clean.

## Verdict: MERGE. Item 1 is right. Item 2's MEASUREMENT is right and its MECHANISM is wrong - and chasing the
right mechanism found the largest defect since the Beta draw: **week-1 team tendencies are a hardcoded
28.0-second pace with no prior-season carry-forward, and pace is never shrunk.** That is why the sim runs
~140 plays a game in weeks 1-2 (real ~125), why the 2026 boards over-project receptions by 7-8 per team,
and it is a fifth of K1's plays/drives/punts excess.

## Item 1 (D135) - drive starts by preceding event. Accepted as reported (parquet committed; the
decomposition matches 5P's totals: turnovers +0.52 of the +0.64 inside-40 excess, downs +0.23, kickoffs -0.06).
Return-yardage tables match PBP; the sim's INT-started drives begin 39.9 yards from the end zone against
52.7 real, so sim interceptions happen ~13 yards deeper downfield than real ones (or the spot ignores where
the ball was caught). Frequency is also high (+0.41 turnovers, +0.46 downs per game). Two separate engine
questions - the spot of an interception, and the turnover/downs rates - both queued (5R item 3).

## Item 2 (D136) - reception volume: measurement reproduced, mechanism refuted
- Reproduced from `phase5q_reception_share.parquet`: sim team receptions 28.3 vs 20.5 real on 2026 wk1-2
  (64 team-games), 25.0 vs 21.0 on the 2024 sample (200); top-6 share sim 0.77 vs real 0.81-0.83.
- **D136's "phantom receivers generate ~6 excess receptions" is wrong.** Cowork ran `simulate_game` with the
  player layer on PIT-ATL and LAC-ARI (2026 wk1), GB-ATL (wk3) and KC-BUF, DAL-PHI (2024): in every game the
  players' summed receptions EQUAL the QB's completions to the decimal (PIT 27.7 = 27.7; ATL 28.2 = 28.2).
  The player layer divides team completions; it cannot create any. Phantom players only lower the top-6
  SHARE (a real but secondary effect: 13-15 active receivers vs ~7 who catch a pass).
- **The excess is team pass VOLUME.** Raw sim, per team-game: 2026 games 39-43 pass attempts and 26-28
  completions against real 2026 33.9 / 20.5; 2024 games 37.6-39.6 / 22.7-23.2 against real 35.2 / 21.4.
- **The cause is in `nfl/sim/ratings.py::build_tendencies` (lines 439-461).** With no prior week in the
  season, a team-week gets `proe 0.0, pace_sec 28.0, n_plays 0` - a hardcoded 28-second pace, no
  prior-season carry-forward; from week 2 on, pace is the RAW mean of the games played (no shrinkage; PROE is
  shrunk toward 0). Full-season pace is 34-35 s (2021-25 tendency means 34.06 / 34.46 / 34.15 / 34.69 /
  35.14); 2026's rows average 30.7 on n = 28 plays. A 28-second pace is ~20% more plays. Evidence in K1
  (`phase5l_k1_after_rows.parquet`): sim plays/game 139.7 in weeks 1-2, 126.9-129.8 in weeks 3+ (real
  124.5 all season); drives 25.4 vs 23.2-23.8; punts 9.4 vs 8.6-8.9.
- Consequences: (1) every 2026 board so far (weeks 1-3) ran on a 28-s / one-game pace, which the anchoring
  to the market total can only mask by pushing EPA down - more completions of shorter yards - which is
  exactly the over-projected receptions the board shows; (2) the 2021-24 fit and calibration were done with
  weeks 1-2 at ~140 plays, so `fit_5m`'s maps absorbed a defect that no longer belongs in them after the
  fix; (3) about a fifth of K1's +5.8 plays / +2 drives / +1 punt excess is weeks 1-2. `start_yl100 = 75.0`
  all over again (CLAUDE.md "Measure, do not assume").

## Checks
Provenance: item 1 reads PBP vs the drive log; item 2's real side is PBP; Cowork's runs use the committed
engine and ratings. Leakage: nothing tuned. Identity: the raw `simulate_game` is what the board anchors;
the board's own post-anchoring pass volume is not logged - 5R logs it. Economics: none. Aggregates: by
preceding event; by sample; by week bucket (the one that exposed this). Sim gates nothing (N54).

## NOT done / UNVERIFIED
- Post-anchoring pass volume on the Week 2/3 boards (5R item 1 logs it).
- Whether `tendencies_situational_weekly` has the same week-1 default (5R item 1 checks).
