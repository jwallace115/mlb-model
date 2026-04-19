# MLB E01 — MANUAL HISTORICAL HYPOTHESIS TEST REPORT

**Test Date:** 2026-04-18
**Candidate ID:** MLB_E01
**Candidate Name:** Barrel Rate x Park HR Factor
**Advancement Type:** MANUAL_FROM_PROVISIONAL_DISCOVERY
**Mechanism Family:** CONTACT-SHAPE x RUN-ENVIRONMENT INTERACTION
**Runtime Object:** MLB_RUNTIME_OBJECT_V1 (19,804 x 130, HISTORICAL_CLEAN)

---

## 1. PURPOSE

This report documents a manual bounded historical hypothesis test for provisional candidate MLB_E01 (Barrel Rate x Park HR Factor) from MLB Bounded Discovery Pass 02. This is the first bounded hypothesis test through the post-rebuild MLB engine stack.

---

## 2. ENGINE STACK CONFIRMATION

| Element | Status |
|---|---|
| Frozen foundation package | `research/engine_foundation/mlb_engine_v1_foundation/` — confirmed |
| Orchestration layer | `research/orchestration/` — default_deny=true, confirmed |
| Runtime object | `mlb_runtime_object_v1.parquet` (19,804 x 130, HISTORICAL_CLEAN) — confirmed |
| Outside-package files used | **NONE** |
| Caveats carried | CAVEAT_01, CAVEAT_02, CAVEAT_03 |

---

## 3. MANUAL ADVANCEMENT STATUS

MLB_E01 was manually advanced from provisional discovery candidate (Bounded Discovery Pass 02). This is not autonomous promotion. The test is conducted under the rebuilt local engine stack with default-deny rules.

---

## 4. FROZEN TEST DEFINITION

Frozen before any results were examined:

| Element | Frozen Value |
|---|---|
| Fields | `contact_barrel_rate_last_10`, `park_factor_hr` |
| Field count | 2 |
| Interaction form | (A) AND rule — both must exceed threshold simultaneously |
| Rule | `contact_barrel_rate_last_10 >= 0.08 AND park_factor_hr >= 1.10` |
| Direction | Flagged games expected to have higher actual_total |
| Split | Discovery 2022-2023, Validation 2024, OOS 2025 |

The AND form was specified in the discovery pass artifact. It was not chosen after seeing results.

---

## 5. FIELD USABILITY CHECK

| Field | Present | Non-null Rate | Usable |
|---|---|---|---|
| contact_barrel_rate_last_10 | YES | 94.2% (18,662/19,804) | YES |
| park_factor_hr | YES | 100.0% | YES |
| actual_total | YES | 100.0% | YES |

Usable rows (2022-2025, both fields + outcome non-null): 18,590.

---

## 6. ANTI-DUPLICATION / MECHANISM CHECK

### 1. Why this is different from dead V1-lite logic
V1-lite used ISO and BB% archetypes — aggregate offensive quality classifications. E01 uses barrel rate, a Statcast-derived contact-SHAPE metric that specifically measures optimal exit-velocity + launch-angle combinations. Barrel rate was not available in V1-era work. The interaction with park_factor_hr is a specific environment modifier, not a generic quality bucket.

### 2. Why this is different from generic park inflation
Generic park inflation would flag ALL games in HR-friendly parks regardless of who is batting. E01 requires the batting team to have an elevated barrel rate — a groundball-heavy team in a HR park would NOT be flagged. The signal is specifically about how barrel-heavy contact profiles interact with HR park amplification.

### 3. Why this is different from generic offense strength
A team with high xwOBA from walks and low barrel rate would NOT be flagged. E01 requires barrel rate ≥ 0.08 specifically — the mechanism is about the SHAPE of contact (barrels), not overall quality.

### 4. What specific interaction structure is claimed
Barrels are batted balls at optimal EV+LA for home runs. HR-friendly parks amplify the probability that a barrel clears the fence. The interaction: a barrel-heavy team in a HR park sees its primary damage mechanism specifically amplified by the park characteristic. This is a true 2-factor interaction, not a single-factor signal.

### Concern: Flag Rate Is Very Broad

The flag rate is 43-57% across stages. This means nearly half of all team-sides are flagged. This raises a serious structural concern: **a flag that captures ~50% of observations may not be capturing a specific interaction — it may be capturing a broad baseline split between "above-average barrel rate in above-average HR park" and everything else.** This is closer to a median split than a targeted interaction flag.

A truly specific contact-shape × environment interaction should flag a meaningfully smaller subset. At 43-57% flag rate, the "interaction" may be mostly park_factor_hr doing the work (HR parks tend to produce more runs regardless of barrel rate), with barrel rate adding only marginal selectivity.

**This concern does not kill the candidate but must be carried forward as a serious structural caveat.**

---

## 7. STAGE RESULTS

| Stage | N Total | N Flagged | Flag % | Mean Flagged | Mean Unflagged | Gap |
|---|---|---|---|---|---|---|
| Discovery (2022-2023) | 9,300 | 4,071 | 43.8% | 8.969 | 8.860 | **+0.109** |
| Validation (2024) | 4,644 | 1,978 | 42.6% | 8.883 | 8.680 | **+0.202** |
| OOS (2025) | 4,646 | 2,637 | 56.8% | 9.007 | 8.777 | **+0.230** |

All gates pass:
- Discovery N=4,071 (well above 30)
- Discovery gap +0.109 (above 0.10 floor, barely)
- Discovery direction correct (flagged > unflagged)
- Validation same sign (+0.202)
- OOS no reversal (+0.230)

The staged profile is monotonically increasing (+0.109 → +0.202 → +0.230) — the strongest stage is OOS. This is a clean profile.

---

## 8. INTERPRETATION

### What Went Right
- All three stages show positive direction consistent with the mechanism
- The profile is monotonically increasing — rare and encouraging
- Validation and OOS are both stronger than discovery, suggesting the signal is not overfitted to the discovery period
- The mechanism is interpretable: barrel-heavy teams produce more runs in HR-friendly parks

### What Raises Concern
- **Discovery gap is marginal.** +0.109 barely clears the 0.10 non-triviality floor. If the floor were 0.15, this would fail.
- **Flag rate is extremely broad (43-57%).** This is not a selective interaction flag — it's closer to a median split. A ~50% flag rate means the "interaction" is more like a broad environmental partition than a targeted mechanism. This undermines the claim that the signal captures a specific contact-shape × environment interaction rather than a generic "above-average power in above-average park" split.
- **The gap magnitudes are small.** Even the strongest stage (OOS +0.230) represents less than a quarter of a run. The economic significance — whether this gap exceeds market pricing noise — is untested.

### Honest Assessment
E01 passes all pre-declared staged gates with a clean monotonic profile. But the combination of marginal discovery gap and extremely broad flag rate raises a legitimate question: **is this a real interaction or is it mostly park_factor_hr partitioning the data?** A component-dominance check (testing park_factor_hr alone vs. the full interaction) would be the natural next diagnostic.

---

## 9. FINAL VERDICT

**ADVANCE — with broad-flag-rate structural caveat**

E01 passes all staged gates. The monotonic profile and mechanism integrity justify advancement. However, the 43-57% flag rate is a serious structural concern that must be evaluated in a child branch (component-dominance check) before further promotion.

This verdict does not imply deployment readiness.

---

## 10. WHAT THIS RESULT DOES NOT CLAIM

- This is **not** deployment approval
- This is **not** profitability proof
- This is **not** a live recommendation
- This does **not** yet prove market mispricing — the gap magnitudes are small and the flag rate is broad
- This does **not** confirm that the interaction adds value beyond park_factor_hr alone

---

*Report generated: 2026-04-18*
*Engine stack: MLB_ENGINE_V1_FOUNDATION + MLB_RESEARCH_ORCHESTRATION_V1 + MLB_RUNTIME_OBJECT_V1*
