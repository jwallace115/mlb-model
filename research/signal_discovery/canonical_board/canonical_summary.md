# Canonical Signal Board — Summary

**Date:** 2026-03-27
**Source:** 300 raw signals → 44 canonical concepts

---

## Overview

| Metric | Count |
|:-------|------:|
| Total canonical concepts | 44 |
| Concepts from new domains (no prior closed research) | 33 |
| Concepts from framework revisits | 11 |
| Upgrade candidates | 12 |
| New signals | 32 |
| Research only | 0 |

## Classification Distribution

| Classification | Count | Description |
|:---------------|------:|:------------|
| NEW_SIGNAL | 32 | Low similarity to existing signals (< 0.30) |
| UPGRADE_CANDIDATE | 12 | Overlaps existing signal with more advanced framework |
| RESEARCH_ONLY | 0 | Requires data/infrastructure not yet available |

## Domain Distribution

| Domain | Concepts | Description |
|:-------|---:|:------------|
| PITCHER | 9 | |
| MARKET_BEHAVIOR | 6 | |
| BULLPEN | 4 | |
| LINEUP | 4 | |
| WEATHER | 3 | |
| RUN_DISTRIBUTION | 3 | |
| SEQUENCING | 3 | |
| GAME_STATE | 3 | |
| TRAVEL | 3 | |
| UMPIRE | 2 | |
| BALLPARK | 2 | |
| PLAYER_FORM | 2 | |

## Upgrade Candidates — Cross-Reference

These 12 concepts apply more advanced frameworks to mechanisms already partially captured by existing LIVE or SHADOW signals.

| # | Concept | Upgrades | Similarity | Frameworks |
|:--|:--------|:---------|---:|:-----------|
| 1 | Pitcher latent fatigue state | F5_totals (LIVE) | 0.47 | DISTRIBUTION_MODEL, EVT_TAIL_MODEL, STATE_MODEL |
| 2 | Pitcher repertoire mix change | V1 (LIVE) | 0.44 | BAYESIAN_UPDATE, CAUSAL_IV, DISTRIBUTION_MODEL +3 |
| 3 | Pitcher deception / entropy | ADJ_CONTACT (SHADOW) | 0.47 | DISTRIBUTION_MODEL, HEURISTIC |
| 4 | Pitcher command regime shift | V1 (LIVE) | 0.44 | BAYESIAN_UPDATE, CAUSAL_IV, DISTRIBUTION_MODEL +1 |
| 5 | TRAVEL — unclustered signals | ST02 (LIVE) | 0.47 | CAUSAL_IV |
| 6 | PITCHER — unclustered signals | V1 (LIVE) | 0.44 | BAYESIAN_UPDATE, CAUSAL_IV, EVT_TAIL_MODEL |
| 7 | Pitcher injury/IL return adjustment lag | V1 (LIVE) | 0.44 | BAYESIAN_UPDATE, EVT_TAIL_MODEL, STATE_MODEL |
| 8 | Starter short-leash / early exit | combined_short_exit (SHADOW) | 0.86 | EVT_TAIL_MODEL |
| 9 | Timezone / jet lag effect | ST02 (LIVE) | 0.47 | BAYESIAN_UPDATE, CAUSAL_IV |
| 10 | Road trip fatigue accumulation | ST02 (LIVE) | 0.82 | CAUSAL_IV, EVT_TAIL_MODEL, STATE_MODEL |
| 11 | Pitcher-lineup platoon mismatch | V1 (LIVE) | 0.58 | BAYESIAN_UPDATE |
| 12 | Pitcher quality metric lag | V1 (LIVE) | 0.86 | BAYESIAN_UPDATE, CAUSAL_IV, DISTRIBUTION_MODEL +3 |

## Framework Variant Analysis

The most valuable research opportunities are concepts that revisit closed domains with fundamentally different mathematical approaches:

| Closed Domain | Original Framework | New Frameworks Available |
|:--------------|:-------------------|:------------------------|
| BULLPEN | REGRESSION_FEATURE | STATE_MODEL, EVT_TAIL_MODEL, BAYESIAN_UPDATE, CAUSAL_IV |
| WEATHER | REGRESSION_FEATURE | EVT_TAIL_MODEL, DISTRIBUTION_MODEL, CAUSAL_IV |
| UMPIRE | HEURISTIC | STATE_MODEL, BAYESIAN_UPDATE, DISTRIBUTION_MODEL |
| BALLPARK | REGRESSION_FEATURE | STATE_MODEL, CAUSAL_IV, BAYESIAN_UPDATE |

The key insight is that prior research in these domains used linear regression features or simple heuristics. The framework_revisit signals propose state-space models, extreme value theory, Bayesian updating, and causal inference — fundamentally different approaches that could reveal signal where regression could not.
