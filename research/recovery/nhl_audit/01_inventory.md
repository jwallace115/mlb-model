# NHL Audit -- Phase 1: Object Inventory

## Date: 2026-04-10

## File Inventory (excluding cache/)

### Research/Training Pipeline
| File | Purpose | Trust Status |
|------|---------|-------------|
| phase1_build_canonical.py | Canonical game table from NHL API + MoneyPuck + Odds API | REVIEW |
| phase2_design.md | Feature design document | DOC |
| phase3_build_features_and_ridge.py | Feature table + Ridge model training | CRITICAL REVIEW |
| phase3_model_audit.txt | Phase 3 diagnostics | DOC |
| phase4_sim.py | Poisson simulation engine | REVIEW |
| phase4_sim_audit.txt | Phase 4 diagnostics | DOC |
| phase45_calibration.py | Dynamic seasonal drift calibration | REVIEW |
| phase45_calibration_audit.txt | Phase 4.5 diagnostics | DOC |
| phase5_market_architecture.py | Signal generation + grading + performance report | REVIEW |

### Model Artifacts
| File | Purpose |
|------|---------|
| ridge_home_model.pkl | Home score Ridge model (alpha selected on validate) |
| ridge_away_model.pkl | Away score Ridge model (alpha selected on validate) |

### Data Artifacts
| File | Shape | Purpose |
|------|-------|---------|
| nhl_games_canonical.csv | 6506 x 62 | Raw game data 2021-2025 (+ 2025-26 appended) |
| nhl_feature_table.parquet | 6506 x 54 | Feature table with rolling stats |
| nhl_sim_results.parquet | -- | Phase 4 simulation results |
| nhl_sim_results_calibrated.parquet | -- | Phase 4.5 calibrated results |
| nhl_model_outputs.parquet | -- | Phase 5 model outputs |
| nhl_market_snapshots.parquet | 5246 x 13 | Market snapshot data |
| nhl_clv_snapshots.parquet | 86 x 7 | CLV tracking |
| nhl_decisions.parquet | 783 x 56 | All signals (train/val/oos/live) |
| nhl_results.parquet | -- | Graded results |

### Live Pipeline
| File | Purpose | Trust Status |
|------|---------|-------------|
| nhl_daily_pipeline.py | Live prediction pipeline | CRITICAL REVIEW |
| nhl_refresh_canonical.py | Daily canonical table refresh | REVIEW |
| extend_canonical_2526.py | 2025-26 season extension | REVIEW |
| nhl_summaries.py | Plain-English signal summaries | LOW RISK |
| push_nhl.py | Serialize to JSON for dashboard | LOW RISK |

### Research (Archetypes -- not deployed)
| File | Purpose |
|------|---------|
| research_archetypes/*.py | 6-phase archetype research program |
| research_archetypes/*.md | Archetype research documentation |

### Data Sources
- NHL Stats API (api-web.nhle.com/v1) -- schedule, boxscore, goalie
- MoneyPuck (bulk CSV) -- xGoals, Corsi, HD shots (2021-2024 only)
- The Odds API -- historical + live closing totals

## Season Split Configuration
- Train: 2021-22, 2022-23 (2624 games)
- Validate: 2023-24 (1312 games)
- OOS: 2024-25 (1312 games)
- Live: 2025-26 (1258 games through 2026-04-09)
