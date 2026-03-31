# Hitter Profile Notes

Total hitter-game rows: 174870
Unique players: 1229

## Metrics Built
- hitter_k_rate_last20: K/PA rolling 20 games (shift+rolling, min 8 games)
- hitter_bb_rate_last20: BB/PA rolling 20 games
- hitter_contact_rate_last20: H/AB rolling 20 games
- hitter_iso_last20: (TB-H)/AB rolling 20 games
- Season-to-date versions of all four (expanding within season, min 5 games)

## Metrics NOT Built
- hitter_hard_hit_rate: requires Statcast batter-level data (not available per-batter locally)
- hitter_barrel_rate: same limitation
- hitter_pull_rate: not available from boxscores
- hitter_avg_launch_angle: not available from boxscores
- Handedness splits: batSide not in boxscore data

## Coverage
- Last 20 metrics available for 97.9% of 2024-2025 hitter-games
- Gaps are early-season (first ~8 games per player per season) and rookies with < 8 career PA
