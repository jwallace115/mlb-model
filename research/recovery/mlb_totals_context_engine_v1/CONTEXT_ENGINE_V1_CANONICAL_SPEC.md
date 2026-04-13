# MLB Totals Context Engine V1 — Canonical Frozen Spec
## Object Identity

| Field | Value |
|-------|-------|
| **Object Name** | MLB Totals Context Engine V1 |
| **Object ID** | MLBCE-V1 |
| **Version** | 1.0 |
| **Date Frozen** | 2026-04-12 |
| **Classification** | Foundation / Decomposition Engine |
| **Status** | CANONICAL — NO FURTHER CHANGES PERMITTED |

---

## 1. Object Identity

- **Full Name:** MLB Totals Context Engine V1
- **Short ID:** MLBCE-V1
- **Version:** 1.0
- **Date Frozen:** 2026-04-12
- **Author / Freeze Authority:** Research pipeline, frozen via Canonical Object Spec Freeze
- **Engine Type:** Structural decomposition engine (descriptive, not predictive)
- **Non-betting confirmation:** This engine produces no edge output, no probability estimate, and no betting recommendation.

---

## 2. Scope and Non-Scope

### In Scope
- Structural decomposition of MLB game run environment into 8 labeled outputs
- Coverage: 9,715 games, seasons 2022–2025
- Downstream use: characterizing structural regime for niche objects (P1B, F5 pressure, dead totals)
- Retestability: engine is fully reconstructible from documented source files and frozen formulas

### Out of Scope
- Any form of betting signal generation or edge calculation
- ROI backtest or optimization
- Adaptive recalibration of formula weights or thresholds
- Use of season-level aggregate features (PIT-contaminated sources permanently excluded)
- Market Path Shape computation (MPS is DATA-BLOCKED — no open-line data available)
- 2026 data (excluded from all formula derivation and validation)

---

## 3. Source Lineage and Exclusions

### Approved Source Files

| Source File | Family | PIT-Safe | Coverage |
|-------------|--------|----------|----------|
| `mlb/data/pitcher_game_logs.parquet` | Starter Quality, Starter Depth, Bullpen Freshness | YES — shift(1) + rolling | 100% |
| `mlb/data/hitter_game_logs.parquet` | Offense Quality | YES — shift(1) + rolling 10-game | 100% |
| `sim/data/bullpen_features.parquet` | Bullpen Quality | YES — last_game / last_3_games by design | ~90% (opening-day nulls → 0) |
| `sim/data/game_table.parquet` | Park Effects, Weather, Environment | YES — static / physical measurement | 100% |
| `sim/data/mlb_historical_closing_lines.parquet` | Market Geometry (2022–2023) | Contextual — closing total only | 78.5–82.4% |
| `sim/data/market_snapshots.parquet` | Market Geometry (2024–2025) | Contextual — closing total + CLV | 100% |

### Permanently Forbidden Sources

| Forbidden Source | Reason |
|-----------------|--------|
| `sim/data/feature_table.parquet` | Built by `sim/phase2_build_features.py` — season-level aggregates joined to game dates, creating target leakage (PIT contaminated) |
| `research/opponent_adjusted_engine_v2/pitcher_recent_adjusted_features.parquet` | Ambiguous lineage, possibly PIT contaminated — excluded by charter |
| Any file under `mlb_sim/data/` feature tables | Ambiguous creation provenance per charter rules |
| FanGraphs xFIP/SIERA (game-level) | Not available as PIT-safe game-level series |
| FanGraphs wRC+ (game-level) | Same; rolling hitter_game_logs used instead |

### Team Abbreviation Normalization
Applied to resolve pitcher_game_logs vs game_table naming mismatches:
`TB→TBR`, `WSH→WSN`, `CWS→CHW`, `SD→SDP`, `SF→SFG`, `AZ→ARI`, `KC→KCR`, `ATH→OAK`

---

## 4. Canonical Table Definition

### Raw Table (`context_engine_raw_table.parquet`)

| Property | Value |
|----------|-------|
| **Rows** | 9,715 |
| **Columns** | 72 |
| **Seasons** | 2022, 2023, 2024, 2025 |
| **Grain** | One row per game (game_pk is unique) |

**Column groups:**

- **Identity / Schedule (8):** `game_pk`, `date`, `season`, `home_team`, `away_team`, `home_score`, `away_score`, `actual_total`
- **Outcomes (4):** `actual_total`, `actual_f5_total`, `innings_played`, `completed_early`
- **Environment (11):** `venue_id`, `venue_name`, `park_id`, `temperature`, `wind_speed`, `wind_direction`, `roof_status`, `park_factor_runs`, `park_factor_hr`, `is_dome_or_closed`, `game_date_dt`
- **Scheduling (5):** `home_rest_days`, `away_rest_days`, `doubleheader_flag`, `game_number`, `game_hour_utc`, `local_start_hour`
- **Umpire (4):** `umpire_name`, `umpire_id`, `umpire_over_rate`, `umpire_k_rate`
- **Home Starter (10):** `home_sp_id`, `home_sp_name`, `home_sp_hand`, `home_sp_actual_ip`, `home_sp_avg_ip_r5`, `home_sp_k_rate_r5`, `home_sp_bb_rate_r5`, `home_sp_hr_rate_r5`, `home_sp_er9_r5`, `home_sp_ip_std_r5`, `home_sp_short_exit_r5`
- **Away Starter (10):** same prefix `away_sp_*`
- **Home Offense (4):** `home_obp_r10`, `home_slg_r10`, `home_iso_r10`, `home_hr_rate_r10`
- **Away Offense (4):** same prefix `away_*`
- **Home Bullpen (4):** `home_bp_rel_last1`, `home_bp_rel_last3`, `home_bp_pit_last3`, `home_bp_hl_avail`
- **Away Bullpen (4):** same prefix `away_bp_*`
- **Market (2):** `market_close_total`, `market_clv`

**HARD CHECK:** Raw table MUST have exactly 9,715 rows and 72 columns. Any deviation signals a rebuild error.

### Output Table (`context_engine_output_table.parquet`)

| Property | Value |
|----------|-------|
| **Rows** | 9,715 |
| **Columns** | 35 |

**Columns:** `game_pk`, `game_date_dt`, `season`, `home_team`, `away_team`, `actual_total`, `actual_f5_total`, `bre`, `bre_label`, `esp`, `esp_label`, `lsp`, `lsp_label`, `ss`, `ss_label`, `both_stable_flag`, `home_sp_stability`, `away_sp_stability`, `bs`, `bs_label`, `home_bp_stability`, `away_bp_stability`, `wpl`, `wpl_label`, `tcv`, `tcv_label`, `mps`, `mps_label`, `market_close_total`, `market_clv`, `park_factor_runs`, `temperature`, `wind_speed`, `is_dome_or_closed`, `umpire_over_rate`

---

## 5. Output Inventory Summary Table

| Code | Output Name | Status | Discovery Corr | Target Variable | Val Monotonic | OOS Monotonic |
|------|-------------|--------|---------------|-----------------|---------------|---------------|
| BRE | Baseline Run Environment | PRIMARY | r=0.098 | actual_total | PASS | PASS |
| ESP | Early Scoring Pressure | PRIMARY | r=0.091 | actual_f5_total | PASS | PASS |
| SS | Starter Stability | PRIMARY | r=0.215 | combined_IP | PASS | PASS |
| BS | Bullpen Stability | PRIMARY | r=-0.049 | late_runs | PASS | PASS |
| WPL | Weather and Park Lift | PRIMARY | r=0.154 | actual_total | PASS | PASS |
| LSP | Late Scoring Pressure | SECONDARY | r=0.049 | late_runs | PASS | PASS |
| TCV | Total Compression/Volatility | SECONDARY | weak | total_std | PASS | BORDERLINE |
| MPS | Market Path Shape | RESERVED-BLOCKED | N/A | line_movement | N/A | N/A |

---

## 6. Output-by-Output Frozen Specs

---

### 6.1 BRE — Baseline Run Environment

**A. Output Name:** Baseline Run Environment
**B. Output Code:** BRE
**C. Status:** PRIMARY

**D. Purpose:** Continuous score summarizing the expected per-game run-scoring baseline before game-day context is applied, combining park factor, umpire over-rate, and team offensive quality.

**E. Exact Formula:**
```
lineup_ops = avg(home_obp_r10 + home_slg_r10, away_obp_r10 + away_slg_r10) / 2

BRE = 0.40 * norm(park_factor_runs) + 0.35 * norm(lineup_ops) + 0.25 * norm(umpire_over_rate)
```
Where `norm()` = percentile rank in [0, 100] anchored to discovery (2022–2023) 5th–95th percentile range.

**F. Required Input Columns:** `park_factor_runs`, `home_obp_r10`, `home_slg_r10`, `away_obp_r10`, `away_slg_r10`, `umpire_over_rate`

**G. Directional Interpretation:** HIGH BRE = structurally high-scoring environment; LOW BRE = structurally low-scoring environment.

**H. Intended Usage:** Structural prior for all other decomposition outputs; population segmentation for niche objects.

**I. Forbidden Usage:** Direct betting trigger; threshold optimization; combined betting score.

**J. Validation Summary:**
- Discovery corr(BRE, actual_total) = 0.098
- HIGH bucket mean total: 9.48 (disc), 9.07 (val), 9.37 (OOS)
- LOW bucket mean total: 8.41 (disc), 8.48 (val), 8.44 (OOS)
- Monotonicity: PASS all splits

**K. Identity Lock:** Formula coefficient changes (0.40/0.35/0.25), input substitution (e.g., replacing umpire_over_rate), normalization bound re-anchoring, or bucket threshold changes each create a new object (V2+).

**Bucket Thresholds (frozen from discovery):**
- LOW: BRE < 39.41
- MEDIUM: 39.41 ≤ BRE ≤ 55.45
- HIGH: BRE > 55.45

---

### 6.2 ESP — Early Scoring Pressure

**A. Output Name:** Early Scoring Pressure
**B. Output Code:** ESP
**C. Status:** PRIMARY

**D. Purpose:** Measures run-scoring pressure concentrated in innings 1–5, driven by starter fragility, opposing offense depth, and early lineup quality.

**E. Exact Formula:**
```
SP_fragility = 0.50 * norm(er_per9_r5) + 0.30 * (100 - norm(avg_ip_r5)) + 0.20 * norm(short_exit_r5)

avg_sp_fragility = avg(home_SP_fragility, away_SP_fragility)

ESP = 0.50 * avg_sp_fragility + 0.30 * norm(lineup_ops) + 0.20 * BRE
```

**F. Required Input Columns:** `home_sp_er9_r5`, `home_sp_avg_ip_r5`, `home_sp_short_exit_r5`, `away_sp_er9_r5`, `away_sp_avg_ip_r5`, `away_sp_short_exit_r5`, `home_obp_r10`, `home_slg_r10`, `away_obp_r10`, `away_slg_r10`, BRE (computed)

**G. Directional Interpretation:** HIGH ESP = starters fragile, heavy early-inning run scoring expected; LOW ESP = starters dominant, early innings suppressed.

**H. Intended Usage:** Primary input for F5 totals niche objects; structural characterization of early-game run pressure.

**I. Forbidden Usage:** Direct betting trigger; treated as independent evidence alongside LSP (they share inputs and have r=0.724 correlation); combined betting score.

**J. Validation Summary:**
- Discovery corr(ESP, actual_f5_total) = 0.091
- HIGH bucket F5 mean: 5.37 (disc), 5.26 (val), 5.26 (OOS)
- LOW bucket F5 mean: 4.68 (disc), 4.84 (val), 4.82 (OOS)
- Monotonicity: PASS all splits

**K. Identity Lock:** Any change to SP_fragility sub-formula weights (0.50/0.30/0.20), ESP formula weights (0.50/0.30/0.20), input substitution, or bucket thresholds creates a new object.

**Bucket Thresholds (frozen from discovery):**
- LOW: ESP < 36.03
- MEDIUM: 36.03 ≤ ESP ≤ 49.89
- HIGH: ESP > 49.89

---

### 6.3 LSP — Late Scoring Pressure

**A. Output Name:** Late Scoring Pressure
**B. Output Code:** LSP
**C. Status:** SECONDARY

**D. Purpose:** Measures run-scoring pressure generated in innings 6–9, driven by bullpen instability, lineup depth, and persistent park/weather conditions. Captures games where the under holds through F5 but the full-game over hits.

**E. Exact Formula:**
```
BP_instability_home = norm(home_bp_pit_last3) * 0.60 + (1 - home_bp_hl_avail) * 100 * 0.40
BP_instability_away = norm(away_bp_pit_last3) * 0.60 + (1 - away_bp_hl_avail) * 100 * 0.40
avg_bp_instability = avg(BP_instability_home, BP_instability_away)

LSP = 0.45 * avg_bp_instability + 0.30 * norm(lineup_ops) + 0.25 * avg_sp_fragility
```

**F. Required Input Columns:** `home_bp_pit_last3`, `home_bp_hl_avail`, `away_bp_pit_last3`, `away_bp_hl_avail`, `home_obp_r10`, `home_slg_r10`, `away_obp_r10`, `away_slg_r10`, `home_sp_er9_r5`, `home_sp_avg_ip_r5`, `home_sp_short_exit_r5`, `away_sp_er9_r5`, `away_sp_avg_ip_r5`, `away_sp_short_exit_r5`

**G. Directional Interpretation:** HIGH LSP = late-inning run pressure elevated, full-game total likely driven by bullpen exposure; LOW LSP = fresh bullpens, late innings suppressed.

**H. Intended Usage:** Identify F5-under / full-game-over divergence games; provide late-inning context for full-game niche objects.

**I. Forbidden Usage:** Independent evidence alongside ESP (shared inputs, r=0.724); direct betting trigger; combined betting score.

**J. Validation Summary:**
- Discovery corr(LSP, late_runs) = 0.049
- HIGH bucket late-run mean: 4.01 (disc), 4.18 (val), 4.07 (OOS)
- LOW bucket late-run mean: 3.73 (disc), 3.71 (val), 3.61 (OOS)
- Monotonicity: PASS all splits
- WARNING: ESP vs LSP r = 0.724 — not to be used as independent factors

**K. Identity Lock:** Any formula weight change, input substitution, or bucket threshold change creates a new object.

**Bucket Thresholds (frozen from discovery):**
- LOW: LSP < 43.08
- MEDIUM: 43.08 ≤ LSP ≤ 54.37
- HIGH: LSP > 54.37

---

### 6.4 SS — Starter Stability

**A. Output Name:** Starter Stability
**B. Output Code:** SS
**C. Status:** PRIMARY

**D. Purpose:** Measures how likely both starters are to go deep, maintain quality through the lineup rotation, and avoid early exits. Anchor input for P1B-style under objects.

**E. Exact Formula:**
```
SP_stability_home = 0.40 * norm(home_sp_avg_ip_r5) + 0.35 * norm(home_sp_k_rate_r5) + 0.25 * (100 - norm(home_sp_bb_rate_r5))
SP_stability_away = 0.40 * norm(away_sp_avg_ip_r5) + 0.35 * norm(away_sp_k_rate_r5) + 0.25 * (100 - norm(away_sp_bb_rate_r5))

SS = avg(SP_stability_home, SP_stability_away)
BOTH_STABLE_flag = (SP_stability_home > 55) AND (SP_stability_away > 55)
```

**F. Required Input Columns:** `home_sp_avg_ip_r5`, `home_sp_k_rate_r5`, `home_sp_bb_rate_r5`, `away_sp_avg_ip_r5`, `away_sp_k_rate_r5`, `away_sp_bb_rate_r5`

**G. Directional Interpretation:** STABLE SS = both starters dominant, pitchers' duel expected, total suppressed; FRAGILE SS = at least one starter at risk of early exit, total elevated.

**H. Intended Usage:** Anchor for P1B (Starter Dominance Under) and similar under niche objects; structural segmentation by pitching regime.

**I. Forbidden Usage:** Direct betting trigger; combined betting score; only one side evaluated when BOTH_STABLE_flag is the operative condition.

**J. Validation Summary:**
- Discovery corr(SS, combined_actual_IP) = 0.215 (strongest output)
- BOTH_STABLE mean total: 8.50 (disc), 8.31 (val), 8.41 (OOS) vs 8.98/8.89/8.98 baseline
- P1B OOS suppression: 0.48 runs below baseline (376 games)
- Monotonicity: PASS all splits (STABLE < AVERAGE < FRAGILE for mean totals)

**K. Identity Lock:** Per-starter sub-formula weight changes (0.40/0.35/0.25), BOTH_STABLE threshold (55) change, input substitution, or bucket thresholds changes create a new object.

**Bucket Thresholds (frozen from discovery):**
- FRAGILE: SS < 45.92
- AVERAGE: 45.92 ≤ SS ≤ 57.09
- STABLE: SS > 57.09

---

### 6.5 BS — Bullpen Stability

**A. Output Name:** Bullpen Stability
**B. Output Code:** BS
**C. Status:** PRIMARY

**D. Purpose:** Measures availability and freshness of both bullpens entering the game. Separates bullpen quality from availability — elite relievers who are unavailable are unstable.

**E. Exact Formula:**
```
BP_stability_home = 0.40 * (100 - norm(home_bp_rel_last3)) + 0.40 * (100 - norm(home_bp_pit_last3)) + 0.20 * home_bp_hl_avail * 100
BP_stability_away = 0.40 * (100 - norm(away_bp_rel_last3)) + 0.40 * (100 - norm(away_bp_pit_last3)) + 0.20 * away_bp_hl_avail * 100

BS = avg(BP_stability_home, BP_stability_away)
```

**F. Required Input Columns:** `home_bp_rel_last3`, `home_bp_pit_last3`, `home_bp_hl_avail`, `away_bp_rel_last3`, `away_bp_pit_last3`, `away_bp_hl_avail`

**G. Directional Interpretation:** STABLE BS = fresh bullpens, late innings suppressed; UNSTABLE BS = heavy recent usage, depleted closers, late-inning run accumulation elevated.

**H. Intended Usage:** Complement to SS; identifies games where high SS + high BS predicts strong under pressure; identifies bullpen implosion risk for over-targeting objects.

**I. Forbidden Usage:** Direct betting trigger; combined betting score.

**J. Validation Summary:**
- Discovery corr(BS, late_runs) = -0.049 (expected negative sign confirmed)
- UNSTABLE late-run mean: 3.99 (disc), 4.08 (val), 4.13 (OOS)
- STABLE late-run mean: 3.72 (disc), 3.67 (val), 3.83 (OOS)
- Monotonicity: PASS all splits

**K. Identity Lock:** Per-team sub-formula weight changes (0.40/0.40/0.20), input substitution, or bucket threshold changes create a new object.

**Bucket Thresholds (frozen from discovery):**
- UNSTABLE: BS < 38.86
- NEUTRAL: 38.86 ≤ BS ≤ 53.26
- STABLE: BS > 53.26

---

### 6.6 WPL — Weather and Park Lift

**A. Output Name:** Weather and Park Lift
**B. Output Code:** WPL
**C. Status:** PRIMARY

**D. Purpose:** Composite score measuring how much the physical environment (park factor, temperature, wind) lifts or suppresses run scoring relative to a neutral environment.

**E. Exact Formula:**
```
park_deviation = (park_factor_runs - 100) / 3
temp_effect = (temperature - 65) / 10
wind_effect = wind_speed * 0.1   [outdoor only; direction not signed]

WPL = IF is_dome_or_closed:
    park_deviation
ELSE:
    0.40 * park_deviation + 0.40 * temp_effect + 0.20 * wind_effect
```
Note: Wind direction is NOT signed in V1. Wind is treated as volatility-additive only. Park bearing data was unavailable. Signed directional wind is a V2 enhancement.

**F. Required Input Columns:** `park_factor_runs`, `temperature`, `wind_speed`, `is_dome_or_closed`

**G. Directional Interpretation:** LIFTED WPL = physical environment pushes run scoring above baseline; SUPPRESSED WPL = conditions actively suppress runs; dome/closed games zero out weather components.

**H. Intended Usage:** Environmental context for all other outputs; niche object regime awareness for weather-adjacent edges.

**I. Forbidden Usage:** Direct betting trigger; combined betting score.

**J. Validation Summary:**
- Discovery corr(WPL, actual_total) = 0.154
- LIFTED mean total: 9.92 (disc), 9.04 (val), 9.32 (OOS)
- SUPPRESSED mean total: 8.25 (disc), 7.89 (val), 8.54 (OOS)
- Monotonicity: PASS all splits

**K. Identity Lock:** Formula weight changes (0.40/0.40/0.20), physical scaling changes (÷3, ÷10, ×0.1), bucket threshold changes (-1.0/+1.0), or addition of signed wind direction create a new object.

**Bucket Thresholds (frozen from discovery — signed scale):**
- SUPPRESSED: WPL < -1.0
- NEUTRAL: -1.0 ≤ WPL ≤ 1.0
- LIFTED: WPL > 1.0

---

### 6.7 TCV — Total Compression / Volatility State

**A. Output Name:** Total Compression / Volatility State
**B. Output Code:** TCV
**C. Status:** SECONDARY

**D. Purpose:** Measures outcome variance — how wide or tight the run distribution is for this game. High TCV means a wide range of outcomes is plausible (blow-up or shutdown). Low TCV means the distribution is compressed.

**E. Exact Formula:**
```
sp_variance = avg(norm(home_sp_ip_std_r5), norm(away_sp_ip_std_r5))
avg_bp_instability = [same as LSP component]
esp_ss_spread = norm(|ESP - SS|)

TCV = 0.40 * sp_variance + 0.35 * avg_bp_instability + 0.25 * esp_ss_spread
```

**F. Required Input Columns:** `home_sp_ip_std_r5`, `away_sp_ip_std_r5`, `home_bp_pit_last3`, `home_bp_hl_avail`, `away_bp_pit_last3`, `away_bp_hl_avail`, ESP (computed), SS (computed)

**G. Directional Interpretation:** VOLATILE TCV = wider outcome distribution, tail risks higher; COMPRESSED TCV = tight distribution, game unlikely to blow up in either direction.

**H. Intended Usage:** Weak context only — identifies games with tail risk for niche objects targeting extreme outcome buckets. Not a lead driver.

**I. Forbidden Usage:** Direct betting trigger; lead driver of niche object decisions; combined betting score.

**J. Validation Summary:**
- Effect size is modest (< 0.2 std spread across buckets)
- Discovery: COMPRESSED std=4.453, VOLATILE std=4.616
- Validation: COMPRESSED std=4.419, VOLATILE std=4.141 (order reverses — BORDERLINE)
- OOS: COMPRESSED std=4.588, VOLATILE std=4.495 (direction holds weakly)
- WARNING: Validation split shows reversal. TCV classified SECONDARY / weak context.

**K. Identity Lock:** Formula weight changes, input substitution, or bucket threshold changes create a new object.

**Bucket Thresholds (frozen from discovery):**
- COMPRESSED: TCV < 42.46
- BALANCED: 42.46 ≤ TCV ≤ 53.32
- VOLATILE: TCV > 53.32

---

### 6.8 MPS — Market Path Shape

**A. Output Name:** Market Path Shape
**B. Output Code:** MPS
**C. Status:** RESERVED-BLOCKED

**D. Purpose:** Intended to classify how the total line moved from open to close (EARLY-HEAVY, LATE-HEAVY, BALANCED, COMPRESSED). Provides market intelligence context about whether informed or public money dominated movement.

**E. Exact Formula:** NOT COMPUTABLE — open total lines unavailable for all seasons 2022–2025. Historical Odds API pull only captured closing snapshots. CLV (2024–2025 only) does not provide directional movement from an open line.

**F. Required Input Columns (blocked):** `open_total` (unavailable all seasons), `noon_total` (unavailable), `close_total`

**G. Directional Interpretation:** Would be: EARLY-HEAVY = informed money drove movement; LATE-HEAVY = public money or late news. Cannot be assigned with current data.

**H. Intended Usage:** Market intelligence context for downstream niche objects assessing sharpness of closing line.

**I. Forbidden Usage:** All downstream use is forbidden until data becomes available and the output is formally unblocked in a future version.

**J. Validation Summary:** N/A — no data available for computation.

**K. Identity Lock:** MPS activation with any formula constitutes a new object distinct from V1. No proxy authorized. Current output table value: "DATA-BLOCKED" for all 9,715 games.

---

## 7. Engine-Level Interpretation Rules (Governance)

**Rule 1 — Engine Classification:** Context Engine V1 is a descriptive/decomposition engine ONLY. It is not a betting engine. It produces no edge output, no probability estimate, and no direct betting recommendation. Any downstream use that generates a bet directly from these outputs violates this rule.

**Rule 2 — PRIMARY Outputs:** BRE, ESP, SS, BS, and WPL are classified PRIMARY. They have consistent directional behavior across discovery, validation, and OOS splits. They may be used as structural characterization inputs for downstream niche objects.

**Rule 3 — SECONDARY Outputs:** LSP and TCV are classified SECONDARY. LSP has r=0.724 with ESP (flagged redundancy). TCV shows borderline monotonicity failure in validation. Both carry directional signal but cannot serve as lead drivers.

**Rule 4 — RESERVED/BLOCKED Output:** MPS is permanently blocked in V1. No proxy formula, no approximation, and no CLV-derived substitute is authorized. MPS activation requires a new engine version with actual open-line data.

**Rule 5 — ESP and LSP Redundancy:** ESP and LSP share input components (avg_sp_fragility, lineup_ops) and have r=0.724 pairwise correlation. They cannot both be treated as independent evidence in the same downstream analysis. If both are used, the analyst must explicitly account for the shared variance and document the reasoning.

**Rule 6 — TCV as Weak Context:** TCV is weak context only. It may be used to note that a game has elevated tail risk, but it cannot drive a downstream signal, filter a population, or be cited as a reason to take or avoid a bet.

**Rule 7 — Downstream Validation Responsibility:** Downstream objects (P1B, F5 pressure objects, dead totals objects) that consume these outputs must independently validate their use within their own structural population. The context engine does not guarantee that its outputs are predictive within any specific niche population.

**Rule 8 — Formula/Input/Fallback Change Control:** Any change to a formula coefficient, input column, missing-data fallback, normalization bound, or bucket threshold creates a new engine version (V2 or a new object). It does not update V1. V1 formulas and thresholds are frozen as of 2026-04-12.

**Rule 9 — Characterization Without Redefinition:** The context engine may characterize downstream objects (e.g., what fraction of P1B's OOS population had LIFTED WPL) but may not redefine them. P1B's firing condition is defined by P1B's own spec, not by this engine.

**Rule 10 — No Combined Betting Score:** No weighted combination, sum, average, or model output derived from BRE, ESP, LSP, SS, BS, WPL, and TCV may be used as a betting signal. These outputs are decomposition components, not factors to be aggregated into a total score.

---

## 8. Known Warnings and Limitations

1. **ESP vs LSP Correlation (r=0.724):** Above the redundancy threshold. They share avg_sp_fragility as a structural component. Downstream objects must not cite both as independent drivers.

2. **TCV Validation Reversal:** In the 2024 validation split, VOLATILE TCV bucket has lower std (4.141) than COMPRESSED (4.419), reversing the expected direction. The pattern recovers weakly in OOS (4.495 vs 4.588). TCV is borderline and classified SECONDARY.

3. **Wind Direction Not Signed:** WPL wind component uses speed only, not direction. Without park CF bearing data, outward vs inward wind cannot be distinguished. This understates WPL accuracy for outdoor stadiums with strong directional wind. This is a V2 enhancement.

4. **Market Coverage Gaps:** Closing total unavailable for ~20% of 2022 and 2023 games. market_clv unavailable for all 2022–2023 games. Niche objects using market geometry context are limited to 2024–2025 full coverage.

5. **MPS Permanently Blocked:** No open-line historical data exists. All 9,715 MPS values are "DATA-BLOCKED". Forward collection from 2026 is required to populate this output in any future version.

6. **Starter Coverage at Season Open:** Games early in season with < 2 prior starts receive None for rolling starter features, which propagates to ESP and SS. These games represent ~6–7% of the sample and fall back to league-average imputation.

7. **TCV Effect Size Is Small:** Even in discovery, the std spread between COMPRESSED and VOLATILE is only 0.16 runs per game. This is a real but modest signal.

8. **BRE vs ESP Correlation (r=0.654):** BRE is a 20% component of ESP by construction. This is expected but means BRE and ESP cannot both be used as fully independent structural axes.

---

## 9. Identity Lock / Change-Control Rules

The following changes each constitute a new engine version (MLBCE-V2 or a new named object). None are authorized under MLBCE-V1:

| Change Type | Effect |
|-------------|--------|
| Formula coefficient change (any output) | New object |
| Input column substitution (any output) | New object |
| Normalization bound re-anchoring (e.g., use 2022–2024 as discovery) | New object |
| Bucket threshold change (any output) | New object |
| Addition of signed wind direction to WPL | New object |
| MPS activation with any formula | New object |
| Inclusion of any forbidden source file | Invalidates V1 permanently |
| Extension of discovery period beyond 2023 | New object |
| Any re-fitting, optimization, or re-calibration | New object |

---

## 10. Approved Downstream Use Cases

1. **Structural segmentation:** Downstream niche objects may use output bucket labels (e.g., BRE=HIGH, SS=STABLE) to define the structural population in which their signal operates.

2. **Regime characterization:** Report which structural quadrant a set of historical signals fired in (e.g., "72% of P1B OOS wins occurred in BRE=LOW or MEDIUM games").

3. **False-positive analysis:** Use WPL or BS to characterize cases where a niche object fired but lost — understand if the loss was correlated with LIFTED WPL or UNSTABLE BS conditions.

4. **Population conditioning:** Define sub-populations of the 9,715-game table by combining output labels, then measure niche object hit rate within that sub-population.

5. **P1B structural depth:** Use WPL and BS to understand the structural headwinds/tailwinds present when both_stable_flag=1, as demonstrated in Phase 9 Case Study 1.

6. **Dead totals identification:** Combine BRE=MEDIUM, WPL=NEUTRAL, SS=AVERAGE, BS=NEUTRAL to identify ordinary games where market efficiency is highest.

7. **Context documentation:** Record the context engine output labels for any live bet to enable post-hoc structural attribution.

---

## 11. Forbidden Downstream Use Cases

1. Deriving a betting edge directly from any context engine output.
2. Combining BRE + ESP + SS + BS + WPL + LSP + TCV into a weighted score for bet sizing or selection.
3. Optimizing niche object thresholds using context engine outputs as predictors.
4. Using MPS in any form (no proxy authorized).
5. Treating ESP and LSP as independent evidence in the same signal.
6. Using TCV as a lead driver for tail-risk betting.
7. Extending the discovery period to improve thresholds retrospectively.
8. Applying context engine outputs to 2026 data without documenting that thresholds were frozen on 2022–2023.
9. Using context engine labels as the sole basis for skipping or taking a bet.
10. Backtesting ROI using context engine output combinations as filters.

---

## 12. Validation Checklist Output

### Discovery-Validation Leakage Check
**PASS.** All formula development, weight assignment, normalization bounds, and bucket thresholds were derived exclusively from discovery data (2022–2023, n=4,860 games). Validation (2024) and OOS (2025) were observe-only. Thresholds were NOT adjusted after viewing validation or OOS results. Discovery is permanently defined as seasons 2022 and 2023.

### PIT Feature Provenance Check
**PASS.** Source-code proof of PIT safety exists for all feature families:
- Starter features: shift(1) applied before rolling 5-start window (pitcher_game_logs)
- Offense features: shift(1) applied before rolling 10-game team aggregates (hitter_game_logs)
- Bullpen features: pre-computed as `last_game` / `last_3_games` lookback (bullpen_features.parquet is PIT-safe by design)
- Park factors: static structural venue properties (no outcome derivation)
- Weather: game-day physical measurement (no statistical aggregate)
- Market closing total: contextual input, not a predictive feature; flagged as market geometry

### Research/Live Identity Check
**N/A (documentation freeze).** No live object exists. All formulas are fully specified in phase5_decomposition_formulas.md and frozen in this document. A live implementation can be constructed directly from the documented formulas without ambiguity.

### Actual-Price Economics Check
**N/A — not a betting engine.** No edge computation, no probability output, no ROI optimization was performed at any stage.

### Regime Breakdown Check
**PASS.** Season-by-season breakdowns are present in phase7_component_validation.md for all 7 active outputs across discovery, validation, and OOS splits. All bucket/split combinations have N ≥ 75. All 5 PRIMARY outputs pass monotonicity in all 3 splits. TCV fails monotonicity in validation (classified SECONDARY/BORDERLINE). MPS has no validation data (DATA-BLOCKED).

---

## 13. Open Blocked Item: MPS

**Item:** Market Path Shape (MPS)
**Status:** RESERVED-BLOCKED in V1
**Reason:** Open total lines are unavailable for all seasons 2022–2025. Historical Odds API pull captured closing snapshots only. No open/noon/5pm lines exist for any game in the canonical table.
**CLV note:** CLV (closing line value) is available for 2024–2025 only, but this is close_total minus decision_line where both are the same closing line. It does not provide directional open-to-close movement.
**Required to unblock:** Systematic live collection of opening totals starting from a defined date (e.g., 2026 Opening Day onward). Minimum sample of 2 full seasons (2026–2027) required before MPS formula can be developed on discovery data.
**No proxy authorized:** CLV, line movement proxies, or inferred movement from CLV magnitude are not authorized substitutes. MPS must be built from actual time-stamped open/noon/close line data.
**Current table value:** All 9,715 MPS values = "DATA-BLOCKED". mps_label = "DATA-BLOCKED" for all rows.
**Action required:** None in V1. This is a documented open item for the V2 research roadmap.

---

## Appendix A: Frozen Threshold Summary

| Output | Low Threshold | Low Label | High Threshold | High Label |
|--------|--------------|-----------|----------------|------------|
| BRE | < 39.41 | LOW | > 55.45 | HIGH |
| ESP | < 36.03 | LOW | > 49.89 | HIGH |
| LSP | < 43.08 | LOW | > 54.37 | HIGH |
| SS | < 45.92 | FRAGILE | > 57.09 | STABLE |
| BS | < 38.86 | UNSTABLE | > 53.26 | STABLE |
| WPL | < -1.0 | SUPPRESSED | > 1.0 | LIFTED |
| TCV | < 42.46 | COMPRESSED | > 53.32 | VOLATILE |
| MPS | DATA-BLOCKED | — | DATA-BLOCKED | — |

---

## Appendix B: Source File Checksums (Rebuild Reference)

| Source File | Rows | Key Column Coverage |
|-------------|------|---------------------|
| `mlb/data/pitcher_game_logs.parquet` | 84,938 total; 19,864 starter rows | innings_pitched: 0% null in starter subset |
| `mlb/data/hitter_game_logs.parquet` | 204,548 rows (starter batters, 2022–2026) | OBP/SLG: full coverage |
| `sim/data/bullpen_features.parquet` | 19,302 team-game rows | hl_avail: ~0% null; usage: ~10% null (opening day) |
| `sim/data/game_table.parquet` | 9,715 games | park_factor_runs: 100% |
| `sim/data/mlb_historical_closing_lines.parquet` | 3,911 games (2022–2023) | close_total: ~80% |
| `sim/data/market_snapshots.parquet` | 4,855 games (2024–2025) | close_total: 100% |

---

*Document frozen: 2026-04-12*
*Engine: MLBCE-V1*
*Status: CANONICAL — NO FURTHER CHANGES PERMITTED*
