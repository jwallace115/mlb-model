# FWD1 Runbook — NFL sim v1 forward test, weeks 4-5

Reader model: `nfl_sim_v1_156cd057`

## Measured runtimes (D231, week 3 pilot, 2026-09-30)

- `pull_nflverse_inputs.py`: 6s
- `ratings.py`: ~8 min (full rebuild; incremental would be faster)
- Sim: ~30s per game (14 games = 7 min; 16 games ≈ 8 min)
- Total pipeline for 14 games: ~16 min

## Input refresh commands

```bash
cd /tmp/eng-fwd2
python3 nfl/sim/pull_nflverse_inputs.py    # ~6s, refreshes depth_charts/injuries/rosters
python3 nfl/sim/ratings.py                 # ~8 min, rebuilds team/usage/tendency ratings
# IMPORTANT: ratings.py overwrites params_v1.json — restore immediately:
git checkout nfl/sim/params_v1.json
```

## Week 4 kick windows

### TNF PIT@CLE — Fri 2026-10-02 00:15Z (Thu 8:15 PM ET)

```bash
python3 nfl/sim/run_forward_v1.py --week 4 --window-hours 2
```

Latest safe start: **23:55Z Thu 10-01** (7:55 PM ET).
Budget: 2h window captures only TNF. 1 game × 30s ≈ 0.5 min + 8 min refresh = 9 min total.
Newest HR props pull: the VM's Thu 22:00Z slot (~2 h old). OK.

### London JAX@IND — Sun 2026-10-05 13:30Z (Sun 9:30 AM ET)

```bash
python3 nfl/sim/run_forward_v1.py --week 4 --window-hours 1.5
```

Latest safe start: **12:55Z Sun 10-05** (8:55 AM ET).
Budget: 1 game × 30s + 8 min refresh = 9 min total.
Newest HR props pull: VM's Sat 14:00Z slot (~23 h old). No Sunday slot before 15:00Z.
Jeff's manual props pull command:

```bash
# Write manual props for London game — credit cost: 1 × 10 × 1 = 10 credits (historical, 1 market, 1 region)
python3 nfl/pipeline/pull_odds.py --sport americanfootball_nfl \
  --markets player_receptions,player_rush_attempts \
  --bookmakers hardrockbet_fl \
  --out data/odds_archive/nfl/props/season=2026/manual/london_wk4_$(date +%Y%m%dT%H%M%SZ).parquet
```

### Sunday 1 PM + 4 PM + SNF — Sun 2026-10-05 17:00Z / 20:05Z / 20:25Z / Mon 00:20Z

```bash
python3 nfl/sim/run_forward_v1.py --week 4 --window-hours 9
```

Latest safe start: **16:40Z Sun 10-05** (12:40 PM ET).
Budget: ~12 games × 30s = 6 min + 8 min refresh = 14 min total. 9h window: 17:00Z–02:00Z.
Newest HR props pull: VM's 16:00Z slot (~40 min old). OK.

### MNF — Tue 2026-10-07 00:15Z (Mon 8:15 PM ET)

```bash
python3 nfl/sim/run_forward_v1.py --week 4 --window-hours 2
```

Latest safe start: **23:55Z Mon 10-06** (7:55 PM ET).
Budget: 1–2 games × 30s + 8 min refresh = 9 min total.
Newest HR props pull: VM's Mon 23:45Z MNF slot (~10 min old). If it hasn't landed,
the newest is Sunday 16:00Z (~32 h old → HALT on stale quotes). Check the sheet's
printed source age.

## Week 5 kick windows

### TNF — Fri 2026-10-10 00:15Z (Thu 8:15 PM ET)

```bash
python3 nfl/sim/run_forward_v1.py --week 5 --window-hours 2
```

Latest safe start: **23:55Z Thu 10-09**.

### Sunday main + SNF — Sun 2026-10-12 17:00Z / Mon 00:20Z

```bash
python3 nfl/sim/run_forward_v1.py --week 5 --window-hours 9
```

Latest safe start: **16:40Z Sun 10-12**.

### MNF — Tue 2026-10-14 00:15Z (Mon 8:15 PM ET)

```bash
python3 nfl/sim/run_forward_v1.py --week 5 --window-hours 2
```

Latest safe start: **23:55Z Mon 10-13**.

## Scoring

### score-experiment (canonical reader, cross-week)

```bash
PYTHONPATH=/tmp/eng-fwd2 python3 nfl/pipeline/log_ai_opinions.py \
  score-experiment --experiment nfl_fwd_v1
```

### At 500 scored two-way legs (estimated: ~week 7-8)

```bash
PYTHONPATH=/tmp/eng-fwd2 python3 nfl/pipeline/log_ai_opinions.py \
  score-experiment --experiment nfl_fwd_v1
```

The primary statistic is descriptive at <500 legs, confirmatory at >1,500.

### Per-week scoring

```bash
for w in 3 4 5; do
  PYTHONPATH=/tmp/eng-fwd2 python3 nfl/pipeline/log_ai_opinions.py score --week $w \
    --out research/nfl_sim/fwd1_score_w${w}.md
done
```

## Notes

- **Anchor rule (D210):** a game whose final anchored mean misses the market by > 1.0
  point on margin OR total is "unanchored"; its props are scored but reported separately.
- **Game lines (h2h, spreads, totals):** always no_view (the sim is market-anchored).
- **Pilot files:** never pooled; only included with `--include-pilot`.
- **Props slots (VM, WO12 deploy):** Tue 14:00 open; Wed-Sat 14:00 and Tue-Sat 02:00 mid;
  Thu 22:00 (TNF); Sun 15:00 and 16:00 close; Mon 23:45 (MNF).
- **ratings.py overwrites params_v1.json** — always `git checkout nfl/sim/params_v1.json`
  after running it, or test_freeze_v1 will fail.
- **London manual pull:** costs 10 credits per call (1 market × 10 historical factor × 1 region).
