# Bridge Depletion Research — Phase 1 Report

**Date:** 2026-04-07
**Hypothesis:** Bullpen bridge depletion (top leverage arms unavailable due to recent heavy usage) creates right-tail scoring expansion that the market underprices.
**Verdict:** CLOSE

---

## Phase 1 — Data Audit

**pitcher_game_logs.parquet**: 84,372 rows (64,640 reliever appearances, 19,732 starts), seasons 2022-2026.
- Columns available: game_pk, game_date, season, player_id, player_name, team, home_away, starter_flag, innings_pitched, batters_faced, pitches, runs_allowed, earned_runs, walks, strikeouts, home_runs_allowed.
- Pitches column: min=0, max=112, mean=18.7 for relievers. Adequate for heavy-usage thresholds.
- 1,377 unique relievers across 30 teams.

**game_table.parquet**: 9,715 regular-season games (2022-2025), with actual_total and actual_f5_total.

**market_snapshots.parquet**: 4,855 games with close_total (2024-2025 only, both seasons fully covered).

Team name alignment required mapping 8 abbreviations (SD->SDP, SF->SFG, KC->KCR, TB->TBR, AZ->ARI, CWS->CHW, WSH->WSN, ATH->OAK).

**Coverage: GOOD.** All columns needed for depletion computation are present. 4 full seasons for raw scoring, 2 seasons for market-relative testing.

---

## Phase 2 — Depletion Flag Construction

**Role identification:** Top 3 relievers per team-season by total appearances (high-leverage proxy). Mean appearances for top-3: 63.0. All 30 teams x 4 seasons = 360 team-season-player combos identified.

**Depletion definitions (pregame-safe, using only data before game_date):**
- SOFT_DEPLETED: 2+ of top 3 relievers appeared in last 2 calendar days.
- HARD_DEPLETED: SOFT_DEPLETED and at least 1 of those relievers threw 25+ pitches yesterday.

**Game-level classification:**

| State | N (2022-2025) | % of Games |
|-------|---------------|------------|
| BOTH_DEPLETED | 4,239 | 43.6% |
| HOME_ONLY | 2,031 | 20.9% |
| AWAY_ONLY | 1,855 | 19.1% |
| NEITHER | 1,590 | 16.4% |

HARD depletion (any side): 1,718 games (17.7%).
HARD depletion (both sides): 103 games (1.1%).

**Key observation:** The depletion base rate is extremely high -- 83.6% of all games have at least one side with 2+ top relievers used in the last 2 days. This is the normal state of MLB bullpen management, not an anomaly. Top relievers pitch frequently by definition; having 2 of 3 appear recently is the default, not the exception.

Frequencies are stable across seasons (no single-year dominance).

---

## Phase 3 — Raw Outcome Test

### All seasons (2022-2025), raw scoring:

| State | N | Mean Actual Total |
|-------|---|-------------------|
| BOTH_DEPLETED | 4,239 | 8.910 |
| HOME_ONLY | 2,031 | 8.831 |
| AWAY_ONLY | 1,855 | 8.833 |
| NEITHER | 1,590 | 8.858 |

**No meaningful difference in raw scoring.** The range is 8.831 to 8.910 -- a 0.08-run spread that is noise.

### Market-relative (2024-2025, games with closing lines):

| State | N | Mean Actual | Mean Close | Residual | Over Rate |
|-------|---|-------------|------------|----------|-----------|
| BOTH_DEPLETED | 2,116 | 8.77 | 8.38 | +0.393 | 0.490 |
| HOME_ONLY | 1,017 | 8.99 | 8.39 | +0.592 | 0.501 |
| AWAY_ONLY | 929 | 8.89 | 8.44 | +0.450 | 0.483 |
| NEITHER | 793 | 8.79 | 8.41 | +0.373 | 0.489 |

**All residuals are positive** (closing lines systematically undershoot actuals by ~0.4 runs), but depletion does not differentiate them. Over rates range from 0.483 to 0.501 -- all below the 0.524 breakeven at -110 juice.

HARD depletion slices show no improvement:

| Slice | N | Residual | Over Rate |
|-------|---|----------|-----------|
| HARD_BOTH | 46 | -0.609 | 0.390 |
| HARD_ANY | 819 | +0.542 | 0.500 |
| SOFT_ONLY | 3,197 | +0.449 | 0.490 |
| NEITHER | 793 | +0.373 | 0.489 |

HARD_BOTH actually goes the wrong way (under-performing), though N=46 is meaningless.

Stricter "all 3 depleted" definition also shows nothing:

| Slice | N | Residual | Over Rate |
|-------|---|----------|-----------|
| BOTH_ALL3 | 490 | +0.417 | 0.484 |
| EITHER_ALL3 | 2,237 | +0.391 | 0.477 |
| NEITHER_ALL3 | 2,618 | +0.486 | 0.503 |

### Season split (2024 vs 2025):

**2024:**
- BOTH_DEPLETED: residual +0.504, over_rate 0.513
- NEITHER: residual +0.353, over_rate 0.474

**2025:**
- BOTH_DEPLETED: residual +0.286, over_rate 0.468
- NEITHER: residual +0.394, over_rate 0.506

Direction is inconsistent across seasons. In 2025, NEITHER actually outperforms all depletion states on over rate.

---

## Phase 4 — Conditional Path Check (Short Starts)

Starter IP is post-hoc (not known pregame). Checked anyway to see if depletion matters more when bullpens are actually needed.

**All games, by start length (regardless of depletion):**
- Either starter < 5.5 IP: N=4,494, residual +1.079, over_rate 0.561
- Both starters >= 5.5 IP: N=604, residual -2.133, over_rate 0.204

This is purely mechanical: short starts = bad outings = more runs scored.

**Within short starts only, depletion states are indistinguishable:**
- BOTH_DEPLETED: over_rate 0.557
- HOME_ONLY: over_rate 0.576
- AWAY_ONLY: over_rate 0.551
- NEITHER: over_rate 0.560

Depletion adds zero beyond the mechanical short-start effect.

---

## Phase 5 — Market-Relative Test

| Bucket | N | Over Rate | Implied ROI at -110 |
|--------|---|-----------|---------------------|
| BOTH_DEPLETED | 2,116 | 0.490 | -6.5% |
| HOME_ONLY | 1,017 | 0.501 | -4.3% |
| AWAY_ONLY | 929 | 0.483 | -7.8% |
| HARD_ANY | 865 | 0.495 | -5.6% |
| HARD_BOTH | 46 | 0.390 | -25.5% |

**Best over rate found: 0.501 (HOME_ONLY).** Breakeven at -110 requires 0.524. No bucket approaches profitability.

---

## Phase 6 — Signal Interaction

**CS028 overlap:** CS028 targets home-side reliever quality (blowup probability), not availability. Conceptually orthogonal, but empirically moot since bridge depletion shows no signal. CS028 has fired 0 times in early 2026 season.

**F5 totals:** As expected, depletion has no relationship with F5 scoring. F5 actuals are flat across states (4.95-5.13), with NEITHER actually highest at 5.131 -- confirming that bullpen availability is irrelevant before the 6th inning.

---

## Phase 7 — Concentration Check

Top 5 teams by depletion frequency: CLE (466), HOU (464), TOR (454), CIN (446), SEA (442).
Bottom 5: CHC (357), LAA (368), PIT (373), OAK (373), CHW (374).

The range is narrow (357-466), reflecting that frequent reliever usage is universal. No single team or season drives the (null) result. Concentration check is academic given no signal.

---

## Phase 8 — Practical Framing

**Not applicable.** No signal to frame.

---

## Decision: CLOSE

### Why this fails:

1. **Base rate too high.** 83.6% of games have at least one side with 2+ top relievers used recently. "Depletion" as defined here is the normal operating state of MLB bullpens. Top relievers appear frequently (~63 times/season); having 2 of 3 pitch in the last 48 hours is expected, not exceptional.

2. **No scoring difference.** Raw actual totals are virtually identical across all depletion states (8.83-8.91 range, 0.08-run spread). The market doesn't need to price bridge depletion because it doesn't affect scoring.

3. **No market edge.** Best over rate is 0.501 (HOME_ONLY), well below the 0.524 -110 breakeven. All implied ROIs are negative.

4. **Inconsistent across seasons.** In 2025, NEITHER outperforms all depletion states on over rate. Direction flips year-to-year.

5. **Short-start interaction is mechanical, not a signal.** Within short starts, depletion states are indistinguishable from the baseline.

### Why "availability" differs from "quality":

CS028 and the existing bullpen features in the Phase 9 model target reliever *quality* (xFIP, high-leverage availability scores). Bridge depletion targets *recent usage patterns* -- whether top arms have pitched recently. The data shows that recent usage patterns do not predict scoring outcomes. Modern bullpen management is designed precisely to rotate arms so that depletion doesn't create vulnerabilities; managers rest depleted relievers and substitute from a deep roster.

### Recommendation:

Do not pursue further. The concept is intuitive but empirically void. The existing Phase 9 bullpen features (high_leverage_avail, bullpen_delta, bp_delta_exposure) already capture the aspects of bullpen state that matter for scoring. Bridge depletion as a standalone signal or overlay adds nothing.
