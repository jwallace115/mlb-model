# PHASE 6 — Retest Queue Design

**Date:** 2026-04-12

---

## Queue Structure

### Active Retests (require new analysis)

| Object | Clean Test Design | Data Needed | Success Criterion | ETA |
|--------|------------------|-------------|-------------------|-----|
| G1 Over Scanner (standalone) | Remove V1 gate. Test OV043/OV016/OV001 standalone on 2024 (val) + 2025 (OOS) with actual closing over prices. Use only PIT-safe boxscore features. | pitcher_start_adjusted_metrics.parquet, bullpen_usage.parquet, bet_results.parquet | OOS ROI > +3% at -110, stable across seasons | May 2026 |
| F3 F5/FG Path Mismatch | Complete late_implied feature. Build simple threshold or regression on 2024, test on 2025 | f5_lines_historical.parquet, market_snapshots.parquet, game_table.parquet | OOS ROI > +3%, non-trivial N (>200) | May 2026 |

### Passive Accumulation (just wait + log prices)

| Object | Current N | Target N | Current Hit% | Kill Threshold | Review Date |
|--------|-----------|----------|-------------|----------------|-------------|
| C2 ADJ_HH | 34 | 100 | 61.8% | <52% | 2026-05-15 |
| C3 ADJ_K_RATE | 30 | 100 | 56.7% | <52% | 2026-05-15 |
| C5 ADJ_RUN_SUPP | 34 | 100 | 55.9% | <52% | 2026-05-15 |
| C1 ADJ_CONTACT | 65 | 100 | 53.8% | <52% | 2026-05-01 |

### Conditional (wait for trigger)

| Object | Trigger | Action |
|--------|---------|--------|
| D5 CS025 | D3 Signal B ROI drops below +15% | Retest command overlay as precision filter |

---

## Retest Protocol

For each active retest:
1. Document the EXACT test design BEFORE running the analysis
2. Pre-register the success criterion and sample boundaries
3. Use strict temporal splits: train <= 2023, validate = 2024, OOS = 2025
4. Evaluate against actual closing prices, not assumed -110
5. Report permutation test p-values alongside ROI
6. Document all exclusions and data cleaning decisions

For passive accumulation:
1. Add actual closing UNDER price logging to shadow pipeline (one-time fix)
2. At review date, compute ROI at actual prices
3. If hit rate is above kill threshold, compute actual-price ROI
4. If actual-price ROI > +3%, promote to live candidate
5. If hit rate below kill threshold, reclassify as CLEAN KILL
