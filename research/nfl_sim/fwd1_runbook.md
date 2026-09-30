# FWD1 Runbook — NFL sim v1 forward test, weeks 4-5

Reader model: `nfl_sim_v1_156cd057`
Generated: 2026-09-30T09:32:19Z

## Measured runtimes (D231)
- Sim: ~30s per game
- Input refresh: ~9 min (pull_nflverse 6s + ratings.py ~8min)
- IMPORTANT: ratings.py overwrites params_v1.json — always `git checkout nfl/sim/params_v1.json` after

## Input refresh (ONCE per week, Wednesday)
```bash
cd ~/mlb-model
python3 nfl/sim/pull_nflverse_inputs.py
python3 nfl/sim/ratings.py
git checkout nfl/sim/params_v1.json
python3 -m pytest nfl/sim/tests/test_freeze_v1.py -q  # must pass
```

## Week 4

### PIT@CLE — Fri 2026-10-02 00:15Z (Thu 8:15 PM ET)
Games: PIT@CLE

```bash
python3 nfl/sim/run_forward_v1.py --week 4 --window-hours 2.0
```

Latest safe start: **Fri 2026-10-02 00:02Z** (Thu 8:02 PM ET)
Runtime: 1 games × 30s = 0 min + 9 min refresh + 3 min margin
VM props slot: 23:45Z Thu (~0.3h old at run time)

### Sunday main + SNF (14 games) — Sun 2026-10-04 [13:30Z, 17:00Z, 20:05Z, 20:25Z, 00:20Z] (Sun 9:30 AM ET+)
Games: IND@WAS, TEN@BAL, NE@BUF, NYJ@CHI, JAX@CIN, DAL@HOU, ARI@NYG, LA@PHI, GB@TB, MIA@MIN, KC@LV, LAC@SEA, DEN@SF, DET@CAR

```bash
python3 nfl/sim/run_forward_v1.py --week 4 --window-hours 12.0
```

Latest safe start: **Sun 2026-10-04 13:11Z** (Sun 9:11 AM ET)
Runtime: 14 games × 30s = 7 min + 9 min refresh + 3 min margin
VM props slot: 02:00Z Sun (~11.2h old at run time)
**STALE**: VM slot is 11.2h old (> 3.0h). Manual pull required:
```bash
python3 nfl/pipeline/pull_hardrock_props.py --window-hours 2 --tag close \
  --out-dir data/odds_archive/nfl/props/season=2026/manual
```
Credit cost: ~10 per event × 1 region = 10 credits

### ATL@NO — Tue 2026-10-06 00:15Z (Mon 8:15 PM ET)
Games: ATL@NO

```bash
python3 nfl/sim/run_forward_v1.py --week 4 --window-hours 2.0
```

Latest safe start: **Tue 2026-10-06 00:02Z** (Mon 8:02 PM ET)
Runtime: 1 games × 30s = 0 min + 9 min refresh + 3 min margin
VM props slot: 23:45Z Mon (~0.3h old at run time)

## Week 5

### TB@DAL — Fri 2026-10-09 00:15Z (Thu 8:15 PM ET)
Games: TB@DAL

```bash
python3 nfl/sim/run_forward_v1.py --week 5 --window-hours 2.0
```

Latest safe start: **Fri 2026-10-09 00:02Z** (Thu 8:02 PM ET)
Runtime: 1 games × 30s = 0 min + 9 min refresh + 3 min margin
VM props slot: 23:45Z Thu (~0.3h old at run time)

### Sunday main + SNF (13 games) — Sun 2026-10-11 [13:30Z, 17:00Z, 20:05Z, 20:25Z, 00:20Z] (Sun 9:30 AM ET+)
Games: PHI@JAX, CIN@MIA, LV@NE, MIN@NO, CLE@NYJ, IND@PIT, HOU@TEN, NYG@WAS, CHI@GB, DEN@LAC, DET@ARI, SF@SEA, BAL@ATL

```bash
python3 nfl/sim/run_forward_v1.py --week 5 --window-hours 12.0
```

Latest safe start: **Sun 2026-10-11 13:11Z** (Sun 9:11 AM ET)
Runtime: 13 games × 30s = 6 min + 9 min refresh + 3 min margin
VM props slot: 02:00Z Sun (~11.2h old at run time)
**STALE**: VM slot is 11.2h old (> 3.0h). Manual pull required:
```bash
python3 nfl/pipeline/pull_hardrock_props.py --window-hours 2 --tag close \
  --out-dir data/odds_archive/nfl/props/season=2026/manual
```
Credit cost: ~10 per event × 1 region = 10 credits

### BUF@LA — Tue 2026-10-13 00:15Z (Mon 8:15 PM ET)
Games: BUF@LA

```bash
python3 nfl/sim/run_forward_v1.py --week 5 --window-hours 2.0
```

Latest safe start: **Tue 2026-10-13 00:02Z** (Mon 8:02 PM ET)
Runtime: 1 games × 30s = 0 min + 9 min refresh + 3 min margin
VM props slot: 23:45Z Mon (~0.3h old at run time)

## Scoring

```bash
python3 nfl/pipeline/log_ai_opinions.py score-experiment --experiment nfl_fwd_v1
```

## Notes

- **Anchor rule (D210):** game whose anchored mean misses market by > 1.0 pt = unanchored, reported separately.
- **Game lines (h2h, spreads, totals):** always no_view (sim is market-anchored).
- **Pilot files:** never pooled; only with `--include-pilot`.
- **500 legs = descriptive; 1,500 legs = confirmatory.**
