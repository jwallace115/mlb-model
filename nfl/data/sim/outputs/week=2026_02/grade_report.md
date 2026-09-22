# NFL Week 2 (2026) Grade Report

Total legs: 1276
Graded: 1276 (hit: 390, miss: 886)
Void: 0
Void-pending (game not in PBP): 0
Unresolved (player_id missing): 0

**One week cannot validate anything -- this is a log, not evidence.**

## By family x position

| Family | Position | N | Hit rate | Brier |
|--------|----------|---|----------|-------|
| anytime_td           | RB   |   62 | 0.161 | 0.158 |
| anytime_td           | TE   |   45 | 0.178 | 0.134 |
| anytime_td           | WR   |  100 | 0.140 | 0.118 |
| pass_attempts        | QB   |    3 | 0.333 | 0.250 |
| pass_completions     | QB   |    8 | 0.750 | 0.250 |
| receptions           | RB   |  173 | 0.358 | 0.201 |
| receptions           | TE   |  225 | 0.276 | 0.180 |
| receptions           | WR   |  508 | 0.337 | 0.190 |
| rush_attempts        | QB   |    5 | 0.600 | 0.250 |
| rush_attempts        | RB   |  147 | 0.361 | 0.183 |

## By calibrated probability bin

| Bin | N | Hit rate | Mean cal_p | Brier |
|-----|---|----------|------------|-------|
| 0.5-0.6 |   97 | 0.392 | 0.569 | 0.268 |
| 0.6-0.7 |   88 | 0.580 | 0.660 | 0.252 |
| 0.7-0.8 |   95 | 0.653 | 0.746 | 0.236 |
| 0.8-1.0 |   87 | 0.678 | 0.857 | 0.247 |

## By tier

| Tier | N | Hit rate |
|------|---|----------|
| TRUSTED                                  |  601 | 0.301 |
| TRUSTED-FLAGGED [RB tail]                |  169 | 0.355 |
| TRUSTED-FLAGGED [TE]                     |  221 | 0.276 |
| UNTRUSTED                                |  107 | 0.168 |
| WATCH [yardage-family calibration not passed] |  139 | 0.353 |
| placed                                   |   39 | 0.538 |

## CLV (where book price exists)

| Family | N | Mean CLV (cal_p - book_implied) |
|--------|---|---------------------------------|
| receptions           |  143 | +0.0088 |
| rush_attempts        |    8 | +0.0331 |

## CLV vs Hard Rock close (close_implied - pick_implied)

| Family | N | Mean CLV |
|--------|---|----------|
| receptions           |  139 | +0.0001 |
| rush_attempts        |    8 | +0.0051 |

Overall mean CLV: +0.0004 (N=147)

## By ticket

| Ticket | Legs | Hits | Misses | All hit? |
|--------|------|------|--------|----------|
| 2026-09-20d:ALLDAY_20_PLACED |   19 |    8 |   11 | NO       |
| 2026-09-20d:LEAD_10_PLACED |   10 |    7 |    3 | NO       |
| 2026-09-20d:LEAD_5_PLACED |    5 |    3 |    2 | NO       |
| 2026-09-20e:LEAD_5_PLACED |    5 |    3 |    2 | NO       |

Sample size: 1276 graded legs from 15 games.
One week cannot validate anything.