# Engine 4B — Expected Zone (Pregame-Safe)

Predictors: umpire season baseline CSR, umpire 3-game rolling CSR, deviation vs baseline.
ALL predictors confirmed pregame-safe (shift-1 verified empirically).
Engine 4 (current-game CSR) VOIDED for leakage.

Framing signals: included (EZ007/EZ008)

| sig | dir | trN | vlN | tr_rate | vl_rate | ROI | perm | gate | yr | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| EZ001 | OVER | 1311 | 609 | 0.5233 | 0.4844 | -0.1% | 98.6 | 85 | True | FAIL (val=0.4844) |
| EZ002 | UNDER | 1537 | 416 | 0.5192 | 0.5096 | -0.88% | 88.2 | 85 | True | FAIL (val=0.5096) |
| EZ003 | OVER | 547 | 274 | 0.5247 | 0.4964 | 0.17% | 91.8 | 95 | False | FAIL (perm=91.8<95; val=0.4964; yr=1/3) |
| EZ004 | UNDER | 656 | 146 | 0.532 | 0.4521 | 1.57% | 93.0 | 95 | True | FAIL (perm=93.0<95; val=0.4521) |
| EZ005 | OVER | 561 | 210 | 0.4955 | 0.4524 | -5.4% | 44.8 | 85 | False | FAIL (perm=44.8<85; val=0.4524; yr=1/3) |
| EZ006 | UNDER | 533 | 217 | 0.5235 | 0.4424 | -0.07% | 77.2 | 85 | False | FAIL (perm=77.2<85; val=0.4424; yr=1/3) |
| EZ007 | OVER | 336 | 155 | 0.5327 | 0.4968 | 1.7% | 91.6 | 95 | False | FAIL (perm=91.6<95; val=0.4968; yr=1/3) |
| EZ008 | UNDER | 366 | 147 | 0.5246 | 0.4694 | 0.15% | 74.2 | 95 | True | FAIL (perm=74.2<95; val=0.4694) |
