# Phase 6: Schedule Front-Loading

## Phase 1 -- Schedule Front-Loading Buckets

Team-seasons analyzed: 533
SOS shift quartiles: Q25=-7.87, Q75=7.29

SOS shift = mean opponent SP+ in Weeks 5+ minus mean opponent SP+ in Weeks 1-4
FRONT_LOAD_EASY = top quartile (easy early schedule, harder later)
FRONT_LOAD_HARD = bottom quartile (hard early schedule, easier later)

Counts by season:
```
bucket  FRONT_LOAD_EASY  FRONT_LOAD_HARD  MIDDLE
season                                          
2022                 29               28      74
2023                 39               39      55
2024                 31               31      71
2025                 35               37      64
```

## Phase 2 -- Transition-Game ATS (Weeks 5-8)

### FRONT_LOAD_EASY
- **N=428, Cover Rate=0.526, ATS Margin=+0.28**

| Season | N | Cover | ATS Margin |
|--------|---|-------|------------|
| 2022 | 95 | 0.595 | +2.14 |
| 2023 | 124 | 0.512 | +0.02 |
| 2024 | 95 | 0.547 | -0.15 |
| 2025 | 114 | 0.465 | -0.64 |

- Weeks 5-6: N=215, Cover=0.540, ATS=+0.96
- Weeks 7-8: N=213, Cover=0.512, ATS=-0.41

### MIDDLE
- **N=847, Cover Rate=0.488, ATS Margin=-0.16**

| Season | N | Cover | ATS Margin |
|--------|---|-------|------------|
| 2022 | 243 | 0.447 | -1.04 |
| 2023 | 174 | 0.509 | +0.41 |
| 2024 | 226 | 0.473 | +0.25 |
| 2025 | 204 | 0.534 | -0.04 |

- Weeks 5-6: N=419, Cover=0.482, ATS=-0.25
- Weeks 7-8: N=428, Cover=0.493, ATS=-0.07

### FRONT_LOAD_HARD
- **N=439, Cover Rate=0.499, ATS Margin=+0.03**

| Season | N | Cover | ATS Margin |
|--------|---|-------|------------|
| 2022 | 96 | 0.542 | +0.52 |
| 2023 | 130 | 0.477 | -0.57 |
| 2024 | 99 | 0.515 | -0.45 |
| 2025 | 114 | 0.474 | +0.72 |

- Weeks 5-6: N=206, Cover=0.495, ATS=-0.49
- Weeks 7-8: N=233, Cover=0.502, ATS=+0.49

### All Weeks 5+

| Bucket | N | Cover | ATS Margin |
|--------|---|-------|------------|
| FRONT_LOAD_EASY | 1090 | 0.520 | +0.54 |
| MIDDLE | 2156 | 0.485 | -0.37 |
| FRONT_LOAD_HARD | 1110 | 0.509 | +0.18 |

## Phase 3 -- Record Inflation

FRONT_LOAD_EASY teams, split by Weeks 1-4 record:

| Early Record | N | Cover | ATS Margin |
|-------------|---|-------|------------|
| Strong (3-4 wins) | 178 | 0.489 | -0.31 |
| Weak (0-2 wins) | 250 | 0.552 | +0.70 |

By season (Strong early record only):

| Season | N | Cover | ATS Margin |
|--------|---|-------|------------|
| 2022 | 39 | 0.526 | -0.32 |
| 2023 | 58 | 0.500 | +0.33 |
| 2024 | 39 | 0.449 | -1.54 |
| 2025 | 42 | 0.476 | -0.05 |

## Phase 4 -- Residual Check (Model Edge)

FRONT_LOAD_EASY, Weeks 5-8, split by model edge:

| Residual Group | N | Cover | ATS Margin |
|---------------|---|-------|------------|
| MODEL_LIKES (edge > 1.5) | 178 | 0.537 | +1.07 |
| AGREE (|edge| <= 1.5) | 89 | 0.528 | +0.19 |
| MARKET_LIKES (edge < -1.5) | 161 | 0.512 | -0.55 |

## Phase 5 -- Conference vs Non-Conference

FRONT_LOAD_EASY, Weeks 5-8:

| Game Type | N | Cover | ATS Margin |
|-----------|---|-------|------------|
| Conference | 401 | 0.535 | +0.50 |
| Non-conference | 27 | 0.389 | -3.09 |

## Phase 6 -- Favorite vs Underdog

FRONT_LOAD_EASY, Weeks 5-8:

| Role | N | Cover | ATS Margin |
|------|---|-------|------------|
| Favored | 208 | 0.488 | -0.28 |
| Underdog | 220 | 0.561 | +0.80 |

## Phase 7 -- Timing Decay

FRONT_LOAD_EASY, by week:

| Week | N | Cover | ATS Margin |
|------|---|-------|------------|
| 5 | 113 | 0.504 | +0.55 |
| 6 | 102 | 0.578 | +1.41 |
| 7 | 110 | 0.527 | -0.21 |
| 8 | 103 | 0.495 | -0.62 |
| 9+ | 662 | 0.517 | +0.72 |

## Phase 8 -- Robustness

### Top 10 Teams by Transition Games (FRONT_LOAD_EASY)

| Team | N | Cover | ATS |
|------|---|-------|-----|
| Alabama | 16 | 0.500 | -3.84 |
| Auburn | 12 | 0.500 | -1.96 |
| Nebraska | 12 | 0.417 | -4.71 |
| Michigan State | 12 | 0.583 | -2.75 |
| UCLA | 11 | 0.727 | +9.23 |
| Duke | 10 | 0.650 | +7.00 |
| Stanford | 10 | 0.400 | +2.45 |
| Texas Tech | 10 | 0.500 | -0.45 |
| Washington | 10 | 0.250 | -6.00 |
| USC | 10 | 0.400 | -6.20 |

### Season Stability

| Season | N | Cover | ATS |
|--------|---|-------|-----|
| 2022 | 95 | 0.595 | +2.14 |
| 2023 | 124 | 0.512 | +0.02 |
| 2024 | 95 | 0.547 | -0.15 |
| 2025 | 114 | 0.465 | -0.64 |

### Conference Concentration

| Conference | Count |
|-----------|-------|
| Big Ten | 39 |
| SEC | 35 |
| ACC | 23 |
| Big 12 | 16 |
| Pac-12 | 8 |
| American Athletic | 5 |
| Sun Belt | 4 |
| FBS Independents | 2 |
| Mountain West | 1 |
| Conference USA | 1 |

Excluding top team (Alabama): N=412, Cover=0.527, ATS=+0.44

FRONT_LOAD_HARD contrast: N=439, Cover=0.499, ATS=+0.03

## Decision

**VERDICT: NEAR MISS**

Directional (cover=0.526) but does not clear the 55% threshold with sufficient sample.

Key numbers:
- FRONT_LOAD_EASY Weeks 5-8: N=428, Cover=0.526, ATS=+0.28
- FRONT_LOAD_HARD Weeks 5-8: N=439, Cover=0.499, ATS=+0.03
- Seasons with cover > 50%: 3/4
- Strong early record sub-split: Cover=0.489 (N=178)
- Residual: MODEL_LIKES cover=0.537, AGREE cover=0.528, MARKET_LIKES cover=0.512