# MLB Totals Closing Price Logging Fix — Executive Summary

**Date:** 2026-04-12
**File modified:** `mlb_sim/pipeline/shadow_signals.py`
**Other files modified:** None

## Problem

Shadow signal records (ADJ_CONTACT, ADJ_HH, adj_k_rate_last3, ADJ_BB_RATE, ADJ_RUN_SUPP, ST02) log `closing_total` (the line number, e.g. 8.5) but NOT the closing under/over prices (e.g. -110/-110). Without prices, ROI calculations are impossible because the payout on a winning under bet depends on the juice.

The odds data IS available in the pipeline at call time — `modules/odds.py` returns per-book `over`/`under` American odds in the `full` dict — but `log_shadow_signals()` never accepted or stored these values.

## Fix

Two changes to `mlb_sim/pipeline/shadow_signals.py`:

1. **New helper function `extract_closing_prices(odds_dict)`** — extracts `closing_under_price`, `closing_over_price`, and `price_source` from the odds dict. Priority: pinnacle > draftkings > fanduel > best_under/best_over fallback.

2. **Extended `log_shadow_signals()` signature** — three new keyword args with `None` defaults:
   - `closing_under_price` (int, American odds, e.g. -110)
   - `closing_over_price` (int, American odds, e.g. -110)
   - `price_source` (str, e.g. "pinnacle", "draftkings")

   These are written to every shadow signal record (ST02 + all ADJ signals).

## Backward Compatibility

All new parameters default to `None`. Existing callers that do not pass prices continue to work unchanged — records will simply have `null` for the three new fields, same as the 820 existing records.

## Caller Integration (run_model.py — NOT yet applied)

To activate price logging, add 3 lines near line 1147 of `run_model.py`:

```python
# Before the log_shadow_signals call, add:
_prices = extract_closing_prices(odds)

# Then pass to log_shadow_signals:
log_shadow_signals(
    ...,
    closing_under_price=_prices["closing_under_price"],
    closing_over_price=_prices["closing_over_price"],
    price_source=_prices["price_source"],
)
```

And update the import at line 1138:
```python
from mlb_sim.pipeline.shadow_signals import (
    compute_st02, compute_adj_signals,
    log_shadow_signals, _v1_direction,
    extract_closing_prices,
)
```

## ROI Readiness

Once prices are flowing, a record is ROI-eligible when:
- `closing_under_price is not None`
- `actual_total is not None`
- `closing_total is not None`

Implied probability from American odds: if price < 0, `p = abs(price) / (abs(price) + 100)`; if price > 0, `p = 100 / (price + 100)`.

## Schema After Fix

| Field | Type | Example | New? |
|-------|------|---------|------|
| game_id | int | 822838 | No |
| date | str | "2026-04-12" | No |
| signal_name | str | "ADJ_CONTACT" | No |
| signal_value | float | 0.004396 | No |
| favorable_zone_flag | bool | true | No |
| v1_direction_context | str | "UNDER" | No |
| closing_total | float | 8.0 | No |
| home_team | str | "TOR" | No |
| away_team | str | "OAK" | No |
| market_line | float | 8.0 | No |
| model_projection | float | 8.4 | No |
| closing_under_price | int | -110 | **Yes** |
| closing_over_price | int | -110 | **Yes** |
| price_source | str | "pinnacle" | **Yes** |
| home_pitcher_value | float | 0.043 | No (ADJ only) |
| away_pitcher_value | float | -0.034 | No (ADJ only) |
| logged_at | str | ISO timestamp | No |
| actual_total | float | 15.0 | No (graded) |
| actual_over_under | str | "OVER" | No (graded) |
| result | str | "LOSS" | No (graded) |
| resolved | bool | true | No (graded) |

## Existing Data

820 records across 11 dates (2026-03-28 through 2026-04-12). All will have `null` for the three new price fields. No data loss or schema breakage.
