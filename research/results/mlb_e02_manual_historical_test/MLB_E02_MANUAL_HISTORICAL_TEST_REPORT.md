# MLB E02 — MANUAL HISTORICAL HYPOTHESIS TEST REPORT

**Test Date:** 2026-04-18
**Candidate ID:** MLB_E02
**Candidate Name:** Launch Angle x Wind-Out
**Advancement Type:** MANUAL_FROM_PROVISIONAL_DISCOVERY
**Mechanism Family:** CONTACT-SHAPE x RUN-ENVIRONMENT INTERACTION
**Runtime Object:** MLB_RUNTIME_OBJECT_V1 (19,804 x 130, HISTORICAL_CLEAN)

---

## 1. PURPOSE

This report documents an attempted manual bounded historical hypothesis test for provisional candidate MLB_E02 (Launch Angle x Wind-Out) from MLB Bounded Discovery Pass 02. The test reached a HARD STOP before staged results could be computed.

---

## 2. ENGINE STACK CONFIRMATION

| Element | Status |
|---|---|
| Frozen foundation package | confirmed |
| Orchestration layer | confirmed (default_deny=true) |
| Runtime object | MLB_RUNTIME_OBJECT_V1 — confirmed |
| Outside-package files | **NONE** |

---

## 3. MANUAL ADVANCEMENT STATUS

MLB_E02 was manually advanced from provisional discovery candidate (Bounded Discovery Pass 02). This is not autonomous promotion.

---

## 4. FROZEN TEST DEFINITION

**HARD STOP reached before test could be frozen and executed.**

The candidate requires defining "wind blowing out" from the runtime object's `wind_direction` (degrees) and `wind_speed` (mph) fields. The discovery pass proposed: `wind_direction between 180-360 degrees` as a generic approximation.

However, the prompt's wind-direction semantics rule explicitly states:

> "a generic degree-range approximation without park orientation data is NOT an honest outward-wind definition"

> "if runtime-object weather fields do not support an honest park-specific outward-wind definition, hard stop and report rather than forcing a generic approximation"

---

## 5. FIELD USABILITY CHECK

| Field | Present | Non-null Rate | Usable for E02 |
|---|---|---|---|
| contact_la_last_10 | YES | ~94% | YES (launch angle is interpretable) |
| wind_speed | YES | 100% | YES (wind speed is interpretable) |
| wind_direction | YES | 100% | **NO for honest wind-out definition** |

`wind_direction` provides compass degrees but the runtime object does NOT contain:
- Park center-field bearing
- Park orientation angle
- Any field mapping wind direction to "blowing out" relative to specific park geometry

The park_context_substrate (available in the foundation package but not merged into the runtime object) was checked: it contains park_factor_runs, park_factor_hr, venue fields, and game context — but **no orientation, bearing, or center-field direction field**.

No artifact in the frozen foundation package contains park-specific orientation data. Without this, any definition of "wind blowing out" is a generic degree-range that will:
- Correctly classify wind in parks oriented roughly north-south
- Incorrectly classify wind in parks with non-standard orientations (e.g., AT&T/Oracle Park faces NE, Wrigley faces NE, Fenway faces ENE)
- Create systematic mislabeling that varies by venue

This is not a minor imprecision — it is a structural inability to define the core environmental condition of the candidate.

---

## 6. ANTI-DUPLICATION / MECHANISM CHECK

Anti-duplication was not reached because the candidate cannot be honestly defined with available fields. The wind-out condition — which is the environmental half of the claimed interaction — cannot be constructed without park orientation data that does not exist in the frozen package.

---

## 7. STAGE RESULTS

**No staged results computed.** HARD STOP reached before test execution.

---

## 8. INTERPRETATION

E02's mechanism (high launch angle x wind blowing out) requires knowing which direction "out" is for each specific park. Wind direction in degrees is meaningless without a reference frame. A 200-degree wind is blowing out at Wrigley but blowing in at a differently oriented park.

The frozen foundation package does not contain park orientation data. This is not a threshold-discipline failure (like E01's vacuous park_factor_hr threshold) — it is a **field-availability gap**. The required environmental definition cannot be constructed from available fields.

### Lesson from E01 + E02

Both E-family candidates had environmental components that failed structurally:
- E01: park_factor_hr threshold was vacuous (below field minimum)
- E02: wind-out definition requires data not in the package

This suggests the CONTACT-SHAPE x RUN-ENVIRONMENT interaction family may require richer environmental data (park orientation, wind-relative-to-park fields) than the current foundation package provides. Future work in this family should verify environmental field sufficiency before candidate generation.

---

## 9. FINAL VERDICT

**HARD_STOP**

The test cannot be run honestly under the rules. The runtime object and frozen foundation package do not contain park orientation data required to define "wind blowing out" honestly. A generic degree-range approximation is explicitly forbidden by the test discipline rules. No staged results were computed.

---

## 10. WHAT THIS RESULT DOES NOT CLAIM

- This does not say the LA x wind-out mechanism is wrong in baseball physics — it may be real
- This does not say the mechanism is untestable in principle — it is untestable with the CURRENT frozen package
- This is not deployment approval or profitability proof
- If park orientation data is added to a future foundation package (V2), E02 could be revisited

---

*Report generated: 2026-04-18*
*Engine stack: MLB_ENGINE_V1_FOUNDATION + MLB_RESEARCH_ORCHESTRATION_V1 + MLB_RUNTIME_OBJECT_V1*
