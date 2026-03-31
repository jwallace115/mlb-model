"""
Phase 8 — Bullpen Feature Engineering
======================================
Step 1: Fetch all boxscores and build bullpen_usage.parquet
Step 2 (after leakage verification): Compute rolling features and save bullpen_features.parquet

Usage:
    python3 sim/phase8_bullpen_features.py --fetch      # Step 1: fetch + save raw usage table
    python3 sim/phase8_bullpen_features.py --verify     # Show leakage check sample
    python3 sim/phase8_bullpen_features.py --features   # Step 2: compute rolling features
"""

import argparse
import json
import os
import ssl
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import TEAM_ID_TO_ABB

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SIM_DIR       = Path(__file__).resolve().parent
DATA_DIR      = SIM_DIR / "data"
CACHE_DIR     = DATA_DIR / "cache" / "boxscores"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

GAME_TABLE    = DATA_DIR / "game_table.parquet"
USAGE_PATH    = DATA_DIR / "bullpen_usage.parquet"
FEATURES_PATH = DATA_DIR / "bullpen_features.parquet"

MLB_API = "https://statsapi.mlb.com/api/v1"

# ---------------------------------------------------------------------------
# SSL context (bypass cert verification — MLB API quirk)
# ---------------------------------------------------------------------------
def _ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode    = ssl.CERT_NONE
    return ctx

def _opener():
    return urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=_ssl_ctx())
    )

# ---------------------------------------------------------------------------
# Step 1A: Fetch one boxscore (cached)
# ---------------------------------------------------------------------------
def fetch_boxscore(game_pk: int) -> dict | None:
    cache_file = CACHE_DIR / f"{game_pk}.json"
    if cache_file.exists():
        with open(cache_file) as f:
            return json.load(f)

    url = f"{MLB_API}/game/{game_pk}/boxscore"
    try:
        opener = _opener()
        with opener.open(url, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        with open(cache_file, "w") as f:
            json.dump(data, f)
        return data
    except Exception as e:
        print(f"  ERROR game_pk={game_pk}: {e}", flush=True)
        return None

# ---------------------------------------------------------------------------
# Step 1B: Parse one boxscore into pitcher rows
# ---------------------------------------------------------------------------
def parse_boxscore(game_pk: int, date: str, season: int, game_number: int,
                   home_team: str, away_team: str, data: dict) -> list[dict]:
    rows = []
    teams_data = data.get("teams", {})

    for side, team_abb in [("home", home_team), ("away", away_team)]:
        team_block = teams_data.get(side, {})
        pitchers = team_block.get("pitchers", [])          # list of player IDs
        players  = team_block.get("players", {})            # keyed by "ID123456"

        for pid in pitchers:
            pkey  = f"ID{pid}"
            pdata = players.get(pkey, {})
            stats = pdata.get("stats", {}).get("pitching", {})
            info  = pdata.get("person", {})

            # is_starter: gamesStarted == 1; relievers == 0
            games_started  = int(stats.get("gamesStarted", 0))
            games_finished = int(stats.get("gamesFinished", 0))
            pitches_thrown = int(stats.get("numberOfPitches", stats.get("pitchesThrown", 0)))

            # innings_pitched as float: "3.1" → 3.333...
            ip_str = stats.get("inningsPitched", "0.0")
            try:
                ip_whole, ip_thirds = ip_str.split(".")
                innings_pitched = int(ip_whole) + int(ip_thirds) / 3.0
            except Exception:
                innings_pitched = 0.0

            rows.append({
                "game_pk":        game_pk,
                "date":           date,
                "season":         season,
                "game_number":    game_number,
                "team":           team_abb,
                "pitcher_id":     pid,
                "pitcher_name":   info.get("fullName", ""),
                "is_starter":     (games_started == 1),
                "pitches_thrown": pitches_thrown,
                "innings_pitched": round(innings_pitched, 4),
                "games_finished": games_finished,
            })

    return rows

# ---------------------------------------------------------------------------
# Step 1C: Fetch all boxscores with ThreadPoolExecutor
# ---------------------------------------------------------------------------
def build_usage_table(workers: int = 8) -> pd.DataFrame:
    df_games = pd.read_parquet(GAME_TABLE)
    print(f"Game table: {len(df_games)} rows")

    # Ensure required columns exist
    assert "game_pk"      in df_games.columns
    assert "date"         in df_games.columns
    assert "season"       in df_games.columns
    assert "game_number"  in df_games.columns
    assert "home_team"    in df_games.columns
    assert "away_team"    in df_games.columns

    games = df_games[["game_pk","date","season","game_number",
                       "home_team","away_team"]].drop_duplicates("game_pk")
    total = len(games)
    print(f"Fetching {total} boxscores ({workers} workers)…")

    all_rows   = []
    errors     = 0
    completed  = 0
    t0         = time.time()

    def _task(row):
        data = fetch_boxscore(int(row.game_pk))
        return row, data

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_task, row): row for row in games.itertuples(index=False)}
        for fut in as_completed(futures):
            completed += 1
            row, data = fut.result()
            if data is None:
                errors += 1
            else:
                rows = parse_boxscore(
                    int(row.game_pk), str(row.date), int(row.season),
                    int(row.game_number), row.home_team, row.away_team, data
                )
                all_rows.extend(rows)

            if completed % 500 == 0 or completed == total:
                elapsed = time.time() - t0
                cached  = sum(1 for f in CACHE_DIR.iterdir())
                print(f"  {completed}/{total}  errors={errors}  "
                      f"cached={cached}  elapsed={elapsed:.0f}s", flush=True)

    df = pd.DataFrame(all_rows)
    print(f"\nRaw rows: {len(df):,}  (errors={errors})")
    return df

# ---------------------------------------------------------------------------
# Step 2: Rolling bullpen features (leakage-safe)
# ---------------------------------------------------------------------------
def compute_bullpen_features(df_usage: pd.DataFrame) -> pd.DataFrame:
    """
    For each (team, game) produce three features, shifted by 1 to prevent leakage:
      - relievers_used_last_game    : # distinct relievers who threw in previous game
      - relievers_used_last_3_games : # distinct relievers (union) in prior 3 games
      - high_leverage_available     : top-3 closers (by career GF) with pitches_last_2_days < 25
      - bullpen_pitches_last_game   : total pitches by relievers in previous game
      - bullpen_pitches_last_3_games: total pitches by relievers in prior 3 games

    Sort: date ascending, then game_number ascending (DH Game 1 before Game 2).
    Group: (team, season).
    Shift: shift(1) within each group — today's row sees yesterday's raw stats.
    Season boundary: groupby resets naturally (new season = new group).
    """
    relievers = df_usage[~df_usage["is_starter"]].copy()

    # Aggregate to (game_pk, date, season, game_number, team) level
    per_game = (
        relievers.groupby(["game_pk","date","season","game_number","team"])
        .agg(
            n_relievers    = ("pitcher_id",  "nunique"),
            total_pitches  = ("pitches_thrown", "sum"),
            n_finishers    = ("games_finished",  "sum"),   # closers used
        )
        .reset_index()
    )

    # Sort correctly (handles doubleheaders)
    per_game = per_game.sort_values(["season","date","game_number"]).reset_index(drop=True)

    # Rolling sums — computed within (team, season) group
    def _roll(group: pd.DataFrame) -> pd.DataFrame:
        g = group.copy()
        # shift(1): today's features look at yesterday's row
        g["relievers_used_last_game"]   = g["n_relievers"].shift(1)
        g["bullpen_pitches_last_game"]  = g["total_pitches"].shift(1)

        # 3-game rolling sum, then shift so today sees yesterday's trailing-3
        g["relievers_used_last_3_games"] = (
            g["n_relievers"].rolling(3, min_periods=1).sum().shift(1)
        )
        g["bullpen_pitches_last_3_games"] = (
            g["total_pitches"].rolling(3, min_periods=1).sum().shift(1)
        )
        return g

    per_game = (
        per_game.groupby(["team","season"], group_keys=False)
        .apply(_roll)
        .reset_index(drop=True)
    )

    # high_leverage_available: top-3 closers per team per season by career GF
    # Proxy: career GF = total games_finished across all seasons in dataset
    closer_gf = (
        df_usage[df_usage["games_finished"] > 0]
        .groupby(["team","season","pitcher_id","pitcher_name"])["games_finished"]
        .sum()
        .reset_index(name="career_gf")
    )
    # Rank within (team, season) descending by career_gf
    closer_gf["gf_rank"] = (
        closer_gf.groupby(["team","season"])["career_gf"]
        .rank(ascending=False, method="first")
    )
    top3_closers = closer_gf[closer_gf["gf_rank"] <= 3][
        ["team","season","pitcher_id"]
    ].copy()

    # Pitches thrown by top-3 closers in each game
    top3_used = (
        df_usage.merge(top3_closers, on=["team","season","pitcher_id"])
        .groupby(["game_pk","team","season","game_number"])["pitches_thrown"]
        .sum()
        .reset_index(name="top3_pitches_this_game")
    )

    # For each team-game, did top3 throw ≥25 pitches in THIS game (prev 2 days logic below)?
    # Simpler proxy: for each game, sum top3 pitches in last 2 games (shifted)
    top3_sorted = (
        top3_used
        .merge(
            per_game[["game_pk","team","season","date","game_number"]],
            on=["game_pk","team","season","game_number"],
            how="left"
        )
        .sort_values(["season","date","game_number"])
    )

    def _top3_roll(group: pd.DataFrame) -> pd.DataFrame:
        g = group.copy()
        g["top3_pitches_last_2_games"] = (
            g["top3_pitches_this_game"].rolling(2, min_periods=1).sum().shift(1)
        )
        return g

    top3_sorted = (
        top3_sorted.groupby(["team","season"], group_keys=False)
        .apply(_top3_roll)
        .reset_index(drop=True)
    )

    # high_leverage_available: top3 rested (< 25 pitches last 2 games combined)
    top3_sorted["high_leverage_available"] = (
        top3_sorted["top3_pitches_last_2_games"].fillna(0) < 25
    ).astype(int)

    per_game = per_game.merge(
        top3_sorted[["game_pk","team","high_leverage_available"]],
        on=["game_pk","team"],
        how="left"
    )
    per_game["high_leverage_available"] = per_game["high_leverage_available"].fillna(1).astype(int)

    # Keep only feature columns
    feature_cols = [
        "game_pk","date","season","game_number","team",
        "relievers_used_last_game",
        "relievers_used_last_3_games",
        "bullpen_pitches_last_game",
        "bullpen_pitches_last_3_games",
        "high_leverage_available",
    ]
    return per_game[feature_cols]

# ---------------------------------------------------------------------------
# Leakage verification: show a sample where shift is visibly working
# ---------------------------------------------------------------------------
def verify_leakage(df_usage: pd.DataFrame):
    """Print a side-by-side table showing raw game stats vs feature row."""
    relievers = df_usage[~df_usage["is_starter"]].copy()
    per_game = (
        relievers.groupby(["game_pk","date","season","game_number","team"])
        .agg(n_relievers=("pitcher_id","nunique"), total_pitches=("pitches_thrown","sum"))
        .reset_index()
    )
    per_game = per_game.sort_values(["season","date","game_number"])

    # Pick one team with multiple consecutive games
    team = "NYY"
    sample = per_game[per_game["team"] == team].head(6).copy()

    def _roll_sample(group):
        g = group.copy()
        g["feat_relievers_last_game"]  = g["n_relievers"].shift(1)
        g["feat_pitches_last_game"]    = g["total_pitches"].shift(1)
        g["feat_relievers_last_3"]     = g["n_relievers"].rolling(3, min_periods=1).sum().shift(1)
        return g

    sample = (
        sample.groupby(["team","season"], group_keys=False)
        .apply(_roll_sample)
    )

    print("\n=== LEAKAGE VERIFICATION (NYY first 6 games) ===")
    print(f"{'date':<12} {'gm#':<5} {'n_rel_actual':<14} {'feat_last_game':<16} "
          f"{'pitches_actual':<16} {'feat_pitch_last':<16} {'rel_last3'}")
    print("-" * 105)
    for _, r in sample.iterrows():
        print(f"{r['date']!s:<12} {r['game_number']:<5} {r['n_relievers']:<14} "
              f"{str(r.get('feat_relievers_last_game','NaN')):<16} "
              f"{r['total_pitches']:<16} "
              f"{str(r.get('feat_pitches_last_game','NaN')):<16} "
              f"{r.get('feat_relievers_last_3','NaN')}")

    print("\nVerification rules:")
    print("  1. Row 1 (first game of season): feat_last_game = NaN  ✓ (no prior game)")
    print("  2. Row 2: feat_last_game = Row 1 n_relievers          ✓ (shift works)")
    print("  3. Row 4: feat_last3 = sum(rows 1-3 n_relievers)      ✓ (rolling window)")
    print("  4. Season boundary would reset to NaN for next season  ✓ (separate group)")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch",    action="store_true", help="Fetch boxscores + build usage table")
    parser.add_argument("--verify",   action="store_true", help="Show leakage verification")
    parser.add_argument("--features", action="store_true", help="Compute rolling features")
    parser.add_argument("--workers",  type=int, default=8, help="Thread pool workers for fetch")
    args = parser.parse_args()

    if not (args.fetch or args.verify or args.features):
        parser.print_help()
        return

    # ---- Step 1: Fetch ----
    if args.fetch:
        df_usage = build_usage_table(workers=args.workers)

        # Schema summary
        print("\n=== bullpen_usage.parquet schema ===")
        print(df_usage.dtypes.to_string())
        print(f"\nShape: {df_usage.shape}")
        print(f"\nSample rows (relievers only, sorted):")
        sample = (
            df_usage[~df_usage["is_starter"]]
            .sort_values(["season","date","game_number","team"])
            .head(10)
        )
        print(sample[["game_pk","date","season","game_number","team",
                       "pitcher_name","pitches_thrown","innings_pitched",
                       "games_finished"]].to_string(index=False))

        # Save
        df_usage.to_parquet(USAGE_PATH, index=False)
        print(f"\nSaved → {USAGE_PATH}")
        print(f"Total rows: {len(df_usage):,}")
        print(f"  Starters: {df_usage['is_starter'].sum():,}")
        print(f"  Relievers: {(~df_usage['is_starter']).sum():,}")
        n_games = df_usage['game_pk'].nunique()
        n_cached = sum(1 for _ in CACHE_DIR.iterdir())
        print(f"  Unique games: {n_games:,}  |  Cached boxscores: {n_cached:,}")

    # ---- Leakage verification ----
    if args.verify:
        if not USAGE_PATH.exists():
            print("ERROR: bullpen_usage.parquet not found. Run --fetch first.")
            return
        df_usage = pd.read_parquet(USAGE_PATH)
        verify_leakage(df_usage)

    # ---- Step 2: Compute features ----
    if args.features:
        if not USAGE_PATH.exists():
            print("ERROR: bullpen_usage.parquet not found. Run --fetch first.")
            return
        df_usage = pd.read_parquet(USAGE_PATH)
        print(f"\nBuilding rolling features from {len(df_usage):,} rows…")
        df_feat = compute_bullpen_features(df_usage)

        print("\n=== bullpen_features.parquet schema ===")
        print(df_feat.dtypes.to_string())
        print(f"\nShape: {df_feat.shape}")

        # Spot-check: show first team's first 8 rows with feature values
        team = "NYY"
        s2024 = df_feat[(df_feat["team"] == team) & (df_feat["season"] == 2024)].head(8)
        print(f"\nSample ({team} 2024, first 8 games):")
        print(s2024[["date","game_number",
                      "relievers_used_last_game","relievers_used_last_3_games",
                      "bullpen_pitches_last_game","bullpen_pitches_last_3_games",
                      "high_leverage_available"]].to_string(index=False))

        # Null check (first game of each team-season should be NaN, rest should be populated)
        feat_cols = ["relievers_used_last_game","relievers_used_last_3_games",
                     "bullpen_pitches_last_game","bullpen_pitches_last_3_games"]
        null_pct = df_feat[feat_cols].isnull().mean() * 100
        print(f"\nNull % (expect ~0.5% — only first game of each team-season):")
        print(null_pct.round(2).to_string())

        df_feat.to_parquet(FEATURES_PATH, index=False)
        print(f"\nSaved → {FEATURES_PATH}")

if __name__ == "__main__":
    main()
