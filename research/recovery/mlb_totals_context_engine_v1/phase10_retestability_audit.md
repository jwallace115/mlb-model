# Phase 10 - Retestability Audit
## MLB Totals Context Engine V1

### Can This Engine Be Rebuilt from Scratch?

**Answer: YES, with one condition.** The engine can be rebuilt completely from raw source files using the documented pipeline. The one condition is that all source files must be available (listed below). No intermediate cached files are required.

---

### Rebuild Pipeline

1. **Source files (raw, no derived files):**
   - `mlb/data/pitcher_game_logs.parquet` - available, audited
   - `mlb/data/hitter_game_logs.parquet` - available, audited
   - `sim/data/game_table.parquet` - available, audited
   - `sim/data/bullpen_features.parquet` - available, audited
   - `sim/data/mlb_historical_closing_lines.parquet` - available, audited
   - `sim/data/market_snapshots.parquet` - available, audited

2. **Phase 4 build script:** Documented in phase4_raw_table_build.md. Can reproduce `context_engine_raw_table.parquet` exactly from source files.

3. **Phase 5 formulas:** Documented in phase5_decomposition_formulas.md. All formula coefficients, input definitions, and discovery normalization bounds are explicitly stated. No code optimization or hyperparameter search was performed.

4. **Phase 5 thresholds:** All bucket thresholds are stated explicitly in phase5_output_formula_table.csv. They are derived from discovery data only and do not change if source data is extended. DISCOVERY = 2022-2023 is a permanent definition.

5. **Phase 6 application:** Apply frozen formulas to full dataset. No additional fit steps.

---

### Formula Freeze Verification

| Formula | Coefficients Documented | Normalization Bounds Fixed | Thresholds Fixed |
|---------|------------------------|--------------------------|-----------------|
| BRE | YES - 0.40, 0.35, 0.25 | YES - discovery 5th-95th | YES - 33rd/67th |
| ESP | YES - 0.50, 0.30, 0.20 | YES - per feature | YES |
| LSP | YES - 0.45, 0.30, 0.25 | YES | YES |
| SS | YES - 0.40, 0.35, 0.25 | YES | YES |
| BS | YES - 0.40, 0.40, 0.20 | YES | YES |
| WPL | YES - 0.40, 0.40, 0.20, signed | Fixed physical scaling | Fixed -1.0/+1.0 |
| TCV | YES - 0.40, 0.35, 0.25 | YES | YES |
| MPS | DATA-BLOCKED | N/A | N/A |

---

### What Would Change in a Rebuild?

**Nothing should change** if:
- The same source files are used
- The same 2022-2023 discovery definition is applied
- The same rolling window sizes and min_periods are used

**What could differ due to external changes:**
- New 2026 seasons added: would NOT change discovery formulas (2022-2023 frozen)
- Team abbreviation corrections: would affect normalization bounds slightly
- Source file schema changes: would require code updates but formulas unchanged

---

### Forbidden Files and Their Effect

| Forbidden File | Effect if Accidentally Used |
|---------------|----------------------------|
| sim/data/feature_table.parquet | PIT contamination - season-level xFIP leaks future data |
| research/opponent_adjusted_engine_v2/ | Unknown lineage - may include game-day information |
| mlb_sim/data/ feature tables | Ambiguous creation date and process |

**Guard:** Phase 4 build script does NOT import these files. They are not referenced anywhere in the Phase 4-6 pipeline.

---

### Data Dependency Graph (simplified)

```
pitcher_game_logs.parquet
  -> shift(1) rolling 5-start features
     -> starter_stability score
     -> starter_fragility score
  
hitter_game_logs.parquet
  -> shift(1) rolling 10-game team features
     -> lineup_ops score

bullpen_features.parquet (already PIT-safe by design)
  -> bullpen_instability score
  -> bullpen_stability score

game_table.parquet
  -> park_factor_runs, temperature, wind_speed, umpire_over_rate
     -> WPL score, BRE components

[all above] -> context_engine_raw_table.parquet
             -> frozen formulas applied
             -> context_engine_output_table.parquet
```

---

### Retestability Verdict

**RETESTABLE.** The engine can be rebuilt in its entirety from approved source files using documented formulas. No hidden state, no cached intermediate models, no external API dependencies during rebuild.

---

Built: 2026-04-12
