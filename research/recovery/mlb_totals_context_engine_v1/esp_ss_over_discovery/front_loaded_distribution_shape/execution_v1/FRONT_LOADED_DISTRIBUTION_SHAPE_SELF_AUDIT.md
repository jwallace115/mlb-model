# FRONT_LOADED_DISTRIBUTION_SHAPE — SELF-AUDIT

**Execution:** V1 | **Date:** 2026-04-14

---

## Protocol Compliance Checklist

| Question | Answer | Notes |
|---|---|---|
| Used only frozen innings 1-3 window? | YES | Window defined in hardening memo; not selected from outcome data |
| Any alternate window tested? | NO | Only inn_1_3 computed; no inn_1_2 or inn_1_4 variants |
| Discovery/validation/OOS kept separate? | YES | Discovery=2022-2023, Validation=2024, OOS=2025; never merged |
| Excluded sources touched? | NO | No live objects, shadow objects, or betting outputs modified |
| Stage C used discovery only? | N/A | Stage C not run; Stage A failed, kill triggered |
| Retrospective outcomes leaked into pregame claims? | NO | inn_1_3_share is a retrospective descriptor; no pregame claim made |
| Any stage continued after kill? | NO | Stage A FAIL triggered immediate close; B and C not run |
| Adjacent universes declared before Stage B results? | YES | ADJ1 and ADJ2 declared before any Stage B computation |

---

## Kill Trigger

Stage A discovery gap = +1.13pp vs +7pp criterion.

The pre-registered kill rule is clear: if the discovery gap does not meet threshold, the test stops. No data from validation or OOS was used to decide whether to continue. Validation and OOS are reported for completeness but played no role in the decision.

---

## Board Sample Validity

The board sample (n=2,000, random_state=42) was declared before Stage A results were computed. It is not a post-hoc selection. It includes games from all universes including the target universe, which creates a slight upward bias in the board baseline — this would make the universe gap appear *smaller* than a pure complement baseline. The gap is +1.1pp even with this mild conservative bias; a complement baseline would likely show a slightly larger gap. This does not change the conclusion (the gap remains far below +7pp regardless).

---

## Inning Cache Integrity

- 5,020 game_pks fetched from MLB Stats API linescore endpoint
- 0 null total_runs entries
- All universe games (1,743) successfully matched
- Cache saved to execution_v1/inning_cache.json before analysis

---

## Window Freeze Confirmation

The innings 1–3 window was frozen in the hardening memo (FRONT_LOADED_DISTRIBUTION_SHAPE_HARDENING_MEMO.md, section 4) based on structural reasoning: this window captures the period before a typical starter removal. No outcome data was consulted to select this window. No alternate windows were tested during this execution.

---

## Adjacent Universe Declaration Order

Per protocol, ADJ1 and ADJ2 were declared before Stage B results were computed:
- ADJ1 (ESP=HIGH x SS=MODERATE): declared in the prompt before any API calls; isolates SS fragility effect
- ADJ2 (ESP=MID x SS=FRAGILE): declared in the prompt before any API calls; isolates ESP magnitude effect

---

## Final Status

FRONT_LOADED_DISTRIBUTION_SHAPE is **CLOSED**. The mechanism was not empirically supported in discovery. No live or shadow behavior is affected. The candidate is removed from the active research queue.
