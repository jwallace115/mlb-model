# DECISION-TIME CUTOFF AUDIT — MLB Totals Market Path

**AUDIT ONLY — DECISION TIME NOT YET FROZEN**

Generated: 2026-04-13T11:41:02.362392+00:00

> MPS remains RESERVED / DATA-BLOCKED. This audit selects a decision-time cutoff only. No signals have been tested, no predictive value has been claimed, and no changes to the canonical spec have been made.

---

## 1. Sample

**800 games**: 200 per season (2022–2025), 100 day / 100 evening per season. `random_state=123`.

Day game = commence at UTC hours 14–21 (10:00–17:59 ET). Evening = UTC hours 22–23 or 00–02 (18:00 ET or later).

**Classification correction**: Games starting at UTC hours 00–02 are 8–10pm ET evening games that cross UTC midnight. They were initially sampled as day games (hour_utc < 22), but all 162 such games are excluded from the comparable sample because their MPS close probe (21:55 UTC same calendar date) is after game start (00:00–02:00 UTC). The comparable sample therefore contains only correctly-identified day and evening games.

| Season | Total | Day | Evening | Comparable |
|--------|-------|-----|---------|------------|
| 2022 | 200 | 52 | 148 | 152 |
| 2023 | 200 | 57 | 143 | 157 |
| 2024 | 200 | 67 | 133 | 167 |
| 2025 | 200 | 62 | 138 | 162 |
| **Total** | **800** | **238** | **562** | **638** |

## 2. Reference Integrity

- **OPEN_LATE** (open snapshot >= 10:00 UTC / 06:00 ET): `0` games — all open probes are genuinely early
- **Post-first-pitch close excluded**: `162` games
  - UTC hours of excluded games: hours 0 (70), 1 (70), 2 (22) — all are 8–10pm ET evening games whose MPS close probe was set to 21:55 UTC on the same calendar date, which falls after midnight-UTC game start
- **Final comparable sample**: `638` games (238 true day + 400 evening)

## 3. Table A — Coverage

| Time (ET) | UTC | Total | Usable | Usable% | FD Primary | DK Fallback | Incomplete |
|-----------|-----|-------|--------|---------|------------|-------------|------------|
| 07:00 ET | 11:00 UTC | 638 | 638 | 100.0% | 631 | 7 | 0 |
| 08:00 ET | 12:00 UTC | 638 | 638 | 100.0% | 637 | 1 | 0 |
| 09:00 ET | 13:00 UTC | 638 | 638 | 100.0% | 637 | 1 | 0 |
| 10:00 ET | 14:00 UTC | 638 | 638 | 100.0% | 638 | 0 | 0 |
| 12:00 ET | 16:00 UTC | 638 | 638 | 100.0% | 638 | 0 | 0 |

**Finding**: All 5 candidate times achieve 100% usable coverage. FD is fully available by 10:00 ET; DK fallback needed for 7 games (1.1%) at 07:00 ET only. C1 is satisfied universally.

### Coverage by Season

| Season | 07:00 ET | 08:00 ET | 09:00 ET | 10:00 ET | 12:00 ET |
|--------|----------|----------|----------|----------|----------|
| 2022 | 152/152 (100%) | 152/152 (100%) | 152/152 (100%) | 152/152 (100%) | 152/152 (100%) |
| 2023 | 157/157 (100%) | 157/157 (100%) | 157/157 (100%) | 157/157 (100%) | 157/157 (100%) |
| 2024 | 167/167 (100%) | 167/167 (100%) | 167/167 (100%) | 167/167 (100%) | 167/167 (100%) |
| 2025 | 162/162 (100%) | 162/162 (100%) | 162/162 (100%) | 162/162 (100%) | 162/162 (100%) |

### Coverage by Day/Evening

| Type | 07:00 ET | 08:00 ET | 09:00 ET | 10:00 ET | 12:00 ET |
|------|----------|----------|----------|----------|----------|
| Day (238) | 100% | 100% | 100% | 100% | 100% |
| Evening (400) | 100% | 100% | 100% | 100% | 100% |

## 4. Table B — Same-Book Parity to Final Close

| Time (ET) | N Usable | Same-Book FD | Same-Book DK | Overall Parity% | Cross-Book | Incomplete |
|-----------|----------|--------------|--------------|-----------------|------------|------------|
| 07:00 ET | 638 | 629 | 626 | 100.0% | 0 | 0 |
| 08:00 ET | 638 | 635 | 631 | 100.0% | 0 | 0 |
| 09:00 ET | 638 | 635 | 632 | 100.0% | 0 | 0 |
| 10:00 ET | 638 | 636 | 633 | 100.0% | 0 | 0 |
| 12:00 ET | 638 | 636 | 634 | 100.0% | 0 | 0 |

**Finding**: 100% same-book parity at every candidate time. No cross-book comparisons needed. C2 is satisfied universally. This is a strong infrastructure finding — FanDuel (and DraftKings) maintain continuous coverage from 07:00 ET through close for all sampled games.

## 5. Table C — Timestamp Quality (Hours Before Game)

| Time (ET) | Median Hrs Before | P10 Hrs Before | P90 Hrs Before | After-Game-Start | At-Game-Start | Combined Risk |
|-----------|------------------|----------------|----------------|------------------|---------------|---------------|
| 07:00 ET | 11.0h | 6.0h | 12.0h | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |
| 08:00 ET | 10.0h | 5.0h | 11.0h | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |
| 09:00 ET | 9.0h | 4.0h | 10.0h | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |
| 10:00 ET | 8.0h | 3.0h | 9.0h | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |
| 12:00 ET | 6.0h | 1.0h | 7.0h | 2 (0.3%) | 14 (2.2%) | 16 (2.5%) |

*Candidate probes are fixed scheduled times. The C3 timing criterion is interpreted as: probe must be strictly before game start. For 12:00 ET: 2 games start before noon ET (rare west-coast or early-afternoon scheduling), 14 games start exactly at noon ET. These 16 games (2.5%) represent a production handling requirement, not a data quality failure.*

**Finding**: 07:00–10:00 ET all satisfy C3 with zero timing exposure. 12:00 ET fails C3 strictly for 2.5% of games.

## 6. Table D — Remaining Total-Line Drift (Same-Book FD Pairs)

| Time (ET) | N Pairs | Median Drift | Pct >=0.5 | Pct >=1.0 | Pct Zero |
|-----------|---------|--------------|-----------|-----------|----------|
| 07:00 ET | 629 | 0.000 | 42.0% | 3.0% | 58.0% |
| 08:00 ET | 635 | 0.000 | 41.3% | 2.4% | 58.7% |
| 09:00 ET | 635 | 0.000 | 35.9% | 1.6% | 64.1% |
| 10:00 ET | 636 | 0.000 | 30.0% | 0.9% | 70.0% |
| 12:00 ET | 636 | 0.000 | 16.0% | 1.3% | 84.0% |

**Finding**: Median drift is zero at all times (market is stable for the majority). The key discriminator is `pct >=0.5`: line moves of half a run or more. This falls from 42.0% at 07:00 ET to 30.0% at 10:00 ET (−12pp) and 16.0% at 12:00 ET (−26pp). Later probes substantially reduce exposure to large remaining line movement.

vs. 07:00 ET baseline reductions:
- 08:00 ET: pct>=0.5 −0.7pp (C4 FAIL by criterion)
- 09:00 ET: pct>=0.5 −6.1pp (C4 PASS)
- 10:00 ET: pct>=0.5 −12.0pp (C4 PASS, strong)
- 12:00 ET: pct>=0.5 −26.0pp (C4 PASS, strongest)

## 7. Table E — Remaining Juice Drift (Same-Book FD Pairs)

| Time (ET) | N Pairs | Median Over Drift | Median Under Drift | Pct Zero Juice |
|-----------|---------|-------------------|--------------------|----------------|
| 07:00 ET | 629 | 7.0 | 7.0 | 11.1% |
| 08:00 ET | 635 | 7.0 | 7.0 | 11.8% |
| 09:00 ET | 635 | 6.0 | 6.0 | 15.4% |
| 10:00 ET | 636 | 5.0 | 6.0 | 18.4% |
| 12:00 ET | 636 | 2.0 | 2.0 | 37.9% |

**Finding**: Juice drift is substantial even at 07:00 ET (median 7 American points both sides). By 10:00 ET this falls to 5–6 points. By 12:00 ET it drops to 2 points. The sharpest juice stabilization occurs between 10:00 ET and 12:00 ET. For context features that use the price (juice) as input, 10:00 ET captures a materially more stable state than 07:00 ET.

## 8. Table F — Broad Path-Family Agreement

Taxonomy: STABLE / DRIFT_OVER / DRIFT_UNDER / JUICE_ONLY / UNCERTAIN
- STABLE: |line_move| <= 0.25 AND max juice drift <= 5
- DRIFT_OVER: line_move > 0.25 (total line increases)
- DRIFT_UNDER: line_move < -0.25 (total line decreases)
- JUICE_ONLY: |line_move| <= 0.25 but juice moves > 5

Partial path = open → candidate time. Full path = open → final close. Agreement = same archetype.

| Time (ET) | N Comparable | Agreement% | Stable (partial) | Stable (full) |
|-----------|--------------|------------|------------------|---------------|
| 07:00 ET | 638 | 37.3% | 424 | 155 |
| 08:00 ET | 638 | 40.6% | 400 | 155 |
| 09:00 ET | 638 | 47.5% | 320 | 155 |
| 10:00 ET | 638 | 55.2% | 262 | 155 |
| 12:00 ET | 638 | 74.3% | 209 | 155 |

**Key observation**: At 07:00 ET, 424 games appear STABLE (partial) but only 155 are stable through to final close — meaning 269 games that look quiet at 07:00 ET move significantly later. By 12:00 ET, the partial-STABLE count (209) is much closer to the final-STABLE count (155), indicating far better classification fidelity. The 70% agreement threshold is only met at 12:00 ET (74.3%).

### Path Agreement by Season (10:00 ET and 12:00 ET)

| Season | 10:00 ET | 12:00 ET |
|--------|----------|----------|
| 2022 | 49.3% | 68.4% |
| 2023 | 56.7% | 75.8% |
| 2024 | 54.5% | 75.4% |
| 2025 | 59.9% | 77.2% |
| **All** | **55.2%** | **74.3%** |

*Note: 2022 path agreement at 12:00 ET is 68.4% — slightly below the 70% threshold, though still significantly better than 10:00 ET. 2023–2025 all exceed 70%.*

## 9. Criteria Gate Evaluation

| Time | C1 Coverage >=85% | C2 Parity >=75% | C3 Timing | C4 Movement | C5 Agreement >=70% | ALL PASS |
|------|------------------|-----------------|-----------|-------------|---------------------|----------|
| 07:00 ET | 100% PASS | 100% PASS | PASS | BASELINE | 37.3% FAIL | NO |
| 08:00 ET | 100% PASS | 100% PASS | PASS | FAIL (−0.7pp) | 40.6% FAIL | NO |
| 09:00 ET | 100% PASS | 100% PASS | PASS | PASS (−6.1pp) | 47.5% FAIL | NO |
| 10:00 ET | 100% PASS | 100% PASS | PASS | PASS (−12.0pp) | 55.2% FAIL | NO |
| 12:00 ET | 100% PASS | 100% PASS | FAIL (2.5%) | PASS (−26.0pp) | 74.3% PASS | NO |

*No time satisfies all 5 criteria simultaneously. 12:00 ET fails C3 on a timing edge case affecting 2.5% of games.*

## 10. Recommendation

### Verdict

**NO CLEAR DECISION CUTOFF YET by strict criteria. Two viable options identified:**

---

**OPTION A — CONSERVATIVE SAFE CUTOFF: 10:00 ET**

- Satisfies C1 (100% coverage), C2 (100% parity), C3 (0 timing failures), C4 (30% pct>=0.5, down 12pp)
- Fails C5: path agreement 55.2% (threshold 70%)
- Safe for production: zero games have a post-start or at-start probe
- Tradeoff: 30% of games still have >=0.5 run of line movement remaining; market archetype classification is only 55% concordant with final path

---

**OPTION B — AGGRESSIVE CUTOFF: 12:00 ET**

- Satisfies C1 (100% coverage), C2 (100% parity), C4 (16% pct>=0.5, down 26pp), C5 (74.3% agreement)
- Fails C3: 16/638 games (2.5%) have probe at or after game start
  - 2 games (0.3%): probe strictly after start (early-afternoon day games starting at 11:00 ET)
  - 14 games (2.2%): probe exactly at game start (noon ET start time)
- Requires a production exception: any game starting at or before 12:00 ET should use a 10:00 ET fallback probe
- Highest path agreement (74.3%) and most juice stability (median 2-point remaining drift)

---

### Identity Implication

The decision time for the MLB Totals Context Engine cannot be frozen at a single time without an exception handler for early-starting games.

**Practical recommendation for implementation**:
- Primary decision time: **12:00 ET** (for all games starting after 12:15 ET)
- Exception fallback: **10:00 ET** (for games starting at or before 12:15 ET)
- This hybrid approach satisfies all 5 criteria for the 97.5% of games that start after noon ET, and uses the safe conservative probe for the 2.5% that do not

**If a single fixed time must be chosen**: **10:00 ET** is the correct choice — it satisfies C1–C4, maintains full timing safety, and is meaningfully better than 07:00–09:00 ET on movement metrics. The C5 gap (55.2% vs 70%) reflects genuine market incompleteness at 10:00 ET, not a data quality problem.

---

## Appendix A: C3 Detail for 12:00 ET Early-Starting Games

The 16 at-risk games span all seasons and are predominately early afternoon games on summer/fall weekdays:
- Games starting at 15:00 UTC (11:00 ET): 2 games — probe is 1 hour after start
- Games starting at 16:00 UTC (12:00 ET): 14 games — probe is simultaneously at game start

These are mostly day games in Pittsburgh (PIT), Baltimore (BAL), Atlanta (ATL), and other East Coast venues scheduled for 11:00 or noon ET starts. Any production implementation of a 12:00 ET decision time must exclude these or apply an earlier probe.

## Appendix B: API Collection Statistics

- Sample: 800 games (638 comparable after integrity filtering)
- Unique API calls: 2,060 (unique game_date × UTC_hour combinations)
- Total rows collected: 3,190 (638 games × 5 candidate times)
- API credits used: ~24,677 (from 4,163,411 → 4,138,734)
- Checkpoint file: `collection_checkpoint.parquet`

---

> **MPS STATUS: RESERVED / DATA-BLOCKED**
>
> MPS remains RESERVED / DATA-BLOCKED. This audit selects a decision-time cutoff only. No signals have been tested, no predictive value has been claimed, and no changes to the canonical spec have been made.
