# Phase 3: Feature Definition Parity

## Feature-by-Feature Comparison

### 1. home_ortg / away_ortg (ORtg — offensive rating)
**Training (features.py):**
- Rolling 15-game window with shift(1) per team
- Location-specific rolling preferred (home games only / away games only)
- Falls back to overall rolling if < 5 same-location games
- Season blending applied (70% prior-season for first 15 games, fading to 0% by game 20)

**Live (run_nba.py _build_current_team_states):**
- Rolling 15-game window from tail(15) of games before today (functionally same as shift(1))
- NO location-specific rolling -- uses overall rolling only
- Season blending applied via same _blend() function from features module

**PARITY GAP: Location-specific rolling missing in live**
- In training, 96% of games (3,540/3,690) use location_rolling fallback level
- Median difference: 1.8 pts ORtg between location-split and overall rolling
- P90 difference: 5.2 pts
- Max difference: 9.0 pts
- Impact: The model was trained on location-split ORtg but receives overall ORtg at prediction time. This is a systematic feature distribution shift.

### 2. home_drtg / away_drtg (DRtg -- defensive rating)
**Same gap as ORtg.** Location-specific rolling in training, overall rolling in live.

### 3. home_pace / away_pace
**Same gap as ORtg.** Location-specific rolling in training, overall rolling in live.

### 4. b2b_flag_away (back-to-back flag, away team)
**Training:** Computed from game table via _build_rest_features()
**Live:** Computed via _compute_b2b() checking yesterday's games
**PARITY: OK** -- both check if team played the previous day

### 5. home_ortg_trend / away_ortg_trend (5-game vs 15-game delta)
**Training:** rolling(5, min_periods=3).shift(1) - rolling(15).shift(1)
**Live:** tail(5).mean() - tail(15).mean() (both from games before today)
**PARITY: OK** -- functionally equivalent. Both use the same 5 and 15 most recent completed games.

### 6. home_pace_trend / away_pace_trend
**Same as ortg_trend.** PARITY: OK.

### 7. home_3pa_rate / away_3pa_rate (3-point attempt rate)
**Training:** Rolling 15-game window with shift(1), overall (no location split)
**Live:** Rolling 15-game window from tail(15), overall
**PARITY: OK** -- same computation, no location split in either path.

### 8. home_ft_rate / away_ft_rate (free throw rate)
**Same as 3pa_rate.** PARITY: OK.

## Summary of Gaps

| Feature | Parity | Gap |
|---------|--------|-----|
| home_ortg, away_ortg | GAP | Location-split in training, overall in live |
| home_drtg, away_drtg | GAP | Location-split in training, overall in live |
| home_pace, away_pace | GAP | Location-split in training, overall in live |
| b2b_flag_away | OK | Both check previous day |
| ortg_trend (home/away) | OK | Same 5v15 delta |
| pace_trend (home/away) | OK | Same 5v15 delta |
| 3pa_rate (home/away) | OK | Both overall rolling |
| ft_rate (home/away) | OK | Both overall rolling |

**Critical gap: 6 of 15 features (ortg, drtg, pace x home/away) differ systematically between training and live. These 6 features carry the largest Ridge coefficients (pace: ~4.1/3.9, ortg: ~2.0/1.6, drtg: ~1.7/1.4).**
