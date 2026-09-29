# NHL sim — amendment A1 (written 2026-09-29, while S-WO3 is running; BEFORE any holdout is opened)

Jeff asked whether tying success to Pinnacle just makes the engine mirror Pinnacle, and whether it should model
pace, coaching style and other modifiers. Agreed changes. They go into the decision log as the first S-entry of the
work order after S-WO3 ("S-WO3b"). This file fixes their wording and time now.

## A1.1 — The engine's target is actual outcomes; Pinnacle is only the yardstick (clarifies S2)
- Nothing in the engine is fitted to prices. Every rating, modifier and constant is fitted to play-by-play outcomes.
- Any correlation with Pinnacle (e.g. S-WO3 item 3) is a one-time sanity floor. It is never a quantity to raise by
  adjusting the ratings. Checks against ACTUAL results come first; the market comparison is secondary.

## A1.2 — The pass rule gains an incremental-information test (amends S2, before the holdout)
S2's BEAT / MATCH / TRAILS on log-loss stays, but MATCH alone no longer earns weight, because an engine that matches
Pinnacle adds nothing. Added, on the holdout (2024-25 + 2025-26), per market (moneyline, total):
- Fit a logistic regression: outcome ~ logit(Pinnacle de-vigged) + [logit(engine) - logit(Pinnacle)].
- The engine earns weight as a layer ONLY IF the coefficient on the disagreement term is > 0 with a game-clustered
  90% CI excluding 0.
- Also reported:
  - the hit rate of the engine's side when |engine - Pinnacle| > 0.03;
  - ROI of that side at the median book price (Hard Rock still has to be checked in the app).
- Pre-registered expectation: the disagreement coefficient's CI includes 0 (the engine adds no information beyond
  Pinnacle).

## A1.3 — Team-specific modifiers (coaching and style), added in S-WO3b and kept only if they earn it
Each one is:
- measured from prior games only;
- shrunk with K from split-half reliability on the fit seasons;
- kept only if adding it improves log-loss on ACTUAL 2023-24 outcomes (validate). Otherwise it is set to the league
  value and the result is reported.

Candidates:
- team score effects: attempt-rate and goals-per-attempt response when leading / trailing, relative to the league
  multipliers in constants_v2;
- goalie-pull aggressiveness: the team's pull timing vs the league hazard, at -1 / -2;
- power-play shooting and zone style: xG per attempt on the PP, rush share;
- rest / back-to-back / travel effects on attempt and xG rates. These are measured as on-ice effects; the edge
  hunt showed they are already in the price, so they add accuracy, not necessarily disagreement;
- goalie workload: second game of a back-to-back, recent starts.

Expected (stated now): most coaching modifiers shrink close to the league value (small samples, e.g. about 10
pulled-goalie situations per team-season). That is a valid result.
