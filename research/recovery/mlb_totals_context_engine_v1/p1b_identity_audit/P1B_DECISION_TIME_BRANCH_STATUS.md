# P1B Decision-Time Branch — Status

**Date:** 2026-04-13  
**Branch:** PAUSED

---

## 1. STATUS

P1B decision-time evaluation is paused. No decision-time variants (DT0700, DT1000, DT1200) are approved or frozen. Current P1B shadow continues unchanged in its coarse pregame form.

## 2. WHAT WAS LEARNED

The P1B identity audit found that decision-time expansion is blocked by temperature-state identity. The current implementation fetches a live Open-Meteo forecast at cron run time (11:20 AM ET). This means:

- Each decision time would receive a forecast with a different lead time (12h at 07:00, 9h at 10:00, 7h at 12:00)
- These are semantically distinct temperature states, making each DT variant a new object
- The intraday decision panel (2022–2025) has no temperature column at all — historical DT-labeled temperature backtests are impossible
- No forecast/archive parity monitor exists to verify forecast accuracy
- Price-side timing also has unresolved alignment between research validation and live deployment

## 3. WHY THE BRANCH IS PAUSED

Repairing this would require building historical decision-time temperature-state infrastructure: fetching or reconstructing game-time weather forecasts as they would have appeared at 07:00 / 10:00 / 12:00 ET for ~9,700 games across 2022–2025. That is a real engineering task with meaningful API cost and validation burden. It is not being prioritized because:

- P1B fires in June–September only and has zero shadow signals yet
- The current coarse shadow is the correct first step — it needs forward evidence before any timing refinement is justified
- Temperature-state reconstruction would be high-effort for a single-object payoff

## 4. WHAT IS NOT BEING DONE NOW

- No DT0700 / DT1000 / DT1200 P1B variants are being created
- No historical temperature backfill is being built
- No forecast parity monitor is being added
- No price-source alignment investigation is being run
- No changes to the current P1B shadow pipeline

## 5. WHAT REMAINS TRUE ABOUT P1B

- P1B passed all 3 splits (discovery, validation, OOS) in its coarse form
- The frozen definition (EARLY_HEAVY, cold park, temp ≥ 75°F, June–Sep, over ≤ −105) is clean
- The shadow pipeline is operational and will begin accumulating signals in June 2026
- Nothing in the identity audit found that P1B is wrong — only that decision-time expansion is not ready

## 6. CONDITIONS THAT WOULD JUSTIFY REOPENING

- Strong forward shadow evidence (e.g., 20+ graded signals with clear directional results) that makes timing comparison economically important
- A broader weather-state infrastructure build driven by other objects or research needs
- A future object family where temperature-state reconstruction becomes high-value across multiple candidates, not just P1B alone

## 7. EXPLICIT STATUS LINE

P1B decision-time expansion is PAUSED. P1B remains SHADOW ONLY in its current frozen form. No decision-time variants are approved or frozen.
