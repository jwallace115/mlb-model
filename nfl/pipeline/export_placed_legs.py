#!/usr/bin/env python3
"""Export the legs actually PLACED on a slate as a grade_week.py `--extra` file.

The sim's grader (nfl/sim/grade_week.py + actuals.py) is the repo's single source of truth for
player-game outcomes and already grades receptions, rush attempts, pass completions and pass
attempts on both sides. This script only reshapes the placement entries of
nfl/data/board/nfl_prop_tickets_2026.json into its canonical columns and resolves player ids
with the same resolver the board uses. It prices nothing and reads no outcome.

Usage: python3 nfl/pipeline/export_placed_legs.py --season 2026 --week 2 --slate 2026-09-20d
Writes: nfl/data/board/week=<S>_<WW>/placed_legs_<slate>.parquet
"""
import argparse, json, sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from nfl.sim.names import load_roster, _build_roster_lookup, resolve_player, FULL_TO_ABBR  # noqa: E402

FAMILY = {"player_receptions": "receptions", "player_rush_attempts": "rush_attempts",
          "player_pass_completions": "pass_completions", "player_pass_attempts": "pass_attempts"}


def placed_rows(log_path, slate):
    ents = json.loads(Path(log_path).read_text())
    ents = ents if isinstance(ents, list) else ents.get("entries", [])
    rows = []
    for e in ents:
        if e.get("slate") == slate and "legs_placed" in e:
            for l in e["legs_placed"]:
                rows.append({"ticket": f"{slate}:{e['ticket_id']}", **l})   # slate-qualified: ids repeat across slates
    return pd.DataFrame(rows)


def export(season, week, slate, log_path=None, cand_path=None, roster=None):
    wk_dir = ROOT / "nfl" / "data" / "board" / f"week={season}_{week:02d}"
    log_path = log_path or ROOT / "nfl" / "data" / "board" / "nfl_prop_tickets_2026.json"
    t = placed_rows(log_path, slate)
    if t.empty:
        raise SystemExit(f"HALT: no placement entries for slate {slate}")
    bad = sorted(set(t["market_key"]) - set(FAMILY))
    if bad:
        raise SystemExit(f"HALT: market with no grader family: {bad}")
    # a slate's players may be missing from a LATER candidates file (a narrower pull window), so
    # look across every candidates file of the week, newest first
    files = [cand_path] if cand_path else sorted(wk_dir.glob("nfl_prop_candidates_*.parquet"), reverse=True)
    cols = ["player_name", "market_key", "team", "home_team", "away_team", "position", "pull_timestamp"]
    c = pd.concat([pd.read_parquet(f)[cols] for f in files], ignore_index=True).drop_duplicates(
        ["player_name", "market_key"], keep="first")
    t = t.merge(c, on=["player_name", "market_key"], how="left")
    if t["home_team"].isna().any():
        raise SystemExit(f"HALT: placed leg not in candidates: {t.loc[t.home_team.isna(), 'player_name'].tolist()}")
    roster = load_roster() if roster is None else roster
    lk = _build_roster_lookup(roster, season, week)
    out = []
    for _, r in t.iterrows():
        home, away = FULL_TO_ABBR.get(r["home_team"], r["home_team"]), FULL_TO_ABBR.get(r["away_team"], r["away_team"])
        teams = [r["team"]] if isinstance(r["team"], str) else [home, away]
        pid, method = resolve_player(r["player_name"], season, week, teams, *lk)
        out.append({"season": season, "week": week, "game_id": f"{away}@{home}", "home": home,
                    "away": away, "player_id": pid, "player_name": r["player_name"],
                    "position": r["position"], "family": FAMILY[r["market_key"]],
                    "line": float(r["line"]), "side": str(r["side"]).lower(),
                    "sim_p": None, "cal_p": None, "tier": "placed", "book_price": r.get("american"),
                    "book_implied": None, "one_sided": False, "pull_batch": "placed_slip",
                    "pull_timestamp": r["pull_timestamp"], "board_generated_utc": None,
                    "status": "bet", "ticket": r["ticket"], "resolve_method": method})
    df = pd.DataFrame(out)
    dest = wk_dir / f"placed_legs_{slate}.parquet"
    df.to_parquet(dest, index=False)
    return df, dest


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--slate", required=True)
    a = ap.parse_args()
    df, dest = export(a.season, a.week, a.slate)
    print(df[["ticket", "player_name", "family", "side", "line", "player_id", "resolve_method"]].to_string())
    print(f"\n{len(df)} legs, unresolved: {(df.player_id.isna()).sum()} -> {dest.relative_to(ROOT)}")
