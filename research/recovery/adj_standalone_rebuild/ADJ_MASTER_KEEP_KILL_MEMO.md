# ADJ Standalone Signal — Keep/Kill Memo

## Live Code Identity
- Source: `mlb_sim/pipeline/shadow_signals.py`
- Feature source: `research/opponent_adjusted_engine_v2/pitcher_recent_adjusted_features.parquet`
- Features: per-start, shift(1) lagged rolling(3, min_periods=2) of opponent-adjusted metrics
- Gate: `combined = (home_val + away_val) / 2; favorable = combined > 0`
- V1 p_under: logged as context ONLY, does NOT gate firing
- Direction: UNDER when favorable_zone_flag = True

## Key Difference from Old Research
- Old scanner required V1 p_under > 0.57 as co-filter (interaction signal)
- Live standalone fires on combined > 0 alone (no V1 gate)
- This means more fires but potentially lower precision vs original scanner results

## Backtest Methodology
- Period: 2022-2025 regular season
- Starter identification: pitcher_game_logs.parquet (starter_flag=1)
- Feature lookup: most recent prf row where prf.game_date < game.date (no lookahead)
- Closing odds: mlb_odds_closing_canonical.parquet (last pull per game)
- ROI: flat $1 bet at actual closing under price

## Signal Verdicts

### ADJ_CONTACT: **DIMINISHED**
- N=3875, Hit=51.2%, ROI=-2.4%
  - 2022: N=797, Hit=50.9%, ROI=-3.2%
  - 2023: N=982, Hit=49.5%, ROI=-5.4%
  - 2024: N=1066, Hit=51.7%, ROI=-1.6%
  - 2025: N=1030, Hit=52.7%, ROI=+0.4%

### ADJ_HH: **DIMINISHED**
- N=3081, Hit=51.1%, ROI=-2.6%
  - 2022: N=777, Hit=50.7%, ROI=-3.5%
  - 2023: N=762, Hit=47.8%, ROI=-8.7%
  - 2024: N=869, Hit=51.0%, ROI=-2.8%
  - 2025: N=673, Hit=55.4%, ROI=+5.6%

### adj_k_rate_last3: **DIMINISHED**
- N=1539, Hit=52.1%, ROI=-0.6%
  - 2022: N=311, Hit=51.2%, ROI=-2.7%
  - 2023: N=407, Hit=50.6%, ROI=-3.1%
  - 2024: N=409, Hit=51.8%, ROI=-1.4%
  - 2025: N=412, Hit=54.7%, ROI=+4.1%

### ADJ_BB_RATE: **DIMINISHED**
- N=1587, Hit=50.6%, ROI=-3.6%
  - 2022: N=288, Hit=52.9%, ROI=+0.5%
  - 2023: N=421, Hit=51.7%, ROI=-1.4%
  - 2024: N=437, Hit=46.9%, ROI=-10.4%
  - 2025: N=441, Hit=51.5%, ROI=-1.8%

### ADJ_RUN_SUPP: **DIMINISHED**
- N=3159, Hit=51.5%, ROI=-1.8%
  - 2022: N=681, Hit=49.3%, ROI=-6.2%
  - 2023: N=776, Hit=50.8%, ROI=-3.0%
  - 2024: N=856, Hit=52.0%, ROI=-0.9%
  - 2025: N=846, Hit=53.4%, ROI=+1.8%

## Recommendation

**MONITOR**: ADJ_CONTACT, ADJ_HH, adj_k_rate_last3, ADJ_BB_RATE, ADJ_RUN_SUPP — continue shadow, do not weight in overlay