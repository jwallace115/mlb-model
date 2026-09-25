# Phase 5T Item 2 — tied_drives red diagnosis

Date: 2026-09-25. Runtime: 14s. 12-game 5A-9 sample, N=500, drive_log=True.
Diagnosis only; no engine change.

## Pre-registered prediction

>= 60% of expirations are a drive whose last snap was inside the final 10s with the clock
running after an in-bounds gain, where a real team spikes or uses a timeout and the sim has
no spike and did not use one.

## Results

Reached (Q4, <=300s, tied, reached the 35): 340 drives. Expired: 33. Rate: 9.71% (real 0/56).

### Expired drive characteristics

| metric | value |
|--------|-------|
| Mean end yardline | 28.2 |
| In FG range (yl <= 45) | 94% |
| Mean start clock | 45.1s |
| Median start clock | 31.6s |
| Mean plays | 3.5 |
| Started inside 35 | 12.1% |

End yardline breakdown: <20 (21%), 20-30 (33%), 30-35 (30%), 35-45 (9%), >45 (6%).

### Non-expired reached drives (307)
FG made 59.6%, TD 25.7%, FG missed 5.5%, fumble 3.6%, downs 2.9%, INT 2.0%, punt 0.7%.

## Pre-registered evaluation

**FAILED.** The prediction targeted "last snap inside final 10s" drives specifically. The drive
log does not record per-play clock, so the exact last-snap clock cannot be verified. However,
39.4% of expired drives started with <= 30s and 54.6% with <= 60s. The median start clock is
31.6s. These are drives that START late and run the clock out in 3-4 plays, not drives that
played a full possession and ran out at the end. The mechanism is broader than "spike/timeout
at the final 10s."

## Diagnosis — the mechanism

**94% of expired drives ended in FG range (yl <= 45).** A real team at the 28-yard line with
the clock expiring would spike the ball and kick a field goal. The sim allows the clock to
run out instead.

The non-expired comparison is telling: 59.6% of non-expired reached drives kick a FG. The
expired drives are in the SAME field position but the clock management logic does not switch
to FG-attempt mode in time.

Candidate causes:
1. The `eoh_fg_decision` table may not trigger when the game is tied in Q4 (it may only fire
   at the literal end of a half, not when the game is about to end with the score tied).
2. The `fg_setup` logic may require more plays/clock than is available (e.g., it needs a
   spike play + FG attempt = 2 plays, but the clock runs out on the spike).
3. The clock-runoff per play may consume the remaining time before the FG logic can fire.

This is NOT a one-table/one-branch fix. The interaction between the FG-decision triggers,
the clock-runoff model, and the end-of-game detection would need to be traced through the
engine's step loop. The fix is queued but not implemented here.

## NOT DONE
- The fix (requires deeper engine analysis of FG-setup/spike/timeout interaction).
- Per-play clock trace (drive log records drive-level, not play-level).

## UNVERIFIED
- Whether the `eoh_fg_decision` table actually triggers in these situations.
- Whether a spike is simulated (the engine has ev_spikes; whether it fires here is unknown).
