#!/usr/bin/env python3
"""S40: team_ratings + goalie_ratings + F(D) → engine TeamMultipliers for each game."""
import json, sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from nhl.sim.engine import TeamMultipliers, GameInputs, league_average_inputs

RATINGS_DIR = ROOT / "nhl" / "data" / "sim" / "ratings"
C8_PATH = ROOT / "nhl" / "data" / "sim" / "constants_v8.json"


def load_all():
    tr = pd.read_parquet(RATINGS_DIR / "team_ratings.parquet")
    gr = pd.read_parquet(RATINGS_DIR / "goalie_ratings.parquet")
    ft = pd.read_parquet(RATINGS_DIR / "finishing_term.parquet")
    with open(C8_PATH) as f:
        c8 = json.load(f)
    q = c8["constants"]["q_league_xg_per_non_en_attempt"]["value"]
    return tr, gr, ft, q


def build_team_mult(row, q):
    """Build TeamMultipliers from a team_ratings row. A NaN raises."""
    def r(col):
        v = row[col] / row[f"lg_{col}"]
        if np.isnan(v):
            raise ValueError(f"NaN in {col} for game {row.get('game_id')}, team {row.get('team')}")
        return float(v)
    return TeamMultipliers(
        ev_att_for=r("ev_att_for_per60"),
        ev_att_against=r("ev_att_against_per60"),
        ev_q_for=r("ev_xg_per_att_for"),
        ev_q_against=r("ev_xg_per_att_against"),
        pp_q_for=r("pp_xg_for_per60"),
        pk_q_against=r("pk_xg_against_per60"),
        pen_taken=r("penalties_taken_per60"),
        pen_drawn=r("penalties_drawn_per60"),
    )


def game_inputs_for(game_id, tr, gr, ft, q, base_inputs=None):
    """Build full GameInputs for a specific game. Missing row or NaN raises."""
    if base_inputs is None:
        base_inputs = league_average_inputs()

    h_row = tr[(tr["game_id"] == game_id) & (tr["role"] == "home")]
    a_row = tr[(tr["game_id"] == game_id) & (tr["role"] == "away")]
    if len(h_row) == 0 or len(a_row) == 0:
        raise ValueError(f"No team_ratings row for game {game_id}")
    h_row, a_row = h_row.iloc[0], a_row.iloc[0]

    # Check for NaN in key columns
    for row, label in [(h_row, "home"), (a_row, "away")]:
        for col in ["ev_att_for_per60", "lg_ev_att_for_per60"]:
            if col in row.index and np.isnan(row[col]):
                raise ValueError(f"NaN in {col} for game {game_id} {label}")

    h_mult = build_team_mult(h_row, q)
    a_mult = build_team_mult(a_row, q)

    # Goalie
    h_gr = gr[(gr["game_id"] == game_id) & (gr["role"] == "home")]
    a_gr = gr[(gr["game_id"] == game_id) & (gr["role"] == "away")]
    if len(h_gr) == 0 or len(a_gr) == 0:
        raise ValueError(f"No goalie_ratings row for game {game_id}")

    h_gsax = h_gr.iloc[0]["gsax_per_att_rating"]
    a_gsax = a_gr.iloc[0]["gsax_per_att_rating"]
    h_mult.goalie_save = 1.0 - a_gsax / q  # opponent's goalie
    a_mult.goalie_save = 1.0 - h_gsax / q

    # Finishing term
    date = h_row["date"]
    ft_row = ft[ft["date"] == date]
    if len(ft_row) == 0 or np.isnan(ft_row.iloc[0]["F"]):
        raise ValueError(f"No finishing term for date {date}")
    F = float(ft_row.iloc[0]["F"])
    h_mult.finishing = F
    a_mult.finishing = F

    import copy
    inp = copy.deepcopy(base_inputs)
    inp.home = h_mult
    inp.away = a_mult
    return inp


if __name__ == "__main__":
    tr, gr, ft, q = load_all()
    print(f"q = {q:.6f}")
    # Test: build inputs for a 2022-23 game
    gid = "2022020100"
    try:
        inp = game_inputs_for(gid, tr, gr, ft, q)
        print(f"Game {gid}: home ev_att_for={inp.home.ev_att_for:.3f}, goalie_save={inp.home.goalie_save:.3f}")
    except Exception as e:
        print(f"Error: {e}")
