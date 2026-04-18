# MLB BOUNDED DISCOVERY PASS 01 — REPORT

**Pass Date:** 2026-04-17
**Operator:** Claude (automated research assistant)
**Mechanism Family:** FORCED-ROLE / ROLE-INSTABILITY / STATE-TRANSITION ASYMMETRY
**Max Candidates:** 2
**Canonical Object:** `mlb_matchup_table_base` (see provenance note)

---

## 1. PURPOSE

This is the first bounded autonomous MLB discovery pass. Its purpose is to generate at most 2 candidate hypotheses worth testing next, within a single mechanism family, using only the approved canonical historical research infrastructure.

Quality over quantity. Returning 0 or 1 candidate is acceptable. The pass proves the system can stay inside the approved object, avoid drift, avoid rediscovering dead families, and produce testable candidates with frozen definitions.

---

## 2. DISCOVERY SCOPE CONFIRMATION

- **Single mechanism family enforced:** YES — all candidates evaluated within FORCED-ROLE / ROLE-INSTABILITY / STATE-TRANSITION ASYMMETRY only.
- **Canonical historical object only:** YES — with provenance substitution noted below.
- **Max 2 candidate cap enforced:** YES — 2 candidates advanced, 0 padded.

### Provenance Substitution Note

The specified canonical historical object (`research/recovery/mlb_canonical_historical_research_matchup_object/mlb_canonical_historical_research_matchup_object.parquet`) does not exist on disk on either the local machine or the production server. The following specified control files also do not exist:

- `research/orchestration/mlb_research_orchestrator.py`
- `research/orchestration/mlb_research_orchestration_config.json`
- `research/orchestration/mlb_research_object_router.json`
- `research/orchestration/mlb_research_workflow_templates.json`
- `research/orchestration/mlb_research_branch_status_schema.json`
- `research/orchestration/MLB_RESEARCH_ORCHESTRATION_REPORT.md`
- `research/orchestration/MLB_RESEARCH_ORCHESTRATION_REGISTRY.json`
- `research/recovery/mlb_stack_standardization/MLB_STACK_APPROVED_OBJECTS_MANIFEST.json`
- `research/recovery/mlb_stack_standardization/MLB_STACK_BANNED_OBJECTS_MANIFEST.json`

**Substitution used:** `research/recovery/mlb_matchup_table_base/mlb_matchup_table_base.parquet` — the accepted MLB matchup table base (19,804 rows, 107 columns, 2022–2026). This object was verified via its registry and build report. It was built from the accepted substrate stack (lineup state, bullpen features, rolling starter profile, per-start starter) and accepted as the base layer for future matchup research per the MLB Substrate Stack Acceptance Memo (2026-04-15).

Field existence was confirmed by reading the parquet file's column list on the production server. No value distributions were inspected. The object was used only for field-existence and field-classification verification.

---

## 3. ANTI-DUPLICATION CONTEXT

### Source for Anti-Duplication

Repo closeout files for the H03 family were available locally at `research/results/mlb_h03_family_closeout/` (created 2026-04-17 from verified user-confirmed summaries). These provisional closeout artifacts were read and used for anti-duplication screening.

The orchestration registry and branch status schema were unavailable. Anti-duplication therefore relied on:
1. The H03 family provisional closeout memo (local)
2. The verified branch summaries documented in the closeout prompt context

### Patterns Screened Out

| Pattern | Why Excluded |
|---------|-------------|
| **H01-style brittle conjunction** | H01 used a 4-field forced-bullpen-exposure conjunction that was too fragile (validation sign reversal). Any candidate requiring 4+ fields in conjunction is excluded. |
| **H02-style diluted broad flag** | H02 used an overly broad bullpen stress definition. Discovery effect was +0.01 (non-trivial gate failure). Any candidate using a single broad stress indicator without a sharper mechanism is excluded. |
| **H03-family recycle** | H03 tested bullpen stress × own-starter short-outing risk. H03A–D exhausted the family's child branches. Any candidate built on the same interaction (own bullpen stress × own starter outing risk) is excluded. |
| **V1-lite restatement** | Any candidate that reduces to "better team / worse pitcher / worse bullpen" without a state-transition mechanism is excluded. |
| **Generic quality framing** | Any candidate that is really about static pitcher or lineup quality rather than role instability or state transition is excluded. |

---

## 4. CANDIDATES CONSIDERED

Three candidates were seriously evaluated. Two advanced. One was rejected.

### Candidate Rejected: Bullpen Acute Spike Recovery

**Concept:** When a team's bullpen threw an unusually high pitch count in the last game (`bullpen_pitches_last_game` >> `bullpen_pitches_last_3_games` / 3), the bullpen is in an acute recovery state. Arms that normally handle leverage are depleted. The team is forced to use lower-leverage relievers in higher-leverage spots the next day.

**Rejection Reason:** This is too close to H01 (forced bullpen exposure) and H02 (broad bullpen stress). The mechanism — bullpen is tired, therefore forced to use worse arms — is the same core concept that H01/H02 tested from different angles. Measuring it at a 1-game spike frequency does not make it a genuinely different mechanism. Additionally, `high_leverage_available` already captures the downstream consequence (whether top arms are rested). This candidate is an H01/H02 re-skin at a different measurement frequency. **REJECTED.**

---

## 5. CANDIDATES ADVANCED

### MLB_D01 — Opposing Starter Workload Trajectory Collapse

| Field | Value |
|---|---|
| **candidate_id** | MLB_D01 |
| **candidate_name** | Opposing Starter Workload Trajectory Collapse |
| **mechanism_family** | FORCED-ROLE / ROLE-INSTABILITY / STATE-TRANSITION ASYMMETRY |

**mechanism_claim:**
When the opposing starter's recent innings pitched (last 3 starts) have dropped sharply below their longer-term norm (last 10 starts), this signals a state transition: the starter is losing the ability to go deep into games. This forces an involuntary role expansion for the bullpen behind them — bullpen arms that normally pitch 2–3 innings are forced into 4–5 inning roles. The hypothesis is that games where the opposing starter is in workload trajectory collapse produce more total runs than the market expects, because the market anchors on the starter's overall profile rather than the trajectory of their workload decline.

**why_market_might_miss_it:**
Markets price opposing starter quality via ERA, FIP, K/BB rates, and recent results. But workload TRAJECTORY — the gap between short-window and long-window innings per start — requires comparing two rolling windows rather than reading a single stat line. A starter whose last-10 average is 5.5 IP but whose last-3 average is 4.3 IP has undergone a meaningful state transition. This could be masked if the starter's per-inning quality metrics (K%, BB%, contact allowed) remain stable — the market sees a "decent pitcher having short outings" rather than a structural role-transition indicator that the bullpen will be forced into extended duty. The role-transition mispricing is specifically about WHO absorbs the extra innings, not just that the starter is underperforming.

**exact_field_list_needed:**
1. `opp_sp_workload_ip_last_3` (opposing starter average IP, last 3 starts)
2. `opp_sp_workload_ip_last_10` (opposing starter average IP, last 10 starts)

**field_classification_check:**
Both fields are confirmed present in `mlb_matchup_table_base` as approved feature fields (category: Opposing Starter Profile Features — workload subcategory). They are rolling averages computed from the per-start starter substrate. Field existence verified via remote parquet column list read. No value distributions were inspected.

**proposed_test_form:**
Single-split staged hypothesis test. Flag games where the opposing starter is in workload trajectory collapse (short-window IP well below long-window IP). Measure the mean residual (actual total runs minus expected or baseline) for flagged vs. unflagged games across discovery / validation / OOS splits.

**proposed_pre_declared_threshold_logic:**
- **Collapse flag:** `opp_sp_workload_ip_last_10 - opp_sp_workload_ip_last_3 >= 1.0`
- **Domain grounding:** A 1.0 IP gap between windows means the starter's recent outings are a full inning shorter than their longer-term norm. In baseball terms: a starter who averaged 5.5 IP over 10 starts but only 4.5 IP over 3 recent starts has dropped from borderline quality-start territory to clearly-short-outing territory. One full inning of additional bullpen exposure per game is approximately 3–4 extra batters facing non-starter pitching. This threshold is grounded in the standard definition of short vs. adequate outings (5 IP is the conventional dividing line), not derived from data inspection.
- **Grain:** One flag per team-side per game (the team BATTING against the collapsing starter is flagged).

**anti_duplication_explanation:**
- **Not H01:** H01 tested forced BULLPEN exposure via a 4-field conjunction on the team's own bullpen state. D01 tests the OPPOSING STARTER's workload trajectory — a different side of the matchup, a different unit of analysis (starter trajectory vs. bullpen availability), and only 2 fields.
- **Not H02:** H02 tested a broad bullpen stress flag. D01 does not use any bullpen stress fields. It uses starter workload fields exclusively.
- **Not H03:** H03 tested the interaction of own bullpen stress × own starter short-outing risk. D01 tests the opposing starter's workload trajectory as a standalone signal — no interaction term, no own-team bullpen component, and a different side of the matchup (opposing starter, not own starter).
- **Not V1-lite:** D01 is not "the opposing starter is bad." A starter in workload trajectory collapse may have stable quality metrics (K%, BB%, contact allowed) — the signal is specifically about the TRAJECTORY of innings, not the level of quality. This is a state-transition signal, not a static quality signal.
- **Not generic framing:** The mechanism is specifically about role instability — who is forced to absorb innings — not about team quality or lineup strength.

**expected_failure_mode:**
The most likely failure mode is that the market already prices recent starter outings (box scores are public) and adjusts totals accordingly. If so, the flagged games will show no meaningful residual over unflagged games. A secondary failure mode: the workload trajectory collapse flag may be noisy — short recent outings can be caused by blowouts, manager rest decisions, or one bad start rather than a genuine structural decline, diluting the signal.

**recommendation:** ADVANCE_TO_TEST

---

### MLB_D02 — Opposing Starter Pitch Efficiency Deterioration

| Field | Value |
|---|---|
| **candidate_id** | MLB_D02 |
| **candidate_name** | Opposing Starter Pitch Efficiency Deterioration |
| **mechanism_family** | FORCED-ROLE / ROLE-INSTABILITY / STATE-TRANSITION ASYMMETRY |

**mechanism_claim:**
When the opposing starter's pitches per batter faced (ppbf) has risen sharply in recent starts (last 3) compared to their longer-term norm (last 10), this is a leading indicator of forced role transition. Higher ppbf means deeper counts, more foul balls, and faster pitch-count accumulation. A starter throwing 4.3 pitches per batter vs. their norm of 3.9 will reach their pitch-count limit approximately 1 inning earlier. This is a LEADING indicator — it precedes and causes shortened outings, whereas IP decline (D01) is the LAGGING consequence. The hypothesis is that pitch-efficiency deterioration predicts over-performance on game totals because the market does not fully incorporate this granular efficiency trajectory into its starter evaluation.

**why_market_might_miss_it:**
Pitches per batter faced is not a widely reported or market-facing statistic. Markets price K%, BB%, ERA, and recent game results. A starter can maintain decent K/BB rates while becoming markedly less efficient — more foul balls, deeper counts, and more total pitches per at-bat do not show up in traditional stat lines. The ppbf trajectory is invisible to most market participants until it manifests as shortened outings (which is already the lagging indicator). This represents a potential information-timing asymmetry: the efficiency deterioration signal is available before the workload decline becomes obvious in box scores.

**exact_field_list_needed:**
1. `opp_sp_workload_ppbf_last_3` (opposing starter pitches per batter faced, last 3 starts)
2. `opp_sp_workload_ppbf_last_10` (opposing starter pitches per batter faced, last 10 starts)

**field_classification_check:**
Both fields are confirmed present in `mlb_matchup_table_base` as approved feature fields (category: Opposing Starter Profile Features — workload subcategory). They are rolling averages computed from the per-start starter substrate. Field existence verified via remote parquet column list read. No value distributions were inspected.

**proposed_test_form:**
Single-split staged hypothesis test. Flag games where the opposing starter is in pitch-efficiency deterioration (short-window ppbf elevated above long-window ppbf). Measure the mean residual (actual total runs minus expected or baseline) for flagged vs. unflagged games across discovery / validation / OOS splits.

**proposed_pre_declared_threshold_logic:**
- **Deterioration flag:** `opp_sp_workload_ppbf_last_3 - opp_sp_workload_ppbf_last_10 >= 0.3`
- **Domain grounding:** MLB starters typically throw 3.7–4.1 pitches per batter faced. A 0.3 increase represents roughly a 7–8% efficiency loss. Applied across ~25 batters faced per start, this equals ~7.5 extra pitches per game — enough to push a starter from a 95-pitch, 6-inning outing to a 95-pitch, 5-inning outing (reaching the pitch limit one inning sooner). This threshold is grounded in the relationship between pitch count and innings: modern managers typically pull starters at 90–100 pitches, and 7–8 extra pitches per start at the same batter count meaningfully shortens the outing. The 0.3 ppbf threshold was not derived from data inspection.
- **Grain:** One flag per team-side per game (the team BATTING against the deteriorating starter is flagged).

**anti_duplication_explanation:**
- **Not H01:** H01 tested forced bullpen exposure via own-team bullpen state (4-field conjunction). D02 tests opposing starter pitch efficiency — entirely different fields, different side of matchup, no bullpen state component.
- **Not H02:** H02 tested broad bullpen stress. D02 uses no bullpen fields. It measures starter efficiency trajectory exclusively.
- **Not H03:** H03 tested own bullpen stress × own starter short-outing risk. D02 tests the opposing starter's pitch efficiency — no interaction term, no own-team component, and the mechanism is about EFFICIENCY (pitches per batter) rather than OUTING LENGTH (innings pitched). D02 is a leading indicator; H03's short-outing component is a lagging indicator.
- **Not D01 re-skin:** D01 measures workload trajectory collapse (IP decline). D02 measures pitch efficiency deterioration (ppbf increase). These are related but distinct: a starter can have stable recent IP while ppbf is rising (if the manager hasn't yet adjusted the leash), or declining IP while ppbf is stable (if shortened outings are due to manager decisions, not efficiency loss). D02 captures the causal precursor (efficiency loss) while D01 captures the downstream consequence (shorter outings). They measure different things and will flag overlapping but non-identical game sets.
- **Not V1-lite:** D02 is not "the opposing starter is bad." A starter with stable K/BB/contact metrics can have deteriorating pitch efficiency (more foul balls, deeper counts). This is a state-transition signal about how quickly the starter burns through their pitch budget, not a quality signal.

**expected_failure_mode:**
The most likely failure mode is that ppbf variation is mostly noise — driven by the opposing lineup's approach (patient teams drive up ppbf regardless of the starter's condition) rather than the starter's own deterioration. If so, the last-3 vs. last-10 gap will not consistently predict game totals. A secondary failure mode: even if the signal is real, the effect size may be too small to be economically meaningful — the extra ~1 inning of bullpen exposure may add only a fraction of a run, which could be within the market's tolerance.

**recommendation:** ADVANCE_TO_TEST

---

## 6. CANDIDATES REJECTED

| ID | Name | Reason |
|----|------|--------|
| (unnamed) | Bullpen Acute Spike Recovery | Too close to H01/H02 — same core mechanism (bullpen is tired, forced to use worse arms) measured at a different frequency. Re-skin, not a new idea. |

No other candidates were seriously considered within this mechanism family. Ideas outside the family (e.g., park-weather interactions, lineup platoon splits, umpire effects) were excluded per the single-family constraint.

---

## 7. FINAL RECOMMENDATION

**Candidates advanced: 2**
**Advanced IDs: MLB_D01, MLB_D02**

Both candidates are immediately testable with the current matchup table base. Both use exactly 2 fields each from the approved feature set. Both have frozen threshold logic grounded in baseball domain knowledge. Both are within the FORCED-ROLE / ROLE-INSTABILITY / STATE-TRANSITION ASYMMETRY mechanism family.

D01 (IP trajectory collapse) and D02 (ppbf efficiency deterioration) are related but distinct — they measure the lagging consequence and leading indicator of the same underlying phenomenon (opposing starter losing the ability to go deep). If the test prompt runner wishes to test only one, D01 is the more conservative and interpretable choice. If both are tested, their flag overlap should be documented to understand whether they capture independent or redundant information.

Neither candidate is guaranteed to produce a usable edge. Both have plausible failure modes. The recommendation is to test, not to deploy.

---

*Report generated: 2026-04-17*
*Provenance: Canonical object substitution documented. Anti-duplication from local H03 closeout + session context.*
