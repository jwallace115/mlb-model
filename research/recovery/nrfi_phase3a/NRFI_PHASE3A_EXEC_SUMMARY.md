# NRFI Phase 3A -- Executive Summary

**Date:** 2026-04-11
**Scope:** First-inning pitcher splits (PIT-safe) + top-of-order lineup overlay (RESEARCH-ONLY)
**Data:** 9900 games, 3163 with 1st-inning SP metrics, 2240 with top-3 lineup metrics

---

## Safety Provenance

| Variable Class | Provenance | Method |
|---------------|------------|--------|
| sp_1st_era, sp_1st_nrfi_rate | **PIT-SAFE** | Per-game 1st-inning runs from linescore cache, shift(1) expanding mean, min 5 prior starts |
| top3_obp, top3_k_rate, top3_hr_rate | **RESEARCH-ONLY** | Actual batting order from post-game box scores. Cannot be known pre-game. |
| Any interaction using top-3 vars | **RESEARCH-ONLY** | Inherits RESEARCH-ONLY from lineup component |

---

## Bottom Line

First-inning pitcher NRFI rate (PIT-safe, built from per-game linescore data with shift(1)) provides
**0 positive-delta overlays inside Gates A/B** (the strongest F5-based pockets).
This is consistent with Phase 2: the F5 market line already encodes starter quality,
including first-inning tendencies.

Top-3 lineup metrics (RESEARCH-ONLY) show some signal for NRFI selection,
but are **not usable in production** because actual batting order is unknown pre-game.

**Verdict:** First-inning pitcher NRFI rate adds marginal but positive lift
in broader pockets (D, E) but not inside the already-strong F5 pockets (A, B). The unfiltered
F5-based pockets remain the primary actionable NRFI selections.

---

## Key Findings

### 1. PIT-Safe First-Inning SP Overlays (positive delta, N>=30)

| Pocket | N | NRFI% | Delta | Stab | ROI@-135 |
|--------|---|-------|-------|------|----------|
| C+both_sp_nrfi>0.6 | 109 | 80.7% | +5.7pp | 0.058 | +40.5% |
| C+both_sp_nrfi>0.7 | 76 | 80.3% | +5.3pp | 0.085 | +39.7% |
| C+both_sp_nrfi>T67 | 50 | 80.0% | +5.0pp | 0.139 | +39.3% |
| C+max_sp_era<med | 90 | 80.0% | +5.0pp | 0.070 | +39.3% |
| C+mean_sp_era<med | 80 | 80.0% | +5.0pp | 0.118 | +39.3% |
| C+max_sp_era<0.3 | 54 | 79.6% | +4.6pp | 0.092 | +38.6% |
| C+both_sp_nrfi>med | 67 | 79.1% | +4.1pp | 0.061 | +37.7% |
| C+min_sp_nrfi>med | 53 | 77.4% | +2.4pp | 0.131 | +34.7% |
| D+both_sp_nrfi>T67 | 796 | 56.4% | +0.7pp | 0.040 | -1.8% |
| D+mean_sp_era<med | 989 | 56.3% | +0.6pp | 0.028 | -2.0% |
| D+min_sp_nrfi>med | 817 | 56.2% | +0.4pp | 0.029 | -2.2% |
| D+both_sp_nrfi>med | 1012 | 56.1% | +0.4pp | 0.042 | -2.3% |

### 2. RESEARCH-ONLY Top-3 Lineup Overlays (positive delta, N>=30)

| Pocket | N | NRFI% | Delta | Stab | ROI@-135 | Provenance |
|--------|---|-------|-------|------|----------|------------|
| C+sp_nrfi>med+top3_k>med [RO] | 37 | 89.2% | +14.2pp | 0.200 | +55.3% | RESEARCH-ONLY |
| C+both_top3_k>med [RO] | 76 | 81.6% | +6.6pp | 0.224 | +42.0% | RESEARCH-ONLY |
| C+both_top3_k>T67 [RO] | 54 | 81.5% | +6.5pp | 0.217 | +41.8% | RESEARCH-ONLY |
| C+max_sp_era<med+max_obp<med [RO] | 44 | 79.5% | +4.5pp | 0.035 | +38.5% | RESEARCH-ONLY |
| C+both_top3_obp<T33 [RO] | 45 | 75.6% | +0.6pp | 0.220 | +31.5% | RESEARCH-ONLY |
| A+both_top3_k>med [RO] | 423 | 67.1% | +1.6pp | 0.118 | +16.9% | RESEARCH-ONLY |
| A+both_top3_k>T67 [RO] | 311 | 66.9% | +1.4pp | 0.117 | +16.4% | RESEARCH-ONLY |
| A+sp_nrfi>med+top3_k>med [RO] | 233 | 66.5% | +1.0pp | 0.286 | +15.8% | RESEARCH-ONLY |
| A+both_top3_obp<T33 [RO] | 310 | 66.1% | +0.6pp | 0.093 | +15.1% | RESEARCH-ONLY |
| A+max_top3_obp<med [RO] | 520 | 65.8% | +0.2pp | 0.069 | +14.5% | RESEARCH-ONLY |
| B+both_top3_k>med [RO] | 489 | 65.6% | +2.4pp | 0.046 | +14.3% | RESEARCH-ONLY |
| A+both_top3_obp<med [RO] | 409 | 65.5% | +0.0pp | 0.019 | +14.1% | RESEARCH-ONLY |

### 3. Credible Overlays (N>=50, delta>0, stability<0.15, 3+ seasons)

**PIT-safe credible:** 20
**RESEARCH-ONLY credible:** 21

| Pocket | N | NRFI% | Delta | Stab | ROI@-135 | Provenance |
|--------|---|-------|-------|------|----------|------------|
| C+both_sp_nrfi>0.6 | 109 | 80.7% | +5.7pp | 0.058 | +40.5% | PIT-SAFE |
| C+both_sp_nrfi>0.7 | 76 | 80.3% | +5.3pp | 0.085 | +39.7% | PIT-SAFE |
| C+both_sp_nrfi>T67 | 50 | 80.0% | +5.0pp | 0.139 | +39.3% | PIT-SAFE |
| C+mean_sp_era<med | 80 | 80.0% | +5.0pp | 0.118 | +39.3% | PIT-SAFE |
| C+max_sp_era<med | 90 | 80.0% | +5.0pp | 0.070 | +39.3% | PIT-SAFE |
| C+max_sp_era<0.3 | 54 | 79.6% | +4.6pp | 0.092 | +38.6% | PIT-SAFE |
| C+both_sp_nrfi>med | 67 | 79.1% | +4.1pp | 0.061 | +37.7% | PIT-SAFE |
| C+min_sp_nrfi>med | 53 | 77.4% | +2.4pp | 0.131 | +34.7% | PIT-SAFE |
| A+both_top3_k>med [RO] | 423 | 67.1% | +1.6pp | 0.118 | +16.9% | RESEARCH-ONLY |
| A+both_top3_k>T67 [RO] | 311 | 66.9% | +1.4pp | 0.117 | +16.4% | RESEARCH-ONLY |
| A+both_top3_obp<T33 [RO] | 310 | 66.1% | +0.6pp | 0.093 | +15.1% | RESEARCH-ONLY |
| A+max_top3_obp<med [RO] | 520 | 65.8% | +0.2pp | 0.069 | +14.5% | RESEARCH-ONLY |
| B+both_top3_k>med [RO] | 489 | 65.6% | +2.4pp | 0.046 | +14.3% | RESEARCH-ONLY |
| A+both_top3_obp<med [RO] | 409 | 65.5% | +0.0pp | 0.019 | +14.1% | RESEARCH-ONLY |
| B+both_top3_k>T67 [RO] | 362 | 64.9% | +1.6pp | 0.066 | +13.0% | RESEARCH-ONLY |
| B+sp_nrfi>med+top3_k>med [RO] | 261 | 64.8% | +1.5pp | 0.148 | +12.7% | RESEARCH-ONLY |
| B+both_top3_obp<T33 [RO] | 363 | 64.5% | +1.2pp | 0.063 | +12.2% | RESEARCH-ONLY |
| B+max_top3_obp<med [RO] | 618 | 63.6% | +0.3pp | 0.072 | +10.7% | RESEARCH-ONLY |
| D+sp_nrfi>med+top3_k>med [RO] | 382 | 60.5% | +4.7pp | 0.095 | +5.3% | RESEARCH-ONLY |
| D+both_top3_k>T67 [RO] | 552 | 59.1% | +3.3pp | 0.042 | +2.8% | RESEARCH-ONLY |
| D+both_top3_k>med [RO] | 752 | 58.8% | +3.0pp | 0.041 | +2.3% | RESEARCH-ONLY |
| D+max_sp_era<med+max_obp<med [RO] | 615 | 56.9% | +1.2pp | 0.103 | -0.9% | RESEARCH-ONLY |
| D+both_top3_obp<T33 [RO] | 647 | 56.7% | +1.0pp | 0.109 | -1.3% | RESEARCH-ONLY |
| D+both_sp_nrfi>T67 | 796 | 56.4% | +0.7pp | 0.040 | -1.8% | PIT-SAFE |
| D+mean_sp_era<med | 989 | 56.3% | +0.6pp | 0.028 | -2.0% | PIT-SAFE |
| D+min_sp_nrfi>med | 817 | 56.2% | +0.4pp | 0.029 | -2.2% | PIT-SAFE |
| D+both_sp_nrfi>med | 1012 | 56.1% | +0.4pp | 0.042 | -2.3% | PIT-SAFE |
| D+max_top3_obp<med [RO] | 1052 | 56.1% | +0.3pp | 0.089 | -2.4% | RESEARCH-ONLY |
| D+both_sp_nrfi>0.6 | 1486 | 56.1% | +0.3pp | 0.029 | -2.4% | PIT-SAFE |
| E+both_top3_obp<T33 [RO] | 949 | 55.0% | +3.3pp | 0.100 | -4.3% | RESEARCH-ONLY |
| E+both_top3_obp<med [RO] | 1335 | 54.2% | +2.5pp | 0.062 | -5.6% | RESEARCH-ONLY |
| E+max_top3_obp<med [RO] | 1638 | 54.0% | +2.3pp | 0.043 | -6.1% | RESEARCH-ONLY |
| E+max_sp_era<med+max_obp<med [RO] | 944 | 53.7% | +2.0pp | 0.085 | -6.5% | RESEARCH-ONLY |
| E+sp_nrfi>med+top3_obp<med [RO] | 576 | 53.6% | +2.0pp | 0.071 | -6.6% | RESEARCH-ONLY |
| E+min_sp_nrfi>med | 1132 | 52.7% | +1.1pp | 0.054 | -8.2% | PIT-SAFE |
| E+both_sp_nrfi>0.7 | 1680 | 52.6% | +0.9pp | 0.036 | -8.4% | PIT-SAFE |
| E+both_sp_nrfi>T67 | 1029 | 52.5% | +0.8pp | 0.061 | -8.6% | PIT-SAFE |
| E+both_sp_nrfi>0.6 | 2397 | 52.2% | +0.5pp | 0.037 | -9.1% | PIT-SAFE |
| E+max_sp_era<0.3 | 1050 | 52.2% | +0.5pp | 0.063 | -9.1% | PIT-SAFE |
| E+mean_sp_era<med | 1722 | 52.1% | +0.4pp | 0.042 | -9.3% | PIT-SAFE |
| E+both_sp_nrfi>med | 1439 | 51.9% | +0.2pp | 0.042 | -9.6% | PIT-SAFE |

---

## Ranking v2 (Top 15)

| Rank | Pocket | N | NRFI% | Delta | Stab | ROI@-135 | Provenance | Score |
|------|--------|---|-------|-------|------|----------|------------|-------|
| 1 | D+both_sp_nrfi>0.6 | 1486 | 56.1% | +0.3pp | 0.029 | -2.4% | PIT-SAFE | 3.976 |
| 2 | E+both_sp_nrfi>0.6 | 2397 | 52.2% | +0.5pp | 0.037 | -9.1% | PIT-SAFE | 3.913 |
| 3 | B+both_top3_k>med [RO] | 489 | 65.6% | +2.4pp | 0.046 | +14.3% | RESEARCH-ONLY | 3.880 |
| 4 | A+both_top3_obp<med [RO] | 409 | 65.5% | +0.0pp | 0.019 | +14.1% | RESEARCH-ONLY | 3.867 |
| 5 | A+max_top3_obp<med [RO] | 520 | 65.8% | +0.2pp | 0.069 | +14.5% | RESEARCH-ONLY | 3.830 |
| 6 | E+max_top3_obp<med [RO] | 1638 | 54.0% | +2.3pp | 0.043 | -6.1% | RESEARCH-ONLY | 3.823 |
| 7 | B+max_top3_obp<med [RO] | 618 | 63.6% | +0.3pp | 0.072 | +10.7% | RESEARCH-ONLY | 3.794 |
| 8 | D+mean_sp_era<med | 989 | 56.3% | +0.6pp | 0.028 | -2.0% | PIT-SAFE | 3.776 |
| 9 | E+both_sp_nrfi>0.7 | 1680 | 52.6% | +0.9pp | 0.036 | -8.4% | PIT-SAFE | 3.767 |
| 10 | D+both_top3_k>med [RO] | 752 | 58.8% | +3.0pp | 0.041 | +2.3% | RESEARCH-ONLY | 3.733 |
| 11 | D+both_sp_nrfi>med | 1012 | 56.1% | +0.4pp | 0.042 | -2.3% | PIT-SAFE | 3.721 |
| 12 | E+mean_sp_era<med | 1722 | 52.1% | +0.4pp | 0.042 | -9.3% | PIT-SAFE | 3.718 |
| 13 | E+both_top3_obp<med [RO] | 1335 | 54.2% | +2.5pp | 0.062 | -5.6% | RESEARCH-ONLY | 3.662 |
| 14 | D+min_sp_nrfi>med | 817 | 56.2% | +0.4pp | 0.029 | -2.2% | PIT-SAFE | 3.656 |
| 15 | E+both_sp_nrfi>med | 1439 | 51.9% | +0.2pp | 0.042 | -9.6% | PIT-SAFE | 3.616 |

---

## ROI Framework

Break-even at -135: 57.4% | Break-even at -125: 55.6%

---

## Actionable Recommendations

1. **F5 <= 3.5 and F5 <= 4.0 remain the best NRFI filters** -- first-inning pitcher overlays do not reliably improve them.
2. **First-inning SP NRFI rate** is a PIT-safe variable computable in production, but marginal value is low inside F5-gated pockets.
3. **Top-3 lineup metrics are RESEARCH-ONLY** -- they confirm lineup quality matters for 1st-inning scoring, but cannot be operationalized pre-game.
4. **Phase 3B should explore:** park factor (dome/outdoor), temperature, and month effects as independent signals.

---

## Files

| File | Description |
|------|-------------|
| nrfi_phase3a_research_table.parquet | 9900 games with 1st-inning SP + top-3 lineup metrics |
| NRFI_PHASE3A_FINAL_TABLE.csv | Top 40 pockets ranked by composite score |
| phase3a_build.py | Full build script |
| NRFI_PHASE3A_EXEC_SUMMARY.md | This file |
