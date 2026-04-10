# V1 Dependency Revalidation — MASTER SURVIVAL MAP

**Date:** 2026-04-10
**Clean V1 model:** v1_ridge_clean.pkl (25 features, alpha=50, sigma=4.4237)
**Clean backtest:** 9695 games, 9451 with closing lines

## Summary Table

| Object | Status | Reason |
|--------|--------|--------|
| F5 Totals Engine | **DIMINISHED** | Consumes V1 p_under/p_over directly; inherits all V1 degradation |
| F5 Run Line (Signal B) | **SURVIVES** | Independent of V1; uses live FG xFIP; 1.0 gap is heuristic |
| S12 Overlay | **DIMINISHED** | Cutoff (8.4468) derived from contaminated xFIP; amplifies losing UNDER bets |
| P09 Overlay | **SURVIVES** | Inputs fully clean (Statcast+config); value contingent on V1 base |
| flyball_wind_interaction | **DIMINISHED** | PIT proxy noisier; small feature (~rank 11/25); live operation clean |
| Tier/Threshold/STRONG | **COLLAPSES** | All thresholds negative ROI on clean V1; no profitable tier exists |

## Detail

### SURVIVES (2/6)
- **F5 Run Line**: Fully independent pipeline. Live xFIP is clean. Threshold is heuristic.
- **P09 Overlay**: Clean inputs (Statcast hard-hit + static park factors). Cutoff derived from clean data.
  Note: overlay value is contingent on V1 UNDER signals being profitable.

### DIMINISHED (3/6)
- **F5 Totals Engine**: Directly reads V1 probabilities. Signal frequency and quality degrade with clean V1.
  Requires threshold re-tuning on clean V1 outputs.
- **S12 Overlay**: Live firing uses fresh FG xFIP (clean), but the 8.4468 cutoff was derived from
  season-final xFIP. The cutoff needs re-derivation. More critically, amplifying negative-ROI
  UNDER signals makes losses worse.
- **flyball_wind_interaction**: PIT proxy (fly_outs ratio) is noisier than season-final FB%.
  Feature ranks 11th/25 by coefficient magnitude. Live operation uses fresh FG data (clean).
  Impact is modest (~2-3% of prediction variance).

### COLLAPSES (1/6)
- **Tier/Threshold/STRONG**: The entire threshold structure was validated on contaminated V1.
  On clean V1, no threshold between p>=0.53 and p>=0.65 produces positive ROI.
  STRONG tier (p>=0.60, edge>=1.0) also fails. The signal edge was illusory.

## Critical Path Forward

1. V1 model itself must be rehabilitated before any downstream object has value
2. F5 Totals threshold needs re-derivation on rehabilitated V1
3. S12 cutoff needs re-derivation (minor, can use live FG xFIP distribution)
4. P09 and F5 Run Line are unblocked — they work independently
5. Tier/Threshold/STRONG structure must be rebuilt from scratch on rehabilitated V1