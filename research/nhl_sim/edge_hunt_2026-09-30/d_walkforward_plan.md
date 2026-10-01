D WALK-FORWARD PLAN (2026-09-30)

For each target season T in 2012..2020, the walk-forward chain uses fit window = T-2, T-1.

xG verdict (D4): one frozen xg_v2.json serves 2010-2020 without refitting (AUC 0.74-0.76
on all seasons, mean 0.7525 vs 0.7467 on the 2021+ fit data). No per-window refit needed.

## Walk-forward schedule

| Target T | Fit window    | Constants source | Ratings fit | Commands |
|----------|---------------|------------------|-------------|----------|
| 2012     | 2010, 2011    | build_constants_v7.py --v8 --seasons 2010,2011 | ratings.py --seasons 2010,2011 --target 2012 | price_games.py --season 2012 |
| 2013     | 2011, 2012    | build_constants_v7.py --v8 --seasons 2011,2012 | ratings.py --seasons 2011,2012 --target 2013 | price_games.py --season 2013 |
| 2014     | 2012, 2013    | build_constants_v7.py --v8 --seasons 2012,2013 | ratings.py --seasons 2012,2013 --target 2014 | price_games.py --season 2014 |
| 2015     | 2013, 2014    | build_constants_v7.py --v8 --seasons 2013,2014 | ratings.py --seasons 2013,2014 --target 2015 | price_games.py --season 2015 |
| 2016     | 2014, 2015    | build_constants_v7.py --v8 --seasons 2014,2015 | ratings.py --seasons 2014,2015 --target 2016 | price_games.py --season 2016 |
| 2017     | 2015, 2016    | build_constants_v7.py --v8 --seasons 2015,2016 | ratings.py --seasons 2015,2016 --target 2017 | price_games.py --season 2017 |
| 2018     | 2016, 2017    | build_constants_v7.py --v8 --seasons 2016,2017 | ratings.py --seasons 2016,2017 --target 2018 | price_games.py --season 2018 |
| 2019     | 2017, 2018    | build_constants_v7.py --v8 --seasons 2017,2018 | ratings.py --seasons 2017,2018 --target 2019 | price_games.py --season 2019 |
| 2020     | 2018, 2019    | build_constants_v7.py --v8 --seasons 2018,2019 | ratings.py --seasons 2018,2019 --target 2020 | price_games.py --season 2020 |

## What each step builds

Per target season:
1. **Constants v8** from the 2-season fit window: attempt rates, goal rates per state,
   penalty rates, pull hazard, ev5_by_time_score, q (league xG per non-EN attempt).
2. **Ratings** (team + goalie + finishing term): K/w hyperparameters from the fit window,
   applied point-in-time to the target season's games.
3. **Prices**: 2,000 sims per game, seed = game_id. Same engine, same schema.

## Structural notes

- 3v3 OT starts 2015-16 (4v4 before): the engine handles this through the OT state pairs;
  constants must be fit from the correct era.
- 2012-13 lockout (720 games): fit window 2011+2012 uses a full season + a short season.
- 2019-20 (1,082 games): target season is truncated but the fit window (2017+2018) is full.
- 2020-21 (868 games, divisional): fit window 2018+2019 is full.

## xG

Frozen xg_v2.json applied to all seasons without refitting. D-WO2 may validate this by
checking xG-derived rating quality per window.

## NOT in this plan

- The walk-forward itself (D-WO2 runs the commands).
- Refitting xG per window (not needed per D4 verdict).
- Any analysis on the prices (that's the hunt, not the infrastructure).
