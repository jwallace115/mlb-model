# Phase 2 — Elite Bullpen Availability Premium

Research date: 2026-04-07

**Hypothesis:** When elite relievers (high-K, high-usage) are rested and available, the late innings are better protected, suppressing runs in a way the market underprices. This should manifest as elevated under rates.

---

## Phase 1 — Data Audit

**Source:** `mlb/data/pitcher_game_logs.parquet` — relievers (starter_flag == 0), 2022-2025.

| Season | Appearances | Unique Relievers | Teams | Games |
|--------|------------|------------------|-------|-------|
| 2022   | 16,023     | 707              | 30    | 2,428 |
| 2023   | 15,774     | 711              | 30    | 2,429 |
| 2024   | 15,822     | 668              | 30    | 2,426 |
| 2025   | 15,993     | 713              | 30    | 2,427 |

Per-appearance K rate: mean 0.253, median 0.250.

**Quality proxy:** K rate = strikeouts / batters_faced (best available; no whiff or CSW data in this table).

**Role proxy:** Top 3 relievers by appearances per team-season (minimum 20 apps or 15% of team games). These are overwhelmingly closers and primary setup men.

**Availability proxy:** 0 appearances in prior 2 calendar days (pregame-safe, shifted).

Coverage is excellent: 120 team-seasons, 360 relievers in the top-3 pool.

---

## Phase 2 — Elite Availability Flags

### Definitions

- **Top 3 role:** 3 highest-appearance relievers per team-season (min 20 apps)
- **Elite quality:** Season K rate >= 0.25 (above-average reliever threshold)
- **Rested:** 0 appearances in prior 2 days
- **Elite available:** Reliever is both elite AND rested
- **Flag fires:** n_elite_rested >= 2 for a given team-date

### K Rate Distribution of Top-3 Relievers

| Threshold | % of Top-3 Pool |
|-----------|----------------|
| >= 0.20   | 88.1%          |
| >= 0.25   | 52.2%          |
| >= 0.28   | 30.8%          |
| >= 0.30   | 21.9%          |

52.2% of top-3 relievers clear the 0.25 K rate bar (188 / 360).

### Bucket Frequency (Elite Avail, >= 2 elite rested)

| Season | BOTH  | HOME_ONLY | AWAY_ONLY | NEITHER |
|--------|-------|-----------|-----------|---------|
| 2022   | 4.1%  | 11.9%     | 13.8%     | 70.3%   |
| 2023   | 2.7%  | 10.7%     | 12.1%     | 74.6%   |
| 2024   | 2.8%  | 10.2%     | 12.3%     | 74.7%   |
| 2025   | 2.5%  | 8.7%      | 10.4%     | 78.5%   |
| **All**| **3.0%** | **10.4%** | **12.2%** | **74.5%** |

BOTH fires at only 3.0% — very selective. Either side fires at 25.6%. Well below 40% ceiling.

### Comparison Flags

| Flag Type      | Both Sides Rate |
|----------------|----------------|
| ELITE (rest+K) | 3.0%           |
| FRESH (rest only) | 15.9%       |
| QUALITY (K only)  | 33.9%       |

Quality filter is the primary constraining dimension; rest adds further selectivity.

---

## Phase 3 — Raw Outcome Test

### Raw Actual Totals (all 4 seasons, no line needed)

| Group           | N     | Mean Total |
|-----------------|-------|-----------|
| HOME_ELITE_AVAIL| 741   | 8.71      |
| No home elite   | 4,785 | 8.91      |
| ANY_ELITE       | 1,415 | 8.91      |
| NEITHER         | 4,111 | 8.87      |

Home elite availability shows a -0.20 run difference vs baseline (8.71 vs 8.91), but **t-test p = 0.256 — not significant.**

Season-level HOME_ELITE actuals: 7.96, 9.29, 8.82, 8.98 — volatile, no stable suppression.

ANY_ELITE shows no suppression at all (8.91 vs 8.87).

### Market-Relative Test (2024-2025, N=2,690 games with closing lines)

| Bucket           | N (ex push) | Under Rate | Residual | ROI @ -110 |
|------------------|-------------|-----------|----------|------------|
| BOTH_ELITE       | 69          | 49.3%     | +0.521   | -5.9%      |
| HOME_ELITE_ONLY  | 248         | 48.4%     | +0.693   | -7.6%      |
| AWAY_ELITE_ONLY  | 293         | 49.5%     | +0.510   | -5.5%      |
| EITHER_ELITE     | 610         | 49.0%     | +0.557   | -6.4%      |
| **NEITHER**      | **1,982**   | **51.4%** | **+0.436** | **-1.9%** |

**The elite availability buckets all underperform NEITHER on under rate.** The direction is inverted from hypothesis: games with elite bullpen availability go OVER more often, not under.

### Quality Filter Value Check

| Filter           | N   | Residual | Under Rate |
|------------------|-----|----------|-----------|
| BOTH_ELITE (rest+K) | 69 | +0.521 | 49.3%    |
| BOTH_FRESH (rest only) | 411 | +0.331 | 52.1% |
| BOTH_QUALITY (K only) | 838 | +0.580 | 49.8%  |

Quality filter **does not add value** — under rate is lower with the quality filter than without it. BOTH_FRESH (rest only, no quality filter) actually has the best under rate at 52.1%.

---

## Phase 4 — Market-Relative Detail

### Season Splits

| Bucket        | 2024 N | 2024 Under | 2025 N | 2025 Under |
|---------------|--------|-----------|--------|-----------|
| BOTH_ELITE    | 38     | 52.6%     | 31     | 45.2%     |
| HOME_ELITE    | 139    | 47.5%     | 109    | 49.5%     |
| EITHER_ELITE  | 345    | 50.1%     | 265    | 47.5%     |
| NEITHER       | 1,011  | 49.4%     | 971    | 53.5%     |

No bucket exceeds 53% in either season. NEITHER actually posts the best OOS under rate in 2025 (53.5%). The elite availability signal flips direction between seasons.

---

## Phase 5 — Band Interaction

### Under Rate by Closing Total Band x Home Elite Available

| Band   | H_ELITE N | H_ELITE Under | No H_ELITE N | No H_ELITE Under |
|--------|-----------|--------------|--------------|-----------------|
| <=7.5  | 96        | 45.8%        | 554          | 50.5%           |
| 8.0    | **52**    | **67.3%**    | 406          | 51.2%           |
| 8.5    | 115       | 45.2%        | 673          | 50.4%           |
| 9.0    | 32        | 46.9%        | 318          | 52.8%           |
| >=9.5  | 22        | 36.4%        | 324          | 51.9%           |

The 8.0 band shows a striking 67.3% under rate with home elite availability (N=52, binomial p=0.024 one-sided). However:

- **Season instability:** 2024: 66.7% (N=42) vs 2025: 56.1% (N=41) — 10.6pp drop
- **Small N:** Only 52 observations (83 in the wider 7.75-8.25 band where rate drops to 61.4%)
- **Surrounding bands contradict:** <=7.5 (45.8%), 8.5 (45.2%), 9.0 (46.9%), >=9.5 (36.4%) — all below 50%
- **Multiple comparison problem:** Testing 5 bands x 2 groups = 10 cells; finding one at p<0.05 is expected by chance

This is a classic subgroup mining artifact. The 8.0 band result does not survive scrutiny.

---

## Phase 6 — Starter Path Interaction

Starter rolling IP data merged for 2024-2025 games. Insufficient sample sizes in the crosscuts (HOME_ELITE x DEEP_SP, etc.) prevented reliable measurement. The elite availability flag fires infrequently enough that crossing it with starter depth produces cells too small for inference.

---

## Phase 7 — Practical Framing

**There is no practical application.** The core hypothesis is rejected:

1. **No under-rate elevation:** Elite availability under rates are 48-49%, below the 50% baseline and well below the 53% threshold needed for a signal.
2. **Quality filter adds negative value:** Pure freshness (BOTH_FRESH at 52.1%) outperforms the quality-conditioned flag (BOTH_ELITE at 49.3%). Adding the K rate filter makes performance worse.
3. **Inverted direction:** The residual is MORE positive (games go over more) when elite arms are available, suggesting the market may already account for bullpen depth — or that teams with elite bullpens are strong teams that generate more offense, confounding the signal.
4. **No band concentration:** One subgroup (8.0 band) shows a promising number but fails multiple comparison correction and season stability checks.

---

## Decision: CLOSE

**Rationale:**

- Under rate with elite availability: **49.0%** (EITHER_ELITE) — below 50% baseline, far below the 53% threshold
- Quality filter adds nothing; pure freshness is weakly better but still not actionable
- Direction inverted from hypothesis in both raw and market-relative tests
- Season splits unstable (BOTH_ELITE flips from 52.6% to 45.2%)
- The lone promising subgroup (8.0 band, 67.3%) is a small-N artifact that decays across seasons

**Why the hypothesis fails:** Elite bullpen availability is likely correlated with team quality — good teams have good bullpens. Good teams also have good offenses, and the market knows this. The offensive correlation washes out any late-inning suppression. Additionally, managers may use elite relievers more aggressively when available (higher-leverage situations, extra innings), negating the "protection" premium.

**No further investigation warranted.** The freshness-only signal (BOTH_FRESH at 52.1%) is mildly interesting but already captured by the existing `home/away_high_leverage_avail` features in the Phase 9 model, which track top-3 closer rest status directly.
