# KP04 Refinement Comparison

**Date:** 2026-03-28
**Purpose:** Compare three versions of the breaking ball mismatch signal before full registration.

## Breaking Ball Definition

Breaking ball = SL + ST + SV + CU + KC + CS (slider, sweeper, curveball families).
Sweeper (ST, SV) explicitly included — both tags present in Statcast data.
P75 threshold frozen on 2023: **BB% >= 0.3842**

## Frozen Thresholds (2023 only)

| Threshold | Value |
|-----------|-------|
| BB% P75 | 0.3842 |
| Team K% STD P75 | 0.2422 |
| Lineup K% P75 | 0.2431 |
| Lineup K% P25 | 0.2021 |
| Lineup contact rate P75 | 0.2506 |

## Summary Table

| Version | N | Flag Rate | Hit Rate | ROI | K-Line Error | 2025 N | 2025 HR | Mean Odds |
|---------|---|-----------|----------|-----|-------------|--------|---------|-----------|
| Baseline (all starts) | 8,650 | 100% | 0.4867 | -7.38% | +0.028 | 3,239 | 0.4955 | -34 |
| **V1 Original (team K%)** | **381** | **4.4%** | **0.5459** | **+4.47%** | **+0.164** | **75** | **0.6000** | **-32** |
| **V2 Lineup K%** | **295** | **3.4%** | **0.5797** | **+10.35%** | **+0.368** | **92** | **0.6413** | **-43** |
| V3 Lineup + Leash | 124 | 1.4% | 0.5323 | +0.67% | +0.040 | 33 | 0.5455 | -41 |
| Mirror UNDER | 104 | 1.2% | 0.5481 | +1.78% | -0.144 | 50 | 0.4800 | -65 |

## Decision Rule Results

| Version | Verdict | Reasoning |
|---------|---------|-----------|
| **V1 Original** | **ADVANCE** | HR=54.6%, N=381, flag=4.4%, ROI=+4.5% (vs -7.4% baseline) |
| **V2 Lineup K%** | **ADVANCE** | HR=58.0%, N=295, flag=3.4%, ROI=+10.4% (vs -7.4% baseline) |
| V3 Lineup + Leash | MARGINAL | HR=53.2% (<54%), flag=1.4% (<3%) — leash filter too restrictive |
| Mirror UNDER | MARGINAL | flag=1.2% (<3%) — too few games to be useful |

## Analysis

### V1 → V2 Improvement

Replacing team K% with lineup K% narrows the population (381 → 295) but
meaningfully sharpens the signal:

| Metric | V1 (team K%) | V2 (lineup K%) | Delta |
|--------|-------------|---------------|-------|
| Hit rate | 54.6% | **58.0%** | **+3.4pp** |
| ROI | +4.5% | **+10.4%** | **+5.9pp** |
| K-line error | +0.164 | **+0.368** | +0.204 |
| 2025 HR | 60.0% | **64.1%** | +4.1pp |

The lineup refinement works. When you know the actual lineup (not just
the team roster), the mismatch signal becomes substantially stronger.
The 2025 OOS subsample is particularly strong: 64.1% on N=92.

### V3 — Leash floor hurts

Adding IP >= 5.2 cuts the sample from 295 to 124 (1.4% flag rate) without
improving hit rate (53.2% vs 58.0%). The leash filter removes games where
the signal works fine. Reject this refinement.

### Mean Odds Check

V2 mean odds = -43 vs baseline -34. The V2 flagged games have slightly
worse odds (books are pricing the K over slightly more aggressively in
these matchups). However, the +10.4% ROI at those actual odds shows the
signal survives the worse juice.

**Flag:** V2 odds are 9 points worse than baseline (>5 point threshold).
This means the market is partially aware of the mismatch. The signal
still clears the vig but the edge is thinner than raw hit rate suggests.

### Mirror — Not viable

The UNDER mirror (BB heavy + low lineup K% + high contact) shows 54.8%
under rate on N=104 — directionally correct but too rare (1.2% flag rate)
to be practically useful. The 2025 subsample reverses to 48.0% (N=50).
Do not carry forward.

## Recommendation

**Register V2 (lineup K%) as KP04 for full safety-layer testing.**

V1 is also viable as a fallback if lineup data has coverage issues on
game day (lineup announcements come late). Consider registering both:
- KP04A: V2 (lineup K%) — primary, sharper signal
- KP04B: V1 (team K%) — fallback for pre-lineup-announcement window

Do NOT register V3 (leash floor adds nothing) or Mirror (too thin).

### Phase progression if KP04 passes safety layer:
1. Permutation test (ROI statistic, 2023 freeze, 2025 binding)
2. Season-by-season stability check
3. Shadow deployment with DraftKings live lines
4. Line shopping integration (Hard Rock may offer better K prop odds)
