# Phase 7 — WHIFF Archetype Overlay on NRFI Parlay Helper

**Date:** 2026-04-06
**Design:** Phase 4 Rule D pool + Phase 6 WHIFF starter archetype. Train 2024, test 2025.

---

## Verdict: CLOSE BRANCH. Phase 4 Rule D stands as-is.

The WHIFF overlay fails the both-year consistency criterion. It improves the
2025 OOS pool (+2.7pp) but HURTS the 2024 in-sample pool (-1.8pp). This is
a year-specific effect, not a stable structural improvement.

---

## Test Results

### Test 1 — WHIFF Filter Variants

| Variant | N 2024 | NRFI 2024 | N 2025 | NRFI 2025 | vs Phase 4 |
|---------|--------|-----------|--------|-----------|-----------|
| Phase 4 Rule D (baseline) | 67 | .597 | 81 | .568 | — |
| A) At least one WHIFF | 38 | **.579** | 42 | **.595** | +.027 (2025), -.018 (2024) |
| B) Both WHIFF | 9 | .889 | 3 | — | N too small |
| C) Away SP WHIFF only | 26 | .538 | 24 | .500 | Worse in both years |
| D) Home SP WHIFF only | 21 | **.762** | 21 | **.714** | Best single variant |

**Variant D (Home SP WHIFF)** shows the strongest raw effect — 71.4% NRFI in
2025 and 76.2% in 2024. But N=21 per year is below the N>=30 threshold.

**Variant A** passes N>=30 (N=42) and +2pp improvement (+2.7pp in 2025), but
fails both-year consistency: NRFI drops from .597 to .579 in 2024.

### Test 2 — DAMAGE vs STABLE Conflict Exclusion

| Year | With all games | Excluding DAMAGE/STABLE | Delta |
|------|---------------|------------------------|-------|
| 2024 | .600 (N=60) | .574 (N=47) | **-2.6pp (worse)** |
| 2025 | .542 (N=72) | .533 (N=60) | -0.8pp |

Excluding DAMAGE vs STABLE matchups hurts the pool in both years. The Phase 4
model already accounts for this matchup quality through its feature set.

### Test 3 — Parlay Simulation (Variant A, 2025 OOS)

| Method | 3-leg | 5-leg |
|--------|-------|-------|
| Random | 14.3% | 3.4% |
| Phase 4 Rule D | 17.4% | 4.7% |
| Phase 4 + WHIFF(A) | **20.3%** | **6.0%** |

The 3-leg improvement (+2.9pp over Phase 4) is real but driven by one year only.

### Fragility Check (Variant A, 2025)

| Removal | N | NRFI |
|---------|---|------|
| Full | 42 | .595 |
| Remove top-5 teams | 13 | **.692** |

Survives team removal — but N=13 after removal is too small to be conclusive.

---

## Decision Criteria

| Criterion | Result | Status |
|-----------|--------|--------|
| Improvement >= +2pp in 2025 OOS | +2.7pp | **PASS** |
| N >= 30 in 2025 OOS | 42 | **PASS** |
| Directionally consistent both years | 2024: -.018, 2025: +.027 | **FAIL** |
| Fragility check survives | Yes (N=13, .692) | **MARGINAL** |

The WHIFF overlay passes 2 of 4 criteria. The critical failure is both-year
consistency: the overlay improves 2025 but hurts 2024.

---

## Interpretation

The WHIFF archetype identifies a real structural feature — high-whiff starters
suppress first-inning contact. But this information is partially captured by the
existing Phase 4 micro model through:
- `home_sp_tto1` (TTO1 wOBA, which correlates with whiff rate)
- `hsp_era_r5` / `asp_era_r5` (pitcher quality, which tracks whiff)

The WHIFF flag adds a small increment in 2025 but subtracts in 2024, suggesting
the overlap between the micro model features and the WHIFF archetype is
year-dependent. This is not a stable structural improvement.

**Variant D (Home SP WHIFF only)** is the most interesting single finding —
76.2% NRFI in 2024, 71.4% in 2025, consistent both years. But N=21 per year
is too small to be actionable. If the NRFI helper accumulates more data through
2026. this variant could be re-evaluated once N reaches 50+ per year.

---

## Conclusion

The first-inning research program is now complete across 7 phases:

| Phase | Branch | Verdict |
|-------|--------|---------|
| 1 | Broad + Micro baseline | Micro marginally better, both weak |
| 2 | NRFI suppression test | Low-total leakage, no market edge |
| 3 | Top-card vs starter interaction | No improvement over baselines |
| 4 | **Parlay helper rules** | **KEEP — deployed as shadow tracker** |
| 5 | Lineup surprise / state change | No practical filter value |
| 6 | First-inning archetypes | Real structure found, limited by cell size |
| 7 | WHIFF overlay on Phase 4 | Fails both-year consistency |

**Phase 4 Rule D is the only surviving production output.** It is deployed as a
shadow tracker at `mlb/pipeline/nrfi_helper_daily.py` and will accumulate live
data through the 2026 season for validation.

No further first-inning research branches are recommended until 2026 shadow
data provides a new evaluation surface.
