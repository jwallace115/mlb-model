# NHL simulation engine — plan (2026-09-29)

Decisions: `NHL_SIM_DECISION_v1.md` (S1 scope, S2 data/splits/test). Code: `nhl/sim/` (mirrors `nfl/sim/`).
Data: `nhl/data/sim/` (derived, committed when < 2 MB per file) and `nhl/cache/pbp/` (raw, gitignored).

## What the engine simulates
One game = one call holding N parallel game states as numpy arrays (vectorised across sims, like the NFL engine).
State: period, seconds left, score, strength state (5v5, 5v4, 4v5, 4v4, 5v3, 3v5, 3v3 in OT), penalty clocks,
goalie on the ice or pulled for each team. The clock advances by event: the waiting time to the next event
(unblocked shot attempt by either team, penalty, goalie pull, period end) is exponential with a rate that depends on
the state. A shot becomes a goal with probability = shooting team's shot quality x opponent's suppression x the
opposing goalie's save factor, applied to a league expected-goals baseline for that strength state.
- Penalties: per-team drawn/taken rates, 2-minute minors ended early by a power-play goal; majors/doubles from
  measured frequencies.
- Score effects: trailing teams generate more attempts, leading teams fewer — multipliers measured by score
  difference and period.
- Pulled goalie: hazard of pulling by score difference and seconds remaining, measured from play-by-play; empty-
  net for/against rates measured.
- Overtime: regular season 5 minutes 3-on-3 sudden death with its own measured rates; then a shootout (measured
  round conversion; best of 3, then sudden death). Final score counts the shootout winner's +1, as books settle.
- Output per sim: final score, regulation score, decided (REG/OT/SO), shots, power-play goals, empty-net goals.
- Prices: ML, puck line +/-1.5, totals (5.5/6/6.5 and Pinnacle's line), 60-minute 3-way, OT yes/no.

## Inputs (all point-in-time: only games before the game date)
- Team ratings per strength state: unblocked attempts for/against per 60, shot quality for/against (own xG per
  attempt), penalties drawn/taken per 60 — shrunk toward league average with weights measured by split-half
  reliability, carried over from the prior season with measured regression.
- Goalie: goals saved above expected per attempt, shrunk; the actual starter (known at puck drop).
- Home ice measured, not assumed.

## Phases (each a work order of <= 4 items)
- **S-WO1 data + constants:** play-by-play pull; event and strength-state tables with exact null controls against
  box scores; own xG model on 2021-23 shots, frozen; measured league constants (with derivations) in one JSON.
- **S-WO2 ratings + reliability:** point-in-time team and goalie ratings; split-half reliability; shrinkage weights.
- **S-WO3 engine:** vectorised engine; determinism; realism report on 2022-23 (fit) with pre-stated bands.
- **S-WO4 pricing + validate:** prices; realism gate and any calibration map on 2023-24 only.
- **S-WO5 holdout:** one locked scoring of 2024-25 + 2025-26 against Pinnacle (S2).
- Later: player props on the same engine (shot/goal/assist shares by ice time), then daily runs feeding the packet.
