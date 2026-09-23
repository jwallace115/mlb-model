# Phase 5N verification (Cowork, 2026-09-22T22:19Z)

Branch `eng/5n` @ `1497e2e` (D124-D126 + log), base `d4c39bb` (main after D123). No engine change;
fingerprint `02fbcab6e6ed042e` unchanged. `git merge-tree` vs main: clean.

## Verdict: MERGE. Item 1 is right. Item 2's finding survives, but its holdout method is leaky and the
committed script must not be cited until fixed. Item 3 is a restatement of K1, not the diagnosis ordered.

## Item 1 (D124) - the two tests
- `test_player_off_hash_stable`: reads the hash from `fixtures/player_off_hash.json` keyed by fingerprint,
  written only by the committed recorder. Entry `02fbcab6e6ed042e -> 10425a6562817ec2`. That hash is what
  Cowork computed independently on Linux yesterday, so the player-OFF play stream is bit-identical across
  machines too. With the fixture removed the test FAILS (shown here); with it, PASSES.
- `test_prekick_line_chosen_for_kicked_game`: asserts PIT@NE absent and IND@KC still pre-kick. Passes.
- Full suite 207/209 on the Mac; the two reds are the 5I pair. Cowork ran the 5m/5j2 files (6 pass).

## Item 2 (D125) - shrinkage without survivorship: FINDING HOLDS, METHOD DOES NOT
- **Leak:** `run_share_shrinkage_5n.py` runs the 11-point grid INSIDE every season, including 2025, and
  reports 2025's own best-w reduction as the "holdout". That is the best of 11 weights chosen on the
  holdout - discovery-validation contamination, exactly the class CLAUDE.md names. The discovery rows
  average per-season optimal w's instead of picking one w on pooled 2021-24. The order said: pick on
  2021-24, apply once to 2025.
- **Recomputed honestly by Cowork** (w chosen on pooled 2021-24, applied once to 2025, same sample and
  weighting, from the script's own data builders):

| pos | share | k | w (2021-24) | n 2025 | reduction | same team n / % | changed team n / % |
|---|---|---|---|---|---|---|---|
| WR | target | 1 | 0.8 | 104 | 36.8% | 78 / 41.1 | 26 / 17.0 |
| WR | target | 2 | 0.6 | 118 | 14.1% | 86 / 16.9 | 32 / 6.2 |
| WR | target | 3 | 0.5 | 122 | 12.4% | 88 / 15.3 | 34 / 3.6 |
| WR | target | 4 | 0.4 | 124 | 6.3% | 89 / 4.3 | 35 / 12.0 |
| TE | target | 1 | 0.8 | 56 | 30.8% | 48 / 34.1 | 8 / 12.6 |
| TE | target | 2 | 0.6 | 62 | 25.0% | 54 / 25.6 | 8 / 19.9 |
| TE | target | 3 | 0.5 | 65 | 17.4% | 56 / 14.4 | 9 / 40.2 |
| TE | target | 4 | 0.5 | 65 | 18.0% | 56 / 15.8 | 9 / 36.1 |
| RB | target | 1 | 0.8 | 52 | 36.2% | 41 / 42.5 | 11 / -29.5 |
| RB | target | 2 | 0.7 | 56 | 16.4% | 46 / 19.8 | 10 / -8.6 |
| RB | target | 3 | 0.5 | 54 | 30.0% | 44 / 33.3 | 10 / 8.0 |
| RB | target | 4 | 0.6 | 58 | 17.2% | 48 / 15.4 | 10 / 27.7 |
| RB | carry | 1 | 0.5 | 61 | 16.0% | 52 / 16.9 | 9 / 10.5 |
| RB | carry | 2 | 0.3 | 61 | 9.1% | 52 / 10.3 | 9 / 1.9 |
| RB | carry | 3 | 0.3 | 63 | 2.3% | 54 / 4.9 | 9 / -7.4 |
| RB | carry | 4 | 0.3 | 62 | 6.1% | 53 / 6.1 | 9 / 5.7 |

  The honest numbers sit within a point of the leaky ones because the MAE curve is flat near its
  minimum - the conclusion survives, the method was still wrong. Pre-registered (a) HELD (36.8 < 47.3,
  > 15); (b) PARTIALLY HELD as D125 says (WR and RB carry fall under 10% by k=4; TE and RB target do
  not, on n = 52-65); (c) - which D125 left UNVERIFIED - **HELD**: players who changed teams gain far
  less (WR 17% vs 41% at k=1; RB target negative). Small n on the changed-team side (8-35).
- What this means: a prior-season blend is worth applying for players on the SAME team, weighted
  0.8 at week 1 falling to ~0.4-0.5 by week 4, for target shares; for carries only at week 1-2 and
  lightly; for players who changed teams, not at all on this evidence. 19% of the Week 3 board has no
  prior season and is unaffected either way.

## Item 3 (D126) - drives: NOT the diagnosis ordered
- The script runs in 1 s because it simulates nothing: the "sim" column is K1's per-game aggregate
  (`plays`, `drives`, `ev_punts`, `ev_fg_att`), read from the 5L rows file (the 5M rows file it names
  was never committed). The real side is decomposed by drive ending; the sim side cannot be, because
  the sim's K1 rows carry no TD / turnover / downs / end-of-half counters. So the pre-registered claim
  ("punt drives have fewer plays in the sim") was untestable and "PARTIALLY CORRECT" overstates it.
- What CAN be read from K1 vs D126's real table: punts +1.0 per game (8.84 vs 7.82) and FG attempts
  about +0.7 (4.00 vs 3.34 by drive ending; K1's own 3.92 counts attempts differently - reconcile in
  5O), with TDs implied by points about even (~4.8). So roughly: half the extra drives end in punts,
  a third in field-goal attempts. Plays per drive 5.47 vs 5.71 says the sim's drives are shorter.
- 5O adds the missing counters to the sim's per-game output (a fingerprint change with NO behaviour
  change - null control: the Week 2 board bit-identical before and after) and then does the
  decomposition properly.

## Checks
Provenance: 1b clean for item 2 (week-1..k shares and the prior season are both known at week k+1).
Leakage: item 2's committed script leaks (above); Cowork's recomputation does not. Identity: nothing
live changed. Economics: none. Aggregates: by position, share, k and team status. Sim gates nothing.

## NOT done / UNVERIFIED
- The committed 5N script still reports leaky holdout numbers; 5O item 1 replaces it.
- Usage rebuild bit-identity (carried since 5J).

## Addendum (identity check, Cowork): the usage layer ALREADY shrinks toward the prior season
`nfl/sim/usage.py` (docstring lines 10-22; `params_v1.json` `k_share = 20`): each share is
`(n_eff*obs + k_share*prior)/(n_eff + k_share)` with `prior` = the player's own s-1 share (>= 50 team
opportunities) else a league depth-group mean, then a further `prior_weight` blend. At week 1 a team has
~35 targets, so the live layer already puts 20/55 = 0.36 on the prior. Both 5M's and 5N's scripts compared
the blend against RAW week-1 shares - a baseline the sim does not use. The honest gain vs the LIVE object
is therefore smaller than 36.8% and has not been measured. What the honest table does say is that the
best weight is ~0.8 at week 1 falling to ~0.4-0.5 by week 4 for targets - which is what a single
`k_share` of about 120-140 team opportunities produces (140/(35+140) = 0.80; 140/(140+140) = 0.50),
against the current 20. So the lever is `k_share`, measured with the layer's own formula - 5O item 4.
