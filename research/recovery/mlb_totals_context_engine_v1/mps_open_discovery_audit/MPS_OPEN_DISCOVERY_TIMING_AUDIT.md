# MPS Open-Discovery Timing Audit — MLB Totals Context Engine V1

> **Status: AUDIT ONLY — MPS REMAINS BLOCKED**
> Generated: 2026-04-13 02:34 UTC

---

## 1. Audit Scope

This is a pure timing and data-availability audit. Its purpose is to identify the
optimal open-probe time for the MLB Totals Context Engine V1 Market Probe Signal (MPS).

**No modeling has been performed. No MPS path states have been defined.**
**No signals have been tested. No changes to the canonical spec have been made.**

The audit answers: *At what time of day do historical totals lines first appear with
sufficient coverage, same-book parity, and movement potential to support an opening-line
capture?*

---

## 2. Sample Design

- **Season:** 2024 (2,427 games after NaN-filter: 1,860 with valid `local_start_hour`)
- **Sample:** 30 games — 15 day starts (local hour ≤15), 15 evening starts (local hour ≥16)
- **Random state:** 99 (reproducible)
- **API calls made:** 270
- **Credits remaining after audit:** 4360434

### Sampled Games

| Date | Away | Home | Type | Local Hour |
|------|------|------|------|-----------|
| 2024-09-15 | NYM | PHI | Day | 13 |
| 2024-09-08 | CHW | BOS | Day | 13 |
| 2024-05-08 | TOR | PHI | Day | 13 |
| 2024-05-17 | PIT | CHC | Day | 13 |
| 2024-03-30 | DET | CHW | Day | 13 |
| 2024-04-17 | CIN | SEA | Day | 13 |
| 2024-09-18 | ARI | COL | Day | 13 |
| 2024-03-28 | SFG | SDP | Day | 13 |
| 2024-04-17 | PIT | NYM | Day | 13 |
| 2024-05-12 | CIN | SFG | Day | 13 |
| 2024-08-08 | MIL | ATL | Day | 12 |
| 2024-07-21 | CIN | WSN | Day | 13 |
| 2024-09-28 | CHW | DET | Day | 13 |
| 2024-07-14 | KCR | BOS | Day | 13 |
| 2024-06-30 | SDP | BOS | Day | 13 |
| 2024-04-19 | TOR | SDP | Evening | 18 |
| 2024-09-11 | CHC | LAD | Evening | 19 |
| 2024-06-28 | HOU | NYM | Evening | 19 |
| 2024-04-30 | NYY | BAL | Evening | 18 |
| 2024-06-27 | DET | LAA | Evening | 18 |
| 2024-05-09 | KCR | LAA | Evening | 18 |
| 2024-08-17 | WSN | PHI | Evening | 18 |
| 2024-07-29 | CHC | CIN | Evening | 19 |
| 2024-07-12 | OAK | PHI | Evening | 18 |
| 2024-05-15 | STL | LAA | Evening | 18 |
| 2024-05-01 | SFG | BOS | Evening | 19 |
| 2024-05-21 | SFG | PIT | Evening | 18 |
| 2024-07-05 | KCR | COL | Evening | 18 |
| 2024-05-29 | TOR | CHW | Evening | 18 |
| 2024-08-24 | ARI | BOS | Evening | 16 |

### Probe Schedule

| ET Probe | UTC Timestamp |
|----------|--------------|
| 00:01 ET | 04:01 UTC |
| 02:00 ET | 06:00 UTC |
| 04:00 ET | 08:00 UTC |
| 06:00 ET | 10:00 UTC |
| 08:00 ET | 12:00 UTC |
| 10:00 ET | 14:00 UTC |
| 12:00 ET | 16:00 UTC |
| 14:00 ET | 18:00 UTC |
| 17:00 ET (day games close) | 21:00 UTC |
| 18:00 ET (evening games close) | 22:00 UTC |

---

## 3. Coverage Results

### Table A — Coverage by Probe Time

| Probe | Games | Matched | Any Total | FanDuel | DraftKings |
|-------|-------|---------|-----------|---------|-----------|
| 00:01 ET | 30 | 28 (93%) | 27 | 25 | 24 |
| 02:00 ET | 30 | 28 (93%) | 28 | 27 | 25 |
| 04:00 ET | 30 | 29 (97%) | 29 | 29 | 27 |
| 06:00 ET | 30 | 30 (100%) | 29 | 28 | 29 |
| 08:00 ET | 30 | 30 (100%) | 29 | 28 | 29 |
| 10:00 ET | 30 | 30 (100%) | 30 | 30 | 30 |
| 12:00 ET | 30 | 30 (100%) | 30 | 30 | 30 |
| 14:00 ET | 30 | 30 (100%) | 30 | 30 | 30 |
| 17:00 ET (close-day) | 15 | 7 (47%) | 7 | 6 | 5 |
| 18:00 ET (close-eve) | 15 | 15 (100%) | 15 | 15 | 15 |

### Table B — First Availability by Bookmaker

| Bookmaker | N Games | Median First Probe | P25 | P75 |
|-----------|---------|-------------------|-----|-----|
| betmgm | 30 | 00:01 ET | 00:01 ET | 00:01 ET |
| betonlineag | 30 | 00:01 ET | 00:01 ET | 00:01 ET |
| betrivers | 30 | 00:01 ET | 00:01 ET | 00:01 ET |
| betus | 30 | 00:01 ET | 00:01 ET | 02:00 ET |
| bovada | 30 | 00:01 ET | 00:01 ET | 02:00 ET |
| draftkings | 30 | 00:01 ET | 00:01 ET | 00:01 ET |
| fanduel | 30 | 00:01 ET | 00:01 ET | 00:01 ET |
| lowvig | 29 | 00:01 ET | 00:01 ET | 00:01 ET |
| mybookieag | 29 | 00:01 ET | 00:01 ET | 00:01 ET |
| pointsbetus | 8 | 00:01 ET | 00:01 ET | 00:01 ET |
| superbook | 20 | 00:01 ET | 00:01 ET | 02:00 ET |
| unibet_us | 14 | 00:01 ET | 00:01 ET | 00:01 ET |
| williamhill_us | 30 | 00:01 ET | 00:01 ET | 00:01 ET |
| wynnbet | 20 | 00:01 ET | 00:01 ET | 00:01 ET |

### Table C — Timestamp Quality

| Probe | N | Median Delta (min) | P90 Delta (min) |
|-------|---|-------------------|----------------|
| 00:01 ET | 30 | 0.4 | 0.4 |
| 02:00 ET | 30 | 4.4 | 4.4 |
| 04:00 ET | 30 | 4.4 | 4.4 |
| 06:00 ET | 30 | 4.4 | 4.4 |
| 08:00 ET | 30 | 4.4 | 4.4 |
| 10:00 ET | 30 | 4.4 | 4.4 |
| 12:00 ET | 30 | 4.4 | 4.4 |
| 14:00 ET | 30 | 4.4 | 4.4 |
| 17:00 ET (close-day) | 15 | 4.4 | 4.4 |
| 18:00 ET (close-eve) | 15 | 4.4 | 4.4 |

---

## 4. Parity Results

### Table D — Same-Bookmaker Open-to-Close Pairs

| Probe | Games | FD Pairs | DK Pairs | FD Parity % | DK Parity % |
|-------|-------|----------|----------|-------------|-------------|
| 00:01 ET | 30 | 18 | 15 | 60.0% | 50.0% |
| 02:00 ET | 30 | 19 | 16 | 63.3% | 53.3% |
| 04:00 ET | 30 | 20 | 18 | 66.7% | 60.0% |
| 06:00 ET | 30 | 19 | 19 | 63.3% | 63.3% |
| 08:00 ET | 30 | 19 | 19 | 63.3% | 63.3% |
| 10:00 ET | 30 | 21 | 20 | 70.0% | 66.7% |
| 12:00 ET | 30 | 21 | 20 | 70.0% | 66.7% |
| 14:00 ET | 30 | 21 | 20 | 70.0% | 66.7% |

---

## 5. Market Movement

### Table E — Total Drift (Open to Close, Same-Book Pairs)

| Probe | N Pairs | Median Drift | ≥0.5 | ≥1.0 | =0.0 (no move) |
|-------|---------|-------------|------|------|---------------|
| 00:01 ET | 159 | 0.5 | 66.0% | 35.2% | 34.0% |
| 02:00 ET | 185 | 0.5 | 51.9% | 17.8% | 48.1% |
| 04:00 ET | 195 | 0.5 | 52.3% | 16.4% | 47.7% |
| 06:00 ET | 195 | 0.5 | 50.3% | 15.9% | 49.7% |
| 08:00 ET | 199 | 0.5 | 50.8% | 15.1% | 49.2% |
| 10:00 ET | 209 | 0.0 | 41.1% | 19.1% | 58.9% |
| 12:00 ET | 217 | 0.0 | 35.9% | 19.4% | 64.1% |
| 14:00 ET | 219 | 0.0 | 33.8% | 19.2% | 66.2% |

### Table F — Juice Drift (Over/Under Price, Open to Close)

| Probe | N Pairs | Med Over$ Drift | Med Under$ Drift | % Zero Juice Move |
|-------|---------|----------------|-----------------|------------------|
| 00:01 ET | 159 | 10.0 | 10.0 | 8.8% |
| 02:00 ET | 185 | 10.0 | 8.0 | 8.1% |
| 04:00 ET | 195 | 10.0 | 8.0 | 8.7% |
| 06:00 ET | 195 | 10.0 | 8.0 | 8.7% |
| 08:00 ET | 199 | 10.0 | 7.0 | 10.1% |
| 10:00 ET | 209 | 9.0 | 6.0 | 18.2% |
| 12:00 ET | 217 | 5.0 | 5.0 | 25.3% |
| 14:00 ET | 219 | 5.0 | 5.0 | 33.8% |

---

## 6. Recommended Open Probe Time

**Recommended probe:** `10:00 ET`

| Criterion | Value | Pass |
|-----------|-------|------|
| Hit rate ≥ 80% | 100.0% | Yes |
| FD parity ≥ 70% | 70.0% | Yes |
| DK parity ≥ 70% | 66.7% | No |
| Median TS delta ≤ 15 min | 4.4 min | Yes |
| Better drift than benchmark | 59% zero drift | No |

---

## 7. Viability Verdict

**PARTIALLY VIABLE**

No probe passes all 4 criteria. Best compromise: 10:00 ET

---

## 8. Full Backfill Implications

| Parameter | Value |
|-----------|-------|
| Seasons to backfill | 2022, 2023, 2024 |
| Games per season (est.) | ~2,430 |
| Total games | ~7,290 |
| Probes per game | 9 (8 standard + 1 close) |
| Estimated API calls | ~65,610 |
| Recommended bookmaker priority | FanDuel, DraftKings, BetMGM, WynnBet |
| Sleep between calls | 0.4s minimum |
| Estimated runtime | ~7.3 hours |

**Recommended probe schedule for backfill:**
- Primary open probe: `10:00 ET` (convert to UTC for each game date)
- Close probe: 17:00 ET for day games, 18:00 ET for evening games
- If full 9-probe backfill not needed, priority is: open probe + close probe (2 calls/game = ~14,580 total)

---

## 9. Status

> **MPS remains RESERVED / DATA-BLOCKED.**
>
> This audit identifies the best available open-probe timing only.
> No path states have been defined, no signals have been tested,
> and no changes to the canonical spec have been made.
> MPS activation requires a separate explicit authorization.