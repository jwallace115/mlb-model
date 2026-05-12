# ADJ Family Formal No-Go Decision V1

**Decision date:** 2026-05-12
**Source of truth:** research/mlb/mlb_system_registry_v2.md (Section B, row 17; Section C, entry 17)
**Supporting evidence:** research/recovery/adj_standalone_rebuild/ADJ_MASTER_KEEP_KILL_MEMO.md

---

## A. Decision

The ADJ family is formally classified as **VALIDATED_NEGATIVE_DEAD**.

The prior May 15 activation concept is **cancelled**.

ADJ is not approved for:
- live betting
- shadow-card deployment
- dashboard promotion
- automated scheduling
- any activation based on calendar date alone

---

## B. Basis for Decision

**Registry v2 classification (Section B, row 17):**

> ADJ Family | FG UNDER | negative (DIMINISHED) | real closing | VALIDATED_NEGATIVE_DEAD | All 5 DIMINISHED

**Registry v2 detail (Section C, entry 17):**

> STATUS: VALIDATED_NEGATIVE_DEAD. All 5 signals DIMINISHED per `research/recovery/adj_standalone_rebuild/ADJ_MASTER_KEEP_KILL_MEMO.md`. Identity MISMATCH: live fires on `combined > 0` alone; research required `p_under > 0.57` co-filter. ADJ May 15 activation remains DELAYED.

**Registry v1 review (Section E, drift table):**

> "ADJ family deploy-ready" → All 5 DIMINISHED → DRIFT

**ADJ Master Keep/Kill Memo findings:**
- All 5 signals returned DIMINISHED verdicts across 2022-2025 backtests
- Overall ROI negative for all 5 signals (ranging from -0.6% to -3.6%)
- Identity MISMATCH: live code fires on `combined > 0` alone; original research required `p_under > 0.57` co-filter — the live system is a different, weaker signal than what was validated
- 2025 showed improvement for some signals, but this does not overcome multi-year negative ROI or the identity mismatch

**Calendar date is not evidence of readiness.**

A system flagged for "activation on date X" without passing all validation gates between classification and date X is not activatable on date X. The May 15 activation plan was a forward-looking placeholder, not a validated deployment decision. When registry v2 classified ADJ as VALIDATED_NEGATIVE_DEAD, the placeholder lost its ground.

This principle applies to any future "activation on date X" plan in the system. Date alone is not a green light. Validation status at date X is the gate.

---

## C. Systems Covered

The following 5 ADJ-family systems are covered by this no-go decision, extracted directly from `research/recovery/adj_standalone_rebuild/ADJ_MASTER_KEEP_KILL_MEMO.md`:

| System | Verdict | Overall N | Overall ROI |
|---|---|---|---|
| ADJ_CONTACT | DIMINISHED | 3,875 | -2.4% |
| ADJ_HH | DIMINISHED | 3,081 | -2.6% |
| adj_k_rate_last3 | DIMINISHED | 1,539 | -0.6% |
| ADJ_BB_RATE | DIMINISHED | 1,587 | -3.6% |
| ADJ_RUN_SUPP | DIMINISHED | 3,159 | -1.8% |

Registry v2 (Section B, row 17) classifies the family collectively as VALIDATED_NEGATIVE_DEAD. The memo lists exactly 5 signals, matching the expected count.

---

## D. Operational Rules

- Do not activate ADJ on May 15.
- Do not place ADJ on any live/shadow card.
- Do not use ADJ in dashboards as an active candidate.
- Do not treat ADJ as paused, pending, waiting for date maturity, or waiting for sample only.
- Treat ADJ as dead unless reopened through the process in Section F.

---

## E. Allowed References

ADJ may still be referenced as:
- historical research
- negative validation example
- audit precedent
- future research inspiration only if clearly labeled dead/archived

ADJ may not be referenced as:
- active
- shadow-ready
- activation-ready
- pending May 15
- waiting for sample only
- paused pending maturity
- monitoring-only without written approval

---

## F. Reopen Conditions

ADJ may only be reopened by a separate future research cycle that includes:

1. New written spec.
2. Fresh feature provenance audit.
3. Research/live object identity check.
4. Fresh validation using non-contaminated discovery/validation separation.
5. Real-market economic test.
6. Explicit registry update.
7. Explicit operator approval before any shadow or live deployment.

For this project, operator approval means Jeff approval.

Approval must be:
- written
- explicit
- recorded in a durable artifact
- not verbal
- not implied from discussion
- not inferred from a calendar date

No automatic reopen.
No date-based reopen.
No "monitoring only" exception without written approval.

---

## G. Final Status

ADJ FAMILY FINAL STATUS:
- Classification: VALIDATED_NEGATIVE_DEAD
- Source of truth: research/mlb/mlb_system_registry_v2.md
- Decision date: 2026-05-12
- May 15 activation: CANCELLED
- Live betting: NOT AUTHORIZED
- Shadow deployment: NOT AUTHORIZED
- Dashboard promotion: NOT AUTHORIZED
- Reopen path: NEW RESEARCH CYCLE ONLY, see Section F
