# G13 x S6 Interaction Test

Generated: 2026-03-31T06:47:04

## Wave Data Coverage
- tee_wave R1/R2 coverage: 100.0%
- Wave source: G13_RESEARCH_METHODOLOGY (realized scoring differential)
- Note: Historical G13 validation used realized scoring differential.
  Live production uses weather forecasts. Same methodology as G13 research.

## 2x2 Cell Results (OOS 2024-2025)

### G13 x S6(REGULAR_HARD) -- MAKE_CUT

| Cell | N | Hit Rate | ROI | CLV | Thin |
|------|---|----------|-----|-----|------|
| NEITHER | 2794 | 55.3% | -10.8% | +0.2% | N |
| G13_ONLY | 468 | 78.6% | +8.5% | -0.0% | N |
| S6_ONLY | 980 | 55.0% | -12.0% | +0.2% | N |
| G13+S6 | 141 | 79.4% | +11.8% | -0.0% | N |

### G13 x S6(REGULAR_HARD) -- TOP_20

| Cell | N | Hit Rate | ROI | CLV | Thin |
|------|---|----------|-----|-----|------|
| NEITHER | 6627 | 18.3% | -23.0% | -0.0% | N |
| G13_ONLY | 468 | 34.8% | +9.6% | -0.8% | N |
| S6_ONLY | 3235 | 14.3% | -22.5% | -0.0% | N |
| G13+S6 | 141 | 41.1% | +25.3% | -0.9% | N |

### G13 x S6(REGULAR_HARD) -- TOP_10

| Cell | N | Hit Rate | ROI | CLV | Thin |
|------|---|----------|-----|-----|------|
| NEITHER | 6667 | 9.6% | -20.4% | -0.0% | N |
| G13_ONLY | 468 | 20.5% | +28.9% | -0.6% | N |
| S6_ONLY | 3230 | 6.9% | -26.5% | -0.0% | N |
| G13+S6 | 141 | 22.0% | +19.8% | -0.6% | N |

### G13 x S6(ELEVATED) -- MAKE_CUT

| Cell | N | Hit Rate | ROI | CLV | Thin |
|------|---|----------|-----|-----|------|
| NEITHER | 3038 | 53.9% | -11.3% | +0.2% | N |
| G13_ONLY | 352 | 76.1% | +9.2% | +0.1% | N |
| S6_ONLY | 736 | 60.7% | -10.3% | +0.0% | N |
| G13+S6 | 257 | 82.5% | +9.3% | -0.2% | N |

### G13 x S6(ELEVATED) -- TOP_20

| Cell | N | Hit Rate | ROI | CLV | Thin |
|------|---|----------|-----|-----|------|
| NEITHER | 7151 | 14.2% | -24.3% | +0.0% | N |
| G13_ONLY | 352 | 36.1% | +12.1% | -0.9% | N |
| S6_ONLY | 2711 | 24.2% | -19.0% | -0.1% | N |
| G13+S6 | 257 | 36.6% | +14.8% | -0.8% | N |

### G13 x S6(ELEVATED) -- TOP_10

| Cell | N | Hit Rate | ROI | CLV | Thin |
|------|---|----------|-----|-----|------|
| NEITHER | 7146 | 7.3% | -23.6% | -0.0% | N |
| G13_ONLY | 352 | 20.5% | +14.9% | -0.6% | N |
| S6_ONLY | 2751 | 12.5% | -19.1% | -0.0% | N |
| G13+S6 | 257 | 21.4% | +43.1% | -0.6% | N |

### G13 x S6(REGULAR_EASY) -- MAKE_CUT

| Cell | N | Hit Rate | ROI | CLV | Thin |
|------|---|----------|-----|-----|------|
| NEITHER | 2495 | 55.7% | -12.5% | +0.1% | N |
| G13_ONLY | 490 | 80.0% | +10.6% | -0.1% | N |
| S6_ONLY | 1279 | 54.3% | -8.5% | +0.3% | N |
| G13+S6 | 119 | 73.9% | +3.6% | +0.3% | N |

### G13 x S6(REGULAR_EASY) -- TOP_20

| Cell | N | Hit Rate | ROI | CLV | Thin |
|------|---|----------|-----|-----|------|
| NEITHER | 6974 | 18.2% | -22.0% | -0.0% | N |
| G13_ONLY | 490 | 35.9% | +15.0% | -0.8% | N |
| S6_ONLY | 2888 | 14.0% | -25.0% | +0.0% | N |
| G13+S6 | 119 | 37.8% | +6.2% | -1.1% | N |

### G13 x S6(REGULAR_EASY) -- TOP_10

| Cell | N | Hit Rate | ROI | CLV | Thin |
|------|---|----------|-----|-----|------|
| NEITHER | 7009 | 9.3% | -23.2% | -0.0% | N |
| G13_ONLY | 490 | 19.6% | +24.8% | -0.6% | N |
| S6_ONLY | 2888 | 7.3% | -20.4% | +0.0% | N |
| G13+S6 | 119 | 26.1% | +35.2% | -0.8% | N |

## Interaction Strength

| S6 Class | Market | N(combo) | ROI(combo) | ROI(G13) | ROI(S6) | HR Ratio | ROI Ratio | Filter | Classification |
|----------|--------|----------|-----------|---------|---------|----------|-----------|--------|----------------|
| REGULAR_HARD | make_cut | 141 | +11.8% | +8.5% | -12.0% | 1.01 | 1.62 | PASS | MULTIPLICATIVE |
| REGULAR_HARD | top_20 | 141 | +25.3% | +9.6% | -22.5% | 1.33 | 2.48 | PASS | MULTIPLICATIVE |
| REGULAR_HARD | top_10 | 141 | +19.8% | +28.9% | -26.5% | 1.24 | 0.87 | FAIL | INTERFERENCE |
| ELEVATED | make_cut | 257 | +9.3% | +9.2% | -10.3% | 0.99 | 0.92 | PASS | INTERFERENCE |
| ELEVATED | top_20 | 257 | +14.8% | +12.1% | -19.0% | 0.79 | 0.85 | PASS | INTERFERENCE |
| ELEVATED | top_10 | 257 | +43.1% | +14.9% | -19.1% | 0.83 | 2.22 | PASS | HIGH_VARIANCE_INTERACTION |
| REGULAR_EASY | make_cut | 119 | +3.6% | +10.6% | -8.5% | 0.94 | 0.24 | FAIL | INTERFERENCE |
| REGULAR_EASY | top_20 | 119 | +6.2% | +15.0% | -25.0% | 1.19 | 0.51 | FAIL | INTERFERENCE |
| REGULAR_EASY | top_10 | 119 | +35.2% | +24.8% | -20.4% | 1.48 | 1.28 | PASS | HIGH_VARIANCE_INTERACTION |

## Yearly Stability

See console output for full tables.
