# Phase 4 — Identity Check

## Three Distinct Objects

### Object A: V1-Interaction Signal (Original Research)
- Gate: V1 p_under > 0.57 AND metric in favorable zone
- N per signal: 53-131 (2024-2025)
- Performance: ROI +14.4pp to +27.1pp lift over V1 baseline
- Status: Never implemented in live code

### Object B: Standalone Signal (Standalone Rebuild)
- Gate: combined > 0 (no V1 requirement)
- N per signal: 1539-3875 (2022-2025)
- Performance: All DIMINISHED (pooled ROI -0.6% to -3.6%)
- 2025 OOS: ADJ_HH +5.6%, adj_k_rate +4.1% (showing late improvement)
- Status: This is what the live code implements

### Object C: Live Shadow (2026)
- Gate: combined > 0 (same as Object B)
- Feature source: FROZEN at end-of-2025 (not updating with 2026 starts)
- V1 context: always "NONE" (not passed through)
- Status: Currently logging to shadow_signals_2026.json

## Identity Mismatch Summary

| Dimension | Research (A) | Standalone (B) | Live (C) |
|-----------|-------------|----------------|----------|
| V1 gate | YES (p_under>0.57) | NO | NO |
| Feature freshness | Historical rolling | Historical rolling | Frozen 2025 |
| N per year | ~50-130 | ~400-1000 | ~16-92 (partial season) |
| Backtest ROI | +14% to +33% | -3.6% to -0.6% | N/A (shadow only) |
| V1 context logged | N/A | N/A | Always "NONE" |

## Key Finding
The live shadow code (Object C) is testing Object B (standalone), NOT Object A
(V1-interaction). The research that showed strong results was Object A. The
standalone rebuild already showed Object B is DIMINISHED.

The early 2026 shadow results (ADJ_HH 63.6% on 33 resolved) are consistent
with the 2025 OOS standalone results (ADJ_HH 55.4%) showing late improvement,
but the sample is too small (N=33) and the feature source is frozen.
