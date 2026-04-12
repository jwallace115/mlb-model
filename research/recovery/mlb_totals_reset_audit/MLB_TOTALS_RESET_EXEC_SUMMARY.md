# MLB TOTALS RESET AUDIT — Executive Summary

**Date:** 2026-04-12
**Auditor:** Forensic triage of all prior MLB totals ideas
**Scope:** 41 distinct objects/ideas inventoried across core models, overlays, shadow signals,
F5 derivatives, team totals, market structure research, over-side research, distribution/shape
work, and signal discovery infrastructure

---

## Bottom Line

**Of 41 MLB totals ideas inventoried, exactly ONE has clean positive evidence: F5 Run Line
Signal B (home side).** Everything else is either dead (CLEAN KILL), contaminated (VOID),
untestable (UNVERIFIABLE), addressing the wrong market (WRONG MARKET FRAME), or awaiting
sufficient data (RETEST REQUIRED).

The primary contamination — end-of-season FanGraphs feature lookahead in the V1 Ridge
training pipeline — invalidated the core totals model and cascaded downstream to corrupt
the F5 totals engine, team totals coefficients, and multiple overlay thresholds. The
clean V1 rebuild confirmed the damage: ROI = -13.2% OOS. The V1 architecture with
current features does not beat the totals market.

---

## Classification Counts

| Classification | Count | Objects |
|---------------|-------|---------|
| CLEAN KILL | 9 | V1 PIT rebuild, V2 engine, S12, P09, ST02, ADJ_BB_RATE, F5 RL away, run-line asymmetry, TT away over |
| VOID / CONTAMINATED | 4 | F5 under engine, F5 over engine, TT home under, TT away under |
| REBUILD REQUIRED | 1 | V1 Ridge (contaminated weights) |
| RETEST REQUIRED | 7 | ADJ_HH, ADJ_K_RATE, ADJ_RUN_SUPP, ADJ_CONTACT, Over Scanner, F5/FG path mismatch, CS004 |
| WRONG MARKET FRAME | 2 | Alt-total surface, NRFI selector |
| UNVERIFIABLE | 4 | CS013, CS028, KP04, Combined Short Exit |
| ARCHIVE | 9 | V1 rules mode, flyball_wind, cross-market triangle, V2 over bias, distribution shape, NRFI (kept frozen), props, canonical board, engines 1-6 |
| CLEAN (KEEP) | 1 | F5 Run Line Signal B (home) |
| CONDITIONAL | 1 | CS025 F5 RL command overlay |
| DEFERRED | 1 | F5 standalone (not built) |
| **TOTAL** | **39** | (2 objects double-counted under TT) |

---

## Eight Known Failure Modes

1. **End-of-season FG lookahead** — 14/25 V1 features. Root cause of cascade.
2. **Research/live identity mismatch** — Team Totals had 3 non-equivalent versions.
3. **Discovery-validation leakage** — Over Scanner promoted on same data used for discovery.
4. **Within-sample median classification** — S12/P09/KP04 cutoffs are quantile artifacts.
5. **PGL proxy failure** — KP04 Statcast thresholds don't transfer to PGL.
6. **Degraded-mode overfiring** — Team Totals fires on 93.8% of games.
7. **Stale priors** — V1 sigma=4.361 from contaminated training.
8. **Parent dependency** — F5 engines parasitic on dead V1.

---

## What Survives

### Confirmed Profitable (1 object)
- **F5 Run Line Signal B (home):** +27.9% pooled ROI (N=335), stable 2024/2025, 0 red flags, PIT-safe, independent

### Promising but Unproven (4 objects, passive accumulation)
- **ADJ_HH:** 61.8% hit rate (N=34) — best early shadow performer, needs N=100
- **ADJ_K_RATE:** 56.7% (N=30) — needs N=100
- **ADJ_RUN_SUPP:** 55.9% (N=34) — needs N=100
- **ADJ_CONTACT:** 53.8% (N=65) — marginal, may be killed at N=100

### Requires Active Retest (2 objects)
- **Over Scanner (standalone):** Must remove contaminated V1 interaction gate and retest
- **F5/FG Path Mismatch:** Research in progress, clean data

---

## Immediate Actions

1. **Log real closing prices** for all surviving shadow signals (ADJ series). Without
   prices, nothing can ever be promoted.
2. **Do NOT rebuild V1 Ridge.** The clean rebuild (A2) proved the architecture is dead.
   Rebuilding with clean data will produce another negative-ROI model.
3. **Protect F5 Run Line Signal B.** It is the only confirmed profitable MLB object.
   Monitor live shadow closely. Do not add overlays unless Signal B degrades.
4. **Run standalone Over Scanner retest** (OV043, OV016, OV001 without V1 gate).
   This is the highest-potential new research track.
5. **Disable shadow logging** for all 5 KILLED objects (S12, P09, ST02, F5 totals, TT)
   to reduce pipeline noise.

---

## Strategic Assessment

The MLB totals market is the most efficient of the markets this system covers. The
V1 contamination masked this reality for months — the apparent +6.5% in-sample /
+2.3% STRONG-tier OOS edge was almost entirely driven by lookahead. Clean testing
reveals the market prices pitcher quality, park factors, weather, and bullpen state
correctly within the vig.

The surviving edge (F5 RL) exploits a specific structural asymmetry: the market
under-prices home starter dominance in the F5 run-line derivative. This is a
niche market with moderate liquidity. It cannot be the foundation of a full totals
betting operation.

The OVER side of the market is the least-explored territory. The Over Scanner
identified real standalone patterns (OV016 +4.3%, OV043 interaction effects) but
these were tested with contaminated V1 gates. A clean standalone retest is the
single highest-priority research task for MLB totals going forward.

---

## Review Schedule

| Date | Action |
|------|--------|
| 2026-04-14 | Disable shadow logging for 5 KILLED objects |
| 2026-05-01 | ADJ_CONTACT N=100 review |
| 2026-05-15 | ADJ_HH, ADJ_K_RATE, ADJ_RUN_SUPP N=100 review |
| 2026-05-31 | Over Scanner standalone retest complete |
| 2026-06-15 | Full mid-season triage refresh |
