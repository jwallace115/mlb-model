# C8 Command vs Stuff Archetype — Forensic Lock + Shadow Design
## Date: 2026-04-12

## VERDICT: NO-GO FOR SHADOW

C8 fails the forensic lock. The signal has three fatal problems that disqualify it from shadow deployment.

---

## Phase 0: Object Lock

**Definition**: In close ML games (fav implied .512-.556), classify each starter as "command" (high zone_rate, low whiff_rate) or "stuff" (high whiff_rate, low zone_rate) using rolling-10 Statcast medians. Bet the command side.

**Key parameters**:
- whiff_r10 / zone_r10: rolling 10-start mean, shift(1), min_periods=5
- Classification: median split (NOT fixed thresholds)
- Source: `pitcher_statcast_per_start_starters_only.parquet`

## Phase 1: Matched Sample

| Phase | N | WR | ImpWR | Resid | ROI |
|-------|---|----|----|-------|-----|
| Discovery (22-23) | 130 | 0.5385 | 0.4934 | +0.0450 | +4.97% |
| ..2022 | 46 | 0.5870 | 0.4905 | +0.0964 | +13.76% |
| ..2023 | 88 | 0.5227 | 0.4985 | +0.0242 | +1.13% |
| Validation (24) | 83 | 0.5060 | 0.4880 | +0.0180 | +1.26% |
| OOS (25) | 55 | 0.5273 | 0.4931 | +0.0342 | +3.48% |

Reproduced exactly. All 4 seasons positive residual.

### By Side
| Orientation | N | WR | Resid | ROI |
|-------------|---|----|----|-----|
| Bet home | 127 | 0.4724 | -0.0311 | -8.40% |
| Bet away | 132 | 0.5530 | +0.0677 | +9.43% |
| HomeFav+BetHome | 69 | 0.3913 | -0.1452 | -30.10% |
| HomeFav+BetAway | 93 | 0.5484 | +0.0845 | +13.12% |
| HomeDog+BetHome | 58 | 0.5690 | +0.1046 | +17.42% |
| HomeDog+BetAway | 39 | 0.5641 | +0.0276 | +0.63% |

**CRITICAL**: The entire signal lives in "bet away" (+9.43% ROI). Betting home = -8.40%. This is a HOME FIELD ADVANTAGE FADE, not a command-vs-stuff signal.

## Phase 2: Fragility Audit

### Team Concentration
- 29 unique teams represented (good breadth)
- Top 5 teams: 90/259 = 34.7% (acceptable)
- SEA (24), STL (18), TOR (18), HOU (15), CHC (15) lead

### Pitcher Concentration
- 116 unique command-side pitchers (good breadth)
- Top 5 pitchers: 43/259 = 16.6% (acceptable)
- No single pitcher dominates

### Season Stability
- 2022: +13.76% (N=46, small)
- 2023: +1.13% (N=88)
- 2024: +1.26% (N=83)
- 2025: +3.48% (N=55, small)
- Declining magnitude. 2022 drives headline numbers.

## Phase 3: Interaction Diagnostic — FATAL FINDING #1

Neither component works alone:

| Test | Disc ROI | Val ROI | OOS ROI |
|------|----------|---------|---------|
| Command-only (bet higher zone) | -12.47% | -5.32% | -9.41% |
| Anti-stuff (bet lower whiff) | -0.70% | -6.20% | -8.31% |
| Zone gap Q75 | +6.14% | -9.82% | +0.34% |
| Whiff gap Q75 | -0.23% | -7.24% | -5.62% |
| **C8 interaction** | **+4.97%** | **+1.26%** | **+3.48%** |

The interaction outperforms components, which is theoretically encouraging. But neither component has standalone validity, meaning the "interaction" may be selecting a specific subset that happens to be profitable by chance.

## Phase 4: Micro-Band Stability — FATAL FINDING #2

| Price Band | N | WR | Resid | ROI |
|------------|---|----|----|-----|
| 0.512-0.525 | 62 | 0.5645 | +0.0658 | +9.23% |
| 0.525-0.540 | 75 | 0.4533 | -0.0362 | -10.60% |
| 0.540-0.556 | 122 | 0.5246 | +0.0297 | +3.29% |

The middle band (0.525-0.540) is **negative**. The signal is not monotonic across price. This is a hallmark of noise, not a structural edge.

## Phase 5: Live Feasibility

### Data Source
- whiff_rate and zone_rate are **Statcast pitch-level metrics**
- NOT available in pitcher_game_logs (PGL)
- Must be pulled from Baseball Savant per-start data

### PGL Proxy Correlation
- corr(PGL K%, Statcast whiff_rate) = 0.657 (moderate)
- corr(PGL BB%, Statcast zone_rate) = -0.367 (weak)

### PGL K%/BB% Proxy C8 — FAILS COMPLETELY

| Phase | N | WR | Resid | ROI |
|-------|---|----|----|-----|
| Discovery | 96 | 0.4792 | -0.0149 | -6.90% |
| Validation | 43 | 0.4186 | -0.0686 | -16.30% |
| OOS | 59 | 0.4746 | -0.0086 | -3.70% |

The PGL proxy produces negative ROI in all phases. The signal does NOT transfer to implementable features.

## Phase 6: Median Leak Diagnostic — FATAL FINDING #3

C8 uses within-sample medians for classification. When we FREEZE the discovery medians and apply them forward:

| Phase | N | WR | Resid | ROI |
|-------|---|----|----|-----|
| Discovery | 127 | 0.5433 | +0.0500 | +5.93% |
| Validation | 83 | 0.5783 | +0.0888 | +14.61% |
| **OOS** | **53** | **0.4528** | **-0.0471** | **-12.06%** |

**OOS collapses to -12% ROI with frozen medians.** The original OOS result (+3.48%) was inflated by letting 2025 data set its own medians (a form of lookahead).

## Fatal Problems Summary

1. **Median leak**: C8's within-sample median classification is a soft lookahead. Frozen medians kill OOS.
2. **Micro-band instability**: The middle price band (0.525-0.540) is negative. Non-monotonic = noise.
3. **Proxy failure**: Cannot replicate with PGL data. Statcast per-start pipeline adds operational complexity for a signal that may not be real.
4. **Small sample**: N=55 OOS is far below the 150-game threshold.
5. **Side asymmetry**: All profit comes from "bet away" orientation. The signal may be capturing HFA miscalibration, not pitcher archetype.

## Phase 7: Monitoring Rules
N/A — signal does not qualify for shadow.

## Phase 8: Go/No-Go

### GO/NO-GO: NO-GO

C8 does not survive forensic examination. The within-sample median leak is disqualifying on its own. Combined with micro-band instability, proxy failure, small N, and side asymmetry, there is no path to a credible shadow.

### Recommendation
- Archive C8 results for reference
- Do NOT build shadow infrastructure
- If Statcast per-start data becomes available in the live pipeline for other reasons, revisit with fixed thresholds and a minimum N=200 OOS requirement
- The Phase 3 discovery board now has **zero actionable survivors**: C8 (sole KEEP) is killed by forensic lock
