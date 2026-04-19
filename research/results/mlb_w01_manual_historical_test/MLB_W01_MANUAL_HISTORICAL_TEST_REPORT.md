# MLB W01 — MANUAL HISTORICAL HYPOTHESIS TEST REPORT

**Test Date:** 2026-04-19
**Candidate ID:** MLB_W01
**Candidate Name:** Short-Outing Starter x Depleted Bullpen
**Advancement Type:** MANUAL_FROM_PROVISIONAL_DISCOVERY
**Mechanism Family:** WORKLOAD / DEPTH / HANDOFF ASYMMETRY
**Runtime Object:** MLB_RUNTIME_OBJECT_V1 (19,804 x 130, HISTORICAL_CLEAN)

---

## 1. PURPOSE

This report documents a manual bounded historical hypothesis test for provisional candidate MLB_W01 from MLB Bounded Discovery Pass 03.

---

## 2. ENGINE STACK CONFIRMATION

| Element | Status |
|---|---|
| Frozen foundation package | confirmed |
| Orchestration layer | confirmed (default_deny=true) |
| Runtime object | MLB_RUNTIME_OBJECT_V1 — confirmed |
| Outside-package files | **NONE** |
| Caveats carried | CAVEAT_01 (bullpen process), CAVEAT_02 (SC averaging), CAVEAT_03 (naming) |

---

## 3. MANUAL ADVANCEMENT STATUS

MLB_W01 was manually advanced from provisional discovery candidate (Bounded Discovery Pass 03). This is not autonomous promotion.

---

## 4. FROZEN TEST DEFINITION

Frozen before any results:

| Element | Value |
|---|---|
| Fields | `opp_sp_workload_ip_last_3`, opponent's `bullpen_pitches_last_3_games` (via self-join) |
| Field count | 2 (+ 1 self-join derivation from existing approved field) |
| Interaction form | (A) AND rule — both must fire simultaneously |
| Rule | `opp_sp_workload_ip_last_3 <= 4.67 AND opp_bullpen_pitches_last_3 >= 200` |
| Direction | Flagged games expected to have higher actual_total |
| Side resolution | **BATTING TEAM perspective** — flagged when the OPPOSING team has both a short-outing starter AND a depleted bullpen |
| Split | Discovery 2022-2023, Validation 2024, OOS 2025 |

**Self-join note:** The runtime object stores `bullpen_pitches_last_3_games` as the row-team's own bullpen. To get the opponent's bullpen pitches, a self-join on (game_pk, opponent_team) was performed. This uses only existing approved fields — no outside-package inputs.

---

## 5. FIELD USABILITY CHECK

| Field | Present | Non-null Rate | Usable |
|---|---|---|---|
| opp_sp_workload_ip_last_3 | YES | 84.7% | YES |
| opp_bullpen_pitches_last_3 (self-join) | YES | 99.2% | YES |
| actual_total | YES | 100% | YES |

Usable rows (2022-2025, both fields + outcome non-null): 16,702.

---

## 6. ANTI-DUPLICATION / MECHANISM CHECK

### 1. Not generic starter weakness
W01 does not flag all short-outing starters. It requires the CONJUNCTION of short outings AND depleted bullpen. A short-outing starter behind a fresh bullpen is NOT flagged.

### 2. Not generic bullpen weakness
W01 does not flag all depleted bullpens. It requires the conjunction with a short-outing starter. A depleted bullpen behind a starter who goes 7 innings is NOT flagged.

### 3. Not simple additive bad-pitching
The mechanism is specifically about HANDOFF STRESS — the starter can't go deep AND the bullpen behind them is already taxed. This is multiplicative depth fragility, not additive "both are bad."

### 4. Specific handoff asymmetry claimed
When the opposing starter has been going short (≤ 4.67 IP avg last 3), the bullpen must absorb more innings. When that bullpen is ALSO already depleted (≥ 200 pitches last 3 games), the forced handoff goes into a weaker relief chain. The asymmetry: the starter's inability to carry load compounds with the bullpen's inability to absorb extra load.

### 5. Not a relabeled already-tested family
**H03 check:** H03 tested OWN bullpen stress × OWN starter short-outing risk — the same team's starter and bullpen. W01 tests the OPPOSING team's starter × OPPOSING team's bullpen from the batting team's perspective. Different side of the matchup. Also different fields: H03 used `high_leverage_available` and bullpen stress indicators; W01 uses `opp_sp_workload_ip_last_3` and `bullpen_pitches_last_3_games`. Structurally distinct.

**D01 check:** D01 tested opposing starter workload trajectory COLLAPSE (gap between windows). W01 tests a level threshold on recent IP conjoined with bullpen load. Different mechanism (level vs. trajectory) and adds a bullpen component D01 lacked.

### Prior lessons carried:
- E01 lesson (vacuous thresholds): W01's flag rate is 7-9% — selective, not broad. Neither threshold is vacuous.
- E02 lesson (unsupported semantics): Both fields are straightforward numeric thresholds with clear baseball meaning. No park-specific or semantic ambiguity.

---

## 7. STAGE RESULTS

| Stage | N Total | N Flagged | Flag % | Mean Flagged | Mean Unflagged | Gap |
|---|---|---|---|---|---|---|
| Discovery (2022-2023) | 8,353 | 745 | 8.9% | 9.213 | 8.890 | **+0.323** |
| Validation (2024) | 4,169 | 288 | 6.9% | 8.764 | 8.745 | **+0.019** |
| OOS (2025) | 4,180 | 314 | 7.5% | 9.185 | 8.821 | **+0.363** |

All gates pass:
- Discovery N=745 (well above 30)
- Discovery gap +0.323 (non-trivial, well above 0.10)
- Discovery direction correct
- Validation same sign (+0.019)
- OOS no reversal (+0.363)

---

## 8. INTERPRETATION

### What Went Right
- Discovery and OOS show strong, consistent gaps (+0.323 and +0.363)
- Flag rate is selective (7-9%) — this is a genuinely targeted conjunction, not a broad bucket
- The mechanism is clear and interpretable
- Anti-duplication checks pass cleanly
- No vacuous thresholds (unlike E01)
- No semantic ambiguity (unlike E02)

### What Raises Concern
- **Validation attenuation is severe.** +0.323 → +0.019 is a 94% shrinkage. This is the same non-monotonic pattern seen in D01 (strong → near-zero → strong). The validation dip could be:
  - Sampling noise (N=288 flagged in validation — smaller sample)
  - A genuine 2024-specific structural change that temporarily masked the signal
  - Evidence that the signal is unstable and the strong OOS is a lucky rebound
- **The non-monotonic pattern is now a recurring concern.** D01 showed the same shape. W01 showing it again suggests either (a) 2024 specifically had structural differences that suppress these types of interactions, or (b) these conjunction signals are inherently noisy in validation-sized samples.

### Honest Assessment
W01 passes all pre-declared gates with a selective flag rate and strong mechanism integrity. The validation attenuation (94% shrinkage) is a documented concern but does not trigger the shelve condition (same sign preserved). The candidate is structurally more satisfying than D01 was — the flag rate is selective (7-9% vs D01's 44%), both thresholds create real selectivity, and the mechanism is a genuine conjunction rather than a single-component signal. However, the validation concern must be carried forward.

---

## 9. FINAL VERDICT

**ADVANCE — with validation-attenuation caveat**

W01 passes all staged gates. The flag rate is selective (7-9%), both thresholds are non-vacuous, the mechanism is a genuine 2-component conjunction, and the anti-duplication checks pass. The 94% validation attenuation is the documented caveat. A component-dominance check is the natural next diagnostic to confirm the conjunction adds value beyond either component alone.

This verdict does not imply deployment readiness.

---

## 10. WHAT THIS RESULT DOES NOT CLAIM

- This is **not** deployment approval
- This is **not** profitability proof
- This is **not** a live recommendation
- This does **not** yet prove market mispricing
- The validation attenuation means structural confirmation is incomplete

---

*Report generated: 2026-04-19*
*Engine stack: MLB_ENGINE_V1_FOUNDATION + MLB_RESEARCH_ORCHESTRATION_V1 + MLB_RUNTIME_OBJECT_V1*
