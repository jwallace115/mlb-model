# Phase 3: PIT-Safety Source Lineage

**Date:** 2026-04-12

---

## Two Separate Contexts

### Context A: LIVE DAILY PIPELINE (Signal Generator)

**Chain:**
```
run_model.py
  -> f5_runline_signal_generator.generate_signals()
    -> modules.pitchers.get_pitcher_metrics(pitcher_info, pitcher_db)
      -> pitcher_db populated from FanGraphs API (live, daily-fresh)
      -> Fallback: Savant xERA -> league average
```

**PIT-safe?** YES. FanGraphs API returns season-to-date stats as of today.
No lookahead. No V1 dependency. No feature_table. No sim model.

**Confirmed by:** Phase 1 parity audit (signal_b_reactivation/phase1_parity_audit.md)
and direct code inspection — `get_pitcher_metrics()` is the ONLY xFIP source.

### Context B: HISTORICAL BACKTEST (Original Research)

**Chain:**
```
research/f5_runline/run_f5_runline_research.py
  -> loads sim_inputs_historical_2022_2024.parquet + sim_inputs_2025.parquet
    -> built by mlb_sim/data/build_sim_inputs.py
      -> reads feature_table (home_sp_xfip, away_sp_xfip)
        -> feature_table has STATIC season-final xFIP per pitcher per season
```

**PIT-safe?** NO. Confirmed by direct inspection:
- MacKenzie Gore: xFIP = 4.151 for ALL 2024 starts (April through June)
- Chris Bassitt: xFIP = 4.422 for ALL 2024 starts
- Kutter Crawford: xFIP = 3.949 for ALL 2024 starts

This means the +27.9% ROI and +29.1% 2025 OOS results are inflated.
The model knew end-of-season pitcher quality when making early-season bets.

### Context C: V1 DEPENDENCY REVALIDATION (PIT-Clean Retest)

**Chain:**
```
research/recovery/v1_dependency_revalidation/run_revalidation.py
  -> loads baseball_features_pit_v1.parquet
    -> xFIP varies game-to-game (expanding means, properly lagged)
```

**PIT-safe?** YES. Confirmed by direct inspection:
- MacKenzie Gore 2024: 4.395, 4.348, 4.260, 4.226, 4.184... (decreasing through season)
- Chris Bassitt 2024: 3.833, 3.843, 3.847, 3.900, 3.857... (varying by game)

This is the ONLY PIT-clean backtest of Signal B's threshold.
Results at this level: gap >= 1.0 = borderline (50-53%), gap >= 1.5 = strong (59-60%).

---

## Summary Table

| Context | Data Source | xFIP Type | PIT-Safe | ROI/Under Rate |
|---------|-----------|-----------|----------|---------------|
| Live daily | FanGraphs API | Season-to-date (live) | YES | N/A (forward) |
| Original backtest | sim_inputs parquet | Season-final (static) | NO | +27.9% ROI (inflated) |
| PIT revalidation | baseball_features_pit_v1 | Expanding mean (lagged) | YES | 59-60% under at 1.5 |

---

## Critical Note on PIT Revalidation Methodology

The V1 revalidation tested Signal B using **full-game under rate** as a proxy,
not F5 run line cover rate. This is because:
1. Historical F5 scores are available but were not part of the PIT features
2. Full-game under rate is a directional proxy (dominant starter -> fewer runs)
3. The 59-60% full-game under rate at gap >= 1.5 is a CONSERVATIVE estimate
   of F5 edge, since the dominant starter effect is strongest in the first 5 innings

The proxy is imperfect but the direction is clear: gap >= 1.5 shows meaningful
PIT-clean signal; gap >= 1.0 does not.
