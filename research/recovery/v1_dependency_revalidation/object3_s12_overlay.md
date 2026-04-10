# OBJECT 3: S12 Overlay

## Formula

S12 = avg(home_csw, away_csw) - 5 * avg(home_xfip, away_xfip)
Cutoff: S12 >= 8.4468 (P80 of 2024 season-final distribution)
Used to amplify V1 UNDER stakes by 1.25x

## Contamination

- CSW: per-start rolling (CLEAN)
- xFIP: season-final FanGraphs (CONTAMINATED in research)
- The 8.4468 cutoff was derived from contaminated xFIP distribution
- In live operation, xFIP comes fresh from FG API (clean)

## PIT FIP S12 Recomputation

sim_inputs CSW columns: ['sp_csw_pct']
  sp_csw_pct: mean=27.14, std=3.37

Phase A statcast files: []

## Analytical Assessment

Since we cannot directly recompute S12 with matched CSW+PIT_FIP per game,
we note the structural impact:
- PIT FIP is noisier than season-final xFIP (expanding mean vs full-season mean)
- S12 = avg_csw - 5 * avg_fip_pit would have HIGHER VARIANCE
- The P80 cutoff of 8.4468 was derived from LOW-VARIANCE season-final xFIP
- With PIT FIP, the distribution would be wider, shifting the P80 cutoff
- However: in LIVE operation, xFIP comes from current FG API (similar to season-final)
- The cutoff contamination affects only the RESEARCH VALIDATION, not live firing

## Impact on Clean V1 Baseline

S12 overlay amplifies stake from 1.0u to 1.25u on qualifying UNDER signals.
Since clean V1 UNDER signals at p>=0.57 show negative ROI (see Object 6),
amplifying losing bets by 1.25x INCREASES losses.
S12 overlay value is only positive if the base UNDER signal is profitable.

## Verdict: DIMINISHED
- Live firing: CLEAN (uses fresh FG xFIP)
- Cutoff derivation: CONTAMINATED (8.4468 from season-final xFIP)
- Overlay value: NEGATIVE when clean V1 base UNDER signals are unprofitable
- Action: cutoff needs re-derivation; overlay value depends on V1 rehabilitation