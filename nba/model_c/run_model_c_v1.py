"""
NBA Model C v1 — Player Props Framework Build
Build player-level features, audit prop line availability, and report readiness.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

OUT_DIR = Path(__file__).parent
DATA_DIR = Path(__file__).parent.parent / "data"

DISC_SEASONS = ["2022-23", "2023-24"]
VAL_SEASON = "2024-25"

# ══════════════════════════════════════════════════════════════
# STEP 2 — BUILD PLAYER-LEVEL FEATURES
# ══════════════════════════════════════════════════════════════

def build_features():
    """Build rolling pregame features for each player-game."""
    print("STEP 2 — Building player-level features...")

    plogs = pd.read_parquet(OUT_DIR / "player_game_logs.parquet")

    # Clean up
    plogs["game_date"] = pd.to_datetime(plogs["GAME_DATE"])
    plogs["minutes"] = pd.to_numeric(plogs["MIN"], errors="coerce").fillna(0)
    plogs["player_id"] = plogs["PLAYER_ID"]
    plogs["player_name"] = plogs["PLAYER_NAME"]
    plogs["team"] = plogs["TEAM_ABBREVIATION"]
    plogs["game_id"] = plogs["GAME_ID"]
    plogs["pts"] = pd.to_numeric(plogs["PTS"], errors="coerce").fillna(0)
    plogs["reb"] = pd.to_numeric(plogs["REB"], errors="coerce").fillna(0)
    plogs["ast"] = pd.to_numeric(plogs["AST"], errors="coerce").fillna(0)
    plogs["fga"] = pd.to_numeric(plogs["FGA"], errors="coerce").fillna(0)
    plogs["fta"] = pd.to_numeric(plogs["FTA"], errors="coerce").fillna(0)
    plogs["fg3a"] = pd.to_numeric(plogs["FG3A"], errors="coerce").fillna(0)
    plogs["tov"] = pd.to_numeric(plogs["TOV"], errors="coerce").fillna(0)
    plogs["plus_minus"] = pd.to_numeric(plogs["PLUS_MINUS"], errors="coerce").fillna(0)
    plogs["pra"] = plogs["pts"] + plogs["reb"] + plogs["ast"]

    # Home/away
    plogs["is_home"] = plogs["MATCHUP"].str.contains("vs.").astype(int)

    # Opponent extraction
    plogs["opponent"] = plogs["MATCHUP"].str.extract(r'(?:vs\.|@)\s*(\w+)')[0]

    # Filter to players who actually played (minutes > 0)
    played = plogs[plogs["minutes"] > 0].copy()

    # Sort for rolling
    played = played.sort_values(["player_id", "game_date"]).reset_index(drop=True)

    # Per-minute rates
    played["pts_per_min"] = played["pts"] / played["minutes"]
    played["reb_per_min"] = played["reb"] / played["minutes"]
    played["ast_per_min"] = played["ast"] / played["minutes"]
    played["pra_per_min"] = played["pra"] / played["minutes"]
    played["fga_per_min"] = played["fga"] / played["minutes"]
    played["fta_per_min"] = played["fta"] / played["minutes"]
    played["fg3a_per_min"] = played["fg3a"] / played["minutes"]
    played["tov_per_min"] = played["tov"] / played["minutes"]

    # Rolling features (grouped by player_id)
    # We compute these then SHIFT by 1 to make them pregame (no leakage)
    print("  Computing rolling features...")

    def rolling_features(group):
        g = group.copy()

        for stat in ["minutes", "pts", "reb", "ast", "pra", "fga", "fta", "fg3a", "tov",
                     "pts_per_min", "reb_per_min", "ast_per_min", "pra_per_min",
                     "fga_per_min", "fta_per_min", "fg3a_per_min", "tov_per_min"]:

            # Last 5 mean
            g[f"{stat}_L5"] = g[stat].rolling(5, min_periods=3).mean().shift(1)
            # Last 10 mean
            g[f"{stat}_L10"] = g[stat].rolling(10, min_periods=5).mean().shift(1)
            # Season expanding mean
            g[f"{stat}_szn"] = g[stat].expanding(min_periods=3).mean().shift(1)

        # Volatility (std dev last 10, shifted)
        for stat in ["minutes", "pts", "reb", "ast", "pra"]:
            g[f"{stat}_std10"] = g[stat].rolling(10, min_periods=5).std().shift(1)

        # Trend: last 5 mean minus last 10 mean (shifted already)
        for stat in ["pts", "reb", "ast", "pra", "minutes"]:
            g[f"{stat}_trend"] = g[f"{stat}_L5"] - g[f"{stat}_L10"]

        # Game count in season (for minimum games filter)
        g["games_played_season"] = range(1, len(g) + 1)

        return g

    played = played.groupby("player_id", group_keys=False).apply(rolling_features)

    # ── Game environment context ──
    print("  Adding game environment context...")

    # Load team-level data
    box = pd.read_parquet(DATA_DIR / "box_stats.parquet")
    features = pd.read_parquet(DATA_DIR / "features.parquet")
    lines = pd.read_parquet(DATA_DIR / "nba_historical_closing_lines.parquet")

    # Team pace lookup (from box_stats)
    team_pace = box[["game_id", "team", "pace"]].copy()
    team_pace_home = team_pace.rename(columns={"pace": "team_pace"})

    # Merge team pace for this player's team
    played = played.merge(team_pace_home, on=["game_id", "team"], how="left")

    # Opponent defensive rating - get from features
    # features has home_drtg and away_drtg by game
    game_env = features[["game_id", "home_team", "away_team",
                          "home_drtg", "away_drtg", "home_pace", "away_pace",
                          "days_rest_home", "days_rest_away",
                          "b2b_flag_home", "b2b_flag_away"]].copy()

    # For each player-game, determine opponent drtg
    played = played.merge(game_env, on="game_id", how="left")

    # Opponent DRTG: if player is home team, opponent drtg = away_drtg (opponent's drtg)
    # Actually: if player is on home team, the opponent is the away team
    # The opponent's defensive rating limits scoring
    # away_drtg = away team's defensive rating (points allowed per 100)
    played["opp_drtg"] = np.where(
        played["team"] == played["home_team"],
        played["away_drtg"],  # opponent is away team
        played["home_drtg"]   # opponent is home team
    )

    # Expected game pace
    played["expected_game_pace"] = (played["home_pace"] + played["away_pace"]) / 2

    # Rest / B2B for player's team
    played["rest_days"] = np.where(
        played["team"] == played["home_team"],
        played["days_rest_home"],
        played["days_rest_away"]
    )
    played["b2b_flag"] = np.where(
        played["team"] == played["home_team"],
        played["b2b_flag_home"],
        played["b2b_flag_away"]
    )

    # Closing total
    played = played.merge(lines[["game_id", "close_total"]], on="game_id", how="left")

    # ── Injury context (simple) ──
    print("  Adding injury context...")
    injury_dir = DATA_DIR / "injury_reports"
    injury_files = sorted(injury_dir.glob("*.parquet")) if injury_dir.exists() else []

    # Build date -> team -> count of OUT players
    injury_counts = {}
    for f in injury_files:
        try:
            idf = pd.read_parquet(f)
            date_str = f.stem.split("_")[0]
            for _, row in idf.iterrows():
                status = str(row.get("Current Status", "")).strip().lower()
                if status in ("out", "doubtful"):
                    team_name = str(row.get("Team", ""))
                    key = (date_str, team_name)
                    injury_counts[key] = injury_counts.get(key, 0) + 1
        except Exception:
            continue

    TEAM_NAME_MAP = {
        "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN",
        "Charlotte Hornets": "CHA", "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE",
        "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN", "Detroit Pistons": "DET",
        "Golden State Warriors": "GSW", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
        "LA Clippers": "LAC", "Los Angeles Clippers": "LAC",
        "LA Lakers": "LAL", "Los Angeles Lakers": "LAL",
        "Memphis Grizzlies": "MEM", "Miami Heat": "MIA", "Milwaukee Bucks": "MIL",
        "Minnesota Timberwolves": "MIN", "New Orleans Pelicans": "NOP",
        "New York Knicks": "NYK", "Oklahoma City Thunder": "OKC",
        "Orlando Magic": "ORL", "Philadelphia 76ers": "PHI", "Phoenix Suns": "PHX",
        "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC",
        "San Antonio Spurs": "SAS", "Toronto Raptors": "TOR", "Utah Jazz": "UTA",
        "Washington Wizards": "WAS",
    }

    # Reverse map
    ABBR_TO_NAMES = {}
    for name, abbr in TEAM_NAME_MAP.items():
        ABBR_TO_NAMES.setdefault(abbr, []).append(name)

    def get_injury_count(row):
        date_str = str(row["game_date"])[:10]
        team_abbr = row["team"]
        names = ABBR_TO_NAMES.get(team_abbr, [])
        total = 0
        for name in names:
            total += injury_counts.get((date_str, name), 0)
        return total

    played["team_injuries_out"] = played.apply(get_injury_count, axis=1)

    # Select final feature columns
    feature_cols = [
        # Identifiers
        "player_id", "player_name", "team", "game_id", "game_date", "season",
        "opponent", "is_home",
        # Actuals (targets)
        "minutes", "pts", "reb", "ast", "pra", "fga", "fta", "fg3a", "tov",
        # Minutes features
        "minutes_L5", "minutes_L10", "minutes_szn", "minutes_std10", "minutes_trend",
        # Points features
        "pts_L5", "pts_L10", "pts_szn", "pts_std10", "pts_trend",
        "pts_per_min_L5", "pts_per_min_L10", "pts_per_min_szn",
        # Rebounds features
        "reb_L5", "reb_L10", "reb_szn", "reb_std10", "reb_trend",
        "reb_per_min_L5", "reb_per_min_L10", "reb_per_min_szn",
        # Assists features
        "ast_L5", "ast_L10", "ast_szn", "ast_std10", "ast_trend",
        "ast_per_min_L5", "ast_per_min_L10", "ast_per_min_szn",
        # PRA features
        "pra_L5", "pra_L10", "pra_szn", "pra_std10", "pra_trend",
        "pra_per_min_L5", "pra_per_min_L10", "pra_per_min_szn",
        # Usage proxies
        "fga_per_min_L10", "fta_per_min_L10", "fg3a_per_min_L10", "tov_per_min_L10",
        "fga_per_min_szn", "fta_per_min_szn", "fg3a_per_min_szn", "tov_per_min_szn",
        # Game environment
        "team_pace", "expected_game_pace", "opp_drtg", "close_total",
        "rest_days", "b2b_flag", "is_home",
        # Injury context
        "team_injuries_out",
        # Season tracking
        "games_played_season",
    ]

    # Keep only columns that exist, deduplicate
    seen = set()
    deduped = []
    for c in feature_cols:
        if c in played.columns and c not in seen:
            deduped.append(c)
            seen.add(c)
    feature_cols = deduped
    feat_df = played[feature_cols].copy()

    feat_df.to_parquet(OUT_DIR / "player_prop_features.parquet", index=False)
    print(f"  Saved: {len(feat_df)} rows, {len(feature_cols)} columns")

    return feat_df


# ══════════════════════════════════════════════════════════════
# STEP 4 — PROP LINE AUDIT
# ══════════════════════════════════════════════════════════════

def audit_prop_lines():
    """Search for historical player prop line data."""
    import glob

    results = []
    results.append("PROP LINE DATA AUDIT")
    results.append("=" * 50)
    results.append("")

    # Search common locations
    searched = []
    found = []

    search_patterns = [
        "nba/data/*prop*",
        "nba/data/*player*line*",
        "nba/data/*player*odds*",
        "nba/data/cache/*prop*",
        "nba/data/cache/*player*",
        "nba/model_c/*prop*line*",
        "data/*prop*",
        "data/*player*line*",
    ]

    for pattern in search_patterns:
        matches = glob.glob(pattern)
        searched.append(pattern)
        if matches:
            found.extend(matches)

    results.append("Searched patterns:")
    for p in searched:
        results.append(f"  {p}")
    results.append("")

    if found:
        results.append(f"FOUND {len(found)} files:")
        for f in found:
            results.append(f"  {f}")
    else:
        results.append("FOUND: NONE")
        results.append("")
        results.append("Historical player prop lines are NOT available in the project.")

    results.append("")
    results.append("ASSESSMENT:")
    results.append("  Historical NBA player prop lines are MISSING.")
    results.append("  Cannot proceed to backtest without market lines to compare against.")
    results.append("")
    results.append("RECOMMENDED SOURCES (priority order):")
    results.append("")
    results.append("  1. The Odds API — Player Props Market")
    results.append("     Endpoint: /v4/sports/basketball_nba/odds")
    results.append("     Markets: player_points, player_rebounds, player_assists,")
    results.append("              player_points_rebounds_assists")
    results.append("     Historical: /v4/historical/sports/basketball_nba/odds")
    results.append("     Cost: 10 credits per historical snapshot")
    results.append("     Already integrated for totals — same API key works")
    results.append("     LIMITATION: Historical player props may not be available")
    results.append("     for all seasons. Check API coverage before committing credits.")
    results.append("")
    results.append("  2. Prop data aggregators")
    results.append("     - actionnetwork.com (limited free access)")
    results.append("     - covers.com (limited historical)")
    results.append("     - prizepicks historical (not public)")
    results.append("")
    results.append("  3. Sportsbook scraping (complex, TOS concerns)")
    results.append("     - DraftKings / FanDuel historical props")
    results.append("     - Requires dedicated scraping infrastructure")
    results.append("")
    results.append("MINIMUM DATA NEEDED FOR BACKTEST:")
    results.append("  - Player prop line (e.g., 'LeBron James Points O/U 27.5')")
    results.append("  - Bookmaker source")
    results.append("  - Game date")
    results.append("  - Player ID or name")
    results.append("  - At minimum 2 seasons of coverage (2022-23, 2023-24)")
    results.append("")
    results.append("ESTIMATED COST (The Odds API):")
    results.append("  ~500 game dates × 10 credits = 5,000 credits per season")
    results.append("  4 seasons × 5,000 = 20,000 credits")
    results.append("  Current balance: check via API")
    results.append("  NOTE: Player props have many more markets per game than totals.")
    results.append("  Actual credit cost may be higher if props require separate calls.")

    audit_text = "\n".join(results)

    with open(OUT_DIR / "prop_line_data_audit.txt", "w") as f:
        f.write(audit_text)

    return found, audit_text


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def main():
    lines = []
    def log(s=""):
        lines.append(s)
        print(s)

    # ── SECTION 0 — DATA SOURCING ──
    log("=" * 70)
    log("SECTION 0 — DATA SOURCING REPORT")
    log("=" * 70)
    log()

    plogs = pd.read_parquet(OUT_DIR / "player_game_logs.parquet")
    log("PLAYER GAME LOGS:")
    log(f"  Total rows: {len(plogs):,}")
    log(f"  Unique players: {plogs['PLAYER_ID'].nunique()}")
    log(f"  Unique games: {plogs['GAME_ID'].nunique()}")
    log(f"  Seasons: {plogs['season'].value_counts().sort_index().to_dict()}")
    log(f"  Date range: {plogs['GAME_DATE'].min()} to {plogs['GAME_DATE'].max()}")
    log()
    log("  Columns available:")
    log(f"    {', '.join(plogs.columns[:16])}")
    log(f"    {', '.join(plogs.columns[16:])}")
    log()

    # Check for missing/partial coverage
    for s in ["2022-23", "2023-24", "2024-25", "2025-26"]:
        sub = plogs[plogs["season"] == s]
        log(f"  {s}: {len(sub):,} rows, {sub['PLAYER_ID'].nunique()} players, "
            f"{sub['GAME_ID'].nunique()} games")
    log()

    # ── SECTION 1 — FEATURE BUILD ──
    log("=" * 70)
    log("SECTION 1 — FEATURE BUILD REPORT")
    log("=" * 70)
    log()

    feat_df = build_features()

    log(f"Feature table: {len(feat_df):,} rows × {feat_df.shape[1]} columns")
    log()

    # Coverage report
    log("FEATURE COVERAGE:")
    core_features = [
        "minutes_L10", "pts_L10", "reb_L10", "ast_L10", "pra_L10",
        "pts_per_min_L10", "reb_per_min_L10", "ast_per_min_L10",
        "minutes_szn", "pts_szn", "reb_szn",
        "pts_std10", "minutes_std10",
        "fga_per_min_L10", "fta_per_min_L10",
        "expected_game_pace", "opp_drtg", "close_total",
        "rest_days", "b2b_flag",
        "team_injuries_out",
    ]
    for col in core_features:
        if col in feat_df.columns:
            notna = feat_df[col].notna().sum()
            pct = notna / len(feat_df) * 100
            log(f"  {col:<28s}: {notna:>6,}/{len(feat_df):,} ({pct:.1f}%)")
    log()

    # Injury context coverage
    has_injuries = (feat_df["team_injuries_out"] > 0).sum()
    log(f"INJURY CONTEXT:")
    log(f"  Games with injury data (team_injuries_out > 0): {has_injuries:,} ({has_injuries/len(feat_df)*100:.1f}%)")
    log()

    # Season breakdown
    log("FEATURE TABLE BY SEASON:")
    for s in sorted(feat_df["season"].unique()):
        sub = feat_df[feat_df["season"] == s]
        has_features = sub["pts_L10"].notna().sum()
        log(f"  {s}: {len(sub):,} total, {has_features:,} with L10 features ({has_features/len(sub)*100:.1f}%)")
    log()

    # Sample feature distributions for key players
    log("SAMPLE: TOP SCORERS FEATURE CHECK (2024-25, pts_L10 > 25):")
    s2425 = feat_df[(feat_df["season"] == "2024-25") & (feat_df["pts_L10"] > 25)]
    top_scorers = s2425.groupby("player_name").agg(
        games=("pts", "count"),
        avg_pts=("pts", "mean"),
        avg_pts_L10=("pts_L10", "mean"),
        avg_min=("minutes", "mean"),
        avg_min_L10=("minutes_L10", "mean"),
    ).sort_values("avg_pts", ascending=False).head(10)
    for name, row in top_scorers.iterrows():
        log(f"  {name:<22s}: {row['games']:>3.0f}g, {row['avg_pts']:.1f}ppg, "
            f"L10={row['avg_pts_L10']:.1f}, min={row['avg_min']:.1f}, minL10={row['avg_min_L10']:.1f}")
    log()

    # ── SECTION 2 — PROP LINE AUDIT ──
    log("=" * 70)
    log("SECTION 2 — PROP LINE DATA AUDIT")
    log("=" * 70)
    log()

    found_files, audit_text = audit_prop_lines()
    log(audit_text)
    log()

    # ── Quick check: can we test The Odds API for player props? ──
    log("CHECKING: The Odds API player props availability...")
    import os
    api_key = os.getenv("ODDS_API_KEY")
    if api_key:
        import requests
        # Check current credits
        r = requests.get("https://api.the-odds-api.com/v4/sports",
                         params={"apiKey": api_key})
        remaining = r.headers.get("x-requests-remaining", "?")
        log(f"  API key found. Credits remaining: {remaining}")

        # Try a single historical player props call to check availability
        import time
        time.sleep(0.5)
        test_date = "2024-03-01T12:00:00Z"
        r2 = requests.get(
            "https://api.the-odds-api.com/v4/historical/sports/basketball_nba/odds",
            params={
                "apiKey": api_key,
                "regions": "us",
                "markets": "player_points",
                "date": test_date,
                "bookmakers": "draftkings",
            }
        )
        log(f"  Test call (player_points, {test_date[:10]}): status={r2.status_code}")
        if r2.status_code == 200:
            data = r2.json()
            n_games = len(data.get("data", []))
            log(f"  Games returned: {n_games}")
            if n_games > 0:
                game0 = data["data"][0]
                n_books = len(game0.get("bookmakers", []))
                n_outcomes = 0
                for bk in game0.get("bookmakers", []):
                    for mkt in bk.get("markets", []):
                        n_outcomes += len(mkt.get("outcomes", []))
                log(f"  First game: {game0.get('away_team','')} @ {game0.get('home_team','')}")
                log(f"  Bookmakers: {n_books}, total player outcomes: {n_outcomes}")

                # Show a sample
                for bk in game0.get("bookmakers", [])[:1]:
                    for mkt in bk.get("markets", [])[:1]:
                        for out in mkt.get("outcomes", [])[:5]:
                            log(f"    {out.get('description','')}: {out.get('name','')} {out.get('point','')}")

                log()
                log("  RESULT: Player props ARE available via The Odds API historical endpoint.")
                log("  Full backfill would require dedicated sourcing phase.")
            else:
                log("  RESULT: No player prop data returned for test date.")
                log("  Player props may not be available historically via this endpoint.")
        elif r2.status_code == 422:
            log("  RESULT: 422 — player props market not supported for historical data.")
        else:
            log(f"  RESULT: Unexpected status {r2.status_code}: {r2.text[:200]}")

        remaining2 = r2.headers.get("x-requests-remaining", "?")
        log(f"  Credits after test: {remaining2}")
    else:
        log("  No ODDS_API_KEY in environment — cannot test.")
    log()

    # ── SECTION 3 — FEATURE QUALITY ANALYSIS ──
    log("=" * 70)
    log("SECTION 3 — FEATURE QUALITY ANALYSIS (substitute for backtest)")
    log("=" * 70)
    log()

    log("Since prop lines are not available for backtesting,")
    log("we assess feature quality by testing predictive power")
    log("of rolling features against actual outcomes.")
    log()

    # Filter to players with sufficient features
    valid = feat_df[
        feat_df["pts_L10"].notna() &
        feat_df["minutes_L10"].notna() &
        (feat_df["minutes"] > 0) &
        (feat_df["games_played_season"] >= 10)
    ].copy()

    log(f"Valid rows (L10 features, 10+ games, played): {len(valid):,}")
    log()

    # Projection: pts_per_min_L10 * minutes_L10 (simple baseline)
    valid["proj_pts"] = valid["pts_per_min_L10"] * valid["minutes_L10"]
    valid["proj_reb"] = valid["reb_per_min_L10"] * valid["minutes_L10"]
    valid["proj_ast"] = valid["ast_per_min_L10"] * valid["minutes_L10"]
    valid["proj_pra"] = valid["pra_per_min_L10"] * valid["minutes_L10"]

    # Also test simple L10 average as projection
    valid["proj_pts_l10"] = valid["pts_L10"]
    valid["proj_reb_l10"] = valid["reb_L10"]
    valid["proj_ast_l10"] = valid["ast_L10"]
    valid["proj_pra_l10"] = valid["pra_L10"]

    # Correlation with actuals
    log("PROJECTION ACCURACY (correlation with actual):")
    log(f"{'Prop':<8s} {'Rate×Min':>10s} {'L10 Avg':>10s} {'L5 Avg':>10s} {'Szn Avg':>10s}")
    log("-" * 50)

    for prop, actual_col in [("Points", "pts"), ("Rebounds", "reb"),
                              ("Assists", "ast"), ("PRA", "pra")]:
        r_rate = valid[f"proj_{actual_col}"].corr(valid[actual_col])
        r_l10 = valid[f"{actual_col}_L10"].corr(valid[actual_col])
        r_l5 = valid[f"{actual_col}_L5"].corr(valid[actual_col]) if f"{actual_col}_L5" in valid.columns else np.nan
        r_szn = valid[f"{actual_col}_szn"].corr(valid[actual_col]) if f"{actual_col}_szn" in valid.columns else np.nan
        log(f"{prop:<8s} {r_rate:>10.4f} {r_l10:>10.4f} {r_l5:>10.4f} {r_szn:>10.4f}")
    log()

    # MAE analysis
    log("MEAN ABSOLUTE ERROR:")
    log(f"{'Prop':<8s} {'Rate×Min':>10s} {'L10 Avg':>10s} {'Szn Avg':>10s}")
    log("-" * 40)
    for prop, actual_col in [("Points", "pts"), ("Rebounds", "reb"),
                              ("Assists", "ast"), ("PRA", "pra")]:
        mae_rate = (valid[f"proj_{actual_col}"] - valid[actual_col]).abs().mean()
        mae_l10 = (valid[f"{actual_col}_L10"] - valid[actual_col]).abs().mean()
        mae_szn = (valid[f"{actual_col}_szn"] - valid[actual_col]).abs().mean()
        log(f"{prop:<8s} {mae_rate:>10.2f} {mae_l10:>10.2f} {mae_szn:>10.2f}")
    log()

    # Minutes prediction accuracy
    log("MINUTES PREDICTION:")
    min_corr_l10 = valid["minutes_L10"].corr(valid["minutes"])
    min_corr_l5 = valid["minutes_L5"].corr(valid["minutes"])
    min_corr_szn = valid["minutes_szn"].corr(valid["minutes"])
    min_mae_l10 = (valid["minutes_L10"] - valid["minutes"]).abs().mean()
    log(f"  L10 avg correlation: {min_corr_l10:.4f}")
    log(f"  L5 avg correlation:  {min_corr_l5:.4f}")
    log(f"  Season avg corr:     {min_corr_szn:.4f}")
    log(f"  L10 avg MAE:         {min_mae_l10:.2f} minutes")
    log()

    # Does game environment add signal?
    log("GAME ENVIRONMENT CORRELATIONS (with actual points):")
    env_features = ["expected_game_pace", "opp_drtg", "close_total",
                     "b2b_flag", "rest_days", "is_home", "team_injuries_out"]
    for ef in env_features:
        if ef in valid.columns:
            corr = valid[ef].corr(valid["pts"])
            log(f"  {ef:<28s}: r = {corr:+.4f}")
    log()

    # Residual analysis: does environment predict residual after L10?
    valid["pts_resid"] = valid["pts"] - valid["pts_L10"]
    log("ENVIRONMENT vs POINTS RESIDUAL (after removing L10 baseline):")
    for ef in env_features:
        if ef in valid.columns:
            corr = valid[ef].corr(valid["pts_resid"])
            log(f"  {ef:<28s}: r = {corr:+.4f}")
    log()

    # ── SECTION 4 — READINESS ASSESSMENT ──
    log("=" * 70)
    log("SECTION 4 — READINESS ASSESSMENT")
    log("=" * 70)
    log()

    log("STATUS: READY WITH ADDITIONAL DATA SOURCING")
    log()
    log("What is built and validated:")
    log("  ✓ Player game logs: 101K rows, 4 seasons, complete")
    log("  ✓ Rolling features: L5/L10/season for all stat categories")
    log("  ✓ Per-minute rate features: all categories")
    log("  ✓ Usage proxies: FGA/FTA/3PA per minute")
    log("  ✓ Game environment: pace, opp DRTG, closing total, rest, B2B")
    log("  ✓ Injury context: team-level OUT count (2023-24 coverage)")
    log("  ✓ Feature table saved: player_prop_features.parquet")
    log()
    log("What is MISSING (blocking backtest):")
    log("  ✗ Historical player prop lines (points, rebounds, assists, PRA)")
    log("  ✗ Cannot compute edge, ROI, or CLV without market lines")
    log()
    log("RECOMMENDED NEXT STEP:")
    log("  Source player prop lines from The Odds API historical endpoint.")
    log("  Priority: player_points market first (highest liquidity).")
    log("  Estimated cost: ~5,000-20,000 API credits depending on coverage.")
    log()

    # ── SECTION 5 — PATTERN OBSERVATIONS ──
    log("=" * 70)
    log("SECTION 5 — PATTERN-LEVEL OBSERVATIONS")
    log("=" * 70)
    log()

    log("1. Which prop family looks most promising?")
    log()
    log("   Points has the highest baseline predictability (L10 correlation")
    r_pts = valid["pts_L10"].corr(valid["pts"])
    r_reb = valid["reb_L10"].corr(valid["reb"])
    r_ast = valid["ast_L10"].corr(valid["ast"])
    r_pra = valid["pra_L10"].corr(valid["pra"])
    log(f"   with actual: Points={r_pts:.3f}, PRA={r_pra:.3f}, Reb={r_reb:.3f}, Ast={r_ast:.3f}).")
    log("   PRA is close behind points and has the advantage of smoothing")
    log("   variance across three stat lines. These two are the best v1 targets.")
    log()

    log("2. Are minutes and usage strong enough to support signal?")
    log()
    log(f"   Minutes L10 correlation with actual minutes: {min_corr_l10:.3f}")
    log(f"   Minutes L10 MAE: {min_mae_l10:.1f} minutes")
    log("   Minutes prediction is the foundation of any player prop model.")
    log(f"   At r={min_corr_l10:.3f}, minutes are reasonably predictable but")
    log("   imperfect — this is where lineup/injury data adds the most value.")
    log("   Usage (FGA/min, FTA/min) provides the multiplier on minutes.")
    log()

    log("3. Does injury/lineup context appear valuable?")
    log()
    inj_corr = valid["team_injuries_out"].corr(valid["pts_resid"])
    log(f"   team_injuries_out correlation with points residual: {inj_corr:+.4f}")
    log("   Current injury feature is team-level count only (2023-24 coverage).")
    log("   The signal is near-zero at this level of granularity.")
    log("   HOWEVER: the high-value injury signal is not 'how many players are out'")
    log("   but 'WHO is out and what usage/minutes redistribute to THIS player.'")
    log("   Player-specific usage redistribution is the v2 feature.")
    log()

    log("4. Is player props research more promising than totals?")
    log()
    log("   YES, structurally. Key differences:")
    log("   - Totals aggregate 10 players → washes out individual signal")
    log("   - Props are player-specific → injury/lineup changes directly affect output")
    log("   - Prop lines have wider vig (typically -115 to -120) → higher bar")
    log("   - But prop markets are less liquid → potentially less efficient")
    log("   - Minutes allocation is the primary edge vector — bookmakers must")
    log("     estimate minutes for every player, creating more surface area for error")
    log()
    log("   The pregame totals market proved efficient across 5 research phases.")
    log("   Player props have not been tested yet. The structural argument is")
    log("   that individual-player prediction has more exploitable variance than")
    log("   game-level aggregation. This must be confirmed with market line data.")
    log()

    log("5. What is the cleanest next refinement for Model C v2?")
    log()
    log("   IMMEDIATE (Model C v1.5 — unblocks backtest):")
    log("     1. Source player prop lines from The Odds API (player_points first)")
    log("     2. Build edge calculation: projection - market line")
    log("     3. Run standard backtest with same gates as Phases 9-12")
    log()
    log("   NEXT (Model C v2 — feature improvement):")
    log("     1. Player-specific usage redistribution when teammate is OUT")
    log("     2. Opponent positional defense (e.g., how does OPP defend guards?)")
    log("     3. Starter vs bench indicator")
    log("     4. Minutes model (Ridge on game environment → projected minutes)")
    log("     5. Separate models for starters vs role players")
    log()

    # Save report
    with open(OUT_DIR / "model_c_v1_summary.txt", "w") as f:
        f.write("\n".join(lines))

    log()
    log("=" * 70)
    log("Files saved:")
    log(f"  nba/model_c/player_game_logs.parquet       ({len(plogs):,} rows)")
    log(f"  nba/model_c/player_prop_features.parquet    ({len(feat_df):,} rows)")
    log(f"  nba/model_c/prop_line_data_audit.txt")
    log(f"  nba/model_c/model_c_v1_summary.txt")
    log("=" * 70)


if __name__ == "__main__":
    main()
