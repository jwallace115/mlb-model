"""
NBA Model B v1 — Player Pace Delta Feature Test
Tests whether lineup-adjusted pace expectation adds predictive signal
beyond team-level pace.
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

def roi_110(hits, n):
    if n == 0:
        return np.nan
    return (hits * (100 / 110) - (n - hits)) / n * 100

def stats(df, label=""):
    n = len(df)
    if n == 0:
        return dict(label=label, N=0, hit_rate=np.nan, roi=np.nan, avg_clv=np.nan)
    hits = df["bet_correct"].sum()
    clv_mean = df["clv"].mean() if "clv" in df.columns else np.nan
    return dict(label=label, N=n, hit_rate=round(hits / n * 100, 1),
                roi=round(roi_110(hits, n), 2), avg_clv=round(clv_mean, 2))


# ══════════════════════════════════════════════════════════════
# STEP 2 — COMPUTE PLAYER PACE DELTAS
# ══════════════════════════════════════════════════════════════

def compute_player_pace_deltas():
    """Compute rolling player pace delta from game logs + team pace."""
    print("STEP 2 — Computing player pace deltas...")

    plogs = pd.read_parquet(OUT_DIR / "player_game_logs.parquet")
    box = pd.read_parquet(DATA_DIR / "box_stats.parquet")

    # Standardize game_id format: box uses '002220xxxx', plogs may differ
    # nba_api GAME_ID is like '0022200001'
    plogs["game_id"] = plogs["GAME_ID"]
    plogs["player_id"] = plogs["PLAYER_ID"]
    plogs["player_name"] = plogs["PLAYER_NAME"]
    plogs["team"] = plogs["TEAM_ABBREVIATION"]
    plogs["game_date"] = pd.to_datetime(plogs["GAME_DATE"])
    plogs["minutes"] = pd.to_numeric(plogs["MIN"], errors="coerce").fillna(0)

    # Build team-game pace lookup from box_stats
    # box has team, game_id, pace
    team_pace = box[["game_id", "team", "pace", "date"]].copy()
    team_pace = team_pace.rename(columns={"date": "game_date"})

    # Merge player logs with team pace
    plogs = plogs.merge(team_pace, on=["game_id", "team"], how="left", suffixes=("", "_box"))

    # Use box game_date if player game_date differs
    plogs["game_date"] = plogs["game_date_box"].fillna(plogs["game_date"])
    plogs = plogs.drop(columns=["game_date_box"], errors="ignore")

    # Filter to players with minutes > 0 = played
    plogs["played"] = (plogs["minutes"] > 0).astype(int)

    # Sort for rolling computations
    plogs = plogs.sort_values(["team", "game_date", "player_id"])

    # For each player-team-season combination, compute:
    # - rolling avg team pace when player played (last 30 team games)
    # - rolling avg team pace when player didn't play (last 30 team games)

    # First: build a team-game level dataset with all players' participation
    team_games = team_pace.sort_values(["team", "game_date"]).copy()

    # Get unique players per team-season
    player_team = plogs[["player_id", "player_name", "team", "season"]].drop_duplicates()

    results = []
    insufficient_absence = 0
    total_computed = 0

    # Group by team and season for efficiency
    for (team, season), group in plogs.groupby(["team", "season"]):
        # Team's games this season
        tg = team_games[(team_games["team"] == team)].sort_values("game_date")
        if team_pace["game_date"].dtype != plogs["game_date"].dtype:
            tg["game_date"] = pd.to_datetime(tg["game_date"])

        # Get unique players on this team this season
        team_players = group[["player_id", "player_name"]].drop_duplicates()

        # For each game, mark which players played
        game_players = group.groupby("game_id").apply(
            lambda x: set(x[x["played"] == 1]["player_id"])
        ).to_dict()

        for _, prow in team_players.iterrows():
            pid = prow["player_id"]
            pname = prow["player_name"]

            # For each team game, mark if this player played
            tg_copy = tg.copy()
            tg_copy["player_played"] = tg_copy["game_id"].map(
                lambda gid: 1 if pid in game_players.get(gid, set()) else 0
            )

            # Rolling computation: for each game, look at prior games only
            played_paces = []
            not_played_paces = []

            for i, row in tg_copy.iterrows():
                # Only use games BEFORE this one (no leakage)
                prior = tg_copy.loc[:i].iloc[:-1]  # all rows before current
                if len(prior) == 0:
                    results.append({
                        "player_id": pid, "player_name": pname,
                        "team": team, "season": season,
                        "game_id": row["game_id"], "game_date": row["game_date"],
                        "pace_delta": np.nan, "played_pace": np.nan,
                        "not_played_pace": np.nan, "n_played": 0, "n_not_played": 0,
                        "insufficient_absence": False
                    })
                    continue

                # Rolling window: last 30 team games
                prior_window = prior.tail(30)

                played_games = prior_window[prior_window["player_played"] == 1]
                not_played_games = prior_window[prior_window["player_played"] == 0]

                n_played = len(played_games)
                n_not_played = len(not_played_games)

                played_pace = played_games["pace"].mean() if n_played >= 5 else np.nan
                not_played_pace = not_played_games["pace"].mean() if n_not_played >= 3 else np.nan

                insuff = n_played >= 5 and n_not_played < 3
                if insuff:
                    insufficient_absence += 1

                delta = (played_pace - not_played_pace) if (
                    not pd.isna(played_pace) and not pd.isna(not_played_pace)
                ) else np.nan

                if not pd.isna(delta):
                    total_computed += 1

                results.append({
                    "player_id": pid, "player_name": pname,
                    "team": team, "season": season,
                    "game_id": row["game_id"], "game_date": row["game_date"],
                    "pace_delta": delta, "played_pace": played_pace,
                    "not_played_pace": not_played_pace,
                    "n_played": n_played, "n_not_played": n_not_played,
                    "insufficient_absence": insuff
                })

    df_deltas = pd.DataFrame(results)
    df_deltas.to_parquet(OUT_DIR / "player_pace_deltas.parquet", index=False)

    return df_deltas, insufficient_absence, total_computed


# ══════════════════════════════════════════════════════════════
# STEP 3 — PREGAME LINEUP-ADJUSTED PACE
# ══════════════════════════════════════════════════════════════

def build_pregame_adjustments(df_deltas):
    """Build pregame lineup-adjusted pace using injury data."""
    print("STEP 3 — Building pregame pace adjustments...")

    # Load main datasets
    preds = pd.read_parquet(DATA_DIR / "predictions.parquet")
    box = pd.read_parquet(DATA_DIR / "box_stats.parquet")
    lines = pd.read_parquet(DATA_DIR / "nba_historical_closing_lines.parquet")

    # Load injury reports
    injury_dir = DATA_DIR / "injury_reports"
    injury_files = sorted(injury_dir.glob("*.parquet")) if injury_dir.exists() else []

    print(f"  Found {len(injury_files)} injury report files")

    # Build injury lookup: date -> list of (team, player_name, status)
    injury_by_date = {}
    for f in injury_files:
        try:
            idf = pd.read_parquet(f)
            # Extract date from filename: YYYY-MM-DD_HHMM.parquet
            date_str = f.stem.split("_")[0]
            if date_str not in injury_by_date:
                injury_by_date[date_str] = []

            for _, row in idf.iterrows():
                status = str(row.get("Current Status", "")).strip().lower()
                if status in ("out", "doubtful"):
                    team_name = str(row.get("Team", ""))
                    player = str(row.get("Player Name", ""))
                    injury_by_date[date_str].append({
                        "team_name": team_name,
                        "player": player,
                        "status": status
                    })
        except Exception:
            continue

    print(f"  Injury data for {len(injury_by_date)} unique dates")

    # Team name to abbreviation mapping
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

    # Build latest pace delta per player (most recent non-null value before each game)
    # We'll use a lookup: for each game_id + team, get the pace deltas of missing players
    df_deltas["game_date"] = pd.to_datetime(df_deltas["game_date"])

    # For efficient lookup: player_id -> latest pace delta before a given date
    # Group by player_id, sort by game_date, forward-fill pace_delta
    delta_lookup = df_deltas[df_deltas["pace_delta"].notna()][
        ["player_id", "player_name", "team", "game_date", "pace_delta"]
    ].sort_values(["player_id", "game_date"])

    # Build game-level features
    # Merge predictions with lines
    df = preds.merge(
        lines[["game_id", "close_total", "opening_total"]],
        on="game_id", how="inner"
    )

    # Get actual pace from box stats
    home_pace = box[box["location"] == "H"][["game_id", "pace"]].rename(columns={"pace": "actual_pace_home"})
    away_pace = box[box["location"] == "A"][["game_id", "pace"]].rename(columns={"pace": "actual_pace_away"})
    df = df.merge(home_pace, on="game_id", how="left")
    df = df.merge(away_pace, on="game_id", how="left")
    df["actual_pace"] = (df["actual_pace_home"] + df["actual_pace_away"]) / 2

    # Baseline pace (from features — pregame rolling)
    df["baseline_pace"] = (df["home_pace"] + df["away_pace"]) / 2

    # For each game, find OUT/DOUBTFUL players and their pace deltas
    results = []
    matched_games = 0
    no_injury_data = 0

    for _, game in df.iterrows():
        game_date_str = str(game["date"])[:10] if hasattr(game["date"], "strftime") else str(game["date"])[:10]

        home_team = game["home_team"]
        away_team = game["away_team"]
        game_id = game["game_id"]

        # Get injuries for this date
        injuries = injury_by_date.get(game_date_str, [])

        home_adj = 0.0
        away_adj = 0.0
        home_missing = []
        away_missing = []

        for inj in injuries:
            team_abbr = TEAM_NAME_MAP.get(inj["team_name"], "")
            if team_abbr not in (home_team, away_team):
                continue

            # Find this player's pace delta
            player_name = inj["player"]
            # Match by name (fuzzy: last name match)
            player_deltas = delta_lookup[
                (delta_lookup["player_name"].str.contains(player_name.split()[-1], case=False, na=False)) &
                (delta_lookup["team"] == team_abbr) &
                (delta_lookup["game_date"] < pd.Timestamp(game_date_str))
            ]

            if len(player_deltas) > 0:
                latest = player_deltas.iloc[-1]
                delta_val = latest["pace_delta"]

                if team_abbr == home_team:
                    home_adj += delta_val
                    home_missing.append(f"{player_name}({delta_val:+.1f})")
                else:
                    away_adj += delta_val
                    away_missing.append(f"{player_name}({delta_val:+.1f})")

        if injuries:
            matched_games += 1
        else:
            no_injury_data += 1

        # Adjusted pace: remove the impact of missing players
        # If a player with +2.0 pace delta is OUT, the team is expected to be
        # 2.0 possessions slower → subtract delta from baseline
        home_adjusted = game["home_pace"] - home_adj
        away_adjusted = game["away_pace"] - away_adj

        adjusted_game_pace = (home_adjusted + away_adjusted) / 2
        baseline_game_pace = (game["home_pace"] + game["away_pace"]) / 2
        pace_adjustment_delta = adjusted_game_pace - baseline_game_pace

        results.append({
            "game_id": game_id,
            "date": game_date_str,
            "season": game["season"],
            "home_team": home_team,
            "away_team": away_team,
            "baseline_pace": baseline_game_pace,
            "adjusted_pace": adjusted_game_pace,
            "pace_adjustment_delta": pace_adjustment_delta,
            "home_adjustment": -home_adj,
            "away_adjustment": -away_adj,
            "home_missing_players": "|".join(home_missing),
            "away_missing_players": "|".join(away_missing),
            "actual_pace": game["actual_pace"],
            "actual_total": game["actual_total"],
            "close_total": game["close_total"],
            "opening_total": game.get("opening_total"),
            "pred_total": game["pred_total"],
        })

    adj_df = pd.DataFrame(results)
    adj_df.to_parquet(OUT_DIR / "pregame_pace_adjustments.parquet", index=False)

    return adj_df, matched_games, no_injury_data


# ══════════════════════════════════════════════════════════════
# STEP 4 — BACKTEST
# ══════════════════════════════════════════════════════════════

def check_gates(df, baseline_roi):
    failed = []
    disc = df[df["season"].isin(DISC_SEASONS)]
    n = len(disc)
    if n < 80:
        failed.append(f"N={n}<80")
    if n == 0:
        return "FAIL", ["no_data"]

    disc_roi = roi_110(disc["bet_correct"].sum(), n)

    for s in DISC_SEASONS:
        ss = disc[disc["season"] == s]
        ns = len(ss)
        if ns < 30:
            failed.append(f"N_{s}={ns}<30")
        elif roi_110(ss["bet_correct"].sum(), ns) <= 0:
            failed.append(f"ROI_{s}={roi_110(ss['bet_correct'].sum(), ns):.1f}%<=0")

    if disc_roi < 3.0:
        failed.append(f"disc_ROI={disc_roi:.1f}%<3%")

    delta = disc_roi - baseline_roi
    if delta < 2.0:
        failed.append(f"delta={delta:.1f}pp<2pp")

    oos = df[df["season"] == VAL_SEASON]
    if len(oos) > 0:
        oos_roi = roi_110(oos["bet_correct"].sum(), len(oos))
        if oos_roi < 0:
            failed.append(f"OOS={oos_roi:.1f}%<0")
    else:
        failed.append("no_OOS")

    if disc_roi > 0 and "clv" in disc.columns:
        avg_clv = disc["clv"].mean()
        if avg_clv < 0:
            failed.append(f"CLV={avg_clv:.2f}_neg")

    if len(failed) == 0:
        return "PASS", []
    elif len(failed) == 1:
        return "NEAR-MISS", failed
    else:
        return "FAIL", failed


def run_backtest(adj_df, baseline_roi, log):
    """Run B1-B5 hypothesis tests."""
    df = adj_df.copy()

    # Bet variables
    df["model_edge"] = df["pred_total"] - df["close_total"]
    df["model_direction"] = np.where(df["model_edge"] > 0, "OVER", "UNDER")
    df["bet_correct_over"] = (df["actual_total"] > df["close_total"]).astype(int)
    df["bet_correct_under"] = (df["actual_total"] < df["close_total"]).astype(int)
    df["bet_correct_model"] = np.where(
        df["model_direction"] == "OVER", df["bet_correct_over"], df["bet_correct_under"])

    # CLV
    df["line_movement"] = df["close_total"] - df["opening_total"]
    df["clv"] = np.where(df["model_direction"] == "OVER", df["line_movement"], -df["line_movement"])

    has_open = df["opening_total"].notna()
    df = df[has_open].copy()

    all_results = []

    # B1: Pace adjusted UP → OVER
    mask = df["pace_adjustment_delta"] > 0
    sub = df[mask].copy()
    sub["bet_correct"] = sub["bet_correct_over"]
    sub["clv"] = sub["line_movement"]
    disc = sub[sub["season"].isin(DISC_SEASONS)]
    oos = sub[sub["season"] == VAL_SEASON]
    r = {"id": "B1", "name": "Pace Adjusted UP → OVER", "direction": "OVER"}
    r["N_disc"] = len(disc)
    r["roi_disc"] = round(roi_110(disc["bet_correct"].sum(), len(disc)), 2) if len(disc) > 0 else np.nan
    r["roi_oos"] = round(roi_110(oos["bet_correct"].sum(), len(oos)), 2) if len(oos) > 0 else np.nan
    r["avg_clv_disc"] = round(disc["clv"].mean(), 2) if len(disc) > 0 else np.nan
    for s in DISC_SEASONS:
        ss = disc[disc["season"] == s]
        r[f"N_{s}"] = len(ss)
        r[f"roi_{s}"] = round(roi_110(ss["bet_correct"].sum(), len(ss)), 2) if len(ss) > 0 else np.nan
    r["delta"] = round(r["roi_disc"] - baseline_roi, 2) if not pd.isna(r["roi_disc"]) else np.nan
    label, failed = check_gates(sub, baseline_roi)
    r["label"] = label
    r["gates_failed"] = failed
    all_results.append(r)

    log(f"B1 — PACE ADJUSTED UP → OVER")
    log(f"  Label: {r['label']}")
    log(f"  N_disc={r['N_disc']}, ROI={r['roi_disc']}%, CLV={r.get('avg_clv_disc')}")
    for s in DISC_SEASONS:
        log(f"  {s}: N={r.get(f'N_{s}')}, ROI={r.get(f'roi_{s}')}%")
    log(f"  OOS: N={len(oos)}, ROI={r['roi_oos']}%")
    log(f"  Delta: {r['delta']}pp")
    if failed: log(f"  Gates: {', '.join(failed)}")
    log()

    # B2: Pace adjusted DOWN → UNDER
    mask = df["pace_adjustment_delta"] < 0
    sub = df[mask].copy()
    sub["bet_correct"] = sub["bet_correct_under"]
    sub["clv"] = -sub["line_movement"]
    disc = sub[sub["season"].isin(DISC_SEASONS)]
    oos = sub[sub["season"] == VAL_SEASON]
    r = {"id": "B2", "name": "Pace Adjusted DOWN → UNDER", "direction": "UNDER"}
    r["N_disc"] = len(disc)
    r["roi_disc"] = round(roi_110(disc["bet_correct"].sum(), len(disc)), 2) if len(disc) > 0 else np.nan
    r["roi_oos"] = round(roi_110(oos["bet_correct"].sum(), len(oos)), 2) if len(oos) > 0 else np.nan
    r["avg_clv_disc"] = round(disc["clv"].mean(), 2) if len(disc) > 0 else np.nan
    for s in DISC_SEASONS:
        ss = disc[disc["season"] == s]
        r[f"N_{s}"] = len(ss)
        r[f"roi_{s}"] = round(roi_110(ss["bet_correct"].sum(), len(ss)), 2) if len(ss) > 0 else np.nan
    r["delta"] = round(r["roi_disc"] - baseline_roi, 2) if not pd.isna(r["roi_disc"]) else np.nan
    label, failed = check_gates(sub, baseline_roi)
    r["label"] = label
    r["gates_failed"] = failed
    all_results.append(r)

    log(f"B2 — PACE ADJUSTED DOWN → UNDER")
    log(f"  Label: {r['label']}")
    log(f"  N_disc={r['N_disc']}, ROI={r['roi_disc']}%, CLV={r.get('avg_clv_disc')}")
    for s in DISC_SEASONS:
        log(f"  {s}: N={r.get(f'N_{s}')}, ROI={r.get(f'roi_{s}')}%")
    log(f"  OOS: N={len(oos)}, ROI={r['roi_oos']}%")
    log(f"  Delta: {r['delta']}pp")
    if failed: log(f"  Gates: {', '.join(failed)}")
    log()

    # B3: Large adjustment (|delta| >= 1.5) → implied direction
    mask = df["pace_adjustment_delta"].abs() >= 1.5
    sub = df[mask].copy()
    sub["bet_correct"] = np.where(
        sub["pace_adjustment_delta"] > 0, sub["bet_correct_over"], sub["bet_correct_under"])
    sub["clv"] = np.where(
        sub["pace_adjustment_delta"] > 0, sub["line_movement"], -sub["line_movement"])
    disc = sub[sub["season"].isin(DISC_SEASONS)]
    oos = sub[sub["season"] == VAL_SEASON]
    r = {"id": "B3", "name": "Large Adjustment (>=1.5) → Implied", "direction": "implied"}
    r["N_disc"] = len(disc)
    r["roi_disc"] = round(roi_110(disc["bet_correct"].sum(), len(disc)), 2) if len(disc) > 0 else np.nan
    r["roi_oos"] = round(roi_110(oos["bet_correct"].sum(), len(oos)), 2) if len(oos) > 0 else np.nan
    r["avg_clv_disc"] = round(disc["clv"].mean(), 2) if len(disc) > 0 else np.nan
    for s in DISC_SEASONS:
        ss = disc[disc["season"] == s]
        r[f"N_{s}"] = len(ss)
        r[f"roi_{s}"] = round(roi_110(ss["bet_correct"].sum(), len(ss)), 2) if len(ss) > 0 else np.nan
    r["delta"] = round(r["roi_disc"] - baseline_roi, 2) if not pd.isna(r["roi_disc"]) else np.nan
    label, failed = check_gates(sub, baseline_roi)
    r["label"] = label
    r["gates_failed"] = failed
    all_results.append(r)

    log(f"B3 — LARGE ADJUSTMENT (>=1.5) → IMPLIED DIRECTION")
    log(f"  Label: {r['label']}")
    log(f"  N_disc={r['N_disc']}, ROI={r['roi_disc']}%")
    for s in DISC_SEASONS:
        log(f"  {s}: N={r.get(f'N_{s}')}, ROI={r.get(f'roi_{s}')}%")
    log(f"  OOS: N={len(oos)}, ROI={r['roi_oos']}%")
    log(f"  Delta: {r['delta']}pp")
    if failed: log(f"  Gates: {', '.join(failed)}")
    log()

    # B4: Adjustment confirms model direction
    adj_dir = np.where(df["pace_adjustment_delta"] > 0, "OVER", "UNDER")
    mask = (adj_dir == df["model_direction"]) & (df["pace_adjustment_delta"].abs() > 0)
    sub = df[mask].copy()
    sub["bet_correct"] = sub["bet_correct_model"]
    disc = sub[sub["season"].isin(DISC_SEASONS)]
    oos = sub[sub["season"] == VAL_SEASON]
    r = {"id": "B4", "name": "Adjustment Confirms Model", "direction": "model"}
    r["N_disc"] = len(disc)
    r["roi_disc"] = round(roi_110(disc["bet_correct"].sum(), len(disc)), 2) if len(disc) > 0 else np.nan
    r["roi_oos"] = round(roi_110(oos["bet_correct"].sum(), len(oos)), 2) if len(oos) > 0 else np.nan
    r["avg_clv_disc"] = round(disc["clv"].mean(), 2) if len(disc) > 0 else np.nan
    for s in DISC_SEASONS:
        ss = disc[disc["season"] == s]
        r[f"N_{s}"] = len(ss)
        r[f"roi_{s}"] = round(roi_110(ss["bet_correct"].sum(), len(ss)), 2) if len(ss) > 0 else np.nan
    r["delta"] = round(r["roi_disc"] - baseline_roi, 2) if not pd.isna(r["roi_disc"]) else np.nan
    label, failed = check_gates(sub, baseline_roi)
    r["label"] = label
    r["gates_failed"] = failed
    all_results.append(r)

    log(f"B4 — ADJUSTMENT CONFIRMS MODEL DIRECTION")
    log(f"  Label: {r['label']}")
    log(f"  N_disc={r['N_disc']}, ROI={r['roi_disc']}%, CLV={r.get('avg_clv_disc')}")
    for s in DISC_SEASONS:
        log(f"  {s}: N={r.get(f'N_{s}')}, ROI={r.get(f'roi_{s}')}%")
    log(f"  OOS: N={len(oos)}, ROI={r['roi_oos']}%")
    log(f"  Delta: {r['delta']}pp")
    if failed: log(f"  Gates: {', '.join(failed)}")
    log()

    # B5: Adjustment contradicts model — test BOTH directions
    mask = (adj_dir != df["model_direction"]) & (df["pace_adjustment_delta"].abs() > 0)

    # Follow model
    sub = df[mask].copy()
    sub["bet_correct"] = sub["bet_correct_model"]
    disc = sub[sub["season"].isin(DISC_SEASONS)]
    oos = sub[sub["season"] == VAL_SEASON]
    r = {"id": "B5_model", "name": "Contradiction → Follow Model", "direction": "model"}
    r["N_disc"] = len(disc)
    r["roi_disc"] = round(roi_110(disc["bet_correct"].sum(), len(disc)), 2) if len(disc) > 0 else np.nan
    r["roi_oos"] = round(roi_110(oos["bet_correct"].sum(), len(oos)), 2) if len(oos) > 0 else np.nan
    r["avg_clv_disc"] = round(disc["clv"].mean(), 2) if len(disc) > 0 else np.nan
    for s in DISC_SEASONS:
        ss = disc[disc["season"] == s]
        r[f"N_{s}"] = len(ss)
        r[f"roi_{s}"] = round(roi_110(ss["bet_correct"].sum(), len(ss)), 2) if len(ss) > 0 else np.nan
    r["delta"] = round(r["roi_disc"] - baseline_roi, 2) if not pd.isna(r["roi_disc"]) else np.nan
    label, failed = check_gates(sub, baseline_roi)
    r["label"] = label
    r["gates_failed"] = failed
    all_results.append(r)

    log(f"B5a — CONTRADICTION → FOLLOW MODEL")
    log(f"  Label: {r['label']}")
    log(f"  N_disc={r['N_disc']}, ROI={r['roi_disc']}%")
    for s in DISC_SEASONS:
        log(f"  {s}: N={r.get(f'N_{s}')}, ROI={r.get(f'roi_{s}')}%")
    log(f"  OOS: N={len(oos)}, ROI={r['roi_oos']}%")
    if failed: log(f"  Gates: {', '.join(failed)}")
    log()

    # Follow pace adjustment
    sub2 = df[mask].copy()
    sub2["bet_correct"] = np.where(
        sub2["pace_adjustment_delta"] > 0, sub2["bet_correct_over"], sub2["bet_correct_under"])
    sub2["clv"] = np.where(
        sub2["pace_adjustment_delta"] > 0, sub2["line_movement"], -sub2["line_movement"])
    disc2 = sub2[sub2["season"].isin(DISC_SEASONS)]
    oos2 = sub2[sub2["season"] == VAL_SEASON]
    r = {"id": "B5_pace", "name": "Contradiction → Follow Pace", "direction": "pace adj"}
    r["N_disc"] = len(disc2)
    r["roi_disc"] = round(roi_110(disc2["bet_correct"].sum(), len(disc2)), 2) if len(disc2) > 0 else np.nan
    r["roi_oos"] = round(roi_110(oos2["bet_correct"].sum(), len(oos2)), 2) if len(oos2) > 0 else np.nan
    r["avg_clv_disc"] = round(disc2["clv"].mean(), 2) if len(disc2) > 0 else np.nan
    for s in DISC_SEASONS:
        ss = disc2[disc2["season"] == s]
        r[f"N_{s}"] = len(ss)
        r[f"roi_{s}"] = round(roi_110(ss["bet_correct"].sum(), len(ss)), 2) if len(ss) > 0 else np.nan
    r["delta"] = round(r["roi_disc"] - baseline_roi, 2) if not pd.isna(r["roi_disc"]) else np.nan
    label, failed = check_gates(sub2, baseline_roi)
    r["label"] = label
    r["gates_failed"] = failed
    all_results.append(r)

    log(f"B5b — CONTRADICTION → FOLLOW PACE ADJUSTMENT")
    log(f"  Label: {r['label']}")
    log(f"  N_disc={r['N_disc']}, ROI={r['roi_disc']}%")
    for s in DISC_SEASONS:
        log(f"  {s}: N={r.get(f'N_{s}')}, ROI={r.get(f'roi_{s}')}%")
    log(f"  OOS: N={len(oos2)}, ROI={r['roi_oos']}%")
    if failed: log(f"  Gates: {', '.join(failed)}")
    log()

    return all_results


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def main():
    lines = []
    def log(s=""):
        lines.append(s)
        print(s)

    # ── SECTION 0 — DATA SOURCING REPORT ──
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
    log()

    # ── STEP 2: Player pace deltas ──
    df_deltas, insufficient_absence, total_computed = compute_player_pace_deltas()

    valid_deltas = df_deltas["pace_delta"].notna()
    n_valid = valid_deltas.sum()
    n_players_valid = df_deltas[valid_deltas]["player_id"].nunique()
    n_players_insuff = df_deltas[df_deltas["insufficient_absence"]]["player_id"].nunique()

    log("PLAYER PACE DELTAS:")
    log(f"  Total player-game-delta rows: {len(df_deltas):,}")
    log(f"  Rows with valid pace delta: {n_valid:,}")
    log(f"  Players with valid delta: {n_players_valid}")
    log(f"  Players flagged insufficient absence: {n_players_insuff}")
    log(f"  Total insufficient absence flags: {insufficient_absence:,}")
    log()

    # Distribution of pace deltas
    deltas = df_deltas[valid_deltas]["pace_delta"]
    log("PACE DELTA DISTRIBUTION:")
    log(f"  Mean:   {deltas.mean():+.2f}")
    log(f"  Median: {deltas.median():+.2f}")
    log(f"  Std:    {deltas.std():.2f}")
    log(f"  Min:    {deltas.min():+.1f}")
    log(f"  Max:    {deltas.max():+.1f}")
    log()

    # Top 10 and bottom 10 by latest pace delta
    latest = df_deltas[valid_deltas].sort_values(["player_id", "game_date"]).groupby("player_id").last()
    # Filter to players with enough games
    latest = latest[latest["n_played"] >= 20]
    latest = latest.sort_values("pace_delta")

    log("TOP 10 PLAYERS — SPEED UP GAMES (highest pace delta):")
    for _, row in latest.tail(10).iloc[::-1].iterrows():
        log(f"  {row['player_name']:<22s} ({row['team']}) delta={row['pace_delta']:+.2f} "
            f"(played={row['n_played']}, missed={row['n_not_played']})")
    log()

    log("BOTTOM 10 PLAYERS — SLOW DOWN GAMES (lowest pace delta):")
    for _, row in latest.head(10).iterrows():
        log(f"  {row['player_name']:<22s} ({row['team']}) delta={row['pace_delta']:+.2f} "
            f"(played={row['n_played']}, missed={row['n_not_played']})")
    log()

    # ── STEP 3: Pregame adjustments ──
    adj_df, matched_games, no_injury_data = build_pregame_adjustments(df_deltas)

    log("=" * 70)
    log("SECTION 1 — FEATURE VALIDATION")
    log("=" * 70)
    log()

    # Coverage
    has_adj = adj_df["pace_adjustment_delta"].notna()
    nonzero_adj = adj_df["pace_adjustment_delta"] != 0
    log("COVERAGE:")
    log(f"  Total games: {len(adj_df)}")
    log(f"  Games with injury data: {matched_games}")
    log(f"  Games without injury data: {no_injury_data}")
    log(f"  Games with non-zero pace adjustment: {nonzero_adj.sum()} ({nonzero_adj.mean()*100:.1f}%)")
    log()

    log("PACE ADJUSTMENT DELTA DISTRIBUTION:")
    pad = adj_df["pace_adjustment_delta"]
    log(f"  Mean:   {pad.mean():+.3f}")
    log(f"  Median: {pad.median():+.3f}")
    log(f"  Std:    {pad.std():.3f}")
    log(f"  Min:    {pad.min():+.2f}")
    log(f"  Max:    {pad.max():+.2f}")
    log(f"  % zero: {(pad == 0).mean()*100:.1f}%")
    log(f"  % |adj| > 0.5: {(pad.abs() > 0.5).sum()} ({(pad.abs() > 0.5).mean()*100:.1f}%)")
    log(f"  % |adj| > 1.0: {(pad.abs() > 1.0).sum()} ({(pad.abs() > 1.0).mean()*100:.1f}%)")
    log(f"  % |adj| > 1.5: {(pad.abs() > 1.5).sum()} ({(pad.abs() > 1.5).mean()*100:.1f}%)")
    log()

    # CORRELATION CHECKS
    valid = adj_df[adj_df["actual_pace"].notna()].copy()
    valid["pace_shock"] = valid["actual_pace"] - valid["baseline_pace"]

    corr_baseline = valid["baseline_pace"].corr(valid["pace_shock"])
    corr_adjusted = valid["adjusted_pace"].corr(valid["pace_shock"])
    corr_delta = corr_adjusted - corr_baseline

    # Also compute: does adjustment predict pace_shock better?
    # Correlation of pace_adjustment_delta with pace_shock
    corr_adj_delta = valid["pace_adjustment_delta"].corr(valid["pace_shock"])

    log("CORRELATION CHECKS:")
    log(f"  Baseline pace vs pace_shock:     r = {corr_baseline:.4f}")
    log(f"  Adjusted pace vs pace_shock:     r = {corr_adjusted:.4f}")
    log(f"  Improvement (adjusted - baseline): Δr = {corr_delta:+.4f}")
    log(f"  pace_adjustment_delta vs pace_shock: r = {corr_adj_delta:.4f}")
    log()

    # Also: correlation with total error
    valid["total_error"] = valid["actual_total"] - valid["close_total"]
    corr_adj_total = valid["pace_adjustment_delta"].corr(valid["total_error"])
    corr_baseline_total = valid["baseline_pace"].corr(valid["total_error"])
    corr_adjusted_total = valid["adjusted_pace"].corr(valid["total_error"])

    log(f"  Baseline pace vs total_error:      r = {corr_baseline_total:.4f}")
    log(f"  Adjusted pace vs total_error:       r = {corr_adjusted_total:.4f}")
    log(f"  pace_adj_delta vs total_error:      r = {corr_adj_total:.4f}")
    log()

    # STOP GATE CHECK
    stop = False
    if abs(corr_adj_delta) < 0.10 and corr_delta < 0.03:
        log("*** STOP GATE TRIGGERED ***")
        log(f"  pace_adjustment_delta correlation with pace_shock: {corr_adj_delta:.4f} (threshold: |r| >= 0.10)")
        log(f"  Improvement over baseline: {corr_delta:+.4f} (threshold: >= 0.03)")
        log()
        log("  The player pace delta adjustment does NOT meaningfully improve")
        log("  pace prediction over team-level averages.")
        log()

        # Even if gate fails, explain WHY and still run backtest for completeness
        if nonzero_adj.mean() < 0.20:
            log(f"  ROOT CAUSE: Only {nonzero_adj.mean()*100:.1f}% of games have non-zero adjustment.")
            log("  Injury reports cover limited dates, and most players who sit out")
            log("  have insufficient game-missed samples for pace delta estimation.")
            log("  The feature has extremely low variance — it is zero for most games.")
        log()

        log("  Per protocol: STOP HERE for correlation gate.")
        log("  Running backtest below for completeness only — results are informational.")
        log()
        stop = True

    if not stop and corr_delta < 0.03:
        log("*** STOP GATE TRIGGERED (no meaningful improvement) ***")
        log(f"  Adjusted correlation: {corr_adjusted:.4f}")
        log(f"  Baseline correlation: {corr_baseline:.4f}")
        log(f"  Delta: {corr_delta:+.4f} (threshold: >= 0.03)")
        log("  The player-level adjustment does not improve on team baseline.")
        log("  Running backtest below for completeness only.")
        log()
        stop = True

    # ── SECTION 2 — BACKTEST ──
    log("=" * 70)
    log("SECTION 2 — BACKTEST RESULTS" + (" (INFORMATIONAL — correlation gate failed)" if stop else ""))
    log("=" * 70)
    log()

    # Baseline ROI (full population, model direction)
    df_bt = adj_df[adj_df["opening_total"].notna()].copy()
    df_bt["model_edge"] = df_bt["pred_total"] - df_bt["close_total"]
    df_bt["model_direction"] = np.where(df_bt["model_edge"] > 0, "OVER", "UNDER")
    df_bt["bet_correct"] = np.where(
        df_bt["model_direction"] == "OVER",
        (df_bt["actual_total"] > df_bt["close_total"]).astype(int),
        (df_bt["actual_total"] < df_bt["close_total"]).astype(int)
    )
    disc_full = df_bt[df_bt["season"].isin(DISC_SEASONS)]
    baseline_roi = roi_110(disc_full["bet_correct"].sum(), len(disc_full))
    log(f"Baseline ROI (full population, model dir, discovery): {baseline_roi:.2f}%")
    log()

    all_results = run_backtest(adj_df, baseline_roi, log)

    # ── SECTION 3 — MASTER SUMMARY ──
    log("=" * 70)
    log("MASTER SUMMARY TABLE")
    log("=" * 70)
    log()

    hdr = f"{'ID':<12} {'Name':<36} {'Label':<10} {'N':>5} {'ROI_D':>7} {'ROI_O':>7} {'CLV':>6} {'Delta':>6} {'Failed'}"
    log(hdr)
    log("-" * len(hdr))
    for r in all_results:
        gf = r.get("gates_failed", [])
        gf_str = gf[0][:25] if len(gf) == 1 else (f"{len(gf)} gates" if gf else "—")
        rd = f"{r.get('roi_disc'):.1f}%" if pd.notna(r.get('roi_disc', np.nan)) else "N/A"
        ro = f"{r.get('roi_oos'):.1f}%" if pd.notna(r.get('roi_oos', np.nan)) else "N/A"
        cl = f"{r.get('avg_clv_disc'):.2f}" if pd.notna(r.get('avg_clv_disc', np.nan)) else "N/A"
        dl = f"{r.get('delta'):.1f}" if pd.notna(r.get('delta', np.nan)) else "N/A"
        log(f"{r['id']:<12} {r['name']:<36} {r['label']:<10} {r.get('N_disc',0):>5} {rd:>7} {ro:>7} {cl:>6} {dl:>6} {gf_str}")
    log()

    # Save CSV
    csv_rows = []
    for r in all_results:
        row = {k: v for k, v in r.items() if k != "gates_failed"}
        row["gates_failed"] = "|".join(r.get("gates_failed", []))
        csv_rows.append(row)
    pd.DataFrame(csv_rows).to_csv(OUT_DIR / "model_b_v1_results.csv", index=False)

    # ── SECTION 4 — PATTERN OBSERVATIONS ──
    log("=" * 70)
    log("SECTION 3 — PATTERN OBSERVATIONS")
    log("=" * 70)
    log()

    n_pass = sum(1 for r in all_results if r["label"] == "PASS")
    n_near = sum(1 for r in all_results if r["label"] == "NEAR-MISS")

    log("1. Does player-level adjustment improve pace prediction over team average?")
    log()
    log(f"   Baseline (team avg) correlation with pace_shock: {corr_baseline:.4f}")
    log(f"   Adjusted (lineup) correlation with pace_shock:   {corr_adjusted:.4f}")
    log(f"   Improvement: {corr_delta:+.4f}")
    log()
    if corr_delta < 0.03:
        log("   NO. The player-level lineup adjustment does not meaningfully")
        log("   improve pace prediction over simple team rolling averages.")
        log("   The improvement is negligible or negative.")
    else:
        log("   YES — modest improvement detected.")
    log()

    log("2. Does the improvement translate to betting signal?")
    log()
    log(f"   Hypotheses passing: {n_pass}")
    log(f"   Near-misses: {n_near}")
    if n_pass == 0:
        log("   NO. Even where the adjustment has marginal predictive value,")
        log("   it does not translate to exploitable betting signal.")
    log()

    log("3. If null again: what does this definitively tell us about NBA pregame totals?")
    log()
    if n_pass == 0 and stop:
        log("   Five research phases (9, 10, 11, 12, Model B) have now tested:")
        log("     - Edge size: no signal")
        log("     - Market movement: no signal")
        log("     - Team-level pace expectation: no predictive signal")
        log("     - Variance environments: no signal")
        log("     - Player-level pace adjustment: no signal")
        log()
        log("   DEFINITIVE CONCLUSION:")
        log("   NBA pregame totals are efficiently priced across every tested")
        log("   dimension — price, movement, pace, variance, and lineup composition.")
        log()
        log("   The market correctly prices player availability into the total.")
        log("   This is expected: bookmakers have access to the same injury reports")
        log("   and likely use far more granular lineup and pace data than what is")
        log("   available through public APIs.")
        log()
        log("   RECOMMENDATION:")
        log("   Close the NBA pregame totals research program.")
        log("   Redirect research resources to:")
        log("     1. NBA first-half (H1) totals (different market, less liquid)")
        log("     2. NBA player props (less efficient, higher vig)")
        log("     3. Sports where validated edges exist (MLB, soccer)")
        log("     4. Live/in-game NBA markets (different efficiency regime)")
    log()

    log("4. If signal found: what is the next refinement?")
    log()
    if n_pass > 0:
        log("   Signal detected — next steps would be:")
        log("     - Add starter vs bench weighting")
        log("     - Source on/off pace splits from pbpstats")
        log("     - Build proper lineup-minutes model")
    else:
        log("   No signal found. No refinement path exists for this framework.")
        log("   The concept is exhausted at the pregame level.")
    log()

    # Save report
    with open(OUT_DIR / "model_b_v1_summary.txt", "w") as f:
        f.write("\n".join(lines))

    log()
    log("=" * 70)
    log("Files saved:")
    log(f"  nba/model_b/player_game_logs.parquet")
    log(f"  nba/model_b/player_pace_deltas.parquet")
    log(f"  nba/model_b/pregame_pace_adjustments.parquet")
    log(f"  nba/model_b/model_b_v1_summary.txt")
    log(f"  nba/model_b/model_b_v1_results.csv")
    log("=" * 70)


if __name__ == "__main__":
    main()
