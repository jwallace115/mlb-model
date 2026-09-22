# Sim vs book on outcomes - 2026 week 2

grades: `nfl/data/sim/outputs/week=2026_02/grades.parquet` (1276 legs; {'miss': 886, 'hit': 390})
candidates: `nfl/data/board/week=2026_02/nfl_prop_candidates_20260920T1424Z.parquet` (203 two-way rec/rush rows)
universe (sim priced the book's exact line AND graded hit/miss): **146** rows, 139 players, 14 games

**One week. This is a log, not evidence. Nothing is tuned on it.**

## All rows

| source        |   n |   mean_p |   over_rate |   brier |   logloss |
|:--------------|----:|---------:|------------:|--------:|----------:|
| book q_over   | 146 |    0.497 |       0.459 |  0.2519 |    0.6972 |
| sim cal_p     | 146 |    0.51  |       0.459 |  0.2993 |    0.8076 |
| sim raw sim_p | 146 |    0.555 |       0.459 |  0.3194 |    0.8613 |
| coin 0.5      | 146 |    0.5   |       0.459 |  0.25   |    0.6931 |

Brier(sim cal_p) - Brier(book) = **+0.0474** (game-cluster bootstrap 95%: +0.0233 .. +0.0723). P1 (book better) HELD; interval excludes 0.

## By family

| family        |   n |   over_rate |   brier_book |   brier_sim |
|:--------------|----:|------------:|-------------:|------------:|
| receptions    | 138 |       0.464 |       0.2521 |      0.3038 |
| rush_attempts |   8 |       0.375 |       0.249  |      0.2214 |

## By tier

| tier                                          |   n |   over_rate |   brier_book |   brier_sim |
|:----------------------------------------------|----:|------------:|-------------:|------------:|
| TRUSTED                                       |  69 |       0.478 |       0.2486 |      0.2981 |
| TRUSTED-FLAGGED [RB tail]                     |  32 |       0.531 |       0.2661 |      0.3289 |
| TRUSTED-FLAGGED [TE]                          |  37 |       0.378 |       0.2465 |      0.2929 |
| WATCH [yardage-family calibration not passed] |   8 |       0.375 |       0.249  |      0.2214 |

## By game_id

| game_id   |   n |   over_rate |   brier_book |   brier_sim |
|:----------|----:|------------:|-------------:|------------:|
| CAR@ATL   |   9 |       0.444 |       0.2273 |      0.3136 |
| CIN@HOU   |  13 |       0.538 |       0.2405 |      0.351  |
| CLE@TB    |  11 |       0.636 |       0.282  |      0.2665 |
| GB@NYJ    |  10 |       0.4   |       0.2271 |      0.2543 |
| IND@KC    |  10 |       0.6   |       0.2652 |      0.3774 |
| JAX@DEN   |   9 |       0.444 |       0.2507 |      0.3436 |
| LV@LAC    |   8 |       0.375 |       0.2749 |      0.3009 |
| MIA@SF    |  12 |       0.333 |       0.2408 |      0.3051 |
| MIN@CHI   |  14 |       0.429 |       0.2528 |      0.2711 |
| NO@BAL    |   9 |       0.778 |       0.2798 |      0.3114 |
| PHI@TEN   |  10 |       0.2   |       0.2489 |      0.2749 |
| PIT@NE    |   9 |       0.111 |       0.245  |      0.3127 |
| SEA@ARI   |  12 |       0.333 |       0.2379 |      0.2005 |
| WAS@DAL   |  10 |       0.8   |       0.2636 |      0.334  |

## Rows where |cal_p - q_over| > 0.2

30 rows: outcome sided with the SIM on 10, with the BOOK on 20. P2 (book more often) HELD.

| k                   | team   | family        |   line |   q_over |   cal_p |   y | sided_with_sim   |
|:--------------------|:-------|:--------------|-------:|---------:|--------:|----:|:-----------------|
| bijan robinson      | ATL    | receptions    |    4.5 |    0.575 |   0.895 |   0 | False            |
| olamide zaccheaus   | ATL    | receptions    |    1.5 |    0.437 |   0.728 |   0 | False            |
| justin jefferson    | MIN    | receptions    |    6.5 |    0.49  |   0.728 |   0 | False            |
| josh oliver         | MIN    | receptions    |    1.5 |    0.5   |   0.76  |   0 | False            |
| aaron jones         | MIN    | receptions    |    2.5 |    0.52  |   0.307 |   0 | True             |
| cole kmet           | CHI    | receptions    |    1.5 |    0.49  |   0.76  |   0 | False            |
| kalif raymond       | CHI    | receptions    |    2.5 |    0.44  |   0.728 |   1 | True             |
| dandre swift        | CHI    | rush_attempts |   14.5 |    0.469 |   0.778 |   1 | True             |
| jamarr chase        | CIN    | receptions    |    6.5 |    0.5   |   0.275 |   1 | False            |
| xavier hutchinson   | HOU    | receptions    |    2.5 |    0.563 |   0.275 |   1 | False            |
| dalton schultz      | HOU    | receptions    |    4.5 |    0.541 |   0.278 |   1 | False            |
| woody marks         | HOU    | receptions    |    1.5 |    0.44  |   0.2   |   1 | False            |
| kc concepcion       | CLE    | receptions    |    3.5 |    0.437 |   0.728 |   1 | True             |
| adonai mitchell     | NYJ    | receptions    |    2.5 |    0.531 |   0.835 |   1 | True             |
| jonnu smith         | GB     | receptions    |    1.5 |    0.449 |   0.654 |   0 | False            |
| mason taylor        | NYJ    | receptions    |    2.5 |    0.5   |   0.76  |   0 | False            |
| demario douglas     | NE     | receptions    |    3.5 |    0.428 |   0.828 |   0 | False            |
| dallas goedert      | PHI    | receptions    |    3.5 |    0.531 |   0.76  |   0 | False            |
| brian thomas        | JAX    | receptions    |    2.5 |    0.52  |   0.286 |   1 | False            |
| michael mayer       | LV     | receptions    |    5.5 |    0.449 |   0.113 |   0 | True             |
| jaxon smithnjigba   | SEA    | receptions    |    6.5 |    0.48  |   0.69  |   1 | True             |
| trey mcbride        | ARI    | receptions    |    6.5 |    0.469 |   0.76  |   1 | True             |
| jeremiyah love      | ARI    | receptions    |    2.5 |    0.554 |   0.349 |   1 | False            |
| jeremiyah love      | ARI    | rush_attempts |    9.5 |    0.49  |   0.087 |   0 | True             |
| jake ferguson       | DAL    | receptions    |    3.5 |    0.469 |   0.171 |   1 | False            |
| ryan flournoy       | DAL    | receptions    |    2.5 |    0.531 |   0.275 |   1 | False            |
| kaelon black        | SF     | rush_attempts |    9.5 |    0.48  |   0.905 |   0 | False            |
| christian mccaffrey | SF     | rush_attempts |   14.5 |    0.51  |   0.151 |   0 | True             |
| alec pierce         | IND    | receptions    |    2.5 |    0.563 |   0.835 |   0 | False            |
| noah gray           | KC     | receptions    |    1.5 |    0.38  |   0.595 |   0 | False            |

## Placed tickets

- 2026-09-20d:ALLDAY_20_PLACED: {'miss': 11, 'hit': 8}
- 2026-09-20d:LEAD_10_PLACED: {'hit': 7, 'miss': 3}
- 2026-09-20d:LEAD_5_PLACED: {'hit': 3, 'miss': 2}
- 2026-09-20e:LEAD_5_PLACED: {'hit': 3, 'miss': 2}

## Placed legs (the sim had no say in these)

| ticket                       | player_name      | family           | side   |   line |   book_price |   q_pick |   cal_pick | grade   | grade_reason   |
|:-----------------------------|:-----------------|:-----------------|:-------|-------:|-------------:|---------:|-----------:|:--------|:---------------|
| 2026-09-20d:LEAD_5_PLACED    | Caleb Douglas    | receptions       | over   |    2.5 |         -165 |    0.583 |      0.749 | miss    |                |
| 2026-09-20d:LEAD_5_PLACED    | Breece Hall      | rush_attempts    | over   |   15.5 |         -130 |    0.531 |    nan     | hit     |                |
| 2026-09-20d:LEAD_5_PLACED    | Emeka Egbuka     | receptions       | over   |    3.5 |         -165 |    0.583 |      0.481 | miss    |                |
| 2026-09-20d:LEAD_5_PLACED    | Chase Brown      | rush_attempts    | over   |   13.5 |         -130 |    0.531 |    nan     | hit     |                |
| 2026-09-20d:LEAD_5_PLACED    | Tyler Shough     | pass_completions | over   |   21.5 |         -130 |    0.531 |    nan     | hit     |                |
| 2026-09-20d:LEAD_10_PLACED   | Christian Watson | receptions       | over   |    3.5 |         -165 |    0.583 |      0.583 | hit     |                |
| 2026-09-20d:LEAD_10_PLACED   | Aaron Jones      | rush_attempts    | over   |   14.5 |         -110 |    0.52  |      0.647 | hit     |                |
| 2026-09-20d:LEAD_10_PLACED   | Brock Purdy      | pass_completions | over   |   19.5 |         -130 |    0.531 |    nan     | hit     |                |
| 2026-09-20d:LEAD_10_PLACED   | Quentin Johnston | receptions       | over   |    3.5 |         -165 |    0.583 |      0.583 | miss    |                |
| 2026-09-20d:LEAD_10_PLACED   | Bijan Robinson   | rush_attempts    | over   |   18.5 |         -125 |    0.52  |    nan     | miss    |                |
| 2026-09-20d:LEAD_10_PLACED   | Daniel Jones     | pass_completions | over   |   20.5 |         -130 |    0.531 |    nan     | hit     |                |
| 2026-09-20d:LEAD_10_PLACED   | Devaughn Vele    | receptions       | over   |    3.5 |         -140 |    0.551 |      0.69  | hit     |                |
| 2026-09-20d:LEAD_10_PLACED   | J.K. Dobbins     | rush_attempts    | over   |   13.5 |         -125 |    0.52  |    nan     | miss    |                |
| 2026-09-20d:LEAD_10_PLACED   | Jalen Hurts      | pass_completions | over   |   17.5 |         -130 |    0.531 |    nan     | hit     |                |
| 2026-09-20d:LEAD_10_PLACED   | CeeDee Lamb      | receptions       | over   |    5.5 |         -135 |    0.541 |      0.578 | hit     |                |
| 2026-09-20d:ALLDAY_20_PLACED | Derrick Henry    | receptions       | under  |    1.5 |          nan |    0.663 |      0.589 | miss    |                |
| 2026-09-20d:ALLDAY_20_PLACED | Dak Prescott     | rush_attempts    | under  |    3.5 |          nan |    0.554 |    nan     | miss    |                |
| 2026-09-20d:ALLDAY_20_PLACED | Jordan Love      | pass_completions | over   |   20.5 |         -130 |    0.531 |    nan     | miss    |                |
| 2026-09-20d:ALLDAY_20_PLACED | Adam Trautman    | receptions       | under  |    1.5 |          nan |    0.649 |    nan     | hit     |                |
| 2026-09-20d:ALLDAY_20_PLACED | Patrick Mahomes  | rush_attempts    | under  |    4.5 |         -145 |    0.554 |    nan     | hit     |                |
| 2026-09-20d:ALLDAY_20_PLACED | Justin Herbert   | pass_completions | under  |   20.5 |          nan |    0.531 |    nan     | hit     |                |
| 2026-09-20d:ALLDAY_20_PLACED | Jonathon Brooks  | receptions       | under  |    1.5 |         -210 |    0.629 |    nan     | hit     |                |
| 2026-09-20d:ALLDAY_20_PLACED | Drake Maye       | rush_attempts    | under  |    5.5 |          nan |    0.547 |    nan     | hit     |                |
| 2026-09-20d:ALLDAY_20_PLACED | Baker Mayfield   | pass_attempts    | under  |   28.5 |          nan |    0.52  |    nan     | miss    |                |
| 2026-09-20d:ALLDAY_20_PLACED | Foster Moreau    | receptions       | under  |    1.5 |         -190 |    0.618 |      0.6   | miss    |                |
| 2026-09-20d:ALLDAY_20_PLACED | Malik Willis     | rush_attempts    | under  |    7.5 |         -135 |    0.541 |    nan     | hit     |                |
| 2026-09-20d:ALLDAY_20_PLACED | Saquon Barkley   | receptions       | under  |    2.5 |         -170 |    0.592 |      0.511 | hit     |                |
| 2026-09-20d:ALLDAY_20_PLACED | George Holani    | rush_attempts    | over   |    7.5 |         -130 |    0.531 |    nan     | miss    |                |
| 2026-09-20d:ALLDAY_20_PLACED | Jayden Daniels   | pass_completions | over   |   19.5 |          nan |    0.531 |    nan     | miss    |                |
| 2026-09-20d:ALLDAY_20_PLACED | Deshaun Watson   | rush_attempts    | under  |    5.5 |          nan |    0.541 |    nan     | miss    |                |
| 2026-09-20d:ALLDAY_20_PLACED | Kirk Cousins     | pass_completions | over   |   18.5 |          nan |    0.531 |    nan     | hit     |                |
| 2026-09-20d:ALLDAY_20_PLACED | Jaylen Warren    | receptions       | over   |    2.5 |          nan |    0.594 |      0.598 | miss    |                |
| 2026-09-20d:ALLDAY_20_PLACED | Bhayshul Tuten   | rush_attempts    | under  |   12.5 |          nan |    0.531 |    nan     | miss    |                |
| 2026-09-20d:ALLDAY_20_PLACED | Noah Fant        | receptions       | over   |    1.5 |          nan |    0.602 |      0.696 | miss    |                |
| 2026-09-20e:LEAD_5_PLACED    | Lamar Jackson    | pass_attempts    | under  |   27.5 |          nan |    0.51  |    nan     | miss    |                |
| 2026-09-20e:LEAD_5_PLACED    | Omarion Hampton  | rush_attempts    | over   |   16.5 |          nan |    0.5   |    nan     | hit     |                |
| 2026-09-20e:LEAD_5_PLACED    | Stefon Diggs     | receptions       | over   |    4.5 |          nan |    0.51  |      0.482 | hit     |                |
| 2026-09-20e:LEAD_5_PLACED    | C.J. Stroud      | pass_attempts    | over   |   30.5 |          nan |    0.52  |    nan     | hit     |                |
| 2026-09-20e:LEAD_5_PLACED    | T.J. Hockenson   | receptions       | over   |    3.5 |          nan |    0.51  |      0.471 | miss    |                |

Legs with no q/cal are families or lines the sim does not price (5J item 3).
