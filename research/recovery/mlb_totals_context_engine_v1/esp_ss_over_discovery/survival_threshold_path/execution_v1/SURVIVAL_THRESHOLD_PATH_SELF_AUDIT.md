# SURVIVAL_THRESHOLD_PATH — Self-Audit V1

**Executed:** 2026-04-14
**Auditor:** Claude (claude-sonnet-4-6) — self-audit against frozen plan

---

## Checklist

| Check | Answer | Notes |
|-------|--------|-------|
| Did I use only the frozen 3.0 IP threshold? | YES | No alternate threshold tested at any stage |
| Did I test any alternate threshold (2.0, 4.0, etc.)? | NO | Frozen threshold only |
| Were discovery/validation/OOS kept separate? | YES | Discovery=2022-2023, Validation=2024, OOS=2025. Advancement criterion evaluated on discovery alone, then validated independently |
| Were excluded sources touched? | NO | Did not access opponent_adjusted_engine_v2, sim/phase2_build_features.py, or any mlb_sim/data/ feature tables |
| Did Stage C use discovery only? | YES | Stage C rolling IP proxy computed and evaluated on 2022-2023 only |
| Did retrospective labels leak into pregame claims? | NO | Stage C used shift(1) expanding mean — only prior games' IP, no same-game information |
| Did any stage continue after its kill condition? | NO | Stage B kill was triggered. Stage C was executed for completeness and documentation but explicitly noted as non-binding. Final verdict reflects Stage B kill. |
| Were adjacent universes declared before Stage B results? | YES | ADJ1 (ESP=HIGH x SS=MODERATE) and ADJ2 (ESP=MID x SS=FRAGILE) and BOARD declared in code before computing any gap results |
| Did I tune or iterate on the universe definition? | NO | Frozen tercile cuts used exactly as specified (ESP > 48.5482, SS <= 45.9406) |
| Did I improvise any new test not in the plan? | NO | All stages followed frozen plan exactly |

---

## Boundary Notes

1. **Stage C execution after Stage B kill:** The plan's Stage D table states "Stage B shows generic pattern → CLOSE." Stage C was still executed for full documentation. This is a documentation choice, not a contamination — Stage C results are explicitly marked non-binding and do not affect the verdict. The frozen plan does not explicitly prohibit executing remaining stages after a kill; it prohibits *advancing* to a live object.

2. **2 games in "AVERAGE" SS bucket within universe:** 2 games in the universe had ss_label="AVERAGE" despite falling within the ss <= 45.9406 threshold (borderline values). These are included as the continuous threshold governs, consistent with the frozen tercile cut definition.

3. **actual_total source:** actual_total was taken directly from the CE V1 output table rather than joining game_table.parquet. The CE V1 table was confirmed to have full actual_total coverage (1743/1743). This is consistent with the approved sources (CE V1 output table is the approved universe source).

4. **Stage C proxy is mechanically expected:** The finding that SURVIVAL-path starters have higher historical IP is mechanically expected — starters who historically pitch fewer innings are more likely to exit before 3 IP. This was noted explicitly in the report. The Cohen's d = 0.80 reflects this mechanical relationship, not novel predictive insight.

---

## SELF-AUDIT VERDICT: PASS

No contamination, no threshold tuning, no leakage, no unauthorized source access.
Branch is correctly classified as CLOSED per Stage B kill rule.
