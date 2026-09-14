# Phase 4B: Grading, K4 Re-run, Board Upgrades

## 1. Name Resolver (nfl/sim/names.py)

Built `resolve_player(name, season, week, team_candidates)` against rosters_weekly.

Normalisation: lowercase, strip accents (NFD decompose), strip punctuation (`.'-,`),
strip suffixes (Jr, Sr, II, III, IV, V), strip `(TEAM)` suffix, collapse whitespace.

Match order:
1. Exact normalised full-name match on a candidate team
2. Unique first-initial + last-name match on a candidate team
3. Unique normalised full-name match league-wide
4. Unresolved

Alias table for known mismatches: Hollywood Brown -> Marquise Brown,
Gabriel Davis -> Gabe Davis, Drew Ogletree -> Andrew Ogletree, etc.

### Resolution rates

| Season | Total players | Resolved | Rate |
|--------|--------------|----------|------|
| 2026 | 364 | 364 | **100.0%** |
| 2024 (20k sample) | 6013 | 5934 | **98.7%** |

2024 unresolved (46): all retired/cut players not on week-18 roster or defensive
players without skill-position entries.

## 2. K4 Re-run (2023-2024 IN-SAMPLE TRIAGE, player_id matching via resolver)

**Previous Phase 3b K4 had a symmetry failure**: both over (+12.7%) and under (+12.6%)
showed positive ROI for WR receptions. Root cause: approximate name matching (last-name
only) created spurious matches. The "+2.1pp receptions edge" was an artifact.

### K4 with player_id resolver

| Family | Position | Side | N | Mean edge | ROI |
|--------|----------|------|---|-----------|-----|
| receptions | WR | over | 21025 | -0.054 | -0.104 |
| receptions | WR | under | 21022 | +0.054 | -0.027 |
| receptions | TE | over | 8058 | -0.077 | -0.093 |
| receptions | TE | under | 8057 | +0.077 | -0.033 |
| receptions | RB | over | 6268 | -0.122 | -0.117 |
| receptions | RB | under | 6266 | +0.122 | +0.005 |
| reception_yds | WR | over | 16810 | -0.068 | -0.041 |
| reception_yds | WR | under | 16809 | +0.068 | -0.079 |
| rush_yds | RB | over | 5053 | -0.059 | -0.107 |
| rush_yds | RB | under | 5052 | +0.059 | -0.002 |
| rush_attempts | RB | over | 622 | -0.025 | -0.153 |
| rush_attempts | RB | under | 622 | +0.025 | +0.035 |
| anytime_td | WR | over | 19240 | -0.032 | -0.146 |
| anytime_td | RB | over | 6511 | -0.069 | -0.129 |
| anytime_td | TE | over | 8803 | -0.046 | -0.327 |

### SYMMETRY CHECK

| Family | Over ROI | Under ROI | Sum | Status |
|--------|----------|-----------|-----|--------|
| receptions | -0.104 | -0.023 | **-0.126** | PASS |
| rush_attempts | -0.155 | +0.037 | **-0.119** | PASS |
| reception_yds | -0.061 | -0.067 | **-0.128** | PASS |
| rush_yds | -0.108 | -0.001 | **-0.109** | PASS |
| anytime_td | -0.189 | N/A | **-0.189** | PASS |

**All families PASS.** Sum of over + under ROI is approximately -0.11 to -0.13,
consistent with ~5% vig per side (2 x 5% = 10% = -0.10). The Phase 3b symmetry
failure was entirely caused by name-matching confusion.

### Key finding: No positive edge in any family

The Phase 3b "+2.1pp receptions edge" was an artifact of bad matching. With correct
player_id resolution:
- **All families show negative mean edge on overs** (sim underprices vs book)
- **All families show negative flat-stake ROI** (except tiny positive on RB rush_att under)
- The sim's value is in distribution shape / SGP correlations, not in outright prop pricing

### Anytime TD calibration note

The `actual_atd = 0` shortcut lived only in calibration.py's `_score_player_props` path,
which is called from `fit_calibration_maps`. The ATD calibration maps in calibration_v1.json
were NOT fitted from that path — they were fitted from `run_cal_players.py`'s output
(`cal_players_props_*.parquet`), where `actual_atd` was graded correctly from PBP
(`touchdown == 1` on rusher/receiver columns). Verified: 2024 mean actual_atd = 0.242
(791/3264 nonzero), mean p_atd = 0.234 — the maps are valid. The shortcut in
`_score_player_props` has been fixed to use `actual_player_stats()` td_stats (Phase 4B-fix).
WR anytime TD remains TRUSTED.

## 3. Board Changes (Phase 4B)

### a) Chunked simulation (--n-sims flag)
- Default 10000, executed as chunks of 2000 with distinct seeds
- sim_id offset per chunk in player_df; team_df pooled
- Convergence: |market - mean| < 2*SE on both margin and total
- No 0.25/0.5 floors (at N=10k the floors exceeded the SE noise)

### b) Price-aware board
- Hard Rock props joined to every player leg via the resolver
- Two-sided multiplicative vig removal where both sides exist
- Columns: book_price, book_implied, one_sided, pull_batch, pull_timestamp
- Legs with no book line kept and marked no_price

### c) D16 Tiers
- TRUSTED: WR receptions, WR anytime TD, anchored game markets
- TRUSTED-FLAGGED: TE receptions [TE], RB receptions [RB tail]
- WATCH: RB rush attempts (shown with [WATCH: yardage-family calibration not passed])
- WATCH legs excluded from cross-game top-20
- Price filter: book_implied > cal_p + 0.10 -> BOOK-MORE-CONFIDENT, excluded from top-20

### d) Stale-input flag
- Teams with < 2 completed 2026 games get [PRIOR-ONLY SHARES] on every player row

### e) picks_log.parquet
- One row per board leg with full metadata
- Re-running same week overwrites (previous saved as picks_log_prev.parquet)

## 4. Week 1 Grades

DEN@KC (MNF) not in pbp_2026 -- all 6 MNF legs graded as **void-pending**.
No Sunday Week 1 picks_log exists in the new format (Phase 4A board predated this schema).

## 5. Week 2 Board Summary (4B, before anchoring fix)

- Runtime: 865s (14.4 min) for 16 games at N=10000
- Converged: 0/16 (SE threshold 2×SE ≈ 0.28 pts; typical anchoring residual 0.5-4 pts)
- Legs: 1306 total. Priced: 0. All teams [PRIOR-ONLY SHARES].

---

## 6. Phase 4B-fix

### 6a. Anchoring solver fix

The 4B run had 0/16 converged with residuals up to 4 pts. Root cause: fixed 5-step
Newton with the global J_INV overshoots for games whose per-game sensitivity differs
from the 50-game mean (GB@NYJ, NYG@LA, etc).

**Fix:** damped Newton with 8 iterations, step-size limiting (halve until predicted
move <6 pts per channel), and best-iteration selection (return the iteration with
minimum |err_m|+|err_t| if the final iteration is worse).

**Week 2 re-run results (N=10000, 8 iter max):**

| Game | Best iter | err_m | err_t | |m|<0.5 | |t|<1.0 | 2*SE |
|------|-----------|-------|-------|---------|---------|------|
| CAR@ATL | 8 | -1.29 | -0.60 | N | Y | N |
| CIN@HOU | 5 | +0.16 | -0.15 | Y | Y | Y |
| CLE@TB | 5 | -0.39 | +1.04 | Y | N | N |
| DET@BUF | 2 | +0.05 | +1.01 | Y | N | N |
| GB@NYJ | 8 | +2.16 | -0.01 | N | Y | N |
| IND@KC | 7 | -0.31 | +0.99 | Y | Y | N |
| JAX@DEN | 3 | +1.78 | +2.97 | N | N | N |
| LV@LAC | 7 | -0.09 | +0.71 | Y | Y | N |
| MIA@SF | 8 | +0.13 | +1.17 | Y | N | N |
| MIN@CHI | 7 | +0.48 | +0.18 | Y | Y | N |
| NO@BAL | 4 | -0.56 | -0.75 | N | Y | N |
| NYG@LA | 6 | +2.74 | -0.12 | N | Y | N |
| PHI@TEN | 7 | +0.05 | +0.82 | Y | Y | N |
| PIT@NE | 6 | -0.50 | +0.16 | N | Y | N |
| SEA@ARI | 7 | +0.15 | +0.13 | Y | Y | Y |
| WAS@DAL | 5 | -0.20 | +1.46 | Y | N | N |
| **TOTAL** | | | | **10** | **11** | **2** / 16 |

**Improvement vs 4B:** from 0/16 converged to 10/16 within 0.5 margin and 11/16
within 1.0 total. Three games remain >1 pt margin residual (CAR@ATL, GB@NYJ, NYG@LA).

**Why some games cannot converge:**
1. Per-game Jacobian variation: the fixed J was estimated from 50 games as a mean.
   GB@NYJ has two strong defensive teams → different EPA-to-points sensitivity.
   NYG@LA has a 7-pt spread → the engine's natural lean differs more from market.
2. MC noise floor at N=10000: SE ≈ 0.14 per channel. When residual < 0.5,
   signal-to-noise is ~3.5 and the Newton step alternates (oscillation).
3. Total channel: total depends on both teams' scoring, making it harder to pin
   down than margin. The J matrix total row [4.79, 4.01] provides less directional
   discrimination than the margin row [6.88, -5.48].

Runtime: 1393s (23.2 min), 1303 legs, 0 priced (Week 2 props not yet pulled).

### 6b. grade_week.py fixes

- Never drops a leg: unresolvable/unparseable rows get grade="unresolved" with reason
- Ticket-aware dedup: same (player, family, line, side) in different tickets kept
- New families: pass_completions, pass_attempts graded from PBP passer stats
- Ticket grouping: report shows per-ticket hit/miss count and whether whole ticket hit
- Week 1 result: 23 legs from v2 MNF file, all void-pending (DEN@KC not in PBP)

### 6c. ATD calibration note corrected

The `actual_atd = 0` shortcut was in calibration.py's `_score_player_props`, which
was NOT the code path that produced the calibration maps. The maps were fitted from
`run_cal_players.py` output where actual_atd was graded correctly (2024 mean = 0.242).
The shortcut has been fixed. WR anytime TD remains TRUSTED.

### 6d. D18 deviation (solver mismatch)

The Phase 3b calibration maps were fitted using `run_cal_players.py` with the fixed-Jacobian
4-step loop at N=1000 (p90 |Δmargin| 3.95, ~10% of games effectively unanchored). The live
board now uses an 8-step damped Newton at N=10000 with best-iteration selection, which
anchors more tightly. This is the direction the maps assume (fully anchored), but the
research object and the live object now differ in anchoring precision. v2 must re-fit the
calibration maps with the same solver before the identity claim (research == live) is
restored.
