# Blind opinion log - score, 2026 week 2

files: ['ai_opinions_20260921T224124Z.parquet']; pilot rows included: True
rows 78, graded 78 (pushes/unresolved 0), with a view 21, no_view share 73.1%

**A pilot or a single game is a log, not evidence. Nothing is tuned on it.**

## Two-way lines (n=54): Brier reader vs de-vigged book: reader 0.2418 / book 0.2364 - P1 (book <= reader) HELD
   lines with a view only (n=18): reader 0.2560 / book 0.2400
## One-way lines (n=24): Brier reader vs vig-inclusive implied: reader 0.0782 / book 0.0715

## Sides taken (n=21): 6 won, units at real price -9.61 (-0.458/leg)
   |p-q| > 0.08 (n=2): 1 won, units -0.29 - P2 (lose units) HELD

### by market_key

| market_key                |   n |   won |   units |
|:--------------------------|----:|------:|--------:|
| h2h                       |   1 |     0 |   -1    |
| player_anytime_td         |   3 |     0 |   -3    |
| player_pass_attempts      |   2 |     0 |   -2    |
| player_pass_interceptions |   2 |     1 |   -0.29 |
| player_pass_yds           |   1 |     0 |   -1    |
| player_reception_yds      |   2 |     1 |   -0.13 |
| player_receptions         |   4 |     1 |   -1.85 |
| player_rush_attempts      |   2 |     0 |   -2    |
| player_rush_yds           |   2 |     2 |    1.74 |
| spreads                   |   1 |     0 |   -1    |
| totals                    |   1 |     1 |    0.91 |

### by tag

| tag         |   n |   won |   units |
|:------------|----:|------:|--------:|
| game_script |   5 |     1 |   -3.17 |
| injury_news |   6 |     2 |   -1.94 |
| role_change |   1 |     1 |    0.91 |
| usage_trend |   9 |     2 |   -5.42 |

### by gap_bucket

| gap_bucket   |   n |   won |   units |
|:-------------|----:|------:|--------:|
| <0.03        |   4 |     2 |   -0.26 |
| 0.03-0.08    |  15 |     3 |   -9.07 |
| >0.08        |   2 |     1 |   -0.29 |

## Every line with a view

| market_key                | player_name       |   line | side_name       |   side_price |   book_p_first |   p_first |   y_first | side_won   |   units | tag         |
|:--------------------------|:------------------|-------:|:----------------|-------------:|---------------:|----------:|----------:|:-----------|--------:|:------------|
| h2h                       |                   |    0   | New York Giants |          250 |          0.724 |      0.69 |         1 | False      |  -1     | injury_news |
| player_anytime_td         | Colby Parkinson   |    0.5 | Over            |          250 |          0.286 |      0.36 |         0 | False      |  -1     | usage_trend |
| player_anytime_td         | Jaxson Dart       |    0.5 | Over            |          260 |          0.278 |      0.4  |         0 | False      |  -1     | usage_trend |
| player_anytime_td         | Tyler Higbee      |    0.5 | Over            |          500 |          0.167 |      0.24 |         0 | False      |  -1     | injury_news |
| player_pass_attempts      | Jaxson Dart       |   29.5 | Over            |         -125 |          0.52  |      0.57 |         0 | False      |  -1     | game_script |
| player_pass_attempts      | Matthew Stafford  |   32.5 | Over            |         -110 |          0.49  |      0.55 |         0 | False      |  -1     | game_script |
| player_pass_interceptions | Jaxson Dart       |    0.5 | Under           |         -140 |          0.449 |      0.36 |         0 | True       |   0.714 | usage_trend |
| player_pass_interceptions | Matthew Stafford  |    0.5 | Under           |         -160 |          0.419 |      0.36 |         1 | False      |  -1     | usage_trend |
| player_pass_yds           | Matthew Stafford  |  241.5 | Under           |         -115 |          0.5   |      0.46 |         1 | False      |  -1     | injury_news |
| player_reception_yds      | Cam Skattebo      |   11.5 | Under           |         -110 |          0.51  |      0.45 |         1 | False      |  -1     | usage_trend |
| player_reception_yds      | Odell Beckham Jr. |    3.5 | Under           |         -115 |          0.5   |      0.44 |         0 | True       |   0.87  | usage_trend |
| player_receptions         | Blake Corum       |    0.5 | Under           |          140 |          0.611 |      0.55 |         1 | False      |  -1     | usage_trend |
| player_receptions         | Cam Skattebo      |    1.5 | Under           |          100 |          0.531 |      0.46 |         1 | False      |  -1     | usage_trend |
| player_receptions         | Davante Adams     |    5.5 | Over            |          115 |          0.437 |      0.5  |         1 | True       |   1.15  | injury_news |
| player_receptions         | Devin Singletary  |    1.5 | Over            |          110 |          0.449 |      0.49 |         0 | False      |  -1     | usage_trend |
| player_rush_attempts      | Jaxson Dart       |    6.5 | Over            |         -130 |          0.531 |      0.55 |         0 | False      |  -1     | game_script |
| player_rush_attempts      | Kyren Williams    |   13.5 | Over            |         -125 |          0.52  |      0.57 |         0 | False      |  -1     | game_script |
| player_rush_yds           | Devin Singletary  |   11.5 | Under           |         -110 |          0.51  |      0.45 |         0 | True       |   0.909 | role_change |
| player_rush_yds           | Kyren Williams    |   63.5 | Over            |         -120 |          0.51  |      0.53 |         1 | True       |   0.833 | game_script |
| spreads                   |                   |   -7   | New York Giants |         -115 |          0.489 |      0.46 |         1 | False      |  -1     | injury_news |
| totals                    |                   |   47.5 | Under           |         -110 |          0.5   |      0.48 |         0 | True       |   0.909 | injury_news |
