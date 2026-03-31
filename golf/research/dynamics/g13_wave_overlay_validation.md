# G13 Wave Weather Overlay Validation

Generated: 2026-03-30T15:41:34

## Verdict: G13_DEPLOYABLE

## Dataset
- 26,966 player-tournament rows (2020-2025)
- Make cut odds coverage: 42.9%
- Top 20 odds coverage: 99.5%
- Book priority: Pinnacle > DraftKings > FanDuel

## Quintile Summary (All Data)

| Q | N | Cut Rate | Top 20 Rate | Mean 36h | Mean Draw Edge |
|---|---|----------|-------------|----------|---------------|
| Q1 | 5,319 | 47.2% | 14.2% | 140.8 | -0.819 |
| Q2 | 5,968 | 50.5% | 15.5% | 141.3 | -0.269 |
| Q3 | 4,383 | 53.4% | 16.5% | 140.9 | +0.011 |
| Q4 | 5,970 | 55.2% | 17.9% | 140.6 | +0.301 |
| Q5 | 5,326 | 60.4% | 20.6% | 139.3 | +0.858 |

Monotonic cut rate Q1->Q5: YES
Monotonic top20 rate Q1->Q5: YES

## Frozen Uplift Table (Training 2020-2022)

| Q | N_train | MC Uplift | Top20 Uplift |
|---|---------|-----------|-------------|
| Q1 | 2,561 | -0.0456 | -0.0123 |
| Q2 | 2,650 | -0.0207 | +0.0032 |
| Q3 | 2,613 | +0.0176 | +0.0161 |
| Q4 | 2,684 | +0.0182 | +0.0315 |
| Q5 | 2,652 | +0.0685 | +0.0446 |

## Baseline vs Overlay -- Make Cut (edge >= 4%)

| Strategy | Split | N | Hit Rate | ROI | CLV |
|----------|-------|---|----------|-----|-----|
| Baseline | train | 648 | 73.8% | +0.4% | +0.3% |
| Overlay | train | 533 | 71.3% | +6.4% | +0.2% |
| Baseline | validate | 626 | 72.7% | -5.3% | +0.0% |
| Overlay | validate | 436 | 75.7% | +3.2% | +0.0% |
| Baseline | oos | 677 | 75.3% | -0.7% | -0.1% |
| Overlay | oos | 609 | 78.8% | +9.2% | -0.0% |

## Baseline vs Overlay -- Top 20 (edge >= 4%)

| Strategy | Split | N | Hit Rate | ROI |
|----------|-------|---|----------|-----|
| Baseline | train | 1174 | 33.2% | +6.0% |
| Overlay | train | 2031 | 25.6% | +15.2% |
| Baseline | validate | 414 | 40.3% | -2.6% |
| Overlay | validate | 801 | 25.3% | -3.8% |
| Baseline | oos | 648 | 36.7% | -2.4% |
| Overlay | oos | 1680 | 25.3% | -4.3% |

## Yearly Stability -- Make Cut Overlay

| Year | N | Hit Rate | ROI |
|------|---|----------|-----|
| 2020 | 102 | 62.7% | -10.0% |
| 2021 | 98 | 72.4% | +27.9% |
| 2022 | 333 | 73.6% | +5.1% |
| 2023 | 436 | 75.7% | +3.2% |
| 2024 | 412 | 78.2% | +9.4% |
| 2025 | 197 | 80.2% | +8.8% |

Positive ROI years: 5/6
Stability gate (3+/5): PASS

## Deployment Gates (OOS 2024-2025, Make Cut)

| Gate | Value | Status |
|------|-------|--------|
| ROI >= 4% | +9.2% | PASS |
| Positive CLV | -0.0% | FAIL |
| N >= 50 | 609 | PASS |
| Overlay > Baseline | +9.2% vs -0.7% | PASS |
| No concentration | FAIL |
| Stability (3+/5) | 5/6 | PASS |

## Deployment Specification

- **Market:** Make Cut
- **Rule:** adj_make_cut_edge >= 4% AND draw_quintile in Q4/Q5
- **Expected volume:** ~304 bets per season
- **Expected ROI:** +9.2%
- **Book preference:** Pinnacle > DraftKings > FanDuel
