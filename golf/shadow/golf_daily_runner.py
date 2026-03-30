#!/usr/bin/env python3
"""Golf Shadow — Daily Runner. Pulls predictions + odds, computes edges, logs candidates."""
import os, sys, json, time, pickle, re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

try:
    from dotenv import load_dotenv; load_dotenv()
except Exception: pass

DG_KEY = os.environ.get("DATAGOLF_API_KEY", "")
ODDS_KEY = os.environ.get("ODDS_API_KEY", "")
DG_BASE = "https://feeds.datagolf.com"
RUN_MODE = os.environ.get("RUN_MODE", "test")

DATA = Path("golf/data/canonical")
SHADOW = Path("golf/shadow")
MODELS = Path("golf/models")
SHADOW.mkdir(parents=True, exist_ok=True)

MAJOR_IDS = {14, 33, 26, 100}
N_OUTCOMES = {"win": 1, "top_5": 5, "top_10": 10, "top_20": 20, "make_cut": None}
MARKETS_ACTIVE = ["make_cut", "top_20"]
MARKETS_PASSIVE = ["win", "top_5", "top_10"]

# Load cut model (logistic regression on dg_make_cut_prob)
_CUT_MODEL = None
_CUT_MODEL_PATH = MODELS / "cut_model.pkl"
if _CUT_MODEL_PATH.exists():
    try:
        _bundle = pickle.load(open(_CUT_MODEL_PATH, "rb"))
        _CUT_MODEL = _bundle.get("model")
        print("Cut model loaded: %s" % _bundle.get("label", "?"), flush=True)
    except Exception as e:
        print("WARNING: Could not load cut model: %s" % e, flush=True)

import requests


def dg_get(path, params=None):
    if params is None: params = {}
    params["file_format"] = "json"
    params["key"] = DG_KEY
    time.sleep(1.5)
    r = requests.get(DG_BASE + path, params=params, timeout=30)
    if r.status_code == 200:
        try: return r.json()
        except: return None
    return None


def parse_odds(s):
    if not s or s == "n/a": return np.nan
    try: return float(str(s).replace("+", ""))
    except: return np.nan


def american_to_implied(o):
    if pd.isna(o) or o == 0: return np.nan
    return 100 / (o + 100) if o > 0 else abs(o) / (abs(o) + 100)


def _cut_model_prob(market, dg_prob):
    """Apply cut model for make_cut market; pass through DG prob for others."""
    if market == "make_cut" and _CUT_MODEL is not None:
        try:
            X = pd.DataFrame({"dg_make_cut_prob": [dg_prob]})
            return float(_CUT_MODEL.predict_proba(X)[0][1])
        except Exception:
            pass
    return dg_prob


def run(capture_type="close"):
    """Run daily projection. capture_type: 'open' (Tuesday) or 'close' (Thursday)."""
    ts = datetime.now().isoformat()
    print("=" * 60, flush=True)
    print("Golf Daily Runner | %s | mode=%s | capture=%s" % (ts[:19], RUN_MODE, capture_type), flush=True)
    print("=" * 60, flush=True)

    # ── Pull predictions ──
    if RUN_MODE == "live":
        d = dg_get("/preds/pre-tournament", {"tour": "pga", "odds_format": "percent"})
        if not d:
            print("No active tournament or API error.", flush=True)
            return
        event_name = d.get("event_name", "Unknown")
        season = d.get("season") or datetime.now().year

        # Resolve event_id from schedule (pre-tournament endpoint doesn't return it)
        event_id = d.get("event_id") or 0
        if not event_id:
            sched_resp = dg_get("/get-schedule", {"tour": "pga"})
            sched_list = sched_resp.get("schedule", sched_resp) if isinstance(sched_resp, dict) else sched_resp
            if isinstance(sched_list, list):
                match = next((e for e in sched_list
                              if isinstance(e, dict) and e.get("event_name", "").lower() == event_name.lower()), None)
                if match:
                    event_id = int(match["event_id"])
                    season = int(match.get("start_date", str(season))[:4])
                    print("  Resolved event_id=%d from schedule" % event_id, flush=True)
            if not event_id:
                print("  WARNING: Could not resolve event_id for '%s'" % event_name, flush=True)

        is_major = event_id in MAJOR_IDS
        baseline = d.get("baseline_history_fit", d.get("baseline", []))
        if not baseline:
            print("Empty prediction field.", flush=True)
            return

        preds = []
        for p in baseline:
            preds.append({
                "dg_id": p.get("dg_id"), "player_name": p.get("player_name", ""),
                "dg_make_cut_prob": p.get("make_cut", 0),
                "dg_top20_prob": p.get("top_20", 0),
                "dg_top10_prob": p.get("top_10", 0),
                "dg_top5_prob": p.get("top_5", 0),
                "dg_win_prob": p.get("win", 0),
            })
        preds_df = pd.DataFrame(preds)
        print("Predictions: %s | %d players" % (event_name, len(preds_df)), flush=True)

    else:
        # Test mode: use most recent event from canonical
        preds_all = pd.read_parquet(DATA / "predictions.parquet")
        latest = preds_all.sort_values(["calendar_year", "event_id"]).groupby(
            ["event_id", "calendar_year"]).first().reset_index().iloc[-1]
        event_id = latest["event_id"]
        season = latest["calendar_year"]
        events = pd.read_parquet(DATA / "events.parquet")
        ev = events[(events["event_id"] == event_id) & (events["calendar_year"] == season)]
        event_name = ev.iloc[0]["event_name"] if len(ev) > 0 else "Test Event"
        is_major = event_id in MAJOR_IDS

        preds_df = preds_all[(preds_all["event_id"] == event_id) & (preds_all["calendar_year"] == season)].copy()
        preds_df = preds_df.rename(columns={
            "make_cut_prob": "dg_make_cut_prob", "top_20_prob": "dg_top20_prob",
            "top_10_prob": "dg_top10_prob", "top_5_prob": "dg_top5_prob",
            "win_prob": "dg_win_prob"
        })
        print("TEST: %s %d | %d players" % (event_name, season, len(preds_df)), flush=True)

    if len(preds_df) == 0:
        print("No predictions available.", flush=True)
        return

    # ── Pull odds ──
    odds_rows = []
    if RUN_MODE == "live":
        # DataGolf betting tools for all non-major events
        for market in ["make_cut", "win", "top_20", "top_5", "top_10"]:
            d = dg_get("/betting-tools/outrights", {"tour": "pga", "market": market, "odds_format": "american"})
            if not d or not isinstance(d, dict):
                continue
            odds_list = d.get("odds", [])
            for o in odds_list:
                if not isinstance(o, dict): continue
                # DraftKings column
                dk_odds = o.get("draftkings")
                if dk_odds is None: continue
                odds_rows.append({
                    "dg_id": o.get("dg_id"), "player_name": o.get("player_name", ""),
                    "market": market, "book": "draftkings",
                    "close_odds": parse_odds(dk_odds),
                })
    else:
        # Test mode: use canonical odds
        odds_all = pd.read_parquet(DATA / "odds_outrights.parquet")
        ev_odds = odds_all[(odds_all["event_id"] == event_id) & (odds_all["calendar_year"] == season) &
                           (odds_all["book"] == "draftkings")]
        for _, o in ev_odds.iterrows():
            odds_rows.append({
                "dg_id": o["dg_id"], "player_name": o.get("player_name", ""),
                "market": o["market"], "book": "draftkings",
                "close_odds": o["close_odds"],
            })

    odds_df = pd.DataFrame(odds_rows)
    if len(odds_df) == 0:
        print("No odds available.", flush=True)
        # Still log predictions without edges
    else:
        print("Odds: %d rows across %s" % (len(odds_df), sorted(odds_df["market"].unique())), flush=True)

    # ── De-vig odds ──
    if len(odds_df) > 0:
        odds_df["raw_implied"] = odds_df["close_odds"].apply(american_to_implied)
        devigged = []
        for (mkt, bk), grp in odds_df.groupby(["market", "book"]):
            grp = grp.copy()
            sum_imp = grp["raw_implied"].sum()
            n_out = N_OUTCOMES.get(mkt)
            if n_out is None:
                n_out = round(len(grp) * 0.65)
            if sum_imp > 0:
                grp["fair_prob"] = grp["raw_implied"] * n_out / sum_imp
            else:
                grp["fair_prob"] = np.nan
            devigged.append(grp)
        odds_df = pd.concat(devigged, ignore_index=True)

    # ── Compute edges ──
    log_rows = []
    for _, pred in preds_df.iterrows():
        dgid = pred["dg_id"]
        pname = pred["player_name"]

        for market in MARKETS_ACTIVE + MARKETS_PASSIVE:
            dg_col = {
                "make_cut": "dg_make_cut_prob", "top_20": "dg_top20_prob",
                "top_10": "dg_top10_prob", "top_5": "dg_top5_prob", "win": "dg_win_prob"
            }[market]
            dg_prob = pred.get(dg_col, 0)
            if pd.isna(dg_prob) or dg_prob <= 0:
                continue

            # Match odds
            player_odds = odds_df[(odds_df["dg_id"] == dgid) & (odds_df["market"] == market)]
            if len(player_odds) > 0:
                mkt_prob = player_odds.iloc[0]["fair_prob"]
                mkt_odds = player_odds.iloc[0]["close_odds"]
            else:
                mkt_prob = np.nan
                mkt_odds = np.nan

            edge = dg_prob - mkt_prob if pd.notna(mkt_prob) else np.nan
            direction = "over" if pd.notna(edge) and edge > 0 else ("under" if pd.notna(edge) else None)

            # Classification
            market_tier = "primary" if market in MARKETS_ACTIVE else "passive"
            if market_tier == "primary" and pd.notna(edge):
                if abs(edge) >= 0.08: cls = "candidate"
                elif abs(edge) >= 0.05: cls = "lean"
                else: cls = "no_bet"
            else:
                cls = "monitor"

            row = {
                "event_id": event_id, "event_name": event_name,
                "calendar_year": season, "is_major": is_major,
                "player_id": dgid, "player_name": pname,
                "dg_rank": np.nan,
                "market": market, "market_tier": market_tier,
                "dg_prob": round(dg_prob, 4),
                "model_prob": round(_cut_model_prob(market, dg_prob), 4),
                "market_prob_open": round(mkt_prob, 4) if capture_type == "open" and pd.notna(mkt_prob) else np.nan,
                "market_prob_close": round(mkt_prob, 4) if capture_type == "close" and pd.notna(mkt_prob) else np.nan,
                "close_odds": mkt_odds,
                "edge": round(edge, 4) if pd.notna(edge) else np.nan,
                "direction": direction,
                "classification": cls,
                "confidence_tier": "LOW",
                "actual_result": np.nan,
                "shadow_pnl": np.nan,
                "clv": np.nan,
                "run_timestamp": ts,
            }
            log_rows.append(row)

    log_df = pd.DataFrame(log_rows)

    # ── Save ──
    log_file = SHADOW / "golf_shadow_log.parquet"
    if log_file.exists():
        existing = pd.read_parquet(log_file)
        log_df = pd.concat([existing, log_df], ignore_index=True)
    log_df.to_parquet(log_file, index=False)

    # Daily best board (candidates + leans only, active markets)
    today = log_df[(log_df["run_timestamp"] == ts) & (log_df["classification"].isin(["candidate", "lean"]))]
    today = today.sort_values("edge", ascending=False, key=abs)
    today.to_parquet(SHADOW / "golf_daily_best_board.parquet", index=False)

    # Console output
    n_cand = (today["classification"] == "candidate").sum()
    n_lean = (today["classification"] == "lean").sum()
    print("\n--- BOARD ---", flush=True)
    print("Event: %s | Players: %d | Candidates: %d | Leans: %d" % (
        event_name, len(preds_df), n_cand, n_lean), flush=True)

    if len(today) > 0:
        print("\n%-25s | %8s | %6s | %6s | %+6s | %s" % ("Player", "Market", "Model", "Mkt", "Edge", "Cls"))
        print("-" * 75)
        for _, r in today.head(15).iterrows():
            mp = r["market_prob_close"] if pd.notna(r["market_prob_close"]) else r["market_prob_open"]
            print("%-25s | %8s | %5.1f%% | %5.1f%% | %+5.1f%% | %s" % (
                str(r["player_name"])[:25], r["market"],
                r["model_prob"] * 100, mp * 100 if pd.notna(mp) else 0,
                r["edge"] * 100 if pd.notna(r["edge"]) else 0, r["classification"]))

    return log_df


def run_matchups(capture_type="close", preds_df=None):
    """Capture matchup/3-ball odds from DG all-pairings + book matchups."""
    ts = datetime.now().isoformat()
    print("\n--- MATCHUP CAPTURE ---", flush=True)

    # DG all-pairings (DG model odds for 3-balls)
    if RUN_MODE == "live":
        d = dg_get("/betting-tools/matchups-all-pairings", {"tour": "pga", "odds_format": "american"})
        if not d or not isinstance(d, dict):
            print("No pairings available.", flush=True)
            return

        event_name = d.get("event_name", "")
        round_num = d.get("round", 1)
        season = datetime.now().year
        event_id = 0
        # Resolve event_id from schedule
        sched_resp = dg_get("/get-schedule", {"tour": "pga"})
        sched_list = sched_resp.get("schedule", sched_resp) if isinstance(sched_resp, dict) else sched_resp
        if isinstance(sched_list, list):
            match = next((e for e in sched_list
                          if isinstance(e, dict) and e.get("event_name", "").lower() == event_name.lower()), None)
            if match:
                event_id = int(match["event_id"])
                season = int(match.get("start_date", str(season))[:4])

        pairings = d.get("pairings", [])
        print("DG pairings: %s R%d, %d groups" % (event_name, round_num, len(pairings)), flush=True)

        # Also try book-specific matchup odds
        book_matchups = {}
        for mkt in ["tournament_matchups", "round_matchups", "3_balls"]:
            time.sleep(1.5)
            r = requests.get(DG_BASE + "/betting-tools/matchups",
                params={"tour": "pga", "market": mkt, "odds_format": "american",
                        "file_format": "json", "key": DG_KEY}, timeout=30)
            if r.status_code == 200:
                data = r.json()
                ml = data.get("match_list", [])
                if isinstance(ml, list) and ml and isinstance(ml[0], dict):
                    book_matchups[mkt] = ml
                    print("  %s: %d matchups from books" % (mkt, len(ml)), flush=True)
                else:
                    print("  %s: not available right now" % mkt, flush=True)

    else:
        # Test mode: use canonical matchup data for most recent event
        mm = pd.read_parquet(DATA / "odds_matchups.parquet")
        latest = mm.sort_values(["calendar_year", "event_id"]).iloc[-1]
        eid, yr = latest["event_id"], latest["calendar_year"]
        pairings_data = mm[(mm["event_id"] == eid) & (mm["calendar_year"] == yr)]
        event_name = "Test Event"
        round_num = 1
        pairings = []  # DG model pairings not in canonical
        book_matchups = {}
        print("TEST: %d matchup rows from canonical" % len(pairings_data), flush=True)

    # Load predictions for DG proxy
    if preds_df is None:
        preds_all = pd.read_parquet(DATA / "predictions.parquet")
        preds_df = preds_all.rename(columns={"win_prob": "dg_win_prob", "top_20_prob": "dg_top20_prob"})

    proxy_lookup = {}
    for _, p in preds_df.iterrows():
        dgid = p.get("dg_id")
        if dgid:
            score = 0.8 * p.get("dg_top20_prob", p.get("dg_top20", 0)) + 0.2 * p.get("dg_win_prob", p.get("dg_win", 0))
            proxy_lookup[dgid] = score

    # Process DG model pairings (3-balls with DG's own odds)
    matchup_rows = []
    for pairing in pairings:
        p1 = pairing.get("p1", {})
        p2 = pairing.get("p2", {})
        p3 = pairing.get("p3", {})

        # Skip tie entries
        if p1.get("dg_id", -1) == -1 or p2.get("dg_id", -1) == -1:
            continue

        p1_odds = parse_odds(p1.get("odds"))
        p2_odds = parse_odds(p2.get("odds"))
        p3_odds = parse_odds(p3.get("odds")) if p3.get("dg_id", -1) != -1 else np.nan

        # De-vig
        imps = [american_to_implied(p1_odds), american_to_implied(p2_odds)]
        if pd.notna(p3_odds):
            imps.append(american_to_implied(p3_odds))
        imps = [i for i in imps if pd.notna(i)]
        total = sum(imps)

        if total <= 0:
            continue

        fp1 = american_to_implied(p1_odds) / total if pd.notna(p1_odds) else np.nan
        fp2 = american_to_implied(p2_odds) / total if pd.notna(p2_odds) else np.nan

        # DG proxy
        dp1 = proxy_lookup.get(p1.get("dg_id"), 0)
        dp2 = proxy_lookup.get(p2.get("dg_id"), 0)
        ptot = dp1 + dp2
        if ptot > 0:
            dp1 /= ptot
            dp2 /= ptot

        # Determine best edge
        e1 = dp1 - fp1 if pd.notna(fp1) else 0
        e2 = dp2 - fp2 if pd.notna(fp2) else 0
        best_player = 1 if e1 >= e2 else 2
        best_edge = max(e1, e2)
        cls = "candidate" if best_edge >= 0.08 else ("lean" if best_edge >= 0.05 else "no_bet")

        matchup_rows.append({
            "event_name": event_name, "round_num": round_num,
            "match_type": "3_ball" if p3.get("dg_id", -1) != -1 else "dg_model_h2h",
            "player_1_id": p1.get("dg_id"), "player_1_name": p1.get("name", ""),
            "player_2_id": p2.get("dg_id"), "player_2_name": p2.get("name", ""),
            "player_3_id": p3.get("dg_id") if p3.get("dg_id", -1) != -1 else np.nan,
            "player_3_name": p3.get("name", "") if p3.get("dg_id", -1) != -1 else "",
            "book_name": "datagolf_model",
            "player_1_odds": p1_odds, "player_2_odds": p2_odds,
            "player_3_odds": p3_odds if pd.notna(p3_odds) else np.nan,
            "player_1_fair_prob": round(fp1, 4) if pd.notna(fp1) else np.nan,
            "player_2_fair_prob": round(fp2, 4) if pd.notna(fp2) else np.nan,
            "overround": round(total - 1.0, 4),
            "player_1_dg_proxy": round(dp1, 4),
            "player_2_dg_proxy": round(dp2, 4),
            "player_1_edge": round(e1, 4),
            "player_2_edge": round(e2, 4),
            "bet_player": best_player,
            "bet_edge": round(best_edge, 4),
            "classification": cls,
            "capture_type": capture_type,
            "capture_timestamp": ts,
            "actual_result": np.nan,
            "shadow_pnl": np.nan,
        })

    # Process book matchup data (real book odds vs DG model probability)
    # Structure: match_list[].odds.{book_key}.{p1, p2, p3}
    if RUN_MODE == "live" and book_matchups:
        book_count = 0
        for mkt_type, matches in book_matchups.items():
            for m in matches:
                odds_by_book = m.get("odds", {})
                p1_id = m.get("p1_dg_id", -1)
                p2_id = m.get("p2_dg_id", -1)
                p3_id = m.get("p3_dg_id", -1) if "p3_dg_id" in m else -1

                for book_key, book_odds in odds_by_book.items():
                    if book_key == "datagolf":
                        continue  # skip DG model odds — already in DG pairings
                    if not isinstance(book_odds, dict):
                        continue

                    bo1 = parse_odds(book_odds.get("p1"))
                    bo2 = parse_odds(book_odds.get("p2"))
                    bo3 = parse_odds(book_odds.get("p3")) if p3_id != -1 else np.nan

                    if pd.isna(bo1) or pd.isna(bo2):
                        continue

                    # De-vig
                    imps = [american_to_implied(bo1), american_to_implied(bo2)]
                    if pd.notna(bo3):
                        imps.append(american_to_implied(bo3))
                    imps = [i for i in imps if pd.notna(i)]
                    total = sum(imps)
                    if total <= 0:
                        continue

                    bfp1 = american_to_implied(bo1) / total
                    bfp2 = american_to_implied(bo2) / total

                    # DG proxy edge vs real book odds
                    dp1 = proxy_lookup.get(p1_id, 0)
                    dp2 = proxy_lookup.get(p2_id, 0)
                    ptot = dp1 + dp2
                    if p3_id != -1:
                        ptot += proxy_lookup.get(p3_id, 0)
                    if ptot > 0:
                        dp1_n = dp1 / ptot
                        dp2_n = dp2 / ptot
                    else:
                        dp1_n = dp2_n = 0

                    e1 = dp1_n - bfp1
                    e2 = dp2_n - bfp2
                    best_player = 1 if e1 >= e2 else 2
                    best_edge = max(e1, e2)
                    cls = "candidate" if best_edge >= 0.08 else ("lean" if best_edge >= 0.05 else "no_bet")

                    matchup_rows.append({
                        "event_name": event_name, "round_num": round_num,
                        "match_type": mkt_type,
                        "player_1_id": p1_id,
                        "player_1_name": m.get("p1_player_name", ""),
                        "player_2_id": p2_id,
                        "player_2_name": m.get("p2_player_name", ""),
                        "player_3_id": p3_id if p3_id != -1 else np.nan,
                        "player_3_name": m.get("p3_player_name", "") if p3_id != -1 else "",
                        "book_name": book_key,
                        "player_1_odds": bo1, "player_2_odds": bo2,
                        "player_3_odds": bo3 if pd.notna(bo3) else np.nan,
                        "player_1_fair_prob": round(bfp1, 4),
                        "player_2_fair_prob": round(bfp2, 4),
                        "overround": round(total - 1.0, 4),
                        "player_1_dg_proxy": round(dp1_n, 4),
                        "player_2_dg_proxy": round(dp2_n, 4),
                        "player_1_edge": round(e1, 4),
                        "player_2_edge": round(e2, 4),
                        "bet_player": best_player,
                        "bet_edge": round(best_edge, 4),
                        "classification": cls,
                        "capture_type": capture_type,
                        "capture_timestamp": ts,
                        "actual_result": np.nan,
                        "shadow_pnl": np.nan,
                    })
                    book_count += 1
        print("Book matchup rows added: %d" % book_count, flush=True)

    # Add event_id + calendar_year to matchup rows
    for r in matchup_rows:
        r["event_id"] = event_id if RUN_MODE == "live" else 0
        r["calendar_year"] = season if RUN_MODE == "live" else 0

    mdf = pd.DataFrame(matchup_rows)
    if len(mdf) > 0:
        mlog = SHADOW / "golf_matchup_log.parquet"
        if mlog.exists():
            existing = pd.read_parquet(mlog)
            mdf = pd.concat([existing, mdf], ignore_index=True)
        mdf.to_parquet(mlog, index=False)

        today_m = mdf[mdf["capture_timestamp"] == ts]
        n_cand = (today_m["classification"] == "candidate").sum()
        n_lean = (today_m["classification"] == "lean").sum()
        n_book = len(today_m[today_m["book_name"] != "datagolf_model"])
        n_dg = len(today_m[today_m["book_name"] == "datagolf_model"])
        print("Matchups logged: %d (DG model: %d, Book: %d) | Candidates: %d | Leans: %d" % (
            len(today_m), n_dg, n_book, n_cand, n_lean), flush=True)

        # Print top candidates
        cands = today_m[today_m["classification"].isin(["candidate", "lean"])].sort_values("bet_edge", ascending=False)
        if len(cands) > 0:
            print("\n%-20s vs %-20s | %-12s | %+6s | %s" % ("Player 1", "Player 2", "Book", "Edge", "Cls"))
            print("-" * 80)
            for _, r in cands.head(10).iterrows():
                print("%-20s vs %-20s | %-12s | %+5.1f%% | %s" % (
                    str(r["player_1_name"])[:20], str(r["player_2_name"])[:20],
                    str(r["book_name"])[:12], r["bet_edge"] * 100, r["classification"]))
    else:
        print("No matchup data captured.", flush=True)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", default="close", choices=["open", "close"])
    parser.add_argument("--include-matchups", action="store_true")
    args = parser.parse_args()
    result = run(capture_type=args.capture)
    if args.include_matchups:
        run_matchups(capture_type=args.capture)
