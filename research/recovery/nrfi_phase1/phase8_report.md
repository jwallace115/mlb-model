# Phase 8: Top-3 Selection Framework

## Objective: Identify the best daily NRFI legs for parlay construction

### Signal hierarchy (from existing micro-model research):
1. **Combined p_yrfi rank** — bottom 10% of slate = strongest NRFI signal
2. **Full-game closing total** — lower total = higher NRFI rate
3. **F5 closing total** — provides independent validation
4. **Dome games** — slightly higher NRFI rate (controlled environment)
5. **Starter archetype** — CONTACT_RISK exclusion from Phase 8 overlay
6. **Top-3 lineup stability** — both-changed exclusion from Phase 11

### Filter value quantification:

### Recommended selection criteria for top-3 NRFI legs:
1. Closing total <= 8.5 (strong prior)
2. F5 total <= 5.0 (confirms starter quality)
3. Micro-model p_yrfi in bottom 10% of slate
4. NOT CONTACT_RISK archetype starter at home
5. Top-3 lineup stable (not both changed)
6. Dome or mild temperature preferred (avoid extreme heat)