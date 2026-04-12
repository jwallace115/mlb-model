# Phase 0: Claims Under Audit

**Date:** 2026-04-12
**Object:** Signal B (F5 Run Line Home — xFIP mismatch)

---

## Three Claims

### Claim 1: The correct threshold is 1.5, not 1.0
The reset audit (2026-04-11) directed the threshold change from 1.0 to 1.5.
This audit traces the full provenance chain: where 1.0 came from, where 1.5
came from, and which is supported by PIT-clean evidence.

### Claim 2: The live pipeline is PIT-safe for daily operation
Signal B's xFIP source in daily production is FanGraphs API via
get_pitcher_metrics(). This claim states that live operation has zero
lookahead contamination regardless of threshold.

### Claim 3: The historical backtest ROI (+27.9%) is inflated
The original research (f5_runline_research_report.md) used sim_inputs
parquet files built from the feature_table, which contains season-final
FanGraphs xFIP. If the xFIP values are static per pitcher per season,
the reported backtest ROI is contaminated with end-of-season lookahead.

---

**Method:** Trace every artifact that mentions the threshold, inspect data
sources for lookahead, examine 2026 live signals for xFIP source lineage.
