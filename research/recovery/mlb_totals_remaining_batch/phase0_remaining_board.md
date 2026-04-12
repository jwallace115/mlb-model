# Phase 0 — Remaining Board Lock

**Date:** 2026-04-12

---

## Scope

This batch pass covers ALL MLB totals objects with classification RETEST REQUIRED,
UNVERIFIABLE, CONDITIONAL, or DEFERRED from the 2026-04-12 reset audit. The purpose
is to produce a final updated verdict for each, incorporating:
1. Completed retests (Over Scanner, Signal B clean backtest, Signal B archive)
2. Ongoing 2026 shadow accumulation (ADJ signals, CS004)
3. Research already completed (F5/FG path mismatch)
4. Items that remain stuck at zero fires

---

## Objects on Remaining Board

| ID | Object | Prior Classification | Status Today |
|----|--------|---------------------|--------------|
| C1 | ADJ_CONTACT | RETEST REQUIRED | Shadow accumulating (65 resolved) |
| C2 | ADJ_HH | RETEST REQUIRED | Shadow accumulating (34 resolved) |
| C3 | ADJ_K_RATE | RETEST REQUIRED | Shadow accumulating (30 resolved) |
| C5 | ADJ_RUN_SUPP | RETEST REQUIRED | Shadow accumulating (34 resolved) |
| C6 | CS013 | UNVERIFIABLE | Still 0 fires in 158 games |
| C7 | CS028 | UNVERIFIABLE | Still 0 fires in 135 games |
| C8 | KP04 | UNVERIFIABLE | Still 0 fires in 284 games |
| C9 | CS004 | RETEST REQUIRED | Shadow accumulating (20 resolved fired) |
| C10 | Combined Short Exit | UNVERIFIABLE | Still 0 fires in 158 games |
| D3 | F5 RL Signal B Home | Was CLEAN (KEEP) | Now ARCHIVED (clean backtest killed it) |
| D5 | CS025 F5 RL Overlay | CONDITIONAL | Dead (parent D3 archived) |
| D6 | F5 Standalone | DEFERRED | Still not built |
| F3 | F5/FG Path Mismatch | RETEST REQUIRED | Research complete (NEAR MISS) |
| G1 | Over Scanner | RETEST REQUIRED | Retest complete (CLEAN KILL) |

---

## Objects Already Resolved in Prior Batches

| ID | Object | Prior Class | Resolved To | Resolution Batch |
|----|--------|-------------|-------------|-----------------|
| G1 | Over Scanner Wave 1 | RETEST REQUIRED | CLEAN KILL | over_scanner_standalone_retest |
| D3 | F5 RL Signal B Home | CLEAN (KEEP) | ARCHIVED | signal_b_clean_backtest + signal_b_archive |
| D4 | F5 RL Signal B Away | CLEAN KILL | CLEAN KILL | (already closed) |
| C4 | ADJ_BB_RATE | CLEAN KILL | CLEAN KILL | (already closed) |
