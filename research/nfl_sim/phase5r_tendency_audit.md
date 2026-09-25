# Phase 5R Item 1 — Measure the pace/PROE defect and the board's exposure

Date: 2026-09-25. Engine fingerprint: `02fbcab6e6ed042e` (unchanged).
Board re-run: 666s (11.1 min), 15 games, 15/15 converged.

## Pre-registered predictions (written before looking)

1. Every 2021-2026 week-1 team-week is on the default (pace == 28.0 and n_plays == 0).
2. K1 plays/game in weeks 1-2 exceed weeks 5+ by >= 8.
3. On the anchored Week 2 board the sim's team pass attempts exceed the book's QB attempt
   lines by >= 5 per team on average.

## Results

### (a) Tendency tables by season x week

| season | week | pace | proe | n_plays | defaults |
|--------|------|------|------|---------|----------|
| 2021 | 1 | 28.0 | 0.000 | 0 | 32 |
| 2021 | 2 | 33.6 | 0.249 | 64 | 0 |
| 2022 | 1 | 28.0 | 0.000 | 0 | 32 |
| 2023 | 1 | 28.0 | 0.000 | 0 | 32 |
| 2024 | 1 | 28.0 | 0.000 | 0 | 32 |
| 2025 | 1 | 28.0 | 0.000 | 0 | 32 |
| 2026 | 1 | 28.0 | 0.000 | 0 | 32 |
| 2026 | 2 | 33.4 | -0.615 | 56 | 2 |

Total team-weeks on default: 194 (32 per season × 6 seasons + 2 in 2026 week 2).

**Prediction (1): HELD.** All 32 teams in every season 2021-2026 have week-1 on the default.

Full-season pace by season: 2021 34.6, 2022 34.7, 2023 34.7, 2024 35.0, 2025 35.5.
The 28.0 default is 19-21% below the real full-season pace (34-35 s).

The situational table (`tendencies_situational_weekly.parquet`) has no `pace_sec` column — it
stores only by-bucket PROE. Its n_plays=0 rows use the prior season's league PROE by bucket.

### (b) K1 plays/drives/punts by week bucket

| bucket | n | sim plays | real plays | diff | sim drives | real drives | sim punts | real punts |
|--------|---|-----------|-----------|------|------------|-------------|-----------|------------|
| 1-2 | 128 | 139.7 | 124.0 | +15.7 | 25.4 | 21.8 | 9.4 | 7.8 |
| 3-4 | 128 | 126.9 | 124.4 | +2.5 | 23.2 | 21.9 | 8.6 | 8.0 |
| 5-8 | 234 | 128.6 | 124.7 | +3.9 | 23.5 | 22.0 | 8.7 | 7.8 |
| 9+ | 597 | 129.6 | 124.6 | +5.1 | 23.7 | 21.9 | 8.8 | 8.0 |
| ALL | 1087 | 130.3 | 124.5 | +5.8 | 23.8 | 21.9 | 8.8 | 7.9 |

**Prediction (2): HELD.** Weeks 1-2 plays/game 139.7 vs weeks 5-8 128.6 = diff 11.1 (>= 8).
Weeks 1-2 vs 9+ = diff 10.1. The excess is 15.7 plays/game in weeks 1-2, falling to 2.5-5.1
in later weeks. About (15.7 - 5.1) / 15.7 ≈ 67% of the weeks-1-2 excess is the pace defect.

### (c) Board team volume (post-anchoring, Week 2 2026)

Board re-run: `--week 2 --as-of 2026-09-20T15:30:00Z`. 15 games, 15/15 converged in 666s.

**NULL: sim_p/cal_p bit-identical to picks_log_mac.parquet: 1353/1353.** The team_volume LOG
is the only addition; no behaviour change.

Mean across 30 team-games:
- Sim pass attempts/team: 36.9
- Sim completions/team: 23.9
- Sim plays/team: 64.8

vs book's QB pass-attempt lines (26 teams with quoted lines):
- Mean (sim - book): **+6.1** per team
- Range: -2.4 (CIN) to +11.4 (NYJ)

**Prediction (3): HELD.** Sim pass attempts exceed book's QB lines by +6.1 on average (>= 5).

Derivation: sim pass attempts = sum of `pass_att` across all players in `player_df` per sim,
averaged across N sims. Book QB line = `player_pass_attempts` market from board candidates,
two-way lines only. Team volume saved to `team_volume.parquet` (30 rows).
