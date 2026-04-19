# MLB BOUNDED DISCOVERY PASS 03 — REPORT

**Pass Date:** 2026-04-19
**Operator:** Claude (automated research assistant)
**Mechanism Family:** WORKLOAD / DEPTH / HANDOFF ASYMMETRY
**Max Candidates:** 2
**Runtime Object:** MLB_RUNTIME_OBJECT_V1 (19,804 x 130, HISTORICAL_CLEAN)

---

## 1. PURPOSE

This is the third post-rebuild MLB bounded discovery pass. It generates at most 2 candidate hypotheses within the WORKLOAD / DEPTH / HANDOFF ASYMMETRY family, using only the clean runtime object and frozen package rules. This family targets starter-to-bullpen transition stress, carrying-capacity shortfall, and depth fragility asymmetry.

---

## 2. ENGINE STACK CONFIRMATION

| Element | Status |
|---|---|
| Frozen foundation package | `research/engine_foundation/mlb_engine_v1_foundation/` — confirmed |
| Orchestration layer | `research/orchestration/` — default_deny=true, confirmed |
| Runtime object | `mlb_runtime_object_v1.parquet` (19,804 x 130, HISTORICAL_CLEAN) — confirmed |
| Outside-package files | **NONE** |
| Caveats carried | CAVEAT_01 (bullpen process), CAVEAT_02 (SC averaging), CAVEAT_03 (naming) |

---

## 3. PRIOR FAMILY LESSONS CARRIED FORWARD

**Source:** E-family Pass 02 closeout files read from disk (persisted local artifacts).

Lessons applied to this pass:
1. **Vacuous thresholds are structural failure** (E01 lesson). Any environmental or contextual threshold that flags ~100% of rows creates a decorative filter, not an interaction. Every threshold proposed in this pass must create real selectivity.
2. **Semantically unsupported mechanisms must hard stop** (E02 lesson). If a candidate requires a field interpretation the runtime object cannot honestly support, it must be rejected, not approximated.
3. **No salvage by quiet reinterpretation.** If an interaction collapses to one component, the candidate fails — it does not silently become a single-factor candidate.

---

## 4. ELIGIBLE SUPPORTING FAMILIES (PRE-DECLARED)

The following runtime-object field families are eligible to support candidates in this pass:

| Family | Fields | Relevance to Workload/Depth/Handoff |
|---|---|---|
| **Opp SP workload profile** | opp_sp_workload_ip_last_{3,5,10}, opp_sp_workload_bf_last_{3,5,10}, opp_sp_workload_pitches_last_{3,5,10}, opp_sp_workload_ppbf_last_{3,5,10} | Starter carrying capacity, workload trajectory, efficiency |
| **Bullpen state** | relievers_used_last_{game,3_games}, bullpen_pitches_last_{game,3_games}, high_leverage_available | Bullpen depth/fatigue/availability context |
| **Opp SP command** | opp_sp_command_bb_rate_last_{3,5,10}, opp_sp_command_zone_rate_last_{3,5,10} | Starter control instability as a workload risk indicator |

Not eligible for primary mechanism (but may serve as context):
- Lineup features (offense quality — not workload/depth)
- Park/weather context (environment — not handoff mechanism)

---

## 5. CANDIDATES ADVANCED

### MLB_W01 — Short-Outing Starter × Depleted Bullpen Conjunction

| Field | Value |
|---|---|
| **candidate_id** | MLB_W01 |
| **candidate_name** | Short-Outing Starter x Depleted Bullpen Conjunction |
| **mechanism_family** | WORKLOAD / DEPTH / HANDOFF ASYMMETRY |

**core_claim:**
When the opposing starter has been averaging short outings recently (low IP last 3) AND the opposing team's bullpen is already depleted (high relievers/pitches used recently), the handoff from starter to bullpen is forced earlier into a bullpen that is less equipped to absorb extra innings. This creates a depth-fragility state: the bullpen arms that normally handle high-leverage spots are tired, and the starter cannot go deep enough to protect them. The hypothesis is that this conjunction produces more total runs than the market expects because the market may price starter quality and bullpen fatigue separately but underreact to the CONJUNCTION of both being unfavorable simultaneously.

**required_runtime_fields:**
1. `opp_sp_workload_ip_last_3` — opposing starter recent innings per start
2. `bullpen_pitches_last_3_games` — opposing team's bullpen pitch load over last 3 games

**interaction_form:** AND rule — both conditions must fire simultaneously.

**proposed_threshold_logic:**
- `opp_sp_workload_ip_last_3 <= 4.67` AND `bullpen_pitches_last_3_games >= 200`
- **Domain grounding:** 4.67 IP = 4 innings + 2 outs, which is below the ~5.0 IP conventional short-outing line. A starter averaging under 4.67 IP over their last 3 starts is consistently failing to get through the order twice. 200 bullpen pitches over 3 games = ~67 pitches/game average for the bullpen, meaning relievers have been absorbing ~4+ innings per game recently. Both thresholds represent meaningful stress states.
- **Grain:** One flag per team-side per game (the team BATTING against the short-outing starter with the depleted bullpen is flagged).

**why_market_might_miss_it:**
Markets price starter quality (ERA, K/BB, recent results) and may adjust for bullpen availability to some extent. But the specific CONJUNCTION — a starter who can't go deep AND a bullpen that's already overworked — creates a multiplicative depth crisis. The market may price each factor with some discount but not fully capture how they compound: a 4.5-IP starter behind a fresh bullpen is manageable; a 4.5-IP starter behind a spent bullpen is a different risk profile entirely.

**anti_duplication_note:**
- Not H03: H03 tested OWN bullpen stress × OWN starter short-outing risk. W01 tests the OPPOSING team's conjunction — a different side of the matchup entirely. Also, H03 used bullpen stress (relievers_used) × starter short-outing risk. W01 uses bullpen PITCH LOAD (pitches, not reliever count) × starter recent IP.
- Not D01: D01 tested opposing starter workload trajectory collapse (gap between windows). W01 tests a level threshold on recent IP, not a trajectory gap, AND conjoins it with bullpen load.
- Not generic bullpen tired: W01 requires BOTH conditions. Bullpen depletion alone is not flagged. Starter short outings alone are not flagged.
- Not E01-style vacuous threshold: Both thresholds (IP <= 4.67, pitches >= 200) are designed to be selective, not broad.

**expected_failure_mode:**
(1) The conjunction may be too rare — if few games have both conditions simultaneously, flagged N may fall below 30 in discovery. (2) The market may already capture both factors individually well enough that the conjunction adds no residual. (3) bullpen_pitches_last_3_games may be noisy or dominated by blowout effects rather than genuine fatigue.

**why_testable_now:**
Both fields exist in MLB_RUNTIME_OBJECT_V1. `opp_sp_workload_ip_last_3` is an OPP_SP_FEATURE (CAVEAT_02 applies). `bullpen_pitches_last_3_games` is a BULLPEN_FEATURE (CAVEAT_01 applies). Both caveats are documented. The AND rule, thresholds, and direction can be frozen before discovery. Testable via standard `historical_hypothesis_test` workflow.

---

### MLB_W02 — Opposing Starter Command Instability × High Bullpen Usage

| Field | Value |
|---|---|
| **candidate_id** | MLB_W02 |
| **candidate_name** | Opposing Starter Command Instability x High Bullpen Usage |
| **mechanism_family** | WORKLOAD / DEPTH / HANDOFF ASYMMETRY |

**core_claim:**
When the opposing starter has recently demonstrated poor command (high BB rate over last 3 starts) AND the opposing bullpen has been heavily used recently (high relievers used last 3 games), the game faces a handoff-pressure asymmetry. A starter with poor command is more likely to have high pitch counts (deep counts, more walks = more pitches per batter), exit earlier, and hand off to a bullpen that is already stretched. The hypothesis is that command instability — not just innings shortfall — is a leading indicator of forced early exit, and when combined with bullpen depletion, it produces a depth-fragility state the market underprices.

**required_runtime_fields:**
1. `opp_sp_command_bb_rate_last_3` — opposing starter walk rate over last 3 starts
2. `relievers_used_last_3_games` — opposing team's reliever usage over last 3 games

**interaction_form:** AND rule — both conditions must fire simultaneously.

**proposed_threshold_logic:**
- `opp_sp_command_bb_rate_last_3 >= 0.10` AND `relievers_used_last_3_games >= 12`
- **Domain grounding:** MLB average BB rate for starters is approximately 7-8%. A 10%+ BB rate over 3 starts represents poor command — the starter is walking roughly 1 in 10 batters faced, leading to high pitch counts and earlier exits. 12+ relievers used over 3 games = 4+ relievers per game average, indicating the bullpen has been absorbing substantial workload (a typical game uses 3-4 relievers; 4+ per game over 3 games means heavy usage).
- **Grain:** One flag per team-side per game (the team BATTING against the wild starter with the taxed bullpen is flagged).

**why_market_might_miss_it:**
Markets price starter BB rate implicitly through ERA/FIP, and may adjust for bullpen usage patterns. But command instability (BB rate) is a LEADING indicator of workload stress — a starter who walks many batters burns through pitch counts faster, even if their other metrics look acceptable. The market may see "decent K rate, moderate ERA" without fully discounting that the high walk rate is a ticking clock for early exit. Combined with a bullpen that's already been heavily used, this creates a depth-fragility state that the individual pricing of each factor may miss.

**anti_duplication_note:**
- Not H03: Different side of matchup (opposing, not own). Different mechanism component (command instability via BB rate, not short-outing risk via IP). Different bullpen component (relievers used count, not bullpen stress flag).
- Not D01: D01 tested IP trajectory collapse (gap between windows). W02 uses BB rate as a leading indicator of handoff pressure, not IP as a lagging indicator.
- Not W01: W01 uses IP level × bullpen pitches. W02 uses BB rate × relievers used. Different fields, different mechanism angle. W01 targets starters who ARE going short. W02 targets starters who are LIKELY to go short because their command is deteriorating, even if recent IP looks adequate.
- Not generic "bad starter": BB rate alone is not flagged. High BB rate with a fresh bullpen is manageable. The flag requires the conjunction with bullpen depletion.
- Not E-family: Different mechanism family entirely.

**expected_failure_mode:**
(1) BB rate over 3 starts may be very noisy — a single bad outing can spike the rate. (2) The conjunction may be too rare. (3) The market may already capture BB rate through FIP-based projections well enough that no residual exists.

**why_testable_now:**
Both fields exist in MLB_RUNTIME_OBJECT_V1. `opp_sp_command_bb_rate_last_3` is an OPP_SP_FEATURE (CAVEAT_02). `relievers_used_last_3_games` is a BULLPEN_FEATURE (CAVEAT_01). Both caveats documented. AND rule, thresholds, and direction can be frozen. Testable via standard workflow.

---

## 6. CANDIDATES REJECTED

| Name | Reason |
|---|---|
| High-Leverage Unavailable × Short-Outing Starter | Too close to H01 (forced bullpen exposure) and H03 (bullpen stress × short-outing risk). Uses `high_leverage_available` which is the same field H01 family tested. Anti-duplication fails. |
| Opposing Starter Pitch Count Trajectory × Bullpen Depletion | Overlaps substantially with D01 (opposing starter workload trajectory collapse). Uses the same trajectory-gap concept (pitches_last_3 vs pitches_last_10) that D01 tested with IP. Not sufficiently distinct. |

---

## 7. FINAL RECOMMENDATION

**Candidates advanced: 2**
**Advanced IDs: MLB_W01, MLB_W02**

Both candidates express genuine WORKLOAD / DEPTH / HANDOFF ASYMMETRY mechanisms:
- W01 tests the conjunction of SHORT OUTING + DEPLETED BULLPEN (lagging depth crisis)
- W02 tests the conjunction of POOR COMMAND + HIGH RELIEVER USAGE (leading depth pressure)

W01 is the more direct candidate — it targets a state that is already manifesting. W02 is the more novel candidate — it uses command instability (BB rate) as a leading indicator of handoff pressure rather than waiting for IP shortfall to materialize. If only one is tested, W01 is recommended first for clarity. W02 is the riskier but potentially more market-inefficient idea.

Neither candidate is guaranteed to produce signal. Both have plausible failure modes. The recommendation is to test, not to deploy.

---

*Report generated: 2026-04-19*
*Engine stack: MLB_ENGINE_V1_FOUNDATION + MLB_RESEARCH_ORCHESTRATION_V1 + MLB_RUNTIME_OBJECT_V1*
