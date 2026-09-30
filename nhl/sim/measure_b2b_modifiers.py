#!/usr/bin/env python3
"""S47 generator: B2B and backup goalie modifiers estimated on 2022-23.

Poisson regression of each team's actual goals on log(engine expected goals) as offset,
plus: own_b2b, opp_b2b, own_backup, opp_backup.

The per-team offset uses mean_home_goals / mean_away_goals from the prices.

Usage:
  python3 nhl/sim/measure_b2b_modifiers.py [--prices nhl/data/sim/prices/season=2022.parquet]
"""
import json, sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

BOX_DIR = ROOT / "nhl" / "cache"
GAMES_PER = 1312
GOALIE_STARTS = ROOT / "research" / "nhl_sim" / "edge_hunt_2026-09-30" / "inputs" / "nhl_goalie_starts.csv"


def load_actuals_goals(season):
    """Load actual goals per team per game (regulation + OT, no shootout goal)."""
    rows = []
    for i in range(1, GAMES_PER + 1):
        gid = f"{season}02{i:04d}"
        bp = BOX_DIR / f"boxscore_{gid}.json"
        if not bp.exists():
            continue
        with open(bp) as f:
            d = json.load(f)
        hs, as_ = d["homeTeam"]["score"], d["awayTeam"]["score"]
        outcome = d.get("gameOutcome", {}).get("lastPeriodType", "REG")
        # Remove shootout goal
        if outcome == "SO":
            if hs > as_:
                hs -= 1
            else:
                as_ -= 1
        h, a = d["homeTeam"]["abbrev"], d["awayTeam"]["abbrev"]
        date = d.get("gameDate", "")
        rows.append({"game_id": gid, "home": h, "away": a, "date": date,
                      "h_goals": hs, "a_goals": as_})
    return pd.DataFrame(rows)


def b2b_flags(act):
    """Mark back-to-back games for each team."""
    # Sort by date to detect B2B
    dates = {}  # team -> list of (date, game_id)
    for _, r in act.iterrows():
        for team_col, role in [("home", "home"), ("away", "away")]:
            team = r[team_col]
            if team not in dates:
                dates[team] = []
            dates[team].append((r["date"], r["game_id"], role))
    b2b = {}
    for team, games in dates.items():
        games.sort()
        for j, (d, gid, role) in enumerate(games):
            if j > 0 and d:
                prev_d = games[j - 1][0]
                if prev_d and d:
                    from datetime import date as _date
                    try:
                        delta = (_date.fromisoformat(d[:10]) - _date.fromisoformat(prev_d[:10])).days
                        b2b[(gid, team)] = delta == 1
                    except Exception:
                        b2b[(gid, team)] = False
                else:
                    b2b[(gid, team)] = False
            else:
                b2b[(gid, team)] = False
    return b2b


def backup_flags(season):
    """Identify backup starts: starting goalie != team's most-used starter before the date."""
    if not GOALIE_STARTS.exists():
        print(f"Warning: {GOALIE_STARTS} not found; backup flags will be all False")
        return {}
    gs = pd.read_csv(GOALIE_STARTS)
    gs = gs[(gs["started"] == 1) & (gs["season"] == season)].sort_values(["date", "game_id"])
    result = {}
    for (tm, se), x in gs.groupby(["team", "season"], sort=False):
        cnt = {}
        for r in x.itertuples(index=False):
            prim = max(cnt, key=cnt.get) if cnt else None
            result[(r.game_id, tm)] = prim is not None and r.goalie_id != prim
            cnt[r.goalie_id] = cnt.get(r.goalie_id, 0) + 1
    return result


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--prices", default=str(ROOT / "nhl" / "data" / "sim" / "prices" / "season=2022.parquet"))
    args = ap.parse_args()

    season = 2022
    act = load_actuals_goals(season)
    prices = pd.read_parquet(args.prices)
    prices["game_id"] = prices["game_id"].astype(str)
    act["game_id"] = act["game_id"].astype(str)

    # Merge to get engine expected goals
    m = act.merge(prices[["game_id", "mean_home_goals", "mean_away_goals"]], on="game_id")
    b2b = b2b_flags(act)
    bk = backup_flags(season)

    # Build per-team rows (each game contributes 2 rows: one home, one away)
    rows = []
    for _, r in m.iterrows():
        for role in ["home", "away"]:
            team = r[role]
            opp = r["away"] if role == "home" else r["home"]
            goals = r["h_goals"] if role == "home" else r["a_goals"]
            expected = r["mean_home_goals"] if role == "home" else r["mean_away_goals"]
            own_b2b = b2b.get((r["game_id"], team), False)
            opp_b2b = b2b.get((r["game_id"], opp), False)
            own_bk = bk.get((int(r["game_id"]), team), False)
            opp_bk = bk.get((int(r["game_id"]), opp), False)
            rows.append({
                "goals": goals,
                "log_expected": np.log(max(expected, 0.1)),
                "own_b2b": int(own_b2b),
                "opp_b2b": int(opp_b2b),
                "own_backup": int(own_bk),
                "opp_backup": int(opp_bk),
            })
    df = pd.DataFrame(rows)

    # Poisson regression with log(expected) as offset
    y = df["goals"]
    X = df[["own_b2b", "opp_b2b", "own_backup", "opp_backup"]]
    X = sm.add_constant(X)
    model = sm.GLM(y, X, family=sm.families.Poisson(), offset=df["log_expected"])
    result = model.fit()
    print(f"Poisson regression on 2022-23 ({len(df)} team-games):\n")
    for name, coef, se, pval in zip(result.params.index[1:], result.params[1:], result.bse[1:], result.pvalues[1:]):
        mult = np.exp(coef)
        print(f"  {name}: coef={coef:.3f} (SE {se:.3f}, p={pval:.3f}, mult {mult:.3f})")


if __name__ == "__main__":
    main()
