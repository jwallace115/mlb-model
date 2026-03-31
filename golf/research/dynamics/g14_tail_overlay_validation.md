# G14 Tail Balance Overlay Validation

Generated: 2026-03-30T17:12:57

## Dataset
- Player-events: 28,430 (2020-2025)
- tail_balance_50 coverage: 100.0%
- Splits: train=13830, validate=5006, oos=9594

## Frozen Cutpoints (2020-2022)
### Skill Bands
- Below: SG < -0.327
- Average: -0.327 to 0.119
- Good: 0.119 to 0.568
- Elite: >= 0.568

### Tail Balance Terciles by Band
- Elite: LOW<0.1200, HIGH>=0.1800
- Good: LOW<0.0400, HIGH>=0.0800
- Average: LOW<-0.0400, HIGH>=0.0000
- Below: LOW<-0.1400, HIGH>=-0.0800

## Frozen Uplift Table (Training 2020-2022)

| Band | Bucket | N | T10 Uplift | T5 Uplift | Win Uplift |
|------|--------|---|------------|-----------|------------|
| Elite | LOW | 931 | +0.0216 | +0.0082 | -0.00208 |
| Elite | MEDIUM | 1215 | +0.0198 | +0.0166 | +0.00441 |
| Elite | HIGH | 1312 | +0.0404 | +0.0355 | +0.00675 |
| Good | LOW | 1074 | +0.0032 | -0.0018 | -0.00563 |
| Good | MEDIUM | 1087 | +0.0236 | +0.0145 | -0.00059 |
| Good | HIGH | 1296 | +0.0148 | +0.0147 | -0.00279 |
| Average | LOW | 1126 | +0.0158 | +0.0077 | -0.00013 |
| Average | MEDIUM | 659 | +0.0192 | +0.0150 | +0.00016 |
| Average | HIGH | 1672 | +0.0001 | -0.0001 | -0.00156 |
| Below | LOW | 1049 | +0.0099 | +0.0082 | +0.00103 |
| Below | MEDIUM | 1184 | +0.0083 | +0.0026 | +0.00268 |
| Below | HIGH | 1225 | +0.0046 | +0.0023 | -0.00030 |

## Baseline vs Overlay (OOS 2024-2025)

| Market | Strategy | Threshold | N | Hit Rate | ROI | CLV |
|--------|----------|-----------|---|----------|-----|-----|
| top_10 | Baseline | 4% | 263 | 30.0% | -12.8% | -1.1% |
| top_10 | Overlay | 4% | 640 | 25.2% | -3.7% | -0.4% |
| top_10 | Baseline | 6% | 74 | 52.7% | +20.0% | -1.1% |
| top_10 | Overlay | 6% | 278 | 33.8% | -3.0% | -0.7% |
| top_5 | Baseline | 4% | 72 | 33.3% | +10.8% | -0.8% |
| top_5 | Overlay | 4% | 433 | 17.8% | +3.2% | -0.4% |
| top_5 | Baseline | 6% | 18 | 61.1% | +27.8% | -0.7% |
| top_5 | Overlay | 6% | 114 | 30.7% | +11.6% | -0.8% |
| win | Baseline | 4% | 2 | 50.0% | +7.0% | +0.4% |
| win | Overlay | 4% | 6 | 16.7% | -64.3% | +0.6% |
| win | Baseline | 6% | 1 | 100.0% | +114.0% | +0.4% |
| win | Overlay | 6% | 1 | 100.0% | +114.0% | +0.4% |

## Field Strength Robustness (OOS, edge >= 4%)

| Market | Field | N | Hit Rate | ROI |
|--------|-------|---|----------|-----|
| top_10 | strong | 416 | 29.3% | +6.5% |
| top_10 | weak | 224 | 17.4% | -22.6% |
| top_5 | strong | 310 | 20.6% | +17.5% |
| top_5 | weak | 123 | 10.6% | -32.7% |
| win | strong | 6 | 16.7% | -64.3% |
| win | weak | 0 | 0.0% | +0.0% |

## Yearly Stability

### TOP_10 (edge >= 4%, HIGH tb)
| Year | N | Hit Rate | ROI |
|------|---|----------|-----|
| 2020 | 332 | 28.6% | +17.1% |
| 2021 | 168 | 26.8% | -13.3% |
| 2022 | 343 | 29.4% | +1.1% |
| 2023 | 373 | 29.5% | -1.7% |
| 2024 | 325 | 25.2% | -11.0% |
| 2025 | 315 | 25.1% | +3.9% |

### TOP_5 (edge >= 4%, HIGH tb)
| Year | N | Hit Rate | ROI |
|------|---|----------|-----|
| 2020 | 247 | 17.4% | -10.8% |
| 2021 | 64 | 18.8% | -22.0% |
| 2022 | 234 | 23.9% | +32.4% |
| 2023 | 258 | 20.9% | +27.4% |
| 2024 | 211 | 19.0% | -12.8% |
| 2025 | 222 | 16.7% | +18.5% |

### WIN (edge >= 4%, HIGH tb)
| Year | N | Hit Rate | ROI |
|------|---|----------|-----|
| 2020 | 4 | 0.0% | -100.0% |
| 2021 | 8 | 12.5% | -42.4% |
| 2022 | 3 | 33.3% | +177.7% |
| 2023 | 7 | 0.0% | -100.0% |
| 2024 | 4 | 25.0% | -46.5% |
| 2025 | 2 | 0.0% | -100.0% |

## Final Verdict

| Market | Verdict |
|--------|---------|
| Top 10 | G14_DEPLOYABLE |
| Top 5 | G14_DEPLOYABLE |
| Win | G14_WATCHLIST |
