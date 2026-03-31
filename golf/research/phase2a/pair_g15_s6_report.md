# G15 x S6 Interaction Test

Generated: 2026-03-31T08:56:39

## G15 Activation
- Elite density bucket: HIGH (>= 0.1538)
- adj_top_20_edge >= 0.04
- Active in OOS: 871 player-events

## Structural Redundancy Check
- REGULAR_HARD: 219 (25.1%)
- ELEVATED: 464 (53.3%)
- REGULAR_EASY: 164 (18.8%)
- MAJOR: 24 (2.8%)
- WEAK_FIELD: 0 (0.0%)

## 2x2 Cell Results (OOS 2024-2025)

### G15 x S6(REGULAR_HARD) -- TOP_20

| Cell | N | Hit Rate | ROI | CLV | Thin |
|------|---|----------|-----|-----|------|
| NEITHER | 6443 | 17.9% | -22.5% | +0.0% | N |
| G15_ONLY | 652 | 34.2% | -4.6% | -0.9% | N |
| S6_ONLY | 3157 | 14.9% | -20.7% | -0.0% | N |
| G15+S6 | 219 | 22.8% | -18.1% | -0.7% | N |

### G15 x S6(REGULAR_HARD) -- TOP_10

| Cell | N | Hit Rate | ROI | CLV | Thin |
|------|---|----------|-----|-----|------|
| NEITHER | 6483 | 9.3% | -19.1% | +0.0% | N |
| G15_ONLY | 652 | 20.4% | +1.9% | -0.7% | N |
| S6_ONLY | 3152 | 7.1% | -26.2% | -0.0% | N |
| G15+S6 | 219 | 14.2% | -1.1% | -0.5% | N |

### G15 x S6(REGULAR_HARD) -- MAKE_CUT

| Cell | N | Hit Rate | ROI | CLV | Thin |
|------|---|----------|-----|-----|------|
| NEITHER | 2903 | 57.2% | -8.5% | +0.2% | N |
| G15_ONLY | 359 | 70.5% | -4.2% | -0.1% | N |
| S6_ONLY | 1027 | 57.2% | -9.6% | +0.2% | N |
| G15+S6 | 94 | 68.1% | -2.0% | +0.0% | N |

### G15 x S6(ELEVATED) -- TOP_20

| Cell | N | Hit Rate | ROI | CLV | Thin |
|------|---|----------|-----|-----|------|
| NEITHER | 7096 | 14.7% | -23.3% | +0.0% | N |
| G15_ONLY | 407 | 25.6% | -10.8% | -0.8% | N |
| S6_ONLY | 2504 | 23.2% | -18.0% | +0.0% | N |
| G15+S6 | 464 | 36.4% | -5.4% | -0.9% | N |

### G15 x S6(ELEVATED) -- TOP_10

| Cell | N | Hit Rate | ROI | CLV | Thin |
|------|---|----------|-----|-----|------|
| NEITHER | 7091 | 7.4% | -23.6% | -0.0% | N |
| G15_ONLY | 407 | 16.2% | +8.5% | -0.6% | N |
| S6_ONLY | 2544 | 11.9% | -15.4% | +0.0% | N |
| G15+S6 | 464 | 21.1% | -5.3% | -0.7% | N |

### G15 x S6(ELEVATED) -- MAKE_CUT

| Cell | N | Hit Rate | ROI | CLV | Thin |
|------|---|----------|-----|-----|------|
| NEITHER | 3153 | 55.3% | -9.8% | +0.2% | N |
| G15_ONLY | 237 | 68.4% | -1.0% | -0.1% | N |
| S6_ONLY | 777 | 64.9% | -4.8% | -0.0% | N |
| G15+S6 | 216 | 71.8% | -6.8% | -0.1% | N |

### G15 x S6(REGULAR_EASY) -- TOP_20

| Cell | N | Hit Rate | ROI | CLV | Thin |
|------|---|----------|-----|-----|------|
| NEITHER | 6757 | 18.1% | -20.5% | -0.0% | N |
| G15_ONLY | 707 | 31.8% | -10.5% | -0.8% | N |
| S6_ONLY | 2843 | 14.1% | -25.3% | +0.0% | N |
| G15+S6 | 164 | 29.3% | +2.9% | -0.9% | N |

### G15 x S6(REGULAR_EASY) -- TOP_10

| Cell | N | Hit Rate | ROI | CLV | Thin |
|------|---|----------|-----|-----|------|
| NEITHER | 6792 | 9.1% | -21.7% | -0.0% | N |
| G15_ONLY | 707 | 18.8% | -4.0% | -0.6% | N |
| S6_ONLY | 2843 | 7.4% | -20.6% | +0.0% | N |
| G15+S6 | 164 | 18.9% | +23.2% | -0.7% | N |

### G15 x S6(REGULAR_EASY) -- MAKE_CUT

| Cell | N | Hit Rate | ROI | CLV | Thin |
|------|---|----------|-----|-----|------|
| NEITHER | 2651 | 58.3% | -9.2% | +0.1% | N |
| G15_ONLY | 334 | 71.0% | -4.4% | -0.1% | N |
| S6_ONLY | 1279 | 55.0% | -8.0% | +0.3% | N |
| G15+S6 | 119 | 67.2% | -2.0% | -0.0% | N |

## Interaction Strength

| S6 Class | Market | N(combo) | ROI(combo) | ROI(G15) | ROI(S6) | HR Ratio | ROI Ratio | Filter | Classification |
|----------|--------|----------|-----------|---------|---------|----------|-----------|--------|----------------|
| REGULAR_HARD | top_20 | 219 | -18.1% | -4.6% | -20.7% | 0.73 | 6.72 | FAIL | MULTIPLICATIVE |
| REGULAR_HARD | top_10 | 219 | -1.1% | +1.9% | -26.2% | 0.78 | 0.22 | FAIL | INTERFERENCE |
| REGULAR_HARD | make_cut | 94 | -2.0% | -4.2% | -9.6% | 0.97 | 0.37 | PASS | INTERFERENCE |
| ELEVATED | top_20 | 464 | -5.4% | -10.8% | -18.0% | 1.07 | 0.98 | PASS | ADDITIVE_FILTER |
| ELEVATED | top_10 | 464 | -5.3% | +8.5% | -15.4% | 1.02 | -0.32 | FAIL | INTERFERENCE |
| ELEVATED | make_cut | 216 | -6.8% | -1.0% | -4.8% | 0.92 | -1.73 | FAIL | INTERFERENCE |
| REGULAR_EASY | top_20 | 164 | +2.9% | -10.5% | -25.3% | 1.05 | -0.19 | PASS | INTERFERENCE |
| REGULAR_EASY | top_10 | 164 | +23.2% | -4.0% | -20.6% | 1.10 | -8.30 | PASS | INTERFERENCE |
| REGULAR_EASY | make_cut | 119 | -2.0% | -4.4% | -8.0% | 0.99 | 0.64 | PASS | INTERFERENCE |
