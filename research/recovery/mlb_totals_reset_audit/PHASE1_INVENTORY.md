# PHASE 1 — Comprehensive Inventory of All MLB Totals Ideas

**Date:** 2026-04-12
**Scope:** Every MLB totals-adjacent signal, model, overlay, engine, and research branch

---

## A. Core Models

| # | Object | Type | Location | Status |
|---|--------|------|----------|--------|
| A1 | V1 Ridge Totals (contaminated) | Trained model | sim/data/phase9_baseline_model.pkl | LIVE (caveated) |
| A2 | V1 Ridge Totals (PIT clean rebuild) | Trained model | research/recovery/v1_clean_model/ | Tested, negative OOS |
| A3 | V1 Rules Mode | Heuristic engine | modules/projections.py | LIVE |
| A4 | V2 Baseline Engine (Model_B) | Trained model | research/recovery/v2_engine/ | Research only |

## B. Overlays (amplify/filter existing signals)

| # | Object | Type | Location | Status |
|---|--------|------|----------|--------|
| B1 | S12 Overlay (CSW-xFIP composite) | Stake amplifier | mlb_sim/pipeline/s12_overlay.py | KILLED (Apr 10) |
| B2 | P09 Overlay (hard-hit x park) | Stake amplifier | mlb_sim/pipeline/p09_overlay.py | KILLED (Apr 10) |
| B3 | ST02 Overlay (road trip fatigue) | Tag overlay | mlb_sim/pipeline/st02_overlay.py | KILLED (Apr 10) |
| B4 | flyball_wind discrete overlay | Interaction overlay | research/recovery/v2_overlay_revalidation/ | FROZEN |

## C. Shadow Signals (standalone, totals-adjacent)

| # | Object | Type | Location | Status |
|---|--------|------|----------|--------|
| C1 | ADJ_CONTACT | Under signal | mlb_sim/pipeline/shadow_signals.py | Shadow-continue |
| C2 | ADJ_HH | Under signal | mlb_sim/pipeline/shadow_signals.py | Shadow-continue |
| C3 | ADJ_K_RATE | Under signal | mlb_sim/pipeline/shadow_signals.py | Shadow-continue |
| C4 | ADJ_BB_RATE | Under signal | mlb_sim/pipeline/shadow_signals.py | FROZEN |
| C5 | ADJ_RUN_SUPP | Under signal | mlb_sim/pipeline/shadow_signals.py | Shadow-continue |
| C6 | CS013 | Under signal | mlb_sim/pipeline/cs013_shadow.py | FROZEN (0 fires) |
| C7 | CS028 | Under signal | mlb_sim/pipeline/cs028_shadow.py | FROZEN (2 fires) |
| C8 | KP04 | Under signal | mlb_sim/pipeline/kp04_shadow.py | FROZEN (0 fires) |
| C9 | CS004 | Under signal | mlb_sim/pipeline/cs004_shadow.py | Shadow |
| C10 | Combined Short Exit | Under signal | mlb_sim/pipeline/combined_short_exit_shadow.py | FROZEN (0 fires) |

## D. F5 (First Five Innings) Signals

| # | Object | Type | Location | Status |
|---|--------|------|----------|--------|
| D1 | F5 Totals Engine (under) | Signal | mlb_sim/pipeline/f5_signal_generator.py | KILLED (V1-dependent) |
| D2 | F5 Totals Engine (over) | Signal | research/f5_over/ | Research only |
| D3 | F5 Run Line Signal B (home) | Signal | mlb_sim/pipeline/f5_runline_signal_generator.py | KEEP (0 flags) |
| D4 | F5 Run Line Signal B (away) | Signal | research/f5_runline/ | Research: FAIL |
| D5 | CS025 F5 RL Command Overlay | Overlay | research/signal_discovery/test_batch_f5/ | Research: PASS |
| D6 | F5 Standalone (not built) | Planned | N/A | DEFERRED |

## E. Team Totals

| # | Object | Type | Location | Status |
|---|--------|------|----------|--------|
| E1 | Team Totals (Home Under) | Signal | mlb/pipeline/team_total_signal.py + research | KILLED (never-matched) |
| E2 | Team Totals (Away Under) | Signal | Same | KILLED (suppressed in code) |
| E3 | Team Totals (Away Over) | Signal | Same | Suppressed by design |

## F. Market Structure Research

| # | Object | Type | Location | Status |
|---|--------|------|----------|--------|
| F1 | Alt-Total Surface Mispricing | Research | research/mlb_discovery/ | CLOSED |
| F2 | Run-Line Comeback Asymmetry | Research | research/mlb_discovery/ | CLOSED |
| F3 | F5 vs Full-Game Path Mismatch | Research | research/mlb_path_mismatch/ | Research in progress |
| F4 | Cross-Market Triangle | Research | research | Market data only |

## G. Over-Side Research

| # | Object | Type | Location | Status |
|---|--------|------|----------|--------|
| G1 | Over Scanner Wave 1 (OV043 etc) | Research | research/over_scanner_wave1/ | Promoted candidates |
| G2 | V2 Over Bias | Diagnostic | research/recovery/v2_engine/ | Identified, not actionable |

## H. Distribution / Shape / Props

| # | Object | Type | Location | Status |
|---|--------|------|----------|--------|
| H1 | Distribution Shape Engine | Research | mlb/distribution_shape/ | Phase 1 complete |
| H2 | NRFI Selector (Phase 1-5) | Research | research/recovery/nrfi_phase1-5/ | Selector built, not deployed |
| H3 | MLB Props (K, TB, Hits) | Research | mlb/props/ + research/mlb_props/ | Multiple phases |

## I. Signal Discovery Infrastructure

| # | Object | Type | Location | Status |
|---|--------|------|----------|--------|
| I1 | Canonical Signal Board (44 concepts) | Infrastructure | research/signal_discovery/canonical_board/ | Reference |
| I2 | Engine 1-6 (pitcher/bullpen/archetype/umpire/run-env/cascade) | Research | research/signal_discovery/ | Scanned, results vary |

---

## Mandatory Object Count: 41 distinct ideas/objects inventoried
