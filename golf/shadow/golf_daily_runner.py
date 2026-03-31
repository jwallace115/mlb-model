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


# ── G14 Tail Balance Overlay — frozen parameters ──
_G14_PATH = Path("golf/research/dynamics/g14_frozen_tail_uplifts.json")
_G14 = None
if _G14_PATH.exists():
    try:
        _g14_raw = json.load(open(_G14_PATH))
        _g14_sb = _g14_raw.get("skill_band_cutpoints")
        _g14_tb = _g14_raw.get("tb_thresholds_by_band")
        _g14_up = _g14_raw.get("uplifts")
        _g14_fs = _g14_raw.get("field_strength_threshold")
        if _g14_sb and _g14_tb and _g14_up and _g14_fs is not None:
            _G14 = {"sb": _g14_sb, "tb": _g14_tb, "up": _g14_up, "fs": _g14_fs}
            print("G14 loaded: field_strength_threshold=%.4f" % _g14_fs, flush=True)
        else:
            missing = [k for k, v in [("skill_band_cutpoints", _g14_sb), ("tb_thresholds_by_band", _g14_tb),
                                       ("uplifts", _g14_up), ("field_strength_threshold", _g14_fs)] if not v]
            print("WARNING: G14 JSON missing %s — G14 disabled" % missing, flush=True)
    except Exception as e:
        print("WARNING: G14 load failed: %s" % e, flush=True)


def _g14_skill_band(sg):
    if _G14 is None: return None
    sb = _G14["sb"]
    if sg >= sb["q75"]: return "Elite"
    if sg >= sb["q50"]: return "Good"
    if sg >= sb["q25"]: return "Average"
    return "Below"


def _g14_tb_bucket(tail_balance, band):
    if _G14 is None or band is None or pd.isna(tail_balance): return None
    thresholds = _G14["tb"].get(band)
    if not thresholds: return None
    t33, t67 = thresholds
    if tail_balance >= t67: return "HIGH"
    if tail_balance >= t33: return "MEDIUM"
    return "LOW"


def _g14_uplift(band, bucket, market):
    if _G14 is None or band is None or bucket is None: return 0.0
    key = {"top_10": "top_10_uplift", "top_5": "top_5_uplift", "win": "win_uplift"}.get(market, "")
    return _G14["up"].get(band, {}).get(bucket, {}).get(key, 0.0)


# ── G15 Elite Density Top-20 Overlay — frozen parameters ──
_G15_PATH = Path("golf/research/engine_program/s2_field_compression/g15_frozen_elite_density_uplifts.json")
_G15 = None
if _G15_PATH.exists():
    try:
        _g15_raw = json.load(open(_G15_PATH))
        _g15_ed = _g15_raw.get("elite_density_cutpoints")
        _g15_up = _g15_raw.get("uplifts")
        if _g15_ed and _g15_up:
            _G15 = {"ed": _g15_ed, "up": _g15_up,
                    "skill_def": _g15_raw.get("skill_proxy_definition", ""),
                    "ed_def": _g15_raw.get("elite_density_definition", "")}
            print("G15 loaded: elite_density t33=%.4f, t67=%.4f" % (_g15_ed["t33"], _g15_ed["t67"]), flush=True)
        else:
            print("WARNING: G15 JSON missing cutpoints or uplifts — G15 disabled", flush=True)
    except Exception as e:
        print("WARNING: G15 load failed: %s" % e, flush=True)


def _g15_elite_density_bucket(ed):
    """Assign elite_density to frozen bucket."""
    if _G15 is None or pd.isna(ed): return None
    if ed >= _G15["ed"]["t67"]: return "HIGH"
    if ed >= _G15["ed"]["t33"]: return "MEDIUM"
    return "LOW"


def _g15_uplift(bucket, market="top_20"):
    """Get frozen uplift for elite density bucket."""
    if _G15 is None or bucket is None: return 0.0
    key = {"top_20": "top_20_uplift", "top_5": "top_5_uplift", "win": "win_uplift"}.get(market, "")
    return _G15["up"].get(bucket, {}).get(key, 0.0)


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


def run_g14(log_df=None):
    """G14 Tail Balance Overlay — top_10/top_5 signals from scoring shape."""
    print("\n--- G14 TAIL BALANCE OVERLAY ---", flush=True)

    if _G14 is None:
        print("  G14 DISABLED: frozen parameters not loaded.", flush=True)
        return
    if RUN_MODE != "live":
        print("  G14 skipped in test mode.", flush=True)
        return

    log_file = SHADOW / "golf_shadow_log.parquet"
    if not log_file.exists():
        print("  G14: no shadow log.", flush=True)
        return

    log = pd.read_parquet(log_file)
    latest_ts = log["run_timestamp"].max()
    latest = log[log["run_timestamp"] == latest_ts]

    # Compute field strength for this event
    event_dg_probs = latest["dg_prob"]
    if "dg_win_prob" not in latest.columns:
        # Use win market rows to compute field strength
        win_rows = latest[latest["market"] == "win"]
        if len(win_rows) >= 10:
            top30 = win_rows.nlargest(30, "dg_prob")["dg_prob"].mean()
        else:
            top30 = 0
    else:
        top30 = 0

    # Alternative: use predictions directly
    try:
        pred_live = pd.read_parquet("golf/data/canonical/predictions.parquet")
        pred_live = pred_live.rename(columns={"win_prob": "dg_win_prob"})
        # Get current event from log
        eid = latest["event_id"].iloc[0] if "event_id" in latest.columns else 0
        yr = latest["calendar_year"].iloc[0] if "calendar_year" in latest.columns else 2026
        ev_pred = pred_live[(pred_live["event_id"] == eid) & (pred_live["calendar_year"] == yr)]
        if len(ev_pred) >= 10:
            top30 = ev_pred.nlargest(30, "dg_win_prob")["dg_win_prob"].mean()
    except Exception:
        pass

    field_type = "STRONG" if top30 >= _G14["fs"] else "WEAK"
    print(f"  Field strength: {top30:.4f} (threshold: {_G14['fs']:.4f}) → {field_type}", flush=True)

    if field_type == "WEAK":
        print("  G14: weak field — signals suppressed, shadow data logged.", flush=True)

    # Load prior rounds for tail_balance computation
    try:
        rounds_all = pd.read_parquet("golf/data/canonical/player_rounds.parquet")
        events_all = pd.read_parquet("golf/data/canonical/events.parquet")
        event_order_local = events_all[["event_id", "calendar_year"]].drop_duplicates()
        if "start_date" in events_all.columns:
            event_order_local = events_all[["event_id", "calendar_year", "start_date"]].drop_duplicates()
            event_order_local["start_date"] = pd.to_datetime(event_order_local["start_date"])
            event_order_local = event_order_local.sort_values("start_date")
        else:
            event_order_local = event_order_local.sort_values(["calendar_year", "event_id"])
        event_order_local["event_seq"] = range(len(event_order_local))

        rounds_with_seq = rounds_all.merge(
            event_order_local[["event_id", "calendar_year", "event_seq"]],
            on=["event_id", "calendar_year"], how="left")

        # Current event seq
        this_ev = event_order_local[(event_order_local["event_id"] == eid) &
                                     (event_order_local["calendar_year"] == yr)]
        this_seq = this_ev["event_seq"].iloc[0] if len(this_ev) > 0 else 9999

        # Pre-compute field percentiles for prior rounds
        round_pctiles = {}
        for (reid, ryr, rrnd), grp in rounds_with_seq.groupby(["event_id", "calendar_year", "round_num"]):
            sg_v = grp["sg_total"].dropna()
            if len(sg_v) >= 20:
                round_pctiles[(reid, ryr, rrnd)] = {"p10": sg_v.quantile(0.10), "p90": sg_v.quantile(0.90)}
    except Exception as e:
        print(f"  G14: cannot load rounds data ({e})", flush=True)
        return

    # Process each player in top_10 and top_5 markets
    g14_signals = {"top_10": [], "top_5": []}
    g14_win_watch = []
    kill_counts = {"top_10": 0, "top_5": 0}
    kill_triggered = False

    for market in ["top_10", "top_5", "win"]:
        mask = (log["run_timestamp"] == latest_ts) & (log["market"] == market)
        for idx in log[mask].index:
            row = log.loc[idx]
            dgid = row["player_id"]

            # Get prior rounds
            p_rounds = rounds_with_seq[rounds_with_seq["dg_id"] == dgid]
            prior = p_rounds[p_rounds["event_seq"] < this_seq]
            sg_vals = prior["sg_total"].dropna().values

            if len(sg_vals) < 20:
                log.loc[idx, "g14_rule_fail_reason"] = "insufficient_round_history"
                log.loc[idx, "g14_rule_pass"] = False
                continue

            last50 = sg_vals[-50:]
            rolling_mean = np.mean(last50)

            # Tail balance
            top_c = bottom_c = checked = 0
            for _, rr in prior.tail(50).iterrows():
                sg = rr.get("sg_total")
                if pd.isna(sg): continue
                key = (rr["event_id"], rr["calendar_year"], rr.get("round_num"))
                pcts = round_pctiles.get(key)
                if pcts is None: continue
                checked += 1
                if sg >= pcts["p90"]: top_c += 1
                if sg <= pcts["p10"]: bottom_c += 1

            if checked < 10:
                log.loc[idx, "g14_rule_fail_reason"] = "insufficient_round_history"
                log.loc[idx, "g14_rule_pass"] = False
                continue

            tail_balance = (top_c - bottom_c) / checked
            band = _g14_skill_band(rolling_mean)
            bucket = _g14_tb_bucket(tail_balance, band)

            # Uplift
            uplift = _g14_uplift(band, bucket, market)
            adj_prob = np.clip(row["dg_prob"] + uplift, 0.01, 0.99)

            # Sanity check
            sanity_fail = False
            if market == "top_5" and adj_prob > 0.30:
                sanity_fail = True
            if market == "top_10" and adj_prob > 0.50:
                sanity_fail = True
            if sanity_fail:
                adj_prob = row["dg_prob"]
                log.loc[idx, "g14_rule_fail_reason"] = "probability_sanity_violation"
                log.loc[idx, "g14_rule_pass"] = False

            # Fair close prob
            fair_close = row.get("market_prob_close") or row.get("market_prob_open")
            if pd.isna(fair_close):
                edge = np.nan
                log.loc[idx, "g14_rule_fail_reason"] = "missing_odds"
                log.loc[idx, "g14_rule_pass"] = False
            else:
                edge = adj_prob - fair_close

            # Reference book
            ref_book = ""
            for bk_col, bk_name in [("pinnacle_odds", "pinnacle"), ("dk_odds", "draftkings"), ("fanduel_odds", "fanduel")]:
                if pd.notna(row.get(bk_col)):
                    ref_book = bk_name
                    break

            # Store
            log.loc[idx, "rolling_mean_sg_50"] = round(rolling_mean, 4)
            log.loc[idx, "tail_balance_50"] = round(tail_balance, 4)
            log.loc[idx, "skill_band"] = band
            log.loc[idx, "tb_bucket"] = bucket
            log.loc[idx, "field_type"] = field_type

            adj_col = f"adj_{market}_prob"
            edge_col = f"{market}_edge"
            log.loc[idx, adj_col] = round(adj_prob, 4)
            log.loc[idx, edge_col] = round(edge, 4) if pd.notna(edge) else np.nan
            log.loc[idx, "g14_signal_version"] = "1.0"
            log.loc[idx, "g14_shadow_mode"] = True

            # Signal flags
            if market in ("top_10", "top_5"):
                signal = (pd.notna(edge) and edge >= 0.02 and bucket == "HIGH"
                          and field_type == "STRONG" and not sanity_fail)
                flag_col = f"g14_{market}_signal"
                log.loc[idx, flag_col] = signal
                log.loc[idx, f"g14_reference_book_{market}"] = ref_book

                if signal:
                    kill_counts[market] += 1
                    g14_signals[market].append(row["player_name"])

                if not signal and not log.loc[idx].get("g14_rule_fail_reason"):
                    if field_type == "WEAK":
                        log.loc[idx, "g14_rule_fail_reason"] = "weak_field"
                    elif bucket != "HIGH":
                        log.loc[idx, "g14_rule_fail_reason"] = "tb_bucket_not_high"
                    elif pd.notna(edge) and edge < 0.02:
                        log.loc[idx, "g14_rule_fail_reason"] = "edge_below_threshold"
                    log.loc[idx, "g14_rule_pass"] = False
                elif signal:
                    log.loc[idx, "g14_rule_pass"] = True

            elif market == "win":
                watch = pd.notna(edge) and edge >= 0.02 and not sanity_fail
                log.loc[idx, "g14_win_watchlist"] = watch
                if watch:
                    g14_win_watch.append(row["player_name"])

    # Kill switch
    for mkt in ["top_10", "top_5"]:
        if kill_counts[mkt] > 25:
            kill_triggered = True
            print(f"  G14 KILL SWITCH TRIGGERED — {mkt}: {kill_counts[mkt]} signals exceeded 25", flush=True)
            flag_col = f"g14_{mkt}_signal"
            mask = (log["run_timestamp"] == latest_ts) & (log["market"] == mkt) & (log.get(flag_col, False) == True)
            log.loc[mask, flag_col] = False
            log.loc[mask, "g14_rule_fail_reason"] = "kill_switch_triggered"
            log.loc[mask, "g14_rule_pass"] = False
            g14_signals[mkt] = []

    log.to_parquet(log_file, index=False)

    # Summary
    print(f"\n  G14 Results:", flush=True)
    print(f"    Field: {field_type} ({top30:.4f})", flush=True)
    print(f"    Top 10 signals: {len(g14_signals['top_10'])}", flush=True)
    print(f"    Top 5 signals: {len(g14_signals['top_5'])}", flush=True)
    print(f"    Win watchlist: {len(g14_win_watch)}", flush=True)
    print(f"    Kill switch: {'TRIGGERED' if kill_triggered else 'OK'}", flush=True)
    if g14_signals["top_10"]:
        print(f"    T10: {', '.join(g14_signals['top_10'][:10])}", flush=True)
    if g14_signals["top_5"]:
        print(f"    T5: {', '.join(g14_signals['top_5'][:10])}", flush=True)
    if g14_win_watch:
        print(f"    Win watch: {', '.join(g14_win_watch[:10])}", flush=True)


def run_g15(log_df=None):
    """G15 Elite Density Top-20 Overlay — field structure signals."""
    print("\n--- G15 ELITE DENSITY OVERLAY ---", flush=True)

    if _G15 is None:
        print("  G15 DISABLED: frozen parameters not loaded.", flush=True)
        return
    if RUN_MODE != "live":
        print("  G15 skipped in test mode.", flush=True)
        return

    log_file = SHADOW / "golf_shadow_log.parquet"
    if not log_file.exists():
        print("  G15: no shadow log.", flush=True)
        return

    log = pd.read_parquet(log_file)
    latest_ts = log["run_timestamp"].max()
    latest = log[log["run_timestamp"] == latest_ts]

    # Compute elite_density from current field predictions
    field_probs = latest[["player_id", "dg_prob", "market"]].copy()
    # Get DG probs for skill_proxy (need top_20 and win)
    t20_rows = latest[latest["market"] == "top_20"][["player_id", "dg_prob"]].rename(columns={"dg_prob": "dg_t20"})
    win_rows = latest[latest["market"] == "win"][["player_id", "dg_prob"]].rename(columns={"dg_prob": "dg_win"})

    if len(t20_rows) == 0:
        # Fallback: use prediction file
        try:
            pred_live = pd.read_parquet("golf/data/canonical/predictions.parquet")
            pred_live = pred_live.rename(columns={"top_20_prob": "dg_t20", "win_prob": "dg_win"})
            eid = latest["event_id"].iloc[0] if "event_id" in latest.columns else 0
            yr = latest["calendar_year"].iloc[0] if "calendar_year" in latest.columns else 2026
            ev_pred = pred_live[(pred_live["event_id"] == eid) & (pred_live["calendar_year"] == yr)]
            t20_rows = ev_pred[["dg_id", "dg_t20"]].rename(columns={"dg_id": "player_id"})
            win_rows = ev_pred[["dg_id", "dg_win"]].rename(columns={"dg_id": "player_id"})
        except Exception:
            pass

    if len(t20_rows) < 20:
        print("  G15: insufficient field data for elite density.", flush=True)
        return

    skill_df = t20_rows.merge(win_rows, on="player_id", how="left")
    skill_df["skill_proxy"] = 0.8 * skill_df["dg_t20"].fillna(0) + 0.2 * skill_df["dg_win"].fillna(0)

    sp = skill_df["skill_proxy"].sort_values(ascending=False).values
    best = sp[0]
    elite_count = np.sum(sp >= best * 0.5)
    elite_density_raw = elite_count / len(sp)
    ed_bucket = _g15_elite_density_bucket(elite_density_raw)

    # Field compression metrics
    field_skill_std = np.std(sp)
    gap_1_20 = sp[0] - sp[min(19, len(sp)-1)]

    print(f"  Elite density: {elite_density_raw:.4f} → {ed_bucket}", flush=True)
    print(f"  Field: {len(sp)} players, skill_std={field_skill_std:.4f}, gap_1_20={gap_1_20:.4f}", flush=True)

    if ed_bucket != "HIGH":
        print(f"  G15: field not HIGH elite density — signals suppressed, shadow logged.", flush=True)

    # Process top_20 market rows
    mask = (log["run_timestamp"] == latest_ts) & (log["market"] == "top_20")
    g15_signals = []
    g15_count = 0

    for idx in log[mask].index:
        row = log.loc[idx]

        # Store tournament-level fields
        log.loc[idx, "elite_density_raw"] = round(elite_density_raw, 4)
        log.loc[idx, "elite_density_bucket"] = ed_bucket
        log.loc[idx, "field_skill_std"] = round(field_skill_std, 4)
        log.loc[idx, "gap_best_to_20th"] = round(gap_1_20, 4)
        log.loc[idx, "g15_signal_version"] = "1.0"
        log.loc[idx, "g15_shadow_mode"] = True

        # Uplift
        uplift = _g15_uplift(ed_bucket, "top_20")
        adj_prob = np.clip(row["dg_prob"] + uplift, 0.01, 0.99)

        # Sanity
        sanity_fail = False
        if adj_prob > 0.65:
            sanity_fail = True
            adj_prob = row["dg_prob"]

        # Fair close prob
        fair_close = row.get("market_prob_close") or row.get("market_prob_open")
        if pd.isna(fair_close):
            edge = np.nan
            log.loc[idx, "g15_rule_fail_reason"] = "missing_odds"
            log.loc[idx, "g15_rule_pass"] = False
        elif sanity_fail:
            edge = np.nan
            log.loc[idx, "g15_rule_fail_reason"] = "probability_sanity_violation"
            log.loc[idx, "g15_rule_pass"] = False
        else:
            edge = adj_prob - fair_close

        # Reference book
        ref_book = ""
        for bk_col, bk_name in [("pinnacle_odds", "pinnacle"), ("dk_odds", "draftkings"), ("fanduel_odds", "fanduel")]:
            if pd.notna(row.get(bk_col)):
                ref_book = bk_name
                break

        log.loc[idx, "adj_top_20_prob_g15"] = round(adj_prob, 4)
        log.loc[idx, "top_20_edge_g15"] = round(edge, 4) if pd.notna(edge) else np.nan
        log.loc[idx, "g15_reference_book"] = ref_book

        # Signal flag
        signal = (pd.notna(edge) and edge >= 0.04 and ed_bucket == "HIGH" and not sanity_fail)

        if signal:
            g15_count += 1
            g15_signals.append(row["player_name"])

        log.loc[idx, "g15_signal_flag"] = signal

        if not signal and not log.loc[idx].get("g15_rule_fail_reason"):
            if ed_bucket != "HIGH":
                log.loc[idx, "g15_rule_fail_reason"] = "elite_density_not_high"
            elif pd.notna(edge) and edge < 0.04:
                log.loc[idx, "g15_rule_fail_reason"] = "edge_below_threshold"
            log.loc[idx, "g15_rule_pass"] = False
        elif signal:
            log.loc[idx, "g15_rule_pass"] = True

    # Kill switch
    kill_triggered = False
    if g15_count > 12:
        kill_triggered = True
        print(f"  G15 KILL SWITCH TRIGGERED — {g15_count} signals exceeded 12", flush=True)
        log.loc[mask & (log.get("g15_signal_flag", False) == True), "g15_signal_flag"] = False
        log.loc[mask & (log.get("g15_signal_flag", False) == False), "g15_rule_fail_reason"] = "kill_switch_triggered"
        log.loc[mask, "g15_rule_pass"] = False
        g15_signals = []
        g15_count = 0

    # Watchlist: top_5 and win (if uplifts exist)
    g15_t5_watch = []
    g15_win_watch = []
    for market, result_flag, watch_list in [("top_5", "g15_top5_watchlist", g15_t5_watch),
                                             ("win", "g15_win_watchlist", g15_win_watch)]:
        m2 = (log["run_timestamp"] == latest_ts) & (log["market"] == market)
        for idx in log[m2].index:
            row = log.loc[idx]
            uplift = _g15_uplift(ed_bucket, market)
            adj = np.clip(row["dg_prob"] + uplift, 0.01, 0.99)
            fair = row.get("market_prob_close") or row.get("market_prob_open")
            edge = adj - fair if pd.notna(fair) else np.nan
            thresh = 0.04 if market == "top_5" else 0.02
            watch = pd.notna(edge) and edge >= thresh
            log.loc[idx, result_flag] = watch
            if watch:
                watch_list.append(row["player_name"])

    log.to_parquet(log_file, index=False)

    # Summary
    print(f"\n  G15 Results:", flush=True)
    print(f"    Elite density: {ed_bucket} ({elite_density_raw:.4f})", flush=True)
    print(f"    Top-20 signals: {g15_count}", flush=True)
    print(f"    Top-5 watchlist: {len(g15_t5_watch)}", flush=True)
    print(f"    Win watchlist: {len(g15_win_watch)}", flush=True)
    print(f"    Kill switch: {'TRIGGERED' if kill_triggered else 'OK'}", flush=True)
    if g15_signals:
        print(f"    Signals: {', '.join(g15_signals[:10])}", flush=True)


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


def run_composite():
    """Composite signal detection — G13 × S6(REGULAR_HARD) shadow amplifier."""
    print("\n--- COMPOSITE DETECTION ---", flush=True)

    log_file = SHADOW / "golf_shadow_log.parquet"
    if not log_file.exists():
        print("  No shadow log.", flush=True)
        return

    log = pd.read_parquet(log_file)
    latest_ts = log["run_timestamp"].max()

    # Load S6 tournament classes
    s6_path = Path("golf/research/engine_program/s6_tournament_segmentation/tournament_classes.parquet")
    if not s6_path.exists():
        print("  S6 classes not found — composite skipped.", flush=True)
        return

    s6 = pd.read_parquet(s6_path)
    if "tourn_class" not in s6.columns:
        print("  S6 missing tourn_class — composite skipped.", flush=True)
        return

    # Get current event
    latest = log[log["run_timestamp"] == latest_ts]
    if len(latest) == 0:
        return

    eid = latest["event_id"].iloc[0]
    yr = latest["calendar_year"].iloc[0]

    # Look up tournament class
    ev_class = s6[(s6["event_id"] == eid) & (s6["calendar_year"] == yr)]
    if len(ev_class) > 0:
        tourn_class = ev_class.iloc[0]["tourn_class"]
    else:
        # Try matching by event_id only (current year may not be in S6 historical data)
        # Use most recent classification for this event_id
        ev_hist = s6[s6["event_id"] == eid].sort_values("calendar_year", ascending=False)
        tourn_class = ev_hist.iloc[0]["tourn_class"] if len(ev_hist) > 0 else None

    if tourn_class is None:
        print(f"  Event {eid} not in S6 classifications — composite skipped.", flush=True)
        return

    print(f"  Tournament class: {tourn_class}", flush=True)

    # Set tourn_class and composite_flag on all current-run rows
    mask = log["run_timestamp"] == latest_ts
    log.loc[mask, "tourn_class"] = tourn_class

    composite_count = 0
    for idx in log[mask].index:
        row = log.loc[idx]
        g13_active = row.get("g13_signal_flag") is True
        is_regular_hard = tourn_class == "REGULAR_HARD"

        if g13_active and is_regular_hard:
            log.loc[idx, "composite_flag"] = "G13_S6_REGULAR_HARD"
            composite_count += 1
        else:
            log.loc[idx, "composite_flag"] = None

    log.to_parquet(log_file, index=False)

    print(f"  G13×S6(REGULAR_HARD) composite: {composite_count} signals", flush=True)
    if composite_count > 0:
        comp_rows = log[mask & (log["composite_flag"] == "G13_S6_REGULAR_HARD")]
        names = comp_rows["player_name"].tolist()
        print(f"  Players: {', '.join(names[:10])}", flush=True)


# ── CL03 Inside-Cut R1 Undervaluation — post-R1 shadow capture ──
# Known no-cut event IDs (playoff events, invitational small fields, etc.)
_NO_CUT_EVENT_IDS = {5, 11, 12, 16, 27, 28, 34, 60, 473, 476, 478, 480, 519, 521, 527, 550}
_CL03_MIN_R1_COMPLETION = 0.80  # 80% of field must have R1 scores
_CL03_CUT_POSITION = 65  # PGA standard: top 65 + ties make the cut


def _fetch_r1_scores_live(event_id, season):
    """Fetch current-event R1 scores via /historical-raw-data/rounds.

    This is a dedicated fetch for CL03 post-R1 capture only.
    Does NOT check event_completed — that gate stays in golf_grader.py.
    """
    d = dg_get("/historical-raw-data/rounds", {"tour": "pga", "event_id": int(event_id), "year": int(season)})
    if not d or not isinstance(d, dict):
        return None, None
    scores = d.get("scores", [])
    if not scores:
        return None, None

    rows = []
    for player in scores:
        dgid = player.get("dg_id")
        pname = player.get("player_name", "")
        r1 = player.get("round_1")
        if not r1 or not isinstance(r1, dict):
            continue
        r1_score = r1.get("score")
        course_par = r1.get("course_par")
        if r1_score is None:
            continue
        rows.append({
            "dg_id": dgid, "player_name": pname,
            "r1_score": int(r1_score), "course_par": int(course_par) if course_par else 72,
            "sg_total": r1.get("sg_total"),
        })
    return rows, d.get("event_name", "Unknown")


def _fetch_r1_scores_test(event_id, season):
    """Load R1 scores from canonical player_rounds for test mode."""
    pr = pd.read_parquet(DATA / "player_rounds.parquet")
    r1 = pr[(pr["event_id"] == event_id) & (pr["calendar_year"] == season) & (pr["round_num"] == 1)]
    if len(r1) == 0:
        return None, None
    rows = []
    for _, row in r1.iterrows():
        rows.append({
            "dg_id": row["dg_id"], "player_name": row["player_name"],
            "r1_score": int(row["round_score"]), "course_par": int(row["course_par"]),
            "sg_total": row.get("sg_total"),
        })
    events = pd.read_parquet(DATA / "events.parquet")
    ev = events[(events["event_id"] == event_id) & (events["calendar_year"] == season)]
    ev_name = ev.iloc[0]["event_name"] if len(ev) > 0 else "Test Event"
    return rows, ev_name


def run_cl03():
    """CL03 Inside-Cut R1 Undervaluation — post-R1 shadow capture.

    Runs ONLY in --capture post_r1 mode.
    Fetches current-event R1 scores, computes projected cut line,
    flags INSIDE_1 players, and appends CL03 fields to shadow log.

    Does NOT modify any pre-tournament or live betting logic.
    """
    ts = datetime.now().isoformat()
    print("\n" + "=" * 60, flush=True)
    print("CL03 Post-R1 Capture | %s | mode=%s" % (ts[:19], RUN_MODE), flush=True)
    print("=" * 60, flush=True)

    # ── Resolve active event ──
    if RUN_MODE == "live":
        d = dg_get("/preds/pre-tournament", {"tour": "pga", "odds_format": "percent"})
        if not d:
            print("CL03: No active tournament or API error.", flush=True)
            return
        event_name = d.get("event_name", "Unknown")
        season = d.get("season") or datetime.now().year
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
            if not event_id:
                print("CL03: Could not resolve event_id — aborting.", flush=True)
                return
    else:
        # Test mode: use most recent event from canonical
        preds_all = pd.read_parquet(DATA / "predictions.parquet")
        latest = preds_all.sort_values(["calendar_year", "event_id"]).groupby(
            ["event_id", "calendar_year"]).first().reset_index().iloc[-1]
        event_id = latest["event_id"]
        season = latest["calendar_year"]
        event_name = "Test Event"

    is_major = event_id in MAJOR_IDS

    # ── Check: standard cut event ──
    is_standard_cut = event_id not in _NO_CUT_EVENT_IDS
    if not is_standard_cut:
        print("CL03: SKIP — event_id=%d is a no-cut format event." % event_id, flush=True)
        return

    # ── Fetch R1 scores ──
    if RUN_MODE == "live":
        r1_rows, ev_name_r1 = _fetch_r1_scores_live(event_id, season)
    else:
        r1_rows, ev_name_r1 = _fetch_r1_scores_test(event_id, season)

    if not r1_rows:
        print("CL03: SKIP — no R1 scores available for event_id=%d." % event_id, flush=True)
        return

    # ── Check: R1 completion >= 80% ──
    # Estimate field size from predictions (pre-tournament) or R1 data
    if RUN_MODE == "live":
        pred_d = dg_get("/preds/pre-tournament", {"tour": "pga", "odds_format": "percent"})
        field_size = len(pred_d.get("baseline_history_fit", pred_d.get("baseline", []))) if pred_d else len(r1_rows)
    else:
        preds_all = pd.read_parquet(DATA / "predictions.parquet")
        field_size = len(preds_all[(preds_all["event_id"] == event_id) & (preds_all["calendar_year"] == season)])

    if field_size == 0:
        field_size = len(r1_rows)

    r1_completion = len(r1_rows) / field_size if field_size > 0 else 0
    print("CL03: R1 scores: %d / %d field (%.1f%% complete)" % (len(r1_rows), field_size, r1_completion * 100), flush=True)

    if r1_completion < _CL03_MIN_R1_COMPLETION:
        print("CL03: WARNING — R1 completion %.1f%% < 80%% threshold. Skipping." % (r1_completion * 100), flush=True)
        return

    # ── Compute projected cut line (65th position by R1 score) ──
    r1_df = pd.DataFrame(r1_rows)
    r1_df = r1_df.sort_values("r1_score").reset_index(drop=True)

    if len(r1_df) < _CL03_CUT_POSITION:
        print("CL03: SKIP — fewer than %d R1 scores (%d). Cannot compute cut line." % (_CL03_CUT_POSITION, len(r1_df)), flush=True)
        return

    projected_cut_line_r1 = int(r1_df.iloc[_CL03_CUT_POSITION - 1]["r1_score"])
    r1_df["distance_from_cut_r1"] = projected_cut_line_r1 - r1_df["r1_score"]

    print("CL03: Projected R1 cut line = %d (65th position)" % projected_cut_line_r1, flush=True)

    # ── Flag INSIDE_1 players (exactly 1 stroke better than cut) ──
    inside_1 = r1_df[r1_df["distance_from_cut_r1"] == 1].copy()
    print("CL03: INSIDE_1 players (1 stroke better than cut): %d" % len(inside_1), flush=True)

    if len(inside_1) > 0:
        for _, p in inside_1.iterrows():
            print("  %s: R1=%d (cut=%d, dist=%+d)" % (
                p["player_name"], p["r1_score"], projected_cut_line_r1, p["distance_from_cut_r1"]), flush=True)

    # ── Pull current make_cut odds for CL03 players ──
    mc_odds = {}
    if RUN_MODE == "live":
        d = dg_get("/betting-tools/outrights", {"tour": "pga", "market": "make_cut", "odds_format": "american"})
        if d and isinstance(d, dict):
            for o in d.get("odds", []):
                if not isinstance(o, dict):
                    continue
                dgid = o.get("dg_id")
                # Find best book odds
                book_odds = {}
                for bk in o:
                    if bk in {"dg_id", "player_name", "datagolf"}:
                        continue
                    val = o[bk]
                    if isinstance(val, dict):
                        continue
                    parsed = parse_odds(val)
                    if pd.notna(parsed):
                        book_odds[bk] = parsed
                if book_odds:
                    best_odds = max(book_odds.values())
                    mc_odds[dgid] = american_to_implied(best_odds)
            print("CL03: Make-cut odds loaded for %d players" % len(mc_odds), flush=True)
        else:
            print("CL03: WARNING — make-cut odds unavailable. Logging nulls.", flush=True)
    else:
        odds_all = pd.read_parquet(DATA / "odds_outrights.parquet")
        ev_mc = odds_all[(odds_all["event_id"] == event_id) & (odds_all["calendar_year"] == season) &
                         (odds_all["market"] == "make_cut") & (odds_all["book"] == "draftkings")]
        for _, o in ev_mc.iterrows():
            mc_odds[o["dg_id"]] = american_to_implied(o["close_odds"])

    # ── Pull DG make_cut predictions ──
    dg_mc = {}
    if RUN_MODE == "live":
        pred_d = dg_get("/preds/pre-tournament", {"tour": "pga", "odds_format": "percent"})
        if pred_d:
            for p in pred_d.get("baseline_history_fit", pred_d.get("baseline", [])):
                dg_mc[p.get("dg_id")] = p.get("make_cut", 0)
    else:
        preds_all = pd.read_parquet(DATA / "predictions.parquet")
        ev_preds = preds_all[(preds_all["event_id"] == event_id) & (preds_all["calendar_year"] == season)]
        col = "make_cut_prob" if "make_cut_prob" in ev_preds.columns else "dg_make_cut_prob"
        for _, p in ev_preds.iterrows():
            dg_mc[p["dg_id"]] = p.get(col, 0)

    # ── Update shadow log with CL03 fields ──
    log_file = SHADOW / "golf_shadow_log.parquet"
    if not log_file.exists():
        print("CL03: No shadow log exists. Cannot append CL03 fields.", flush=True)
        return

    log = pd.read_parquet(log_file)

    # Ensure CL03 columns exist (append only, never rename existing)
    for col in ["cl03_flag", "distance_from_cut_r1", "projected_cut_line_r1",
                "r1_score", "cl03_market_prob", "cl03_capture_time", "is_standard_cut_event"]:
        if col not in log.columns:
            log[col] = np.nan if col != "cl03_flag" else False

    # Find rows for this event in the latest run (make_cut market only)
    latest_ts = log["run_timestamp"].max()
    mask = ((log["run_timestamp"] == latest_ts) &
            (log["event_id"] == event_id) &
            (log["market"] == "make_cut"))

    cl03_count = 0
    # Build INSIDE_1 lookup by dg_id
    inside_1_ids = set(inside_1["dg_id"].tolist()) if len(inside_1) > 0 else set()
    r1_lookup = {row["dg_id"]: row for _, row in r1_df.iterrows()}

    for idx in log[mask].index:
        row = log.loc[idx]
        dgid = row["player_id"]

        r1_info = r1_lookup.get(dgid)
        if r1_info is None:
            # Player not in R1 scores (WD, DNS, etc.)
            log.loc[idx, "cl03_flag"] = False
            log.loc[idx, "is_standard_cut_event"] = True
            log.loc[idx, "cl03_capture_time"] = ts
            continue

        is_inside_1 = dgid in inside_1_ids
        log.loc[idx, "cl03_flag"] = is_inside_1
        log.loc[idx, "distance_from_cut_r1"] = int(r1_info["distance_from_cut_r1"])
        log.loc[idx, "projected_cut_line_r1"] = projected_cut_line_r1
        log.loc[idx, "r1_score"] = int(r1_info["r1_score"])
        log.loc[idx, "cl03_market_prob"] = mc_odds.get(dgid, np.nan)
        log.loc[idx, "cl03_capture_time"] = ts
        log.loc[idx, "is_standard_cut_event"] = True

        if is_inside_1:
            cl03_count += 1

    log.to_parquet(log_file, index=False)

    # ── Summary ──
    print("\nCL03 SUMMARY:", flush=True)
    print("  Event: %s (%d, %d)" % (event_name, event_id, season), flush=True)
    print("  R1 cut line: %d" % projected_cut_line_r1, flush=True)
    print("  INSIDE_1 signals: %d" % cl03_count, flush=True)
    print("  DG make_cut probs loaded: %d" % len(dg_mc), flush=True)
    print("  Market make_cut probs loaded: %d" % len(mc_odds), flush=True)

    total_cl03 = log["cl03_flag"].sum() if "cl03_flag" in log.columns else 0
    print("  Season CL03 total: %d" % total_cl03, flush=True)

    # ── CL04: Log post-R1 Top 20 / Top 10 odds + R1 sg_total buckets ──
    # Data collection only — no signal, no bet recommendations.
    print("\n--- CL04 DATA COLLECTION ---", flush=True)

    # Pull post-R1 top_20 and top_10 odds
    t20_odds = {}
    t10_odds = {}
    if RUN_MODE == "live":
        for mkt, dest in [("top_20", t20_odds), ("top_10", t10_odds)]:
            d = dg_get("/betting-tools/outrights", {"tour": "pga", "market": mkt, "odds_format": "american"})
            if d and isinstance(d, dict):
                for o in d.get("odds", []):
                    if not isinstance(o, dict):
                        continue
                    dgid = o.get("dg_id")
                    book_odds = {}
                    for bk in o:
                        if bk in {"dg_id", "player_name", "datagolf"}:
                            continue
                        val = o[bk]
                        if isinstance(val, dict):
                            continue
                        parsed = parse_odds(val)
                        if pd.notna(parsed):
                            book_odds[bk] = parsed
                    if book_odds:
                        best_odds = max(book_odds.values())
                        dest[dgid] = american_to_implied(best_odds)
                print("CL04: %s odds loaded for %d players" % (mkt, len(dest)), flush=True)
            else:
                print("CL04: WARNING — %s odds unavailable. Logging nulls." % mkt, flush=True)
    else:
        odds_all = pd.read_parquet(DATA / "odds_outrights.parquet")
        for mkt, dest in [("top_20", t20_odds), ("top_10", t10_odds)]:
            ev_mkt = odds_all[(odds_all["event_id"] == event_id) & (odds_all["calendar_year"] == season) &
                              (odds_all["market"] == mkt) & (odds_all["book"] == "draftkings")]
            for _, o in ev_mkt.iterrows():
                dest[o["dg_id"]] = american_to_implied(o["close_odds"])

    # Reload log (CL03 already saved it)
    log = pd.read_parquet(log_file)

    # Ensure CL04 columns exist (append only)
    for col in ["cl04_top20_market_prob", "cl04_top10_market_prob",
                "cl04_r1_sg_total", "cl04_r1_bucket", "cl04_r1_position"]:
        if col not in log.columns:
            log[col] = np.nan

    # R1 sg_total and position lookup
    r1_sg_lookup = {}
    for _, row in r1_df.iterrows():
        sg = row.get("sg_total")
        r1_sg_lookup[row["dg_id"]] = float(sg) if pd.notna(sg) else np.nan

    # R1 leaderboard position (rank by r1_score ascending, lower = better)
    r1_df["r1_position"] = r1_df["r1_score"].rank(method="min").astype(int)
    r1_pos_lookup = {row["dg_id"]: int(row["r1_position"]) for _, row in r1_df.iterrows()}

    def _cl04_bucket(sg):
        if pd.isna(sg):
            return "OTHER"
        if sg > 5:
            return "OUTLIER_HIGH"
        if sg > 3:
            return "EXTREME_HIGH"
        if sg > 1:
            return "HIGH"
        return "OTHER"

    # Update all make_cut rows for this event (same mask as CL03)
    latest_ts = log["run_timestamp"].max()
    mask = ((log["run_timestamp"] == latest_ts) &
            (log["event_id"] == event_id) &
            (log["market"] == "make_cut"))

    cl04_logged = 0
    for idx in log[mask].index:
        dgid = log.loc[idx, "player_id"]
        sg = r1_sg_lookup.get(dgid, np.nan)
        log.loc[idx, "cl04_top20_market_prob"] = t20_odds.get(dgid, np.nan)
        log.loc[idx, "cl04_top10_market_prob"] = t10_odds.get(dgid, np.nan)
        log.loc[idx, "cl04_r1_sg_total"] = sg
        log.loc[idx, "cl04_r1_bucket"] = _cl04_bucket(sg)
        log.loc[idx, "cl04_r1_position"] = r1_pos_lookup.get(dgid, np.nan)
        cl04_logged += 1

    log.to_parquet(log_file, index=False)

    # Summary
    n_t20 = sum(1 for v in t20_odds.values() if pd.notna(v))
    n_t10 = sum(1 for v in t10_odds.values() if pd.notna(v))
    n_oh = log[mask & (log["cl04_r1_bucket"] == "OUTLIER_HIGH")].shape[0]
    n_eh = log[mask & (log["cl04_r1_bucket"] == "EXTREME_HIGH")].shape[0]
    print("CL04: Logged %d players | T20 odds: %d | T10 odds: %d" % (cl04_logged, n_t20, n_t10), flush=True)
    print("CL04: OUTLIER_HIGH: %d | EXTREME_HIGH: %d" % (n_oh, n_eh), flush=True)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", default="close", choices=["open", "close", "post_r1"])
    parser.add_argument("--include-matchups", action="store_true")
    parser.add_argument("--skip-g13", action="store_true", help="Skip G13 wave overlay")
    args = parser.parse_args()

    if args.capture == "post_r1":
        # Post-R1 mode: only run CL03 shadow capture
        run_cl03()
    else:
        # Standard pre-tournament flow (unchanged)
        result = run(capture_type=args.capture)
        if not args.skip_g13:
            run_g13(result)
        run_g14(result)
        run_g15(result)
        run_composite()
        if args.include_matchups:
            run_matchups(capture_type=args.capture)
