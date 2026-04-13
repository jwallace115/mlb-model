# Context Engine V1 × MPS Descriptive Taxonomy V1 — Crosswalk Spec

**Object ID:** CROSSWALK-MLBCE-V1-MPS-V1  
**Version:** 1.0  
**Date Frozen:** 2026-04-13  
**Verdict:** CROSSWALK FROZEN

---

## 1. Scope

This document defines a **descriptive crosswalk** between the frozen MLB Totals Context Engine V1 outputs and the frozen MPS Descriptive Taxonomy V1 archetypes.

**This crosswalk is:**
- A descriptive mapping of structural game states to observed market-path behavior
- Infrastructure for future research characterization and object filtering

**This crosswalk is NOT:**
- A betting signal
- An edge claim
- A predictive model
- A basis for threshold optimization

No realized game outcomes, closing errors, or wager results were used anywhere in this crosswalk.

---

## 2. Source Tables

| Source | Path | Rows |
|--------|------|------|
| Context Engine V1 Output Table | `context_engine_output_table.parquet` | 9,715 |
| MPS Taxonomy V1 Labeled Table | `mps_taxonomy_v1/mps_taxonomy_v1_labeled.parquet` | 9,715 |

**Join key:** `game_pk` (context) = `game_id` (MPS)  
**Inner join:** 9,715 rows (0 unmatched on either side)

**Comparable universe definition:**
- Exclude CROSS_BOOK and INCOMPLETE MPS archetypes: 3,475 excluded
- Require non-null values for all 5 primary context outputs (BRE, ESP, SS, BS, WPL)
- **Final comparable universe: 6,240 games**

| Season | Comparable Rows |
|--------|----------------|
| 2022 | 1,411 |
| 2023 | 1,484 |
| 2024 | 1,597 |
| 2025 | 1,748 |

---

## 3. Context Buckets

All bucket cut points were derived from the full 2022–2025 joined comparable universe (6,240 games) using terciles. These cut points are frozen and must be treated as fixed in any downstream use.

| Output | Labels | P33 Cut | P67 Cut | Bucket Sizes |
|--------|--------|---------|---------|-------------|
| BRE | LOW / MID / HIGH | 40.80 | 56.45 | 2080 / 2080 / 2080 |
| ESP | LOW / MID / HIGH | 36.45 | 48.55 | 2080 / 2080 / 2080 |
| SS | FRAGILE / MODERATE / STABLE | 45.94 | 57.38 | 2080 / 2080 / 2080 |
| BS | LOW / MID / HIGH | 39.34 | 53.68 | 2080 / 2080 / 2080 |
| WPL | LOW / MID / HIGH | 0.17 | 0.87 | 2080 / 2080 / 2080 |

**SS bucket labels** use FRAGILE / MODERATE / STABLE to match the frozen Context Engine V1 spec interpretation (higher SS = more stable starters).

---

## 4. Response Family Mapping

The 7 frozen MPS archetypes are collapsed into 5 broad response families:

| Response Family | MPS Archetypes |
|----------------|----------------|
| OVERWARD_NUMBER | NUMBER_UP_SMALL, NUMBER_UP_LARGE |
| UNDERWARD_NUMBER | NUMBER_DOWN_SMALL, NUMBER_DOWN_LARGE |
| OVERWARD_JUICE_ONLY | JUICE_ONLY_OVER |
| UNDERWARD_JUICE_ONLY | JUICE_ONLY_UNDER |
| STATIC | STATIC |

**Overall distribution in comparable universe:**

| Family | Count | Pct |
|--------|-------|-----|
| UNDERWARD_NUMBER | 1,722 | 27.6% |
| UNDERWARD_JUICE_ONLY | 1,487 | 23.8% |
| OVERWARD_JUICE_ONLY | 1,361 | 21.8% |
| OVERWARD_NUMBER | 1,245 | 20.0% |
| STATIC | 425 | 6.8% |

The board has a **persistent underward bias**: underward families (NUMBER + JUICE) total 51.4% vs overward 41.8%. This is a structural baseline, not an edge.

---

## 5. Main Crosswalk Results

### BRE (Baseline Run Environment)

| Bucket | OW_NUM | UW_NUM | OW_JUICE | UW_JUICE | STATIC | Asym_N | Asym_J |
|--------|--------|--------|----------|----------|--------|--------|--------|
| LOW | 22% | 29% | 20% | 23% | 6% | -6pp | -3pp |
| MID | 18% | 28% | 23% | 25% | 7% | -10pp | -1pp |
| HIGH | 20% | 26% | 22% | 24% | 7% | -6pp | -2pp |

**Tendency:** BRE LOW has higher number-move propensity (51%) and larger NUMBER_UP_LARGE share (6.4% vs 2.5% at HIGH). Higher BRE shifts slightly toward juice-only moves. Underward asymmetry is persistent across all buckets.

### ESP (Early Scoring Pressure)

| Bucket | OW_NUM | UW_NUM | OW_JUICE | UW_JUICE | STATIC | Asym_N | Asym_J |
|--------|--------|--------|----------|----------|--------|--------|--------|
| LOW | 19% | 29% | 20% | 26% | 6% | -10pp | -6pp |
| MID | 19% | 29% | 22% | 23% | 8% | -10pp | -1pp |
| HIGH | 22% | 25% | 24% | 22% | 7% | -3pp | +2pp |

**Tendency:** ESP shows the clearest gradient. LOW ESP has strong underward bias (asym_N = -10pp, asym_J = -6pp). HIGH ESP nearly neutralizes both asymmetries (asym_N = -3pp, asym_J = +2pp). This is the most structurally informative context output for market-response direction.

### SS (Starter Stability)

| Bucket | OW_NUM | UW_NUM | OW_JUICE | UW_JUICE | STATIC | Asym_N | Asym_J |
|--------|--------|--------|----------|----------|--------|--------|--------|
| FRAGILE | 23% | 24% | 24% | 22% | 7% | -0pp | +3pp |
| MODERATE | 21% | 27% | 21% | 23% | 7% | -6pp | -2pp |
| STABLE | 15% | 32% | 20% | 26% | 6% | -17pp | -7pp |

**Tendency:** SS is the strongest single-output differentiator. STABLE starters produce massive underward number asymmetry (-17pp) and underward juice asymmetry (-7pp). FRAGILE starters produce near-zero number asymmetry and slightly overward juice bias. The market responds to starter quality with clear directional differentiation.

### BS (Bullpen Stability)

| Bucket | OW_NUM | UW_NUM | OW_JUICE | UW_JUICE | STATIC | Asym_N | Asym_J |
|--------|--------|--------|----------|----------|--------|--------|--------|
| LOW | 19% | 28% | 22% | 24% | 7% | -9pp | -3pp |
| MID | 21% | 29% | 21% | 22% | 7% | -9pp | -1pp |
| HIGH | 20% | 25% | 22% | 25% | 7% | -5pp | -3pp |

**Tendency:** BS shows mild differentiation. HIGH BS slightly reduces underward number asymmetry (-5pp vs -9pp at LOW/MID). The effect is smaller than SS. STATIC share is flat across all buckets (~7%).

### WPL (Weather/Park Lift)

| Bucket | OW_NUM | UW_NUM | OW_JUICE | UW_JUICE | STATIC | Asym_N | Asym_J |
|--------|--------|--------|----------|----------|--------|--------|--------|
| LOW | 20% | 31% | 19% | 24% | 6% | -11pp | -5pp |
| MID | 19% | 26% | 23% | 25% | 7% | -7pp | -2pp |
| HIGH | 21% | 25% | 24% | 23% | 7% | -5pp | +1pp |

**Tendency:** WPL shows a clean gradient similar to ESP. LOW WPL (suppressed parks/weather) has the strongest underward bias (-11pp number, -5pp juice) and highest number-move propensity (52%). HIGH WPL nearly neutralizes the underward bias and shifts toward juice-only resolution. NUMBER_UP_LARGE and NUMBER_DOWN_LARGE are concentrated in LOW WPL (8% and 9% vs 2% and 3% at HIGH).

---

## 6. Interaction Snapshots

Four fixed interaction views were examined. Selection was structural (not outcome-driven):
1. **BRE × WPL** — run environment vs environmental lift
2. **SS × BS** — starter quality vs bullpen quality
3. **ESP × SS** — early pressure vs starter stability
4. **BRE × BS** — run environment vs bullpen quality

### BRE × WPL
UNDERWARD_NUMBER dominates nearly all cells (25–34%). The only exception: BRE=LOW × WPL=HIGH, where OVERWARD_JUICE_ONLY edges to 24% — suggesting that in low-baseline environments with high park/weather lift, the market responds via juice rather than number movement.

### SS × BS
UNDERWARD_NUMBER dominates all cells. The strongest concentration is SS=STABLE × BS=MID (35%). FRAGILE × HIGH is the only cell where OVERWARD_JUICE_ONLY competes (25%).

### ESP × SS
This is the most differentiated interaction. ESP=HIGH × SS=FRAGILE produces OVERWARD_NUMBER dominance (25%) — the only cell in the entire crosswalk where overward number movement leads. ESP=LOW × SS=STABLE produces the strongest UNDERWARD_NUMBER (32%).

### BRE × BS
Weakest interaction. UNDERWARD_NUMBER dominates all cells (24–31%). The only mild shift: BRE=HIGH × BS=HIGH slightly favors UNDERWARD_JUICE_ONLY (26%).

---

## 7. Static / Juice-Only Diagnostics

### STATIC share by context bucket

STATIC ranges from 6.1% to 7.5% across all context buckets — effectively flat. No context output meaningfully predicts whether the market will be static. STATIC appears to be a market-microstructure phenomenon rather than a structural-game-state phenomenon.

### Juice-only diagnostics

| Output | LOW Juice% | MID Juice% | HIGH Juice% | Gradient? |
|--------|-----------|-----------|------------|-----------|
| BRE | 42.8% | 47.6% | 46.4% | Mild — LOW has less juice-only |
| ESP | 46.1% | 45.2% | 45.7% | Flat |
| SS | 46.0% (FRAGILE) | 44.8% (MOD) | 46.2% (STABLE) | Flat |
| BS | 46.0% | 43.1% | 47.7% | Mild — HIGH BS = more juice |
| WPL | 42.1% | 47.9% | 46.9% | WPL LOW = more number moves |

**Key finding:** WPL LOW is the context state with the highest number-move propensity (51.8%) and lowest juice-only share (42.1%). Suppressed-environment games are where the market is most likely to move the number rather than adjust juice.

### WPL × Month — STATIC share

March and October have elevated STATIC rates (10–16%) but very small sample sizes (n < 60 per cell). These are fringe-month artifacts. April through September STATIC rates are stable at 4.4–9.4% with no month contributing > 40% of any WPL bucket's STATIC count.

---

## 8. Sanity Notes

- **No single-season artifacts detected.** All 5 primary outputs show UNDERWARD_NUMBER as dominant family across all 4 seasons in most buckets. The only season-level variation is in secondary-family rankings (which family comes 2nd), not primary dominance.
- **SS=FRAGILE is the noisiest bucket.** Dominant family alternates between OVERWARD_NUMBER (2022, 2023), UNDERWARD_NUMBER (2024), and OVERWARD_JUICE_ONLY (2025). This is expected — fragile starters create the most uncertain pregame state.
- **No month concentration > 40%** for any highlighted pattern.
- **October cells are too thin** (n < 50) for any interpretation — they are preserved but should not be cited.
- **All bucket sizes are exactly 2,080** (perfect tercile split), confirming no labeling errors.

---

## 9. Identity Lock

Any change to the following creates **Context × MPS Crosswalk V2**:

- Source context table or MPS taxonomy table
- Comparable universe definition (exclusion rules, null handling)
- Context bucket cut points or labels
- Response family mapping rules
- Interaction selection (which pairs, how many)
- Discovery/calibration data window

The current crosswalk is frozen on the full 2022–2025 joined comparable universe. Re-derivation on a subset creates a new version.

---

## 10. Explicit Status Statement

MPS remains RESERVED / DATA-BLOCKED. This crosswalk is a descriptive mapping between frozen context outputs and frozen market-path archetypes only. No signals have been tested, no predictive value has been claimed, and no changes to the canonical spec have been made.
