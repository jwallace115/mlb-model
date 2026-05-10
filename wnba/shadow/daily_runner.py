#!/usr/bin/env python3
"""WNBA Shadow System — Daily Projection Runner (Component 1)
Runs: 11:00 AM ET each game day
"""
import os, sys, json, time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

DATA_DIR = Path("wnba/data")
SHADOW_DIR = Path("wnba/shadow")
FIXTURE_DIR = SHADOW_DIR / "test_fixtures"

RUN_MODE = os.environ.get("RUN_MODE", "test")

# Odds API
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass
API_KEY = os.environ.get("ODDS_API_KEY", "")

WNBA_SPORT = "basketball_wnba"
PROP_MARKETS = "player_points,player_rebounds,player_assists,player_points_rebounds_assists"
PREFERRED_BOOKS = ["draftkings", "fanduel", "betmgm", "betrivers", "williamhill_us"]

STAT_MAP = {
    "player_points": "points",
    "player_rebounds": "rebounds",
    "player_assists": "assists",
    "player_points_rebounds_assists": "pra",
}

FLOORS = {"points": 3.0, "rebounds": 1.8, "assists": 1.5, "pra": 4.0}
CAPS = {"points": 999, "rebounds": 6.0, "assists": 5.0, "pra": 10.0}


def american_to_implied(odds):
    if pd.isna(odds) or odds == 0: return np.nan
    return 100 / (odds + 100) if odds > 0 else abs(odds) / (abs(odds) + 100)


def american_to_decimal(odds):
    if pd.isna(odds) or odds == 0: return np.nan
    return (odds / 100) + 1 if odds > 0 else (100 / abs(odds)) + 1


def assign_role(start_rate, avg_minutes, gp=99):
    if gp < 5: return "Deep Bench"
    if start_rate >= 0.80 and avg_minutes >= 28: return "Starter-Heavy"
    if start_rate >= 0.50 and avg_minutes >= 22: return "Starter"
    if start_rate < 0.50 and avg_minutes >= 14: return "Rotation"
    if avg_minutes >= 7: return "Bench"
    return "Deep Bench"


def run(run_date=None, test_fixture=None):
    """Main daily runner. run_date: 'YYYY-MM-DD' string."""
    if run_date is None:
        run_date = datetime.now().strftime("%Y-%m-%d")
    run_ts = datetime.now().isoformat()
    print("=" * 60, flush=True)
    print("WNBA Shadow — Daily Runner | %s | mode=%s" % (run_date, RUN_MODE), flush=True)
    print("=" * 60, flush=True)

    # ── Step 1A: Fetch props ──
    if RUN_MODE == "test":
        fixture_path = test_fixture or FIXTURE_DIR / "odds_snapshot_20240628.json"
        with open(fixture_path) as f:
            raw_data = json.load(f)
        events = raw_data.get("data", [])
        print("TEST MODE: loaded %d events from fixture" % len(events), flush=True)
    else:
        import requests
        r = requests.get("https://api.the-odds-api.com/v4/sports/%s/odds" % WNBA_SPORT,
                         params={"apiKey": API_KEY, "regions": "us", "markets": PROP_MARKETS,
                                 "oddsFormat": "american"}, timeout=20)
        if r.status_code != 200:
            print("No games or API error: %d" % r.status_code, flush=True)
            return
        events = r.json()
        print("LIVE: %d events, credits remaining: %s" % (len(events), r.headers.get("x-requests-remaining")), flush=True)

    if not events:
        print("No events. Exiting.", flush=True)
        return

    # ── Step 1B: Extract prop lines ──
    prop_rows = []
    for event in events:
        eid = event.get("id", "")
        home = event.get("home_team", "")
        away = event.get("away_team", "")
        commence = event.get("commence_time", "")
        for bk in event.get("bookmakers", []):
            bk_key = bk.get("key", "")
            for mkt in bk.get("markets", []):
                mkt_key = mkt.get("key", "")
                outcomes = mkt.get("outcomes", [])
                # Group by description (player name) + point (line)
                by_player_line = {}
                for o in outcomes:
                    desc = o.get("description", "")
                    point = o.get("point", o.get("line", np.nan))
                    key = (desc, point)
                    by_player_line.setdefault(key, {})[o["name"].lower()] = o.get("price")
                for (player_api, line), sides in by_player_line.items():
                    if not player_api: continue
                    prop_rows.append({
                        "api_name": player_api, "game_id": eid, "game_date": run_date,
                        "commence_time": commence, "home_team": home, "away_team": away,
                        "market": mkt_key, "line": line,
                        "over_odds": sides.get("over"), "under_odds": sides.get("under"),
                        "bookmaker": bk_key,
                    })

    props = pd.DataFrame(prop_rows)
    if len(props) == 0:
        print("No prop lines extracted. Exiting.", flush=True)
        return

    # Best price aggregation
    agg_rows = []
    for (api_name, gid, market, line), grp in props.groupby(["api_name", "game_id", "market", "line"]):
        over_valid = grp[grp["over_odds"].notna()]
        under_valid = grp[grp["under_odds"].notna()]
        best_over = over_valid.loc[over_valid["over_odds"].idxmax()] if len(over_valid) > 0 else None
        best_under = under_valid.loc[under_valid["under_odds"].idxmax()] if len(under_valid) > 0 else None
        agg_rows.append({
            "api_name": api_name, "game_id": gid, "game_date": run_date, "market": market, "line": line,
            "home_team": grp.iloc[0]["home_team"], "away_team": grp.iloc[0]["away_team"],
            "commence_time": grp.iloc[0]["commence_time"],
            "best_over_odds": best_over["over_odds"] if best_over is not None else np.nan,
            "best_over_book": best_over["bookmaker"] if best_over is not None else None,
            "best_under_odds": best_under["under_odds"] if best_under is not None else np.nan,
            "best_under_book": best_under["bookmaker"] if best_under is not None else None,
        })
    best_prices = pd.DataFrame(agg_rows)
    n_players = best_prices["api_name"].nunique()
    n_markets = best_prices["market"].nunique()
    print("Props: %d lines, %d players, %d markets" % (len(best_prices), n_players, n_markets), flush=True)

    # ── Step 1C: Player name matching ──
    enr = pd.read_parquet(DATA_DIR / "player_game_logs_enriched.parquet")
    all_players = enr[["player_id", "player_name"]].drop_duplicates()
    name_to_id = dict(zip(all_players["player_name"].str.lower(), all_players["player_id"]))

    map_file = SHADOW_DIR / "player_name_map.parquet"
    if map_file.exists():
        name_map = pd.read_parquet(map_file)
    else:
        name_map = pd.DataFrame(columns=["api_name", "player_id", "player_name", "match_method", "confirmed", "created_date"])

    existing_map = dict(zip(name_map["api_name"].str.lower(), name_map["player_id"]))

    api_names = best_prices["api_name"].unique()
    exact, fuzzy_new, unmatched_names = 0, 0, []
    new_map_rows = []

    try:
        from rapidfuzz import fuzz, process as rfprocess
        has_fuzzy = True
    except ImportError:
        has_fuzzy = False

    for api_name in api_names:
        key = api_name.lower()
        if key in existing_map:
            exact += 1
            continue
        # Direct match
        if key in name_to_id:
            new_map_rows.append({"api_name": api_name, "player_id": name_to_id[key],
                                 "player_name": api_name, "match_method": "exact",
                                 "confirmed": True, "created_date": run_date})
            exact += 1
            continue
        # Fuzzy
        if has_fuzzy:
            match = rfprocess.extractOne(key, list(name_to_id.keys()), scorer=fuzz.ratio, score_cutoff=85)
            if match:
                matched_name, score, _ = match
                pid = name_to_id[matched_name]
                real_name = all_players[all_players["player_id"] == pid].iloc[0]["player_name"]
                new_map_rows.append({"api_name": api_name, "player_id": pid,
                                     "player_name": real_name, "match_method": "fuzzy",
                                     "confirmed": False, "created_date": run_date})
                fuzzy_new += 1
                print("  Fuzzy: '%s' -> '%s' (%.0f%%)" % (api_name, real_name, score), flush=True)
                continue
        unmatched_names.append(api_name)

    if new_map_rows:
        new_df = pd.DataFrame(new_map_rows)
        name_map = pd.concat([name_map, new_df], ignore_index=True).drop_duplicates(subset=["api_name"])
    name_map.to_parquet(map_file, index=False)
    full_map = dict(zip(name_map["api_name"].str.lower(), name_map["player_id"]))

    print("Matching: exact=%d, fuzzy=%d, unmatched=%d" % (exact, fuzzy_new, len(unmatched_names)), flush=True)
    if unmatched_names:
        print("  Unmatched: %s" % unmatched_names[:10], flush=True)

    # Map player_id to best_prices
    best_prices["player_id"] = best_prices["api_name"].str.lower().map(full_map)
    matched = best_prices[best_prices["player_id"].notna()].copy()
    matched["player_id"] = matched["player_id"].astype(int)
    print("Matched props: %d/%d" % (len(matched), len(best_prices)), flush=True)

    if len(matched) == 0:
        print("No matched props. Exiting.", flush=True)
        return

    # ── Step 1D: Build pregame features ──
    # HARD RULE: filter to game_date < run_date
    cutoff = pd.Timestamp(run_date)
    enr["game_date"] = pd.to_datetime(enr["game_date"])
    prior = enr[(enr["game_date"] < cutoff) & (enr["minutes"] > 0)].copy()
    prior = prior.sort_values(["player_id", "game_date"])

    # Current season
    # Determine current season from run_date
    run_year = int(run_date[:4])
    run_month = int(run_date[5:7])
    current_season = run_year if run_month >= 4 else run_year - 1

    features = {}
    player_ids = matched["player_id"].unique()
    roles_df = pd.read_parquet(DATA_DIR / "role_classifications.parquet")
    var_profiles = pd.read_parquet(DATA_DIR / "player_variance_profiles.parquet")
    changes = pd.read_parquet(DATA_DIR / "role_change_log.parquet")

    for pid in player_ids:
        pp = prior[prior["player_id"] == pid]
        pp_season = pp[pp["season"] == current_season]

        f = {"player_id": pid, "low_history": False}

        if len(pp_season) >= 3:
            recent = pp_season.tail(8)
            l5 = pp_season.tail(5)["minutes"].mean() if len(pp_season) >= 5 else pp_season["minutes"].mean()
            l8 = recent["minutes"].mean()
            season_avg = pp_season["minutes"].mean()
            f["rolling_avg_min_L5"] = l5
            f["rolling_avg_min_L8"] = l8
            f["season_avg_minutes"] = season_avg

            # Role
            sr5 = pp_season.tail(5)["started"].mean() if len(pp_season) >= 5 else pp_season["started"].mean()
            f["rolling_role_L5"] = assign_role(sr5, l5)

            sr8 = recent["started"].mean()
            f["rolling_role_L8"] = assign_role(sr8, l8)

            # Stat rates (cumulative career through yesterday)
            total_pts = pp["points"].sum()
            total_reb = pp["rebounds_total"].sum()
            total_ast = pp["assists"].sum()
            total_min = pp["minutes"].sum()
            if total_min > 0:
                f["career_pts_pm"] = total_pts / total_min
                f["career_reb_pm"] = total_reb / total_min
                f["career_ast_pm"] = total_ast / total_min
                f["career_pra_pm"] = (total_pts + total_reb + total_ast) / total_min

            # Role-specific rates
            starters = pp[pp["started"] == True]
            bench = pp[pp["started"] == False]
            for label, sub in [("starter", starters), ("bench", bench)]:
                if len(sub) >= 10 and sub["minutes"].sum() > 0:
                    tm = sub["minutes"].sum()
                    f[label + "_pts_pm"] = sub["points"].sum() / tm
                    f[label + "_reb_pm"] = sub["rebounds_total"].sum() / tm
                    f[label + "_ast_pm"] = sub["assists"].sum() / tm
                    f[label + "_pra_pm"] = (sub["points"].sum() + sub["rebounds_total"].sum() + sub["assists"].sum()) / tm

            # Rolling std (L20 residuals)
            if len(pp_season) >= 10:
                recent20 = pp_season.tail(20)
                for stat, proj_col, rate_key in [
                    ("pra", "pra", "career_pra_pm"), ("points", "points", "career_pts_pm"),
                    ("rebounds", "rebounds_total", "career_reb_pm"), ("assists", "assists", "career_ast_pm")]:
                    rate = f.get(rate_key, 0)
                    if rate > 0:
                        predicted = recent20["minutes"] * rate
                        actual = recent20[proj_col]
                        f["rolling_%s_std_L20" % stat] = (actual - predicted).std()

            # Rest days
            last_game = pp_season["game_date"].max()
            f["rest_days"] = (cutoff - last_game).days

        else:
            # Fallback to prior season
            f["low_history"] = True
            prior_role = roles_df[(roles_df["player_id"] == pid) & (roles_df["season"] == current_season - 1)]
            if len(prior_role) > 0:
                f["rolling_avg_min_L5"] = prior_role.iloc[0]["avg_minutes"]
                f["rolling_avg_min_L8"] = prior_role.iloc[0]["avg_minutes"]
                f["season_avg_minutes"] = prior_role.iloc[0]["avg_minutes"]
                f["rolling_role_L5"] = prior_role.iloc[0]["role_bucket"]
            else:
                f["rolling_avg_min_L5"] = 15.0
                f["rolling_avg_min_L8"] = 15.0
                f["season_avg_minutes"] = 15.0
                f["rolling_role_L5"] = "Rotation"

            if pp["minutes"].sum() > 0:
                tm = pp["minutes"].sum()
                f["career_pts_pm"] = pp["points"].sum() / tm
                f["career_reb_pm"] = pp["rebounds_total"].sum() / tm
                f["career_ast_pm"] = pp["assists"].sum() / tm
                f["career_pra_pm"] = (pp["points"].sum() + pp["rebounds_total"].sum() + pp["assists"].sum()) / tm
            f["rest_days"] = np.nan

        # Role change flag
        recent_changes = changes[(changes["player_id"] == pid) & (changes["season"] == current_season)]
        f["recent_role_change_flag"] = 0
        if len(recent_changes) > 0:
            latest_change = recent_changes["game_date"].max()
            games_since = len(pp_season[pp_season["game_date"] >= latest_change])
            if games_since <= 3:
                f["recent_role_change_flag"] = 1

        # ── Compute projections inline (Step 1E) ──
        l5 = f.get("rolling_avg_min_L5", 15)
        l8 = f.get("rolling_avg_min_L8", 15)
        sa = f.get("season_avg_minutes", 15)
        if pd.notna(l5) and pd.notna(l8):
            baseline = 0.50 * l5 + 0.30 * l8 + 0.20 * (sa if pd.notna(sa) else l5)
        else:
            baseline = sa if pd.notna(sa) else 15.0

        b2b = 1.0
        rd = f.get("rest_days")
        if pd.notna(rd) and rd == 0:
            role = f.get("rolling_role_L5", "")
            b2b = 0.94 if role in ("Starter", "Starter-Heavy") else 0.97
        final_min = round(baseline * b2b, 2)
        pace = 1.0

        role = f.get("rolling_role_L5", "Rotation")
        for stat, rate_key_s, rate_key_b, rate_key_c in [
            ("points", "starter_pts_pm", "bench_pts_pm", "career_pts_pm"),
            ("rebounds", "starter_reb_pm", "bench_reb_pm", "career_reb_pm"),
            ("assists", "starter_ast_pm", "bench_ast_pm", "career_ast_pm"),
            ("pra", "starter_pra_pm", "bench_pra_pm", "career_pra_pm"),
        ]:
            if role in ("Starter", "Starter-Heavy") and pd.notna(f.get(rate_key_s)):
                rate = 0.70 * f[rate_key_s] + 0.30 * f.get(rate_key_c, f[rate_key_s])
            elif role in ("Rotation", "Bench", "Deep Bench") and pd.notna(f.get(rate_key_b)):
                rate = 0.70 * f[rate_key_b] + 0.30 * f.get(rate_key_c, f[rate_key_b])
            else:
                rate = f.get(rate_key_c, 0)
            if pd.isna(rate): rate = 0
            f["proj_" + stat] = round(final_min * rate * pace, 2)

            rolling_std = f.get("rolling_%s_std_L20" % stat)
            if pd.notna(rolling_std):
                std = rolling_std
            else:
                vp = var_profiles[var_profiles["player_id"] == pid]
                if len(vp) > 0:
                    std = vp.iloc[0].get("career_%s_std" % stat, 5.0)
                    if pd.isna(std): std = 5.0
                else:
                    std = 5.0
            std = max(std, FLOORS.get(stat, 3.0))
            std = min(std, CAPS.get(stat, 999))
            f["std_" + stat] = round(std, 3)

        f["final_projected_minutes"] = final_min
        f["pace_factor"] = pace
        features[pid] = f

    feat_df = pd.DataFrame(features.values())

    # ── Step 1F: Edge calculation ──
    candidate_rows = []
    for _, prop in matched.iterrows():
        pid = prop["player_id"]
        f = features.get(pid, {})
        stat = STAT_MAP.get(prop["market"], "pra")
        projection = f.get("proj_" + stat, 0)
        std = f.get("std_" + stat, 5.0)
        line = prop["line"]
        if pd.isna(projection) or pd.isna(std) or pd.isna(line) or std == 0:
            continue

        p_over = 1 - norm.cdf(line, loc=projection, scale=std)
        p_under = norm.cdf(line, loc=projection, scale=std)

        best_over = prop["best_over_odds"]
        best_under = prop["best_under_odds"]

        imp_over = american_to_implied(best_over) if pd.notna(best_over) else np.nan
        imp_under = american_to_implied(best_under) if pd.notna(best_under) else np.nan

        edge_over = p_over - imp_over if pd.notna(imp_over) else np.nan
        edge_under = p_under - imp_under if pd.notna(imp_under) else np.nan

        # Kelly
        def calc_kelly(p, odds):
            if pd.isna(p) or pd.isna(odds) or p <= 0: return 0
            d = american_to_decimal(odds)
            if pd.isna(d): return 0
            b = d - 1
            k = (b * p - (1 - p)) / b if b > 0 else 0
            return min(max(k, 0) / 2, 0.05)

        kelly_over = calc_kelly(p_over, best_over)
        kelly_under = calc_kelly(p_under, best_under)

        # Classification (tightened P6a thresholds)
        proj_min = f.get("final_projected_minutes", 0)
        is_low_hist = f.get("low_history", False)

        def classify(edge, prob, side_label):
            if pd.isna(edge) or edge < 0.03 or prob < 0.54:
                return "no_bet"
            if is_low_hist:
                return "no_bet"
            if proj_min < 18:
                return "no_bet"
            if edge >= 0.08 and prob >= 0.60:
                return "strong_candidate"
            if edge >= 0.05 and prob >= 0.57:
                return "candidate"
            if edge >= 0.03 and prob >= 0.54:
                return "lean"
            return "no_bet"

        cls_over = classify(edge_over, p_over, "over")
        cls_under = classify(edge_under, p_under, "under")

        # Select side — priority: strong_candidate > candidate > lean
        TIER = {"strong_candidate": 3, "candidate": 2, "lean": 1, "no_bet": 0}
        sides = []
        for side_label, edge_val, odds_val, prob_val, kelly_val, cls_val in [
            ("over", edge_over, best_over, p_over, kelly_over, cls_over),
            ("under", edge_under, best_under, p_under, kelly_under, cls_under),
        ]:
            if TIER[cls_val] >= 1:
                sides.append((side_label, edge_val, odds_val, prob_val, kelly_val, cls_val))

        if sides:
            sel = max(sides, key=lambda x: (TIER[x[5]], x[1] if pd.notna(x[1]) else -1))
            sel_side, sel_edge, sel_odds, sel_prob, sel_kelly, sel_cls = sel
        else:
            sel_side, sel_edge, sel_odds, sel_prob, sel_kelly, sel_cls = None, np.nan, np.nan, np.nan, 0, "no_bet"

        # Get player name
        nm = name_map[name_map["player_id"] == pid]
        pname = nm.iloc[0]["player_name"] if len(nm) > 0 else prop["api_name"]

        candidate_rows.append({
            "player_id": pid, "player_name": pname,
            "game_id": prop["game_id"], "game_date": run_date,
            "commence_time": prop.get("commence_time"),
            "market": prop["market"], "line": line,
            "home_team": prop["home_team"], "away_team": prop["away_team"],
            "best_over_odds": best_over, "best_over_book": prop["best_over_book"],
            "best_under_odds": best_under, "best_under_book": prop["best_under_book"],
            "projection": projection, "std_used": std,
            "p_over": round(p_over, 4), "p_under": round(p_under, 4),
            "implied_prob_over": round(imp_over, 4) if pd.notna(imp_over) else np.nan,
            "implied_prob_under": round(imp_under, 4) if pd.notna(imp_under) else np.nan,
            "edge_over": round(edge_over, 4) if pd.notna(edge_over) else np.nan,
            "edge_under": round(edge_under, 4) if pd.notna(edge_under) else np.nan,
            "kelly_capped_over": round(kelly_over, 4),
            "kelly_capped_under": round(kelly_under, 4),
            "classification_over": cls_over,
            "classification_under": cls_under,
            "selected_side": sel_side,
            "selected_edge": round(sel_edge, 4) if pd.notna(sel_edge) else np.nan,
            "selected_odds": sel_odds,
            "selected_prob": round(sel_prob, 4) if pd.notna(sel_prob) else np.nan,
            "selected_kelly": round(sel_kelly, 4),
            "selected_classification": sel_cls,
            "projected_minutes": proj_min,
            "recent_role_change_flag": f.get("recent_role_change_flag", 0),
            "low_history": f.get("low_history", False),
            "run_timestamp": run_ts,
        })

    cand_df = pd.DataFrame(candidate_rows)

    # ── Step 1G: Write outputs ──
    # Append to prop_candidates
    pc_file = SHADOW_DIR / "prop_candidates.parquet"
    if pc_file.exists():
        existing = pd.read_parquet(pc_file)
        cand_df = pd.concat([existing, cand_df], ignore_index=True)
    cand_df.to_parquet(pc_file, index=False)

    # Daily best board — only leans and above
    board = cand_df[(cand_df["game_date"] == run_date) & (cand_df["selected_side"].notna())].copy()
    board = board[board["selected_classification"].isin(["lean", "candidate", "strong_candidate"])]
    market_order = {"player_points_rebounds_assists": 0, "player_rebounds": 1,
                    "player_assists": 2, "player_points": 3}
    tier_order = {"strong_candidate": 0, "candidate": 1, "lean": 2}
    board["mkt_order"] = board["market"].map(market_order).fillna(9)
    board["tier_order"] = board["selected_classification"].map(tier_order).fillna(9)
    board = board.sort_values(["mkt_order", "tier_order", "selected_edge"], ascending=[True, True, False])
    board = board.drop(columns=["mkt_order", "tier_order"])
    board.to_parquet(SHADOW_DIR / "daily_best_board.parquet", index=False)

    # Projections
    proj_out = feat_df[feat_df["player_id"].isin(matched["player_id"].unique())].copy()
    dp_file = SHADOW_DIR / "daily_projections.parquet"
    if dp_file.exists():
        existing = pd.read_parquet(dp_file)
        proj_out["game_date"] = run_date
        proj_out = pd.concat([existing, proj_out], ignore_index=True)
    else:
        proj_out["game_date"] = run_date
    proj_out.to_parquet(dp_file, index=False)

    # Console summary
    today_all = cand_df[cand_df["game_date"] == run_date]
    strong = board[board["selected_classification"] == "strong_candidate"]
    candidates = board[board["selected_classification"] == "candidate"]
    leans = board[board["selected_classification"] == "lean"]

    print("\n--- DAILY BOARD ---", flush=True)
    print("Date: %s | Games: %d | Players: %d | Props evaluated: %d" % (
        run_date, matched["game_id"].nunique(), n_players, len(today_all)), flush=True)
    print("Strong: %d | Candidate: %d | Lean: %d | No bet: %d" % (
        len(strong), len(candidates), len(leans),
        len(today_all) - len(strong) - len(candidates) - len(leans)), flush=True)
    print("Candidate rate: %.1f%%" % ((len(strong) + len(candidates)) / len(today_all) * 100), flush=True)

    for _, r in pd.concat([strong, candidates]).head(20).iterrows():
        print("  [%s] %-20s %s L=%.1f %5s edge=%.1f%% odds=%s proj=%.1f std=%.1f" % (
            r["selected_classification"][:6],
            str(r["player_name"])[:20], r["market"].replace("player_", "")[:4],
            r["line"], r["selected_side"], r["selected_edge"]*100,
            r["selected_odds"], r["projection"], r["std_used"]), flush=True)

    # Log
    with open(SHADOW_DIR / "p6_shadow_log.txt", "a") as f:
        f.write("\n%s | %s | games=%d players=%d strong=%d cand=%d lean=%d\n" % (
            run_ts, run_date, matched["game_id"].nunique(), n_players,
            len(strong), len(candidates), len(leans)))

    return cand_df


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    args = parser.parse_args()
    run(run_date=args.date)
