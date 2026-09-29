# FWD1 Runbook — NFL sim v1 forward test

## Before each kick window

### TNF (Thursday ~8:15 PM ET)

```bash
cd /Users/jw115/mlb-model
python3 nfl/sim/run_forward_v1.py --week <W>
```

This runs for the games in the window. If only TNF is pre-kick, it covers that one game.

### Sunday 1 PM ET window

```bash
cd /Users/jw115/mlb-model
python3 nfl/sim/run_forward_v1.py --week <W>
```

Run ~30 min before the 1 PM ET kickoff (12:30 PM ET / 16:30 UTC). This covers
all Sunday early games plus any late-afternoon games.

For games kicking later (4:25 PM ET, SNF 8:20 PM ET), run again with a later
--as-of if the first run didn't cover them (depends on props pull timing).

### MNF

```bash
cd /Users/jw115/mlb-model
python3 nfl/sim/run_forward_v1.py --week <W>
```

Same pattern. The harness only picks up games that haven't kicked yet.

## Scoring (at each checkpoint)

```bash
cd /Users/jw115/mlb-model
python3 nfl/pipeline/log_ai_opinions.py score --week <W> --out research/nfl_sim/fwd1_score_w<W>.md
```

For cumulative scoring across weeks, score each week individually and combine.

Checkpoints: 500 and 1,500 scored two-way legs. Nothing is concluded before 500.

## Verify (any time)

```bash
python3 nfl/pipeline/log_ai_opinions.py verify --week <W>
```

## Notes

- The harness runs test_freeze_v1 first — if the engine was modified, it halts.
- Game lines (h2h, spreads, totals) are logged as no_view (the sim is anchored to the market).
- The anchor sidecar is written next to the frozen file for each run.
- A game whose anchored margin or total misses the market by > 1.0 point is "unanchored";
  its props are scored but reported separately and excluded from P1/P2.
