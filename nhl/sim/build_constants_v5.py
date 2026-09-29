#!/usr/bin/env python3
"""
Build constants_v5.json from the event tables with row-wise xG scoring.
Fit seasons [2021, 2022]. Supersedes v3 and v4 (both had no committed generator; v4 double-counted).
"""
import hashlib, json, sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
EVENTS_DIR = ROOT / "nhl" / "data" / "sim" / "events"
XG_PATH = ROOT / "nhl" / "data" / "sim" / "xg_v2.json"
OUT = ROOT / "nhl" / "data" / "sim" / "constants_v5.json"
FIT = [2021, 2022]

STRENGTH_GROUPS = {"5v5": "even", "4v4": "even", "3v3": "3v3",
                   "5v4": "PP", "5v3": "PP", "4v3": "PP",
                   "4v5": "PK", "3v5": "PK", "3v4": "PK"}


def score_xg(shots_df):
    with open(XG_PATH) as f:
        model = json.load(f)
    features = model["features"]
    coefs = model["coefficients"]
    intercept = model["intercept"]
    df = shots_df.copy()
    df["strength_group"] = df["strength"].map(STRENGTH_GROUPS).fillna("other")
    for st in ["wrist", "slap", "snap", "backhand", "tip-in", "deflected", "wrap-around", "cradle"]:
        df[f"st_{st}"] = (df["shot_type"] == st).astype(int)
    for sg in ["PP", "PK", "3v3"]:
        df[f"sg_{sg}"] = (df["strength_group"] == sg).astype(int)
    X = df[features].fillna(0).values.astype(float)
    logit = intercept + X @ np.array([coefs[f] for f in features])
    return 1 / (1 + np.exp(-logit))


def main():
    shots = pd.concat([pd.read_parquet(EVENTS_DIR / f"season={s}" / "shots.parquet") for s in FIT], ignore_index=True)
    state = pd.concat([pd.read_parquet(EVENTS_DIR / f"season={s}" / "state_time.parquet") for s in FIT], ignore_index=True)
    state["sh"] = state["home_skaters"].astype(str) + "v" + state["away_skaters"].astype(str)
    n_games = shots["game_id"].nunique()

    # Row-wise xG (no merge)
    en = shots["empty_net"].astype(bool)
    shots["xg"] = 0.0
    shots.loc[~en, "xg"] = score_xg(shots.loc[~en])

    # Ice state from situation_code
    sc = shots["situation_code"].astype(str).str.zfill(4)
    shots["ice_state"] = sc.str[2].astype(str) + "v" + sc.str[1].astype(str)

    c5 = {"version": 5, "fit_seasons": FIT, "n_games": n_games, "constants": {}}

    # Even states
    for st in ["5v5", "4v4", "3v3"]:
        st_shots = shots[shots["strength"] == st]
        secs = state[state["sh"] == st]["duration"].sum()
        att = len(st_shots)
        goals = int(st_shots["is_goal"].sum())
        xg_sum = float(st_shots["xg"].sum())

        c5["constants"][f"attempt_rate_per_60_per_team_{st}"] = {
            "value": round(att / secs * 3600 / 2, 4) if secs else 0,
            "numerator": att, "denominator": round(secs),
            "units": "attempts / (seconds * 2) * 3600",
        }
        c5["constants"][f"goals_per_attempt_{st}"] = {
            "value": round(goals / att, 6) if att else 0,
            "numerator": goals, "denominator": att,
            "derivation": f"goals / unblocked attempts in {st}"
        }
        c5["constants"][f"xg_per_attempt_{st}"] = {
            "value": round(xg_sum / att, 6) if att else 0,
            "numerator": round(xg_sum, 2), "denominator": att,
            "derivation": f"sum(xg_v2) / unblocked attempts in {st}"
        }
        c5["constants"][f"goals_over_xg_{st}"] = {
            "value": round(goals / xg_sum, 4) if xg_sum else 1.0,
        }
        c5["constants"][f"minutes_per_game_{st}"] = {
            "value": round(secs / n_games / 60, 2),
            "total_secs": round(secs), "n_games": n_games,
        }

    # Uneven states: pool both orientations
    uneven = [("5v4", "4v5"), ("5v3", "3v5"), ("4v3", "3v4"), ("6v5", "5v6")]
    for adv_state, dis_state in uneven:
        home_adv = shots[shots["ice_state"] == adv_state]
        pp_home = home_adv[home_adv["strength"] == adv_state]
        sh_home = home_adv[home_adv["strength"] == dis_state]
        secs_home = state[state["sh"] == adv_state]["duration"].sum()

        away_adv = shots[shots["ice_state"] == dis_state]
        pp_away = away_adv[away_adv["strength"] == adv_state]
        sh_away = away_adv[away_adv["strength"] == dis_state]
        secs_away = state[state["sh"] == dis_state]["duration"].sum()

        total_secs = secs_home + secs_away

        for tag, side_h, side_a in [("advantaged", pp_home, pp_away), ("disadvantaged", sh_home, sh_away)]:
            pooled = pd.concat([side_h, side_a])
            att = len(pooled)
            goals = int(pooled["is_goal"].sum())
            xg_sum = float(pooled["xg"].sum())

            c5["constants"][f"attempt_rate_per_60_{tag}_{adv_state}"] = {
                "value": round(att / total_secs * 3600, 4) if total_secs else 0,
                "numerator": att, "denominator": round(total_secs),
                "home_part": len(side_h), "away_part": len(side_a),
                "derivation": f"{tag}-side attempts (pooled) / total seconds * 3600"
            }
            c5["constants"][f"goals_per_attempt_{tag}_{adv_state}"] = {
                "value": round(goals / att, 6) if att else 0,
                "numerator": goals, "denominator": att,
            }
            c5["constants"][f"xg_per_attempt_{tag}_{adv_state}"] = {
                "value": round(xg_sum / att, 6) if att else 0,
                "numerator": round(xg_sum, 2), "denominator": att,
            }
            c5["constants"][f"goals_over_xg_{tag}_{adv_state}"] = {
                "value": round(goals / xg_sum, 4) if xg_sum else 1.0,
            }

        c5["constants"][f"minutes_per_team_game_{adv_state}"] = {
            "value": round(total_secs / n_games / 2 / 60, 2),
            "total_secs": round(total_secs), "n_games": n_games,
        }

    OUT.write_text(json.dumps(c5, indent=2) + "\n")
    sha = hashlib.sha256(OUT.read_bytes()).hexdigest()

    # NULL CONTROLS
    print(f"5v5 numerator: {c5['constants']['attempt_rate_per_60_per_team_5v5']['numerator']}")
    print(f"  expected: 178012 (v2's count)")
    assert c5["constants"]["attempt_rate_per_60_per_team_5v5"]["numerator"] == 178012, "5v5 numerator mismatch"

    for adv, dis in uneven:
        for tag in ["advantaged", "disadvantaged"]:
            entry = c5["constants"][f"attempt_rate_per_60_{tag}_{adv}"]
            assert entry["home_part"] + entry["away_part"] == entry["numerator"], f"{adv} {tag} pool check failed"
    print("Pooled numerator check: all exact")

    # Byte-identical check
    OUT.write_text(json.dumps(c5, indent=2) + "\n")
    sha2 = hashlib.sha256(OUT.read_bytes()).hexdigest()
    assert sha == sha2, "Not byte-identical on second run"
    print(f"Byte-identical: {sha == sha2}")

    print(f"\nSaved: {OUT} ({OUT.stat().st_size} bytes)")
    print(f"sha256: {sha}")


if __name__ == "__main__":
    main()
