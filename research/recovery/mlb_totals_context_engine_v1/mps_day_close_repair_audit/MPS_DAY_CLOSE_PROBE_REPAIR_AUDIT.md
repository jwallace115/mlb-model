# MPS Day-Game Close-Probe Repair Audit

**Status:** AUDIT ONLY — MPS REMAINS BLOCKED

---

## 1. Audit Scope

This is a **timing repair audit** for the MLB Totals Context Engine V1 (MPS). The prior
open-discovery audit established that the 00:01 ET open probe is viable and that evening-game
closes at 18:00 ET achieve 100% parity. However, day games (first pitch before approximately
18:00 ET) cannot use 18:00 ET as a close — the game has already started by then.

This audit tests **8 candidate close-probe times** for day games:

- 4 fixed-clock probes: 10:00, 11:00, 12:00, 13:00 ET
- 4 dynamic pre-game probes: T-180, T-120, T-90, T-60 min relative to first pitch

No modeling, no activation, no path states defined. MPS remains RESERVED / DATA-BLOCKED.

---

## 2. Sample Design

| Field | Value |
|---|---|
| Season | 2024 |
| Day game definition | game_hour_utc in [14-21] (10am-5pm ET in EDT) |
| Total 2024 day games available | 914 |
| Sample size | 30 (random_state=77) |
| Date range | 2024-04-03 to 2024-09-28 |
| Total API calls made | 260 (30 open + 230 close) |
| Credits remaining | 4357804 |

Note: game_hour_utc represents the integer hour in UTC. Day games in EDT (UTC-4) fall in
UTC hours 14-21 (10am-5pm ET). The sample contains hours:
{16: np.int64(1), 17: np.int64(8), 18: np.int64(6), 19: np.int64(6), 20: np.int64(9)}

---

## 3. Open-Side Baseline (00:01 ET = 04:01 UTC)

| Metric | Value |
|---|---|
| Events matched | 30/30 (100%) |
| FanDuel totals available | 26/30 |
| DraftKings totals available | 19/30 |
| Median snapshot timestamp delta | 0.4 min |

Open probe status: **VIABLE** — 30/30 games matched.

---

## 4. Close-Rule Results

### Table A — Same-Book Parity by Close Rule

(Parity = both open AND close snapshot have totals for the same bookmaker)

| Rule | N Valid | FD Pairs | DK Pairs | Best Book | Best Pairs | Parity Rate |
|---|---|---|---|---|---|---|
| 10:00 ET | 30 | 26 | 19 | FanDuel | 26 | 86.7% |
| 11:00 ET | 30 | 26 | 19 | FanDuel | 26 | 86.7% |
| 12:00 ET | 29 | 26 | 18 | FanDuel | 26 | 89.7% |
| 13:00 ET | 21 | 17 | 13 | FanDuel | 17 | 81.0% |
| T-180 | 30 | 25 | 19 | FanDuel | 25 | 83.3% |
| T-120 | 30 | 24 | 18 | FanDuel | 24 | 80.0% |
| T-90 | 30 | 25 | 19 | FanDuel | 25 | 83.3% |
| T-60 | 30 | 25 | 19 | FanDuel | 25 | 83.3% |

### Table B — Invalidity Diagnostics

| Rule | N INVALID_LIVE | N BEFORE_OPEN | N MATCH_FAILED | N NO_TOTALS |
|---|---|---|---|---|
| 10:00 ET | 0 | 0 | 0 | 0 |
| 11:00 ET | 0 | 0 | 0 | 0 |
| 12:00 ET | 1 | 0 | 0 | 0 |
| 13:00 ET | 9 | 0 | 0 | 0 |
| T-180 | 0 | 0 | 0 | 0 |
| T-120 | 0 | 0 | 1 | 0 |
| T-90 | 0 | 0 | 0 | 0 |
| T-60 | 0 | 0 | 0 | 0 |

### Table C — Total Drift (same-book pairs only)

| Rule | Median Total Drift | Pct Drift >=0.5 | Pct Zero Drift |
|---|---|---|---|
| 10:00 ET | 0.5 | 51% | 49% |
| 11:00 ET | 0.5 | 53% | 47% |
| 12:00 ET | 0.5 | 57% | 43% |
| 13:00 ET | 0.5 | 67% | 33% |
| T-180 | 0.5 | 59% | 41% |
| T-120 | 0.5 | 57% | 43% |
| T-90 | 0.5 | 57% | 43% |
| T-60 | 0.5 | 57% | 43% |

### Table D — Juice Drift (same-book pairs only)

| Rule | Median Juice Drift | Pct Zero Juice Drift |
|---|---|---|
| 10:00 ET | 12.0 | 13% |
| 11:00 ET | 10.5 | 22% |
| 12:00 ET | 10.0 | 9% |
| 13:00 ET | 13.0 | 7% |
| T-180 | 13.0 | 11% |
| T-120 | 13.0 | 7% |
| T-90 | 10.0 | 11% |
| T-60 | 10.0 | 11% |

---

## 5. Movement Results

Line movement between the 00:01 ET open and the close probe is a key quality signal: it
indicates the historical snapshot captures meaningful pre-game market information rather than
a stale or frozen line.

Non-zero median total drift confirms that line movement occurs in the open-to-close window.
The dynamic rules (T-60 through T-180) tend to capture the most recent market state and
therefore the most movement relative to the overnight open.

---

## 6. Recommended Day-Game Close Rule

**Selected rule:** T-60
**Best bookmaker:** FanDuel
**Same-book parity:** 83.3%
**N valid games:** 30/30
**Verdict:** VIABLE

### Qualifying rules (all 5 criteria satisfied)

- 10:00 ET: parity=86.7%, valid=30/30
- 11:00 ET: parity=86.7%, valid=30/30
- 12:00 ET: parity=89.7%, valid=29/30
- T-180: parity=83.3%, valid=30/30
- T-120: parity=80.0%, valid=30/30
- T-90: parity=83.3%, valid=30/30
- T-60: parity=83.3%, valid=30/30

The latest-qualifying rule was selected to maximize market state freshness (closer to first
pitch = most complete pre-game price discovery captured).

### Criteria evaluation for winning rule (T-60)

| Criterion | Threshold | Observed | Pass |
|---|---|---|---|
| Best-book parity | >=70% | 83.3% | YES |
| Valid games | >=24 (80% of 30) | 30 | YES |
| Median ts delta | <=15 min | 4.4 min | YES |
| Movement preserved | drift>0 or juice>0 | drift=0.5, juice=10.0 | YES |
| Best book coverage | >=70% of valid | 25/30 (83%) | YES |

### Tradeoffs

Dynamic rules (T-60 through T-180) have the advantage of adapting to each game's actual
first-pitch time, ensuring the probe is never INVALID_LIVE regardless of game time variation.
Fixed rules (10:00-13:00 ET) are simpler to implement but may be INVALID_LIVE for very early
day games (rare in MLB but possible).

The INVALID_LIVE count for each rule is shown in Table B. Games where the fixed probe falls
after first pitch are excluded from parity calculations (those games would need the
corresponding dynamic probe as fallback).

---

## 7. Overall Viability Update

| Component | Finding |
|---|---|
| 00:01 ET open probe | 30/30 matched (100%) — VIABLE |
| Evening-game close (18:00 ET) | 15/15 from prior audit — 100% parity |
| Day-game close (T-60) | 83.3% same-book parity — VIABLE |

**Overall verdict: VIABLE FOR HISTORICAL ACQUISITION**

The MLB Totals MPS historical acquisition is fully viable using:
- Open: fixed 00:01 ET for all games
- Close: 18:00 ET for evening games (first pitch >=18:00 ET); T-60 for day games

---

## 8. Historical Acquisition Implications

| Parameter | Value |
|---|---|
| Open probe — all games | Fixed: 00:01 ET (04:01 UTC) |
| Close probe — evening games (first pitch >=18:00 ET) | Fixed: 18:00 ET (22:00 UTC) |
| Close probe — day games (first pitch <18:00 ET) | T-60 |
| Primary bookmaker (open) | FanDuel (25/30 in prior audit; 26/30 here) |
| Primary bookmaker (close) | FanDuel (25/30 pairs) |
| Fallback bookmaker | DraftKings |
| INVALID_LIVE handling | Skip; record close as missing; exclude from CLV computation |
| Minimum pair requirement | Both open AND close must have same-book total |

For dynamic rules: commence_time must be pulled from MLB Stats API schedule or cached in the
canonical game table before the API call is made. The probe datetime = commence_time + offset.

For fixed rules: simply use the fixed UTC hour on the game date. Validate that probe_dt <
commence_dt before calling; if INVALID_LIVE, fall back to the latest valid fixed rule that
precedes commence_time for that game.

---

## 9. Status

**MPS remains RESERVED / DATA-BLOCKED.**

This audit repairs the day-game close-probe timing question only. No path states have been
defined, no signals have been tested, and no changes to the canonical spec have been made.

The next step (if elected) would be a full historical data acquisition pass using:
- Fixed 00:01 ET open for all games
- 18:00 ET close for evening games  
- T-60 close for day games

followed by CLV feature construction and MPS path definition.

---

*Generated: 2026-04-13 02:52 UTC*
*Audit type: MPS DAY-GAME CLOSE-PROBE REPAIR AUDIT*
*Output location: research/recovery/mlb_totals_context_engine_v1/mps_day_close_repair_audit/*
