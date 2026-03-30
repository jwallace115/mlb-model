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

# ── G13 Wave Weather Overlay — frozen parameters ──
_G13_PATH = Path("golf/research/dynamics/g13_frozen_wave_uplifts.json")
_G13_UPLIFTS = None
_G13_CUTPOINTS = None
if _G13_PATH.exists():
    try:
        _g13_raw = json.load(open(_G13_PATH))
        _G13_CUTPOINTS = _g13_raw.get("quintile_cutpoints")
        if _G13_CUTPOINTS and len(_G13_CUTPOINTS) == 4:
            _G13_UPLIFTS = {int(k): v for k, v in _g13_raw.items() if k.isdigit()}
            print("G13 loaded: cutpoints=%s, uplifts for Q1-Q5" % [round(c, 3) for c in _G13_CUTPOINTS], flush=True)
        else:
            print("WARNING: G13 JSON missing quintile_cutpoints — G13 disabled", flush=True)
    except Exception as e:
        print("WARNING: G13 load failed: %s" % e, flush=True)


def _g13_assign_quintile(draw_edge):
    """Assign draw_edge to frozen quintile (1-5)."""
    if pd.isna(draw_edge) or _G13_CUTPOINTS is None:
        return np.nan
    for i, c in enumerate(_G13_CUTPOINTS):
        if draw_edge < c:
            return i + 1
    return 5


def _g13_get_uplift(quintile, market="make_cut"):
    """Get frozen uplift for a quintile and market."""
    if _G13_UPLIFTS is None or pd.isna(quintile):
        return 0.0
    q = int(quintile)
    entry = _G13_UPLIFTS.get(q, {})
    key = "make_cut_uplift" if market == "make_cut" else "top20_uplift"
    return entry.get(key, 0.0)


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

    # ── Pull odds (all available books) ──
    BOOK_PRIORITY = ["pinnacle", "bet365", "bovada", "betonline", "draftkings", "fanduel"]
    BOOK_META = {"dg_id", "player_name", "datagolf"}  # non-book keys

    odds_rows = []
    if RUN_MODE == "live":
        for market in ["make_cut", "win", "top_20", "top_5", "top_10"]:
            d = dg_get("/betting-tools/outrights", {"tour": "pga", "market": market, "odds_format": "american"})
            if not d or not isinstance(d, dict):
                continue
            odds_list = d.get("odds", [])
            if not isinstance(odds_list, list):
                continue
            for o in odds_list:
                if not isinstance(o, dict): continue
                dgid = o.get("dg_id")
                pname = o.get("player_name", "")

                # Extract odds from all available books
                book_odds = {}
                for bk in o:
                    if bk in BOOK_META: continue
                    val = o[bk]
                    if isinstance(val, dict): continue  # skip datagolf model dict
                    parsed = parse_odds(val)
                    if pd.notna(parsed):
                        book_odds[bk] = parsed

                if not book_odds:
                    continue

                # Find best odds (highest American odds = best price for bettor)
                best_book = max(book_odds, key=book_odds.get)
                best_odds = book_odds[best_book]

                odds_rows.append({
                    "dg_id": dgid, "player_name": pname,
                    "market": market, "book": best_book,
                    "close_odds": best_odds,
                    "best_book": best_book,
                    "best_odds": best_odds,
                    "pinnacle_odds": book_odds.get("pinnacle", np.nan),
                    "dk_odds": book_odds.get("draftkings", np.nan),
                    "bet365_odds": book_odds.get("bet365", np.nan),
                    "bovada_odds": book_odds.get("bovada", np.nan),
                    "betonline_odds": book_odds.get("betonline", np.nan),
                    "fanduel_odds": book_odds.get("fanduel", np.nan),
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
        # Book coverage summary
        for bk_col in ["pinnacle_odds", "dk_odds", "bet365_odds", "bovada_odds", "betonline_odds", "fanduel_odds"]:
            if bk_col in odds_df.columns:
                n = odds_df[bk_col].notna().sum()
                print("  %s: %d players" % (bk_col.replace("_odds", ""), n), flush=True)
        if "best_book" in odds_df.columns:
            print("  Best book dist: %s" % dict(odds_df["best_book"].value_counts()), flush=True)

    # ── De-vig odds (use best_odds per player, de-vig across full field) ──
    if len(odds_df) > 0:
        odds_df["raw_implied"] = odds_df["best_odds"].apply(american_to_implied)
        devigged = []
        for mkt, grp in odds_df.groupby("market"):
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

            # Match odds (best book)
            player_odds = odds_df[(odds_df["dg_id"] == dgid) & (odds_df["market"] == market)]
            if len(player_odds) > 0:
                po = player_odds.iloc[0]
                mkt_prob = po["fair_prob"]
                mkt_odds = po["close_odds"]
                _best_book = po.get("best_book", "")
                _best_odds = po.get("best_odds", np.nan)
                _pin_odds = po.get("pinnacle_odds", np.nan)
                _dk_odds = po.get("dk_odds", np.nan)
                _b365_odds = po.get("bet365_odds", np.nan)
                _bov_odds = po.get("bovada_odds", np.nan)
                _bol_odds = po.get("betonline_odds", np.nan)
                _fd_odds = po.get("fanduel_odds", np.nan)
            else:
                mkt_prob = mkt_odds = np.nan
                _best_book = ""
                _best_odds = _pin_odds = _dk_odds = _b365_odds = np.nan
                _bov_odds = _bol_odds = _fd_odds = np.nan

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
                "best_book": _best_book,
                "best_odds": _best_odds,
                "pinnacle_odds": _pin_odds,
                "dk_odds": _dk_odds,
                "bet365_odds": _b365_odds,
                "bovada_odds": _bov_odds,
                "betonline_odds": _bol_odds,
                "fanduel_odds": _fd_odds,
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


def run_g13(log_df=None):
    """G13 Wave Weather Overlay — compute draw edges and make-cut adjustments.

    Requires:
    - Pairings with tee times from /betting-tools/matchups-all-pairings
    - Venue weather forecast from Open-Meteo
    - Frozen G13 parameters (cutpoints + uplifts)
    """
    print("\n--- G13 WAVE WEATHER OVERLAY ---", flush=True)

    if _G13_UPLIFTS is None or _G13_CUTPOINTS is None:
        print("  G13 DISABLED: frozen parameters not loaded.", flush=True)
        return

    if RUN_MODE != "live":
        print("  G13 skipped in test mode.", flush=True)
        return

    # Pull pairings with tee times
    d = dg_get("/betting-tools/matchups-all-pairings", {"tour": "pga", "odds_format": "american"})
    if not d or not isinstance(d, dict):
        print("  G13: no pairings available — skipping.", flush=True)
        return

    pairings = d.get("pairings", [])
    event_name = d.get("event_name", "")
    round_num = d.get("round", 1)

    if not pairings:
        print("  G13: empty pairings — skipping.", flush=True)
        return

    # Extract player tee times and wave assignments
    player_waves = {}
    for pairing in pairings:
        tee_time_str = pairing.get("teetime", "")
        wave = pairing.get("wave", "")
        # Determine AM/PM from tee time or wave field
        hour = None
        if tee_time_str:
            try:
                # Format: "2026-03-19 09:19" or similar
                import re as _re
                m = _re.search(r'(\d{1,2}):(\d{2})', tee_time_str)
                if m:
                    h = int(m.group(1))
                    # Check for PM indicator
                    if 'pm' in tee_time_str.lower() and h < 12:
                        h += 12
                    elif h < 6:  # likely 24h format afternoon
                        pass
                    hour = h
            except Exception:
                pass

        if hour is not None:
            player_wave = "AM" if hour < 12 else "PM"
        elif wave:
            player_wave = "AM" if wave.lower() in ("early", "am") else "PM"
        else:
            continue

        for pk in ["p1", "p2", "p3"]:
            p = pairing.get(pk, {})
            dgid = p.get("dg_id", -1)
            if dgid != -1:
                player_waves[dgid] = player_wave

    if not player_waves:
        print("  G13: could not extract wave assignments — skipping.", flush=True)
        return

    n_am = sum(1 for w in player_waves.values() if w == "AM")
    n_pm = sum(1 for w in player_waves.values() if w == "PM")
    print(f"  Waves: {n_am} AM, {n_pm} PM players (R{round_num})", flush=True)

    # Get venue weather forecast from Open-Meteo
    # Look up venue coordinates from schedule
    sched_resp = dg_get("/get-schedule", {"tour": "pga"})
    sched_list = sched_resp.get("schedule", sched_resp) if isinstance(sched_resp, dict) else sched_resp
    venue_lat, venue_lon = None, None
    if isinstance(sched_list, list):
        match = next((e for e in sched_list if isinstance(e, dict)
                      and e.get("event_name", "").lower() == event_name.lower()), None)
        if match:
            venue_lat = match.get("latitude")
            venue_lon = match.get("longitude")

    if venue_lat is None or venue_lon is None:
        print("  G13: could not resolve venue coordinates — using draw_edge=0.", flush=True)
        # Fall back to equal draw edges (no weather differential)
        for dgid in player_waves:
            player_waves[dgid] = (player_waves[dgid], 0.0)
    else:
        print(f"  Venue: {event_name} ({venue_lat}, {venue_lon})", flush=True)

        # Pull hourly weather forecast
        try:
            wx_url = "https://api.open-meteo.com/v1/forecast"
            wx_params = {
                "latitude": venue_lat, "longitude": venue_lon,
                "hourly": "windspeed_10m",
                "forecast_days": 4, "timezone": "America/New_York",
            }
            wx_resp = requests.get(wx_url, params=wx_params, timeout=15)
            wx_data = wx_resp.json()
            hourly = wx_data.get("hourly", {})
            times = hourly.get("time", [])
            winds = hourly.get("windspeed_10m", [])

            # Compute AM vs PM wind for each forecast day
            from collections import defaultdict
            daily_wind = defaultdict(lambda: {"am": [], "pm": []})
            for t, w in zip(times, winds):
                if w is None:
                    continue
                date_part = t[:10]
                hour = int(t[11:13])
                if 7 <= hour < 12:
                    daily_wind[date_part]["am"].append(w)
                elif 12 <= hour < 17:
                    daily_wind[date_part]["pm"].append(w)

            # Average across forecast days (proxy for tournament conditions)
            am_winds = []
            pm_winds = []
            for day_data in daily_wind.values():
                if day_data["am"]:
                    am_winds.extend(day_data["am"])
                if day_data["pm"]:
                    pm_winds.extend(day_data["pm"])

            avg_am_wind = np.mean(am_winds) if am_winds else 10.0
            avg_pm_wind = np.mean(pm_winds) if pm_winds else 10.0
            wind_diff = avg_pm_wind - avg_am_wind  # positive = PM windier

            print(f"  Weather: AM wind={avg_am_wind:.1f} km/h, PM wind={avg_pm_wind:.1f} km/h, diff={wind_diff:+.1f}", flush=True)

            # Convert wind differential to draw_edge
            # Scale: 1 km/h wind diff ≈ 0.15 strokes diff (empirical from research)
            WIND_TO_STROKES = 0.15
            for dgid, wave in list(player_waves.items()):
                if wave == "AM":
                    draw_edge = wind_diff * WIND_TO_STROKES  # PM windier = AM advantage
                else:
                    draw_edge = -wind_diff * WIND_TO_STROKES  # PM windier = PM disadvantage
                player_waves[dgid] = (wave, draw_edge)

        except Exception as e:
            print(f"  G13: weather fetch failed ({e}) — using draw_edge=0.", flush=True)
            for dgid in list(player_waves.keys()):
                player_waves[dgid] = (player_waves[dgid], 0.0)

    # Apply G13 overlay to shadow log
    log_file = SHADOW / "golf_shadow_log.parquet"
    if not log_file.exists():
        print("  G13: no shadow log to update.", flush=True)
        return

    log = pd.read_parquet(log_file)

    # Find rows for the current run (most recent timestamp, make_cut market)
    latest_ts = log["run_timestamp"].max()
    mask = (log["run_timestamp"] == latest_ts) & (log["market"] == "make_cut")

    g13_count = 0
    g13_signals = []
    g13_avoids = []

    for idx in log[mask].index:
        row = log.loc[idx]
        dgid = row["player_id"]
        wave_info = player_waves.get(dgid)

        if wave_info is None or isinstance(wave_info, str):
            # No wave data for this player
            log.loc[idx, "draw_edge_total"] = np.nan
            log.loc[idx, "draw_quintile"] = np.nan
            log.loc[idx, "adj_make_cut_prob"] = np.nan
            log.loc[idx, "adj_make_cut_edge"] = np.nan
            log.loc[idx, "g13_signal_flag"] = False
            log.loc[idx, "g13_avoid_flag"] = False
            continue

        wave, draw_edge = wave_info
        quintile = _g13_assign_quintile(draw_edge)
        uplift = _g13_get_uplift(quintile, "make_cut")
        adj_prob = np.clip(row["dg_prob"] + uplift, 0.02, 0.98)

        # Fair close prob for make_cut: use the market_prob_close if available
        fair_close = row.get("market_prob_close") or row.get("market_prob_open")
        if pd.isna(fair_close):
            adj_edge = np.nan
        else:
            adj_edge = adj_prob - fair_close

        # G13 reference book
        ref_book = row.get("best_book", "")
        for bk_col, bk_name in [("pinnacle_odds", "pinnacle"), ("dk_odds", "draftkings"), ("fanduel_odds", "fanduel")]:
            if pd.notna(row.get(bk_col)):
                ref_book = bk_name
                break

        # Signal/avoid flags
        signal = pd.notna(adj_edge) and adj_edge >= 0.04 and quintile in (4, 5)
        dg_edge = row["dg_prob"] - fair_close if pd.notna(fair_close) else np.nan
        avoid = quintile == 1 and pd.notna(dg_edge) and dg_edge >= 0.04

        log.loc[idx, "draw_edge_total"] = round(draw_edge, 4)
        log.loc[idx, "draw_quintile"] = quintile
        log.loc[idx, "adj_make_cut_prob"] = round(adj_prob, 4)
        log.loc[idx, "adj_make_cut_edge"] = round(adj_edge, 4) if pd.notna(adj_edge) else np.nan
        log.loc[idx, "g13_signal_flag"] = signal
        log.loc[idx, "g13_avoid_flag"] = avoid
        log.loc[idx, "g13_reference_book"] = ref_book

        if signal:
            g13_signals.append(row["player_name"])
            g13_count += 1
        if avoid:
            g13_avoids.append(row["player_name"])

    log.to_parquet(log_file, index=False)

    # Update daily best board with G13 columns
    board_file = SHADOW / "golf_daily_best_board.parquet"
    if board_file.exists():
        board = pd.read_parquet(board_file)
        # Merge G13 columns from updated log
        g13_cols = ['player_id', 'market', 'draw_edge_total', 'draw_quintile',
                    'adj_make_cut_prob', 'adj_make_cut_edge', 'g13_signal_flag',
                    'g13_avoid_flag', 'g13_reference_book']
        g13_data = log[mask & log['g13_signal_flag'].notna()][g13_cols].copy()
        if len(g13_data) > 0:
            board = board.merge(g13_data.drop(columns=['market'], errors='ignore'),
                               on='player_id', how='left', suffixes=('', '_g13'))
            board.to_parquet(board_file, index=False)

    print(f"\n  G13 Results: {g13_count} signals, {len(g13_avoids)} avoids", flush=True)
    if g13_signals:
        print(f"  Signals: {', '.join(g13_signals[:10])}", flush=True)
    if g13_avoids:
        print(f"  Avoids: {', '.join(g13_avoids[:10])}", flush=True)


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
    parser.add_argument("--skip-g13", action="store_true", help="Skip G13 wave overlay")
    args = parser.parse_args()
    result = run(capture_type=args.capture)
    if not args.skip_g13:
        run_g13(result)
    if args.include_matchups:
        run_matchups(capture_type=args.capture)
