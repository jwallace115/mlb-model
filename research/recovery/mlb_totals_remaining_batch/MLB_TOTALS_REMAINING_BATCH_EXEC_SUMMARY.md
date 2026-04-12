# MLB Totals Remaining Board — Batch Pass Executive Summary

**Date:** 2026-04-12
**Scope:** All 15 MLB totals objects with open/pending classifications from the reset audit

---

## Bottom Line

Of 15 remaining objects, **5 stay in active shadow monitoring** and **10 are permanently
closed.** No new research is needed. The only action is to wait for shadow accumulation
and add closing-price logging before the next review.

**ADJ_HH is the single best remaining MLB totals candidate** — 63.6% hit rate on 33
resolved 2026 shadow decisions, backed by a 2025 OOS backtest showing +5.6% ROI. Review
at N=50 (est. late April 2026).

---

## Classification Updates

| Category | Count | Objects |
|----------|-------|---------|
| CONTINUE SHADOW | 5 | ADJ_HH, adj_k_rate, ADJ_RUN_SUPP, ADJ_CONTACT, CS004 |
| ARCHIVE | 4 | F5/FG Path Mismatch, CS025, F5 Standalone, Signal B Home |
| CONFIRMED KILL | 2 | ADJ_BB_RATE, Over Scanner |
| DORMANT | 4 | CS013, CS028, KP04, Combined Short Exit |

### Reclassifications Made in This Batch

| Object | From | To | Reason |
|--------|------|----|--------|
| F3 F5/FG Path Mismatch | RETEST REQUIRED | ARCHIVE | Research complete; real effect but +2.5% ROI at -110 is not exploitable after realistic vig |
| D5 CS025 F5 RL Overlay | CONDITIONAL | ARCHIVE | Parent signal (Signal B) is ARCHIVED; overlay has no host |
| D6 F5 Standalone | DEFERRED | ARCHIVE | No evidence basis; V1 Ridge architecture proven unprofitable |
| D3 Signal B Home | CLEAN (KEEP) | ARCHIVED | Clean PIT-safe backtest: -6.2% ROI (was +27.9% before decontamination) |
| G1 Over Scanner | RETEST REQUIRED | CLEAN KILL | 0/8 signals survived standalone retest |
| C6/C7/C8/C10 | UNVERIFIABLE | DORMANT | Still 0 fires after 135-284 games; dead code |

---

## Active Monitoring Board (ranked by priority)

| Rank | Object | 2026 Hit% | N Resolved | 2025 Backtest | Next Review |
|------|--------|----------|------------|---------------|-------------|
| 1 | ADJ_HH | 63.6% | 33 | +5.6% | N=50 (late Apr) |
| 2 | adj_k_rate | 60.7% | 28 | +4.1% | N=50 (late Apr) |
| 3 | CS004 | 60.0% | 20 | n/a | N=50 (early May) |
| 4 | ADJ_RUN_SUPP | 59.4% | 32 | +1.8% | N=50 (late Apr) |
| 5 | ADJ_CONTACT | 55.6% | 63 | +0.4% | N=100 (early May) |

Kill threshold for all: hit rate < 52% at review date.

---

## Critical Prerequisite

**Closing under price logging is NOT implemented in the shadow tracker.**

The shadow_signals.py tracker logs favorable_zone_flag and game result but NOT
the actual closing under price from The Odds API. Without this, ROI at actual
prices cannot be computed at the next review. This is a one-time operational
fix that must be done before the N=50 review date.

---

## Key Findings

### F5/FG Path Mismatch (F3)
The research is thorough and complete. The F5 market does underadjust for game
quality (71% of F5 lines are exactly 4.5 regardless of FG total). The HIGH_EARLY_INFLATION
F5 UNDER signal shows 53.7% hit rate, but this is only +2.5% ROI at -110 — not
exploitable after realistic juice. No full-game totals application exists.

### ADJ Identity Consistency
The live shadow implementation (combined > 0, no V1 gate) is identical to the
standalone rebuild backtest. There is no identity mismatch. The 2026 shadow
results are measuring the same object that was backtested.

### ADJ 2026 Shadow Results
All four surviving ADJ signals show hit rates above the 52.4% breakeven at -110.
ADJ_HH is the standout at 63.6% on 33 decisions. The pattern of 2025 backtest
improvement continuing into 2026 live data is encouraging but sample sizes
remain too small for commitment.

### Zero-Fire Signals
CS013, CS028, KP04, and Combined Short Exit have accumulated 0 fires across
135-284 games each. These signals are effectively dead and should not consume
review time.

---

## Recommendations

1. **Do nothing new.** All remaining MLB totals edge candidates are in shadow
   accumulation. No new research, no new code, no new signals.

2. **Add closing under price logging** to shadow_signals.py before late April.

3. **Review ADJ_HH at N=50** (~April 20-22). This is the single highest-value
   checkpoint in the MLB totals universe.

4. **Redirect research time** to other sports/markets. The MLB totals universe
   has been fully audited. The only remaining value is passive data accumulation.

---

## Files Created

| File | Contents |
|------|----------|
| phase0_remaining_board.md | Board lock: all 15 objects inventoried |
| phase1_f5fg_path_mismatch_verdict.md | F5/FG path mismatch: ARCHIVE |
| phase2_adj_identity_audit.md | ADJ signal identity + 2026 shadow state |
| phase3_unverifiable_and_conditional.md | Zero-fire signals + D5/D6 closure |
| phase4_next_action_board.md | Next-action board with review dates |
| phase5_best_next_target.md | Priority ranking of active objects |
| remaining_board_table.csv | Machine-readable classification table |
| MLB_TOTALS_REMAINING_BATCH_EXEC_SUMMARY.md | This file |
