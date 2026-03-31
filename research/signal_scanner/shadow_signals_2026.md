# Shadow Signals — 2026 Monitoring Definitions

These signals passed holdout validation but are NOT deployed live.
They will be tracked in shadow mode through the 2026 season for
forward validation before any deployment decision.

---

## P11: Combined Swinging Strike Rate

**Formula (frozen):**
```
P11 = (home_sp_whiff_rate + away_sp_whiff_rate) / 2
```

**Source:** `pitcher_statcast_per_start_starters_only.parquet`
- `whiff_rate` = swinging strikes / total swings (per start, Statcast pitch-level)

**Direction:** UNDER (higher combined whiff → more run suppression)

**Qualifying game criteria:**
- Both home and away starters must have Statcast whiff_rate available
- Game must have closing total and actual total for grading
- Regular season only

**What to log per game:**
- `game_id`, `date`, `home_team`, `away_team`
- `home_sp_whiff_rate`, `away_sp_whiff_rate`
- `P11_value` = average of the two
- `P11_top20_flag` = 1 if P11 >= 2024-defined 80th percentile cutoff
- `closing_total`, `actual_total`
- `actual_under` = 1 if actual < closing, 0 if actual > closing
- `implied_under` from under_price

**2024-defined top-20% cutoff:** To be computed from first full Statcast pull of 2026 starters using 2024 reference distribution.

**Backtest reference:**
- Pooled top-20% ROI: +8.7%
- 2025 holdout top-20% ROI: +19.4%
- 2025 permutation: 100th percentile
- Robustness: p=0.0001 after controls
- S12 independence: p=0.0000

**Reassessment trigger:** After 200 qualifying 2026 games with both starters in Statcast data.

---

## P10: Whiff Rate × CSW Interaction

**Formula (frozen):**
```
P10 = home_sp_whiff_rate * home_sp_csw_pct / 100
```

**Source:**
- `whiff_rate` from `pitcher_statcast_per_start_starters_only.parquet`
- `csw_pct` from `pitcher_start_metrics_per_start.csv` (CSW rolling 5-start)

**Direction:** UNDER (higher home whiff×CSW → stronger suppression)

**Qualifying game criteria:**
- Home starter must have both Statcast whiff_rate and pipeline CSW
- Game must have closing total and actual total
- Regular season only

**What to log per game:**
- `game_id`, `date`, `home_team`, `away_team`
- `home_sp_whiff_rate`, `home_sp_csw_pct`
- `P10_value` = whiff_rate × csw_pct / 100
- `P10_top20_flag` = 1 if P10 >= 2024-defined 80th percentile cutoff
- `closing_total`, `actual_total`
- `actual_under`, `implied_under`

**2024-defined top-20% cutoff:** To be computed from 2024 reference distribution.

**Backtest reference:**
- Pooled top-20% ROI: +6.9%
- 2025 holdout top-20% ROI: +13.4%
- 2025 permutation: 100th percentile
- Robustness: p=0.011 after controls
- S12 independence: p=0.021

**Reassessment trigger:** After 200 qualifying 2026 games.

---

## combined_short_exit: Durable Starters OVER Amplifier

**Formula (frozen):**
```
combined_short_exit = avg(home_sp_short_exit_r15, away_sp_short_exit_r15)
where short_exit = fraction of last 15 starts with IP < 5.0
```

**Source:** Derived from `pitcher_start_adjusted_metrics.parquet` (IP per start)

**Direction:** OVER (LOW values = durable starters → favorable OVER zone)

**Role:** V1 OVER-lean amplifier candidate (p_under < 0.45 AND short_exit in bottom 20%)

**Qualifying game criteria:**
- Both starters must have ≥5 prior starts for rolling calculation
- V1 p_under must be available for direction context
- Regular season only

**What to log per game:**
- `game_id`, `date`, `home_team`, `away_team`
- `combined_short_exit_value`
- `combined_short_exit_favorable_zone` = 1 if value <= 0.133333
- `v1_direction_context` = OVER / UNDER / NONE
- `closing_total`, `actual_total`
- `actual_result_over`, `over_hit`, `market_residual_over`

**2024-defined bottom-20% cutoff:** 0.133333

**Config file:** `mlb_sim/pipeline/combined_short_exit_shadow_config.json`
**Shadow log:** `mlb_sim/logs/combined_short_exit_shadow_2026.json`
**Module:** `mlb_sim/pipeline/combined_short_exit_shadow.py`

**Backtest reference:**
- Walk-forward V1 bot20 pooled ROI: +4.9% (N=253)
- 2024: +8.4%, 2025: +1.8%
- Permutation: 88th percentile (PASS)
- Robustness: p=0.004 after 7 controls
- Market awareness: r=+0.16 (mostly missed)
- Availability bias: CLEAN (0.000)

**Promotion gates (manual review only):**
- N ≥ 100 in favorable zone
- over_rate ≥ 57%
- ROI ≥ +3%
- permutation ≥ 85th percentile on 2026 data
- positive lift vs V1 OVER-lean baseline
- NO auto-promotion

**Reassessment trigger:** After 100 qualifying V1+short_exit games in 2026.

---

## Shelved Signals (not monitoring)

| Signal | Reason |
|--------|--------|
| P03 chase_gap | Absorbed by controls (p=0.71). No incremental value. |
| COMMAND_INDEX | Overfit on thin sample. Does not outperform P11 alone. corr(CMD, S12)=0.70. |

---

## Archived Signals (research complete, not monitoring)

| Signal | Status | Note |
|--------|--------|------|
| combined_lineup_iso | ARCHIVE | Standalone OVER predictor (p=0.0001) but harmful inside V1 OVER-lean stack. Market pre-adjusts high-ISO environments when V1 leans OVER. Revisit only as standalone OVER concept outside V1 framework. |
| ST02 road_trip_6plus | INVESTIGATE | Walk-forward 2024 negative, 2025 positive. Monitor in 2026 but not shadow-tracked. |
| adj_k_rate_last3 | INVESTIGATE | Walk-forward 2024 negative, 2025 strong. Monitor in 2026 but not shadow-tracked. |
| OV001 bb_x_hard_hit | INVESTIGATE | V1 OVER interaction 2024-driven, 2025 negative. Monitor in 2026. |
| OV043 bullpen_overuse | SHELVE | Walk-forward kills static result. 2025 negative, permutation fails. |

---

## Next Scanner Priorities

After shadow monitoring is established, the following signals are queued for deep analysis:

1. **P08 extension_gap** — survived triage, not yet deep tested
2. **P06 exit_velo_gap** — survived triage, not yet deep tested
3. **Umpire interactions** — triaged, all SHELVED (no residual signal)
4. **Weather interactions** — triaged, all SHELVED (no residual signal)
