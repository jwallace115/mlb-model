# Over Scanner Standalone Retest — Executive Summary

**Date:** 2026-04-12
**Scope:** 8 signals tested standalone (no V1 gate)

## Background

The Over Scanner Wave 1 research tested 10 OVER-side signals. The original
analysis used V1 simulation p_over as an INTERACTION GATE to filter signals.
V1 probabilities were subsequently found to be CONTAMINATED (look-ahead bias
in the feature_table used for V1 training).

This retest removes the V1 gate entirely and tests each signal as a pure
standalone using only PIT-safe boxscore features and market data.

## Test Design

- **Discovery (2022-2023):** Signal direction vs actual total (no closing lines)
- **Validation (2024):** Bet grading at actual closing over prices
- **OOS (2025):** Final test at actual closing over prices
- **Success criterion:** OOS ROI > +3% at actual prices, over rate > 53%
- **All features:** PIT-safe lagged rolling windows from boxscore data
- **No V1 output used anywhere in the pipeline**

## Signals Tested

| Signal | Description |
|--------|-------------|
| OV043 | bullpen_overuse_pitches_3g |
| OV016 | high_pitch_count_fatigue |
| OV001 | bb_x_hard_hit |
| OV021 | low_k_contact_both |
| OV041 | short_starter_x_weak_bp |
| OV_FIP_BOTH | both_starters_high_era |
| OV_ERA_SPIKE | era_spike_combined |
| OV_BP_IP | bp_ip_last_2d_combined |

## Results Summary

| Verdict | Count |
|---------|-------|
| PROMOTE | 0 |
| SHADOW_MONITOR | 0 |
| KILL | 8 |

## Decision Table

| Signal | Discovery | Val Status | Val ROI | OOS Status | OOS ROI | Verdict |
|--------|-----------|------------|---------|------------|---------|---------|
| OV043 | PASS | PASS | +4.3% | FAIL | -3.6% | **KILL** |
| OV016 | DIRECTIONAL | PASS | +1.4% | FAIL | -7.1% | **KILL** |
| OV001 | PASS | MARGINAL | -4.2% | FAIL | -10.1% | **KILL** |
| OV021 | PASS | PASS | +11.0% | FAIL | -7.9% | **KILL** |
| OV041 | DIRECTIONAL | MARGINAL | -3.5% | FAIL | -3.5% | **KILL** |
| OV_FIP_BOTH | PASS | MARGINAL | -3.1% | FAIL | -6.5% | **KILL** |
| OV_ERA_SPIKE | DIRECTIONAL | MARGINAL | -0.6% | FAIL | -1.6% | **KILL** |
| OV_BP_IP | DIRECTIONAL | PASS | +2.8% | FAIL | -10.8% | **KILL** |

## Key Findings

**No signals survived the standalone retest pipeline.**

The OVER Scanner concept, once stripped of the contaminated V1 interaction
gate, does not produce independently profitable signals. The original Wave 1
results were likely artifacts of:
1. The V1 interaction gate (which selected games where the contaminated model
   already predicted OVER, creating a self-fulfilling selection bias)
2. Discovery-validation leakage (promoted on same 2024-2025 data)
3. Multiple testing across 10 signals without proper correction

## Recommendation

**CLEAN KILL the Over Scanner concept.** The standalone signals do not
carry independent edge. Do not invest further research time.

If OVER-side signals are desired in the future, they should be built from
scratch using a different conceptual framework (e.g., game-state dynamics,
in-play events, or market microstructure) rather than pregame pitcher/bullpen
features which the market already prices efficiently.
