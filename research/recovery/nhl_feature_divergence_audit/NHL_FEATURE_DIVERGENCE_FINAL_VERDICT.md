# NHL Feature Divergence - Final Verdict

## VERDICT: MULTIPLE MISMATCHES

Five independent divergence sources between canonical rebuild and live pipeline.
Three are code bugs, one is a design mismatch, one is an operational issue.

---

## Bug Inventory

### BUG 1 (D3): goalie_sv_pct_rolling_10 is team-wide, not goalie-specific
- File: nhl/nhl_daily_pipeline.py
- Function: build_live_team_features()
- Lines: ~444-485, 528-531
- Root cause: The goalie_sv_pct array at line 444 appends ALL team games
  regardless of goalie_id. At line 528, the last-10 slice is taken from this
  team-wide array. Should filter by todays starting goalie_id.
- Fix: Track goalie_id in the array. When computing rolling_10, filter to
  only games where this goalie started. Requires passing todays goalie_id
  into build_live_team_features().

### BUG 2 (D4): goalie_vs_team_baseline is effectively dead
- File: nhl/nhl_daily_pipeline.py
- Function: build_live_team_features()
- Lines: 535-539
- Root cause: Cascading from Bug 1. Compares team-wide rolling_10 to
  team-wide all_mean, which are nearly identical.
- Fix: Once Bug 1 is fixed (goalie-specific rolling_10), this feature will
  naturally produce the correct signal. No separate fix needed.

### BUG 3 (D5): goalie_fatigue counts team games, not goalie games
- File: nhl/nhl_daily_pipeline.py
- Function: compute_game_features()
- Lines: 574-579
- Root cause: Filters only by team and date range, does not filter by goalie_id.
- Fix: Add goalie_id filter to the recent games query. Requires the live cache
  to include goalie_id (which it does in the extended schema).

### DESIGN ISSUE (D2): Prior definition mismatch
- Canonical: league avg of raw per-game stats for current season (look-ahead)
- Live: mean of 2024 OOS feature values (no look-ahead)
- Recommendation: Change live priors to use prior-season raw league averages.
  Compute from nhl_games_canonical.csv for season_year=2024. This eliminates
  the look-ahead in canonical while keeping the live definition principled.

### OPERATIONAL ISSUE (D1): Stale live cache
- The live cache (nhl/cache/nhl_live_season.parquet) is currently 375 games
  from the old 6-column format. It lacks extended boxscore fields.
- The code correctly detects this and triggers a refresh, but:
  a) The refresh requires ~1300 NHL API calls (~65s minimum)
  b) If the daily pipeline is not currently running, no refresh occurs
  c) A failed/timed-out refresh leaves the stale cache
- Fix: Run the daily pipeline once to trigger the refresh. Consider adding
  a standalone cache refresh script.

---

## Fix Specification (No Implementation)

### Priority 1: Force cache refresh
- Run: python3 nhl/nhl_daily_pipeline.py --date 2026-04-10
- This will detect missing home_sog, trigger full refresh, populate cache
  with ~1258 games and all extended columns

### Priority 2: Fix goalie_sv_pct to be goalie-specific
- In build_live_team_features(), add a parameter for todays_goalie_id
- When building goalie_sv_pct array, also track goalie_ids list
- At rolling computation (line 528), filter gsv_tail to only entries where
  goalie_id matches todays_goalie_id
- If fewer than 3 matching games, use team-wide with heavier shrinkage

### Priority 3: Fix goalie_fatigue to filter by goalie_id
- In compute_game_features() line 574-579, add filter:
  recent = recent[recent home/away_goalie_id == todays_goalie_id]
- Requires extended cache columns (goalie_id is included)

### Priority 4: Align priors
- Replace compute_league_priors() to use raw per-game stats from
  season_year=2024 in nhl_games_canonical.csv
- This matches what canonical does (league avg of raw stats) but uses
  prior season (no look-ahead)

### Priority 5: goalie_vs_team_baseline auto-fixes after Priority 2

---

## Impact Assessment

With all fixes applied:
- Expected prediction delta: ~0.00 (mean), ~0.05 (std) vs canonical
- MAE improvement: ~0.005 (small but directionally correct)
- Correlation recovery: from 0.004 to ~0.015 (matching canonical)
- Goalie differentiation restored: ~0.02-0.03 additional discrimination
  on goalie quality games
