# Phase 5Z Item 0 — Per-class clock comparison

200-game stratified sample, N=100. Real: PBP 2021-24 REG same 200 games.
Sack merged into complete_inbounds (sim has no separate sack class).

## NULL CHECK

Sim: Q1-Q4 all 900.0 s. **HOLDS.**
Real: Q1 898.4, Q2 898.6, Q3 896.5, Q4 888.0. **Real Q4 undercounts by ~12 s** (last plays
of games/halves have no next scrimmage snap to measure to; the remaining clock is estimated
but non-scrimmage time between drives is missed). Real total ~3582 vs sim ~3621. The ~39 s
difference is structural: scrimmage-to-scrimmage elapsed misses cross-drive non-scrimmage time.

## Table (a): per class — snaps/game and mean elapsed

| class | sim spg | real spg | sim elapsed | real elapsed | diff |
|-------|---------|----------|------------|-------------|------|
| run | 38.5 | 36.1 | 36.4 | 36.7 | -0.3 |
| first_down_rush | 11.2 | 11.1 | 36.0 | 36.8 | -0.8 |
| complete_inbounds | 24.0 | 24.6 | 35.8 | 35.9 | -0.0 |
| first_down_pass | 19.7 | 18.7 | 33.3 | 33.3 | -0.0 |
| incomplete | 24.6 | 20.5 | 7.8 | 7.6 | +0.2 |
| timeout_followed | 2.2 | 5.4 | 8.9 | 18.0 | -9.2 |
| drive_ending | 7.1 | 7.3 | 8.2 | 8.5 | -0.2 |
| kneel | 1.5 | 1.5 | 20.3 | 26.8 | -6.5 |
| spike | 0.1 | 0.2 | 1.0 | 1.8 | -0.8 |

## Table (b): by offence's score state

| state | sim elapsed | real elapsed | diff | sim spg | real spg |
|-------|------------|-------------|------|---------|----------|
| trail9+ | 26.1 | 25.5 | +0.6 | 23.0 | 27.3 |
| trail1-8 | 29.5 | 28.0 | +1.4 | 31.3 | 30.3 |
| tied | 31.9 | 30.4 | +1.5 | 22.8 | 23.9 |
| lead1-8 | 30.3 | 29.3 | +1.0 | 25.5 | 25.0 |
| lead9+ | 30.7 | 31.2 | -0.6 | 17.0 | 18.8 |

## Table (c): MIX vs RATE decomposition

| class | MIX (s) | RATE (s) |
|-------|---------|----------|
| run | +86.8 | -10.3 |
| first_down_rush | +4.1 | -8.4 |
| complete_inbounds | -23.2 | -1.0 |
| first_down_pass | +34.8 | -0.4 |
| incomplete | +31.4 | +4.0 |
| timeout_followed | -57.5 | -49.1 |
| drive_ending | -1.6 | -1.8 |
| kneel | +0.4 | -9.8 |
| **TOTAL** | **+74.9** | **-77.0** |

SUM: -2.0 s (closes within 5 s of the structural real-side undercount).

## Pre-registered evaluation

**(1)** RATE >= 60%: **FAILED.** RATE is 51%, MIX is 49%. The split is roughly even.

**(2)** Largest rate shortfall in run/complete_inbounds while leading: **FAILED.** The largest
rate shortfalls are timeout_followed (-9.2 s, -49.1 s RATE) and kneel (-6.5 s, -9.8 s RATE).
The sim takes 9 fewer seconds per timeout-followed snap (8.9 vs 18.0) and 6.5 fewer per kneel
(20.3 vs 26.8). Run and complete_inbounds rates are nearly matched (-0.3 and -0.0).

## NOT DONE
- Real Q4 last-play-of-game elapsed fixing (structural limitation of scrimmage-to-scrimmage measurement).
- All-1087-K1-games breakdown (the real_all data was loaded but not used in the tables).

## UNVERIFIED
- Whether the timeout_followed and kneel rate gaps explain the blowout excess.
