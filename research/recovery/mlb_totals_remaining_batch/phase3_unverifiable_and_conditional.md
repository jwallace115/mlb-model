# Phase 3 — Unverifiable, Conditional, and Deferred Items

**Date:** 2026-04-12

---

## Unverifiable Items (Zero Fires)

### C6 CS013 — CONFIRMED UNVERIFIABLE -> DORMANT
- 158 games logged, 0 fires
- Signal condition is too restrictive for current market conditions
- **Action:** Keep code. Stop active monitoring. If condition EVER fires,
  log it but do not act. Re-evaluate concept only if market structure changes.

### C7 CS028 — CONFIRMED UNVERIFIABLE -> DORMANT
- 135 games logged, 0 fires
- Same pattern as CS013
- **Action:** Keep code. Stop active monitoring.

### C8 KP04 — CONFIRMED UNVERIFIABLE -> DORMANT
- 284 games logged (pitcher-level, so more entries), 0 fires
- kp04_flag = False on ALL 284 entries
- The signal condition (bb_usage x lineup_k_pct threshold) never triggers
- **Action:** Keep code. Stop active monitoring. This is a dead signal.

### C10 Combined Short Exit — CONFIRMED UNVERIFIABLE -> DORMANT
- 158 games logged, 0 fires
- combined_short_exit_favorable_zone = False on all entries
- **Action:** Keep code. Stop active monitoring.

### Summary: All four UNVERIFIABLE items remain at zero fires after 158+ games
(16 days of regular season). These signals are effectively dead code. They
should not consume any review time. Reclassify all four to DORMANT.

---

## CS004 — RETEST REQUIRED -> CONTINUE SHADOW

### Current State
- 158 games logged, 25 fired (15.8% fire rate — reasonable)
- 20 resolved: **12W-8L (60.0% hit rate)**
- Direction: UNDER when cs004_favorable_zone = True

### Assessment
- Fire rate is healthy (unlike CS013/CS028/KP04/CSE which never fire)
- 60.0% hit rate on 20 decisions is above breakeven but N is very small
- No closing under price logged — cannot compute actual ROI
- Combined tail score is the underlying feature (bullpen fatigue metric)

### Verdict: CONTINUE SHADOW
- Review at N=50 resolved (est. early May 2026)
- Kill threshold: hit rate < 52% at review date
- Needs closing under price logging (same fix as ADJ signals)

---

## D5 CS025 F5 RL Overlay — CONDITIONAL -> DEAD

### Prior Condition
CS025 was to be retested "only if D3 (Signal B) shows degradation."

### Current State
D3 (Signal B) is not merely degraded — it is ARCHIVED. The clean PIT-safe
backtest found the original +27.9% ROI was contaminated; actual ROI is -6.2%.
Signal B no longer generates any signals.

CS025 is an overlay ON TOP OF Signal B. With the parent signal dead, the
overlay has no host to attach to.

### Verdict: DEAD (reclassify to ARCHIVE)
No further work possible or warranted.

---

## D6 F5 Standalone — DEFERRED -> REMAINS DEFERRED

### State
The F5 standalone totals model was never built. The reset audit classified it
as DEFERRED. The planned approach was to use the same Ridge architecture as
the full-game V1 model but with F5_WEIGHTS and 5-inning target.

### Assessment
Given that:
1. V1 Ridge (full-game) is a CLEAN KILL at -13.2% OOS
2. F5 totals under/over engines are VOID (V1 contamination)
3. Signal B (F5 run line) is ARCHIVED
4. F5/FG path mismatch is a NEAR MISS (not exploitable)
5. No F5-specific features have shown standalone edge

There is no evidence basis to justify building an F5 totals model. The
architecture that would underlie it (Ridge on pitcher/offense features)
has been proven unprofitable for full-game totals.

### Verdict: ARCHIVE
Reclassify from DEFERRED to ARCHIVE. Do not build without new research
basis that demonstrates F5-specific edge independent of the V1 framework.
