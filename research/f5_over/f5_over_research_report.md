# F5 Over Research Report

## 1. Core Results

### All books (books_count >= 1)

| Signal | N | Win% | ROI (actual) | ROI (-110) | Net |
|--------|---|------|-------------|-----------|-----|
| O1: F5 Over (p>0.57) | 356 | 59.2% | +12.4% | +12.9% | +44.1u |
| O2: F5 Over (p>0.60) | 162 | 57.8% | +10.2% | +10.2% | +16.6u |

### Books >= 2

| Signal | N | Win% | ROI (actual) | ROI (-110) | Net |
|--------|---|------|-------------|-----------|-----|
| O1: F5 Over (p>0.57) | 335 | 59.0% | +12.0% | +12.6% | +40.1u |
| O2: F5 Over (p>0.60) | 152 | 56.3% | +7.4% | +7.4% | +11.2u |

Signal O2 (p>0.60) is weaker than O1 (p>0.57) — win rate drops from 59.2% to 57.8%. This is the opposite of F5 under, where higher thresholds strengthened the signal. Noteworthy but does not disqualify O1.

---

## 2. Threshold Sensitivity (Test A)

| Threshold | N | Win% | 95% Wilson CI | ROI (actual) |
|-----------|---|------|---------------|-------------|
| 0.54 | 690 | 55.4% | [51.6–59.1] | +4.8% |
| 0.55 | 567 | 55.6% | [51.5–59.6] | +5.3% |
| 0.56 | 446 | 58.1% | [53.5–62.6] | +10.2% |
| 0.57 | 356 | 59.2% | [54.0–64.1] | +12.4% |
| 0.58 | 274 | 57.9% | [51.9–63.6] | +10.3% |
| 0.59 | 215 | 58.4% | [51.7–64.8] | +11.8% |
| 0.60 | 162 | 57.8% | [50.0–65.1] | +10.2% |

**Win rate monotonicity: NOT perfectly monotonic.** Win rate peaks at 0.57 (59.2%), dips at 0.58 (57.9%), partially recovers at 0.59 (58.4%), then dips again at 0.60 (57.8%). The dips are within sampling noise (CI overlaps at all thresholds), but the pattern differs from F5 under's clean monotonic curve.

**N decay:** Smooth decline from 690 → 162 as expected.

**Interpretation:** The edge plateau above 0.57 is less clean than the under side. ROI is relatively flat from 0.57 to 0.60 (+10–13%), suggesting diminishing signal resolution at higher thresholds. The 0.57 threshold is not an artifact — it sits in the middle of a smooth gradient from 0.54 to 0.57.

---

## 3. Season Standalone (Test B)

| Period | N | Win% | ROI (actual) |
|--------|---|------|-------------|
| 2024 (PARTIAL) | 190 | 59.8% | +13.8% |
| 2025 | 166 | 58.4% | +10.9% |
| Pooled | 356 | 59.2% | +12.4% |

Both seasons positive. 2025 standalone at +10.9% clearly supports advancement. 2024 is slightly stronger than 2025 but both are in the same direction — not MIXED.

---

## 4. Line-Band Analysis (Test C)

| Band | Signal N | Win% | ROI | Unsignaled over rate |
|------|----------|------|-----|---------------------|
| <=4.0 | 91 | 55.6% | -2.4% | 49.7% |
| =4.5 | 251 | 59.8% | +16.2% | 47.6% |
| >=5.0 | 14 | 71.4% | +40.7% (THIN) | 44.8% |

The <=4.0 band is ROI-negative (-2.4%) despite a 55.6% win rate — the vig overwhelms thin edge at low lines. Signal separation over baseline: +5.9pp at <=4.0, +12.2pp at =4.5, +26.6pp at >=5.0 (THIN).

The f5_line=4.5 band dominates the sample (251/356 = 70.5%) and drives the overall result.

---

## 5. Permutation Test (Test D)

| Season | Actual ROI | Shuffled mean | Shuffled std | Percentile |
|--------|-----------|---------------|-------------|------------|
| 2024 (PARTIAL) | +13.8% | -5.0% | 6.1% | **100%** |
| 2025 | +10.9% | -9.6% | 6.7% | **100%** |

Both seasons at 100th percentile. The signal is strongly non-random.

---

## 6. Signal O3 Diagnostic — Weak Starter Filter

xFIP quartile cuts (frozen train 2022-2023): Q25=3.918, Q50=4.263, Q75=4.594.
Filter: both starters xFIP >= Q50 (worse than median).

| Subset | N | Win% | ROI (actual) |
|--------|---|------|-------------|
| All books | 140 | 64.7% | +21.9% |
| Books >= 2 | 134 | 65.4% | +23.1% |
| 2024 (PARTIAL) | 65 | 64.1% | +21.6% |
| 2025 | 75 | 65.3% | +22.1% |

Signal O3 is substantially stronger than O1 (+22% vs +12% ROI) but at lower volume (140 vs 356). When both starters are below-median, F5 over wins at 65%. This is diagnostic only — not a deployment signal.

---

## 7. Comparison Table — F5 Under vs F5 Over (books >= 2)

| Metric | F5 Under (B) | F5 Over (O1) |
|--------|-------------|-------------|
| N | 742 | 335 |
| Win% | 60.2% | 59.0% |
| ROI actual | +13.6% | +12.0% |
| ROI at -110 | +14.9% | +12.6% |
| Perm 2024 | 100% | 100% |
| Perm 2025 | 100% | 100% |
| 2025 ROI | +16.9% | +10.3% |

F5 under triggers on 2.2x more games (742 vs 335), has slightly higher win rate and ROI, and shows a cleaner threshold gradient. F5 over is profitable but lower-volume and less clean.

The two signals fire on **different games** (under when p_under>0.57 vs over when p_over>0.57) so they are complementary, not competing.

---

## 8. Decision Criteria

| Criterion | Result | Status |
|-----------|--------|--------|
| ROI >= 3% pooled actual | +12.4% | **PASS** |
| N >= 200 | 356 | **PASS** |
| 2025 standalone ROI positive | +10.9% | **PASS** |
| Permutation top 10% both seasons | 100%/100% | **PASS** |
| 2025 clearly supports advancement | +10.9% | **PASS** |

**All 5 criteria met. Signal O1 advances.**

### Caveats

1. **Threshold sensitivity is not perfectly monotonic.** Win rate plateaus/dips slightly above 0.57, unlike F5 under's clean gradient. This is within CI noise but warrants monitoring.
2. **Edge disappears at f5_line <= 4.0** (ROI -2.4%). Low F5 lines do not support over bets.
3. **O2 (p>0.60) is weaker than O1 (p>0.57)** — the higher-confidence tier does not improve. This means staking logic should NOT increase units at higher p_over thresholds (unlike the under side).
4. **N=356 is less than half the under volume** (807). The over side of the V1 engine triggers less often.
