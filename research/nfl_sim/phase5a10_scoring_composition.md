# Phase 5A-10: scoring-event composition — where the key-number mass really lives

**Executed by Cowork directly, 2026-09-16.** Diagnostic + two fixes (D35, D36), each
measured on the full K1 protocol (1,087 games × N = 500, drive log on; two runs, 2,100 s
each, cloud). Script: `nfl/sim/scoring_composition.py`; actual table
`nfl/data/sim/tables/actual_scoring_composition_2021_2024.parquet` (per game per team:
TDs by PAT outcome 7 / 6 / 8, FGs made and missed, defensive/return TDs conceded, safeties
conceded, Q4-drive TDs and FGs; reconstructs the final score in 99.6% of team-games — the
8 misses are defensive two-point returns and try rows the parser does not see).

## 1. The question

5A-9 left the headline where it was: P(|final| = 3) 8.1% vs 14.5% real, with the whole
margin histogram a smoothed version of reality already at 5:00 although the per-team
means of TDs and FGs were right. Is the composition of scoring events wrong, and where?

## 2. The composition is right on average — and wrong in structure

Per team-game (actual | sim, 5A-9 engine): TDs 2.38 | 2.45, of which XP made 2.02 | 2.07,
no XP 0.24 | 0.26, two-point 0.11 | 0.12; FGs made 1.67 | 1.59, missed 0.29 | 0.27;
defensive/return TDs conceded 0.12 | 0.11; safeties 0.024 | 0.033; XP-miss share 10.2 |
10.7%; two-point share 4.7 | 4.7%; FG make 85.1 | 85.6%. Distributions of TDs per team and
FGs per team match cell for cell (variances 1.94 | 1.94 and 1.47 | 1.41). Q4-drive TDs
0.548 | 0.543; Q4-drive FGs 0.359 | 0.312 (−13%, concentrated in close games: 1.12 vs 0.87
per game when |final| ≤ 3).

The structure is where it breaks. Write the margin as 7·(TD difference) + 3·(FG
difference) + noise, where the noise is XP misses, two-point tries, defensive TDs and
safeties. Then:

| composition | share of games act \| sim | P(margin lands on the nominal number) act \| sim (5A-9) |
|---|---|---|
| 3 (equal TDs, one FG apart) | 11.2 \| 9.5% | **71.3 \| 45.0%** |
| 6 (equal TDs, two FGs apart) | 6.3 \| 5.3% | 39.7 \| 38.5% |
| 7 (one TD apart, equal FGs) | 9.2 \| 9.0% | 48.0 \| 56.1% |
| 0 (equal TDs, equal FGs) | 3.3 \| 3.8% | 5.6 \| 9.8% (a tie) |

Given a "3-composition", the real margin is exactly 3 in 71% of games and off by one (2
or 4) in 10%; the sim was exactly 3 in 45% and off by one in 29%. Per-team rates of the
noise events match, but real off-events are *placed* — a two-point try happens at the
score where it lands the margin on a key number — while the sim's were spread.

## 3. Two causes found

**D35 — the two-point decision was bucketed, and the real decision is exact.** The old
table keyed (quarter × 7 score buckets): Q4 "trail 1–8 after the TD" = 34% everywhere.
Measured by the exact post-TD differential (2021–2024, n per cell 16–284): down 2 → 97%,
down 5 → 97%, up 1 → 97%, down 10 → 96%, up 5 → 96%, up 12 → 75%, up 4 → 60% — and down
3 → 2%, down 7 → 2%, down 4 → 4%, tied → 1%, down 6 → 7%, up 2 → 4%. The bucket smeared
a near-deterministic rule: a team down 3 after its TD went for two a third of the time
(landing on 1 or 3 at random), a team down 5 kicked two-thirds of the time (landing on 4
instead of 3). New table: complete grid, period (Q1-3 / Q4+) × exact post-TD differential
−16…+16 (pooled beyond), each cell shrunk toward its period × bucket parent with k measured
by method of moments (1.8 / 10.7 / 4.5 — the cells stand on their own data). The table is
loaded through `_CACHE` so it can be perturbed in tests.

**D36 — one uniform decided the two-point question and then the XP make.** `u_pat`
decided "go for two"; conditional on kicking it is ≥ p_2pt, so the XP make draw
`u_pat < xp_rate` was biased low by exactly p_2pt/(1 − p_2pt)·(1 − xp): with the Q4
trailing buckets at 34–43% the effective make rate was ~92%, and the K1 XP-miss rate was
6.2% vs 5.1% measured — extra off-by-one noise exactly in close Q4 games. The two-point
conversion also borrowed the OT coin-flip uniform. Both now have their own draws.

## 4. K1 after D35 + D36 (actual → 5A-9 → 5A-10)

| \|m\| | actual | 5A-9 | 5A-10 | | \|m\| | actual | 5A-9 | 5A-10 |
|---|---|---|---|---|---|---|---|---|
| 0 | 0.3 | 0.7 | 0.9 | | 7 | 7.3 | 7.0 | 9.1 |
| 1 | 4.7 | 5.6 | 4.1 | | 8 | 4.5 | 3.8 | 3.4 |
| 2 | 5.2 | 4.9 | 3.8 | | 9 | 2.0 | 3.6 | 2.6 |
| **3** | **14.5** | **8.1** | **10.6** | | 10 | 5.1 | 4.9 | 6.2 |
| 4 | 4.9 | 5.8 | 5.0 | | 11 | 1.5 | 3.9 | 3.6 |
| 5 | 4.6 | 4.0 | 3.9 | | 13 | 1.7 | 3.7 | 3.3 |
| 6 | 7.5 | 5.3 | 4.5 | | 14 | 4.3 | 3.8 | 4.7 |

P(|m| = 3) 8.1 → **10.6%** (14.5); the 3-composition now lands on 3 in 60.6% (71.3);
|m| ≤ 7 41.4 → 41.8% (49.0); SD 15.12 → 15.17 (14.20); by season 10.7 / 10.7 / 10.3 / 10.5%.
Mass moved from the off-numbers to 3, 7, 10 and 14 — and now overshoots 7 (9.1 vs 7.3) and
10 (6.2 vs 5.1) while 6 fell further (4.5 vs 7.5) and 1 / 2 went under. The exact-3 rule
now shows the structure of what is left:

| composition | P(nominal) act \| sim | P(nominal − 1) | P(nominal + 1) |
|---|---|---|---|
| 3 | 73.0 \| 60.6 | 4.9 \| 8.7 | 5.7 \| 11.1 |
| 6 | 39.7 \| 38.5 | 19.1 \| 14.3 | 13.2 \| 20.8 |
| 7 | 48.0 \| 56.1 | **24.0 \| 11.3** | 10.0 \| 9.7 |
| 14 | 62.2 \| 48.6 | 4.4 \| 11.2 | 8.9 \| 8.6 |
| 0 | 5.6 \| 15.1 | — | 38.9 \| 32.1 |

Real one-TD-apart games land on **6** a quarter of the time (a missed XP or failed try on
the leading side, or a made try on the trailing side and a miss elsewhere) — the sim only
11%; the sim's 3-compositions still carry twice the real ±1 noise; composition-tied games
end tied 15% vs 5.6% (the OT problem: 19% of sim OT games end tied, real 4.3%). So the
noise events are now placed right on average but still not *where* reality places them.

## 5. Two more structural facts, measured but not fixed

1. **The two teams' TD counts are positively correlated in real games and independent in
   the sim**: corr(td_home, td_away) 0.12 vs 0.01; total TDs per game variance 4.31 vs
   3.95. Real games share an environment (pace, weather, officiating, the way both
   offences play the same game); the sim's two offences are conditionally independent
   given the ratings. Fewer equal-TD games follow (23.3% vs 21.6%) — every one of them a
   candidate for a 3 or a 6.
2. **Q4 FGs are 13% short**, all of it in close games (Q4-drive FGs 1.12 vs 0.87 per game
   when |final| ≤ 3) — the end-of-game FG count is still the 5A-9 residual (tied drives
   that reach the 35 get the kick off 54% vs 85%).

## 6. Tests

`test_engine_5a10.py` (4, all green): exact-grid two-point table with the measured
decisions; XP make rate equals the measured league rate with the two-point decision off
(D36; 0.949 ± 0.01); P(|m| = 3) within 0.035 of 0.145 on the 12-game sample (0.112);
3-composition exactness within 0.10 of 0.713. The `test_dead_twopt_decision` placeholder
(`assert True` since 5A-5) is now a real perturbation test. Full suite on this commit: see
`logs/agent_sessions.md`.

## 7. Next (5A-11)

1. OT: 19% of sim OT games end tied vs 4.3% (OT drives: FG 13% vs 26%, expiry 10% vs 1%)
   — the OT possession/decision behaviour has never been audited.
2. Placement of the noise events: XP-miss and two-point outcomes by state and quarter
   (real one-TD-apart games land on 6 in 24%, sim 11%) and the 3-composition ±1 noise.
3. Game-level correlation of the two offences (shared environment factor; measured from
   the residual correlation of the two teams' scoring after ratings).
4. Q4 FG count / end-of-game kick (5A-9 residual), 4th-down conversion 45% vs 57%,
   two-minute-drill expiry.
5. Then 5B (usage builder) and 5C (grader/pricer, maps) as planned.
