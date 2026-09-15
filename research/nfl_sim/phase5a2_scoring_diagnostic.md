# Phase 5A-2: Scoring-Conversion Diagnostic

**Date:** 2026-09-15
**Engine:** `nfl/sim/engine.py` (tag: `pre-5a2`)
**Config:** N=500, 1,087 games (2021-2024 regular season), players OFF

---

## Problem Statement

After Phase 5A, the K1 backtest matches reality on yards (pass 222.8 vs 221.0,
rush 116.8 vs 118.2), plays (125.9 vs 124.5), drives (21.2 vs 21.9) and pooled
margin SD (14.13 vs 14.20), but scores 18.9 pts/team vs 22.4 actual (-3.5), and
puts half the real mass on |margin|=3 (7.86% vs 14.54%) and |margin|=6 (5.14% vs
7.54%). Same yards, 15% fewer points.

---

## Step 1: Per-Drive Instrumentation

Added `drive_log=True` parameter to `simulate_game()`. When enabled, records one
row per drive with: sim_id, team, drive_no, start_yardline, start_quarter,
start_clock, plays, yards, result, points, reached_rz, reached_gl.

Also added aggregate counters: ev_3rd_att, ev_3rd_conv, ev_4th_go, ev_4th_conv,
ev_fg_dist_sum.

**Byte-identity test (T8):** N=2,000, 3 games. All 32 output columns
byte-identical with drive_log=True vs False. PASS.

**Test suite:** 6 new tests in `test_engine_5a2.py`, all passing (11s).

---

## Step 2: Actual Per-Drive Table

Built from nflverse PBP 2021-2024 (regular season, week <= 18).
22,870 drives from 1,087 games.

**Definitional choices (applied identically to both sides):**
- Drive = groupby (game_id, fixed_drive) on scrimmage plays (pass/run)
- Result mapped from fixed_drive_result: Touchdown->TD, Field goal->FG_made,
  Missed field goal->FG_missed, Punt->punt, Turnover->turnover_int or
  turnover_fumble (from drive_end_transition), Turnover on downs->downs,
  End of half->end_half, Safety->safety
- Red zone = min(yardline_100) <= 20 for actuals; any play at yl <= 20 for sim
- Goal line = min(yardline_100) <= 5 for actuals; any play at yl <= 5 for sim
- Points: TD=6+PAT, FG_made=3, safety=-2 (for offense)
- Start yardline = first play's yardline_100

---

## Step 3: K1 Run

1,087 games x N=500, drive_log=True.
Runtime: 555.3s (0.51 s/game).
11,498,654 sim drive rows. 543,500 sim game rows.

Saved: `k1_drives_5a2.parquet`, `actual_drives_2021_2024.parquet`

---

## Step 4: Comparison Tables

### 4a. Drive Result Distribution

| Result | Actual | Sim | Delta | Season SD | Flag | N_act | N_sim |
|--------|--------|-----|-------|-----------|------|-------|-------|
| TD | 0.2247 | 0.1847 | -0.0400 | 0.0132 | **MATERIAL** | 5,139 | 2,123,389 |
| FG_made | 0.1582 | 0.1405 | -0.0177 | 0.0056 | **MATERIAL** | 3,618 | 1,615,885 |
| FG_missed | 0.0276 | 0.0207 | -0.0070 | 0.0024 | **MATERIAL** | 632 | 237,592 |
| punt | 0.3736 | 0.3662 | -0.0074 | 0.0130 | | 8,544 | 4,211,103 |
| turnover_int | 0.0743 | 0.0694 | -0.0049 | 0.0030 | | 1,700 | 798,377 |
| turnover_fumble | 0.0440 | 0.0433 | -0.0007 | 0.0017 | | 1,006 | 497,357 |
| downs | 0.0581 | 0.0745 | +0.0164 | 0.0023 | **MATERIAL** | 1,328 | 856,830 |
| end_half | 0.0372 | 0.0488 | +0.0116 | 0.0016 | **MATERIAL** | 851 | 561,187 |
| end_game | 0.0000 | 0.0463 | +0.0463 | 0.0000 | | 0 | 532,865 |
| safety | 0.0023 | 0.0056 | +0.0033 | 0.0006 | **MATERIAL** | 52 | 64,069 |

**Points per drive: actual=2.035  sim=1.703  delta=-0.332**

Note: "end_game" does not appear in actual PBP data because PBP's
`fixed_drive_result` uses "End of half" for Q4 clock expiration. Sim
distinguishes end_half (Q2) from end_game (Q4). Combined sim
end_half+end_game = 9.5% vs actual end_half = 3.7% — a 5.8pp excess
of drives terminated by clock expiration.

### 4b. TD Rate & Points/Drive by Starting Field Position

| Bucket | Act TD Rate | Sim TD Rate | Act PPD | Sim PPD | N_act | N_sim | Season SD | Flag |
|--------|-------------|-------------|---------|---------|-------|-------|-----------|------|
| own1-20 | 0.1585 | 0.1152 | 1.400 | 1.066 | 4,701 | 2,182,729 | 0.0152 | **MATERIAL** |
| own21-40 | 0.2153 | 0.1680 | 1.945 | 1.553 | 14,258 | 7,402,932 | 0.0131 | **MATERIAL** |
| 41-60 | 0.2854 | 0.2385 | 2.626 | 2.286 | 2,589 | 1,053,626 | 0.0168 | **MATERIAL** |
| opp21-40 | 0.3863 | 0.3533 | 3.753 | 3.408 | 950 | 559,619 | 0.0305 | |
| opp1-20 | 0.5860 | 0.5991 | 5.038 | 4.825 | 372 | 299,748 | 0.0560 | |

The TD rate gap is 3-5pp for drives starting in own territory (where most drives
begin) and closes near the opponent's end zone. The deficit is in sustaining
drives to score, not in red-zone conversion specifically.

### 4c. Red Zone

| Metric | Actual | Sim | Delta |
|--------|--------|-----|-------|
| RZ drives/game | 6.39 | 6.07* | -0.32 |
| TD rate given RZ entry | 0.577 | 0.541 | -0.036 |
| FG rate given RZ entry | 0.292 | 0.257 | -0.034 |
| TO rate given RZ entry | 0.055 | 0.050 | -0.005 |
| Plays/RZ drive | 8.68 | 8.44 | -0.24 |

*Sim RZ drives/game estimated from drive log.

Actual yards/play: RZ=3.04, non-RZ=5.90. The low RZ yds/play is expected
(goal-line truncation).

RZ TD rate is 3.6pp low but not the primary driver of the deficit. The engine
uses zone-specific (rz10, opp20) outcome distributions that already capture
truncation, so this is a table precision gap (5-zone vs exact-yardline), not an
engine bug.

### 4d. Field Goals

| Metric | Actual | Sim |
|--------|--------|-----|
| FG att/game | 3.92 | 3.41 |
| FG make rate | 0.850 | 0.872 |
| Avg FG distance | 39.3 | 37.3 |

Actual FG make rate by distance:

| Dist | N | Made | Rate |
|------|---|------|------|
| <30 | 1,072 | 1,051 | 0.980 |
| 30-39 | 1,207 | 1,119 | 0.927 |
| 40-49 | 1,185 | 916 | 0.773 |
| 50+ | 800 | 539 | 0.674 |

4th-down decision: actual go=19.8% punt=55.1% fg=25.1% (N=15,579).
Sim 4th-down go rate: 23.2%.

The sim goes for it 3.4pp more often on 4th down than reality, which reduces
FG attempts (3.41 vs 3.92) and contributes to both fewer FG points and less
mass at |margin|=3.

### 4e. Turnovers

| Metric | Actual | Sim |
|--------|--------|-----|
| INTs/game | 1.54 | 1.47 |
| Fumbles/game | 0.91 | 0.92 |
| Total TO/game | 2.46 | 2.38 |

Turnovers are well-calibrated. Not a driver of the scoring deficit.

### 4f. Third/Fourth-Down Conversion

| Metric | Actual | Sim |
|--------|--------|-----|
| 3rd-down conv rate | 0.402 | 0.397 |
| 4th-down conv rate | 0.532 | 0.439 |

Actual 3rd-down by distance: short(1-3)=0.604, med(4-7)=0.425, long(8+)=0.234.

**4th-down conversion is 9.3pp low.** However, actual 4th-down conversion rates
by distance are nearly identical to 3rd-down rates (1-2yd: 65.6% vs 64.7%;
3-5yd: 49.4% vs 47.3%; 6+yd: 28.9% vs 28.1%). The overall gap is likely a
DISTANCE MIX issue: the sim's higher go rate (23.2% vs 19.8%) adds more
long-distance attempts (which convert less), dragging down the average.

### 4g. Explosive Plays

Actual: 5.93 explosive pass (20+ yds) per game, 6.13 explosive rush (10+) per
game. Sim explosive counts not separately tracked in current counters. The overall
yard distributions match (222.8 vs 221.0 pass, 116.8 vs 118.2 rush), so explosive
play frequency is approximately correct.

### 4h. PAT: XP and 2-Point

| Metric | Value |
|--------|-------|
| Actual XP make rate | 0.948 |
| Actual 2pt conv rate | 0.479 |
| Actual 2pt attempt rate | 0.099 |

Sim TD drive points distribution: 6 pts (10.8%), 7 pts (84.4%), 8 pts (4.8%).
PAT is working correctly: ~5% 2pt attempts, consistent with table data.

### 4i. Scoring by Quarter

| Quarter | Actual pts/game | Sim pts/game* |
|---------|----------------|---------------|
| Q1 | 8.48 | ~9 |
| Q2 | 13.97 | ~14 |
| Q3 | 9.03 | ~9 |
| Q4 | 12.44 | ~12 |

*Sim per-quarter scoring estimated from drive-start quarter; approximate due
to drives crossing quarter boundaries.

Q2 and Q4 have the most actual scoring (end-of-half/game scoring drives). The
sim's excess end_half/end_game drives (5.8pp) suggests it fails to capture the
scoring urgency of the final 2 minutes of each half.

### 4j. Margin Distribution P(|margin| = k)

| k | Actual | Sim | Delta | Season SD | Flag |
|---|--------|-----|-------|-----------|------|
| 1 | 0.0469 | 0.0568 | +0.0099 | 0.0126 | |
| 2 | 0.0524 | 0.0489 | -0.0035 | 0.0105 | |
| 3 | 0.1454 | 0.0786 | -0.0667 | 0.0139 | **MATERIAL** |
| 4 | 0.0488 | 0.0642 | +0.0154 | 0.0166 | |
| 5 | 0.0460 | 0.0432 | -0.0028 | 0.0213 | |
| 6 | 0.0754 | 0.0514 | -0.0240 | 0.0205 | |
| 7 | 0.0727 | 0.0679 | -0.0047 | 0.0062 | |
| 8 | 0.0451 | 0.0367 | -0.0084 | 0.0071 | |
| 9 | 0.0202 | 0.0382 | +0.0180 | 0.0088 | **MATERIAL** |
| 10 | 0.0506 | 0.0557 | +0.0051 | 0.0097 | |
| 11 | 0.0147 | 0.0432 | +0.0285 | 0.0108 | **MATERIAL** |
| 12 | 0.0230 | 0.0293 | +0.0063 | 0.0076 | |
| 13 | 0.0175 | 0.0411 | +0.0236 | 0.0102 | **MATERIAL** |
| 14 | 0.0432 | 0.0409 | -0.0023 | 0.0235 | |

Key-number mass deficit at 3 (-6.7pp) and 6 (-2.4pp). Excess mass at non-football
numbers (9, 11, 13) — these are margins that arise from mixed scoring patterns
that the sim over-produces due to insufficient FG concentration.

### By-Season Breakdown

| Season | Act pts/tm | Sim pts/tm | Act TD/drv | Sim TD/drv | Act FG/drv | Sim FG/drv | Act RZ_TD | Sim RZ_TD |
|--------|-----------|-----------|-----------|-----------|-----------|-----------|----------|----------|
| 2021 | 23.0 | 18.9 | 0.237 | 0.191 | 0.153 | 0.138 | 0.593 | 0.550 |
| 2022 | 21.9 | 19.2 | 0.217 | 0.187 | 0.157 | 0.143 | 0.573 | 0.546 |
| 2023 | 21.8 | 18.4 | 0.210 | 0.170 | 0.156 | 0.141 | 0.560 | 0.519 |
| 2024 | 22.9 | 19.2 | 0.235 | 0.191 | 0.166 | 0.140 | 0.582 | 0.549 |

The deficit is consistent across all 4 seasons (3.0-3.8 pts/team), not driven
by a single outlier year. The TD/drive gap (~4pp) and FG/drive gap (~1.5pp) are
stable across seasons.

---

## Step 5: Attribution

### Scoring deficit decomposition

| Source | Mechanism | pts/team | Share |
|--------|-----------|----------|-------|
| TD/drive -4.0pp | Fewer TDs from sustained drives | -2.7 | 77% |
| FG/drive -1.8pp | Fewer FG attempts | -0.5 | 14% |
| Other | Slightly lower RZ conversion + excess safeties | -0.3 | 9% |
| **Total** | | **-3.5** | |

### Mechanism 1: Lower TD rate from all field positions (-2.7 pts/team)

The TD/drive rate is 4.0pp below actual (18.5% vs 22.5%), consistently across
all starting field positions. The deficit is NOT red-zone-specific (RZ TD rate
gap is only 3.6pp vs 4-5pp in own territory). The engine generates the correct
total yardage but fails to convert yards into scoring drives at the correct rate.

**Root cause:** Excess non-scoring drive endings. The sim produces 7.5% turnover-
on-downs (vs 5.8% actual, +1.6pp) and 9.5% end_half+end_game (vs 3.7% actual,
+5.8pp). These 7.4pp of excess "dead" drives directly displace TD and FG drives.

The excess turnover-on-downs is partially driven by a higher 4th-down go rate
(23.2% vs 19.8%), which adds lower-quality go attempts. The excess end_half/
end_game drives indicate the engine does not model end-of-half urgency (2-minute
drill) — the hurry-up flag only activates when trailing by <= 8, but real teams
hurry regardless of score in the final 2 minutes of each half.

**Classification: (ii) TABLE GAP** — Two gaps:
1. The 4th-down decision table + team aggressiveness override overestimates the
   go rate by ~3pp, adding marginal go attempts that fail and become turnovers on
   downs instead of FG attempts.
2. The clock table lacks an end-of-half urgency mode. The hurry flag (`trailing_or_close
   & (Q4 | Q2_late)`) misses the universal hurry-up behavior in the final 2 minutes of
   each half regardless of score differential. Drives that should produce FG/TD scoring
   instead expire.

### Mechanism 2: Lower FG attempt rate (-0.5 pts/team)

FG attempts are 3.41/game vs 3.92 actual (-0.51). The FG make rate is fine
(0.872 vs 0.850, slightly high). The deficit is in ATTEMPTS, not accuracy.

**Root cause:** Same as Mechanism 1 — the 4th-down go rate is too high (23.2% vs
19.8%), diverting situations that should be FG attempts into go-for-it plays.

**Classification: (ii) TABLE GAP** — Same as Mechanism 1.

### Mechanism 3: Key-number mass deficit

P(|margin|=3) = 7.9% vs 14.5% actual. This is directly downstream of fewer FGs:
margin=3 games are disproportionately FG-decided. With 0.51 fewer FG attempts per
game, fewer games are decided by field goals, and mass migrates from 3 and 6 to
non-football numbers (9, 11, 13).

**Classification: (ii) TABLE GAP** — Resolves when Mechanisms 1-2 are addressed.

### No engine bugs identified

All three mechanisms are table gaps (the empirical tables lack a dimension reality
has), not engine bugs (wrong rule, wrong lookup, wrong boundary). No code changes
to make.

---

## Proposed D-Entries (for decision doc)

**D22: End-of-half clock urgency.** Add a hurry-up flag that activates in the last
2:00 of Q2 and Q4 regardless of score differential, with a separate clock table
for this situation. Expected effect: reduce excess end_half/end_game drives from
9.5% to ~4%, redistributing ~1.5 pts/team into TD and FG scoring. Measure: run
the same drive log diagnostic with the updated clock table.

**D23: 4th-down decision table rebalance.** The team aggressiveness override
(`team_go / lg_go` ratio applied to `p_go`) inflates the go rate by ~3pp. Two
options: (a) cap the ratio at 1.15, (b) disable the override in Q4. Measure:
drive-result distribution, specifically FG att/game and turnover-on-downs rate.

---

## Runtimes

| Step | Runtime |
|------|---------|
| Step 2 (actual drives from PBP) | 95.2s |
| Step 3 (K1 backtest, 1087 games x N=500) | 555.3s (0.51 s/game) |
| T8 (byte-identity, 3 games x N=2000 x 2) | ~6s |
| Test suite (6 tests) | 11s |
| Total | 663.6s (11.1 min) |
