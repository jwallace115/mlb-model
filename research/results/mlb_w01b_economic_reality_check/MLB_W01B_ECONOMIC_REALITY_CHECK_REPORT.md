# MLB W01B — ECONOMIC REALITY CHECK REPORT

**Test Date:** 2026-04-19
**Branch:** MLB_W01B_ECONOMIC_REALITY_CHECK
**Parent:** MLB_W01_MANUAL_HISTORICAL_TEST
**Candidate:** MLB_W01 (Short-Outing Starter x Depleted Bullpen)
**Bridge:** mlb_w01_market_bridge_v1.parquet (DraftKings closing total)

---

## 1. PURPOSE

Test whether W01's conjunction adds economically meaningful residual information beyond what the DraftKings closing total already prices.

## 2. ENGINE STACK CONFIRMATION

| Element | Status |
|---|---|
| Frozen foundation | confirmed |
| Orchestration | confirmed |
| Bridge object | mlb_w01_market_bridge_v1.parquet — confirmed |
| Outside-package files | NONE |
| Parent rule inherited exactly | YES |

## 3. PARENT RULE CONFIRMED

Inherited from W01 registry without mutation:
- Fields: opp_sp_workload_ip_last_3, opp_bullpen_pitches_last_3 (self-join)
- Form: AND rule
- Thresholds: IP <= 4.67 AND bullpen_pitches >= 200
- Side: batting team perspective
- Direction: flagged > unflagged

## 4. RESIDUAL DEFINITION

`residual = actual_total - closing_total`

Rows with null closing_total excluded (not imputed). Total excluded: 227 discovery, 48 validation, 51 OOS.

## 5. STAGE RESULTS

### Discovery (2022-2023)

| Group | Raw Gap | Residual Gap | Interpretation |
|---|---|---|---|
| Component A | +0.247 | **+0.017** | Market prices ~93% of starter-alone effect |
| W01 Full | +0.323 | **+0.080** | Conjunction retains more residual than Comp A |

The conjunction shows a residual of +0.080 vs Component A's +0.017. The market prices the starter-alone signal almost entirely, but the conjunction's additional bullpen-depletion context retains a small residual the market doesn't fully capture.

### Validation (2024)

| Group | Raw Gap | Residual Gap | Interpretation |
|---|---|---|---|
| Component A | +0.008 | **-0.188** | Residual reverses. Market overprices this in 2024. |
| W01 Full | +0.019 | **-0.204** | Residual also reverses. Conjunction fails validation. |

Both groups show negative residuals in validation. The market appears to overprice short-outing starter weakness in 2024 — flagged games actually underperform their closing lines. This is a material validation failure for the residual.

### OOS (2025)

| Group | Raw Gap | Residual Gap | Interpretation |
|---|---|---|---|
| Component A | +0.297 | **-0.009** | Market fully prices starter-alone effect |
| W01 Full | +0.363 | **+0.023** | Tiny positive residual survives but economically trivial |

The conjunction retains a barely positive OOS residual (+0.023) while Component A is essentially zero (-0.009). The conjunction adds marginal incremental value over the market, but +0.023 runs is not economically meaningful.

## 6. KEY QUESTIONS ANSWERED

| Question | Answer |
|---|---|
| W01 residual positive in discovery? | **YES** (+0.080) |
| Validation residual sign preserved? | **NO** (-0.204 reversal) |
| OOS material reversal? | **NO** (+0.023, barely positive) |
| W01 full stronger than Comp A in 1+ stage? | **YES** (discovery +0.080 vs +0.017; OOS +0.023 vs -0.009) |
| Conjunction adds incremental value after market? | **MARGINAL** — small in discovery, failed in validation, trivial in OOS |

## 7. INTERPRETATION

### The Market Already Prices Most of W01

The raw W01 signal (+0.323 discovery, +0.363 OOS) looks strong. But after accounting for closing totals, the residual collapses:
- Discovery: +0.323 raw → +0.080 residual (75% priced by market)
- Validation: +0.019 raw → -0.204 residual (overpriced)
- OOS: +0.363 raw → +0.023 residual (94% priced by market)

The market already captures the vast majority of the run-scoring implications of short-outing starters and depleted bullpens through its closing total lines.

### The Conjunction Adds Marginal Value Over Component A

In residual space, the full conjunction (+0.080 discovery, +0.023 OOS) consistently exceeds Component A alone (+0.017 discovery, -0.009 OOS). This confirms the bullpen-depletion component adds SOMETHING beyond what the starter alone provides — but the incremental value is small and economically questionable.

### Validation Failure Is Material

The validation residual reversal (-0.204) is a serious concern. It suggests the market may even overprice this conjunction type in some seasons. A residual that reverses in validation cannot support an ADVANCE verdict.

## 8. FINAL VERDICT

**PRESERVE_AS_CONTEXT**

W01 is a real structural mechanism (confirmed by raw gaps and W01A component analysis). However, the market already prices the vast majority of the effect through closing totals. The residual is small in discovery (+0.080), reversed in validation (-0.204), and trivial in OOS (+0.023). This does not support advancement as an active exploitable edge.

W01 is preserved as documented research context — the mechanism is real but not currently economically exploitable. It may become relevant if:
- Market pricing becomes less efficient at capturing bullpen depletion
- A future model architecture uses W01 as a context layer rather than a standalone signal
- Additional factors narrow the conjunction to a more selective and less market-priced subset

## 9. WHAT THIS RESULT DOES NOT CLAIM

- Not deployment approval
- Not profitability proof
- Not a live recommendation
- The raw signal existing does not validate economic exploitability
- The small discovery residual does not prove market inefficiency

---

*Report generated: 2026-04-19*
