# Phase 5P Item 2 — What is the sim-vs-book gap made of?

Date: 2026-09-25. Engine fingerprint: `02fbcab6e6ed042e` (unchanged).
Zero API credits. Inputs: picks_log_mac.parquet, board candidates, PBP 2026, player_usage_weekly.

## Pre-registered predictions (written before looking)

1. The gap is mostly a MEAN problem — replacing the sim's mean with the book's line removes
   more than half of the SD.
2. Players with no 2025 season and players on a new team carry a larger mean error than the
   rest (>= 0.5 receptions larger).
3. The sim's team pass-attempt error explains less than a third of the player mean error.

## Derivation

**Matched rows:** 131 players with two-way receptions lines in the board AND rung probabilities
in the picks_log, matched by player_name. The board provides the book's line (its median) and
de-vigged `q_over` = P(X >= ceil(line + 0.5)). The picks_log provides `sim_p` = P(X >= k)
at k = 2,3,...,7 (filtered to [0.05, 0.95]).

**Sim mean:** E[X] = sum_{k=1}^{inf} P(X >= k). Computed from the picks_log rungs. P(X >= 1)
set to 1.0 (virtually all skill players catch at least once). Rungs below the lowest available
(where P > 0.95 and was filtered) set to 0.975. Rungs above the highest available (P < 0.05)
contribute one tail term at 0.025. This is the empirical survival-function method; the sim uses
no parametric family — sim_p is the raw fraction of N draws where X >= k.

**Sim SD:** Var(X) = sum_{k=1}^{K} (2k-1)*P(X>=k) - [E(X)]^2 (telescoping identity for
non-negative integer-valued X). Computed from the same survival function.

**Book mean and SD:** Fitted Poisson(lambda) where P(X >= ceil(line+0.5) | Poisson(lambda)) = q_over.
Solved via Brent's method. Book mean = lambda; book SD = sqrt(lambda). One-parameter family
is the most that one data point (q_over at one line) can identify.

**Actuals:** PBP 2026 Week 2, play_type == "pass" and complete_pass == 1, grouped by
receiver_player_id. Players with zero catches in PBP get actual = 0.

**2025 status:** From player_usage_weekly.parquet, season == 2025. "Same team" = player's
last-week team in 2025 matches their 2026 board team.

**Team pass-attempt error:** sim's team reception total (sum of sim_mean for all matched players
on the team) minus book's QB pass-attempt line (from board, market_key = player_pass_attempts).
Terciles of this error.

**Mean-vs-spread decomposition:** To test whether the gap is a mean or spread problem, shift the
sim's survival function so its mean matches the book's line. Method: compute shift = sim_mean -
book_line, then interpolate the sim's survival function at k_threshold + shift to get the
adjusted sim_p. SD of (adjusted_sim_p - book_q) vs original SD gives the fraction removed by
fixing the mean.

## Results

### Overall

| metric | value |
|--------|------:|
| N (matched player-lines) | 131 |
| mean(sim_mean - book_line) | +0.409 |
| SD(sim_mean - book_line) | 0.746 |
| mean(gap = sim_p - book_q) | +0.039 |
| SD(gap) | 0.147 |

The sim's mean is biased high by 0.41 receptions on average. This confirms D131's sim-vs-book
gap is partly a level shift.

### By position

| pos | n | mean_error | SD_error | mean_gap | SD_gap |
|-----|--:|----------:|---------:|---------:|-------:|
| RB  | 31 | +0.252 | 0.487 | -0.013 | 0.130 |
| TE  | 34 | +0.382 | 0.709 | +0.037 | 0.126 |
| WR  | 66 | +0.497 | 0.853 | +0.064 | 0.160 |

WR carries the largest mean error (+0.50) and the most gap dispersion. RBs are closest to the
book. The WR excess is consistent with the sim over-projecting target volume for wide receivers.

### By 2025 season status

| status | n | mean_error | SD_error |
|--------|--:|----------:|---------:|
| had 2025 season | 121 | +0.394 | 0.750 |
| no 2025 season | 10 | +0.590 | 0.707 |

### By same team as 2025

| status | n | mean_error | SD_error |
|--------|--:|----------:|---------:|
| same team | 102 | +0.360 | 0.737 |
| changed team | 19 | +0.579 | 0.810 |
| no 2025 season | 10 | +0.590 | 0.707 |

**Prediction (2): FAILED.** No-2025 players have a 0.196-reception larger mean error (0.590 vs
0.394); changed-team players have a 0.219-reception larger error (0.579 vs 0.360). Both are in
the right direction but below the 0.5 threshold. The prior-season and team-change effects are
real but modest, not the dominant source of error.

### By team pass-attempt error (terciles)

| tercile | n | team_pass_err | mean_error | SD_error |
|---------|--:|--------------:|-----------:|---------:|
| low | 46 | -17.1 | +0.106 | 0.733 |
| mid | 41 | -13.0 | +0.439 | 0.587 |
| high | 44 | -9.1 | +0.698 | 0.784 |

Note: all team_pass_err values are negative because sim_team_rec_total (sum of sim's player
reception means) is substantially below the book's QB pass-attempt line. This is expected:
not every pass attempt results in a reception (completion rate ~65%), and the sim's player
means are bounded receptions, not attempts.

**Prediction (3): HELD.** Between-group R^2 of team_pass_err terciles on mean_error is ~11%
(computed: between-SS 7.94 / total-SS 72.3). Less than one third.

The monotonic pattern (low error → low team error; high error → high team error) confirms that
team pass volume contributes to individual mean error, but most of the player-level error is
player-specific, not inherited from the team total.

### Who is closer to actual? (MAE)

| group | sim MAE | book MAE | n |
|-------|--------:|---------:|--:|
| Overall | 1.765 | 1.569 | 131 |
| RB | 1.412 | 1.403 | 31 |
| TE | 1.879 | 1.676 | 34 |
| WR | 1.872 | 1.591 | 66 |
| had 2025 | 1.831 | 1.616 | 121 |
| no 2025 | 0.973 | 1.000 | 10 |

Sim wins on count: 53 closer vs 78 book closer. The book is a better point predictor overall
(MAE 1.569 vs 1.765), with the largest sim disadvantage in WR and TE. Notably, the 10 no-2025
players are the one group where the sim is slightly closer (0.973 vs 1.000), though n=10 is too
small to conclude anything.

### Mean vs spread decomposition

| metric | value |
|--------|------:|
| Original SD(sim_p - book_q) | 0.1471 |
| Adjusted SD (mean replaced, dispersion kept) | 0.0895 |
| Fraction of SD removed | 39.2% |

**Prediction (1): FAILED.** Replacing the sim's mean with the book's line removes 39.2% of the
gap SD, not > 50%. The gap is NOT primarily a mean problem.

| metric | sim | book (Poisson) | ratio |
|--------|----:|---------------:|------:|
| Mean SD across players | 1.700 | 1.761 | 0.984 |

The sim's and book's dispersions are nearly identical in aggregate (ratio 0.984). So the
remaining 61% of the gap is NOT from the sim having the wrong variance — it's from
player-level shape differences: individual players where the sim's probability at the book's
specific line diverges from the book, even after correcting the mean. This is consistent with
the sim's count distribution having a different shape (e.g., heavier or lighter tails than the
Poisson the book prices imply) at the individual-player level.

## Diagnosis — what the gap is made of

The sim-vs-book gap (SD 0.147) is made of three layers, none dominant:

1. **A mean bias (+0.41 receptions, explaining ~39% of the gap SD).** The sim over-projects
   receptions, worst for WR (+0.50) and players who changed teams (+0.58) or lack 2025 data
   (+0.59). Fixing the mean alone would reduce the gap SD from 0.147 to 0.090.

2. **Team pass-volume error (explaining ~11% of mean error variance).** Players on teams where
   the sim's total differs more from the book carry larger individual errors, but this is a
   minority of the total. Most error is player-specific.

3. **Player-level shape noise (the remaining ~61%).** The sim's and book's aggregate dispersions
   are nearly identical (SD ratio 0.984), so the residual gap is not a global spread error.
   It is player-by-player probability differences at the specific line the book quotes — the
   sim's count distribution shape differs from the book's Poisson-like pricing at the individual
   level. This could reflect: (a) the sim's discrete count distribution (from 100 draws) having
   sampling noise at each rung; (b) the sim's mixture of game states producing a different
   distributional shape than Poisson; or (c) the book adjusting individual player lines based on
   information the sim doesn't have (injury reports, matchup adjustments, sharp money).

No engine, usage, table, or parameter change made. No fix proposed.
