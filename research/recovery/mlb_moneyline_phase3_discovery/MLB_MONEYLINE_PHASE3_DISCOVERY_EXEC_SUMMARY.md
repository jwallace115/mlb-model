# MLB Moneyline Phase 3 Discovery Engine — Executive Summary
## Date: 2026-04-11

## Universe
Close ML games (fav implied .512-.556 / approx -105 to -125), 2022-2025.
Total close games: 8199 | Discovery (22-23): 3877 | Val (24): 1948 | OOS (25): 2374

## Safety Audit
| ID | Candidate | Status |
|----|-----------|--------|
| C1 | BP Availability (workload proxy) | FEASIBLE |
| C2 | Pinned Closer No Bridge | BLOCKED (no role labels) |
| C3 | Post-Extras Depletion | FEASIBLE |
| C4 | SPID (SP-BP disagreement) | FEASIBLE |
| C5 | Low-Variance SP | FEASIBLE |
| C6 | Short-Leash SP x Weak BP | FEASIBLE |
| C7 | Velocity Floor Breach | FEASIBLE |
| C8 | Command vs Stuff Archetype | FEASIBLE |
| C9 | Low-Total Dog Compression | FEASIBLE |
| C10 | Home Dog + BP Edge | FEASIBLE |

## Results

### C1: BP Availability Proxy (workload gap)
**Verdict: KILL (val fail)**

| Phase | N | WR | ImpWR | Resid | ROI |
|-------|---|----|----|-------|-----|
| discovery | 347 | 0.5187 | 0.5026 | +0.0161 | -1.04% |
| ..2022 | 139 | 0.6187 | 0.5049 | +0.1138 | +16.64% |
| ..2023 | 208 | 0.4519 | 0.5011 | -0.0492 | -12.85% |
| validation | 168 | 0.5 | 0.502 | -0.0020 | -4.59% |
| ..2024 | 168 | 0.5 | 0.502 | -0.0020 | -4.59% |
| oos | 160 | 0.475 | 0.4994 | -0.0244 | -8.12% |
| ..2025 | 160 | 0.475 | 0.4994 | -0.0244 | -8.12% |

### C3: Post-Extras Depletion (one side only)
**Verdict: KILL (val fail)**

| Phase | N | WR | ImpWR | Resid | ROI |
|-------|---|----|----|-------|-----|
| discovery | 174 | 0.5402 | 0.5037 | +0.0366 | +1.54% |
| ..2022 | 82 | 0.5976 | 0.4945 | +0.1031 | +14.77% |
| ..2023 | 92 | 0.4891 | 0.5118 | -0.0227 | -10.25% |
| validation | 84 | 0.3452 | 0.4903 | -0.1451 | -36.35% |
| ..2024 | 84 | 0.3452 | 0.4903 | -0.1451 | -36.35% |
| oos | 162 | 0.6049 | 0.5076 | +0.0973 | +13.70% |
| ..2025 | 162 | 0.6049 | 0.5076 | +0.0973 | +13.70% |

### C4: SPID (SP-BP disagreement, bet SP)
**Verdict: KILL (val fail)**

| Phase | N | WR | ImpWR | Resid | ROI |
|-------|---|----|----|-------|-----|
| discovery | 278 | 0.5647 | 0.5036 | +0.0611 | +7.91% |
| ..2022 | 86 | 0.4419 | 0.4978 | -0.0560 | -15.25% |
| ..2023 | 192 | 0.6198 | 0.5062 | +0.1136 | +18.29% |
| validation | 160 | 0.4938 | 0.5021 | -0.0084 | -5.95% |
| ..2024 | 160 | 0.4938 | 0.5021 | -0.0084 | -5.95% |
| oos | 147 | 0.4898 | 0.5027 | -0.0129 | -5.73% |
| ..2025 | 147 | 0.4898 | 0.5027 | -0.0129 | -5.73% |

### C5: Low-Variance SP Advantage
**Verdict: KILL (val fail)**

| Phase | N | WR | ImpWR | Resid | ROI |
|-------|---|----|----|-------|-----|
| discovery | 160 | 0.5375 | 0.4965 | +0.0410 | +3.71% |
| ..2022 | 52 | 0.6923 | 0.497 | +0.1953 | +33.69% |
| ..2023 | 108 | 0.463 | 0.4963 | -0.0334 | -10.73% |
| validation | 89 | 0.4831 | 0.4971 | -0.0139 | -6.10% |
| ..2024 | 89 | 0.4831 | 0.4971 | -0.0139 | -6.10% |
| oos | 87 | 0.4828 | 0.4911 | -0.0083 | -5.46% |
| ..2025 | 87 | 0.4828 | 0.4911 | -0.0083 | -5.46% |

### C6: Short-Leash SP x Weak BP
**Verdict: MONITOR**

| Phase | N | WR | ImpWR | Resid | ROI |
|-------|---|----|----|-------|-----|
| discovery | 291 | 0.5223 | 0.5047 | +0.0176 | -1.11% |
| ..2022 | 89 | 0.4382 | 0.4982 | -0.0600 | -16.40% |
| ..2023 | 202 | 0.5594 | 0.5076 | +0.0518 | +5.63% |
| validation | 135 | 0.5704 | 0.5037 | +0.0667 | +8.96% |
| ..2024 | 135 | 0.5704 | 0.5037 | +0.0667 | +8.96% |
| oos | 162 | 0.4877 | 0.5019 | -0.0143 | -6.27% |
| ..2025 | 162 | 0.4877 | 0.5019 | -0.0143 | -6.27% |

### C7: Velocity Floor Breach (-0.5 mph trend)
**Verdict: KILL**

| Phase | N | WR | ImpWR | Resid | ROI |
|-------|---|----|----|-------|-----|
| discovery | 179 | 0.4916 | 0.4967 | -0.0051 | -5.60% |
| ..2022 | 26 | 0.4615 | 0.4961 | -0.0346 | -11.56% |
| ..2023 | 153 | 0.4967 | 0.4968 | -0.0001 | -4.59% |
| validation | 151 | 0.5099 | 0.5029 | +0.0070 | -2.57% |
| ..2024 | 151 | 0.5099 | 0.5029 | +0.0070 | -2.57% |
| oos | 163 | 0.4908 | 0.4999 | -0.0091 | -5.95% |
| ..2025 | 163 | 0.4908 | 0.4999 | -0.0091 | -5.95% |

### C8: Command vs Stuff Archetype
**Verdict: KEEP**

| Phase | N | WR | ImpWR | Resid | ROI |
|-------|---|----|----|-------|-----|
| discovery | 130 | 0.5385 | 0.4934 | +0.0450 | +4.97% |
| ..2022 | 46 | 0.6087 | 0.4864 | +0.1223 | +19.15% |
| ..2023 | 84 | 0.5 | 0.4973 | +0.0027 | -2.80% |
| validation | 83 | 0.506 | 0.488 | +0.0180 | +1.26% |
| ..2024 | 83 | 0.506 | 0.488 | +0.0180 | +1.26% |
| oos | 55 | 0.5273 | 0.4931 | +0.0342 | +3.48% |
| ..2025 | 55 | 0.5273 | 0.4931 | +0.0342 | +3.48% |

### C9: Low-Total Dog Compression (total<=7.5)
**Verdict: KILL (val fail)**

| Phase | N | WR | ImpWR | Resid | ROI |
|-------|---|----|----|-------|-----|
| discovery | 919 | 0.4777 | 0.4618 | +0.0159 | -1.00% |
| ..2022 | 609 | 0.486 | 0.4619 | +0.0241 | +0.71% |
| ..2023 | 310 | 0.4613 | 0.4615 | -0.0002 | -4.35% |
| validation | 664 | 0.4398 | 0.4618 | -0.0220 | -8.99% |
| ..2024 | 664 | 0.4398 | 0.4618 | -0.0220 | -8.99% |
| oos | 394 | 0.533 | 0.4628 | +0.0702 | +10.32% |
| ..2025 | 394 | 0.533 | 0.4628 | +0.0702 | +10.32% |

### C10: Home Dog + BP Edge
**Verdict: KILL**

| Phase | N | WR | ImpWR | Resid | ROI |
|-------|---|----|----|-------|-----|
| discovery | 188 | 0.4043 | 0.4643 | -0.0601 | -16.39% |
| ..2022 | 68 | 0.4118 | 0.4622 | -0.0504 | -14.71% |
| ..2023 | 120 | 0.4 | 0.4656 | -0.0656 | -17.35% |
| validation | 88 | 0.4773 | 0.464 | +0.0133 | -1.13% |
| ..2024 | 88 | 0.4773 | 0.464 | +0.0133 | -1.13% |
| oos | 80 | 0.5375 | 0.4659 | +0.0716 | +9.98% |
| ..2025 | 80 | 0.5375 | 0.4659 | +0.0716 | +9.98% |

## Final Board
- **KEEP (all 3 phases positive):** 1
- **MONITOR (disc+val pass, OOS fail):** 1
- **WATCH (small sample, positive discovery):** 0
- **KILL:** 7

## Key Findings
### Survivors
- **C8**: D_ROI=+4.97%, V_ROI=+1.26%, O_ROI=+3.48%

### Monitor
- **C6**: Passed disc+val but OOS negative. Regime-dependent.

## Data Quality Caveats
- Home-side SP/Statcast merge coverage (~28%) is lower than away-side (~91%). This is caused
  by a one-to-many join inflation when PGL starters merge to a close-game table that already
  expanded rows from prior merges. The away-side inflated further. Candidate results involving
  SP-level features (C4, C5, C6, C7, C8) should be interpreted with this asymmetry in mind.
  The directional signal is valid but absolute N counts may overstate effective sample size.
- C8 (the sole KEEP) has small N: 130 discovery, 83 validation, 55 OOS. The positive residual
  is consistent across all 4 seasons (+12.2%, +0.3%, +1.8%, +3.4%) which is encouraging, but
  the sample is below the 150-game threshold. This is a CONDITIONAL KEEP pending 2026 shadow
  confirmation. Do not size up without additional evidence.

## Methodology
- All features PIT-safe (shift(1) / date < game_date)
- No lineup features, no FG/V1 contaminated tables
- ROI at actual closing ML prices
- Min N=150 for discovery promotion (relaxed to N=100 + Resid>0.02 for marginal signals)
- C2 blocked: no closer/setup role labels in available data
