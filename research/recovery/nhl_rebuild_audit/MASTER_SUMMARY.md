# NHL Rebuild Audit -- Master Summary
Date: 2026-04-10

## Audit Scope
Independent provenance and identity audit of the NHL clean rebuild
(research/recovery/nhl_rebuild/nhl_rebuild.py) to verify it:
1. Uses clean data (no MoneyPuck analytics contamination)
2. Is PIT-safe (no look-ahead bias)
3. Did not reuse contaminated artifacts
4. Can be run live identically

## Phase Results

### Phase 1: Feature Lineage -- CLEAN
- Reads only 2 files: canonical CSV + market snapshots
- Zero MoneyPuck analytics columns used as features
- SOG values come from MoneyPuck's NHL data aggregation (not proprietary xG/HD)
- All 32 features traceable to NHL API boxscore or schedule data

### Phase 2: PIT Safety -- CLEAN (with minor caveat)
- Rolling windows use strict `iloc[:i]` (prior games only)
- Per-season reset with no cross-season leakage
- 5/5 manual spot checks match exactly (delta = 0.0000)
- MINOR: League average shrinkage prior uses full-season avg (look-ahead)
  - Severity LOW: affects only first ~10 games, avg varies <0.15/season

### Phase 3: Artifact Reuse -- CLEAN
- Zero references to any contaminated artifact (10 checked)
- No pickle loads; all models trained from scratch
- All output isolated under research/recovery/nhl_rebuild/

### Phase 4: Idempotency -- VERIFIED
- 6,506/6,506 games match between feature table and canonical
- All scores match exactly
- All features in plausible ranges, zero unexpected NaN
- Script is deterministic (fixed random_state=42)

### Phase 5: Live Identity -- NOT IDENTICAL (fixable)
- 32/32 rebuild features exist in live feature table (100% overlap)
- HOWEVER: live pipeline does not currently extract SOG/PP/PK from
  NHL API boxscores (falls back to MoneyPuck priors, which are stale)
- Fix requires ~30 lines in nhl_daily_pipeline.py (the endpoint is
  already being called; parsing is missing)

### Phase 6: Economics -- HONEST
- Uses actual closing prices (not flat -110)
- 100% price coverage in OOS season
- Price distribution is realistic (mean around -110, range -142 to +300)

### Phase 7: Regime -- GENUINE SIGNAL with bias concern
- corr(edge, market_error) = 0.1552 (strong genuine signal)
- Edge-size calibration is monotonic (0.3+ edge -> 52-63% win rate)
- Both over and under directions show positive win rates
- CONCERN: Growing negative bias (-0.02 in 2023 -> -0.16 in 2024)
- SOG trend declining (31.6 -> 28.0 avg), may require recalibration

## Key Metrics (OOS 2024-25)

| Model              | MAE    | vs Market | corr(edge,mkt_err) |
|-------------------|--------|-----------|-------------------|
| Market baseline   | 1.8956 | --        | --                |
| Model A (pure)    | 1.8714 | -1.3%     | 0.1552            |
| Model B (residual)| 1.8882 | -0.4%     | n/a               |
| Model C (hybrid)  | 1.8742 | -1.1%     | 0.1415            |

## Betting Simulation (Model A, OOS, actual prices)
| Edge Threshold | Bets | Win%  | ROI    |
|---------------|------|-------|--------|
| >= 0.0        | 1266 | 56.3% | +5.3%  |
| >= 0.5        | 358  | 56.7% | +3.8%  |
| >= 0.8        | 114  | 58.8% | +6.6%  |
| >= 1.0        | 30   | 63.3% | +12.2% |
