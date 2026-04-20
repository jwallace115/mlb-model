# MLB RESEARCH ORCHESTRATION REPORT

**Build Date:** 2026-04-19 (rebuilt after session-loss event)
**Primary Source of Truth:** Local Mac

## Purpose
This orchestration layer governs all future MLB research/engine work by enforcing the frozen MLB Engine V1 Foundation package as the sole approved input source. Rebuilt from the surviving foundation package after the orchestration directory was lost between sessions.

## Default-Deny Rules
| Rule | Setting |
|---|---|
| Default deny | TRUE |
| Repo-wide fallback | FALSE |
| Closest-equivalent substitution | FALSE |
| Opening confirmation required | TRUE |
| Caveat carryforward required | TRUE |
| Exact path validation required | TRUE |

## Session Log
`research/SESSION_LOG.txt` must be checked at every session start. All artifact creation appends to it.

## Frozen Foundation Package Enforced
`research/engine_foundation/mlb_engine_v1_foundation/` — 15 included families, 22 excluded families, 5 caveats.

## Real Current Base Object
`mlb_matchup_table_base` — 19,804 x 107, frozen at `base_object/mlb_matchup_table_base.parquet`.

## Workflow Modes
8 templates: historical_hypothesis_test, historical_child_branch_check, bounded_candidate_generation, economic_reality_check, component_dominance_check, market_structure_check, closeout_memo, governance_audit.

## Final Status
**ORCHESTRATION_READY**
