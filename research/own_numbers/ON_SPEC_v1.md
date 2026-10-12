# Own Numbers (ON) — spec v1, Cowork priors, work order ON-1 (2026-10-12)

Jeff (2026-10-12): "build our own numbers, so the way we look at data is how we want to and not what the books
already do." Cowork's framing, agreed in chat: not a third power rating (the engine's ratings and the ridge are
already that, at 0.82 with the market, nothing left over) but our own QUESTIONS — the ones the book's process
cannot answer: how confident is the number; what happens to it when specific players are out; the Monday number
before the market has converged. Hard Rock posts early (Jeff, 2026-10-12).

## What the tape says about the early-week target (NFL 2026 weeks 2-5, 75 games, measured 2026-10-12)

- Hard Rock lists 95 % of games ≥ 5 days out (median 6.7 days: the Monday before). Pinnacle: 93 %.
- Hard Rock's FIRST number vs its close: mean |Δ| 0.76 pts; ≥ 1 pt in 33 %, ≥ 2 pts in 8 %. Pinnacle's opener is
  no better: 0.81 / 43 % / 9 %. At 3 days out: 0.53 / 25 % / 1 %.
- Hard Rock's opener differs from Pinnacle's opener on 48 % of games, by ≥ 1 pt on 12 %.
- So: ~5 of 16 games per week will move ≥ 1 pt from Hard Rock's Monday number to kickoff. The ON product is a
  Monday number with an error bar that (a) says which games those are and (b) calls the direction better than
  50 %. Historical analogue: bet365 open→close 2021-23 (815 games, now on disk as spread_opens_2021_23.parquet;
  retail open, labelled as such) — mean |open−close| 1.54, ≥ 1 pt in 59 %.

## The four pieces (in build order)

1. **Uncertainty.** Every number we publish carries an error bar built from three measured parts: the ratings'
   sample depth (games played into the shrinkage), the Monte-Carlo SE at N = 5,000, and the as-of calibration of
   |ours − close| from prior seasons. "High confidence" = the gap between our number and the line exceeds our
   own error bar. This is what turns "few, high-confidence" from a wish into a filter.
2. **Availability through the engine.** The timestamped injury feed (the cleanest PIT source in the inventory) is
   folded in at the PLAYER level through the existing usage layer and the engine — a left tackle out changes the
   pass-protection channel, not a team-wide fudge. Two numbers per game: Monday-noon state and kickoff state.
   The size of our Monday→kickoff change versus the line's open→close move measures how much of the market's
   movement is availability we could have seen first.
3. **Distribution, not mean.** Already partly tested (GL-1 item 3: the engine's shape ≈ normal). The remaining
   question is joint structure (side × total, same-game legs); it needs SGP prices that are not captured. Deferred;
   not in ON-1.
4. **The Monday runner.** Every Monday 12:00 ET: our number + error bar for every game, Hard Rock's opener and
   Pinnacle's, logged before anything is bet; the confident list (|ours − HR| ≥ error bar AND ≥ 1 pt) shown to the
   reader as a layer; graded against the close and the result. This is the forward test that answers the question
   in-season.

## Discipline (unchanged)

Target invariant in every builder (|corr(residual, close)| < 0.05, known-game assertions, zero-variance HALT).
2021-23 for construction; 2024 the one clean look, still UNTOUCHED, opened only for a frozen spec after review;
2026 forward via the runner. Pre-registration before numbers; permutation null on every fit; tune nothing.
Credits: 0. Scoring of the Monday number on 2026 weeks 2-5 is an interim look at forward data, not a tuning set.

## Cowork priors (ledger IDs ON-*)

| id | prediction | prior |
|---|---|---|
| ON-0 | On the 2024 clean look, the confident subset (|ours − open| ≥ error bar, ≥ 1 pt) calls the direction of open→close movement > 55 % with N ≥ 60 | 30 % |
| ON-1a | Same test on 2021-23 bet365 opens (construction seasons; in-sample for calibration, not for the engine) > 55 % | 45 % |
| ON-1b | Outside the confident subset, direction agreement is 48-52 % (the error bar separates signal from noise) | 60 % |
| ON-2 | corr(our Monday→kickoff change, line open→close move) > 0.2 on 2021-23 (availability is a visible share of movement) | 45 % |
| ON-3 | The confident subset beats the CLOSE on outcome (actual − close has the sign of ours − close) > 53 % on 2024 | 15 % |

ON-0 and ON-3 are the two that matter; everything else is plumbing that can be true while they are false.
