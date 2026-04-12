# Phase 1 — F5/FG Path Mismatch Design Review + Verdict

**Date:** 2026-04-12
**Object:** F3 (F5/FG Path Mismatch)
**Prior classification:** RETEST REQUIRED
**Research file:** research/mlb_path_mismatch/phase1_f5_vs_fullgame_path_mismatch.md

---

## What the Hypothesis Was

When the F5 closing line is LOW relative to the full-game closing total
("late-heavy" games), the market implies most scoring comes in late innings.
When the F5 line is HIGH relative to the full-game total ("early-heavy" games),
the market implies scoring is frontloaded.

The hypothesis: the market systematically misprices this split, creating
exploitable F5 over/under opportunities.

## What the Research Found

### Real Finding

The F5 market does underadjust for game quality. When the full-game total is 9+,
the F5 line stays at 4.5 in most games. Actual F5 scoring in these games averages
5.26. The difference between HIGH_LATE_INFLATION F5 over rate (53.4%) and
HIGH_EARLY_INFLATION F5 under rate (53.7%) is statistically significant (p=0.0004).

### Why It Is Not Actionable

1. **Artifact-dominated.** 71.1% of F5 lines are exactly 4.5. The "mismatch"
   is not two markets independently disagreeing; it is the F5 market lacking
   granularity. The late_ratio feature is 71% a pure function of the FG line.

2. **Thin edge.** 53.7% win rate at -110 yields +2.5% ROI. After realistic
   juice (-115 to -120 on many F5 unders), this is breakeven or negative.

3. **One-sided stability.** F5 OVER on HIGH_LATE_INFLATION collapsed from
   +6.6% ROI in 2024 to -2.2% in 2025. Only the UNDER side holds.

4. **Redundant.** "Bet F5 under when FG total < 8.0 and F5 line >= 4.5"
   captures the same effect without the mismatch framework.

5. **No full-game application.** Zero signal for full-game over/under decisions.

### Existing Research Verdict

The research file concludes: **NEAR MISS** — the effect is real but not
independently profitable after vig. The only potential use is as a confidence
booster for an existing F5 model's UNDER signal.

## Updated Verdict: ARCHIVE

**Rationale:** The research is complete and thorough. The effect is real but
not exploitable as a standalone signal. No further testing is warranted.

The only potential future use case (F5 UNDER confidence booster) requires
an F5 model that does not yet exist (D6 is DEFERRED / not built). Since
Signal B (the only F5 object) is now ARCHIVED and no F5 totals model
survived decontamination, there is no parent to boost.

**Action:** Reclassify F3 from RETEST REQUIRED to ARCHIVE. No further work.
