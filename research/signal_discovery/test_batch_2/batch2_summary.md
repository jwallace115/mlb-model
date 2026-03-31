# Test Batch 2 — Summary Report

**Date:** 2026-03-27
**Signals tested:** CS007A-CS012 (10 registered, 8 tested, 2 data-gapped)
**Safety layer:** All tests ran through hypothesis_registry.json with pre-registered thresholds

---

## Result Table

| Signal | Name | Dir | N (2025) | Perm %ile | 2024 Dir | 2025 Dir | Verdict |
|:-------|:-----|:----|---:|---:|:---:|:---:|:--------|
| CS007A | Run dist tail: OVER | OVER | 617 | 69.0 | + | - | **FAIL** |
| CS007B | Run dist tail: UNDER | UNDER | 293 | 72.6 | + | + | **FAIL** |
| CS008A | Extreme weather: OVER | OVER | 98 | 58.8 | + | - | **FAIL** |
| CS008B | Extreme weather: UNDER | UNDER | 31 | 61.2 | - | + | **FAIL** |
| CS009A | Umpire tight zone: UNDER | UNDER | — | — | — | — | **DATA_GAP** |
| CS009B | Umpire loose zone: OVER | OVER | — | — | — | — | **DATA_GAP** |
| CS010A | Dynamic park env: OVER | OVER | 233 | **98.8** | + | - | **FAIL** |
| **CS010B** | **Dynamic park env: UNDER** | **UNDER** | **515** | **91.6** | **+** | **+** | **PASS** |
| CS011 | Bullpen deployment opt | OVER | 1,182 | **95.2** | + | - | **FAIL** |
| CS012 | Travel compression | UNDER | 15 | 57.2 | + | - | **FAIL** |

---

## Verdicts

### PASS: CS010B — Dynamic Park Environment: UNDER

- **Permutation:** 91.6th percentile (> 85 required)
- **2024 direction:** Positive (54.3% under rate)
- **2025 direction:** Positive (50.7% under rate)
- **Mechanism:** Game-specific pitcher-friendly environment (low park factor + cold temp + wind in) creates run suppression beyond what static park factors capture
- **Frozen threshold:** env_score <= 1.0652 (bottom 20%, 2022-2023)
- **Effect size:** Small — 50.7% under rate in 2025 is modest but the permutation percentile is strong, indicating the signal reliably identifies a distinct cohort
- **Next step:** Advance to shadow monitoring; evaluate overlap with existing P09 (both target UNDER in specific park environments)

### Notable FAIL with high permutation: CS010A and CS011

**CS010A** (Dynamic park OVER) had 98.8th permutation percentile — the highest in either batch. However, 2025 direction was negative (48.5% over rate). The signal identifies a real statistical cluster but the effect *reversed* in the validation year. This is the classic p-hacking trap the safety layer is designed to catch: high permutation ≠ real signal if it doesn't replicate out-of-sample.

**CS011** (Bullpen deployment) had 95.2th permutation percentile but 2025 direction was negative (47.8% over rate). Same pattern — strong in-sample, fails OOS. The market appears to already price depleted high-leverage arms.

### DATA_GAP: CS009A/B — Umpire Zone Regime

The local umpire data (`umpire_k_rate` in game_table) is a **static season-level rating**, not a per-game called strike metric. All games for the same umpire in a season have the identical k_rate value. A rolling umpire zone state cannot be built from this data.

**Required:** Per-game umpire zone metrics (called strikes above expected, zone expansion rate) from Umpire Scorecards or Statcast per-game umpire data. This is a data engineering task.

### FAIL: CS007A/B — Run Distribution Tail Shape

Neither direction cleared the permutation gate (69.0 / 72.6). CS007B (UNDER for low-variance environments) was directionally positive in both 2024 and 2025 (53.9% under rate in 2025) but the permutation test shows the effect is not reliably distinguishable from random team performance variation.

### FAIL: CS008A/B — Extreme Weather

Extreme heat/wind (CS008A OVER): 43.9% over rate in 2025 — anti-directional. The market already adjusts for extreme weather conditions.

Extreme cold (CS008B UNDER): 51.6% under rate in 2025 but only N=31 in validation, far too thin. Permutation at 61.2 is below threshold.

### FAIL: CS012 — Travel Compression

Only 35 compressed travel games in 2024-2025 combined (N=15 in 2025). The phenomenon is too rare for reliable signal testing. The safety layer correctly identified this as THIN_SAMPLE.

---

## Combined Batch 1 + Batch 2 Signal Board

| Signal | Batch | Verdict | Perm %ile | Note |
|:-------|:------|:--------|---:|:-----|
| CS001 | 1 | FAIL | 64.4 | Command regime — insufficient N |
| CS002 | 1 | FAIL | 60.2 | Short leash — market prices it |
| CS003 | 1 | FAIL | 21.0 | Fatigue — anti-directional |
| CS004 | 1 | **PASS** | 89.8 | Bullpen tail risk — SHADOW_READY |
| CS005 | 1 | FAIL | 30.0 | BP fatigue — anti-directional |
| CS006 | 1 | DATA_GAP | — | K prop data needed |
| CS007A | 2 | FAIL | 69.0 | Run dist OVER — not distinguishable |
| CS007B | 2 | FAIL | 72.6 | Run dist UNDER — not distinguishable |
| CS008A | 2 | FAIL | 58.8 | Weather OVER — market adjusts |
| CS008B | 2 | FAIL | 61.2 | Weather UNDER — thin sample |
| CS009A | 2 | DATA_GAP | — | Per-game umpire data needed |
| CS009B | 2 | DATA_GAP | — | Per-game umpire data needed |
| CS010A | 2 | FAIL | 98.8 | Park env OVER — reverses OOS |
| **CS010B** | **2** | **PASS** | **91.6** | **Park env UNDER — shadow candidate** |
| CS011 | 2 | FAIL | 95.2 | BP deploy — reverses OOS |
| CS012 | 2 | FAIL | 57.2 | Travel compress — too rare |

**16 tested, 2 PASS (CS004, CS010B), 11 FAIL, 3 DATA_GAP**

---

## Top Finding

**CS010B (Dynamic Park Environment: UNDER)** is the second signal to pass through the safety layer, joining CS004 from Batch 1. Both are small-effect signals (+0.7pp UNDER rate for CS010B, +0.5pp OVER rate for CS004) that reliably identify distinct game environments.

CS010B is particularly interesting because it overlaps with P09's domain (park-based UNDER) but uses a different mechanism: P09 uses pitcher hard-hit suppression × park factor, while CS010B uses temperature deviation × wind interaction × park factor. The two could potentially stack if they identify different subsets of games.

---

## Recommended Next Steps

| Signal | Action |
|:-------|:-------|
| **CS010B** | Shadow monitor — track UNDER rate in 2026; evaluate P09 overlap |
| CS004 | Continue shadow monitoring (from Batch 1) |
| CS009A/B | Acquire per-game umpire zone data, then re-test |
| CS006 | Acquire K prop data, then re-test |
| CS007B | Archive — borderline but below permutation threshold |
| All others | Archive — failed permutation and/or OOS validation |

---

## Safety Layer Performance

All 8 tested signals ran through the full safety protocol. The layer correctly:
- Caught 2 signals with high permutation (CS010A=98.8, CS011=95.2) that failed OOS validation — prevented false positives
- Passed CS010B which cleared both permutation AND season support gates
- Identified 2 data gaps (CS009A/B) without attempting invalid tests
- Flagged CS012 thin sample (N=15 in 2025) appropriately
