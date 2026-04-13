# DECISION-TIME CUTOFF AUDIT — MLB Totals Market Path

**AUDIT ONLY — DECISION TIME NOT YET FROZEN**

Generated: 2026-04-13T11:41:02.362392+00:00

> MPS remains RESERVED / DATA-BLOCKED. This audit selects a decision-time cutoff only. No signals have been tested, no predictive value has been claimed, and no changes to the canonical spec have been made.

---

## 1. Sample

**800 games**: 200 per season (2022–2025), 100 day / 100 evening per season. `random_state=123`.

Day game = commence at UTC hours 14–21 (10:00–17:59 ET). Evening = UTC hours 22–23 or 00–02 (18:00 ET or later).

**Classification correction**: Games starting at UTC hours 00–02 are 8–10pm ET evening games that cross UTC midnight. They were initially sampled as 'day' games (hour_utc < 22), but all 162 such games are excluded from the comparable sample because their MPS close probe (21:55 UTC same calendar date) is after game start (00:00–02:00 UTC). The comparable sample therefore contains only correctly-identified day and evening games.

| Season | Total | Day | Evening | Comparable |
|--------|-------|-----|---------|------------|
| 2022 | 200 | 52 | 148 | 152 |
| 2023 | 200 | 57 | 143 | 157 |
| 2024 | 200 | 67 | 133 | 167 |
| 2025 | 200 | 62 | 138 | 162 |
| **Total** | **800** | **238** | **562** | **638** |

## 2. Reference Integrity

- **OPEN_LATE** (open snapshot ≥ 10:00 UTC / 06:00 ET): `0` games
- **Post-first-pitch close** excluded: `162` games
- **Final comparable sample**: `638` games

All open snapshots are before 10:00 UTC, confirming genuinely early open probe capture.

## 3. Table A — Coverage

| Time (ET) | UTC | Total | Usable | Usable% | FD Primary | DK Fallback | Incomplete |
|-----------|-----|-------|--------|---------|------------|-------------|------------|
| 07:00 ET | 11:00 UTC | 638 | 638 | 100.0% | 631 | 7 | 0 |
| 08:00 ET | 12:00 UTC | 638 | 638 | 100.0% | 637 | 1 | 0 |
| 09:00 ET | 13:00 UTC | 638 | 638 | 100.0% | 637 | 1 | 0 |
| 10:00 ET | 14:00 UTC | 638 | 638 | 100.0% | 638 | 0 | 0 |
| 12:00 ET | 16:00 UTC | 638 | 638 | 100.0% | 638 | 0 | 0 |

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
| Day | 238/238 (100%) | 238/238 (100%) | 238/238 (100%) | 238/238 (100%) | 238/238 (100%) |
| Evening | 400/400 (100%) | 400/400 (100%) | 400/400 (100%) | 400/400 (100%) | 400/400 (100%) |

## 4. Table B — Same-Book Parity to Final Close

| Time (ET) | N Usable | Same-Book FD | Same-Book DK | Overall Parity% | Cross-Book | Incomplete |
|-----------|----------|--------------|--------------|-----------------|------------|------------|
| 07:00 ET | 638 | 629 | 626 | 100.0% | 0 | 0 |
| 08:00 ET | 638 | 635 | 631 | 100.0% | 0 | 0 |
| 09:00 ET | 638 | 635 | 632 | 100.0% | 0 | 0 |
| 10:00 ET | 638 | 636 | 633 | 100.0% | 0 | 0 |
| 12:00 ET | 638 | 636 | 634 | 100.0% | 0 | 0 |

## 5. Table C — Timestamp Quality (Hours Before Game)

| Time (ET) | Median Hrs Before | P10 Hrs Before | P90 Hrs Before | After-Game-Start |
|-----------|------------------|----------------|----------------|------------------|
| 07:00 ET | 11.0h | 6.0h | 12.0h | 0 |
| 08:00 ET | 10.0h | 5.0h | 11.0h | 0 |
| 09:00 ET | 9.0h | 4.0h | 10.0h | 0 |
| 10:00 ET | 8.0h | 3.0h | 9.0h | 0 |
| 12:00 ET | 6.0h | 1.0h | 7.0h | 2 |

*Note: Candidate probes are fixed scheduled times (07:00–12:00 ET). The 'delta' criterion is inherently met for historical API fixed probes; this table shows hours before game as the timing quality indicator.*

## 6. Table D — Remaining Total-Line Drift (Same-Book FD Pairs)

| Time (ET) | N Pairs | Median Drift | Pct ≥0.5 | Pct ≥1.0 | Pct Zero |
|-----------|---------|--------------|----------|----------|----------|
| 07:00 ET | 629 | 0.0 | 42.0% | 3.0% | 58.0% |
| 08:00 ET | 635 | 0.0 | 41.3% | 2.4% | 58.7% |
| 09:00 ET | 635 | 0.0 | 35.9% | 1.6% | 64.1% |
| 10:00 ET | 636 | 0.0 | 30.0% | 0.9% | 70.0% |
| 12:00 ET | 636 | 0.0 | 16.0% | 1.3% | 84.0% |

## 7. Table E — Remaining Juice Drift (Same-Book FD Pairs)

| Time (ET) | N Pairs | Median Over Drift | Median Under Drift | Pct Zero Juice |
|-----------|---------|-------------------|--------------------|----------------|
| 07:00 ET | 629 | 7.0 | 7.0 | 11.1% |
| 08:00 ET | 635 | 7.0 | 7.0 | 11.8% |
| 09:00 ET | 635 | 6.0 | 6.0 | 15.4% |
| 10:00 ET | 636 | 5.0 | 6.0 | 18.4% |
| 12:00 ET | 636 | 2.0 | 2.0 | 37.9% |

## 8. Table F — Broad Path-Family Agreement

Taxonomy applied: STABLE / DRIFT_OVER / DRIFT_UNDER / JUICE_ONLY / UNCERTAIN
- STABLE: |line_move| ≤ 0.25 and max juice drift ≤ 5
- DRIFT_OVER: line_move > 0.25
- DRIFT_UNDER: line_move < -0.25
- JUICE_ONLY: |line_move| ≤ 0.25 and max juice drift > 5

Partial path = open → candidate time. Full path = open → final close. Agreement = same archetype.

| Time (ET) | N Comparable | Agreement% |
|-----------|--------------|------------|
| 07:00 ET | 638 | 37.3% |
| 08:00 ET | 638 | 40.6% |
| 09:00 ET | 638 | 47.5% |
| 10:00 ET | 638 | 55.2% |
| 12:00 ET | 638 | 74.3% |

## 9. Criteria Gate Evaluation

| Time | C1 Coverage ≥85% | C2 Parity ≥75% | C3 Timing | C4 Movement | C5 Agreement ≥70% | ALL PASS |
|------|-----------------|----------------|-----------|-------------|-------------------|----------|
| 07:00 ET | 100.0% PASS | 100.0% PASS | PASS (0 after-game) | PASS (BASELINE) | 37.3% FAIL | NO |
| 08:00 ET | 100.0% PASS | 100.0% PASS | PASS (0 after-game) | FAIL (no reduction) | 40.6% FAIL | NO |
| 09:00 ET | 100.0% PASS | 100.0% PASS | PASS (0 after-game) | PASS (pct05_reduced_6.1≥5pp) | 47.5% FAIL | NO |
| 10:00 ET | 100.0% PASS | 100.0% PASS | PASS (0 after-game) | PASS (pct05_reduced_12.0≥5pp) | 55.2% FAIL | NO |
| 12:00 ET | 100.0% PASS | 100.0% PASS | FAIL (2 after-game) | PASS (pct05_reduced_26.0≥5pp; over_drift_reduced_5.0≥3; under_drift_reduced_5.0≥3) | 74.3% PASS | NO |

## 10. Recommendation

**NO CLEAR DECISION CUTOFF YET — Best compromise: 12:00 ET (4/5 criteria)**

Reason: No time satisfies all 5 criteria; 12:00 ET passes most

### Identity Implication

No single time satisfies all criteria. The decision time is not yet frozen.
Recommend expanding data collection or relaxing criteria thresholds before cutoff selection.

---

## Appendix: Collection Statistics

- API calls this session: 2060
- Total rows in checkpoint: 3190
- Credits remaining: 4138734
- Checkpoint file: `collection_checkpoint.parquet`

---

> **MPS STATUS: RESERVED / DATA-BLOCKED**
> 
> MPS remains RESERVED / DATA-BLOCKED. This audit selects a decision-time cutoff only. No signals have been tested, no predictive value has been claimed, and no changes to the canonical spec have been made.