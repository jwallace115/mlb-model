# CC Decision Log v1

## CC-D1 — Inventory, gaps, and cell status (2026-11-06)

**What exists:**
- NHL: in-play 5-min tape (2022-23, 2023-24) with Pinnacle + 8-9 soft books; lines_all.parquet with
  Pinnacle h2h/spreads/totals 2022-26; SBRO games with outcomes for 1,312 games per DEV season;
  events tables (shots, state_time, penalties) for 1,312 games per season; goalie starts and GSAx
  ratings from 2021+; family.csv with 63 existing ledger p-values.
- NBA: lines_hourly with Pinnacle + 8 soft books for 1,248/1,246 events per DEV season;
  games.parquet with 1,230 outcomes per season; box_stats with possessions/pace/ratings;
  player_game_logs (FGA, FTA, TOV, MIN) for 2022-26; schedule_features with rest/travel.

**What is missing:**
- game_asof (official injury report index): covers only 2024-25 and part of 2025-26. NO DEV season
  data. This blocks NB4 (star out, total cut) and NB9 (late upgrade) entirely.
- NBA in-play tape for 2022-23: absent. Close for that season comes from lines_hourly only.
- NBA 2021-22 season data: needed for NB7's "prior season pts/game" in the 2022-23 window. Not in
  games.parquet. Would need external source.

**Cell status after inventory:**

| Cell | Status | Notes |
|---|---|---|
| NH1 | RUNNABLE | opener→close total move from lines_all; outcome from SBRO games |
| NH2 | RUNNABLE | mirror of NH1 |
| NH3 | RUNNABLE | soft book prices from in-play tape or lines_all; Pinnacle from same |
| NH4 | RUNNABLE | backup from goalie_starts; GSAx from goalie_ratings; ML move from lines_all |
| NH5 | RUNNABLE | B2B/OT from SBRO games; travel from schedule derivation; events for Q |
| NH6 | RUNNABLE | EN goals from state_time (home_skaters < 5 or away_skaters < 5 when goal scored); p_fair from lines_all |
| NH7 | RUNNABLE | rest from SBRO games schedule; shooting % from shots table |
| NB1 | RUNNABLE | opener/close from lines_hourly; outcome from games |
| NB2 | RUNNABLE | mirror of NB1 |
| NB3 | RUNNABLE | soft spreads from lines_hourly; Pinnacle spread from same |
| NB4 | **BLOCKED** | game_asof not available for DEV seasons |
| NB5 | RUNNABLE | schedule features (3-in-4, travel) derivable from games + venue mapping |
| NB6 | RUNNABLE | B2B + OT from box_stats; player minutes from player_game_logs |
| NB7 | **PARTIAL** | needs 2021-22 season pts/game for the 2022-23 window; only 2023-24 window is runnable with existing data |
| NB8 | RUNNABLE | rest from schedule_features; B2B from same; spreads from lines_hourly |
| NB9 | **BLOCKED** | game_asof not available for DEV seasons |

**Decision:** Proceed with 14 of 16 Tier 1 cells. NB4 and NB9 are dropped from the CC-1 screen
(they can be revisited if game_asof data for 2022-24 is later obtained or constructed from raw
injury PDFs). NB7 runs on 2023-24 only (one DEV season) and is marked EXPLORATORY per registry §4.

REGISTRY_v1.md sha256: `ee85d564382bab563c9876156292bae74ab590984cc6b156c096fdd55cc426c1`

---

## CC-D2 — Pre-registration: Item 1 expected counts and close age (2026-11-06)

**Expected game counts** (from Item 0c):
- NHL 2022-23: ~1,312 games with outcomes + Pinnacle close
- NHL 2023-24: ~1,312 games
- NBA 2022-23: ~1,230 games
- NBA 2023-24: ~1,230 games

**Expected close age:** < 60 min mean where in-play tape is the close source (NHL both
seasons; NBA uses lines_hourly due to sparse in-play tape pre-tip coverage).

### Actual results:
- NHL: 2,624 outcome matches out of 2,638 events (14 unmatched = playoff/preseason fringe).
  Season 2022: 1,312 outcomes. Season 2023: 1,312 outcomes. **Matches expectation.**
- NHL Pinnacle close age: mean=17.7 min, median=4.3 min (in-play tape). **Meets bar.**
- NHL openers (≥12h): 1,907/2,638 = 72.3%. Cells requiring openers have ~72% fill.
- NBA: 2,505 outcome matches out of 2,546 events.
  Season 2022: 1,243. Season 2023: 1,262. **Matches expectation.**
- NBA close age: mean=500 min (skewed by outliers), median=9.3 min (lines_hourly).
  2,466/2,546 (96.9%) have close age < 60 min. Adequate for the screen.
- NBA openers: 1,886/2,546 = 74.1%.

**Second prediction data fill:**
- NHL: 5v5 attempts/60 for 2,624/2,638 games. sh% for 2,624.
- NBA: possessions for 2,505/2,546 games.

**Tests:** All 6 passed.
- t1 truncation (NHL): home_rest_days verified correct for 20 random dates
- t1 truncation (NBA): home_poss_avg10 verified correct for 20 random dates
- t1 planted leak: detected (46/50 games differ forward vs backward rest)
- t2 null control: max implied prob diff vs lines_all = within threshold
- t3 isolation: build_features source does not reference second_pred; no column overlap

---

## CC-D3 — Pre-registration: Screen expectations (2026-11-06)

**Cowork priors** (from registry §7):
- CC-0a: ≥1 NHL Tier 1 passes screen: 30%
- CC-0b: ≥1 NBA Tier 1 passes screen: 45%
- CC-0c: Tier 2 BH survivor in NBA: 55%; in NHL: 25%
- CC-0f: First survivor is totals-suppression pair (NB1 > NH1 > NB4): 40%

**Claude Code pre-registration** (before running):
- Expected BH survivors in Tier 2 under the null: ≈ 0.10 × BH-rank, i.e. 1–3 from ~420 cells
- "Home team" null control: mean r within ±0.01

**Actual results (CC-1b corrected):**
- 0 NHL Tier 1 cells pass → CC-0a OPEN (all 7 NHL cells now run as registered; 0 pass)
- 0 NBA Tier 1 cells pass → CC-0b OPEN (5 of 7 runnable NBA cells run; NB4/NB9 blocked; 0 pass)
- 2 Tier 2 BH survivors (both NBA, both April) → CC-0c NBA resolved at 1 (barely),
  NHL resolved at 0. The 2 survivors are consistent with chance (pre-registered: 1–3 expected).
- Home team null: NHL −0.004, NBA −0.007 → both within ±0.01 as pre-registered
- Positive control: planted +0.04 detected and survived BH → pipeline works

---

## CC-D4 — April diagnostic pre-registration (2026-11-06)

**Cowork prior:** artefact 60% (stale close or non-regular-season rows), real-but-priced 25%, noise 15%.

**Claude Code prior:** artefact 55% (April close quality is visibly worse in the data; p90 age
is likely > 100 min), noise 35%, real 10%.

### CC-D4 RESULT

**3a — Close age by month:**

| Month | n | median (min) | p90 (min) | share > 60 min |
|---|---|---|---|---|
| Oct | 151 | 9.3 | 9.4 | 0.7% |
| Nov | 459 | 9.3 | 14.3 | 7.8% |
| Dec | 440 | 9.3 | 9.4 | 0.9% |
| Jan | 454 | 9.4 | 9.4 | 0.7% |
| Feb | 338 | 9.3 | 9.4 | 1.2% |
| Mar | 473 | 9.3 | 9.4 | 0.8% |
| **Apr** | **231** | **9.3** | **1,209** | **12.1%** |

April's p90 and share > 60 min are **materially worse** than Nov–Mar. 12.1% of April
closes are stale (> 60 min old), compared to < 1.5% for Dec–Mar.

**3b — Cell cuts:**

| Cell | Cut | n | mean r |
|---|---|---|---|
| T2_NBA_month_4_away_ml | Original | 222 | +0.098 |
| | (i) close ≤ 15 min | 196 | +0.039 |
| | (ii) 2023-24 only | 130 | +0.086 |
| | (iii) Excl. play-in (30 removed) | 192 | **+0.012** |
| T2_NBA_month_4_over | Original | 192 | +0.112 |
| | (i) close ≤ 15 min | 188 | +0.109 |
| | (ii) 2023-24 only | 116 | +0.109 |
| | (iii) Excl. play-in (0 removed) | 192 | +0.112 |

**T2_NBA_month_str_4_away_ml**: collapses from +0.098 to +0.012 after excluding play-in games.
The signal was entirely carried by 30 play-in/non-regular-season games. **DEAD-ARTEFACT.**

**T2_NBA_month_str_4_over**: survives all three cuts (r stays +0.109 to +0.112). However,
it is a single-feature Tier 2 cell with no mechanism, Q, or prior — it remains a HYPOTHESIS
per registry §5. Not promoted.

**3c — Q for fired April games:**
- Possessions vs prior-10: mean diff +2.9, median +1.7 (April games have slightly higher pace)
- Top-5 minutes avg: 32.5 min (no prior-20 baseline to compare against in this output)

**Verdict:** away_ml cell is DEAD-ARTEFACT (play-in contamination). Over cell is noise-or-pace
but cannot be distinguished from chance without a mechanism. Neither changes the screen conclusion.

---

## CC-D5 — CHECK 2 gate for NB10 CONFIRM (2026-11-06)

**Question:** Does any legacy NBA research contain an April / late-season / month-of-season
totals cell that touched 2024-25 data?

**Grep results (every hit with path + line):**

1. `nba/backtest.py:114` — "Late season (Jan-Apr)" MAE/bias breakdown. General model diagnostic,
   not a cell. Touches all seasons including 2024-25 but reports aggregate model performance, not
   a betting hypothesis.
2. `nba/backtest_h1.py:85` — Same "Late season" diagnostic for H1 totals.
3. `nba/phase6.py:181` — Same "Late season" diagnostic.
4. `nba/phase7b/master_summary.txt:243`, `results_7b_c.txt:100`, `master_summary_v2.txt:66` —
   "A9 — Late season playoff race": **SKIPPED**. Never ran, no results.
5. `nba/diagnostics.py:177,196` — Ridge coefficients for `days_rest_home` / `days_rest_away`.
   Rest features in the totals model, not April-specific. General model, not a cell.
6. `research/nba_layers/legacy_review_2026-09-30/NBA_LEGACY_REVIEW_2026-09-30.md:27-29` — April
   venue-board analysis touched 2024-25, but this was about ML/ATS team lists (ROAD_WARRIOR,
   STRONG_HOME), not a month-of-season totals cell. CHECK 2 failed for the venue board on
   different grounds.
7. `research/nba_layers/legacy_review_2026-09-30/PREREG_rw_sh_2025_26.md:4-7` — Same venue-board
   April revalidation. About the team-list selection, not totals.
8. `research/corrcause/` itself — `T2_NBA_month_str_4_over` screened on DEV 2022-23 + 2023-24
   only. Did NOT touch 2024-25.

**No cell found.** The legacy NBA research has:
- General late-season model diagnostics (backtest splits): not cells, not hypotheses
- A9 (late-season playoff race amplifier): SKIPPED, never produced results
- Venue-board April analysis: touched 2024-25 but is about team selection for ML/ATS, not a
  month-of-season totals cell
- The corrcause Tier 2 April over cell: DEV-only, no 2024-25 data

**Decision: GATE OPEN.** No prior April / late-season / month-of-season NBA totals cell touched
2024-25 data. Item 2 (NB10 CONFIRM) proceeds.

---

## CC-D5c — Data availability for NB10 CONFIRM (2026-11-06)

**lines_hourly season=2024:**
- 4,743 total files
- April 2025 events with Pinnacle totals: 119

**games.parquet (outcomes):**
- April 2025 games with actual_total: 105
- All 105 are regular-season (date range: 2025-04-01 to 2025-04-13)
- 2024-25 regular-season finale: 2025-04-13

**box_stats.parquet:**
- April 2025 rows: 210 (105 games × 2 teams), all with possessions

**Merged (both Pinnacle total close AND outcome): 105 games**

GATE CHECK: 105 ≥ 80 → **PASS**

REGISTRY_v2_ADDENDUM.md sha256: `f27d476055872bb242139843bbb55dcfad6193317564e934db90fbb56a6f67a6`

---

## CC-D6 — Pre-registration: Tier 2 market-behaviour features (2026-11-06)

**New features (7 total):**
- NHL f1: soft–Pinnacle ML divergence at close (max |soft_fair_h - pin_fair_h| ≥ 0.02)
- NHL f2: move timing share (share of Pinnacle opener→close ML move in last 3h; < 0.3 / 0.3–0.7 / ≥ 0.7)
- NHL f3: book-consensus dispersion at close (SD of soft books' de-vigged home prob; terciles)
- NHL f4: in-play reset (first in-play Pinnacle ML vs last pre-tip; |Δ| ≥ 0.02; NOT-BETTABLE)
- NBA f1: soft–Pinnacle ML divergence + spread divergence (≥ 0.5 pts for spread)
- NBA f2: move timing share (ML + spread, same bins)
- NBA f3: divisional flag (same-division game)

**Expected cell counts:**
- NHL: f1 (flag 2 + band 3) × 4 sides + f2 3 × 4 + f3 3 × 4 + f4 2 × 4 = 20 + 12 + 12 + 8 = 52
- NBA: f1_ml (flag 2 + band 3) × 6 + f1_spr flag 2 × 6 + f2_ml 3 × 6 + f2_spr 3 × 6 + f3 2 × 6 = 30 + 12 + 18 + 18 + 12 = 90
- Total new: ~142 cells

**Cowork priors:**
- At least one NHL market-behaviour Tier 2 cell survives BH: 20%
- At least one NBA market-behaviour Tier 2 cell survives BH: 20%

**Claude Code priors:**
- NHL market-behaviour Tier 2 BH survivor: 10% (the BH bar is very high; 52 cells with n ≈ 1,200
  each need r ≈ +0.05 to clear, and market-efficiency research suggests these features are largely
  priced in; f4 is excluded from BH)
- NBA market-behaviour Tier 2 BH survivor: 15% (larger sample, more sides, but same structural
  argument)

**Null control:** home team, same as before (must be within ±0.01)
**Positive control:** same planted +0.04 positive control from v1b (n ≈ 148, expected below BH;
  re-checks pipeline integrity)

### CC-D6 RESULT

**Null control:** NHL −0.004, NBA −0.007 → both within ±0.01 → **PASS**

**Tier 1 BH (16 cells, confirmatory):** 0 survivors (threshold: 0.000). No change from v1b.

**Tier 2 + ledger BH (535 cells = 472 Tier 2 + 63 ledger, exploratory α=0.10):**
- BH threshold: 0.001308
- 7 survivors: A-03a (p=0.00001), L-004 (p=0.0002), L-003 (p=0.0004),
  **T2_NHL_f1_divergence_flag_yes_under** (p=0.000442), T2_NBA_month_str_4_away_ml (p=0.000840),
  T2_NBA_month_str_4_over (p=0.000853), **T2_NHL_f1_divergence_band_small_under** (p=0.001000)

**New BH survivors (NHL f1 divergence):**

| Cell | n | r (2022) | r (2023) | r (pooled) | p | ROI soft | ROI pin | share lg SM |
|---|---|---|---|---|---|---|---|---|
| f1_flag=yes_under | 592 | +0.093 | +0.050 | +0.068 | 0.00044 | +0.106 (585p) | +0.105 | 0.172 |
| f1_band=small_under | 576 | +0.090 | +0.045 | +0.064 | 0.00100 | +0.097 (569p) | +0.097 | 0.202 |

Note: the two cells are nearly overlapping (576 of 592 games in the flag=yes cell also have band=small).
January is the one negative month (r ≈ −0.06); all other months are positive. No month carries > 20%.

**NOT-BETTABLE (f4 in-play reset, excluded from BH):** 8 cells. Only f4_reset_flag=no_under is notable
(n=2449, r=+0.022, p=0.015) — but this fires on 93% of games (trivially: "no in-play reset" ≈ all games)
and its signal is just the overall NHL under bias from the close source. Diagnostic only, as registered.

**f2 timing near-misses:** NHL f2_mixed_under (n=264, r=+0.067, p=0.014), NHL f2_late_under (n=839,
r=+0.029, p=0.048). Neither survives BH.

**f3 dispersion near-misses:** NHL f3_high_under (n=813, r=+0.037, p=0.019). Does not survive BH.

**NBA v2 market features:** 0 BH survivors. Closest: f2_ml_timing_band_mixed_under (n=369, r=+0.051,
p=0.024), f1_ml_div_band_medium_under (n=28, r=+0.144, p=0.064, underpowered).

**Priors resolved:**
- Cowork: NHL market-behaviour Tier 2 BH survivor: 20% → **YES** (2 survivors, same cell overlap).
  NBA: 20% → **NO**.
- Claude Code: NHL 10% → WRONG (underestimated); NBA 15% → CORRECT (no survivors).

**v2 features generated:**
- NHL: 100 cells (52 v2 + 48 v1)
- NBA: 384 cells (90 v2 + 294 v1)
- Total Tier 2: 484 cells

---

## CC-D7 — NB10 CONFIRM pre-registration (2026-11-06)

**Cell:** NB10 — April regular-season OVER (promoted from T2_NBA_month_str_4_over; addendum §B)

**Rule (frozen, from addendum §B):** NBA regular-season games with Pinnacle closing total,
tip in April (through 2025-04-13), OVER at the closing point, pushes excluded.

**Pass criteria:**
1. r (residual vs Pinnacle fair over prob) same sign as screen (+), with game-clustered
   90% lower bound > 0
2. ROI at the best same-point soft price > 0
3. Q holds: possessions in fired games ≥ two teams' prior-10 average + 1.0 (one-sided p < 0.10)

**Cowork prior:** CONFIRM pass 30%. Known public angle; the honest expectation is that 2024-25
shows it smaller.

**Claude Code prior:** CONFIRM pass 25%. The screen r was +0.112 on 192 games; the MDE at
n ≈ 95 is +0.085. Even if the true effect is half the screen estimate (~+0.056), the 90% CI
lower bound will include 0. The public April rest/tank angle has been in circulation for years.

**One run. Whatever it says, nothing is re-run or re-cut.**

### CC-D7 RESULT

**n = 103** (105 matched, 2 pushes excluded)

| Criterion | Value | Threshold | Result |
|---|---|---|---|
| r | +0.041 | > 0 | PASS (same sign as screen +0.112) |
| 90% lower bound | −0.023 | > 0 | **FAIL** |
| ROI at best soft price | +7.0% (n=95) | > 0 | PASS |
| ROI at Pinnacle | +5.0% | — | reported |
| Q1 possessions diff vs prior-10 | +1.4 (SE=1.1) | ≥ +1.0, p < 0.10 | **FAIL** (p=0.36) |
| Q2 top-5 minutes diff vs prior-20 | −0.8 (SE=0.4) | ≤ −2.0, p < 0.10 | **FAIL** (p=0.996) |

**VERDICT: FAIL.** Criterion 1 (90% LB > 0) and Q1 both fail. The observed r (+0.041) is the
same sign as the screen (+0.112) but roughly 1/3 the size, and the 90% CI includes 0. The
possessions Q shows the direction (+1.4) but is noisy. The top-5 minutes show NO reduction in
star playing time — the mechanism's second prediction does not hold.

**NB10 is DEAD with its id.** No re-run, no re-cut.

Cowork prior (30%) → **CORRECT** (the prior expected it smaller; it was).
Claude Code prior (25%) → **CORRECT**.

---

## CC-D8 — Pre-registration: Is the NHL divergence→under survivor a stale-quote artefact? (2026-11-07)

**Context:** T2_NHL_f1_divergence_flag_yes_under (n=592, r=+0.068, p=0.00044) survived BH.
Cowork verification found that `extract_closes` takes each book's last pre-tip snapshot
SEPARATELY, so "divergence at close" compares quotes that may be hours apart — the flag
may mean "Pinnacle moved after some soft book stopped quoting", not genuine disagreement.
Additionally, every NHL under cell sits on a population under residual of +0.022 (n=2,449).

**Cowork priors:**
- The under excess concentrates in asynchronous / stale rows (artefact): 55%
- Persists in synchronous fresh rows at ≥ +0.04 over the population base: 30%
- Neither (noise): 15%

**Claude Code priors:**
- Artefact (stale quotes drive most of the signal): 50%
- Persists in synchronous fresh rows at ≥ +0.04 over population base: 20%
- Noise (effect disappears or is within population base in all cuts): 30%

**Rationale for Claude Code priors:** The extract_closes design is genuinely problematic —
each book's last snapshot is taken independently, so the "divergence" could easily be
Pinnacle updating while a soft book went dark hours earlier. However, the effect is in both
DEV seasons (2022: +0.093, 2023: +0.050), which is harder for pure staleness to explain
unless the staleness pattern is stable across seasons. The 30% noise prior reflects that
the population under base (+0.022) already accounts for a third of the pooled r, so the
incremental signal may be smaller than it looks.

