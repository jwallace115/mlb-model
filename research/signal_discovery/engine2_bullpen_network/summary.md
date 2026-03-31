# Engine 2 — Bullpen Network Fragility

Bridge role proxy: top 2 GF = closer, avg IP > 2.0 = long relief, else bridge (5+ apps).
Thresholds frozen 2022-2023. Training 2022-2024. Validation 2025.

## Results

| signal | train_N | val_N | train_rate | val_rate | ROI | perm | yr_stable | verdict |
|---|---|---|---|---|---|---|---|---|
| BN001 | 1388 | 534 | 0.5036 | 0.4738 | -3.86% | 75.4 | True | FAIL (perm=75.4; val=0.4738) |
| BN002 | 158 | 62 | 0.5063 | 0.4355 | -3.34% | 60.8 | True | FAIL (perm=60.8; val=0.4355) |
| BN003 | 563 | 227 | 0.5044 | 0.3877 | -3.7% | 65.0 | True | FAIL (perm=65.0; val=0.3877) |
| BN004 | 0 | 0 | None | N/A | N/A% | 0 | False | FAIL (THIN_SAMPLE) |
| BN005 | 1725 | 636 | 0.5084 | 0.4796 | -2.94% | 89.0 | True | FAIL (val=0.4796) |

## Component Analysis

- **proxy_bridge_fraction**: N=2154, lift=+0.06pp
- **leverage_overload_score**: N=1881, lift=+0.08pp
- **handedness_concentration**: N=7515, lift=+0.20pp
- **depth_score**: N=7515, lift=+0.20pp

## Interpretation

All 5 signals FAIL. Bullpen network fragility — bridge availability, leverage overload,
handedness bottleneck, and depth collapse — does NOT predict over outcomes.
Component lifts are near zero (0.06-0.20pp). The market prices bullpen state accurately.

BN005 reached permutation 89th percentile (closest to passing) but failed 2025 validation
(47.96% over rate vs 52.4% required). The leverage+depth combination showed mild training
signal that collapsed out of sample — classic overfitting artifact.

BN004 (bridge_missing) produced ZERO qualifying games — the bridge_fraction < 0.5 threshold
is too strict with the proxy role definition. Bridge availability as defined is rarely
depleted enough to trigger.
