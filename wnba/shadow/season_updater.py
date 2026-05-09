#!/usr/bin/env python3
"""WNBA Shadow — Season Updater (Component 5). Runs 10:00 AM ET daily.
Ingests completed WNBA box scores into player/team/game logs and recomputes
rolling features. Updates all four target files idempotently.
"""
import os, sys, time, shutil
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

DATA_DIR = Path("wnba/data")
SHADOW_DIR = Path("wnba/shadow")
RUN_MODE = os.environ.get("RUN_MODE", "test")

ROLE_ORDER = {"Deep Bench": 1, "Bench": 2, "Rotation": 3, "Starter": 4, "Starter-Heavy": 5}

HEADERS = {
    "Host": "stats.nba.com",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://www.nba.com/",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
}


def assign_role(start_rate, avg_minutes, gp=99):
    if gp < 5: return "Deep Bench"
    if start_rate >= 0.80 and avg_minutes >= 28: return "Starter-Heavy"
    if start_rate >= 0.50 and avg_minutes >= 22: return "Starter"
    if start_rate < 0.50 and avg_minutes >= 14: return "Rotation"
    if avg_minutes >= 7: return "Bench"
    return "Deep Bench"


def minutes_to_decimal(min_str):
    if pd.isna(min_str) or min_str is None or str(min_str).strip() == "":
        return 0.0
    s = str(min_str).strip()
    if ":" in s:
        parts = s.split(":")
        try: return int(parts[0]) + int(parts[1]) / 60.0
        except: return 0.0
    try: return float(s)
    except: return 0.0


def _backup(path):
    if path.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        bak = path.with_suffix(f".parquet.bak_{ts}")
        shutil.copy2(path, bak)
        print(f"  Backup: {bak}", flush=True)


def _fetch_box_scores(update_date):
    """Fetch player and team box scores for completed games on update_date."""
    from nba_api.stats.endpoints import BoxScoreTraditionalV3, LeagueGameLog

    print(f"Fetching WNBA games for {update_date}...", flush=True)
    time.sleep(1)

    season_year = int(update_date[:4])
    lg = LeagueGameLog(league_id="10", season=str(season_year),
                       season_type_all_star="Regular Season",
                       headers=HEADERS, timeout=60)
    games_df = lg.get_data_frames()[0]
    games_df["GAME_DATE"] = pd.to_datetime(games_df["GAME_DATE"])
    day_games = games_df[games_df["GAME_DATE"].dt.strftime("%Y-%m-%d") == update_date]
    game_ids = day_games["GAME_ID"].unique()
    print(f"  Found {len(game_ids)} games", flush=True)

    if len(game_ids) == 0:
        return [], [], []

    # Build team-level info from LeagueGameLog for matchup context
    team_info = {}
    for _, row in day_games.iterrows():
        gid = row["GAME_ID"]
        tid = row["TEAM_ID"]
        team_info[(gid, tid)] = {
            "wl": row.get("WL", ""),
            "pts": row.get("PTS", 0),
            "matchup": row.get("MATCHUP", ""),
        }

    player_rows = []
    team_rows = []
    game_index_rows = []

    for gid in game_ids:
        time.sleep(1)
        try:
            result = BoxScoreTraditionalV3(game_id=gid, headers=HEADERS, timeout=60)
            dfs = result.get_data_frames()
        except Exception as e:
            print(f"  Failed {gid}: {e}", flush=True)
            continue

        # dfs[0] = player stats, dfs[2] = team totals
        pdf = dfs[0]  # player box score
        tdf = dfs[2]  # team totals

        game_date = pd.Timestamp(update_date)
        season = int(update_date[:4])

        # Identify home/away from team data
        teams_in_game = tdf["teamId"].unique().tolist()
        # Use LeagueGameLog matchup to determine home/away
        home_tid = away_tid = None
        for tid in teams_in_game:
            info = team_info.get((gid, tid), {})
            matchup = info.get("matchup", "")
            if "vs." in matchup:
                home_tid = tid
            elif "@" in matchup:
                away_tid = tid
        if home_tid is None and away_tid is not None:
            home_tid = [t for t in teams_in_game if t != away_tid][0] if len(teams_in_game) == 2 else None
        if away_tid is None and home_tid is not None:
            away_tid = [t for t in teams_in_game if t != home_tid][0] if len(teams_in_game) == 2 else None

        # Team scores from team totals
        team_scores = {}
        for _, tr in tdf.iterrows():
            team_scores[tr["teamId"]] = {
                "tricode": tr["teamTricode"],
                "points": tr["points"],
            }

        home_score = team_scores.get(home_tid, {}).get("points", 0)
        away_score = team_scores.get(away_tid, {}).get("points", 0)
        home_tricode = team_scores.get(home_tid, {}).get("tricode", "")
        away_tricode = team_scores.get(away_tid, {}).get("tricode", "")

        # Determine starters (first 5 per team by position in box score order)
        starters_by_team = {}
        for tid in teams_in_game:
            team_players = pdf[pdf["teamId"] == tid]
            # Players with non-empty position are typically starters in V3
            starters = team_players.head(5)["personId"].tolist()
            starters_by_team[tid] = set(starters)

        # Parse player rows
        for _, pr in pdf.iterrows():
            tid = pr["teamId"]
            pid = pr["personId"]
            opp_tid = away_tid if tid == home_tid else home_tid
            opp_tricode = away_tricode if tid == home_tid else home_tricode
            ha = "HOME" if tid == home_tid else "AWAY"

            mins = minutes_to_decimal(pr.get("minutes", "0:00"))
            is_starter = pid in starters_by_team.get(tid, set())
            is_dnp = mins == 0.0

            pts = int(pr.get("points", 0) or 0)
            reb = int(pr.get("reboundsTotal", 0) or 0)
            ast = int(pr.get("assists", 0) or 0)

            player_rows.append({
                "game_id": gid,
                "team_id": tid,
                "team_abbreviation": pr.get("teamTricode", ""),
                "TEAM_CITY": pr.get("teamCity", ""),
                "player_id": pid,
                "player_name": f"{pr.get('firstName', '')} {pr.get('familyName', '')}".strip(),
                "NICKNAME": None,
                "COMMENT": pr.get("comment", "") or None,
                "fgm": float(pr.get("fieldGoalsMade", 0) or 0),
                "fga": float(pr.get("fieldGoalsAttempted", 0) or 0),
                "fg_pct": float(pr.get("fieldGoalsPercentage", 0) or 0),
                "fg3m": float(pr.get("threePointersMade", 0) or 0),
                "fg3a": float(pr.get("threePointersAttempted", 0) or 0),
                "fg3_pct": float(pr.get("threePointersPercentage", 0) or 0),
                "ftm": float(pr.get("freeThrowsMade", 0) or 0),
                "fta": float(pr.get("freeThrowsAttempted", 0) or 0),
                "ft_pct": float(pr.get("freeThrowsPercentage", 0) or 0),
                "rebounds_offensive": float(pr.get("reboundsOffensive", 0) or 0),
                "rebounds_defensive": float(pr.get("reboundsDefensive", 0) or 0),
                "rebounds_total": reb,
                "assists": ast,
                "steals": float(pr.get("steals", 0) or 0),
                "blocks": float(pr.get("blocks", 0) or 0),
                "turnovers": float(pr.get("turnovers", 0) or 0),
                "personal_fouls": float(pr.get("foulsPersonal", 0) or 0),
                "points": pts,
                "plus_minus": float(pr.get("plusMinusPoints", 0) or 0),
                "season": season,
                "game_date": game_date,
                "season_type": "Regular Season",
                "minutes": round(mins, 2),
                "started": is_starter,
                "starter_proxy_minutes20": mins >= 20,
                "pra": pts + reb + ast,
                "pr": pts + reb,
                "pa": pts + ast,
                "ra": reb + ast,
                "dnp": is_dnp,
                "dnp_reconstructed": False,
                "home_away": ha,
                "opponent_team_id": float(opp_tid) if opp_tid else np.nan,
                "opponent_team_abbreviation": opp_tricode,
            })

        # Parse team rows (one per team per game)
        for _, tr in tdf.iterrows():
            tid = tr["teamId"]
            opp_tid = away_tid if tid == home_tid else home_tid
            ha = "HOME" if tid == home_tid else "AWAY"
            team_pts = int(tr.get("points", 0) or 0)
            opp_pts = team_scores.get(opp_tid, {}).get("points", 0)
            wl = team_info.get((gid, tid), {}).get("wl", "")

            team_rows.append({
                "team_id": tid,
                "team_abbreviation": tr.get("teamTricode", ""),
                "game_id": gid,
                "game_date": game_date,
                "home_away": ha,
                "points_scored": team_pts,
                "points_allowed": int(opp_pts),
                "win_loss": wl,
                "season": season,
                "season_type": "Regular Season",
            })

        # Game index row
        game_index_rows.append({
            "game_id": gid,
            "game_date": game_date,
            "home_team_id": home_tid,
            "home_team_abbreviation": home_tricode,
            "away_team_id": away_tid,
            "away_team_abbreviation": away_tricode,
            "home_score": int(home_score),
            "away_score": int(away_score),
            "season": season,
            "season_type": "Regular Season",
        })

        print(f"  Parsed {gid}: {away_tricode}@{home_tricode} {away_score}-{home_score} "
              f"({len(pdf)} players)", flush=True)

    return player_rows, team_rows, game_index_rows


def run(update_date=None):
    """Update data for games played on update_date (yesterday by default)."""
    if update_date is None:
        update_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"WNBA Season Updater | {update_date} | mode={RUN_MODE}", flush=True)

    # Load existing files
    pgl_path = DATA_DIR / "player_game_logs.parquet"
    enr_path = DATA_DIR / "player_game_logs_enriched.parquet"
    tgl_path = DATA_DIR / "team_game_logs.parquet"
    gi_path = DATA_DIR / "game_index.parquet"

    pgl = pd.read_parquet(pgl_path)
    enr = pd.read_parquet(enr_path)
    tgl = pd.read_parquet(tgl_path)
    gi = pd.read_parquet(gi_path)

    for df in [pgl, enr, tgl, gi]:
        if "game_date" in df.columns:
            df["game_date"] = pd.to_datetime(df["game_date"])

    # Check if update_date already in enriched data
    existing_dates = enr["game_date"].dt.strftime("%Y-%m-%d").unique()
    if update_date in existing_dates:
        print(f"Data for {update_date} already exists ({(enr['game_date'].dt.strftime('%Y-%m-%d') == update_date).sum()} rows). Skipping fetch.", flush=True)
    elif RUN_MODE == "test":
        print(f"TEST MODE: skipping live fetch for {update_date}.", flush=True)
    else:
        player_rows, team_rows, gi_rows = _fetch_box_scores(update_date)

        if not player_rows:
            print("No completed games found. Exiting.", flush=True)
            return

        new_players = pd.DataFrame(player_rows)
        new_teams = pd.DataFrame(team_rows)
        new_gi = pd.DataFrame(gi_rows)

        # ── Append to player_game_logs ──
        pre_pgl = len(pgl)
        pgl_cols = pgl.columns.tolist()
        for c in pgl_cols:
            if c not in new_players.columns:
                new_players[c] = np.nan
        new_players = new_players[pgl_cols]
        pgl = pd.concat([pgl, new_players], ignore_index=True)
        pgl = pgl.drop_duplicates(subset=["game_id", "player_id"], keep="last")
        print(f"  player_game_logs: {pre_pgl} -> {len(pgl)} (+{len(pgl)-pre_pgl} net, {len(new_players)} parsed)", flush=True)

        # ── Append to player_game_logs_enriched ──
        pre_enr = len(enr)
        enr_cols = enr.columns.tolist()
        for c in enr_cols:
            if c not in new_players.columns:
                new_players[c] = np.nan
        # Enriched has extra team/rolling columns — fill with nan for now, recompute below
        new_enr = new_players.reindex(columns=enr_cols)
        enr = pd.concat([enr, new_enr], ignore_index=True)
        enr = enr.drop_duplicates(subset=["game_id", "player_id"], keep="last")
        print(f"  enriched: {pre_enr} -> {len(enr)} (+{len(enr)-pre_enr} net)", flush=True)

        # ── Fill enriched team context columns ──
        new_mask = enr["game_date"].dt.strftime("%Y-%m-%d") == update_date
        for _, tr in new_teams.iterrows():
            gid = tr["game_id"]
            tid = tr["team_id"]
            mask = new_mask & (enr["game_id"] == gid) & (enr["team_id"] == tid)
            opp_tid = [t["team_id"] for _, t in pd.DataFrame(team_rows).iterrows()
                       if t["game_id"] == gid and t["team_id"] != tid]
            opp_pts = [t["points_scored"] for _, t in pd.DataFrame(team_rows).iterrows()
                       if t["game_id"] == gid and t["team_id"] != tid]
            enr.loc[mask, "team_points_scored"] = tr["points_scored"]
            enr.loc[mask, "team_points_allowed"] = tr["points_allowed"]
            enr.loc[mask, "team_win_loss"] = tr["win_loss"]
            if opp_pts:
                enr.loc[mask, "opponent_points_scored"] = opp_pts[0]
                enr.loc[mask, "opponent_points_allowed"] = tr["points_scored"]

        # ── Append to team_game_logs ──
        pre_tgl = len(tgl)
        tgl_cols = tgl.columns.tolist()
        for c in tgl_cols:
            if c not in new_teams.columns:
                new_teams[c] = np.nan
        new_teams = new_teams[tgl_cols]
        tgl = pd.concat([tgl, new_teams], ignore_index=True)
        tgl = tgl.drop_duplicates(subset=["game_id", "team_id"], keep="last")
        print(f"  team_game_logs: {pre_tgl} -> {len(tgl)} (+{len(tgl)-pre_tgl} net)", flush=True)

        # ── Append to game_index ──
        pre_gi = len(gi)
        gi_cols = gi.columns.tolist()
        for c in gi_cols:
            if c not in new_gi.columns:
                new_gi[c] = np.nan
        new_gi = new_gi[gi_cols]
        gi = pd.concat([gi, new_gi], ignore_index=True)
        gi = gi.drop_duplicates(subset=["game_id"], keep="last")
        print(f"  game_index: {pre_gi} -> {len(gi)} (+{len(gi)-pre_gi} net)", flush=True)

        # ── Compute rest_days, back_to_back, season_game_num for new team rows ──
        tgl = tgl.sort_values(["team_id", "game_date"]).reset_index(drop=True)
        for tid in tgl[tgl["game_date"].dt.strftime("%Y-%m-%d") == update_date]["team_id"].unique():
            team_games = tgl[tgl["team_id"] == tid].sort_values("game_date")
            prev_game = team_games[team_games["game_date"] < pd.Timestamp(update_date)]
            today_idx = team_games[team_games["game_date"].dt.strftime("%Y-%m-%d") == update_date].index
            if len(prev_game) > 0 and len(today_idx) > 0:
                last_date = prev_game["game_date"].iloc[-1]
                rest = (pd.Timestamp(update_date) - last_date).days
                tgl.loc[today_idx, "rest_days"] = float(rest)
                tgl.loc[today_idx, "back_to_back"] = rest <= 1
            else:
                tgl.loc[today_idx, "rest_days"] = np.nan
                tgl.loc[today_idx, "back_to_back"] = False
            # Season record
            season_team = team_games[team_games["season"] == int(update_date[:4])].sort_values("game_date")
            for j, (idx, row) in enumerate(season_team.iterrows()):
                gn = j + 1
                wins = (season_team.iloc[:j+1]["win_loss"] == "W").sum()
                losses = gn - wins
                tgl.loc[idx, "season_game_num"] = float(gn)
                tgl.loc[idx, "season_wins"] = float(wins)
                tgl.loc[idx, "season_losses"] = float(losses)
                tgl.loc[idx, "season_record"] = f"{wins}-{losses}"

        # ── Compute rest_days/b2b for game_index from team_game_logs ──
        for _, gir in gi[gi["game_date"].dt.strftime("%Y-%m-%d") == update_date].iterrows():
            gidx = gir.name
            for side in ["home", "away"]:
                tid = gir[f"{side}_team_id"]
                team_tgl = tgl[tgl["team_id"] == tid].sort_values("game_date")
                row = team_tgl[team_tgl["game_id"] == gir["game_id"]]
                if len(row) > 0:
                    gi.loc[gidx, f"{side}_rest_days"] = row.iloc[0].get("rest_days", np.nan)
                    gi.loc[gidx, f"{side}_b2b"] = row.iloc[0].get("back_to_back", False)

        # ── Also fill rest_days/b2b on enriched player rows ──
        for _, tr in tgl[tgl["game_date"].dt.strftime("%Y-%m-%d") == update_date].iterrows():
            mask = (enr["game_date"].dt.strftime("%Y-%m-%d") == update_date) & (enr["team_id"] == tr["team_id"])
            enr.loc[mask, "rest_days"] = tr.get("rest_days", np.nan)
            enr.loc[mask, "back_to_back"] = tr.get("back_to_back", False)

        # ── Write all files ──
        _backup(pgl_path)
        pgl.to_parquet(pgl_path, index=False)
        _backup(enr_path)
        enr.to_parquet(enr_path, index=False)
        _backup(tgl_path)
        tgl.to_parquet(tgl_path, index=False)
        _backup(gi_path)
        gi.to_parquet(gi_path, index=False)
        print(f"  All files written.", flush=True)

    # ── Recompute rolling features for players who played on update_date ──
    enr = pd.read_parquet(enr_path)
    enr["game_date"] = pd.to_datetime(enr["game_date"])
    played = enr[(enr["game_date"].dt.strftime("%Y-%m-%d") == update_date) & (enr["minutes"] > 0)]
    affected_players = played["player_id"].unique()
    print(f"Affected players: {len(affected_players)}", flush=True)

    if len(affected_players) == 0:
        print("No players to update rolling features. Exiting.", flush=True)
        return

    all_played = enr[enr["minutes"] > 0].copy()
    all_played = all_played.sort_values(["player_id", "game_date"])

    update_count = 0
    for pid in affected_players:
        pp = all_played[all_played["player_id"] == pid].sort_values("game_date")
        if len(pp) < 2:
            continue
        last_idx = pp.index[-1]
        prior = pp.iloc[:-1]
        l5 = prior.tail(5)["minutes"].mean() if len(prior) >= 1 else np.nan
        l8 = prior.tail(8)["minutes"].mean() if len(prior) >= 1 else np.nan
        sr5 = prior.tail(5)["started"].mean() if len(prior) >= 1 else np.nan
        sr8 = prior.tail(8)["started"].mean() if len(prior) >= 1 else np.nan

        enr.loc[last_idx, "rolling_avg_min_L5"] = round(l5, 2) if pd.notna(l5) else np.nan
        enr.loc[last_idx, "rolling_avg_min_L8"] = round(l8, 2) if pd.notna(l8) else np.nan
        enr.loc[last_idx, "rolling_role_L5"] = assign_role(sr5, l5) if pd.notna(sr5) else None
        enr.loc[last_idx, "rolling_role_L8"] = assign_role(sr8, l8) if pd.notna(sr8) else None
        enr.loc[last_idx, "rolling_start_rate_L5"] = round(sr5, 3) if pd.notna(sr5) else np.nan
        enr.loc[last_idx, "rolling_start_rate_L8"] = round(sr8, 3) if pd.notna(sr8) else np.nan
        enr.loc[last_idx, "rolling_role_numeric_L5"] = ROLE_ORDER.get(assign_role(sr5, l5), 0) if pd.notna(sr5) else np.nan
        enr.loc[last_idx, "rolling_role_numeric_L8"] = ROLE_ORDER.get(assign_role(sr8, l8), 0) if pd.notna(sr8) else np.nan
        update_count += 1

    enr.to_parquet(enr_path, index=False)
    print(f"Updated rolling features for {update_count} players", flush=True)

    # Final state
    print(f"\nFinal state:", flush=True)
    print(f"  enriched: {len(enr)} rows, max_date={enr['game_date'].max()}", flush=True)
    print(f"  2026 rows: {(enr['game_date'].dt.year == 2026).sum()}", flush=True)

    with open(SHADOW_DIR / "p6_shadow_log.txt", "a") as f:
        f.write(f"{datetime.now().isoformat()} | season_updater | {update_date} | "
                f"{update_count} players updated | mode={RUN_MODE}\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    args = parser.parse_args()
    run(update_date=args.date)
