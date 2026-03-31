# Test Batch 3 — Summary Report

**Date:** 2026-03-27
**Signals tested:** CS013-CS018 (8 registered, 7 tested, 1 data-gapped)
**Safety layer:** All tests ran through hypothesis_registry.json with pre-registered thresholds

---

## Result Table

| Signal | Name | Dir | N (2025) | Perm %ile | 2024 Dir | 2025 Dir | Verdict |
|:-------|:-----|:----|---:|---:|:---:|:---:|:--------|
| **CS013** | **Bullpen blowup state model** | **OVER** | **741** | **100.0** | **+** | **+** | **PASS** |
| CS014A | Umpire tight zone: UNDER | UNDER | 52 | 83.0 | + | + | **FAIL** |
| CS014B | Umpire loose zone: OVER | OVER | 43 | 1.6 | - | - | **FAIL** |
| CS015 | Cross-market prop/total arb | UNDER | — | — | — | — | **DATA_GAP** |
| CS016A | Repertoire improvement: UNDER | UNDER | 259 | 6.4 | - | + | **FAIL** |
| CS016B | Repertoire instability: OVER | OVER | 628 | 50.4 | + | - | **FAIL** |
| CS017 | Pitch-mix entropy: UNDER | UNDER | 1,277 | 79.4 | + | + | **FAIL** |
| CS018 | Inning-level run clustering | OVER | 570 | 39.2 | - | + | **FAIL** |

---

## Verdicts

### PASS: CS013 — Bullpen Blowup State Model

**The strongest signal in the entire discovery project.**

- **Permutation:** 100.0th percentile — observed metric exceeded all 500 random shuffles
- **2024 direction:** Positive (55.9% over rate in flagged games)
- **2025 direction:** Positive (54.8% over rate)
- **Train ROI at -110:** +6.8% (N=2,047)
- **2025 ROI at -110:** +4.6% (N=741)
- **Mechanism:** When 2+ relievers on the same team are individually in a degraded state (trailing 5-appearance runs > 1.5x their season baseline), the team's bullpen has elevated blowup risk. Markets price aggregate bullpen quality but not the state of individual reliever degradation.
- **Flagged games:** 2,788 out of 8,411 non-push (33.1%) — high prevalence for volume

**This signal is mechanistically distinct from CS004.** CS004 uses run-allowed *variance* (statistical tail risk). CS013 uses individual reliever *state deterioration* (component degradation). Both target bullpen OVER, but through different lenses:
- CS004: "the bullpen has high-variance outcomes" (statistical)
- CS013: "specific relievers are individually breaking down" (structural)

**Next step:** Full diagnostic pass (quintile calibration, segmentation, decay, CS004 interaction).

### Near-miss: CS014A — Umpire Tight Zone

- Permutation at 83.0 — just 2 points below the 85th threshold
- Directionally positive in both 2024 and 2025 (53.8-55.6% under rate)
- N is thin (52 in 2025, 117 in train) due to the 1-SD regime threshold
- **The umpire zone mechanism may be real but the current proxy is too restrictive.** A gentler threshold (0.75 SD instead of 1.0 SD) might produce sufficient N while maintaining signal quality — but this would require re-registration and a new test, not post-hoc tuning.

### Anti-directional: CS014B — Umpire Loose Zone

- Permutation at 1.6th — far below threshold
- Over rate of 44.2% in flagged games — strongly anti-directional
- **Loose zone umpires may actually correlate with pitcher-friendly game environments** (good pitchers get more borderline calls) rather than causing more runs
- Archive

### DATA_GAP: CS015 — Cross-Market Prop/Total

- SP K prop data not available in structured parquet form locally
- Pull scripts exist in `research/kprop/` but no matched game-level dataset
- Remains REGISTERED

### FAIL: CS016A/B — Pitcher Repertoire Mix Change

- CS016A (improvement → UNDER): 6.4th permutation, anti-directional in train
- CS016B (instability → OVER): 50.4th permutation, coin-flip
- **The pitch mix change signal has no detectable market impact.** Markets likely already adjust for visible repertoire shifts (new pitch additions are covered by media).

### Near-miss: CS017 — Pitch-Mix Entropy

- Permutation at 79.4 — below 85th but closer than most failures
- 2025 under rate 53.6% in flagged games — directionally positive
- N = 1,277 in 2025 — excellent sample
- **Entropy captures something real about unpredictability, but the effect is too small to clear the permutation gate.** This may be because high-entropy pitchers are already valued by the market (high whiff rates correlate with diverse arsenals).

### FAIL: CS018 — Inning-Level Run Clustering

- Permutation at 39.2 — well below threshold
- The simple scoring-variance proxy does not capture true inning-level clustering
- Would need actual per-inning linescore data to test properly

---

## Combined Signal Board (All 3 Batches)

| Signal | Batch | Verdict | Perm | Note |
|:-------|:------|:--------|-----:|:-----|
| CS001 | 1 | FAIL | 64.4 | Command regime |
| CS002 | 1 | FAIL | 60.2 | Short leash — priced |
| CS003 | 1 | FAIL | 21.0 | Fatigue — anti-directional |
| **CS004** | **1** | **PASS** | **89.8** | **Bullpen variance tail risk** |
| CS005 | 1 | FAIL | 30.0 | BP fatigue — anti-directional |
| CS006 | 1 | DATA_GAP | — | K prop data needed |
| CS007A | 2 | FAIL | 69.0 | Run dist OVER |
| CS007B | 2 | FAIL | 72.6 | Run dist UNDER |
| CS008A | 2 | FAIL | 58.8 | Weather OVER — priced |
| CS008B | 2 | FAIL | 61.2 | Weather UNDER — thin |
| CS009A/B | 2 | DATA_GAP | — | Now resolved by c041 build |
| CS010A | 2 | FAIL | 98.8 | Park env OVER — reverses OOS |
| CS010B | 2 | PASS→NEEDS_DATA | 91.6 | Park env UNDER — inconsistent decay |
| CS011 | 2 | FAIL | 95.2 | BP deploy — reverses OOS |
| CS012 | 2 | FAIL | 57.2 | Travel compress — too rare |
| **CS013** | **3** | **PASS** | **100.0** | **Bullpen state degradation — STRONGEST** |
| CS014A | 3 | FAIL | 83.0 | Umpire tight zone — near miss |
| CS014B | 3 | FAIL | 1.6 | Umpire loose zone — anti-directional |
| CS015 | 3 | DATA_GAP | — | K prop data needed |
| CS016A | 3 | FAIL | 6.4 | Repertoire improvement — no signal |
| CS016B | 3 | FAIL | 50.4 | Repertoire instability — no signal |
| CS017 | 3 | FAIL | 79.4 | Entropy — near miss |
| CS018 | 3 | FAIL | 39.2 | Run clustering — poor proxy |

**24 registered, 21 tested, 2 PASS (CS004 + CS013), 16 FAIL, 3 DATA_GAP, CS010B downgraded**

---

## Top Finding

**CS013 is the strongest signal in the discovery project** — 100th permutation percentile, +4.6% ROI in 2025 OOS, directionally consistent across all training and validation periods. It identifies a specific structural mechanism (individual reliever degradation) that the market does not price.

CS013 and CS004 both target bullpen OVER but through different mechanisms. Their correlation and interaction should be tested in diagnostics to determine whether they stack or are redundant.

---

## Recommended Next Steps

| Signal | Action |
|:-------|:-------|
| **CS013** | **Run full diagnostic pass** — quintiles, segmentation, decay, CS004 interaction |
| CS014A | Consider re-registration with 0.75 SD threshold (requires new CS014A_v2 entry) |
| CS017 | Monitor — near miss at 79.4 permutation, may strengthen with more data |
| CS015 | Acquire K prop data for testing |
| All others | Archive |
