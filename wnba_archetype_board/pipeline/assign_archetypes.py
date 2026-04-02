#!/usr/bin/env python3
"""
WNBA Archetype Board — Archetype Assignment Pipeline
=====================================================
Assigns season and rolling-state archetypes to teams for each game.
Uses frozen cluster definitions from research — no re-clustering.

Safeguards:
  1. Rolling-state archetype requires >= 8 prior games in season.
     Falls back to season archetype if insufficient history.
  2. Expansion teams (GSV for 2025+) are flagged separately
     in all signal tracking outputs.
"""

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

# ── Configuration ────────────────────────────────────────────────────────────

MIN_GAMES_FOR_STATE = 8  # Minimum prior games before rolling-state is valid

# Expansion teams: teams with no archetype training history.
# GSV (Golden State Valkyries) — new franchise in 2025.
# PHX is Phoenix rebranded from PHO — NOT expansion, has history under PHO.
EXPANSION_TEAMS = {"GSV"}

# PHO → PHX rebrand mapping (same franchise, different abbreviation)
REBRAND_MAP = {"PHX": "PHO"}  # Map current abbrev → historical abbrev for lookups

BOARD_ROOT = PROJECT_ROOT / "wnba_archetype_board"
CONFIG_DIR = BOARD_ROOT / "config"
DATA_DIR = BOARD_ROOT / "data"


def load_frozen_assignments():
    """Load frozen season and state archetype assignments from research."""
    season_clusters = pd.read_parquet(
        PROJECT_ROOT / "research/wnba/archetypes/team_season_clusters.parquet"
    )
    state_clusters = pd.read_parquet(
        PROJECT_ROOT / "research/wnba/archetypes/team_game_state_clusters.parquet"
    )
    signal_registry = json.load(open(CONFIG_DIR / "archetype_signal_registry.json"))
    return season_clusters, state_clusters, signal_registry


def assign_season_archetype(team, season, season_clusters):
    """Look up season archetype for a team.

    Handles PHX→PHO rebrand and expansion team flagging.
    Returns (archetype_name, is_expansion).
    """
    lookup_team = REBRAND_MAP.get(team, team)

    if team in EXPANSION_TEAMS:
        return None, True

    match = season_clusters[
        (season_clusters["team"] == lookup_team) & (season_clusters["season"] == season)
    ]
    if len(match) > 0:
        return match.iloc[0]["cluster_name"], False

    # Try most recent prior season
    prior = season_clusters[
        (season_clusters["team"] == lookup_team) & (season_clusters["season"] < season)
    ].sort_values("season", ascending=False)
    if len(prior) > 0:
        return prior.iloc[0]["cluster_name"], False

    return None, team in EXPANSION_TEAMS


def assign_state_archetype(team, game_id, game_date, season, state_clusters, game_index):
    """Look up rolling-state archetype for a team at a specific game.

    SAFEGUARD 1: Requires >= MIN_GAMES_FOR_STATE prior games in current season.
    Returns (archetype_name, source_label).
      source_label: "STATE" if rolling state used, "SEASON_ONLY" if fallback.
    """
    lookup_team = REBRAND_MAP.get(team, team)

    if team in EXPANSION_TEAMS:
        return None, "EXPANSION"

    # Count prior games this season
    team_games = game_index[
        (game_index["season"] == season)
        & (game_index["game_date"] < game_date)
        & (
            (game_index["home_team_abbreviation"] == team)
            | (game_index["away_team_abbreviation"] == team)
            | (game_index["home_team_abbreviation"] == lookup_team)
            | (game_index["away_team_abbreviation"] == lookup_team)
        )
    ]
    games_played = len(team_games)

    if games_played < MIN_GAMES_FOR_STATE:
        return None, "SEASON_ONLY"

    # Find most recent prior state assignment
    prior_states = state_clusters[
        (state_clusters["team"] == lookup_team)
        & (state_clusters["game_date"] < game_date)
    ].sort_values("game_date", ascending=False)

    if len(prior_states) > 0:
        return prior_states.iloc[0]["cluster_name"], "STATE"

    return None, "SEASON_ONLY"


def detect_signals(home_season, away_season, home_state, away_state, registry):
    """Match game archetypes against frozen signal registry."""
    matched = []
    for sig in registry:
        mode = sig["archetype_mode"]
        key = sig["matchup_key"]

        if mode == "SEASON":
            if home_season and away_season:
                game_key = f"{home_season}_vs_{away_season}"
                if game_key == key:
                    matched.append(sig)
        elif mode == "STATE":
            if home_state and away_state:
                game_key = f"{home_state}_vs_{away_state}"
                if game_key == key:
                    matched.append(sig)

    return matched


def run():
    """Main assignment pipeline."""
    print("WNBA Archetype Assignment Pipeline")
    print("=" * 50)

    season_clusters, state_clusters, registry = load_frozen_assignments()

    gi = pd.read_parquet(PROJECT_ROOT / "wnba/data/game_index.parquet")
    gi["game_id"] = gi["game_id"].astype(str).str.split(".").str[0]

    print(f"Season clusters: {season_clusters.shape}")
    print(f"State clusters: {state_clusters.shape}")
    print(f"Signals in registry: {len(registry)}")
    print(f"Expansion teams: {EXPANSION_TEAMS}")
    print(f"Min games for state: {MIN_GAMES_FOR_STATE}")

    # Process each game
    n_season_only = 0
    n_expansion = 0
    n_state_used = 0
    n_signals = 0

    results = []
    for _, game in gi.iterrows():
        gid = game["game_id"]
        gdate = game["game_date"]
        season = game["season"]
        home = game["home_team_abbreviation"]
        away = game["away_team_abbreviation"]

        # Season archetypes
        h_season, h_exp = assign_season_archetype(home, season, season_clusters)
        a_season, a_exp = assign_season_archetype(away, season, season_clusters)

        # State archetypes (with safeguard)
        h_state, h_src = assign_state_archetype(home, gid, gdate, season, state_clusters, gi)
        a_state, a_src = assign_state_archetype(away, gid, gdate, season, state_clusters, gi)

        # Track safeguard counts
        if h_src == "SEASON_ONLY" or a_src == "SEASON_ONLY":
            n_season_only += 1
        if h_src == "EXPANSION" or a_src == "EXPANSION":
            n_expansion += 1
        if h_src == "STATE" and a_src == "STATE":
            n_state_used += 1

        # Detect signals
        matched = detect_signals(h_season, a_season, h_state, a_state, registry)
        expansion_game = h_exp or a_exp
        exp_team = home if h_exp else (away if a_exp else None)

        if matched:
            n_signals += len(matched)

        results.append({
            "game_id": gid,
            "game_date": gdate,
            "season": season,
            "home_team": home,
            "away_team": away,
            "home_season_archetype": h_season,
            "away_season_archetype": a_season,
            "home_state_archetype": h_state,
            "away_state_archetype": a_state,
            "home_state_source": h_src,
            "away_state_source": a_src,
            "n_matched_signals": len(matched),
            "expansion_game": expansion_game,
            "expansion_team": exp_team,
        })

    df = pd.DataFrame(results)

    print(f"\nResults:")
    print(f"  Total games processed: {len(df)}")
    print(f"  Games with signals: {(df['n_matched_signals'] > 0).sum()}")
    print(f"  Season-only fallback (< {MIN_GAMES_FOR_STATE} games): {n_season_only}")
    print(f"  Expansion team games: {n_expansion}")
    print(f"  Games with full state archetypes: {n_state_used}")
    print(f"  Total signal matches: {n_signals}")

    # Season archetype distribution
    print(f"\n  Season archetype distribution:")
    for arch in sorted(df["home_season_archetype"].dropna().unique()):
        n = ((df["home_season_archetype"] == arch) | (df["away_season_archetype"] == arch)).sum()
        print(f"    {arch}: {n} team-game appearances")

    return df


if __name__ == "__main__":
    run()
