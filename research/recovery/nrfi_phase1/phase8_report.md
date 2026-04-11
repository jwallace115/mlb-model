# Phase 8: Top-3 Selection Framework

## Objective: Best daily NRFI legs for parlay construction

### Signal hierarchy:
1. Combined p_yrfi rank -- bottom 10% of slate
2. Full-game closing total -- lower = higher NRFI
3. F5 closing total -- independent validation
4. Park factor -- pitcher parks boost NRFI
5. Starter archetype -- CONTACT_RISK exclusion
6. Top-3 lineup stability -- both-changed exclusion

### Filter values:
  FG <=8.0: NRFI=55.6% (n=4107)
  FG >=10.0: NRFI=38.9% (n=699)
  Lift: +16.7%

  F5 <=4.0: NRFI=63.3% (n=1250)
  F5 >=5.5: NRFI=36.9% (n=1234)
  Lift: +26.4%

  Combined (FG<=8.5 & F5<=5.0): NRFI=55.6% (n=4130)
  vs baseline 51.2% = +4.4% lift

  Tightest (FG<=7.5 & F5<=4.5): NRFI=55.7% (n=1303)

### Breakeven at -135 (57.4% implied):
  Baseline: NRFI=51.2%, ROI=-10.8% (n=9900)
  FG<=8.0: NRFI=55.6%, ROI=-3.3% (n=4107)
  FG<=8.5 & F5<=5.0: NRFI=55.6%, ROI=-3.2% (n=4130)
  FG<=7.5 & F5<=4.5: NRFI=55.7%, ROI=-3.0% (n=1303)

### Recommended daily selection:
1. Closing total <= 8.5
2. F5 total <= 5.0
3. Micro-model p_yrfi bottom 10%
4. Exclude CONTACT_RISK starters
5. Exclude both-top-3-changed lineups
6. Pitcher park preferred