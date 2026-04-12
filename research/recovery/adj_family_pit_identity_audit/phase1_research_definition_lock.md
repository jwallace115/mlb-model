# Phase 1 — Research Definition Lock

## Original Research (V2 Signal Scanner)

Source: `research/opponent_adjusted_engine_v2/scanner/v2_signal_scan_report.md`

The original V2 research tested ADJ signals in TWO modes:

### Part A — Standalone
Signals tested alone with no V1 gate. Best standalone results:
- adj_k_rate: top_10, N=424, Under%=56.8%, ROI=+8.5% (but PRICED, mkt corr -0.331)
- ADJ_CONTACT: top_10, N=426, Under%=56.6%, ROI=+8.0% (PARTIAL corr -0.220)
- ADJ_RUN_SUPP: top_10, N=425, Under%=53.4%, ROI=+2.0% (PARTIAL corr -0.257)
- ADJ_HH: top_10, N=411, Under%=52.1%, ROI=-0.6% (standalone FLAT)
- ADJ_BB_RATE: top_20, N=861, Under%=53.7%, ROI=+2.4%

### Part B — V1 Interaction (p_under > 0.57 gate)
When filtered to games where V1 already predicts UNDER, all signals showed large lifts:
- ADJ_BB_RATE: N=60, Under%=70.0%, ROI=+33.6% (+27.1pp lift over V1 baseline)
- ADJ_HH: N=109, Under%=66.1%, ROI=+26.1% (+19.6pp lift)
- ADJ_CONTACT: N=131, Under%=63.4%, ROI=+21.0% (+14.4pp lift)
- ADJ_RUN_SUPP: N=96, Under%=63.5%, ROI=+21.3% (+14.8pp lift)

### Critical Distinction
The V1 interaction mode required p_under > 0.57 as a prerequisite. This dramatically
reduced sample sizes (N=53-131 vs N=400-860) but produced much stronger precision.
The standalone mode showed modest to flat results.

## Standalone Rebuild (2022-2025)

Source: `research/recovery/adj_standalone_rebuild/ADJ_MASTER_KEEP_KILL_MEMO.md`

Tested the STANDALONE version (combined > 0, no V1 gate) across 2022-2025:

| Signal | N | Hit% | ROI | 2025 OOS |
|--------|---|------|-----|----------|
| ADJ_CONTACT | 3875 | 51.2% | -2.4% | +0.4% |
| ADJ_HH | 3081 | 51.1% | -2.6% | +5.6% |
| adj_k_rate | 1539 | 52.1% | -0.6% | +4.1% |
| ADJ_BB_RATE | 1587 | 50.6% | -3.6% | -1.8% |
| ADJ_RUN_SUPP | 3159 | 51.5% | -1.8% | +1.8% |

All five classified as DIMINISHED. However, 2025 OOS showed improvement
(especially ADJ_HH at +5.6% and adj_k_rate at +4.1%).
