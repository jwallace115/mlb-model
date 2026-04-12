# Phase 4 — Next-Action Board

**Date:** 2026-04-12

---

## Active Monitoring (items that need future review dates)

| ID | Object | Current Hit% | N Resolved | Next Review | Kill Threshold | Action at Review |
|----|--------|-------------|------------|-------------|----------------|-----------------|
| C2 | ADJ_HH | 63.6% | 33 | N=50 (~late Apr) | <52% | If above: add price logging, continue. If below: KILL |
| C3 | adj_k_rate | 60.7% | 28 | N=50 (~late Apr) | <52% | Same |
| C5 | ADJ_RUN_SUPP | 59.4% | 32 | N=50 (~late Apr) | <52% | Same |
| C1 | ADJ_CONTACT | 55.6% | 63 | N=100 (~early May) | <52% | Same |
| C9 | CS004 | 60.0% | 20 | N=50 (~early May) | <52% | Same |

## Prerequisite Fix (Before Next Review)

**Add closing under price logging to shadow tracker.**
- File: mlb_sim/pipeline/shadow_signals.py
- The shadow tracker logs favorable_zone_flag and result but NOT the closing
  under price from The Odds API
- Without this, ROI at actual prices cannot be computed
- This is a one-time operational fix, not a research task
- Priority: HIGH (blocks all ROI evaluation at next review)

## Permanently Resolved (No Further Action)

| ID | Object | Final Verdict | Reason |
|----|--------|--------------|--------|
| G1 | Over Scanner | CLEAN KILL | 0/8 signals survived standalone retest |
| D3 | Signal B Home | ARCHIVED | -6.2% ROI after decontamination |
| D4 | Signal B Away | CLEAN KILL | -3.5% OOS |
| C4 | ADJ_BB_RATE | CLEAN KILL | 50.0% backtest + 50.0% shadow |
| F3 | F5/FG Path Mismatch | ARCHIVE | Real effect but not exploitable after vig |
| D5 | CS025 F5 RL Overlay | ARCHIVE | Parent signal (D3) dead |
| D6 | F5 Standalone | ARCHIVE | No evidence basis to build |
| C6 | CS013 | DORMANT | 0 fires in 158 games |
| C7 | CS028 | DORMANT | 0 fires in 135 games |
| C8 | KP04 | DORMANT | 0 fires in 284 games |
| C10 | Combined Short Exit | DORMANT | 0 fires in 158 games |

## Summary Counts

| Category | Count |
|----------|-------|
| Active monitoring | 5 |
| Permanently resolved | 11 |
| Prerequisite fix needed | 1 |
| **Total objects on board** | **16** |
