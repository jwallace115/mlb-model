# MLB Archetype Engine V1-Lite — Clean Rerun on Accepted Matchup Base
**Build Date:** 2026-04-15  
**Status:** COMPLETE — NO-GO

---

## 1. Purpose

This document records a clean rerun of the MLB Archetype Engine V1-Lite using the accepted
mlb_matchup_table_base as the sole input source (replacing the original hitter_game_logs +
pitcher_game_logs direct build). The purpose is to test whether the V1-lite matchup-archetype
interaction concept holds when applied through the validated matchup base, and to determine
whether the original NO-GO verdict changes with the home-side coverage asymmetry resolved.

---

## 2. Same-Concept Identity Assessment

**Original V1-lite dimensions (3 lineup + 2 SP):**
- PATIENCE: Rolling 15-game BB/PA
- DAMAGE: Rolling 15-game ISO
- CONCENTRATION: Rolling 15-game mean Gini(slot_hits)  <-- NOT AVAILABLE in matchup base
- BAT-MISS: Rolling 5-start K/BF
- COMMAND: Rolling 5-start BB/BF

**Matchup base available fields:**
- PATIENCE: `plate_bb_rate_last_15`  -- PRESENT, exact same concept
- DAMAGE: `damage_iso_last_15`  -- PRESENT, exact same concept
- CONCENTRATION: no Gini-of-slot-hits field  -- DROPPED
- BAT-MISS: `opp_sp_batmiss_k_rate_last_5`  -- PRESENT, exact same concept
- COMMAND: `opp_sp_command_bb_rate_last_5`  -- PRESENT, exact same concept

**Same-Object Verdict:** SAME CONCEPT, MEDIATED THROUGH MATCHUP BASE. Concentration dimension
is lost (3-dim lineup reduced to 2-dim), but the core 2-lineup x 2-SP interaction structure
is preserved and the 4 key fields are exact column-level matches to the original spec.

**PIT-Safety:** No new data sourced. Matchup base was pre-accepted. No 2026 data used.
Tercile cuts derived exclusively from 2022-2023 discovery split.

---

## 3. Frozen Object Definition

| Item | Value |
|------|-------|
| Source | `mlb_matchup_table_base.parquet` |
| Seasons in scope | 2022, 2023, 2024, 2025 (2026 excluded) |
| Lineup Dim 1 | `plate_bb_rate_last_15` (PATIENCE) |
| Lineup Dim 2 | `damage_iso_last_15` (DAMAGE) |
| SP Dim 1 | `opp_sp_batmiss_k_rate_last_5` (BAT-MISS) |
| SP Dim 2 | `opp_sp_command_bb_rate_last_5` (COMMAND) |
| Window | 15-game lineup, 5-start SP (frozen from original spec) |
| Tercile source | 2022-2023 only |
| Missing-data policy | Drop rows missing any of 4 predictors OR team_runs outcome |
| Outcome label | team_runs -- home_score for H rows, away_score for A rows (from game_table) |
| Control | Main-effect additive baseline (lineup_arch + sp_profile main effects) |

**Row counts:**
- Full matchup base: 19,804 rows (all seasons)
- After excluding 2026: 19,430
- After missing-data drop: 15,578 (dropped 3,852 -- 19.8%)
- By season: 2022=3,926 | 2023=3,867 | 2024=3,881 | 2025=3,904
- Discovery (2022-2023): 7,793 rows

**Home/Away symmetry:** 9,902 H / 9,902 A in full base -- symmetric, no asymmetry bias.
This resolves the critical structural flaw from the original V1-lite (26.7% home coverage).

---

## 4. Tercile Cuts (Frozen from Discovery)

| Dimension | Low Cut | High Cut |
|-----------|---------|----------|
| PATIENCE (plate_bb_rate_last_15) | 0.07347 | 0.08800 |
| DAMAGE (damage_iso_last_15) | 0.14114 | 0.16803 |
| BAT-MISS (opp_sp_k_rate_last_5) | 0.19005 | 0.24194 |
| COMMAND (opp_sp_bb_rate_last_5) | 0.06184 | 0.08859 |

Comparison to original V1-lite cuts:
- PATIENCE: orig 0.07576/0.09043 -> rerun 0.07347/0.08800 (similar range)
- DAMAGE: orig 0.14315/0.17030 -> rerun 0.14114/0.16803 (similar range)
- SP K%: orig 0.18966/0.24194 -> rerun 0.19005/0.24194 (essentially identical)
- SP BB%: orig 0.06061/0.08661 -> rerun 0.06184/0.08859 (essentially identical)

---

## 5. Archetype Distribution

**Lineup archetypes (all seasons, post-filter):**

| Archetype | Count |
|-----------|-------|
| MIXED | 8,838 |
| IMPATIENT_WEAK | 2,121 |
| PATIENT_DAMAGE | 2,064 |
| PATIENT_CONTACT | 1,288 |
| IMPATIENT_POWER | 1,267 |

**SP profiles (all seasons, post-filter):**

| Profile | Count |
|---------|-------|
| AVERAGE | 8,521 |
| VULNERABLE | 2,021 |
| ELITE | 1,989 |
| CONTACT | 1,524 |
| WILD_POWER | 1,523 |

---

## 6. Stage Results

### Grand Mean (discovery period): 4.435 runs/team/game

### Stage 1: DISCOVERY (2022-2023) -- PASS

**Criterion:** max |interaction residual| >= 0.50 runs
**Result:** max |residual| = 0.7191 -- **PASS**

All interaction cells (sorted by residual):

| Lineup | SP Profile | n | Runs | Expected | Residual |
|--------|-----------|---|------|----------|----------|
| IMPATIENT_POWER | WILD_POWER | 61 | 4.721 | 4.002 | +0.719 |
| IMPATIENT_WEAK | VULNERABLE | 135 | 5.170 | 4.510 | +0.661 |
| PATIENT_CONTACT | WILD_POWER | 59 | 4.390 | 4.080 | +0.310 |
| IMPATIENT_WEAK | ELITE | 162 | 3.846 | 3.548 | +0.298 |
| IMPATIENT_POWER | ELITE | 62 | 3.984 | 3.744 | +0.240 |
| PATIENT_DAMAGE | AVERAGE | 686 | 5.038 | 4.890 | +0.148 |
| PATIENT_CONTACT | ELITE | 72 | 3.958 | 3.822 | +0.137 |
| MIXED | CONTACT | 424 | 4.764 | 4.699 | +0.066 |
| IMPATIENT_WEAK | CONTACT | 102 | 4.333 | 4.269 | +0.064 |
| PATIENT_CONTACT | AVERAGE | 322 | 4.332 | 4.296 | +0.036 |
| MIXED | AVERAGE | 2302 | 4.453 | 4.451 | +0.002 |
| MIXED | WILD_POWER | 399 | 4.226 | 4.235 | -0.010 |
| MIXED | VULNERABLE | 579 | 4.924 | 4.939 | -0.015 |
| MIXED | ELITE | 564 | 3.943 | 3.977 | -0.034 |
| IMPATIENT_POWER | AVERAGE | 349 | 4.163 | 4.218 | -0.055 |
| PATIENT_CONTACT | CONTACT | 55 | 4.455 | 4.543 | -0.089 |
| IMPATIENT_WEAK | AVERAGE | 640 | 3.869 | 4.022 | -0.153 |
| PATIENT_DAMAGE | VULNERABLE | 150 | 5.220 | 5.378 | -0.158 |
| PATIENT_DAMAGE | CONTACT | 133 | 4.955 | 5.137 | -0.182 |
| PATIENT_DAMAGE | WILD_POWER | 105 | 4.419 | 4.674 | -0.255 |
| IMPATIENT_POWER | VULNERABLE | 75 | 4.400 | 4.706 | -0.306 |
| PATIENT_DAMAGE | ELITE | 129 | 4.109 | 4.415 | -0.307 |
| IMPATIENT_WEAK | WILD_POWER | 97 | 3.495 | 3.806 | -0.311 |
| IMPATIENT_POWER | CONTACT | 50 | 4.100 | 4.465 | -0.366 |
| PATIENT_CONTACT | VULNERABLE | 81 | 4.333 | 4.784 | -0.451 |

### Stage 2: VALIDATION (2024) -- FAIL

**Criterion:** directional consistency >= 60%
**Result:** 14/25 cells agree in sign (56.0%) -- **FAIL**

Cell-level detail (sorted by discovery residual):

| Lineup | SP Profile | Disc Resid | Val Resid | Direction |
|--------|-----------|-----------|----------|-----------|
| IMPATIENT_POWER | WILD_POWER | +0.719 | +0.137 | AGREE |
| IMPATIENT_WEAK | VULNERABLE | +0.660 | -0.682 | FLIP |
| PATIENT_CONTACT | WILD_POWER | +0.310 | -1.080 | FLIP |
| IMPATIENT_WEAK | ELITE | +0.298 | -0.117 | FLIP |
| IMPATIENT_POWER | ELITE | +0.240 | +0.151 | AGREE |
| PATIENT_DAMAGE | AVERAGE | +0.148 | +0.134 | AGREE |
| PATIENT_CONTACT | ELITE | +0.137 | +0.073 | AGREE |
| MIXED | CONTACT | +0.066 | +0.094 | AGREE |
| IMPATIENT_WEAK | CONTACT | +0.064 | +0.076 | AGREE |
| PATIENT_CONTACT | AVERAGE | +0.036 | -0.030 | FLIP |
| MIXED | AVERAGE | +0.002 | -0.113 | FLIP |
| MIXED | WILD_POWER | -0.010 | -0.524 | AGREE |
| MIXED | VULNERABLE | -0.015 | +0.172 | FLIP |
| MIXED | ELITE | -0.034 | -0.023 | AGREE |
| IMPATIENT_POWER | AVERAGE | -0.055 | +0.212 | FLIP |
| PATIENT_CONTACT | CONTACT | -0.089 | -0.395 | AGREE |
| IMPATIENT_WEAK | AVERAGE | -0.153 | +0.037 | FLIP |
| PATIENT_DAMAGE | VULNERABLE | -0.158 | -0.203 | AGREE |
| PATIENT_DAMAGE | CONTACT | -0.182 | -0.561 | AGREE |
| PATIENT_DAMAGE | WILD_POWER | -0.255 | -0.042 | AGREE |
| IMPATIENT_POWER | VULNERABLE | -0.306 | +0.464 | FLIP |
| PATIENT_DAMAGE | ELITE | -0.307 | -0.665 | AGREE |
| IMPATIENT_WEAK | WILD_POWER | -0.311 | +0.672 | FLIP |
| IMPATIENT_POWER | CONTACT | -0.365 | +0.535 | FLIP |
| PATIENT_CONTACT | VULNERABLE | -0.451 | -0.963 | AGREE |

### Stage 3: OOS (2025) -- FAIL

**Criterion:** directional consistency >= 50% (above chance)
**Result:** 12/25 cells agree in sign (48.0%) -- **FAIL** (below chance)

Cell-level detail (sorted by discovery residual):

| Lineup | SP Profile | Disc Resid | OOS Resid | Direction |
|--------|-----------|-----------|----------|-----------|
| IMPATIENT_POWER | WILD_POWER | +0.719 | +0.212 | AGREE |
| IMPATIENT_WEAK | VULNERABLE | +0.660 | -0.227 | FLIP |
| PATIENT_CONTACT | WILD_POWER | +0.310 | -0.516 | FLIP |
| IMPATIENT_WEAK | ELITE | +0.298 | +0.309 | AGREE |
| IMPATIENT_POWER | ELITE | +0.240 | +0.523 | AGREE |
| PATIENT_DAMAGE | AVERAGE | +0.148 | +0.155 | AGREE |
| PATIENT_CONTACT | ELITE | +0.137 | -1.061 | FLIP |
| MIXED | CONTACT | +0.066 | -0.225 | FLIP |
| IMPATIENT_WEAK | CONTACT | +0.064 | -0.182 | FLIP |
| PATIENT_CONTACT | AVERAGE | +0.036 | -0.006 | FLIP |
| MIXED | AVERAGE | +0.002 | +0.048 | AGREE |
| MIXED | WILD_POWER | -0.010 | -0.204 | AGREE |
| MIXED | VULNERABLE | -0.015 | -0.195 | AGREE |
| MIXED | ELITE | -0.034 | -0.057 | AGREE |
| IMPATIENT_POWER | AVERAGE | -0.055 | +0.658 | FLIP |
| PATIENT_CONTACT | CONTACT | -0.089 | -0.930 | AGREE |
| IMPATIENT_WEAK | AVERAGE | -0.153 | +0.283 | FLIP |
| PATIENT_DAMAGE | VULNERABLE | -0.158 | -0.740 | AGREE |
| PATIENT_DAMAGE | CONTACT | -0.182 | +0.641 | FLIP |
| PATIENT_DAMAGE | WILD_POWER | -0.255 | -0.325 | AGREE |
| IMPATIENT_POWER | VULNERABLE | -0.306 | +1.268 | FLIP |
| PATIENT_DAMAGE | ELITE | -0.307 | +0.085 | FLIP |
| IMPATIENT_WEAK | WILD_POWER | -0.311 | +0.449 | FLIP |
| IMPATIENT_POWER | CONTACT | -0.365 | +0.068 | FLIP |
| PATIENT_CONTACT | VULNERABLE | -0.451 | -0.617 | AGREE |

---

## 7. Comparison to Original V1-Lite

| Item | Original V1-Lite | This Rerun |
|------|-----------------|------------|
| Source | hitter/pitcher_game_logs direct | mlb_matchup_table_base |
| Home coverage | 26.7% (severe asymmetry) | 50% (symmetric) |
| Concentration dim | Present (Gini slot-hits) | DROPPED |
| Discovery max|resid| | 0.804 | 0.719 |
| Validation consistency | 40.0% (FAIL) | 56.0% (FAIL) |
| OOS consistency | not run | 48.0% (FAIL) |
| Final verdict | NO-GO | NO-GO |

**Key finding:** Fixing the home-side coverage asymmetry improved validation consistency from
40% to 56%, confirming the original failure was partly an artifact of unrepresentative
discovery data. However, 56% still fails the 60% threshold, and OOS falls to 48% (below
chance). The core NO-GO conclusion is confirmed and is now stronger: even with clean symmetric
data, the 2-dim lineup x 2-dim SP interaction signal does not persist across seasons.

The concentration dimension (Gini slot-hits) is absent in this rerun. Whether its inclusion
would improve results is unknown, but the 4-dimensional original model also failed validation
at 40%, so there is no affirmative basis to expect the 3-dim version to behave differently.

---

## 8. Final Verdict

**NO-GO**

Discovery signal exists (max residual 0.719 runs above additive expectation) but does not
persist into validation or OOS. Validation directional consistency 56.0% (threshold 60%).
OOS directional consistency 48.0% (below-chance, threshold 50%). No deployment path justified.
9 of 25 cells show direction stability across all three stages -- insufficient to support a
sub-set strategy without additional confirmatory evidence.
