# Phase 5H Item 3 — D89 on this Mac, and the penalty breakdown

## D89 effect (this Mac, salt=0)

| Metric | D89-off | D89-on | Delta | Spec | Status |
|--------|---------|--------|-------|------|--------|
| off_pen | 6.197 | 5.755 | -0.442 | \|x-5.51\| < 0.5 | FAIL→PASS |
| def_pen | 3.879 | 3.599 | -0.280 | \|x-3.45\| < 0.5 | PASS→PASS |
| fd_pen_pt | 1.540 | 1.431 | -0.109 | \|x-1.73\| < 0.3 | PASS→PASS |
| go_rate | 0.2103 | 0.2094 | -0.001 | — | null control |
| tied_expiry | 0.111 | 0.108 | -0.003 | — | null control |

D89-on: off_pen passes (0.245 < 0.5). fd_pen_pt stays PASS on Mac (0.299 < 0.3).
Go rate and tied expiry null controls: moved < 0.003 — not affected by D89.
Consistent with Cowork's Linux measurement (D93 table).

## D89-on seed noise (11 salts)

| Metric | Mean | SD | Min | Max |
|--------|------|-----|-----|-----|
| off_pen | 5.744 | 0.018 | 5.707 | 5.768 |
| def_pen | 3.596 | 0.007 | 3.584 | 3.611 |
| fd_pen_pt | 1.429 | 0.003 | 1.425 | 1.437 |
| go_rate | 0.2108 | 0.0007 | 0.2094 | 0.2123 |
| tied_expiry | 0.116 | 0.016 | 0.089 | 0.136 |

## Real penalty breakdown by type (no-play penalties, 2021-24)

### Offense (5.51/game total)
| Type | /game | Yds |
|------|-------|-----|
| False Start | 2.25 | 4.9 |
| Offensive Holding | 1.55 | 9.8 |
| Delay of Game | 0.59 | 4.9 |
| Offensive Pass Interference | 0.26 | 9.7 |
| Ineligible Downfield Pass | 0.22 | 5.0 |
| Illegal Formation | 0.19 | 4.9 |
| Illegal Shift | 0.14 | 5.0 |
| Other | 0.32 | — |

### Defense (3.45/game total)
| Type | /game | Yds |
|------|-------|-----|
| Defensive Pass Interference | 1.01 | 16.0 |
| Defensive Offside | 0.52 | 4.8 |
| Defensive Holding | 0.49 | 4.7 |
| Neutral Zone Infraction | 0.35 | 4.8 |
| Roughing the Passer | 0.24 | 13.5 |
| Illegal Contact | 0.20 | 5.0 |
| Other | 0.65 | — |

### By quarter
| Qtr | Off/game | Def/game | Total |
|-----|----------|----------|-------|
| Q1 | 1.14 | 0.72 | 1.86 |
| Q2 | 1.60 | 1.04 | 2.64 |
| Q3 | 1.33 | 0.73 | 2.06 |
| Q4 | 1.40 | 0.94 | 2.34 |

### By down
| Down | /game | % of total |
|------|-------|-----------|
| 1st | 3.18 | 35.5% |
| 2nd | 2.48 | 27.6% |
| 3rd | 2.32 | 25.8% |
| 4th | 0.87 | 9.7% |

## First downs by penalty (D89 split, from PBP)

- No-play penalty FDs: 2,719 / 1,087 = **1.251/team** (defense penalties with auto-first-down)
- Scrimmage-play penalty FDs: 1,036 / 1,087 = **0.477/team** (play counted, FD awarded)
- Total: 3,755 / 1,087 = **1.727/team** (test target: 1.73)

The sim only models no-play penalty FDs. D89's correct rate (0.0672 vs 0.0720) reduces
the sim's total penalties, which reduces the no-play penalty FD count from ~1.54 to ~1.43
per team — still 0.28 below the 1.73 target, but now for the right reason (missing
scrimmage-penalty FD mechanism) rather than partially masked by an inflated rate.

## Sim vs real: penalty mix comparison

The sim's penalty model is a single draw with P(offense) = 0.615 and separate
5yd/10yd/DPI yardage tables. It does NOT condition on quarter, down, or score state.
Real data shows penalty rates vary by quarter (Q2 highest at 2.64/game, Q1 lowest at
1.86/game) and by down (1st down 35.5% of penalties). The sim draws a flat rate per
play attempt regardless of context.
