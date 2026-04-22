# MLB F5 DISCOVERY PASS 02 — REPORT

**Date:** 2026-04-22
**Market:** F5 Totals | **Benchmark:** F5 Opening Line (2am ET)
**Features:** Proprietary drift metrics (V3) | **Runtime Object:** V3 (19,430 × 209)

---

## A. Why Drift Features May Differ in F5

F5 covers only the first 5 innings — the period where the starting pitcher's state matters most. Drift features (velocity declining, zone command deteriorating, pitch mix changing relative to own baseline) should have maximum impact in F5 before the bullpen transition dilutes the signal. If drift features work anywhere, they should work in F5.

---

## B. Baseline (Discovery, May-Dec 2023)

| Metric | Value |
|---|---|
| Mean f5_open_residual | +0.527 |
| Std dev | 3.486 |
| Over rate | 49.1% |
| Under rate | 48.0% |

---

## C-D. Thresholds and Flag Rates

53 candidates (12 MG + 41 enumeration). All passed flag rate filter. Flag rates 3.6-12.2%.

---

## E. Discovery Results

**2 candidates advanced:**

| Candidate | N | Gap | p_under | Months Consistent |
|---|---|---|---|---|
| **2strike_drift_L3 × xwOBA_L3** | 249 | **−0.387** | 0.048 | 5/8 |
| **MG03 (zone_drift_L3 × xwOBA_L3)** | 260 | **−0.342** | 0.068 | 5/8 |

Both are under signals — games go under the F5 opening line when pitcher drift deterioration meets quality batting contact.

**Notable near-miss:** `zone_drift_L5 × xwOBA_L3` had the largest gap (−0.497, p=0.015) but only 4/8 months consistent.

---

## F. Validation Results (2024)

| Candidate | Disc Gap | Val Gap | N |
|---|---|---|---|
| 2strike_drift_L3 × xwOBA_L3 | −0.387 | **+0.052** | 328 |
| MG03 (zone_drift × xwOBA) | −0.342 | **+0.109** | 393 |

**Both reversed sign in validation.** Discovery negative gaps (+under) became positive (+over) in 2024. Zero candidates advanced to OOS.

---

## G-H. OOS and Dispositions

No candidates reached OOS. All 53 candidates DEAD.

---

## I. Comparison to Full-Game Drift Results (Pass 08)

| Signal | Full-Game Disc Gap | F5 Disc Gap | Full-Game Val | F5 Val |
|---|---|---|---|---|
| Velo drift × HH | +0.253 (OVER) | −0.139 | collapsed | N/A |
| Zone drift × xwOBA | ~0 | **−0.342 (UNDER)** | N/A | **reversed** |
| 2strike drift × xwOBA | −0.227 | **−0.387 (UNDER)** | N/A | **reversed** |
| Double drift (MG04) | +0.515 (OVER) | −0.191 | reversed | N/A |

**Drift features show OPPOSITE direction in F5 vs full-game.** In full-game Pass 08, velo drift × HH produced positive (over) gaps. In F5, the same family produces negative (under) gaps. This is structurally interesting — the starter-only window of F5 reverses the direction — but the signal still collapses in validation.

---

## J. Is F5 Equally Efficient?

**Yes.** The F5 opening line market is just as efficient as the full-game closing line market relative to drift features. The pattern is identical across both:
1. Discovery shows moderate gaps (0.3-0.5 range)
2. Validation shows collapse or reversal
3. No signal persists

The F5 market sets lines algorithmically from the full-game total, and both markets incorporate pitcher state information at roughly the same speed. There is no structural efficiency gap to exploit.

---

## Cumulative Research Assessment

Across all passes testing F5 markets (Pass 01: V2 features, Pass 02: V3 drift features), zero signals have survived validation. The F5 opening line at 2am ET is efficient relative to all Statcast-derived features tested.

---

*Report generated: 2026-04-22*
