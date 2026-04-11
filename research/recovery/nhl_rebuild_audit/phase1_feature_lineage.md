# Phase 1: Feature Lineage Audit

## Data Sources
The rebuild script reads exactly TWO files:
1. nhl/nhl_games_canonical.csv -- raw game data (6,506 games, 62 columns, seasons 2021-2025)
2. nhl/nhl_market_snapshots.parquet -- closing lines (5,246 games, 13 columns)

## MoneyPuck Contamination Check
The canonical file contains 13 MoneyPuck-derived columns:
- home/away_xgoals, home/away_xgoals_against
- home/away_corsi_pct, home/away_fenwick_pct
- home/away_hd_shots, home/away_hd_shots_against
- moneypuck_available

NONE of these columns are used by the rebuild as model features.

The rebuild references "hd_shots" and "hd_shots_against" ONLY in documentation
strings (lines 77-78, 110, 1156-1157) listing what was deliberately excluded.

## SOG Source Caveat
shots_on_goal in the canonical file originates from MoneyPuck (proven by perfect
correlation: SOG NaN == moneypuck_available=0, 196/196 match).

However, SOG values from MoneyPuck are the same as NHL API boxscore SOG for the
same games -- MoneyPuck simply aggregates NHL official data. The values themselves
are not proprietary analytics. The rebuild trains only on games where SOG is
available (seasons 2021-2024), and handles NaN via dropna() in rolling windows
with shrinkage to league average.

VERDICT: CLEAN -- no MoneyPuck analytics used as features.
