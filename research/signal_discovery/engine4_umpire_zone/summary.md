# Engine 4 — Umpire Zone Effects

zone_score = called_strike_rate. zone_deviation = called_strike_rate_r3_vs_season.
All thresholds frozen 2022-2023. Permutation gate: 85th (standalone) / 95th (interactions).
CS014A reference: permutation 83.0 (FAIL under old framework).

| sig | dir | trN | vlN | tr_rate | vl_rate | ROI | perm | gate | yr | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| UZ001 | OVER | 1527 | 593 | 0.5435 | 0.5481 | 3.77% | 100.0 | 85 | True | PASS |
| UZ002 | UNDER | 1544 | 521 | 0.5926 | 0.572 | 13.14% | 100.0 | 85 | True | PASS |
| UZ003A | OVER | 545 | 203 | 0.4954 | 0.4483 | -5.42% | 45.8 | 85 | False | FAIL (perm=45.8<85; val=0.4483; yr=1/3) |
| UZ003B | UNDER | 533 | 217 | 0.5235 | 0.4424 | -0.07% | 80.0 | 85 | False | FAIL (perm=80.0<85; val=0.4424; yr=1/3) |
| UZ004 | OVER | 981 | 378 | 0.5708 | 0.582 | 8.98% | 100.0 | 95 | True | PASS |
| UZ005 | UNDER | 1002 | 311 | 0.6108 | 0.6077 | 16.6% | 100.0 | 95 | True | PASS |


## VOIDED

**Engine 4 invalidated.** Signals were built using current-game called_strike_rate, which is not pregame-safe and introduces leakage. Results are not actionable for pregame betting. The pass confirms only that realized in-game zone correlates with scoring, not that pregame expected zone creates edge. Replaced by Engine 4B using prior-games-only umpire zone predictors.
