# MLB Sides Phase 4 — Reason-for-Favoritism / Win-Path Decomposition
## Executive Summary
**Date:** 2026-04-12

## VERDICT: 1 CONDITIONAL KEEP, 4 KILLS

The win-path decomposition reveals one structurally persistent pattern but it is economically marginal. The SP-LED favorite advantage (+8.9% discovery residual) collapses completely OOS. Most favoritism classes show the close-game favorite underperforming implied probability across all periods.

---

## Universe

Close ML games (fav implied .512-.556), 2022-2025, requiring all features (SP FIP, offense R/G, BP ERA, closing total).

| Period | N |
|--------|---|
| Discovery (22-23) | 924 |
| Validation (24) | 563 |
| OOS (25) | 591 |
| **Total** | **2,078** |

## Frozen Thresholds (discovery only)

| Threshold | Value | Description |
|-----------|-------|-------------|
| sp_material | 1.200 | p67 of \|SP FIP diff\| |
| sp_small | 0.814 | p50 of \|SP FIP diff\| |
| off_material | 1.150 | p67 of \|offense diff\| |
| off_small | 0.800 | p50 of \|offense diff\| |
| bp_material | 0.849 | p67 of \|BP ERA diff\| |
| bp_small | 0.583 | p50 of \|BP ERA diff\| |
| total_low | 8.000 | p33 of closing total |
| total_high | 9.000 | p67 of closing total |

## Classification Distributions

### Reason for Favoritism
| Class | Disc | Val | OOS | Rule |
|-------|------|-----|-----|------|
| SP-LED | 166 | 96 | 109 | Fav SP FIP gap >= 1.20, dominant gap |
| OFFENSE-LED | 100 | 50 | 50 | Fav offense gap >= 1.15, SP gap small |
| BP-LED | 55 | 35 | 29 | Fav BP ERA gap >= 0.85, SP+off small |
| HOME-LED | 63 | 49 | 45 | Fav is home, all gaps small |
| MIXED | 540 | 333 | 358 | No single dominant driver |

### Win-Path Profile
| Class | Disc | Val | OOS | Rule |
|-------|------|-----|-----|------|
| STARTER-HOLD | 162 | 92 | 89 | Fav SP FIP bottom tercile + adequate BP |
| LATE-CONVERT | 248 | 127 | 165 | Fav SP weak, offense or BP strong |
| GRIND-OUT | 105 | 102 | 76 | Low total, thin margins |
| VOLATILE | 77 | 34 | 59 | High total, offense-driven |
| UNCLASSIFIED | 332 | 208 | 202 | No clean pattern |

## Part A: Reason for Favoritism Results

| Class | Phase | N | WR | ImpWR | Resid | ROI_fav | ROI_dog |
|-------|-------|---|----|----|-------|---------|---------|
| SP-LED | Discovery | 166 | .6265 | .5371 | +.0894 | +11.80% | -22.75% |
| SP-LED | Validation | 96 | .4792 | .5390 | -.0598 | -14.65% | +8.47% |
| SP-LED | OOS | 109 | .5138 | .5366 | -.0228 | -8.85% | -0.25% |
| MIXED | Discovery | 540 | .5111 | .5361 | -.0250 | -8.56% | +1.09% |
| MIXED | Validation | 333 | .5195 | .5359 | -.0163 | -7.17% | -0.90% |
| MIXED | OOS | 358 | .4972 | .5339 | -.0367 | -11.05% | +3.07% |
| HOME-LED | Discovery | 63 | .6032 | .5364 | +.0668 | +7.75% | -18.08% |
| HOME-LED | OOS | 45 | .4444 | .5355 | -.0911 | -21.37% | +13.36% |

## Part B: Win-Path Results

| Class | Phase | N | Resid | ROI_fav | ROI_dog |
|-------|-------|---|-------|---------|---------|
| LATE-CONVERT | Discovery | 248 | -.0244 | -8.44% | +0.97% |
| LATE-CONVERT | Validation | 127 | +.0306 | +1.18% | -10.73% |
| LATE-CONVERT | OOS | 165 | -.0608 | -15.32% | +8.01% |
| UNCLASSIFIED | Discovery | 332 | +.0392 | +2.97% | -12.11% |
| UNCLASSIFIED | Validation | 208 | -.0073 | -5.54% | -2.70% |
| UNCLASSIFIED | OOS | 202 | -.0443 | -12.60% | +4.33% |

## Cross-Tab Highlights

| Cross-Cell | Disc N | Disc Resid | Val Resid | OOS Resid |
|------------|--------|-----------|-----------|-----------|
| SP-LED+UNCLASSIFIED | 93 | +.1074 | -.1043 | -.0560 |
| MIXED+LATE-CONVERT | 162 | -.0429 | +.0195 | -.0022 |
| MIXED+GRIND-OUT | 72 | -.0365 | -.0665 | -.0799 |
| MIXED+VOLATILE | 53 | -.0828 | -.1137 | -.0639 |

## Survivor Board

### KEEP (conditional)

**MIXED (dog side)**: When no single baseball factor drives the favorite, the dog wins more than implied.

| Phase | N | Resid | ROI_dog |
|-------|---|-------|---------|
| Discovery | 540 | -.0250 | +1.09% |
| Validation | 333 | -.0163 | -0.90% |
| OOS | 358 | -.0367 | +3.07% |

**Assessment**: Residual is negative all 3 periods (consistent direction). Dog ROI is +3.07% OOS but -0.90% in validation. This is a **structural observation** — close-game favorites with no clear dominant edge (MIXED) underperform — but the dog-side economics are marginal. The vig eats most of the residual in validation. NOT profitable enough for standalone deployment without additional filters.

### KILLS (4)

1. **SP-LED (fav)**: Discovery residual +8.94% is spectacular but collapses to -5.98% in validation and -2.28% OOS. Classic overshoot — the market already prices the SP edge correctly or even overweights it.

2. **LATE-CONVERT (dog)**: Residual flips sign in validation (+3.06%). No consistency.

3. **UNCLASSIFIED (fav)**: Residual vanishes in validation (-0.73%) and OOS (-4.43%). Discovery artifact.

4. **MIXED+LATE-CONVERT (dog)**: Validation residual flips positive. No hold.

## Key Structural Findings

1. **SP-LED favorites are overbet**: The market's biggest pricing error in discovery (+8.9% residual for SP-LED favs) completely reverses OOS. The betting public overvalues known SP matchup advantages in close games. This is the "ace tax."

2. **MIXED-reason dogs have a persistent structural edge**: When the market prices a team as a small favorite without a clear single driver, the dog outperforms. This is consistent with "no strong reason to be favored = don't deserve to be favored." The residual is negative in all 3 periods.

3. **High-total MIXED (volatile) games strongly favor the dog**: Discovery -8.28% residual, validation -11.37%, OOS -6.39%. Small N but directionally consistent all 3 periods. The market may overprice favorites in high-variance close games.

4. **GRIND-OUT MIXED dogs also look consistent**: Discovery -3.65%, validation -6.65%, OOS -7.99%. The residual actually GROWS OOS. Sub-N=150 so treated as marginal, but worth monitoring.

## Verdict

The decomposition confirms a structural theme: **close-game favorites with diffuse/unclear advantages underperform.** The strongest version is MIXED-reason dogs, but the economics are thin (+1-3% dog ROI through vig). This is an **edge identifier** rather than a standalone betting signal — it would need to be combined with other filters (C8 command archetype, BP availability, etc.) to produce actionable ROI.

No new standalone signal clears the full KEEP + profitable gate. MIXED-dog is a conditional keep for overlay/filtering use only.

## Files
- `MLB_SIDES_PHASE4_FINAL_TABLE.csv` — all cell results by phase
- `classification_table.csv` — per-game classifications
- `survivors.csv` — survivor board
- `phase4_winpath.py` — full analysis script
