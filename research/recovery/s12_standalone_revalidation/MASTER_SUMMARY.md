# S12 Standalone Revalidation — Master Summary

## What is S12?
S12 = avg(home_csw, away_csw) - 5 * avg(home_xfip, away_xfip)

High S12 = both starters have elite pitch quality (high CSW) relative to their
run-prevention (xFIP). The original hypothesis: when S12 >= 8.4468 (top-20%),
the game environment strongly suppresses scoring -> bet UNDER.

## PIT Safety Assessment
- **CSW**: PIT-safe. Built from per-start Statcast data with shift(1) rolling-5.
  Each game uses only prior starts. Source: `research/mlb_phase_a/pitcher_start_metrics_per_start.csv`
- **xFIP**: PIT-safe. Using `v1_clean_features/baseball_features_pit_v1.parquet`
  which was independently rebuilt with proper shift(1) rolling.
- **Contamination delta**: 0.0pp (PIT-safe vs full dataset identical because all
  9,040 games have PIT-safe xFIP available)
- **Verdict**: S12 can be cleanly constructed. No contamination present.

## Data Coverage
- 9,040 games with complete CSW + xFIP + actuals (2022-2025)
- 8,169 games with closing lines
- S12 fires (>= 8.4468) on ~32% of games

## Phase 3: Old Rule Test (cutoff 8.4468)
| Season | N    | WR    | ROI    |
|--------|------|-------|--------|
| 2022   | 518  | 53.3% | +1.7%  |
| 2023   | 656  | 51.1% | -2.5%  |
| 2024   | 704  | 49.3% | -6.2%  |
| 2025   | 718  | 54.6% | +4.3%  |
| ALL    | 2596 | 52.0% | -0.8%  |

- Alternating seasons: positive 2022, negative 2023-2024, positive 2025
- Overall negative ROI (-0.8%) at the old cutoff

## Phase 4: Threshold Ladder (train 2022-2024, OOS 2025)
Key finding: **every threshold is negative in-sample** (2022-2024), but several
are positive OOS (2025). This is suspicious — the signal appears to be noise
that happens to align with 2025.

Best thresholds in-sample: 11.0 (+0.7% train, +6.6% OOS, N=273 OOS)
Best threshold OOS (N>=20): 13.5 (+7.2%, N=80) — but only 80 games, unreliable.

The 8.5-9.0 range shows: -2.7% to -3.8% train, +4.7% to +5.2% OOS (N=594-706).
This OOS performance could be 2025-specific rather than a durable edge.

## Phase 5: Stability
- **Season stability**: 2/4 seasons positive. Not stable.
- **Total-band**: S12 performs best on HIGHER totals (9.5+: +5.9%), worst on LOW
  totals (under 7.5: -3.2%). This is counterintuitive for an under signal.
- **Price dependence**: Best at neutral prices (-105 to -95: +5.4%), worst when
  the market agrees with over (-95+: -7.4%) or disagrees strongly (<-115: -0.9%).

## Phase 6: Baseline Comparison
| Strategy                | N     | WR    | ROI    |
|-------------------------|-------|-------|--------|
| Blind UNDER all         | 7831  | 51.1% | -2.5%  |
| Blind UNDER total<=8.0  | 3337  | 50.9% | -2.7%  |
| Blind UNDER mkt fav     | 989   | 52.2% | -4.6%  |
| **S12 >= 8.4468**       | 2596  | 52.0% | -0.8%  |
| S12 + close<=8.5        | 2168  | 51.2% | -2.2%  |
| S12 + close>8.5         | 428   | 55.8% | +6.3%  |

- S12 is +1.8pp better than blind under — marginal
- S12 at HIGH totals (>8.5) shows +6.3% ROI but only 428 bets
- S12 at LOW totals (<=8.5) is -2.2%, worse than blind under on same games

## Phase 7: Verdict

**VERDICT: DIMINISHED**

### Evidence Against S12 as Standalone Signal
1. Overall ROI is negative (-0.8%) at the original cutoff
2. In-sample (2022-2024) is negative at EVERY threshold tested
3. Only 2/4 seasons are positive
4. The signal is NOT additive on low totals where under bets concentrate
5. OOS (2025) performance may be year-specific noise

### One Interesting Finding
S12 at high totals (>8.5) shows +6.3% ROI. This suggests S12 may have value
as a *contra-market* signal: when the market sets a high total but both
pitchers have elite pitch quality relative to their xFIP, the market is
over-estimating scoring. However, N=428 over 4 seasons is thin.

### Recommendation
- S12 does NOT survive as a standalone under signal
- It should NOT be used as a blind trigger
- The high-total subset (>8.5) warrants monitoring as a possible overlay
  condition, but the sample is too small to deploy with confidence
- The +1.8pp edge vs blind under is within noise given the season instability
