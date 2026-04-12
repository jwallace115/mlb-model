# MLB Moneyline Watchlist Forensic Memo
## Date: 2026-04-11

## Purpose
Deep forensic audit of the 8 WATCH-listed strategies from Phase 2 Deep.
Diagnosis only -- no retuning, no optimization, no new signal search.

## Watch Item Definitions (Locked)

### W1_fav_sp_decline_dog_sp_improve: Fav SP declining + Dog SP improving
- **Side:** Bet on dog
- **Definition:** `fav_sp_era_div < 0 AND dog_sp_era_div > 0`
- **Total games:** 654

### W2_dog_sp_materially_improving: Dog SP materially improving (div>0.5)
- **Side:** Bet on dog
- **Definition:** `dog_sp_era_div > 0.5`
- **Total games:** 971

### W3_bp_workload_mismatch: BP workload mismatch favors dog
- **Side:** Bet on dog
- **Definition:** `bp_workload_mismatch > 0 (fav_bp_workload_3d > dog_bp_workload_3d)`
- **Total games:** 1514

### W4_dog_better_rd5: Dog better recent form (RD5)
- **Side:** Bet on dog
- **Definition:** `rd5_mismatch > 0 (dog_rd_5 > fav_rd_5)`
- **Total games:** 2805

### W5_INT1_sp_rd5_mismatch: INT1: SP+RD5 mismatch (dog)
- **Side:** Bet on dog
- **Definition:** `sp_era_mismatch > 0 AND rd5_mismatch > 0`
- **Total games:** 618

### W6_INT2_sp_bp_mismatch: INT2: SP+BP mismatch (dog)
- **Side:** Bet on dog
- **Definition:** `sp_era_mismatch > 0 AND bp_workload_mismatch > 0`
- **Total games:** 521

### W7_INT4_triple_mismatch: INT4: Triple mismatch SP+BP+RD5 (dog)
- **Side:** Bet on dog
- **Definition:** `sp_era_mismatch > 0 AND bp_workload_mismatch > 0 AND rd5_mismatch > 0`
- **Total games:** 254

### W8_INT5_fav_confirming: INT5: Fav SP improving + hot streak (fav)
- **Side:** Bet on fav
- **Definition:** `fav_sp_era_div > 0.5 AND fav_rd_5 > 1.0`
- **Total games:** 538

## Discovery Sample Reconstruction

| Watch ID | Label | Side | Disc N | Disc WR | Disc Impl | Disc Resid | Disc ROI |
|----------|-------|------|--------|---------|-----------|------------|----------|
| W1_fav_sp_decline_dog_sp_improve | Fav SP declining + Dog SP improving | dog | 346 | 0.4277 | 0.4680 | -0.0403 | -12.7% |
| W2_dog_sp_materially_improving | Dog SP materially improving (div>0.5) | dog | 503 | 0.4414 | 0.4685 | -0.0272 | -10.0% |
| W3_bp_workload_mismatch | BP workload mismatch favors dog | dog | 775 | 0.4645 | 0.4664 | -0.0019 | -4.7% |
| W4_dog_better_rd5 | Dog better recent form (RD5) | dog | 1402 | 0.4686 | 0.4673 | +0.0013 | -4.0% |
| W5_INT1_sp_rd5_mismatch | INT1: SP+RD5 mismatch (dog) | dog | 326 | 0.4141 | 0.4684 | -0.0543 | -15.3% |
| W6_INT2_sp_bp_mismatch | INT2: SP+BP mismatch (dog) | dog | 256 | 0.4219 | 0.4680 | -0.0461 | -13.9% |
| W7_INT4_triple_mismatch | INT4: Triple mismatch SP+BP+RD5 (dog) | dog | 124 | 0.4113 | 0.4675 | -0.0562 | -15.7% |
| W8_INT5_fav_confirming | INT5: Fav SP improving + hot streak (fav) | fav | 272 | 0.5662 | 0.5325 | +0.0336 | +1.7% |

**Critical finding:** 6/8 watch items had NEGATIVE discovery residuals.
Only 2/8 had non-negative discovery residuals: Dog better recent form (RD5), INT5: Fav SP improving + hot streak (fav)

These items reached WATCH status because val+OOS were positive despite negative disc.
This is a **reversed temporal pattern** (disc- / val+ / OOS+), which could indicate:
1. Market regime change (market got less efficient at pricing these features post-2023)
2. Survivor bias in the keep/kill algorithm (items that happened to recover got WATCH)
3. Genuine delayed structural edge (features became more predictive as league evolved)

## Failure Diagnosis Summary

| Watch ID | Label | Primary Diagnosis |
|----------|-------|-------------------|
| W1_fav_sp_decline_dog_sp_improve | Fav SP declining + Dog SP improving | WIN_RATE_SHORTFALL_DISC |
| W2_dog_sp_materially_improving | Dog SP materially improving (div>0.5) | WIN_RATE_SHORTFALL_DISC; DISC_NEGATIVE_RECOVERING |
| W3_bp_workload_mismatch | BP workload mismatch favors dog | PRICE_SHAPE |
| W4_dog_better_rd5 | Dog better recent form (RD5) | PRICE_SHAPE |
| W5_INT1_sp_rd5_mismatch | INT1: SP+RD5 mismatch (dog) | WIN_RATE_SHORTFALL_DISC; DISC_NEGATIVE_RECOVERING |
| W6_INT2_sp_bp_mismatch | INT2: SP+BP mismatch (dog) | WIN_RATE_SHORTFALL_DISC |
| W7_INT4_triple_mismatch | INT4: Triple mismatch SP+BP+RD5 (dog) | WIN_RATE_SHORTFALL_DISC; DISC_NEGATIVE_RECOVERING |
| W8_INT5_fav_confirming | INT5: Fav SP improving + hot streak (fav) | AMBIGUOUS |

## Year-by-Year Discovery Map

Key pattern across watch items:

- **2023 was the drag season for 4/8 watch items.** Most dog-side strategies 
  had sharply negative residuals in 2023, while 2022 was neutral-to-slightly-negative.

| Watch ID | 2022 Resid | 2023 Resid | 2024 Resid | 2025 Resid | Pattern |
|----------|------------|------------|------------|------------|---------|
| W1_fav_sp_decline_dog_sp_improve | +0.0117 | -0.0683 | +0.0404 | +0.0047 | +-++ |
| W2_dog_sp_materially_improving | -0.0223 | -0.0299 | +0.0340 | +0.0504 | --++ |
| W3_bp_workload_mismatch | -0.0082 | +0.0011 | +0.0210 | +0.0219 | -+++ |
| W4_dog_better_rd5 | -0.0194 | +0.0140 | -0.0130 | +0.0411 | -+-+ |
| W5_INT1_sp_rd5_mismatch | -0.0072 | -0.0770 | +0.0210 | +0.0417 | --++ |
| W6_INT2_sp_bp_mismatch | +0.0069 | -0.0711 | +0.0178 | +0.0038 | +-++ |
| W7_INT4_triple_mismatch | -0.0198 | -0.0723 | +0.0429 | +0.0142 | --++ |
| W8_INT5_fav_confirming | +0.1239 | -0.0164 | +0.0065 | -0.0948 | +-+- |

## Split Contrast Table

| Watch ID | Label | Disc Resid | Val Resid | OOS Resid | Direction |
|----------|-------|------------|-----------|-----------|-----------|
| W1_fav_sp_decline_dog_sp_improve | Fav SP declining + Dog SP improving | -0.0403 | +0.0404 | +0.0047 | -++ |
| W2_dog_sp_materially_improving | Dog SP materially improving (div>0.5) | -0.0272 | +0.0340 | +0.0504 | -++ |
| W3_bp_workload_mismatch | BP workload mismatch favors dog | -0.0019 | +0.0210 | +0.0219 | -++ |
| W4_dog_better_rd5 | Dog better recent form (RD5) | +0.0013 | -0.0130 | +0.0411 | +-+ |
| W5_INT1_sp_rd5_mismatch | INT1: SP+RD5 mismatch (dog) | -0.0543 | +0.0210 | +0.0417 | -++ |
| W6_INT2_sp_bp_mismatch | INT2: SP+BP mismatch (dog) | -0.0461 | +0.0178 | +0.0038 | -++ |
| W7_INT4_triple_mismatch | INT4: Triple mismatch SP+BP+RD5 (dog) | -0.0562 | +0.0429 | +0.0142 | -++ |
| W8_INT5_fav_confirming | INT5: Fav SP improving + hot streak (fav) | +0.0336 | +0.0065 | -0.0948 | ++- |

## Coarseness Observations (No Fix Proposed)

1. **W3 (BP workload mismatch):** N=775 in disc, the broadest filter. Residual near zero (-0.002) suggests the definition captures too much noise.
2. **W4 (Dog better RD5):** N=1402 in disc, even broader. Near-zero disc residual (+0.001) is definitionally coarse.
3. **W1, W5, W6, W7:** Interaction/conjunction filters produce narrower samples (124-346 in disc) but all had negative disc residuals, suggesting the conjunction does not reliably identify mispricing.
4. **W8 (fav confirming):** Only fav-side item. Disc was positive (+0.034) but OOS collapsed to -0.095. This is the classic overfit signature.

## Structural Conclusions

### 1. The -/+/+ temporal pattern is suspicious
6/8 watch items show negative discovery residuals recovering in val/OOS. This is backwards from the typical edge-discovery pattern (+/+/+ or +/+/-). The WATCH classification was triggered by val+OOS positivity, but the discovery shortfall means we never had a robust signal to begin with.

### 2. 2023 was a systematic drag season for dog-side bets
Nearly all dog-side strategies suffered badly in 2023. This may reflect a league-wide pattern (favorites dominated in 2023 close games) rather than a flaw in the features themselves. The recovery in 2024-2025 could be mean reversion rather than signal.

### 3. No item has positive residual in all 4 seasons
Even the strongest performers (W2, W4) only have 2/4 positive seasons. This level of inconsistency is incompatible with a durable structural edge.

### 4. ROI drag exceeds residual in most cases
Even when residuals are slightly positive, ROI is often negative or marginal. The vig absorbs the thin residual, confirming that MLB closing ML prices leave no room for flat-bet profit on these features.

### 5. INT5 (fav confirming) is dead
The only fav-side WATCH item showed strong 2022 results (+12.4% residual) that never replicated. OOS residual of -9.5% is a definitive kill signal masquerading as WATCH due to the aggregation algorithm.

## Recommendation

**Downgrade all 8 WATCH items to KILL.** None meet the standard for 2026 shadow deployment:

| Watch ID | Prior Decision | Forensic Decision | Reason |
|----------|---------------|-------------------|--------|
| W1 | WATCH | KILL | Disc negative, 2023 drag, inconsistent |
| W2 | WATCH | KILL | Disc negative, only 2/4 seasons positive |
| W3 | WATCH | KILL | Definition too coarse, disc residual ~0 |
| W4 | WATCH | KILL | Definition too coarse, disc residual ~0, 2023 drag |
| W5 | WATCH | KILL | Disc negative, 2023 drag, interaction adds no lift |
| W6 | WATCH | KILL | Disc negative, OOS marginal (+0.004) |
| W7 | WATCH | KILL | Disc negative, N too thin (124), OOS marginal |
| W8 | WATCH | KILL | Classic overfit: 2022 anomaly, OOS collapse -9.5% |

**MLB closing moneylines remain fully efficient against PIT-safe pitcher/team features.**
The Phase 2 Deep WATCH list contained no actionable signals -- only statistical noise 
and temporal mean reversion patterns that the keep/kill algorithm misclassified as potential edges.