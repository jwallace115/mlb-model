# MLB Moneyline Phase 3 Discovery — Executive Summary

## Date: 2026-04-11

## Universe
Close moneyline games (fav -105 to -125 implied), 2022-2025.

## 10 Candidates Evaluated
| ID | Name | Safety |
|----|------|--------|
| C1 | BP Availability Proxy (workload) | FEASIBLE |
| C2 | Pinned Closer No Bridge | BLOCKED (no role labels) |
| C3 | Post-Extras Depletion | FEASIBLE |
| C4 | SPID (SP good, BP bad) | FEASIBLE |
| C5 | Low-Variance SP Advantage | FEASIBLE |
| C6 | Short-Leash SP x Weak BP | FEASIBLE |
| C7 | Velocity Floor Breach | FEASIBLE |
| C8 | Command vs Stuff Archetype | FEASIBLE |
| C9 | Low-Total Dog Compression | FEASIBLE |
| C10 | Home Dog + BP Edge | FEASIBLE |

## Results Board

### C1: BP Availability Proxy (workload)
- **Verdict: MONITOR (val pass, OOS fail)**
- Discovery (2022-23): N=404, Resid=+0.0195, ROI=-0.48%
- Validation (2024): N=185, Resid=+0.0010, ROI=-4.01%
- OOS (2025): N=176, Resid=-0.0218, ROI=-7.38%
  - 2022: N=188, WR=0.6223, Resid=+0.1243, ROI=+18.57%
  - 2023: N=216, WR=0.4306, Resid=-0.0717, ROI=-17.06%
  - 2024: N=185, WR=0.5027, Resid=+0.0010, ROI=-4.01%
  - 2025: N=176, WR=0.4773, Resid=-0.0218, ROI=-7.38%

### C3: Post-Extras Depletion
- **Verdict: KILL**
- Discovery (2022-23): N=130, Resid=-0.0194, ROI=-9.65%
- Validation (2024): N=52, Resid=-0.0353, ROI=-11.70%
- OOS (2025): N=72, Resid=-0.0612, ROI=-16.30%
  - 2022: N=55, WR=0.5273, Resid=+0.0320, ROI=-2.00%
  - 2023: N=75, WR=0.4533, Resid=-0.0571, ROI=-15.26%
  - 2024: N=52, WR=0.4615, Resid=-0.0353, ROI=-11.70%
  - 2025: N=72, WR=0.4444, Resid=-0.0612, ROI=-16.30%

### C4: SPID (SP good, BP bad = bet SP side)
- **Verdict: KILL**
- Discovery (2022-23): N=0, Resid=+0.0000, ROI=+0.00%

### C5: Low-Variance SP Advantage
- **Verdict: KILL**
- Discovery (2022-23): N=0, Resid=+0.0000, ROI=+0.00%

### C6: Short-Leash SP x Weak BP
- **Verdict: KILL**
- Discovery (2022-23): N=0, Resid=+0.0000, ROI=+0.00%

### C7: Velocity Floor Breach
- **Verdict: KILL**
- Discovery (2022-23): N=0, Resid=+0.0000, ROI=+0.00%

### C8: Command vs Stuff Archetype
- **Verdict: KILL**
- Discovery (2022-23): N=0, Resid=+0.0000, ROI=+0.00%

### C9: Low-Total Dog Compression
- **Verdict: KILL**
- Discovery (2022-23): N=425, Resid=-0.0272, ROI=-9.78%
- Validation (2024): N=243, Resid=-0.0055, ROI=-5.46%
- OOS (2025): N=163, Resid=+0.0080, ROI=-2.64%
  - 2022: N=272, WR=0.4007, Resid=-0.0611, ROI=-17.02%
  - 2023: N=153, WR=0.4967, Resid=+0.0329, ROI=+3.11%
  - 2024: N=243, WR=0.4568, Resid=-0.0055, ROI=-5.46%
  - 2025: N=163, WR=0.4724, Resid=+0.0080, ROI=-2.64%

### C10: Home Dog + BP Edge
- **Verdict: KILL**
- Discovery (2022-23): N=196, Resid=-0.0498, ROI=-14.41%
- Validation (2024): N=105, Resid=-0.0078, ROI=-5.66%
- OOS (2025): N=84, Resid=+0.1057, ROI=+17.05%
  - 2022: N=79, WR=0.4177, Resid=-0.0431, ROI=-13.35%
  - 2023: N=117, WR=0.4103, Resid=-0.0543, ROI=-15.13%
  - 2024: N=105, WR=0.4571, Resid=-0.0078, ROI=-5.66%
  - 2025: N=84, WR=0.5714, Resid=+0.1057, ROI=+17.05%

## Summary Counts
- **KEEP (3-phase survivor):** 0
- **MONITOR (val pass, OOS fail):** 1
- **WATCH (small sample):** 0
- **KILL:** 8

## Key Takeaways
No candidates survived all three phases with N>=150 and positive residual.

### Monitor List
- **C1** (BP Availability Proxy (workload)): Passed validation but failed OOS. Could be regime-dependent or sample-size issue.

## Methodology Notes
- All features PIT-safe (shift(1) or date < game_date)
- No lineup features used
- No FanGraphs/V1 contaminated tables
- Economic ROI computed at actual closing ML prices
- Minimum N=150 for promotion; smaller samples noted as WATCH
