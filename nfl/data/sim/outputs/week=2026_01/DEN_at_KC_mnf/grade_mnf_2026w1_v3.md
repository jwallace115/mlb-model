# NFL Week 1 (2026) Grade Report

Total legs: 30
Graded: 30 (hit: 9, miss: 21)
Void: 0
Void-pending (game not in PBP): 0
Unresolved (player_id missing): 0

**One week cannot validate anything -- this is a log, not evidence.**

## By family x position

| Family | Position | N | Hit rate | Brier |
|--------|----------|---|----------|-------|
| anytime_td           | RB   |    1 | 1.000 | 0.250 |
| pass_completions     | QB   |    3 | 0.000 | 0.250 |
| receptions           | RB   |    2 | 0.500 | 0.290 |
| receptions           | TE   |    4 | 0.000 | 0.546 |
| receptions           | WR   |   16 | 0.188 | 0.255 |
| rush_attempts        | RB   |    3 | 1.000 | 0.250 |
| rush_yds             | RB   |    1 | 1.000 | 0.047 |

## By calibrated probability bin

| Bin | N | Hit rate | Mean cal_p | Brier |
|-----|---|----------|------------|-------|
| 0.5-0.6 |    3 | 0.667 | 0.525 | 0.227 |
| 0.6-0.7 |    5 | 0.200 | 0.654 | 0.352 |
| 0.7-0.8 |    5 | 0.400 | 0.741 | 0.325 |
| 0.8-1.0 |    2 | 0.000 | 0.819 | 0.671 |

## By tier

| Tier | N | Hit rate |
|------|---|----------|
| manual                                   |   30 | 0.300 |

## CLV (where book price exists)

| Family | N | Mean CLV (cal_p - book_implied) |
|--------|---|---------------------------------|
| anytime_td           |    1 | -0.0652 |
| pass_completions     |    3 | +nan |
| receptions           |   22 | +0.0406 |
| rush_attempts        |    3 | +nan |
| rush_yds             |    1 | +0.0497 |

## By ticket

| Ticket | Legs | Hits | Misses | All hit? |
|--------|------|------|--------|----------|
| bonus_6leg_sgp_+2612_$20 |    6 |    1 |    5 | NO       |
| cash_5leg_sgp_+397_$15 |    5 |    4 |    1 | NO       |
| confidence_5leg      |    5 |    1 |    4 | NO       |
| sim_unbet            |    9 |    2 |    7 | NO       |
| swing_5leg           |    5 |    1 |    4 | NO       |

Sample size: 30 graded legs from 1 games.
One week cannot validate anything.