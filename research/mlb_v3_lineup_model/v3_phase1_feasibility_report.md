# V3 Lineup Model — Phase 1 Feasibility Report

## Q1: Can we reconstruct historical actual lineups reliably?

**YES.** 9715 games with batting order extracted from boxscores.
Complete 9-player lineups: 100.0% of all team-games.
Coverage: 2022-2025, all regular season + postseason games cached.

## Q2: Can we build pregame rolling hitter skill profiles reliably?

**YES, for boxscore-derived metrics.** K rate, BB rate, contact rate, ISO all computed
as rolling-20-game and season-to-date features.
Coverage (2024-2025 hitter-games):
- hitter_k_rate_last20: 97.9%
- hitter_bb_rate_last20: 97.9%
- hitter_contact_rate_last20: 97.9%
- hitter_iso_last20: 97.9%
- hitter_k_rate_season: 92.6%
- hitter_bb_rate_season: 92.6%
- hitter_contact_rate_season: 92.6%
- hitter_iso_season: 92.6%

**NOT available from boxscores:** hard_hit_rate, barrel_rate, pull_rate, launch_angle.
These would require Statcast batter-level data (currently only available at pitcher-level).

## Q3: Which lineup-level metrics have strong enough coverage for V3?

| Metric | 2024-2025 Coverage |
|--------|-------------------|
| lineup_k_rate_last20 | 100.0% |
| lineup_bb_rate_last20 | 100.0% |
| lineup_contact_rate_last20 | 100.0% |
| lineup_iso_last20 | 100.0% |
| lineup_size | 100.0% |
| top4_iso_last20 | 100.0% |
| bottom3_k_rate_last20 | 100.0% |

All four core metrics (K rate, BB rate, contact rate, ISO) exceed 90% coverage.
Structural features (top4 ISO, bottom3 K rate) also exceed 85%.

## Q4: Are handedness splits feasible now or later?

**LATER.** batSide (L/R/S) is not in the boxscore player data.
Would need a separate roster/player-info API pull to build handedness lookup.

## Q5: Data foundation readiness

**Game-level foundation dataset: 9715 games**
- Both full lineup metrics: 98.7%
- Core metrics (K rate + ISO) both sides: 98.7%
- With closing total (2024-2025): 4855
- With V1 p_under (2024-2025): 4855

## Biggest Data Gaps

1. **Statcast batter metrics** (hard_hit, barrel, pull, launch angle)
2. **Batter handedness** — needed for pitcher-lineup platoon interaction modeling
3. **Projected lineups** — current data uses actual lineups only

## Recommendation

**ADVANCE to Phase 2.**

The data foundation is solid for boxscore-derived metrics:
- 9715 games with complete actual lineups
- ~98% hitter rolling profile coverage
- ~99% game-level lineup environment coverage

Phase 2 should:
1. Test actual-lineup features as ceiling test against team-level features
2. Determine if lineup-level modeling materially improves totals prediction
3. If ceiling test passes, proceed to Phase 3 (projected-lineup engine)
