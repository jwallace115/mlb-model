# Red-Flag Checklist — All 19 MLB Objects

Date: 2026-04-10

## Checklist Criteria

For each object, five questions determine keep/kill:
1. **Identity match**: Is the live object the same as what was researched?
2. **PIT safety**: Are all inputs point-in-time clean?
3. **Parent dependency**: Does it depend on a contaminated/dead parent?
4. **Economics**: Are actual prices available for evaluation?
5. **Evidence**: What is the best clean evidence of value?

---

## 1. F5 Run Line (Signal B)

| Check | Result |
|-------|--------|
| Identity | MATCH — live code uses same xFIP gap >= 1.0 threshold as research |
| PIT safe | YES — uses live FanGraphs API xFIP (daily-fresh, not season-final) |
| Parent dep | NONE — fully independent of V1; does not consume V1 probabilities |
| Economics | YES — F5 run line prices logged in shadow; actual RL lines available |
| Evidence | PIT FIP gap>=1.0: 53.1% under rate 2025, 50.3% 2024. Gap>=1.5: 59.4%/60.0% |

**Flags raised: 0/5**
Shadow 2026: 7 entries, 0 fired yet (early season, low frequency expected)

---

## 2. ADJ_CONTACT

| Check | Result |
|-------|--------|
| Identity | MATCH — live code uses combined avg > 0 as favorable zone |
| PIT safe | YES — per-start boxscores with shift(1) rolling |
| Parent dep | PARTIAL — research used V1 p_under > 0.57 as interaction gate; live fires independently |
| Economics | NO — shadow-only, flat -110 assumed, no actual prices logged |
| Evidence | Shadow 2026: 75 favorable, 65 resolved, 35W = 53.8% hit rate |

**Flags raised: 1/5** (economics — no actual prices)
Note: Research interaction gate (V1 p_under>0.57) is NOT used in live code. Signal fires standalone.

---

## 3. ADJ_HH

| Check | Result |
|-------|--------|
| Identity | MATCH — live code uses combined avg > 0 |
| PIT safe | YES — per-start Statcast hard-hit with shift(1) |
| Parent dep | PARTIAL — same as ADJ_CONTACT (research used V1 gate, live is standalone) |
| Economics | NO — shadow-only, no prices |
| Evidence | Shadow 2026: 38 favorable, 34 resolved, 21W = 61.8% hit rate |

**Flags raised: 1/5** (economics)
Best early performer. Small sample (34 resolved).

---

## 4. ADJ_K_RATE

| Check | Result |
|-------|--------|
| Identity | MATCH |
| PIT safe | YES — per-start K rate with shift(1) |
| Parent dep | PARTIAL (same research V1 gate, not used live) |
| Economics | NO — shadow-only |
| Evidence | Shadow 2026: 34 favorable, 30 resolved, 17W = 56.7% |

**Flags raised: 1/5** (economics)

---

## 5. ADJ_BB_RATE

| Check | Result |
|-------|--------|
| Identity | MATCH |
| PIT safe | YES — per-start BB rate with shift(1) |
| Parent dep | PARTIAL (same research V1 gate, not used live) |
| Economics | NO — shadow-only |
| Evidence | Shadow 2026: 19 favorable, 16 resolved, 8W = 50.0% |

**Flags raised: 2/5** (economics + evidence shows 50% = no edge)

---

## 6. ADJ_RUN_SUPP

| Check | Result |
|-------|--------|
| Identity | MATCH |
| PIT safe | YES — per-start run suppression with shift(1) |
| Parent dep | PARTIAL (same research V1 gate, not used live) |
| Economics | NO — shadow-only |
| Evidence | Shadow 2026: 42 favorable, 34 resolved, 19W = 55.9% |

**Flags raised: 1/5** (economics)

---

## 7. CS013

| Check | Result |
|-------|--------|
| Identity | MATCH — per-game boxscore signal with shift(1) |
| PIT safe | YES |
| Parent dep | NONE — independent pipeline |
| Economics | NO — shadow-only |
| Evidence | Shadow 2026: 128 entries, 0 fired. No evidence yet. |

**Flags raised: 2/5** (economics + zero fires = no evidence)

---

## 8. CS028

| Check | Result |
|-------|--------|
| Identity | MATCH |
| PIT safe | YES — per-game boxscores with shift(1) |
| Parent dep | NONE |
| Economics | NO |
| Evidence | Shadow 2026: 105 entries, 2 fired, 1 resolved, 1W. Trivial sample. |

**Flags raised: 2/5** (economics + near-zero evidence)

---

## 9. KP04

| Check | Result |
|-------|--------|
| Identity | MATCH |
| PIT safe | YES — per-game boxscores with shift(1) |
| Parent dep | NONE |
| Economics | NO |
| Evidence | Shadow 2026: 226 entries, 0 fired. No evidence. |

**Flags raised: 2/5** (economics + zero fires)

---

## 10. ST02 (Road Trip Fatigue)

| Check | Result |
|-------|--------|
| Identity | MATCH — road_trip_game_num >= 6 |
| PIT safe | YES — schedule data only (static) |
| Parent dep | PARTIAL — docstring says "tags existing V1 UNDER signals"; overlay-only |
| Economics | NO |
| Evidence | Shadow 2026: 0 fired in favorable zone. ST02 requires long road trips (rare early season). |

**Flags raised: 3/5** (economics + zero evidence + V1 dependency as overlay)

---

## 11. P09 Overlay

| Check | Result |
|-------|--------|
| Identity | MATCH — avg(hard_hit) * park_factor, cutoff <= 31.7305 |
| PIT safe | YES — Statcast hard-hit + static park config |
| Parent dep | YES — amplifies V1 UNDER stakes by 1.25x; value contingent on V1 being profitable |
| Economics | NO — overlay-only, no standalone prices |
| Evidence | V2 overlay revalidation: OOS blind-under active=50.9%, inactive=52.8% = COLLAPSES |

**Flags raised: 3/5** (economics + parent dependency on V1 + OOS collapse)

---

## 12. S12 Overlay

| Check | Result |
|-------|--------|
| Identity | PARTIAL — live uses fresh FG xFIP (clean), but cutoff 8.4468 derived from contaminated season-final xFIP |
| PIT safe | YES for live firing; NO for cutoff derivation |
| Parent dep | YES — amplifies V1 UNDER stakes |
| Economics | NO |
| Evidence | Standalone revalidation: overall -0.8% ROI. Alternating seasons (noise). Every threshold negative in-sample. |

**Flags raised: 4/5** (identity mismatch on cutoff + economics + parent dep + negative evidence)

---

## 13. V2 Baseline Engine

| Check | Result |
|-------|--------|
| Identity | MATCH — Model_B Ridge, 14 features, target=market_error |
| PIT safe | YES — rebuilt with PIT features |
| Parent dep | NONE — independent Ridge model |
| Economics | NO — shadow-only |
| Evidence | RMSE barely beats market (+0.01). Mean predicted edge +0.43 (strong over bias). ~900 over signals/season, ~0 under. Not bettable. |

**Flags raised: 2/5** (economics + evidence shows no bettable edge)

---

## 14. flyball_wind (Discrete Overlay)

| Check | Result |
|-------|--------|
| Identity | MATCH |
| PIT safe | YES (wind is per-game; flyball from live FG API) |
| Parent dep | Tested as V2 overlay — V2 itself has no bettable edge |
| Economics | NO |
| Evidence | V2 overlay: FW-active OVER hit=49.1%, inactive=46.3%. +4pp lift but within unprofitable universe. |

**Flags raised: 2/5** (economics + parent universe unprofitable)

---

## 15. F5 Totals Engine

| Check | Result |
|-------|--------|
| Identity | MISMATCH — consumes V1 p_under/p_over; clean V1 produces drastically different signals (1033->160 under signals) |
| PIT safe | YES for F5 lines; NO for V1 probabilities it consumes |
| Parent dep | YES — directly reads V1 probabilities. F5 threshold 0.57 tuned on contaminated V1. |
| Economics | PARTIAL — F5 lines collected but signal count collapsed with clean V1 |
| Evidence | Signal count drops 85% with clean V1. Inherits all V1 degradation. |

**Flags raised: 4/5** (identity mismatch + parent dep + evidence of collapse + threshold contaminated)

---

## 16. F5 Standalone (Not Built)

| Check | Result |
|-------|--------|
| Identity | N/A — does not exist |
| PIT safe | N/A |
| Parent dep | N/A |
| Economics | N/A |
| Evidence | N/A — would need independent clean baseline |

**Flags raised: N/A** (object does not exist)

---

## 17-18. Team Totals (Home + Away)

| Check | Result |
|-------|--------|
| Identity | NEVER-MATCHED — three distinct TT objects in codebase, none equivalent. Live uses ERA (baseline 4.50); research used xFIP (baseline 4.231) with end-of-season look-ahead. |
| PIT safe | Live formula: YES (PIT-safe expanding ERA). Research: NO (season-final xFIP). |
| Parent dep | Live does not depend on V1. But the formula coefficients were derived from contaminated research. |
| Economics | NO — prices not logged in either live or shadow |
| Evidence | Shadow 2026: 16 entries, 0 fired. Backtest with live formula (ERA-based): results not replicated. |

**Flags raised: 5/5** (identity mismatch + coefficient contamination + no economics + no evidence + never-matched)

---

## 19. Combined Short Exit

| Check | Result |
|-------|--------|
| Identity | MATCH — independent pipeline |
| PIT safe | YES — per-game boxscores with shift(1) |
| Parent dep | NONE |
| Economics | NO |
| Evidence | Shadow 2026: 128 entries, 0 fired. No evidence. |

**Flags raised: 2/5** (economics + zero fires)
