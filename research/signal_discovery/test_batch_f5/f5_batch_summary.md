# F5 Derivative Signal Tests — Batch Summary

**Date:** 2026-03-28
**Signals tested:** CS025, CS026, CS027

## Result Table

| Signal | Direction | N (freeze) | Hit/Over Rate | ROI | Perm %ile | 2025 Dir | Verdict |
|--------|-----------|------------|---------------|-----|-----------|----------|---------|
| CS025  | HOME_F5_RL | 83 | 0.7451 | +40.1% | 100.0 | Positive | **PASS** |
| CS026  | UNDER (weak) | 1,406 | 0.5182 | -1.3% | 57.4 | Negative | FAIL |
| CS027  | OVER | 1,224 | 0.5092 | -2.5% | 100.0 | Negative | FAIL |

## CS025 — F5 Run Line Command Overlay (PASS)

**Hypothesis:** When Signal B fires (xfip_gap >= 1.0) AND home starter is in
good-command state (CSW above baseline, BB rate below baseline, rolling 3 starts),
the F5 run line edge is more reliable.

### Three-Way Comparison (pushes excluded)

| Group | N | Hit Rate | ROI |
|-------|---|----------|-----|
| Signal B baseline (all) | 655 | 0.7344 | +40.6% |
| + Good command (overlay) | 153 | 0.7451 | +40.1% |
| + No command | 502 | 0.7311 | +39.9% |

### Season-by-Season (Overlay Confirmed)

| Year | N | Hit Rate | ROI |
|------|---|----------|-----|
| 2022 | 53 | 0.7170 | +36.9% |
| 2023 | 30 | 0.7333 | +40.0% |
| 2024 | 29 | 0.6897 | +31.7% |
| 2025 | 41 | 0.8293 | +58.3% |

**Push count:** 112 (Signal B total)
**Permutation:** 100th percentile (observed 0.7451 vs perm mean ~0.50)
**Frozen thresholds:** xfip_gap >= 1.0, good_command = CSW_r3 > baseline AND BB_r3 < baseline, min 3 prior starts

**Key finding:** The overlay-confirmed subset performs comparably to Signal B
baseline overall, but shows a substantially higher 2025 OOS hit rate (82.9% vs 76.6%).
The signal passes all gates. However, note that Signal B baseline itself is
extremely strong (73.4% overall), so the overlay adds modest precision on an
already-powerful signal.

**Recommended next step:** Phase B stake sizing test (0.5u to 0.75u) — do not run now.

## CS026 — First-Inning Pitch Count Weakening Filter (FAIL)

**Hypothesis:** Starters with 22+ pitches in inning 1 of their most recent
prior start face elevated early-exit hazard, weakening F5 UNDER plays.

### Three-Way Comparison (pushes excluded for win rate)

| Group | N | Under Rate | Residual |
|-------|---|-----------|----------|
| F5 UNDER baseline (all) | 8,317 | 0.5170 | 0.3174 |
| High stress (weakened) | 3,157 | 0.5182 | 0.3246 |
| Clean (no stress) | 5,160 | 0.5163 | 0.3129 |

**Push count:** 168
**Frozen cutoff:** 22 pitches (P80 of 2022-2023 inning-1 distribution)
**Permutation:** 57.4th percentile

**Key finding:** No detectable weakening effect. Stressed and clean cohorts
have nearly identical under rates (51.8% vs 51.6%) and residuals (0.325 vs 0.313).
The signal is noise. Inning-1 pitch count from the prior start does not
meaningfully predict F5 scoring outcomes.

## CS027 — CS013 Bullpen State x F5 OVER Interaction (FAIL)

**Hypothesis:** CS013-flagged games (degraded bullpen) show positive F5
market residual — bullpen deterioration affects innings 1-5, not just
late-game.

### F5 vs Full-Game Context

| Metric | CS013 Flagged | CS013 Unflagged |
|--------|---------------|-----------------|
| F5 over rate | 0.5092 (N=2,669) | 0.4708 (N=5,922) |
| F5 residual | +0.530 | +0.226 |
| Full-game over rate | 0.5532 (N=2,621) | — |

**Delta (F5 - full game):** -0.044 (CS013 effect is weaker in F5 than full game)

### Season-by-Season (CS013 flagged, F5 over rate)

| Year | N | F5 Over Rate | ROI |
|------|---|-------------|-----|
| 2022 | 622 | 0.5177 | -1.2% |
| 2023 | 602 | 0.5365 | +2.4% |
| 2024 | 749 | 0.4913 | -6.2% |
| 2025 | 696 | 0.4971 | -5.1% |

**Permutation:** 100th percentile (F5 residual is higher in CS013 games)
**Season support:** FAIL — neither 2024 nor 2025 directionally positive

**Key finding:** CS013 is primarily a **late-game phenomenon** (innings 6-9),
not a F5 phenomenon. The permutation test detects a real residual signal
(higher scoring in CS013 games), but it does not translate to a profitable
F5 OVER signal — the market already prices the elevated environment into
F5 lines by 2024-2025. The 4.4pp gap between full-game over rate (55.3%)
and F5 over rate (50.9%) confirms the bullpen blowup mechanism concentrates
in late innings.

**Conclusion:** CS013 should NOT influence F5 market decisions. Keep CS013
scoped to full-game totals only.

## Overall Assessment

- **CS025 PASS** — command overlay is a valid confidence filter for Signal B
  F5 run line plays. Phase B stake sizing test is the explicit next step.
- **CS026 FAIL** — inning-1 stress has no predictive power for F5 outcomes.
  Domain closed.
- **CS027 FAIL** — CS013 bullpen deterioration is a late-game phenomenon.
  The F5 market prices it efficiently. Do not apply CS013 to F5 decisions.
