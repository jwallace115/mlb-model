# NHL Archetype Layering Test — Phase 5

**Date:** 2026-04-06
**Data:** 5,248 games, 4 NHL seasons, confirmed-starter subset

---

## Verdict: CLOSE — Sample too thin for layering conclusions

The live NHL model fires edge >= 0.12 on only **24 confirmed-starter games across
4 seasons**. This is far too few games to meaningfully test archetype conditioning.
No split produces cells with N >= 30. All results below are directionally
interesting but statistically meaningless.

---

## Why N = 24

The NHL model uses a high edge threshold (>= 0.12) and the confirmed-starter gate
further reduces the sample. Of the 1,805 confirmed-starter games in the dataset,
only 24 (1.3%) have model edge >= 0.12 for the over side. This is by design —
the NHL model is selective — but it means layering tests require many more seasons
of data to reach usable sample sizes.

---

## Baseline (for reference only — N=24)

| Metric | Value |
|--------|-------|
| N | 24 |
| Over hit rate | 54.2% |
| Fair implied | 50.2% |
| Residual | +4.0pp |
| ROI at -110 | +3.4% |

The baseline looks promising but is heavily season-dependent:
- 2021: N=16, Over=75.0% (drives the average)
- 2024: N=6, Over=16.7%

This is noise, not signal, at N=24.

---

## Edge Conditioning (all cells N < 15)

### Branch 8 (Process Dominance)

| Context | N | Over% | Residual | ROI |
|---------|---|-------|----------|-----|
| FAVORABLE | 14 | 57.1% | +8.0pp | +9.1% |
| NEUTRAL | 10 | 50.0% | -1.6pp | -4.5% |
| UNFAVORABLE | 0 | — | — | — |

### Branch 7 (Special Teams Net)

| Context | N | Over% | Residual | ROI |
|---------|---|-------|----------|-----|
| FAVORABLE | 9 | 66.7% | +17.3pp | +27.3% |
| NEUTRAL | 9 | 33.3% | -18.0pp | -36.4% |
| UNFAVORABLE | 6 | 66.7% | +16.8pp | +27.3% |

Branch 7 UNFAVORABLE showing 66.7% over (N=6) — this is pure noise. The labels
are not functioning as expected at this sample size.

---

## Threshold Modifier (N < 20)

| Test | N | Over% | Baseline |
|------|---|-------|----------|
| edge >= 0.10 + B8 FAVORABLE | 19 | 63.2% | 54.2% |
| edge >= 0.10 + B7 FAVORABLE | 13 | 53.8% | 54.2% |

Directionally interesting (Branch 8 at 63.2%) but N=19 is far below the minimum
needed for confidence.

---

## Combined Layer (N < 10)

| Combined | N | Over% |
|----------|---|-------|
| Both FAVORABLE | 8 | 75.0% |
| Either UNFAVORABLE | 6 | 66.7% |

N=8 and N=6. These numbers are meaningless.

---

## CLV Check

Market snapshot data exists (opening_total and line_movement columns in
`nhl_market_snapshots.parquet`). However, with N=24 total edge games, CLV
analysis would be unreliable.

---

## Decision

| Framing | Result | Status |
|---------|--------|--------|
| CONFIDENCE LAYER | Cannot evaluate — N < 30 in every cell | **CLOSE** |
| PASS FILTER | Cannot evaluate — UNFAVORABLE cell N=6 | **CLOSE** |
| THRESHOLD MODIFIER | Directionally interesting (N=19) but below minimum | **CLOSE** |

**All framings fail the minimum sample requirement.** The NHL model's high
selectivity (edge >= 0.12 fires on only 1.3% of games) makes conditional
layering tests infeasible with 4 seasons of data.

---

## Recommendations

1. **Close the NHL archetype research program.** Five phases tested, no deployable
   finding survived practical validation.

2. **The structural framework is architecturally sound** — archetypes are real,
   interpretable, and stable across seasons. But the NHL totals market efficiently
   prices process-stat information, and the live model's high selectivity leaves
   too few games for conditional analysis.

3. **If revisiting in the future:**
   - Accumulate 8+ seasons of data for the layering test to reach N >= 100
   - Or lower the model edge threshold to generate more signal games
   - Or test archetypes on a different NHL market (period totals, team totals)
     where the market may be less efficient

4. **The only actionable NHL finding from this program:** Phase 2's backup-goalie
   interaction (+3.3pp in backup-goalie games within certain archetype cells).
   This could be folded into the existing goalie-state logic in the live model
   rather than treated as an archetype overlay.
