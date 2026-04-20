# MLB W02 — MANUAL HISTORICAL HYPOTHESIS TEST REPORT

**Test Date:** 2026-04-19
**Candidate ID:** MLB_W02
**Candidate Name:** Command Instability x High Bullpen Usage
**Advancement Type:** MANUAL_FROM_PROVISIONAL_DISCOVERY
**Mechanism Family:** WORKLOAD / DEPTH / HANDOFF ASYMMETRY
**Runtime Object:** MLB_RUNTIME_OBJECT_V1 (19,430 x 130, HISTORICAL_CLEAN)

---

## 1. PURPOSE

This report documents a manual bounded historical hypothesis test for provisional candidate MLB_W02 from MLB Bounded Discovery Pass 03. The hypothesis is that when an opposing starter shows elevated command instability (high BB rate) AND the opposing bullpen has been heavily used recently, the compounding handoff pressure produces more total runs than the market expects.

---

## 2. ENGINE STACK CONFIRMATION

| Element | Status |
|---|---|
| Frozen foundation package | `research/engine_foundation/mlb_engine_v1_foundation/` — confirmed |
| Orchestration layer | `research/orchestration/` — default_deny=true, confirmed |
| Runtime object | MLB_RUNTIME_OBJECT_V1 (19,430 x 130) — confirmed |
| Outside-package files | **NONE** |
| Caveats carried | CAVEAT_01 (bullpen process), CAVEAT_02 (SC averaging), CAVEAT_03 (naming) |

---

## 3. MANUAL ADVANCEMENT STATUS

MLB_W02 was manually advanced from provisional discovery candidate (Bounded Discovery Pass 03). This is not autonomous promotion. All work is local. Frozen engine stack is being used. No outside-package inputs are allowed.

---

## 4. FROZEN TEST DEFINITION

Frozen before any results:

| Element | Value |
|---|---|
| Fields | `opp_sp_command_bb_rate_last_3`, opponent's `relievers_used_last_3_games` (via self-join) |
| Field count | 2 (+1 self-join derivation from existing approved field) |
| Interaction form | AND rule — both must fire simultaneously |
| Rule | `opp_sp_command_bb_rate_last_3 >= 0.10 AND opp_relievers_used_last_3 >= 12` |
| Direction | Flagged games expected to have higher actual_total |
| Side resolution | **BATTING TEAM perspective** — flagged when the OPPOSING team has both a wild starter AND a taxed bullpen |
| Split | Discovery 2022-2023, Validation 2024, OOS 2025 |

**Threshold domain grounding:**
- BB rate >= 0.10: MLB average starter BB rate is ~7-8%. A 10%+ BB rate over 3 starts represents poor command — the starter is walking roughly 1 in 10 batters faced, leading to high pitch counts and earlier exits.
- Relievers used >= 12 over 3 games: 4+ relievers per game average, indicating the bullpen has been absorbing substantial workload (typical game uses 3-4 relievers; 4+ per game over 3 games means heavy usage).

**Self-join note:** The runtime object stores `relievers_used_last_3_games` as the row-team's own bullpen. To get the opponent's reliever usage, a self-join on (game_pk, opponent_team) was performed. This uses only existing approved fields — no outside-package inputs.

---

## 5. FIELD USABILITY CHECK

| Field | Present | Non-null Rate | Usable |
|---|---|---|---|
| opp_sp_command_bb_rate_last_3 | YES | 86.0% (16,702/19,430) | YES |
| opp_relievers_used_last_3 (self-join) | YES | 99.4% (19,310/19,430) | YES |
| actual_total | YES | 100% | YES |

Usable rows (2022-2025, both fields + outcome non-null): **16,702**.

---

## 6. VACUOUS THRESHOLD CHECK

| Stage | Component A (BB>=0.10) | Component B (rel>=12) | W02 Full |
|---|---|---|---|
| DISCOVERY | 2,201 / 8,353 (26.3%) | 1,656 / 8,353 (19.8%) | 406 / 8,353 (4.9%) |
| VALIDATION | 1,078 / 4,169 (25.9%) | 774 / 4,169 (18.6%) | 210 / 4,169 (5.0%) |
| OOS | 1,165 / 4,180 (27.9%) | 846 / 4,180 (20.2%) | 220 / 4,180 (5.3%) |
| **OVERALL** | **4,444 / 16,702 (26.6%)** | **3,276 / 16,702 (19.6%)** | **836 / 16,702 (5.0%)** |

- Component A: 26.6% — NOT vacuous (within 5-80% range)
- Component B: 19.6% — NOT vacuous (within 5-80% range)
- Full formulation: 5.0% — selective, at the 5% floor but not below it
- **Vacuous verdict: NEITHER component is vacuous**

---

## 7. ANTI-DUPLICATION / MECHANISM CHECK

### 1. Not generic starter command weakness
W02 does not flag all high-BB-rate starters. It requires the CONJUNCTION with high reliever usage on the same opposing team. A wild starter backed by a fresh bullpen is NOT flagged.

### 2. Not generic bullpen fatigue
W02 does not flag all high-usage bullpens. A heavily-used bullpen behind a starter with excellent command is NOT flagged. The flag requires the conjunction.

### 3. Not W01 (short-outing x depleted bullpen)
W01 uses IP level (lagging — starter IS going short) x bullpen pitches. W02 uses BB rate (leading — command deterioration signals LIKELY early exit) x relievers used count. Different fields, different mechanism angle. W01 detects an existing depth crisis; W02 detects an emerging one.

### 4. Not H03-family bullpen stress
H03 tested OWN bullpen stress x OWN starter short-outing risk — the same team's starter and bullpen. W02 tests the OPPOSING team's conjunction from the batting team's perspective. Different side of the matchup, different fields.

### 5. Specific compounding handoff asymmetry claimed
A high-walk-rate starter burns pitch counts faster (deep counts, free baserunners), making earlier exits more likely. Combined with a bullpen that has already been heavily used (4+ relievers per game recently), the forced handoff goes into a relief chain with less available depth. Command instability accelerates the starter-to-bullpen transition into a bullpen least equipped to handle it.

---

## 8. STAGE RESULTS

| Stage | N Total | N Flagged | Flag % | Mean Flagged | Mean Unflagged | Gap |
|---|---|---|---|---|---|---|
| Discovery (2022-2023) | 8,353 | 406 | 4.9% | 9.347 | 8.897 | **+0.450** |
| Validation (2024) | 4,169 | 210 | 5.0% | 9.405 | 8.712 | **+0.693** |
| OOS (2025) | 4,180 | 220 | 5.3% | 8.409 | 8.873 | **-0.464** |

### Gate Evaluation

| Gate | Result |
|---|---|
| Discovery direction correct and non-trivial | **PASS** (+0.450, well above 0.10) |
| Discovery flagged N >= 30 | **PASS** (N=406) |
| Validation preserves sign | **PASS** (+0.693, amplified) |
| OOS does not materially reverse | **FAIL** (-0.464, complete sign reversal, magnitude exceeds discovery) |
| Neither component vacuous | **PASS** |
| Mechanism interaction-specific | **PASS** |

**One gate fails: OOS material reversal.**

---

## 9. INTERPRETATION

### What Went Right
- Discovery gap is strong (+0.450) and mechanistically plausible
- Validation gap amplifies (+0.693) — unusual and initially encouraging
- Flag rate is very selective (5.0%) — this is a genuinely targeted conjunction
- Neither component is vacuous (26.6% and 19.6%)
- Anti-duplication checks pass cleanly
- No vacuous thresholds (unlike E01)

### What Went Wrong
- **OOS reversal is decisive.** +0.450 / +0.693 / -0.464 means the signal completely collapses in the most recent season. The gap doesn't just attenuate — it flips sign with comparable magnitude.
- **The validation amplification is a red flag in retrospect.** Discovery +0.450 amplifying to validation +0.693 (54% increase) is suspicious. True signals generally attenuate in validation, not amplify. The amplification followed by reversal suggests instability, not robustness.
- **Contrast with W01's pattern.** W01 showed discovery +0.323, validation +0.019, OOS +0.363 (non-monotonic but same sign throughout). W02 shows discovery +0.450, validation +0.693, OOS -0.464 (sign reversal). W02's pattern is materially worse than W01's.

### Comparison to W01 Lessons
- W01 had 94% validation attenuation but preserved sign. W02 has validation amplification but OOS reversal. Different failure modes, both concerning.
- W01's economic reality check showed the market prices most of the raw signal. W02 does not merit an economic reality check given the OOS reversal.
- The W-family as a whole (workload/depth/handoff asymmetry) now has one candidate at PRESERVE_AS_CONTEXT (W01) and one at SHELVE (W02).

### Honest Assessment
W02 fails the OOS gate decisively. A signal that amplifies in validation and then reverses in OOS is a hallmark of noise or regime-dependent effects that do not generalize. The mechanism is conceptually sound (command instability as a leading indicator of handoff pressure), but the empirical evidence does not support it. The 5% flag rate, while selective, also means small-N sensitivity: 220 OOS flagged games, where a few high-scoring or low-scoring games can swing the mean substantially.

---

## 10. FINAL VERDICT

**SHELVE**

W02 fails the OOS material reversal gate. Discovery (+0.450) and validation (+0.693) do not survive into OOS (-0.464). The sign reversal is complete and the magnitude is comparable to the discovery effect. This is not a marginal miss — the signal demonstrably does not hold out of sample.

W02 is shelved. No further branches (component dominance, economic reality check) are warranted given the OOS reversal.

---

## 11. WHAT THIS RESULT DOES NOT CLAIM

- This is **not** deployment approval
- This is **not** profitability proof
- This is **not** a live recommendation
- This does **not** prove or disprove market mispricing
- The discovery/validation signal may reflect real but unstable or regime-specific effects
- Shelving does not mean the mechanism is wrong — it means the evidence does not support advancement

---

*Report generated: 2026-04-19*
*Engine stack: MLB_ENGINE_V1_FOUNDATION + MLB_RESEARCH_ORCHESTRATION_V1 + MLB_RUNTIME_OBJECT_V1*
