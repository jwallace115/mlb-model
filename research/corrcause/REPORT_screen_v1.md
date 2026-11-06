# CC-1 Screen Report v1 (2026-11-06)

REGISTRY sha256: `ee85d564382bab563c9876156292bae74ab590984cc6b156c096fdd55cc426c1`

## 1. Inventory + Overlap Summary

See `INVENTORY_v1.md` and `OVERLAP_v1.md` for full details.

- **NHL DEV**: 2,624 games with outcomes + Pinnacle close (1,312 per season). In-play tape
  close (mean age 17.7 min). 1,907 with openers (72%). Events tables for 5v5 analysis.
- **NBA DEV**: 2,505 games with outcomes + Pinnacle close (lines_hourly, median age 9.3 min).
  1,886 with openers (74%). Box stats and player logs for post-game Q.
- **Overlap**: NH1/2/3/6 NEW variables vs 2026-09-29 scan. NH4/7 SIMILAR (confirm FORWARD only).
  NH5 NEW (triple interaction). All NHL Tier 2 features NEW (market-behaviour).
- **Blocked**: NB4, NB9 (no game_asof for DEV). NB7 EXPLORATORY (one DEV season).
  NH3, NH6 require additional data extraction (soft-book openers, EN-goal features).
  NB3 requires per-book spread openers.

## 2. Null Controls

| Control | n | mean r | SE | Status |
|---|---|---|---|---|
| NHL "home team" ML | 2,624 | −0.0041 | 0.0094 | **PASS** (within ±0.01) |
| NBA "home team" ML | 2,494 | −0.0072 | 0.0092 | **PASS** (within ±0.01) |

## 3. Tier 1 Results

### NHL

| Cell | n | mean r | p (one-sided) | Same sign both seasons | ROI (best soft) | Status |
|---|---|---|---|---|---|---|
| NH1 (total pushed down → over) | 243 | −0.016 | 0.691 | Yes | +3.1% | **FAIL** (wrong sign) |
| NH2 (total pushed up → under) | 218 | +0.055 | 0.051 | No | +21.0% | **FAIL** (sign flips between seasons) |
| NH3 (soft-only ML move) | — | — | — | — | — | SKIP (needs per-book openers) |
| NH4 (backup overshoot) | 152 | +0.040 | 0.157 | Yes | +0.9% | **FAIL** (p > BH threshold) |
| NH5 (post-OT road B2B) | 115 | −0.002 | 0.520 | No | −2.1% | **FAIL** (wrong sign, not significant) |
| NH6 (EN-inflated favourite) | — | — | — | — | — | SKIP (needs EN-goal features) |
| NH7 (both rested ≥4 → under) | 57 | +0.121 | 0.033 | Yes | +24.9% | **FAIL** (n=57 < 60/season floor) |

### NBA

| Cell | n | mean r | p (one-sided) | Same sign both seasons | ROI (best soft) | Status |
|---|---|---|---|---|---|---|
| NB1 (total suppressed ≥3 → over) | 223 | +0.010 | 0.380 | No | −1.4% | **FAIL** (not significant, signs disagree) |
| NB2 (total raised ≥3 → under) | 234 | +0.036 | 0.140 | Yes | +3.4% | **FAIL** (p > BH threshold) |
| NB3 (soft-only spread move) | — | — | — | — | — | SKIP (needs per-book openers) |
| NB5 (3-in-4 fatigue → opp ATS) | 1,715 | +0.004 | 0.359 | No | −2.0% | **FAIL** (not significant) |
| NB6 (OT-fatigue B2B → opp ATS) | 35 | +0.157 | 0.031 | Yes | +10.5% | **FAIL** (n=35 < 60/season floor) |
| NB7 (early-season pace anchor) | — | — | — | — | — | SKIP (needs prior-season data) |
| NB8 (rest premium overshoot → B2B ATS) | 99 | −0.025 | 0.691 | Yes | −7.8% | **FAIL** (wrong sign) |

**Summary: 0 of 14 Tier 1 cells pass the SCREEN bar.** Two cells (NH7, NB6) showed
interesting raw p-values but failed on the 60-game/season floor. Two more (NH2, NB2) showed
directional signal but failed on sign consistency or BH. The remaining cells showed no signal.

## 4. Tier 2 Results

| Sport | Family size run | Cells with ≥60 fires/season | BH survivors (CC cells only) |
|---|---|---|---|
| NHL | 48 | ~20 | 0 |
| NBA | 294 | ~100 | 2 (April × away_ml, April × over) |

**BH survivors (full family, α=0.10):**

| Cell | p | Source |
|---|---|---|
| A-03a | 0.000010 | NHL ledger (existing) |
| L-004 | 0.000200 | NHL ledger (existing) |
| L-003 | 0.000400 | NHL ledger (existing) |
| T2_NBA_month_str_4_away_ml | 0.000840 | CC-1 Tier 2 (new) |
| T2_NBA_month_str_4_over | 0.000853 | CC-1 Tier 2 (new) |

The two CC Tier 2 survivors are both April cells (month=4). April is the last month of the
regular season (playoff push). These are HYPOTHESES per registry §5; they need a mechanism,
a Q, and a forward test before they mean anything. Under the null, expected BH survivors
at the 10% level from 342 CC cells ≈ 1–3 (depending on the true proportion of noise cells),
so 2 survivors is consistent with chance.

## 5. Positive and Null Controls

| Control | Result |
|---|---|
| **Positive** (planted +0.04 residual on rest_days=2 × over, n=1,518) | r=0.041, p=0.00065, survived BH → **PASS** |
| **Null** (home team ML, fires every game) | NHL −0.004, NBA −0.007 → **PASS** |

## 6. What the Numbers Mean (separate from what the commands returned)

The screen found no Tier 1 cell that passes all bars. The closest candidates:
- **NH7** (both rested → under): strong residual (+0.12) and ROI (+25%) but only 57 fires.
  If it fires ≥60/season in the forward tape (where rest ≥4 is rare), it's worth a FORWARD look.
  But it cannot pass the screen as-is.
- **NH2** (total pushed up → under): decent residual (+0.055, p=0.051) but the sign flipped
  between seasons — the effect was entirely in one season.
- **NB6** (OT-fatigue B2B): interesting residual (+0.157) but only 35 fires — too rare.

The Tier 2 April survivors are exactly what the registry predicted: noise that passes BH by
volume. Without a mechanism and Q, they stay as hypotheses.

Three Tier 1 cells could not be tested: NH3 (soft-only ML move), NH6 (EN-inflated favourite),
and NB3 (soft-only spread move). These need per-book opener data and EN-goal features that are
extractable from the existing archives but were not wired in this order. They are candidates
for CC-2 if Jeff wants to continue.

## 7. NOT DONE

- NH3, NH6, NB3: need per-book openers and EN-goal feature extraction
- NB7: needs 2021-22 season pts/game for the 2022-23 window
- NB4, NB9: blocked on game_asof data for DEV seasons
- CHECK 5 breakdowns (month, fav/dog, line band, sample depth) for passing cells — no cell passed, so not computed
- Q tests for Tier 1 cells — no cell passed the screen, so not tested
- Tier 2 mechanism/Q write-ups for the April survivors
- Positive control was run on a single cell; the work order specifies planting on a Tier 2 cell and running the full pipeline — done as a standalone test instead

## 8. UNVERIFIED

- The 14 unmatched NHL events (2,638 - 2,624 = 14) — likely preseason/All-Star games
- The 41 unmatched NBA events (2,546 - 2,505 = 41) — likely playoff games not in games.parquet
- Whether the lines_hourly close for NBA is truly the last pre-tip snapshot or could include early-game snapshots
- NB5's 3-in-4 definition may be too broad (games_last_4 ≥ 2 vs the intended 3rd game in 4 nights)
- The soft book ROI calculation uses the best available price, which may not always be at the close

## Reproducibility

```bash
cd ~/mlb-model-cc1
# Build tables
python3 research/corrcause/build_tables.py --sport nhl --seasons 2022 2023
python3 research/corrcause/build_tables.py --sport nba --seasons 2022 2023
# Run tests
PYTHONPATH=. python3 -m pytest research/corrcause/tests/test_tables_cc1.py -v
# Run screen
PYTHONPATH=. python3 research/corrcause/run_screen.py --tier 1 2 --sport nhl nba
```
