# NRFI Phase 2 -- Executive Summary

**Date:** 2026-04-11
**Scope:** Starter quality refinement for NRFI pocket selection
**Data:** 9900 games, 5253 with reliable (3+ prior starts) PIT metrics

---

## Bottom Line

Starter quality filtering provides **marginal, inconsistent lift** for NRFI
selection. The critical finding: **starter metrics do NOT improve the already-
strong F5-based pockets** (A/B). They produce negative deltas inside F5<=3.5
and F5<=4.0 -- the market line already prices in starter quality. The only
pocket where starters add genuine lift is **Base C (FG 8.5-9.0 x F5<=4.0)**,
which reaches 78-81% NRFI but with small N (26-69 games) and uncertain
stability.

**Verdict:** Starter quality is a weak incremental signal for NRFI after the
market total is observed. The F5 line and full-game total remain the dominant
filters. Phase 3 should focus on lineup-level or park/weather features instead.

---

## Key Findings

### 1. Starter filtering HURTS inside strong F5 pockets

Inside F5<=3.5 (Base A, NRFI=65.5%) and F5<=4.0 (Base B, NRFI=62.9%),
every starter quality filter tested produced **negative deltas**:

| Base | Filter | N | NRFI% | Delta |
|------|--------|---|-------|-------|
| A (F5<=3.5) | both_FIP<med | 163 | 50.3% | -15.2pp |
| A | both_K%>med | 166 | 58.4% | -7.1pp |
| A | both_WHIP<med | 154 | 55.8% | -9.7pp |
| B (F5<=4.0) | both_FIP<med | 192 | 50.5% | -12.4pp |
| B | both_K%>med | 197 | 54.8% | -8.1pp |
| B | max_BB%<T67 | 525 | 61.0% | -1.9pp |

**Interpretation:** The F5 total already encodes starter quality. Filtering
further selects for games where the market *correctly* expects dominant pitching
but other factors (lineup, park, weather) create scoring. The low F5 line is
already the best available starter-quality filter.

### 2. Base C (FG 8.5-9.0 x F5<=4.0) is the one exception

This narrow pocket (N=103) combines a moderate full-game total with a low F5,
and starter quality adds genuine lift:

| Filter | N | NRFI% | Delta vs 73.8% base |
|--------|---|-------|--------------------|
| both_FIP<med | 26 | 80.8% | +7.0pp |
| min_K%>med | 52 | 78.8% | +5.1pp |
| min_K%>T33 | 69 | 78.3% | +4.5pp |

However, these samples are small and stability is untested.

### 3. Starter quality helps in broader/weaker pockets

Inside FG<=7.5 (Base D) and the F5 4.0-4.5 range, starter overlays produce
small but positive lifts:

| Pocket | Filter | N | NRFI% | Delta |
|--------|--------|---|-------|-------|
| D (FG<=7.5) | both_BB%<med | 309 | 56.3% | +1.2pp |
| D | min_K/BB>med | 655 | 56.2% | +1.1pp |
| D | both_WHIP<med | 294 | 55.8% | +0.7pp |
| F5 4.0-4.5 x FG<=9.0 | mean_K%>med | 1019 | 54.6% | +2.7pp |
| F5 4.0-4.5 x FG<=8.5 | quality_combo | 569 | 55.7% | +1.7pp |

These are below the -135 break-even (57.4%) so not directly actionable at
standard prices.

### 4. Stability is poor for most starter-enriched pockets

Only **B+both_WHIP<med** (season spread 0.024) and **D+both_K%>med** (spread
0.088) show acceptable stability. Most others have season spreads of 0.15-0.60,
indicating the lift is not reliable across years.

### 5. Phase 5 interactions confirm the pattern

Crossing F5 buckets with FG buckets with starter overlays consistently shows:
- F5<=3.5 or F5<=4.0 pockets: starter overlays produce **negative** deltas
- F5=4.0-4.5 pockets: starter overlays produce **small positive** deltas (1-3pp)

## ROI Framework

| Pocket | N | NRFI% | ROI@-135 | ROI@-125 | Actionable? |
|--------|---|-------|----------|----------|-------------|
| Base C+min_K%>T33 | 69 | 78.3% | +36.2% | +40.9% | Maybe (small N) |
| Base A (no filter) | 656 | 65.5% | +14.1% | +18.1% | YES |
| Base B (no filter) | 787 | 62.9% | +9.6% | +13.4% | YES |
| B+both_WHIP<med | 178 | 56.7% | -1.3% | +2.2% | Marginal |
| D+both_WHIP<med | 294 | 55.8% | -2.8% | +0.7% | No |

**The unfiltered F5 pockets (A, B) remain the best actionable NRFI selections.**

## Actionable Recommendations

1. **Do NOT add starter quality filters** to F5<=3.5 or F5<=4.0 NRFI pockets --
   they destroy edge.
2. **Base C (FG 8.5-9.0 x F5<=4.0)** is worth monitoring as a high-conviction
   but low-frequency pocket. Add min_K%>T33 as a soft filter.
3. **For F5 4.0-4.5 games**, mean_K%>median adds ~2pp but still below break-even
   at standard prices. Only actionable at -115 or better.
4. **Phase 3 should focus on**: park factor, weather (wind/temp), and lineup
   contact rate -- these may provide independent signal that the market total
   does not fully encode.
5. **The market total IS the starter quality filter.** This is the core lesson.

## Files

| File | Description |
|------|-------------|
| nrfi_phase2_research_table.parquet | 9900 games with 59 columns including PIT metrics |
| NRFI_PHASE2_FINAL_TABLE.csv | Top 25 pockets ranked by score |
| phase2_full_report.md | Full phase-by-phase output |
| NRFI_PHASE2_EXEC_SUMMARY.md | This file |
