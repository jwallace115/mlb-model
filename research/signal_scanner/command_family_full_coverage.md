# Command Family — Full Coverage Rerun

Prior coverage: 755 games (16.2%) | New coverage: 3,131 games (67.1%)

corr(P10, P11) = 0.6843

## Full Coverage Results (pooled 2024+2025)

| Signal | N | Pooled ROI | 2024 ROI | 2025 ROI | Perm 2025 | Robust p | S12 indep p |
|--------|---|-----------|----------|----------|-----------|---------|------------|
| P10 whiff×CSW | 659 | +6.9% | +0.2% | +13.4% | 100% | 0.011 | 0.021 |
| P11 combined_whiff | 639 | +8.7% | -1.6% | +19.4% | 100% | 0.0001 | 0.0000 |
| P03 chase_gap | 631 | +2.3% | -3.7% | +8.6% | 90% | 0.71 | 0.76 |
| CMD_IDX composite | 625 | +6.6% | +0.8% | +12.9% | 100% | 0.10 | 0.10 |

## Comparison to Prior (755-game) Results

| Signal | Prior ROI | New ROI | Diff | Verdict |
|--------|----------|---------|------|---------|
| P10 top-20% | +15.0% | +6.9% | -8.1pp | WEAKENS |
| P11 top-20% | +17.3% | +8.7% | -8.6pp | WEAKENS |
| CMD top-20% | +26.0% | +6.6% | -19.4pp | WEAKENS |
| CMD 2025 | +35.2% | +12.9% | -22.3pp | WEAKENS |

## Final Verdicts

| Signal | Verdict | Rationale |
|--------|---------|-----------|
| **P11** combined_whiff | **SHADOW MONITOR 2026** | Strongest individual signal. Survives all controls (p=0.0001). Independent of S12. 2025 holdout +19.4%. But 2024 flat (-1.6%) — needs forward validation. |
| **P10** whiff×CSW | **SHADOW MONITOR 2026** | Survives controls (p=0.011). Independent of S12 (p=0.021). 2025 +13.4%. Same 2024 concern. |
| P03 chase_gap | **SHELVE** | Absorbed by controls (p=0.71). No incremental value over starter quality metrics. |
| COMMAND_INDEX | **SHELVE** | Composite overfit on thin 755-game sample. Does not outperform P11 alone on full data. Corr(CMD, S12) = 0.70 — too dependent. |

## Key Lesson

The initial 755-game Statcast sample (25K pitch cap) was biased toward elite starters, inflating signal effect sizes by ~2x. Full coverage validation is essential before any deployment decision.
