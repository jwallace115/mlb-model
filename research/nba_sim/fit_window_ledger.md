# NBA Sim — Fit-Window Ledger

Updated: 2026-10-05. One row per (season, object, use). Every use of historical data — including
viewing — must be recorded here on the day it happens.

## Rule

No season 2022-23 through 2025-26 is blind to this lane. The sim may use 2024-25 and 2025-26 for
validation/holdout only if no S-design choice is tuned on them from today forward. The first blind
evidence for the NBA sim is **2026-27**.

## Ledger

| Season | Object | Use | Citing file or commit |
|--------|--------|-----|----------------------|
| 2022-23 | Ridge totals model (Phase 3) | discovery (training) | nba/train_model.py L45-48, L105-109 |
| 2023-24 | Ridge totals model (Phase 3) | discovery (training) | nba/train_model.py L45-48, L105-109 |
| 2024-25 | Ridge totals model (Phase 3) | validation | nba/train_model.py L45-48, L105-109; nba/backtest.py |
| 2025-26 | Ridge totals model (Phase 4B) | consumed holdout (OOS test, no retraining) | nba/phase4b.py |
| 2022-23 | Small-edge system (0-1 edge) | discovery | nba/phase8_replay_2025_summary.txt; nba/docs/nba_small_edge_postmortem.md |
| 2023-24 | Small-edge system (0-1 edge) | discovery | nba/phase8_replay_2025_summary.txt; nba/docs/nba_small_edge_postmortem.md |
| 2024-25 | Small-edge system (0-1 edge) | validation (holdout) | nba/phase8_replay_2025_summary.txt; nba/docs/nba_small_edge_postmortem.md |
| 2025-26 | Small-edge system (0-1 edge) | consumed holdout (point-in-time replay) | nba/phase8_replay_2025_summary.txt |
| 2022-23 | Archetype classification (Phase 5-6) | discovery (in-sample) | research/recovery/nba_archetype_revalidation/phase56_verdicts.md |
| 2023-24 | Archetype classification (Phase 5-6) | discovery (in-sample) | research/recovery/nba_archetype_revalidation/phase56_verdicts.md |
| 2024-25 | Archetype classification (Phase 5-6) | discovery (in-sample, labelled OOS but list tuned on it) | research/recovery/nba_archetype_revalidation/phase56_verdicts.md |
| 2022-23 | Venue signal: ROAD_WARRIOR @ STRONG_HOME | discovery | commit b448fbd36 (2026-03-21); research/nba_venue_subset_analysis.txt |
| 2023-24 | Venue signal: ROAD_WARRIOR @ STRONG_HOME | discovery | commit b448fbd36 |
| 2024-25 | Venue signal: ROAD_WARRIOR @ STRONG_HOME | discovery (list selected from this season, then tested on it = CHECK 2 fail) | commit 58704cd42, 7868c748e (2026-03-22); research/nba_venue_pruned_validation.txt; research/nba_venue_expansion_candidates.txt |
| 2025-26 | Venue signal: RW@SH pre-registered forward test | consumed holdout (pre-registered, real prices, locked lists) | research/nba_layers/legacy_review_2026-09-30/run_rw_sh_2025_26.py; PREREG_rw_sh_2025_26.md |
| 2022-23 | Referee crew signal | discovery/validation (no explicit split) | research/nba_referee_validation.txt |
| 2023-24 | Referee crew signal | discovery/validation (no explicit split) | research/nba_referee_validation.txt |
| 2024-25 | Referee crew signal | discovery/validation (no explicit split) | research/nba_referee_validation.txt |
| 2023-24 | Props pipeline (P2-P5) | discovery (training) | nba/props/p2_summary.txt |
| 2024-25 | Props pipeline (P2-P5) | validation | nba/props/p2_summary.txt |
| 2025-26 | Props pipeline (P2-P5) | consumed holdout (OOS) | nba/props/p2_summary.txt |
| 2022-23 | Schedule fatigue signals | discovery (training) | research/nba/schedule_fatigue/hypothesis_registry.json |
| 2023-24 | Schedule fatigue signals | discovery (training) | research/nba/schedule_fatigue/hypothesis_registry.json |
| 2024-25 | Schedule fatigue signals | validation | research/nba/schedule_fatigue/hypothesis_registry.json |
| 2025-26 | Schedule fatigue signals | holdout (registered, not yet consumed) | research/nba/schedule_fatigue/hypothesis_registry.json |
| 2022-23 | Historical odds (B-D1 lines) | viewed (data pull, no model built) | research/nba_layers/NBA_LAYERS_DECISION_v1.md B-D1 |
| 2023-24 | Historical odds (B-D1 lines) | viewed (data pull, no model built) | research/nba_layers/NBA_LAYERS_DECISION_v1.md B-D1 |
| 2024-25 | Historical odds (B-D1 lines) | viewed (data pull, no model built) | research/nba_layers/NBA_LAYERS_DECISION_v1.md B-D1 |
| 2025-26 | Historical odds (B-D1 lines) | viewed (data pull, no model built) | research/nba_layers/NBA_LAYERS_DECISION_v1.md B-D1 |
| 2025-26 | RW@SH symmetry check (A5) | viewed (2026-10-05, under ROI computed) | research/nba_layers/legacy_review_2026-09-30/symmetry_rw_sh_2025_26.py |
