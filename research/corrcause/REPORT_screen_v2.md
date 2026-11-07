# CC-2 Screen Report v2 (2026-11-06)

REGISTRY_v1 sha256: `ee85d564382bab563c9876156292bae74ab590984cc6b156c096fdd55cc426c1`
REGISTRY_v2_ADDENDUM sha256: `f27d476055872bb242139843bbb55dcfad6193317564e934db90fbb56a6f67a6`

## Tier 2 — New Market-Behaviour Features

### NHL features (4)

| Feature | id | Description | Non-null | Method |
|---|---|---|---|---|
| f1 | `f1_max_divergence` | Max \|soft_fair_h − pin_fair_h\| ≥ 0.02 across 9 soft books at close | 637 / 2,638 | De-vig each soft book's ML close, compare to Pinnacle fair |
| f2 | `f2_timing_share` | Share of Pinnacle opener→close ML move in last 3h | 1,845 / 2,638 | From in-play tape + lines_all pre-tip snapshots |
| f3 | `f3_dispersion` | SD of soft books' de-vigged home prob at close | 2,634 / 2,638 | Tercile bins |
| f4 | `f4_ip_reset_delta` | First in-play Pinnacle ML vs last pre-tip, \|Δ\| ≥ 0.02 | 7 / 2,638 | **NOT-BETTABLE**, excluded from BH |

### NBA features (3)

| Feature | id | Description | Non-null |
|---|---|---|---|
| f1 | `f1_ml_divergence` / `f1_spread_divergence` | Soft-Pinnacle divergence on ML (≥ 0.02) and spread (≥ 0.5 pts) | 662 ML / 2,223 spread |
| f2 | `f2_ml_timing_share` / `f2_spread_timing_share` | Timing share on ML and spread | 1,676 ML / 1,517 spread |
| f3 | `f3_divisional` | Same-division flag | 2,546 (all) |

NBA Division Map (committed):
- Atlantic: BOS, BKN, NYK, PHI, TOR
- Central: CHI, CLE, DET, IND, MIL
- Southeast: ATL, CHA, MIA, ORL, WAS
- Northwest: DEN, MIN, OKC, POR, UTA
- Pacific: GSW, LAC, LAL, PHX, SAC
- Southwest: DAL, HOU, MEM, NOP, SAS

### BH — Two Families Side by Side (per addendum §A)

**Tier 1 (confirmatory, 16 pre-registered cells):**

| Cell | n | r | p | BH survivor |
|---|---|---|---|---|
| NH7 | 57 | +0.121 | 0.033 | no |
| NB6 | 35 | +0.158 | 0.031 | no |
| NB2 | 234 | +0.036 | 0.140 | no |
| NH4 | 152 | +0.040 | 0.157 | no |
| NH2 | 218 | +0.055 | 0.051 | no |

0 survivors. BH threshold: 0.000 (no p-value below the step function at α=0.10 / 14).
All 14 runnable cells fail. The Tier 1 cells proposed mechanism-first hypotheses; none are
confirmed even at the uncorrected level except NH7 (p=0.033, but n < 60/season: reclassified
in addendum §C as post-break UNDER, not a cell).

**Tier 2 + ledger (exploratory, 535 cells = 472 Tier 2 + 63 ledger):**

| Cell | Source | n | r (s1) | r (s2) | r (pooled) | p | ROI soft | BH |
|---|---|---|---|---|---|---|---|---|
| A-03a | ledger | — | — | — | — | 0.000010 | — | **YES** |
| L-004 | ledger | — | — | — | — | 0.000200 | — | **YES** |
| L-003 | ledger | — | — | — | — | 0.000400 | — | **YES** |
| **f1_flag_yes_under** | **v2 NEW** | **592** | **+0.093** | **+0.050** | **+0.068** | **0.000442** | **+10.6%** | **YES** |
| month_4_away_ml | v1 | 222 | +0.098 | +0.086 | +0.098 | 0.000840 | — | YES (DEAD-ARTEFACT) |
| month_4_over | v1 | 192 | +0.117 | +0.109 | +0.112 | 0.000853 | — | YES (NB10 DEAD via CONFIRM) |
| **f1_band_small_under** | **v2 NEW** | **576** | **+0.090** | **+0.045** | **+0.064** | **0.001000** | **+9.7%** | **YES** |

BH threshold: 0.001308. 7 survivors; 2 are new v2 cells.

### New BH Survivors — Detail

**T2_NHL_f1_divergence_flag_yes_under** (the "divergence UNDER" cell):
- Fires: 592 games (256 s2022 + 336 s2023) where ≥ 1 soft book diverges from Pinnacle on
  ML by ≥ 0.02 implied prob. Side: UNDER on NHL totals.
- r: +0.068 pooled (SE=0.019, p=0.00044). Same sign both seasons (+0.093 / +0.050).
- ROI at best soft price: +10.6% (585 priced, SE=4.1%). ROI at Pinnacle: +10.5%.
- share_largest_sm: 0.172 (no single season-month carries > 18%).
- By month: Jan −0.059, Feb +0.104, Mar +0.102, Apr +0.028, Oct +0.093, Nov +0.090, Dec +0.097.
  January is the only negative month; effect is broadly distributed.
- MDE at p < 0.05: +0.037 (well below observed +0.068).

**T2_NHL_f1_divergence_band_small_under** (the "small divergence" sub-cell):
- Nearly overlapping: 576 of 592 games. Small = divergence 0.02–0.04.
- r: +0.064 (p=0.001), ROI +9.7%. Same sign, same pattern.
- These two cells are effectively one cell counted twice. The medium (n=13, r=+0.297) and
  large (n=3) bins are underpowered.

**Interpretation:** when soft books disagree with Pinnacle on NHL ML by ≥ 2 implied prob pts
at close, the corresponding game's total goes UNDER more than the Pinnacle close predicts.
This is a Tier 2 exploratory finding with no mechanism, Q, or prior written down. It is a
HYPOTHESIS per registry §5 — it needs mechanism, second prediction, and why-missed before
any CONFIRM look or promotion to Tier 1.

### NB10 CONFIRM Result

**FAIL.** April 2024-25 regular-season OVER:
- n=103, r=+0.041 (same sign as screen +0.112, but 1/3 the size)
- 90% lower bound: −0.023 (includes 0) → Criterion 1 FAIL
- ROI at best soft: +7.0% (n=95) → Criterion 2 pass
- Q1 possessions: +1.4 vs prior-10 (p=0.36) → FAIL
- Q2 top-5 minutes: −0.8 vs prior-20 (p=0.996) → FAIL
- The mechanism's second prediction (reduced star minutes in April) does not hold.

**NB10 is DEAD.** The April away_ml cell (DEAD-ARTEFACT from v1) + the over cell (DEAD from
CONFIRM) are both resolved. No April NBA cell survives.

### Power Lines

At the ≥ 60/season floor (120 pooled DEV games):
- MDE at p < 0.05 (uncorrected): +0.076
- MDE at BH threshold (0.001308): +0.137

At 240 games: MDE p < 0.05 = +0.053, MDE BH = +0.097.

The NHL f1 divergence cell (n=592) has MDE p < 0.05 = +0.037, MDE BH = +0.056 — comfortable
margin above both thresholds given the observed +0.068.

Cells with MDE > +0.05 at uncorrected p < 0.05 are labelled UNDERPOWERED. This applies to
all cells with n < ~240 at typical NHL/NBA residual volatility (σ ≈ 0.5).

### Controls

| Control | Result |
|---|---|
| Null (home team ML) | NHL −0.004, NBA −0.007: **PASS** (within ±0.01) |
| Positive (planted +0.04, n=148, CC-1b) | Pipeline integrity confirmed (same data, same code) |

### Leak Test (Item 3)

`test_planted_leak_fails_truncation`:
- **WITH `CORRCAUSE_PLANT_LEAK=1`:** Rebuilds NHL features with `season_prior` using `<= game_date`
  instead of `< game_date`. Truncation check finds 133 errors (games with rest_days = 0 where
  true rest > 0). Test correctly FAILs. Exit code 1.
- **WITHOUT env var:** Rebuilds features normally. Truncation check finds 0 errors. Test PASSES.
  Exit code 0.
- Both outputs pasted in the test session.

Close null (0.005 threshold):
- 975 / 2,534 common events have |diff| > 0.005 between the in-play tape close and lines_all close.
  This is expected: the in-play tape has snapshots much closer to tip (mean ~17 min) while lines_all
  snapshots can be 1–18h earlier. These are real price movements, not extraction errors.
- Max diff: 0.045. All are below the 0.05 structural-error threshold.
- Sample of games > 0.005 with snapshot times: Florida Panthers (tape=2023-03-25 20:55, lines=01:40,
  diff=0.045), Minnesota Wild (tape=2022-12-03 18:55, lines=01:40, diff=0.011), etc.

### NH3/NB3 Fired Parquets — Collapsed

| Cell | Before | After | Duplicates removed |
|---|---|---|---|
| NH3 (v1b + v2) | 85 | 73 | 12 (games counted in multiple soft-book directions) |
| NB3 (v1b + v2) | 213 | 137 | 76 (same) |

## NOT DONE

- No mechanism, Q, or prior written for the NHL f1 divergence cell — it is a HYPOTHESIS only.
  Writing these is a precondition for any CONFIRM look per addendum §A.
- NHL f4 (in-play reset) fired on only 7 games; effectively unmeasurable. Diagnostic only.
- NBA market-behaviour features produced 0 BH survivors. The features work (non-trivial fill
  rates) but the cells are noise at current power.

## UNVERIFIED

- The NHL f1 divergence cell's ROI (+10.6%) is computed at the best available soft close price
  with same-point matching. It has NOT been checked against closing-line value (CLV) or against
  a tighter close-age window. The signal could be partly a close-timing artefact (soft books
  with stale prices contribute both the divergence and the favorable payout).
- The January negative month (−0.059) in the f1 cell has not been investigated. It could be
  seasonal, it could be noise at n=82.
- The NBA f2 timing near-miss (mixed_under, p=0.024) was not investigated further.
