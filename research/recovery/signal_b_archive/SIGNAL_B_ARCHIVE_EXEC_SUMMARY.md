# Signal B HOME — Archive Executive Summary

**Date:** 2026-04-12
**Action:** Operational deactivation and permanent archive
**Object ID:** mlb_f5_rl_signal_b_home
**Prior status:** SHADOW
**New status:** ARCHIVED

---

## What Was Done

### Phase 0: Locked Negative Verdict
Clean PIT-safe backtest confirms Signal B HOME is unprofitable:
- 724 games, 53.9% hit rate vs 57.4% breakeven @ -135
- ROI: -6.2% (was +27.9% before contamination fix)
- Only 2022 profitable; 2023-2025 all negative
- Live 2026 shadow: 2W-5L, -48.8% ROI (7 signals)

### Phase 1: Operational Touchpoints Identified

| File | Line(s) | Type | Action |
|---|---|---|---|
| `mlb_sim/pipeline/f5_runline_status.json` | — | Status file | Updated to ARCHIVED |
| `mlb_sim/pipeline/f5_runline_signal_generator.py` | 418-420 | Generator | Added ARCHIVED gate |
| `run_model.py` | 1336-1343 | Caller | No change needed (try/except, returns []) |
| `push_results.py` | 411 | JSON push | No change needed (file still exists, just empty signals) |
| `dashboard.py` | — | Display | No references found |
| `mlb_sim/pipeline/f5_runline_tracker.py` | — | Perf tracker | No change needed |
| `mlb_sim/pipeline/line_overrides.py` | 47 | Market enum | No change needed (enum value only) |

### Phase 2: Signal Generation Disabled
1. `f5_runline_status.json` set to `"status": "ARCHIVED"`
2. Added explicit ARCHIVED gate in `run_daily()` — returns `[]` before any API calls or signal generation
3. Verified: `run_daily("2026-04-12")` returns `[]` with log message confirming ARCHIVED status

### Phase 3: State/Label Correction
No dashboard references to Signal B found. No label changes needed.

### Phase 4: Tracker Preservation
All tracker files preserved (not deleted):

| File | Size | Last Modified |
|---|---|---|
| `mlb_sim/logs/f5_runline_2026.parquet` | 16,008 B | 2026-04-11 |
| `mlb_sim/logs/f5_runline_2026.json` | 4,572 B | 2026-04-11 |
| `mlb_sim/logs/f5_runline_lines_2026.parquet` | 11,036 B | 2026-04-12 |
| `mlb_sim/logs/f5_runline_performance_2026.json` | 519 B | 2026-04-12 |

### Phase 5: Post-Disable Dry Check
```
$ python3 -c "from mlb_sim.pipeline.f5_runline_signal_generator import run_daily; print(run_daily(2026-04-12))"
INFO:f5_runline:F5 run line ARCHIVED: Clean PIT-safe backtest: 53.9% hit rate, -6.2% ROI at -135...
Result: []
PASS
```

---

## Files Modified (allowed list only)

1. `mlb_sim/pipeline/f5_runline_status.json` — status SHADOW -> ARCHIVED
2. `mlb_sim/pipeline/f5_runline_signal_generator.py` — added ARCHIVED gate in run_daily()

## Files Created (documentation only)

1. `research/recovery/signal_b_archive/phase0_locked_archive_basis.md`
2. `research/recovery/signal_b_archive/SIGNAL_B_ARCHIVE_EXEC_SUMMARY.md`
3. `research/recovery/signal_b_archive/touchpoints.csv`

## Files NOT Modified

- `run_model.py` — no change needed (try/except wrapper handles empty return)
- `push_results.py` — no change needed (pushes JSON file regardless)
- `dashboard.py` — no Signal B references found
- All tracker/log files — preserved as-is for audit trail

## Reactivation Policy

Do not reactivate without:
1. New independent research basis (not xFIP gap alone)
2. PIT-safe backtest showing profitability at realistic vig
3. Minimum 50-game forward shadow validation
