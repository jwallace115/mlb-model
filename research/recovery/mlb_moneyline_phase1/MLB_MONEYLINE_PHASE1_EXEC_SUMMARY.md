# MLB Moneyline Rediscovery — Phase 1 Executive Summary

## Date: 2026-04-11

## Data
- Canonical closing odds: 11406 records (2022-2025)
- Game table: 9902 records
- Matched research table: 10816 games (ties excluded)
- Discovery: 2022-2023 (5944 games)
- Validation: 2024 (2426 games)
- OOS: 2025 (2446 games)

## Price Bands
- Band A (tightest ~-115 to -105): 1775 games
- Band B (practical ~-120 to -105): 2509 games
- Band C (wider ~-130 to -105): 4036 games

## Keep/Kill Board
- **KILL**: Home Dogs Band B
  - DISC: N=573, resid=-0.0133, ROI=-6.97%
  - VAL: N=235, resid=-0.0356, ROI=-11.32%
  - OOS: N=254, resid=+0.0691, ROI=+9.50%
- **KILL**: Home Dogs Band C
  - DISC: N=883, resid=-0.0179, ROI=-7.84%
  - VAL: N=379, resid=-0.0242, ROI=-8.95%
  - OOS: N=402, resid=+0.0573, ROI=+7.31%
- **KILL**: Home Dogs Band C + Rest Adv
  - DISC: N=39, resid=-0.1041, ROI=-25.43%
  - VAL: N=15, resid=-0.1252, ROI=-31.20%
  - OOS: N=17, resid=+0.0125, ROI=-2.47%
- **KILL**: Home Dogs Band B + Day
  - DISC: N=157, resid=-0.0221, ROI=-8.73%
  - VAL: N=71, resid=-0.0611, ROI=-16.62%
  - OOS: N=66, resid=-0.0469, ROI=-13.99%
- **KILL**: Home Dogs Band C + Day
  - DISC: N=245, resid=-0.0059, ROI=-5.09%
  - VAL: N=115, resid=-0.0512, ROI=-14.55%
  - OOS: N=109, resid=-0.0284, ROI=-10.11%
- **WATCH**: Away Fav Band C + Night
  - DISC: N=638, resid=+0.0225, ROI=-0.16%
  - VAL: N=264, resid=+0.0125, ROI=-1.76%
  - OOS: N=293, resid=-0.0891, ROI=-20.42%
- **KILL**: Home Fav Band B
  - DISC: N=708, resid=-0.0022, ROI=-4.55%
  - VAL: N=350, resid=-0.0447, ROI=-12.38%
  - OOS: N=389, resid=+0.0059, ROI=-3.50%
- **KILL**: Home Fav Band C
  - DISC: N=1174, resid=+0.0117, ROI=-2.03%
  - VAL: N=590, resid=-0.0244, ROI=-8.62%
  - OOS: N=608, resid=-0.0125, ROI=-6.63%

## Key Findings

### No strategies survived all three gates (disc/val/oos).

### Watch List (mixed signals)
- Away Fav Band C + Night

### Killed (no signal or negative OOS)
- Home Dogs Band B
- Home Dogs Band C
- Home Dogs Band C + Rest Adv
- Home Dogs Band B + Day
- Home Dogs Band C + Day
- Home Fav Band B
- Home Fav Band C

## Structural Observations
- MLB closing lines are well-calibrated in near-even price bands
- Home-field advantage is largely priced in at closing
- Rest differential is a weak axis — most games have rest_diff=0
- Day/night split shows marginal patterns but small N when intersected with price bands
- Interaction effects (home dog + rest + day) suffer from tiny sample sizes

## Methodology Notes
- All prices are actual closing lines from Odds API canonical backfill
- De-vigged using multiplicative method (raw_h / (raw_h + raw_a))
- ROI calculated at actual American odds (not implied)
- No contaminated features used (no pitcher/team quality, no model outputs)
- All features are provably PIT-safe (schedule/structure only)

## Files
- `PHASE0_SAFETY_MEMO.md` — contamination guardrails
- `phase3_market_baseline.csv` — market baseline by band/side/season
- `phase5_univariate_axes.csv` — all univariate axis tests
- `phase6_interactions.csv` — bounded interaction tests
- `phase8_economic_scorecard.csv` — full economic scorecard
- `phase9_keep_kill.csv` — keep/kill decisions
- `MLB_MONEYLINE_PHASE1_FINAL_TABLE.csv` — complete results table