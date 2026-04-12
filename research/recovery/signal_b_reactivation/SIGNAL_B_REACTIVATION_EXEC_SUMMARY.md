# Signal B (F5 Run Line Home) — Reactivation Executive Summary
Generated: 2026-04-12

## Verdict: SHADOW (not reactivated)

Signal B is clean, independent, and operationally functional.
However, the live threshold was never updated from 1.0 to 1.5 as directed
by the reset audit. This audit found and fixed the discrepancy.
Reactivation requires 30+ resolved signals at the corrected 1.5 threshold.

## Critical Finding
The reset audit (2026-04-11) directed two changes that were NOT implemented:
1. **Threshold:** Code still used 1.0 (should be 1.5) -- FIXED in this audit
2. **Status:** File still said ACTIVE (should be SHADOW) -- FIXED in this audit

The tracker had 7 entries, 6 of which fired under the old 1.0 threshold
and would NOT have fired at 1.5. These are legacy signals from an
invalidated threshold era.

## Fixes Applied
| Fix | File | Change |
|-----|------|--------|
| Threshold | `mlb_sim/pipeline/f5_runline_signal_generator.py` | `XFIP_GAP_THRESHOLD = 1.0` -> `1.5` |
| Docstring | Same file | Updated to "xFIP mismatch >= 1.5" |
| Status | `mlb_sim/pipeline/f5_runline_status.json` | `"ACTIVE"` -> `"SHADOW"` |

## Identity Audit Results
| Check | Result |
|-------|--------|
| xFIP source | CLEAN (live FanGraphs API) |
| V1 dependency | NONE |
| S12/P09 dependency | NONE |
| Contaminated tables | NONE |
| Home-only routing | CORRECT |
| Grading logic | CORRECT |
| Hard stop | CORRECT (-10% at N>=40) |
| Operational wiring | CORRECT (run_model.py, push_results.py) |

## Tracker State
| Metric | Value |
|--------|-------|
| Total entries | 7 |
| Entries at gap >= 1.5 | 1 |
| Entries at gap < 1.5 (legacy) | 6 |
| Record at >= 1.5 | 0-1-0 |
| Record at < 1.5 (legacy, invalid) | 2-4-0 |

## Reactivation Gate
- **Required:** 30+ resolved signals at gap >= 1.5
- **Current:** 1 resolved signal at gap >= 1.5
- **Estimated timeline:** ~September 2026 (~0.2 signals/day)
- **Status until gate:** SHADOW (signals fire and log, not live-traded)

## Dry Run (2026-04-12)
- 15 games on today slate
- 0 signals fire (max gap = +0.404, well below 1.5)
- All imports, data sources, and operational paths confirmed working

## Files Created
- `phase0_locked_spec.md` — Full signal definition and threshold history
- `phase1_parity_audit.md` — Line-by-line implementation vs spec check
- `phase2_tracker_audit.md` — Tracker contents and mixed-threshold analysis
- `phase3_implementation_fixes.md` — Changes made to code
- `phase4_operational_path.md` — Daily execution chain verification
- `phase5_dry_run.md` — Today dry run results
- `phase6_website_state.md` — Dashboard and push pipeline state
- `phase7_reactivation_decision.md` — Gate assessment and timeline
- `signal_b_audit_table.csv` — Machine-readable audit table
