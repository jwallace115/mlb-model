# Pre-registration ALT — the engine as a pricing layer: soft-book totals at points Pinnacle does not hang
(Cowork, written while the engine grid was still running, before any conditioned price met an outcome)

Why: the engine's own team-strength opinion lost to Pinnacle three ways (log-loss, A1/A2, CLV). But PREREG_EV2
confirmed that soft-book prices beating Pinnacle's fair price ~25 h out keep +2.7% CLV to the close. Pinnacle's fair
price only exists at Pinnacle's own point. 17% of soft-book total quotes sit at a different point (6.5 vs 6.0 vs 5.5).
Converting between points needs the full final-total distribution (OT/SO +1 makes even totals rare: P(total=6) is
~11%, not a Poisson ~16%). That is exactly what a game-state sim knows and a market doesn't publish.

Engine object: engine.py (S34+S39, constants_v8) at league-average inputs, with two knobs only:
strength s (home non-EN goal rate x e^s, away x e^-s) and pace m (all non-EN goals x m).
Grid s = -0.5..0.5 step 0.125, m = 0.80..1.16 step 0.06, 20,000 sims per cell, seed = cell index
(market_grid_v1.npz). Joint final-score pmf per cell, bilinear interpolation in (s, m).
No team ratings are used: strength and pace come from Pinnacle, the SHAPE comes from the engine.

Per game and snapshot: solve (s, m) so the engine matches Pinnacle's de-vigged P(home win) and P(over) at Pinnacle's
total point (integer point: P(over | no push)). Drop games whose solve leaves the grid or misses by > 0.005.

Bets: every non-Pinnacle totals quote at a point != Pinnacle's point at the same snapshot. For each game, the best
price per (point, side) across books; EV = p_win x (dec - 1) - p_lose (push returns stake). Bet when EV >= 0.02;
ONE bet per game (largest EV).

Seasons: 2022-23 + 2023-24 (dev). If H3 holds, 2024-25 + 2025-26 is run ONCE as confirmation with no change.

H3 (primary): EARLY snapshot (earliest >= 12 h before puck with Pinnacle): mean CLV > 0, 90% CI lower bound > 0,
game-clustered. CLV = EV of the same bet recomputed with the CLOSE-snapshot solve (same point, same bet price).
Secondary (reported, not tested): ROI with SE; CLOSE-snapshot rule; by season, month, point, side, book, EV band.
Engine-structure check (no betting): engine-conditioned P(favourite -1.5) vs Pinnacle's de-vigged puck line on the
same games, mean difference and log-loss on outcomes.
One run. If H3 fails, the alt-line layer is dead at this spec and is not re-tuned.
