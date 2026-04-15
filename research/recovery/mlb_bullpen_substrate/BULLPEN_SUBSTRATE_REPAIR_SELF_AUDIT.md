# BULLPEN SUBSTRATE REPAIR — SELF-AUDIT
Date: 2026-04-15

## Authorization Check
- [x] Files written only to authorized paths (research/recovery/mlb_bullpen_substrate/, sim/data/)
- [x] No live/shadow objects modified (only production data files replaced)
- [x] No commits or pushes made
- [x] No background tasks used
- [x] All SSH work on root@142.93.242.4, /root/mlb-model

## PIT-Safety Audit

### Defect 1 (CG Gap)
- CG rows correctly receive n_relievers=0, total_pitches=0
- Rolling features for the NEXT game correctly see 0 relievers/pitches used in the CG game
- No information from the current game appears in that game's own feature row ✓

### Defect 2 (Closer Look-Ahead)
- BEFORE: closer_gf = groupby(team, season, pitcher_id).sum() of games_finished
  → Uses ALL 162 games of a season to rank April closers. NOT PIT-safe.
- AFTER: Incremental cumulative GF updated after each game processed.
  → At each game G, pitcher_cum_gf contains only games BEFORE G (date < G.date or 
    same date with game_number < G.game_number for doubleheaders). ✓
- The "last 2 games" window uses recent_games[-2:] which is built from already-processed
  prior games. No current-game data used. ✓
- HLA at first game of season = 1 (no trailing data → closers assumed rested). 
  This is conservative and correct. ✓

### Rolling Features
- relievers_used_last_game: shift(1) within (team, season) group → first game = NaN ✓
- bullpen_pitches_last_game: same ✓
- relievers_used_last_3_games: shift(1) + rolling(3) within (team, season) group ✓
- bullpen_pitches_last_3_games: same ✓
- No cross-season leakage (groupby resets at season boundary) ✓

## Schema Integrity
- Original columns preserved exactly: game_pk, date, season, game_number, team,
  relievers_used_last_game, relievers_used_last_3_games, bullpen_pitches_last_game,
  bullpen_pitches_last_3_games, high_leverage_available ✓
- No new columns added (consumers require no modification) ✓
- No columns removed ✓
- Data types preserved (int for HLA, float for lag features, object/datetime for keys) ✓

## Data Lineage
- bullpen_usage_repaired: bullpen_usage.parquet + 2026 rows from sim/data/cache/boxscores/
  (same parse_boxscore() logic as phase8_bullpen_features.py)
- bullpen_features_repaired: rebuilt from bullpen_usage_repaired using corrected logic
- Production files: exact copies of staging files (no transformations at promotion step)

## Consumers Verified
All consumers use path `sim/data/bullpen_features.parquet` (or `bullpen_usage.parquet`).
Schema unchanged → no code modifications required. ✓

## Residual Risks
- MINOR: The HLA threshold of <25 combined pitches (top-3 in last 2 games) was retained
  from the original spec. This threshold was not re-tuned in this repair pass.
- MINOR: 2026 games only extend to 2026-04-09. As more games accumulate, phase8 
  --fetch should be re-run to extend cache further.
- ACCEPTABLE: 150 NaN rows in rolling lag columns (first game of each team-season).
  Downstream models handle these via fillna or dropna in merge operations.

## Verdict
PIT-SAFETY: CONFIRMED. No future data used in any feature computation.
BACKWARD COMPAT: CONFIRMED. All 19,302 original rows preserved unchanged in repaired.
EXTENSION: CONFIRMED. 2026 fully covered through 2026-04-09 (187 games).
PRODUCTION: PROMOTED. Staging verified before promotion. Backups retained.
