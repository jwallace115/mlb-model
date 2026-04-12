# MLB SIDES PHASE 7 -- EXEC SUMMARY
## Operational Shadow Deployment: night_dog + bp_adv_dog

**Date**: 2026-04-12

---

## Objects Deployed

| Object | Definition | Historical OOS ROI | Expected Freq |
|--------|-----------|-------------------|---------------|
| night_dog | MIXED + night game (local >= 17h) -> back dog | +6.50% (N=268) | ~268/season |
| bp_adv_dog | MIXED + dog BP ERA < fav BP ERA -> back dog | +3.73% (N=179) | ~179/season |

---

## Infrastructure

### Script
`mlb/pipeline/mlb_sides_daily_shadow.py`

### Modes
- `--date YYYY-MM-DD`: Run daily shadow for a given date
- `--grade`: Grade ungraded signals from past dates via MLB Stats API
- `--summary`: Print cumulative performance for both objects
- `--trace-bp N`: Print BP ERA audit trail for N bp_adv_dog signals

### Trackers
- `mlb/logs/mlb_mixed_night_dog_shadow_2026.json`
- `mlb/logs/mlb_mixed_bp_adv_dog_shadow_2026.json`

### Data Sources
- Schedule: MLB Stats API (`/api/v1/schedule`)
- ML lines: The Odds API (h2h market, pinnacle preferred)
- SP FIP: pitcher_game_logs.parquet (starter_flag==1, expanding FIP)
- BP ERA: pitcher_game_logs.parquet (starter_flag==0, expanding ERA)
- Offense: game_table.parquet (rolling 20-game runs/game)
- Historical odds: mlb_odds_closing_canonical.parquet (2022-2025)

---

## Frozen Thresholds (Discovery 2022-2023, p50)

| Feature | Threshold |
|---------|-----------|
| SP FIP diff | 0.814 |
| Offense R20 diff | 0.800 |
| BP ERA diff | 0.583 |

Close-game universe: fav_implied in [0.512, 0.556].

---

## Dry Run Results (2026-04-12)

- 15 games on slate
- 4 games in close-game universe
- 2 MIXED classifications (SFG@BAL, BOS@STL)
- 0 night_dog signals (all close games were day games)
- 2 bp_adv_dog signals:
  - SFG @ BAL: back SFG +113 (BAL bp=4.570 > SFG bp=4.310)
  - BOS @ STL: back STL +110 (BOS bp=4.636 > STL bp=4.480)
- BP ERA trace verified: cumulative ER/IP match PGL source exactly

---

## Monitoring Rules

| Rule | Threshold |
|------|-----------|
| Kill switch | ROI < -15% after 50+ bets |
| Promotion gate | ROI > 0% after 100+ bets |

---

## Daily Operation

```bash
# Morning: generate signals
python3 mlb/pipeline/mlb_sides_daily_shadow.py --date $(date +%Y-%m-%d)

# Next morning: grade yesterday's signals
python3 mlb/pipeline/mlb_sides_daily_shadow.py --grade

# Weekly: check cumulative performance
python3 mlb/pipeline/mlb_sides_daily_shadow.py --summary
```

---

## Activation Decision

Shadow mode begins 2026-04-12. Minimum 50 graded signals required before any go/no-go decision.
At ~1-3 signals/day, expect 50-signal gate around late May 2026.

---

## Files
- `phase0_locked_specs.md` -- frozen thresholds and object definitions
- `MLB_SIDES_PHASE7_EXEC_SUMMARY.md` -- this file
- `MLB_SIDES_PHASE7_FINAL_TABLE.csv` -- signal log snapshot
- `mlb/pipeline/mlb_sides_daily_shadow.py` -- operational script
- `mlb/logs/mlb_mixed_night_dog_shadow_2026.json` -- night_dog tracker
- `mlb/logs/mlb_mixed_bp_adv_dog_shadow_2026.json` -- bp_adv_dog tracker
