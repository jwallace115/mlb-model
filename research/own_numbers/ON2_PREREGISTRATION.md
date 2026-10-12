# ON-2 Pre-registrations — written BEFORE scoring

## ON-1a (from spec, prior 45%)
Same test on 2021-23 bet365 opens (construction seasons; in-sample for
calibration, not for the engine) > 55%.

**Prediction:** The confident subset (|ours_m - open_spread| >= err_m AND >= 1.0 pt)
calls the direction of open→close movement > 55%.

## ON-1b (from spec, prior 60%)
Outside the confident subset, direction agreement is 48-52%
(the error bar separates signal from noise).

## ON-2 (from spec, prior 45%)
corr(our Monday→kickoff change, line open→close move) > 0.2 on 2021-23
(availability is a visible share of movement).

**Note:** ON-2 requires two engine runs per game (Monday vs kickoff active universe).
If usage.py cannot take an as-of active universe without editing, this sub-item STOPs.

## Null control
Our numbers shuffled across games within the same week, 1,000 draws seeded (seed=42).
Direction agreement under the null must sit at 50 +/- noise.
