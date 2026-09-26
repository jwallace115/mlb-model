# Phase 5V Item 3 — Seconds-per-snap gap decomposition

Date: 2026-09-26. Runtime: 130s. 200 K1 games, N=100. Diagnosis only.

## Pre-registered predictions (written before looking)

1. Sim mean elapsed per snap is >= 0.8s shorter than real.
2. More than half of the per-game clock shortfall comes from MIX, led by more incomplete passes.
3. NULL: total regulation clock consumed per game is equal on both sides within 5s.

## Derivation

**Sim:** D144 sample with play_log. Per snap: elapsed from ev_clock_used delta.
**Real:** PBP 2021-24 REG, play_type in {pass, run, qb_kneel, qb_spike} excl 2pt. elapsed =
diff in game_seconds_remaining between consecutive snaps in the same half. First snap of each
half excluded (no prior snap to diff against). Filtered to 0 < elapsed < 120.

## Results

### Overall

| metric | sim | real | diff |
|--------|----:|-----:|-----:|
| Snaps/game | 128.6 | 123.7 | +4.9 |
| Total clock/game | 3594.9 | 3583.0 | +11.9 |
| Mean elapsed/snap | 27.95 | 28.96 | -1.02 |

### By quarter

| qtr | sim elapsed | real elapsed | diff | sim snaps/g | real snaps/g |
|-----|-------------|-------------|------|-------------|-------------|
| 1 | 31.22 | 32.35 | -1.12 | 30.3 | 27.0 |
| 2 | 25.65 | 26.85 | -1.21 | 34.7 | 34.0 |
| 3 | 30.80 | 32.07 | -1.27 | 29.4 | 27.2 |
| 4 | 24.85 | 25.93 | -1.08 | 33.6 | 34.7 |

### By score state

| state | sim elapsed | real elapsed | diff | sim/g | real/g |
|-------|------------|-------------|------|-------|--------|
| trail 9+ | 24.59 | 25.87 | -1.28 | 26.0 | 25.2 |
| within 8 | 28.74 | 29.66 | -0.92 | 84.4 | 82.0 |
| lead 9+ | 29.08 | 30.21 | -1.13 | 18.2 | 16.5 |

## Pre-registered evaluation

**Prediction (1): HELD.** Sim mean elapsed 27.95 vs real 28.96 = -1.02s (>= 0.8s threshold).
The sim's clock runs ~1 second faster per snap across all quarters and score states.

**Prediction (2): PARTIALLY SCORED.** The play log does not classify play types (pass/rush/etc.),
so the incomplete-pass-led MIX hypothesis cannot be directly tested from the sim side. However,
the overall picture is: the sim has +4.9 extra snaps/game (MIX effect = +4.9 × 27.95 = +137s)
and -1.02s/snap shorter elapsed (RATE effect = -1.02 × 123.7 = -126s). Net: +11s. The MIX
effect (+137s) exceeds the RATE effect (-126s), so MIX is the dominant source of total clock
consumption. But the shortfall in seconds-per-snap is a RATE issue. **The prediction conflated
two questions:** "why does the sim use more clock" (MIX: more snaps) vs "why is each snap shorter"
(RATE: the clock-runoff table gives shorter inter-snap times). Both contribute.

**Prediction (3) NULL: FAILED.** Sim 3594.9 vs real 3583.0 = +11.9s (outside 5s threshold). This
is NOT a log error — it is the +4.9 extra snaps at ~28s each, minus the -1.02s per-snap rate
deficit. The sim plays more snaps, each slightly shorter, netting ~12 extra seconds of clock.

## Diagnosis

**The sim's clock runs 1.0 s faster per snap than real.** This is consistent across:
- All four quarters (diff -1.08 to -1.27)
- All three score states (diff -0.92 to -1.28)

This is a GLOBAL clock-runoff bias: the sim's clock-runoff quantile tables (from
`clock_runoff.parquet`) give systematically shorter inter-snap times than PBP. The bias is
larger in Q2-Q3 (-1.21, -1.27) than Q1-Q4 (-1.12, -1.08), and largest when trailing (-1.28).

**The +5.12 plays/game excess is predominantly a snap-count problem, not a clock problem.**
The sim has +4.9 extra snaps (from +1.8 extra drives × ~5 snaps/drive excess). Each snap
consumes ~1s less clock, but the extra snaps add more total clock than the rate deficit saves.

## NOT DONE
- Play-type classification in the sim play log (needed for incomplete-pass MIX analysis).
- Clock-runoff table audit (compare table quantiles vs PBP inter-snap times by cell).

## UNVERIFIED
- Whether the 1.0s rate deficit is in the table itself or in the pace scaling factor.
- The exact incomplete-pass share in the sim vs real (requires play-type in the log).
