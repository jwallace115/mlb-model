# G13 Weather-Based Revalidation Report

Generated: 2026-03-31T12:39:18

## Methodology
- Weather source: Open-Meteo Archive API (timezone=auto)
- Events fetched: 280 success, 0 failed
- AM window: 07:00-12:00, PM window: 12:00-17:00 local time
- draw_edge = 0.6 * wind_diff + 0.3 * gust_diff
- Wave quintile: frozen G13 cutpoints applied to weather-based draw_edge
- Player-events with weather wave: 34373

## Weather Diagnostics
- Mean AM wind: 12.0 km/h
- Mean PM wind: 14.3 km/h
- R1+R2 rounds with |draw_edge| >= 3: 353/560 (63%)

## Results (OOS 2024-2025)

| Signal | Score ROI | Weather ROI | N | Win Rate | Status |
|--------|-----------|-------------|---|----------|--------|
| G13 standalone MC | +9.2% | +0.0% | 997 | 72.9% | WEAKENS |
| G13xS6(RH) MC | +11.8% | +1.8% | 268 | 72.8% | WEAKENS |
| G13xS6(RH) T20 | +25.3% | +0.7% | 268 | 33.6% | WEAKENS |
| 72H matchup RH | +15.7% | +2.5% | 797 | 53.3% | WEAKENS |

## Permutation Test — G13 Standalone MC
- Observed: +0.0%
- Perm mean: -1.7%, 95th: +0.3%
- p-value: 0.0830

## Permutation Test — Matchup Pick-em RH
- Observed: +2.5%
- Perm mean: -4.3%, 95th: +2.0%
- p-value: 0.0320
