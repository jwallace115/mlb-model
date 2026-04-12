# Phase 5 — Tracker Interpretability

## Shadow Tracker Schema Issues

### 1. `correct` Field Never Populated
The `correct` field is None for all 820 records in shadow_signals_2026.json.
Actual hit rates must be computed manually: `actual_total < closing_total`.

### 2. V1 Direction Context Always "NONE"
All records show `v1_direction_context: "NONE"`, meaning either:
- The V1 projection is not being passed to `log_shadow_signals()`
- The V1 sim is not running when shadow signals are computed

This makes it impossible to filter for V1-interaction signals from the tracker.

### 3. Tracker Results ARE Comparable To
- Standalone rebuild backtest (Object B) — same gate logic
- NOT comparable to V1-interaction research (Object A) — different gate

## 2026 Shadow Results (manually computed, through 2026-04-11)

| Signal | Favorable | Resolved | Push | Under-Hit | Hit% (non-push) |
|--------|-----------|----------|------|-----------|-----------------|
| ADJ_CONTACT | 92 | 65 | 2 | 35 | 55.6% |
| ADJ_HH | 47 | 34 | 1 | 21 | 63.6% |
| adj_k_rate_last3 | 38 | 30 | 2 | 17 | 60.7% |
| ADJ_BB_RATE | 26 | 16 | 0 | 8 | 50.0% |
| ADJ_RUN_SUPP | 55 | 34 | 2 | 19 | 59.4% |

### Interpretation Caveats
1. Feature source is frozen at end-of-2025 — not updating with 2026 pitcher starts
2. Early-season samples are small (N=16-65 resolved)
3. No closing-price ROI computed (would need odds data)
4. ADJ_HH at 63.6% on N=33 non-push is above the standalone backtest rate but
   is within normal variance for that sample size (95% CI: ~46%-79%)
