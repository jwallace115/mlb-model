# P09 Monitoring Follow-Up V1

**Date:** 2026-05-12
**Source:** research/mlb/p09_runner_feature_identity_check_v1.md (Amendment — Verdict Reconciliation)

---

## A. Reason

P09 runner implementation was accepted for shadow deployment, but one input-freshness monitoring item remains open from feature-identity reconciliation. The runner's formula identity, signal identity, and PIT skip behavior all passed verification. However, two starters showed hard-hit rolling values that diverged between the runner's data source (pre-built aggregate parquet) and an independent pitch-level reconstruction, due to extra regular-season appearances present in the pitch-level chunks but not yet incorporated into the aggregate at its last rebuild.

---

## B. Source Artifact

`research/mlb/p09_runner_feature_identity_check_v1.md`

Amendment — Verdict Reconciliation (May 12, 2026) records:

- Formula identity: PASS
- Signal identity: PASS
- PIT skip: PASS
- Input freshness parity: PARTIAL
- Raw delta threshold: FAIL (max delta 0.069048 exceeds 0.02 MATCH threshold and 0.05 SOFT MATCH threshold)
- Final push recommendation: SAFE TO PUSH 2acf51fc WITH MONITORING NOTE

---

## C. Players to Re-Check

- Brenan Hanifee — player ID 669724 (max delta 0.069048)
- Keegan Akin — player ID 669211 (max delta 0.050000)

---

## D. Required Trigger

Re-check after the next Statcast aggregate rebuild (`mlb/pipeline/rebuild_statcast_aggregates.py`).

---

## E. Required Check

After the next Statcast aggregate rebuild, rerun the P09 feature-identity comparison and confirm whether the max raw delta drops below 0.02 for:

- Hanifee (669724)
- Akin (669211)

If max raw delta < 0.02:
- Close the monitoring item.
- Cron decision and promotion consideration proceed under their own separate gates.

If max raw delta >= 0.02 on the first re-check after rebuild:
- Flag as persistent freshness divergence.
- Re-check once more after the subsequent Statcast aggregate rebuild.
- Do not close the monitoring item.

If max raw delta remains >= 0.02 after two consecutive rebuild re-checks:
- Escalate to a new P09 feature provenance investigation.
- Block promotion consideration until investigation completes.
- Cron may continue running shadow execution because this re-check is not a shadow-blocker under the reconciliation verdict.

---

## F. Operational Status

- This monitoring item does not block shadow display.
- This monitoring item does not authorize live betting.
- This monitoring item does not authorize promotion.
- This monitoring item does not by itself authorize cron scheduling.
- Cron scheduling requires a separate cron/launchd decision.
- This monitoring item must be resolved before any future P09 promotion consideration.

---

## G. Final Status Block

P09 MONITORING STATUS:
- Issue: Input freshness parity PARTIAL
- Affected players: Hanifee (669724), Akin (669211)
- Formula identity: PASS
- Signal identity: PASS
- Shadow display: NOT BLOCKED
- Cron scheduling: NOT BLOCKED BY THIS MONITORING ITEM; SEPARATE CRON DECISION STILL REQUIRED
- Promotion consideration: BLOCKED UNTIL RE-CHECK COMPLETE
- Trigger: Next Statcast aggregate rebuild
- Required action: Re-run feature-identity comparison
- Escalation: Two consecutive rebuild re-checks with max raw delta >= 0.02
