# OBJECT 6: Tier / Threshold / STRONG — Clean V1 Revalidation

Model sigma: 4.4237
Total enriched games with lines: 9451
By season: {2022: 2327, 2023: 2328, 2024: 2400, 2025: 2396}


## 2024 (val) — 2400 games with lines

| Threshold | Bets | W | L | P | Win% | ROI |
|-----------|------|---|---|---|------|-----|
| p>=0.53 | 196 | 97 | 94 | 5 | 50.8% | -3.0% |
| p>=0.55 | 108 | 55 | 50 | 3 | 52.4% | +0.0% |
| p>=0.57 | 58 | 30 | 26 | 2 | 53.6% | +2.3% |
| p>=0.59 | 25 | 10 | 13 | 2 | 43.5% | -17.0% |
| p>=0.60 | 19 | 9 | 8 | 2 | 52.9% | +1.1% |
| p>=0.61 | 14 | 8 | 4 | 2 | 66.7% | +27.3% |
| p>=0.63 | 8 | 4 | 3 | 1 | 57.1% | +9.1% |
| p>=0.65 | 5 | 4 | 1 | 0 | 80.0% | +52.7% |

### STRONG tier: p>=0.60 AND |edge|>=1.0
Bets: 19, W-L-P: 9-8-2, Win%: 52.9%, ROI: +1.1%

### p>=0.57 AND |edge|>=0.5
Bets: 58, W-L-P: 30-26-2, Win%: 53.6%, ROI: +2.3%

### Optimal Threshold Search (maximize ROI, min 20 bets)
Best: p>=0.57, 58 bets, W-L: 30-26, Win%: 53.6%, ROI: +2.3%

## 2025 (OOS) — 2396 games with lines

| Threshold | Bets | W | L | P | Win% | ROI |
|-----------|------|---|---|---|------|-----|
| p>=0.53 | 387 | 187 | 181 | 19 | 50.8% | -3.0% |
| p>=0.55 | 248 | 117 | 122 | 9 | 49.0% | -6.5% |
| p>=0.57 | 158 | 78 | 73 | 7 | 51.7% | -1.4% |
| p>=0.59 | 120 | 56 | 57 | 7 | 49.6% | -5.4% |
| p>=0.60 | 97 | 46 | 46 | 5 | 50.0% | -4.5% |
| p>=0.61 | 84 | 40 | 40 | 4 | 50.0% | -4.5% |
| p>=0.63 | 65 | 33 | 30 | 2 | 52.4% | -0.0% |
| p>=0.65 | 47 | 26 | 20 | 1 | 56.5% | +7.9% |

### STRONG tier: p>=0.60 AND |edge|>=1.0
Bets: 97, W-L-P: 46-46-5, Win%: 50.0%, ROI: -4.5%

### p>=0.57 AND |edge|>=0.5
Bets: 158, W-L-P: 78-73-7, Win%: 51.7%, ROI: -1.4%

### Optimal Threshold Search (maximize ROI, min 20 bets)
Best: p>=0.65, 47 bets, W-L: 26-20, Win%: 56.5%, ROI: +7.9%

## 2024+2025 — 4796 games with lines

| Threshold | Bets | W | L | P | Win% | ROI |
|-----------|------|---|---|---|------|-----|
| p>=0.53 | 583 | 284 | 275 | 24 | 50.8% | -3.0% |
| p>=0.55 | 356 | 172 | 172 | 12 | 50.0% | -4.5% |
| p>=0.57 | 216 | 108 | 99 | 9 | 52.2% | -0.4% |
| p>=0.59 | 145 | 66 | 70 | 9 | 48.5% | -7.4% |
| p>=0.60 | 116 | 55 | 54 | 7 | 50.5% | -3.7% |
| p>=0.61 | 98 | 48 | 44 | 6 | 52.2% | -0.4% |
| p>=0.63 | 73 | 37 | 33 | 3 | 52.9% | +0.9% |
| p>=0.65 | 52 | 30 | 21 | 1 | 58.8% | +12.3% |

### STRONG tier: p>=0.60 AND |edge|>=1.0
Bets: 116, W-L-P: 55-54-7, Win%: 50.5%, ROI: -3.7%

### p>=0.57 AND |edge|>=0.5
Bets: 216, W-L-P: 108-99-9, Win%: 52.2%, ROI: -0.4%

### Optimal Threshold Search (maximize ROI, min 20 bets)
Best: p>=0.66, 46 bets, W-L: 27-18, Win%: 60.0%, ROI: +14.5%

## Assessment

Clean V1 UNDER signals show consistently negative ROI across all thresholds.
The contaminated model's apparent edge was driven by lookahead bias in features.
The STRONG tier (p>=0.60, edge>=1.0) does not rescue profitability.

## Verdict: COLLAPSES
All tier definitions lose profitability when V1 is rebuilt on PIT features.
The threshold and STRONG tier structure provided false confidence from contamination.