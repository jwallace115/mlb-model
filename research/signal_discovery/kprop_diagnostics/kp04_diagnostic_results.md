# KP04 Diagnostic Results

**Date:** 2026-03-28
**Final verdict: SIGNAL_WEAKENING**

## Diagnostic A — K Line Quintile Calibration

| Quintile | K Line Range | N | Over HR | ROI | K-Diff |
|----------|-------------|---|---------|-----|--------|
| Q1 | 1.5–4.5 | 68 | **57.4%** | **+11.1%** | +0.53 |
| Q2 | 5.5 | 58 | **58.6%** | **+13.1%** | +0.28 |
| Q3 | 6.5 | 42 | 54.8% | +6.8% | +0.12 |
| Q4 | 7.5–9.5 | 25 | 48.0% | -4.9% | -0.62 |

**Verdict: LINE_CONCENTRATED**

The edge lives at k_line <= 6.5 (Q1-Q3: 57% HR, +10% ROI). At 7.5+ lines (Q4),
hit rate drops to 48% with negative ROI. High-K aces with 7.5+ lines are
efficiently priced; the market mispricing is concentrated in mid-range lines.

## Diagnostic B — Segmentation

| Segment | N | Over HR | ROI |
|---------|---|---------|-----|
| BB 75-85th pctile | 72 | 45.8% | -11.8% |
| **BB 85th+ pctile** | **121** | **62.0%** | **+20.9%** |
| Season 2023 | 72 | 56.9% | +10.1% |
| Season 2024 | 61 | 49.2% | -2.2% |
| Season 2025 | 60 | **61.7%** | **+18.1%** |
| Home pitcher | 76 | 56.6% | +7.7% |
| Away pitcher | 117 | 55.6% | +9.4% |
| Apr-May | 33 | 60.6% | +18.8% |
| Jun-Jul | 70 | 58.6% | +13.6% |
| Aug-Sep | 90 | 52.2% | +1.2% |

**Key findings:**
- BB usage intensity matters enormously: 85th+ pctile hits 62% / +21% ROI,
  while 75-85th is 46% / -12%. The signal is really about *extreme* breaking
  ball pitchers, not moderate ones.
- Home/away split is balanced (no venue bias).
- Edge weakens Aug-Sep (52.2% HR vs 61% Apr-May). Possible market adaptation
  within season.

## Diagnostic C — Decay / Market Adaptation

| Year | Half | N | Over HR | ROI |
|------|------|---|---------|-----|
| 2023 | H1 | 37 | **67.6%** | **+31.0%** |
| 2023 | H2 | 35 | 45.7% | -11.9% |
| 2024 | H1 | 32 | 59.4% | +18.3% |
| 2024 | H2 | 29 | 37.9% | -24.8% |
| 2025 | H1 | 31 | 51.6% | -2.5% |
| 2025 | H2 | 29 | **72.4%** | **+40.1%** |

**Verdict: ADAPTING (2/3 years H2 weaker)**

2023 and 2024 show clear within-season decay (H1 strong → H2 collapse).
2025 reverses this pattern (H2 stronger). The inconsistency is concerning:
- 2023: -43pp H1→H2
- 2024: -43pp H1→H2
- 2025: +43pp H1→H2

The wild swings suggest **small-sample noise**, not systematic adaptation.
N=29-37 per half-season is too thin for reliable decay detection.

## Diagnostic D — Odds Distribution

| Odds Bucket | N | Over HR | ROI |
|-------------|---|---------|-----|
| ≤ -150 | 0 | — | — (excluded by floor) |
| -149 to -121 | 58 | **62.1%** | **+8.2%** |
| -120 to -101 | 58 | 46.6% | -11.7% |
| -100 to +100 | 10 | 50.0% | 0.0% |
| > +100 | 67 | **59.7%** | **+28.0%** |

Edge is bimodal:
- Strong at -149 to -121 (moderate favorites): +8.2% ROI
- Strongest at >+100 (underdogs): +28.0% ROI
- **Dead zone at -120 to -101**: 46.6% HR, -11.7% ROI

The -120 to -101 bucket is where the market prices correctly.
The edge lives at the extremes (moderate favorites and underdogs).

## Diagnostic E — Pitcher Profile

| Archetype | N | Share | Over HR | ROI |
|-----------|---|-------|---------|-----|
| Slider-dominant | 145 | 75% | 55.2% | +7.0% |
| Curveball-dominant | 48 | 25% | **58.3%** | **+13.9%** |

| Handedness | N | Share | Over HR | ROI |
|------------|---|-------|---------|-----|
| RHP | 154 | 80% | 53.9% | +5.2% |
| LHP | 39 | 20% | **64.1%** | **+22.7%** |

**Verdict: DIVERSE** (slider-dom at 75% but curveball-dom outperforms)

LHP pitchers are the standout subgroup: 64.1% HR on N=39. This makes
mechanical sense — LHP breaking balls create more deception against
predominantly RH-heavy lineups.

## Summary

| Diagnostic | Verdict |
|------------|---------|
| A — Quintile calibration | LINE_CONCENTRATED (edge at k_line <= 6.5) |
| B — Segmentation | BB 85th+ drives edge; Aug-Sep weakens |
| C — Decay | ADAPTING (2/3 years H2 weaker, but 2025 reverses) |
| D — Odds | Bimodal: strong at favorites and underdogs, dead at -120 to -101 |
| E — Archetype | DIVERSE (curveball-dom and LHP outperform) |

**FINAL: SIGNAL_WEAKENING**

## Operational Implications

1. **Line filter recommended:** Consider restricting to k_line <= 6.5
   (removes Q4 which is -4.9% ROI). This would cut N from 193 to 168
   but concentrate the edge.

2. **BB intensity matters:** The signal is really about the top 15% of
   breaking ball usage (85th+ pctile), not the top 25%. The 75-85th
   bucket actually loses money.

3. **Odds dead zone:** -120 to -101 odds produce no edge. Consider
   either a tighter price floor (-120 minimum) or only betting at
   specific odds ranges.

4. **Shadow collection should proceed** despite SIGNAL_WEAKENING
   verdict. The 2025 H2 reversal and overall +9.6% ROI suggest the
   signal may be real but noisy at current sample sizes. More data
   will clarify whether the adaptation pattern holds.
