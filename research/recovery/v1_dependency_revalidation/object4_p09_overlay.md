# OBJECT 4: P09 Overlay

## Formula

P09 = avg(home_hard_hit_rate, away_hard_hit_rate) * park_run_factor
Cutoff: P09 <= 31.7305 (bottom 20%)
Amplifies V1 UNDER stakes by 1.25x

## Data Sources

- hard_hit_rate: per-start Statcast with shift(1).rolling() → CLEAN
- park_run_factor: static config → CLEAN
- P09 computation itself: CLEAN

## Contamination Vector

P09's own inputs are clean. However:
- Its 31.7305 cutoff was derived during research using contaminated V1 as baseline
- Its INCREMENTAL VALUE was measured on top of contaminated V1
- The cutoff itself is data-driven (P20 of 2024 distribution) and clean
  since it only depends on hard_hit_rate and park_factor

## Incremental Value on Clean V1

P09 only amplifies UNDER stakes. Same logic as S12:
- If clean V1 UNDER signals are unprofitable, amplifying them is net negative
- The incremental lift was measured as: contaminated_V1+P09 vs contaminated_V1
- On clean V1, the base rate is worse, so P09's incremental value may differ

## Verdict: SURVIVES (inputs clean, but overlay value contingent on V1 base)
- P09 computation: CLEAN (Statcast + static config)
- P09 cutoff (31.7305): CLEAN (derived from clean inputs)
- Incremental value: UNCERTAIN — depends on whether V1 base UNDER signal recovers
- Action: no re-derivation needed for P09 itself; overlay effectiveness
  is tied to V1 signal profitability