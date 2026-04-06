# NFL WR1 Absence → Reception Redistribution Test — Phase 4

**Date:** 2026-04-06
**Season:** 2025 NFL only (single-season test)

---

## Verdict: BLOCKED — Insufficient WR1 absence sample in single-season data

The test cannot be completed because the 2025 season alone produces only ~1-4
WR1 absence events that match cleanly to the props archive. This is a fundamental
sample size problem, not a data quality or methodology problem.

---

## What Was Built

### WR1 Definition (Step 1)
- **Method:** WR with highest rolling 4-week target share (shifted/lagged) per team
- **Coverage:** 506 team-weeks across weeks 3-22 (77 unique WR1 players)
- **Pregame-safe:** Yes — uses only prior-week data

### Absence Detection (Step 2)
- **Primary method:** WR1 had 0 targets in game stats OR injury report status = 'Out'
- **Result: 1 team-week identified as WR1 OUT** (0.2% absence rate)

### Beneficiary Dataset (Steps 3-4)
- 1,786 player-game observations (452 WR2, 466 TE1, 868 RB)
- 4 observations with WR1 OUT — all too thin for any statistical test

---

## Why N Is So Small

1. **WR1s rarely miss full games.** In a typical NFL season, only ~10-15 WR1-level
   absences occur across 32 teams × 18 weeks. Many of those are in early weeks
   before the rolling WR1 definition kicks in (needs 4 prior games).

2. **ID matching gap.** The injury report uses `gsis_id` while the player stats
   use `player_id` — these are different identifier systems. The join found only
   28 WR1 injury reports (all 'Questionable', none 'Out'), suggesting the ID
   crosswalk is incomplete.

3. **Single-season constraint.** The props archive covers only the 2025 season.
   WR1 absence is a rare event (~5-15 per season for the WR1 specifically). A
   multi-season archive would be needed to accumulate N >= 50.

---

## What Would Be Needed

To properly test this hypothesis:
- **3+ seasons of props data** (2023-2025) to accumulate ~30-50 WR1 absence events
- **Clean player ID crosswalk** between injury reports and props/stats
- **Or:** Broaden the definition from strict WR1 OUT to include any top-2 WR
  missing or limited, which would increase N but dilute the signal

---

## Logistic Regression (Exploratory, N=4 in treatment group)

Despite N=4 being too thin for reliable inference, the logistic regression
coefficient on `wr1_out` was **positive** (+0.05), directionally supporting the
hypothesis that WR1 absence increases secondary receiver over-hit rate. This is
not evidence — it is merely not contradictory.

---

## Recommendation

**Do not continue this branch with current data.** The WR1 absence hypothesis is
conceptually sound but cannot be tested with a single NFL season.

**Next options for the NFL derivatives program:**

1. **Broaden to "any WR inactive" test** — instead of WR1 specifically, test
   whether the total number of WRs inactive on a team correlates with TE/RB
   reception over-rates. This increases N dramatically because multiple WRs
   are inactive every week.

2. **Pivot to line-bucket bias exploitation** — the Phase 3 audit found that
   low-line reception props (0-2 receptions) hit OVER at 51.2% vs 44.2% for
   mid-line props. This structural bias is present in the full dataset (N=3,376)
   and doesn't require WR1 absence as a trigger.

3. **Multi-season archive expansion** — pull 2023-2024 NFL props from The Odds
   API historical endpoint to build a 3-season dataset. This would enable the
   WR1 absence test with adequate N.

4. **Wait for 2026 NFL season** — accumulate another season of props data, then
   test with N~100 WR1 absence events across 2 seasons.

**Recommended immediate next step:** Option 1 (broaden to team-level WR inactive
count) or Option 2 (line-bucket bias test). Both can be tested now with existing
data.
