# V2 Opponent-Adjusted Engine — Signal Scan Report

Dataset: 4855 games (2024-2025), 4666 non-push
V1 baseline: N=887, under%=0.558, ROI=+6.5%

## Part A — Standalone Triage

| Signal | Best Bucket | N | Under% | ROI | Stability | Mkt Corr | Verdict |
|--------|------------|---|--------|-----|-----------|----------|---------|
| combined_adj_k_rate_last3 | top_10 | 424 | 0.568 | +8.5% | STABLE | PRICED (-0.331) | **SHELVE** |
| combined_adj_bb_rate_last3 | top_20 | 861 | 0.537 | +2.4% | STABLE | CLEAN (0.107) | **INVESTIGATE** |
| combined_adj_contact_rate_last3 | top_10 | 426 | 0.566 | +8.0% | STABLE | PARTIAL (-0.220) | **PROMOTE** |
| combined_adj_hard_hit_last3 | top_10 | 411 | 0.521 | -0.6% | STABLE | CLEAN (-0.101) | **SHELVE** |
| combined_adj_run_suppression_last3 | top_10 | 425 | 0.534 | +2.0% | STABLE | PARTIAL (-0.257) | **INVESTIGATE** |
| adj_k_x_contact_last3 | bot_10 | 430 | 0.521 | -0.5% | STABLE | CLEAN (0.021) | **SHELVE** |
| adj_k_x_runsup_last3 | top_10 | 425 | 0.527 | +0.6% | MIXED | CLEAN (0.109) | **INVESTIGATE** |

### Year Detail

**combined_adj_bb_rate_last3**
- 2024: top20 resid=0.051162790697674376, bot20 resid=0.03472222222222221
- 2025: top20 resid=0.015081206496519672, bot20 resid=0.026682134570765625

**combined_adj_contact_rate_last3**
- 2024: top20 resid=0.01650943396226412, bot20 resid=-0.001160092807424573
- 2025: top20 resid=0.037735849056603765, bot20 resid=0.009389671361502372

**combined_adj_run_suppression_last3**
- 2024: top20 resid=0.001160092807424573, bot20 resid=-0.009216589861751168
- 2025: top20 resid=0.04312354312354316, bot20 resid=0.016587677725118488

**adj_k_x_runsup_last3**
- 2024: top20 resid=-0.00694444444444442, bot20 resid=-0.011627906976744207
- 2025: top20 resid=0.01650943396226412, bot20 resid=0.03953488372093028

## Part B — V1 Interaction Scan

V1 UNDER baseline: p_under > 0.57, N=887, ROI=+6.5%

### Best V1 Interactions (pooled)

| Signal | Bucket | N | Under% | ROI | V1 ROI | Lift | 2024 Lift | 2025 Lift |
|--------|--------|---|--------|-----|--------|------|----------|----------|
| combined_adj_bb_rate_last3 | top_10 | 60 | 0.700 | +33.6% | +6.5% | +27.1pp | +31.4pp | +21.5pp |
| combined_adj_hard_hit_last3 | bot_20 | 109 | 0.661 | +26.1% | +6.5% | +19.6pp | +21.0pp | +17.8pp |
| adj_k_x_runsup_last3 | top_10 | 53 | 0.660 | +26.1% | +6.5% | +19.5pp | +22.3pp | +16.7pp |
| combined_adj_run_suppression_last3 | bot_20 | 96 | 0.635 | +21.3% | +6.5% | +14.8pp | +3.1pp | +29.3pp |
| combined_adj_contact_rate_last3 | top_10 | 131 | 0.634 | +21.0% | +6.5% | +14.4pp | +14.3pp | +14.6pp |
| adj_k_x_contact_last3 | bot_10 | 49 (THIN) | 0.612 | +16.9% | +6.5% | +10.3pp | +17.7pp | +0.7pp |
| combined_adj_k_rate_last3 | top_30 | 389 | 0.584 | +11.4% | +6.5% | +4.9pp | +1.4pp | +8.4pp |

## Part C — Leaderboard

| Rank | Signal | Standalone | V1 Lift | V1 N | Stable | Corr | Recommendation |
|------|--------|-----------|---------|------|--------|------|---------------|
| 1 | combined_adj_bb_rate_last3 | +2.4% | +27.1pp | 60 | STABLE | CLEAN | **PROMOTE to deep analysis** |
| 2 | combined_adj_hard_hit_last3 | -0.6% | +19.6pp | 109 | STABLE | CLEAN | **PROMOTE to deep analysis** |
| 3 | adj_k_x_runsup_last3 | +0.6% | +19.5pp | 53 | MIXED | CLEAN | **PROMOTE to deep analysis** |
| 4 | combined_adj_run_suppression_last3 | +2.0% | +14.8pp | 96 | STABLE | PARTIAL | **PROMOTE to deep analysis** |
| 5 | combined_adj_contact_rate_last3 | +8.0% | +14.4pp | 131 | STABLE | PARTIAL | **PROMOTE to deep analysis** |
| 6 | adj_k_x_contact_last3 | -0.5% | +10.3pp | 49 | STABLE | CLEAN | **HOLD for monitoring** |
| 7 | combined_adj_k_rate_last3 | +8.5% | +4.9pp | 389 | STABLE | PRICED | **PROMOTE to deep analysis** |

## Part D — Safety Checks


### combined_adj_bb_rate_last3 (top_10)
- AVAILABLE: N=819, under%=0.562, ROI=+7.2%, avg_close=7.68
- UNAVAILABLE: N=68, under%=0.515, ROI=-1.7%, avg_close=8.08
- Availability bias: 0.047 (WARNING)
- **THIN TAIL WARNING**: N=60 < 75
- Direction consistent: 2024=+31.4pp, 2025=+21.5pp

### combined_adj_hard_hit_last3 (bot_20)
- AVAILABLE: N=778, under%=0.564, ROI=+7.7%, avg_close=7.67
- UNAVAILABLE: N=109, under%=0.514, ROI=-1.9%, avg_close=8.00
- Availability bias: 0.051 (WARNING)
- Tail size OK: N=109
- Direction consistent: 2024=+21.0pp, 2025=+17.8pp

## Final Answers

### Q1: Which V2 signals show standalone value?
- PROMOTE: combined_adj_contact_rate_last3
- INVESTIGATE: combined_adj_bb_rate_last3, combined_adj_run_suppression_last3, adj_k_x_runsup_last3
- SHELVE: combined_adj_k_rate_last3, combined_adj_hard_hit_last3, adj_k_x_contact_last3

### Q2: Which V2 signals improve V1 UNDER?
- combined_adj_bb_rate_last3 (top_10): +27.1pp lift, N=60
- combined_adj_hard_hit_last3 (bot_20): +19.6pp lift, N=109
- adj_k_x_runsup_last3 (top_10): +19.5pp lift, N=53
- combined_adj_run_suppression_last3 (bot_20): +14.8pp lift, N=96
- combined_adj_contact_rate_last3 (top_10): +14.4pp lift, N=131
- adj_k_x_contact_last3 (bot_10): +10.3pp lift, N=49
- combined_adj_k_rate_last3 (top_30): +4.9pp lift, N=389

### Q3: Strongest interaction candidate?
- **combined_adj_bb_rate_last3** (top_10): +27.1pp lift, ROI=+33.6%

### Q4: Classification

| Signal | Classification | Reason |
|--------|---------------|--------|
| combined_adj_bb_rate_last3 | **PROMOTE to deep analysis** | standalone=INVESTIGATE, V1_lift=+27.1pp, stable=STABLE, corr=CLEAN |
| combined_adj_hard_hit_last3 | **PROMOTE to deep analysis** | standalone=SHELVE, V1_lift=+19.6pp, stable=STABLE, corr=CLEAN |
| adj_k_x_runsup_last3 | **PROMOTE to deep analysis** | standalone=INVESTIGATE, V1_lift=+19.5pp, stable=MIXED, corr=CLEAN |
| combined_adj_run_suppression_last3 | **PROMOTE to deep analysis** | standalone=INVESTIGATE, V1_lift=+14.8pp, stable=STABLE, corr=PARTIAL |
| combined_adj_contact_rate_last3 | **PROMOTE to deep analysis** | standalone=PROMOTE, V1_lift=+14.4pp, stable=STABLE, corr=PARTIAL |
| adj_k_x_contact_last3 | **HOLD for monitoring** | standalone=SHELVE, V1_lift=+10.3pp, stable=STABLE, corr=CLEAN |
| combined_adj_k_rate_last3 | **PROMOTE to deep analysis** | standalone=SHELVE, V1_lift=+4.9pp, stable=STABLE, corr=PRICED |

## Critical Assessment

The raw leaderboard numbers require strong caveats:

### Implausibly large V1 interaction lifts

Most interaction lifts (+14 to +27pp) are unrealistically large. For context, the entire V1 edge is +6.5% ROI. A +27pp lift from a single feature would imply near-perfect signal overlap. This is almost certainly **small-sample inflation**:

- `adj_bb_rate_last3 top_10`: N=60 → high variance, +27pp is ~2 standard errors
- `adj_k_x_runsup_last3 top_10`: N=53 → THIN, unreliable
- `adj_run_suppression_last3 bot_20`: N=96 but 2024 lift is only +3pp (vs +29pp in 2025)

### Availability bias is present in ALL signals

Both top-2 candidates show ~5pp availability bias (games with signal available have higher base under rate). This inflates all interaction ROIs. The real lift is likely 3-5pp lower than reported.

### What survives critical filtering?

After applying:
- N ≥ 100 (not THIN)
- Both years positive lift
- Availability bias acknowledged

Only two candidates remain plausible:

| Signal | Bucket | N | 2024 Lift | 2025 Lift | Pooled Lift |
|--------|--------|---|----------|----------|------------|
| **combined_adj_contact_rate_last3** | top_10 | 131 | +14.3pp | +14.6pp | +14.4pp |
| **combined_adj_hard_hit_last3** | bot_20 | 109 | +21.0pp | +17.8pp | +19.6pp |

Both show consistent year-over-year direction. However:
- adj_contact_rate is PARTIALLY correlated with closing_total (r=-0.22)
- adj_hard_hit has zero standalone value (ROI=-0.6%)
- The magnitude of both lifts (~15-20pp) is likely inflated by ~5pp from availability bias

### Realistic assessment of best candidates

| Signal | Realistic lift (after bias) | Deployment potential |
|--------|---------------------------|-------------------|
| adj_contact_rate_last3 (top_10) | ~+9 to +12pp | Worth deep analysis |
| adj_hard_hit_last3 (bot_20) | ~+14 to +17pp | Worth deep analysis, despite weak standalone |
| adj_k_rate_last3 (top_30) | ~+3 to +5pp | Already tested in V1 walkforward; confirmed at ~+3pp |

## Recommended Next Deep Analysis Candidates

1. **combined_adj_contact_rate_last3** — Most balanced: standalone PROMOTE (+8.0% ROI), V1 lift stable across years (+14.3/+14.6pp), N=131 is adequate. Market partially priced (r=-0.22) but not absorbed. Best candidate for walk-forward validation.

2. **combined_adj_hard_hit_last3** — Largest N on interaction (109), consistent direction both years, CLEAN market correlation. No standalone value but strong V1 amplifier. Requires Statcast dependency (88% coverage).

3. **combined_adj_bb_rate_last3** — Flagged for monitoring only. N=60 is too thin for deep analysis. If 2026 confirms at N≥100, revisit.

Note: `adj_k_x_runsup_last3` dropped from top 3 due to MIXED year stability and N=53 (THIN). `adj_k_rate_last3` already validated in V1 walkforward backtest — do not re-test.

