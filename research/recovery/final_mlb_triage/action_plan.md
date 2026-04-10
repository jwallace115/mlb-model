# Final Triage Action Plan

Date: 2026-04-10

---

## Immediate Actions (This Week)

### 1. KEEP — Activate for Daily Review
- **F5 Run Line (Signal B)**: Continue shadow logging. Begin tracking actual F5 RL prices.
  When 50+ resolved signals accumulate, evaluate ROI at actual prices for promotion to live.

### 2. SHADOW-CONTINUE — Keep Running, Review at N=100
- **ADJ_HH**: Best performer (61.8%, N=34). Priority monitor. Review at N=100 resolved.
- **ADJ_K_RATE**: Strong (56.7%, N=30). Review at N=100.
- **ADJ_RUN_SUPP**: Promising (55.9%, N=34). Review at N=100.
- **ADJ_CONTACT**: Moderate (53.8%, N=65). Approaching review threshold. May downgrade if flat at N=100.
- All four: begin logging actual closing prices (UNDER at -110 minimum) alongside shadow flags.

### 3. KILL — Disable Shadow Logging
- **S12 Overlay**: Remove from daily pipeline. Negative in-sample at every threshold. Dead.
- **P09 Overlay**: Remove from daily pipeline. OOS collapse confirmed. Dead.
- **ST02 Overlay**: Remove from daily pipeline. V1-dependent, zero fires, no standalone path.
- **F5 Totals Engine**: Remove from daily pipeline. Fully dependent on contaminated V1.
- **Team Totals (Home + Away)**: Remove from daily pipeline. Identity NEVER-MATCHED. Dead.

### 4. FREEZE — Keep Code, Stop Daily Review
- CS013, CS028, KP04: Keep shadow logging active (low cost) but remove from daily attention.
  Review only at end of April if any fires accumulate.
- ADJ_BB_RATE: Keep logging but do not pursue. 50% = noise.
- V2 Engine, flyball_wind discrete, Combined Short Exit: Retain for reference. No action.

---

## Economics Gap (Critical)

The single biggest gap across all surviving objects is **no actual prices logged**.
Every surviving signal assumes flat -110. This must be fixed:

1. For F5 Run Line: capture actual RL prices from Odds API at signal fire time
2. For ADJ signals: capture actual UNDER closing line at game resolution time
3. Without real prices, no object can ever be promoted to live betting

---

## Review Schedule

| Date | Action |
|------|--------|
| 2026-04-14 | Disable shadow logging for 5 KILL objects |
| 2026-04-30 | Check FREEZE objects for any accumulated fires |
| 2026-05-10 | ADJ signals N=100 review (if pace holds) |
| 2026-05-31 | F5 Run Line N=50 review |
| 2026-06-15 | Full mid-season triage refresh |

---

## Top 3 KEEP / Top 3 RETIRE

### Top 3 to Keep (ordered by evidence strength)
1. **F5 Run Line** — Only object with 0 red flags. Independent, PIT-safe, directionally confirmed.
2. **ADJ_HH** — 61.8% hit rate in early shadow (N=34). PIT-safe. Independent in live code.
3. **ADJ_K_RATE** — 56.7% hit rate (N=30). Clean pipeline. Needs sample size.

### Top 3 to Retire (ordered by contamination severity)
1. **Team Totals** — Identity NEVER-MATCHED. 5/5 flags. Three different objects, none equivalent.
2. **F5 Totals Engine** — 85% signal collapse with clean V1. Fully parasitic on dead parent.
3. **S12 Overlay** — Negative in-sample at every threshold tested. Amplifies losing bets.
