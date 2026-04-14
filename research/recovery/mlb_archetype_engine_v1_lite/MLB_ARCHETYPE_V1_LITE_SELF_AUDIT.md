# MLB Archetype Engine V1-Lite — Self-Audit

## PIT-Safety Audit
| Check | Answer | Evidence |
|-------|--------|----------|
| All dimensions use shift(1)? | YES | lineup rolling via `.shift(1).rolling(15).sum()` before dividing |
| Starter rolling uses shift(1)? | YES | `.shift(1).rolling(5).sum()` on K, BB, BF per pitcher |
| Concentration Gini uses shift(1)? | YES | per-game Gini then `.shift(1).rolling(15).mean()` |
| Minimum game requirement? | YES | lineup min_periods=10; starter min_periods=3 |
| NULL labels excluded from testing? | YES | `halves_clean` requires both lineup_arch and sp_profile notna() |

## Split Discipline
| Check | Answer | Evidence |
|-------|--------|----------|
| Discovery/validation/OOS kept separate? | YES | DISCOVERY=[2022,2023], VALIDATION=[2024], OOS=[2025] |
| Tercile cuts derived from discovery only? | YES | `disc_tg = team_game[team_game['season'].isin([2022,2023])]` |
| SP profile cuts derived from discovery only? | YES | `disc_sp = starters[starters['season'].isin([2022,2023])]` |
| Validation/OOS use frozen discovery cuts? | YES | Same `patience_cuts`, `damage_cuts`, `k_cuts`, `bb_cuts` applied |
| Main effect baselines frozen from discovery? | YES | `lineup_means`, `sp_means` from discovery halves only |

## Source Exclusion
| Check | Answer | Evidence |
|-------|--------|----------|
| pitcher_recent_adjusted_features.parquet avoided? | YES | Not imported or referenced |
| sim/phase2_build_features.py outputs avoided? | YES | feature_table.parquet not used |
| mlb_sim/data/ V1-era tables avoided? | YES | Not imported |
| Only hitter_game_logs + pitcher_game_logs + game_table used? | YES | Three sources only |

## Reporting Discipline
| Check | Answer | Evidence |
|-------|--------|----------|
| Cell sizes reported honestly? | YES | N column in all interaction tables; LOW_N flag for n<50 |
| Season-level breakdown provided? | YES | Phase 4 shows 2022 vs 2023 top cells separately |
| All cells reported (not cherry-picked)? | YES | Full interaction table sorted by residual, all rows shown |
| Kill rule defined and applied? | YES | Discovery: max valid residual < 0.20 → STOP |
| Verdict pre-specified? | YES | NO-GO / PROMISING BUT THIN / GO criteria defined before Phase 4 |

## Final Answers
- All dimensions PIT-safe with shift(1)? **YES**
- Discovery/validation/OOS kept separate? **YES**
- Tercile cuts derived from discovery only? **YES**
- Excluded sources avoided? **YES**
- Cell sizes reported honestly? **YES**
- Season-level breakdowns provided? **YES**
## Data Quality Caveat

### Home-Side Coverage Asymmetry
- home_lineup_arch coverage: 26.7% vs away_lineup_arch coverage: 98.2%
- Root cause: hitter_game_logs has unequal H/A entries — 76,321 home rows vs 128,227 away rows
- Impact: the ~14,234 valid discovery team-halves are asymmetrically weighted toward away-team observations
- This asymmetry means the "home lineup" dimension tests a non-representative subset
- The apparent discovery signal (max residual 0.804) should be interpreted with this caveat
- The validation failure (40% directional consistency) may partly reflect this structural bias

### Coverage Assessment
| Check | Answer | Notes |
|-------|--------|-------|
| Home lineup coverage adequate? | PARTIAL | 26.7% home vs 98.2% away — structural imbalance |
| Away lineup coverage adequate? | YES | 98.2% |
| SP profile coverage adequate? | YES | 90.3% both sides |
| Data asymmetry disclosed? | YES | hgl has 128K away vs 76K home batter rows |
