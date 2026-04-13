# MLB Totals Context Engine V1 - Executive Summary
## MLB Totals Context Engine V1

### Engine Classification: FOUNDATION READY WITH WARNINGS

---

### What Was Built

A structural decomposition engine that takes a single MLB game and produces 8 labeled outputs describing the structural run environment. All features are point-in-time safe. All formulas are frozen on 2022-2023 discovery data. No betting edge is computed.

**Source files:** pitcher_game_logs, hitter_game_logs, game_table, bullpen_features, historical closing lines
**Games processed:** 9,715 (2022-2025)
**Forbidden files used:** 0
**PIT contamination incidents:** 0

---

### Output Scorecard

| Output | Disc Corr | Val Mono | OOS Mono | Classification |
|--------|-----------|----------|----------|----------------|
| BRE - Baseline Run Environment | r=0.098 | PASS | PASS | **CORE KEEP** |
| ESP - Early Scoring Pressure | r=0.091 (F5) | PASS | PASS | **CORE KEEP** |
| LSP - Late Scoring Pressure | r=0.049 | PASS | PASS | **USEFUL BUT SECONDARY** |
| SS - Starter Stability | r=0.215 (IP) | PASS | PASS | **CORE KEEP** |
| BS - Bullpen Stability | r=-0.049 | PASS | PASS | **CORE KEEP** |
| WPL - Weather/Park Lift | r=0.154 | PASS | PASS | **CORE KEEP** |
| TCV - Compression/Volatility | weak | PASS | BORDERLINE | **USEFUL BUT SECONDARY** |
| MPS - Market Path Shape | N/A | N/A | N/A | **DATA-BLOCKED** |

---

### Key Findings

**Strongest outputs:**
1. SS (Starter Stability): corr=0.215 with combined actual IP, consistent across all 3 splits. BOTH_STABLE_FLAG shows 8.50 vs 8.98 mean totals in discovery, 8.41 vs 8.98 in OOS.
2. WPL (Weather/Park Lift): corr=0.154 with actual total. LIFTED games average 9.32 vs SUPPRESSED 8.54 in OOS.
3. BRE (Baseline Run Environment): corr=0.098. Structural park+offense+umpire composite stable across splits.
4. BS (Bullpen Stability): UNSTABLE bullpens show higher late-inning runs in all 3 splits (4.13 vs 3.83 in OOS).

**Warnings:**
- ESP vs LSP correlation = 0.724 (above 0.70 threshold). They share input components. LSP classified as USEFUL BUT SECONDARY.
- TCV volatility spread is small (< 0.2 std across buckets). Compression/volatility state is measurable but effect size is modest.
- MPS is completely data-blocked. Opening lines were never available in historical data. This output can only be activated with future live collection.

---

### P1B Case Study Result (OOS 2025)
- BOTH_STABLE games: 376 games, mean total 8.41
- OOS baseline: 8.90
- Structural suppression: 0.48 runs
- Within P1B + WPL=LIFTED: partial offset observed (context engine adds regime awareness)

---

### Retestability
**FULLY RETESTABLE.** All formulas documented. All source files available. No black-box components. No external API calls during rebuild.

---

### Verdict Sentence

The MLB Totals Context Engine V1 is foundation-ready: 5 of 7 active outputs (BRE, ESP, SS, BS, WPL) show consistent directional behavior across discovery, validation, and OOS splits, with 0 PIT contamination incidents and full retestability from raw source files, making it a durable structural scaffold for downstream niche objects.

---

Built: 2026-04-12 | Engine Version: V1
