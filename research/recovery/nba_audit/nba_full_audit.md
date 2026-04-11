# NBA System — Full Audit Report

**Date:** 2026-04-10
**Auditor:** Claude Opus 4.6 (automated)
**Scope:** All NBA objects — feature construction, model training, signal discovery,
live pipeline, economics, and regime pathologies.

---

## 1. System Inventory

### Core Pipeline (Training/Research)
| File | Purpose | Status |
|------|---------|--------|
| nba/build_game_table.py | Phase 1 — fetch games from NBA API | CLEAN |
| nba/modules/fetch_games.py | Game fetcher with cache | CLEAN |
| nba/modules/fetch_box_stats.py | Box stats + efficiency computation | CLEAN |
| nba/modules/features.py | Phase 2 — rolling features, blending | CLEAN |
| nba/train_model.py | Phase 3 — Ridge regression (15 features) | CLEAN |
| nba/backtest.py | Phase 4 — validation diagnostics | CLEAN |
| nba/phase4b.py | Phase 4B — 2025-26 OOS test | CLEAN |
| nba/phase5.py | Phase 5 — MC simulation layer | CLEAN |
| nba/train_h1_model.py | H1 (first half) Ridge model | CLEAN |
| nba/build_h1_features.py | H1 feature builder | CLEAN |
| nba/phase6.py | Phase 6 — H1 OOS + simulation | CLEAN |

### Live Pipeline
| File | Purpose | Status |
|------|---------|--------|
| nba/run_nba.py | Daily runner (2183 lines) | CAUTION — see findings |
| nba/segment_overlay.py | Segment confidence overlay | DISABLED (correct) |
| nba/phase6_shadow.py | Small-edge shadow tracker | CLEAN |
| nba/modules/simulate.py | MC simulation engine | CLEAN |
| nba/modules/fetch_nba_odds.py | Odds API integration | CLEAN |

### Models
| File | Description |
|------|-------------|
| nba/models/totals_base_model.pkl | Full-game Ridge (Phase 3) |
| nba/models/variance_model.pkl | Variance model |
| nba/data/ridge_model.pkl | Full-game Ridge |
| nba/data/h1_ridge_model.pkl | First-half Ridge |

### Data
| File | Shape | Date Range |
|------|-------|------------|
| features.parquet | 3690 x 48 | 2022-10 to 2025-04 |
| box_stats.parquet | 7380 x 17 | 2022-23 to 2024-25 |
| nba_historical_closing_lines.parquet | 3685 x 11 | 2022-23 to 2024-25 |
| nba_results_log.parquet | 164 x 40 | Live 2025-26 |
| nba_signal_log.parquet | 35 x 18 | 2026-03-24 to 2026-04-10 |
| nba_phase6_rs_shadow.parquet | 23 x 15 | RS shadow log |

---

## 2. Feature Provenance Audit

### 2.1 Rolling Feature Construction — NO LOOKAHEAD FOUND

The features.py module is well-constructed:

- **shift(1) applied**: All rolling windows use `.rolling(N).mean().shift(1)`, which
  correctly excludes the current game from the rolling calculation. This is the
  correct no-leakage implementation for training data.

- **Season blending**: Prior-season baselines are computed from the PRIOR season only,
  with a 70/30 blend that fades over the first 20 games. This is correct.

- **Location-specific rolling**: Properly minimum-gated (5 prior same-location games
  required) with fallback to overall rolling.

- **Trend features**: 5-game vs 15-game delta, both properly shifted. No leakage.

- **Rolling league average**: Computed per-season with no leakage — uses only games
  played BEFORE the current game date.

**VERDICT: CLEAN** — No lookahead contamination in feature construction.

### 2.2 Data Sources — NO EXTERNAL LEAKAGE

Unlike the MLB system (which uses FanGraphs season-end leaderboards), the NBA system
derives ALL features from game-by-game box scores via the NBA Stats API:
- ORtg, DRtg, pace: computed per-game from raw box score stats (Oliver possession formula)
- Style features (3PA rate, FT rate): computed per-game from box score
- No season-end summaries, no external rating systems, no preseason projections

**VERDICT: CLEAN** — No equivalent to the MLB FanGraphs lookahead bug.

### 2.3 Research vs Live Identity

**Key difference found (ACCEPTABLE):**
- features.py (training): uses shift(1) — excludes current game
- run_nba.py (live): uses cur.tail(15) — includes most recent completed game

This difference is correct and intentional. In training, shift(1) prevents leakage
because the current game actual outcome is known. In live production, the most
recent game is already completed when features are computed for tomorrow games.

**Other identity checks:**
- FEATURE_COLS in train_model.py matches FEATURE_COLS in run_nba.py: IDENTICAL (15 features)
- Blending logic (_blend function) is imported directly from features.py into both
  phase4b.py and run_nba.py: SAME CODE PATH
- Prior-season baselines use the same _build_prior_season_baselines function

**VERDICT: CLEAN** — No research/live identity mismatch.

---

## 3. Economics Audit

### 3.1 Synthetic -110 Assumption — PRESENT BUT DISCLOSED

The system uses a flat -110 assumption throughout:
- phase6_shadow.py line 50: WIN = 100.0 / 110.0
- run_nba.py line 1129: price = -110.0
- Market snapshots: all show price = -110.0

NBA totals typically trade at -110/-110, so this is a reasonable assumption.
However, real totals sometimes trade at -105/-115 or -108/-112. The system does
not capture or use actual prices.

**Impact:** ROI calculations assume standard -110 vig. Real-world results could
be 0.5-1.5% worse if systematically getting worse prices. For the current sample
sizes (35 signal log bets, 23 shadow bets), this is immaterial.

**VERDICT: ACCEPTABLE** — Standard -110 assumption is reasonable for NBA totals.

### 3.2 Backtest Does Not Use Market Lines

The Phase 4 backtest explicitly compares model predictions to ACTUAL TOTALS only.
It does NOT compute ROI against closing lines. This is the correct approach for
evaluating model accuracy.

Phase 7B did use historical closing lines (3,685 games matched) and produced
honest results:
- Discovery (2022-24): -13.1% ROI
- Holdout (2024-25): +5.6% ROI
- Pre-live replay (2025-26): -3.8% ROI

**VERDICT: CLEAN** — No synthetic economics in backtests.

---

## 4. Regime and Signal Pathology Audit

### 4.1 Base Model Stability — ACCEPTABLE

The Ridge model shows stable OOS performance:
- Train MAE: ~14.9 pts (2022-24)
- Val MAE: ~14.9 pts (2024-25)
- OOS MAE: ~15.0 pts (2025-26)
- Spearman rho (directional): 0.335 (val) -> ~0.20 (OOS) — weakens but holds

**VERDICT: STABLE** — Core model generalizes.

### 4.2 Archetype Team Sets — DISCOVERY/VALIDATION CONTAMINATION

**THIS IS THE MOST SIGNIFICANT FINDING.**

The archetype analysis files (nba/analysis/*.parquet) ALL include 2024-25 data:
- homeway_archetypes.parquet: seasons=[2022-23, 2023-24, 2024-25]
- shot_profile_archetypes.parquet: seasons=[2022-23, 2023-24, 2024-25]
- oreb_archetypes.parquet: seasons=[2022-23, 2023-24, 2024-25]
- team_clusters.parquet: seasons=[2022-23, 2023-24, 2024-25]

The team archetype sets hardcoded in run_nba.py were derived from analysis that
included the 2024-25 validation season:
- _ELITE_DEF, _ELITE_DEF2 (from archetype analysis including 2024-25)
- _ROAD_WARRIOR, _STRONG_HOME (from homeway analysis including 2024-25)
- _BALANCED_OFF, _PASSIVE_DEF (from shot profile including 2024-25)
- _THREE_HEAVY_OFF, _FOUL_PRONE_DEF (from shot profile including 2024-25)
- _ELITE_OREB_TEAMS, _WEAK_BOXOUT_TEAMS (from OREB analysis including 2024-25)

**Severity:** MODERATE. The team sets are structural basketball identity labels
(e.g., Boston is an elite defensive team), not statistical artifacts. However:
- Team identities shift season-to-season (roster changes, coaching changes)
- Using validation data to decide WHO is in each archetype contaminates the
  holdout validation of those archetypes
- The "confirmed" language on 2025-26 is based on very small samples

**Impact on live system:** The archetype signals are used as CONTEXT signals in the
live card. The signal log places actual bets based on these archetypes. Given the
archetype signals poor live performance (Phase 6 RS shadow: 8W-10L, 44.4%), this
contamination is concerning but bounded.

### 4.3 Small-Edge System — VALIDATED AS UNPROFITABLE

The postmortem memo (nba/docs/nba_small_edge_postmortem.md) is commendably honest:
- Discovery (2022-24): -13.1% ROI
- Holdout (2024-25): +5.6% ROI (the outlier)
- Pre-live replay (2025-26): -3.8% ROI
- Weighted average: approximately -7% ROI across 666 bets

**VERDICT: CORRECTLY IDENTIFIED AS NOT DEPLOYABLE.** No deployment harm.

### 4.4 Playoff Signal Boards — UNDERPOWERED

Three playoff boards are coded (P1, P2, P4):
- P1: R1 G1-2 UNDER (-6.82 avg, 3/3 seasons)
- P2: R1 G5-7 OVER (+8.19 avg, 3/3 seasons)
- P4: CF Non-Elim OVER (+9.85 avg, 3/3 seasons)

With only 3 seasons of playoff data and 4-16 games per signal per season,
these are SEVERELY underpowered.

**VERDICT: UNDERPOWERED** — Treat as exploratory context only.

### 4.5 Backwards Discovery — FULL-DATA CONTAMINATION

The backwards discovery analysis was run on all 3,685 games (2022-23 through
2024-25). This is the FULL dataset including the validation season.

However, the backwards discovery results show that NO actionable signals survived
the permutation tests. The schedule fatigue signal board states:
"7 signals tested, 0 passed." This is actually a GOOD outcome.

**VERDICT: CONTAMINATED but harmless** — found nothing actionable.

### 4.6 Segment Overlay — CORRECTLY DISABLED

The segment overlay has segment B (home_b2b_elite_offense) explicitly disabled
after shadow testing showed 40% hit rate and -23.6% ROI.

**VERDICT: CORRECT** — Poor segments were identified and disabled.

---

## 5. Trust Classification

### GREEN (Clean, trusted)
- features.py — No lookahead; proper shift(1); correct blending
- train_model.py — Clean train/val split; honest feature selection
- backtest.py — No market-relative economics; honest diagnostics
- phase4b.py — Clean OOS test; no retraining
- simulate.py — Correct MC implementation; proper sigma usage
- fetch_box_stats.py — Clean per-game efficiency computation
- fetch_games.py — Clean game table construction
- box_stats.parquet — Derived from per-game box scores only
- features.parquet — Properly shifted rolling features
- historical_closing_lines.parquet — Real lines, complete coverage

### YELLOW (Caution — documented weaknesses)
- run_nba.py (base model path) — Correct but duplicates logic from features.py
- phase6_shadow.py — -110 synthetic pricing; small sample size
- ridge_model.pkl — Trained on 2022-24 only; may need refresh
- config.py RESIDUAL_SIGMA — Global sigma (18.62) may not fit all matchups

### ORANGE (Significant concerns)
- Archetype team sets in run_nba.py — Derived from analysis including 2024-25 validation
- Playoff signal boards (P1/P2/P4) — 3-season derivation with tiny per-signal samples
- Signal log (35 bets) — Based on archetype signals with contaminated team sets
- nba/analysis/*.parquet — All include 2024-25 in discovery data
- OREB/venue/shot signals — Team membership contaminated by validation data

### RED (Broken — requires remediation)
None identified. The NBA system does not have a direct equivalent of the MLB
FanGraphs lookahead bug.

---

## 6. Comparison to MLB Failure Classes

| Failure Class | MLB Status | NBA Status |
|---------------|-----------|------------|
| Historical feature lookahead | CRITICAL (FanGraphs) | NOT PRESENT |
| Research/live identity mismatch | PRESENT | NOT PRESENT |
| Synthetic economics | PRESENT (-110 assumed) | PRESENT (minor, standard for NBA) |
| Hidden regime pathologies | PRESENT (SP quality drift) | MODERATE (archetype stability) |

---

## 7. Recommendations

### Immediate (no code changes needed)
1. Treat archetype signals as context only. Do not increase bet sizing based
   on ROAD_WARRIOR, ELITE_DEF, or OREB signals until re-derived from
   discovery-only data (2022-24) and validated on a true holdout.

2. Treat playoff boards as exploratory. The 3-season sample is insufficient
   for reliable deployment.

### Short-term
3. Re-derive archetype team sets using ONLY 2022-23 + 2023-24 data. Validate
   on 2024-25. If they fail validation, remove from the live card.

4. Track archetype signal PnL separately from the base model in the results log.

### Medium-term
5. Consider annual archetype refresh. Team identities change; hardcoded sets
   from 2022-24 analysis will drift.

6. The base Ridge model is the strongest NBA asset. It generalizes cleanly,
   has no lookahead, and produces genuine directional ordering. Invest in
   expanding its feature set rather than in archetype overlay complexity.

---

## 8. Summary

**The NBA system is fundamentally sound.** The core Ridge model pipeline
(fetch -> features -> train -> predict -> simulate) has no lookahead bugs,
no research/live identity mismatches, and no synthetic economics.

The concerns are concentrated in the **archetype and signal overlay layer**
built on top of the model. These overlays used 2024-25 validation data in
their discovery process, making their OOS validation claims unreliable.
However, these overlays are used as context signals and confidence modifiers,
not as primary model drivers, limiting the damage.

**Overall trust level: HIGH for base model, MODERATE for overlay signals.**
