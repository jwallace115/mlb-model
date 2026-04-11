# NHL Shadow Deployment: Executive Memo

## Date: 2026-04-11
## Status: DEPLOYED AND VERIFIED

---

## Summary

The NHL daily pipeline has been updated to use the PK%-corrected aligned Ridge models
with zero drift. The pipeline was dry-run successfully on 2026-04-11 (15-game slate),
producing 2 qualified signals and writing to both nhl_decisions.parquet and the new
aligned shadow tracker.

## Changes Made to nhl/nhl_daily_pipeline.py

| # | Change | Old Value | New Value |
|---|--------|-----------|-----------|
| 1 | REBUILD_HOME path | research/recovery/nhl_rebuild/model_A_home.pkl | research/recovery/nhl_final_alignment/model_A_home.pkl |
| 2 | REBUILD_AWAY path | research/recovery/nhl_rebuild/model_A_away.pkl | research/recovery/nhl_final_alignment/model_A_away.pkl |
| 3 | VALIDATE_DRIFT | 0.4458 | 0.0 |
| 4 | Shadow tracker write | (none) | Writes to nhl/logs/nhl_shadow_aligned_2026.json after each pipeline run |

No other logic was changed. Tiers, thresholds, sim parameters, stop rules, and grading
logic are all unchanged.

## Dry Run Results (2026-04-11)

- Games on slate: 15 (13 with odds from Odds API)
- Lambda total range: 5.45 - 6.34 (all within sane 4.5-7.5 range)
- Signals generated: 2
  - VGK @ COL UNDER 6.5 edge=0.145 tier=SHADOW_MEDIUM
  - VAN @ SJS UNDER 6.5 edge=0.182 tier=HIGH
- Decisions file: 785 total rows (appended)
- Shadow tracker: 2 signals written
- No errors, no warnings (except 2 games without odds)

## Model Validation

- Aligned home model: 29 features, intercept=3.2679
- Aligned away model: 29 features, intercept=3.0564
- League-average lambda total (drift=0.0): 6.26 (was 6.71 with old drift)
- Same feature set as rebuild models (verified identical feature names)

## Active Configuration

- HIGH tier: ACTIVE (edge >= 0.15, not high-vol) -- 1.0 stake units
- MEDIUM tier: SHADOW (edge >= 0.12) -- 0.0 stake units
- LOW tier: SHADOW (edge < 0.12) -- 0.0 stake units
- Evaluation date: 2026-05-01

## Monitoring Checklist

Daily:
- [ ] Pipeline runs without error (check logs)
- [ ] Lambda totals in 4.5-7.5 range
- [ ] Signals appear in both decisions parquet and shadow tracker
- [ ] Grade yesterday's signals (--grade-yesterday flag)

Weekly:
- [ ] Check pred-vs-actual bias (target: within +/- 0.2)
- [ ] Review HIGH tier win rate (target: >= 52%)
- [ ] Review signal count per tier

At 50+ graded games:
- [ ] Compute live bias; recalibrate drift if |bias| > 0.2
- [ ] Assess regime stability (no month below 45% WR)

## Files

| File | Location | Purpose |
|------|----------|---------|
| nhl/nhl_daily_pipeline.py | Server | Modified pipeline (4 changes) |
| nhl/nhl_daily_pipeline.py.bak.20260411 | Server | Pre-change backup |
| nhl/logs/nhl_shadow_aligned_2026.json | Server | New aligned shadow tracker |
| nhl/data/nhl_stop_rules.json | Server | Tier stop rules (unchanged) |
| research/recovery/nhl_shadow_deploy/ | Both | This documentation |

## Rollback

If issues arise, restore the backup:
```bash
cp nhl/nhl_daily_pipeline.py.bak.20260411 nhl/nhl_daily_pipeline.py
```
This restores the old model paths (nhl_rebuild/) and VALIDATE_DRIFT=0.4458.
