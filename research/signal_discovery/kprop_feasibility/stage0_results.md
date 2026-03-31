# K Prop Stage-0 Feasibility Screen

**Date:** 2026-03-28
**Purpose:** Does raw data show even a hint of directional edge before investing in full signal testing?
**Threshold:** Must reach ~53-54% directional hit rate to have any chance of overcoming vig (~8pp ROI hurdle).

## Market Baseline

| Metric | Value |
|--------|-------|
| K Over ROI (blind) | -7.39% |
| K Under ROI (blind) | -4.47% |
| Over hit rate | 48.67% |
| Under hit rate | 51.33% |

## Signal Family 1 — Workload Compression (K UNDER)

**Hypothesis:** Pitchers on short rest after heavy workload have reduced leash/effectiveness, leading to fewer Ks.

| Subset | N | Under HR | Mean Delta | Verdict |
|--------|---|----------|-----------|---------|
| A: rest=4 + prior_pitches>=105 | 0 | — | — | DATA_GAP |
| B: rest<=4 + season_avg_IP>=5.5 | 1 | 1.000 | +0.50 | N=1 (unusable) |
| C: prior_pitches>=110 (any rest) | **73** | **0.5616** | **+0.21** | **PROMISING** |
| (ctx) rest=4 (any workload) | 5 | 0.800 | +0.70 | N=5 (unusable) |
| (ctx) prior_pitches>=100 (any rest) | 1,264 | 0.5158 | -0.05 | REJECT |

**Family 1 verdict: MARGINAL — one viable subset**

Subset C (prior start 110+ pitches) hits 56.2% under rate on N=73. This clears the 54% feasibility bar. However, N is thin and the broader cut at 100+ pitches collapses to 51.6% (noise). The signal exists only in the extreme tail of workload (110+ pitches), which is rare.

Short rest (4 days) has essentially zero sample in combination with heavy workload — MLB scheduling rarely produces this combination in the K prop dataset era (2023+).

## Signal Family 2 — Weapon Upgrade (K OVER)

**Hypothesis:** Market lags when pitchers improve velocity, add pitches, or shift to breaking balls.

| Subset | N | Over HR | Mean Delta | Verdict |
|--------|---|---------|-----------|---------|
| A: FF velo last 2 >= baseline + 1.0mph | 259 | 0.4903 | -0.03 | **REJECT** |
| B: BB usage last 2 >= baseline + 10pp | 206 | 0.4903 | -0.06 | **REJECT** |
| C: New pitch (>=15% usage, was <5%) | 1 | 1.000 | +0.50 | N=1 (unusable) |
| (ctx) FF velo + 0.5mph | 1,339 | 0.4929 | +0.02 | REJECT |

**Family 2 verdict: REJECT — no viable subset**

Velocity spikes and pitch mix changes show **zero** K over signal. The market prices these changes efficiently — likely because velocity data is publicly available in real time and props adjust rapidly. The "weapon upgrade" hypothesis is empirically dead.

## Signal Family 3 — Pitch Shape Mismatch (K OVER)

**Hypothesis:** When a pitcher's primary weapon targets a lineup weakness, Ks may be underpriced.

| Subset | N | Over HR | Mean Delta | Verdict |
|--------|---|---------|-----------|---------|
| A: BB usage>=30% + opp K%>=avg | 1,738 | 0.5362 | +0.24 | MARGINAL |
| B: FF usage>=50% + opp K%>=avg | 2,465 | 0.5026 | +0.10 | REJECT |
| **C: BB top 25% + opp K% top 25%** | **571** | **0.5534** | **+0.28** | **PROMISING** |
| (ctx) opp K% top 25% (any pitcher) | 2,238 | 0.5362 | +0.24 | MARGINAL |

**Family 3 verdict: PROMISING — one clear viable subset**

Subset C (pitcher breaking ball usage top quartile + opponent K% top quartile) reaches **55.3% over hit rate on N=571**. This is the strongest signal in the screen:
- N is substantial (571 starts)
- Hit rate clears the 54% bar
- Mean delta of +0.28 K per start suggests real systematic mispricing
- The broader cuts (A at 53.6%, context at 53.6%) show the effect is real but concentrated in the extreme mismatch

The mechanism makes sense: high-breaking-ball pitchers facing K-prone lineups create a compounding strikeout environment that the market underweights because props are set primarily from pitcher season K rate, not matchup-specific interactions.

Fastball-heavy pitchers (Subset B) show no such effect — fastball Ks are well-priced.

## Summary

| Family | Best Subset | N | Hit Rate | Verdict |
|--------|------------|---|----------|---------|
| 1 — Workload Compression | C: 110+ pitch prior start | 73 | 56.2% UNDER | MARGINAL (thin N) |
| 2 — Weapon Upgrade | none | — | <50% | REJECT |
| **3 — Pitch Shape Mismatch** | **C: BB top 25% + opp K% top 25%** | **571** | **55.3% OVER** | **PROMISING** |

## Recommendation

**Do NOT close K props permanently.** One signal family shows clear feasibility.

**Carry forward to full safety-layer testing:**
- Family 3, Subset C: Breaking ball mismatch (BB usage top 25% + opponent K% top 25%)
  - Register as KP04
  - Freeze BB usage and opp K% thresholds on 2023
  - Run permutation test with ROI statistic
  - Binding validation on 2025

**Deprioritize:**
- Family 1 Subset C (110+ pitches) — directionally interesting but N=73 is likely too thin for a standalone signal. Could be a weakening filter for K OVER plays rather than a standalone K UNDER signal.
- Family 2 — closed. Velocity/mix changes are efficiently priced.

**Note on vig hurdle:** 55.3% over hit rate translates to roughly breakeven ROI at standard -110 juice. To be profitable, the signal needs to be combined with line shopping (finding -105 or better) or used as a filter on top of existing edge. The raw hit rate alone may not clear the vig after accounting for the 7.4% baseline drag. Full testing with actual DK odds will determine feasibility.
