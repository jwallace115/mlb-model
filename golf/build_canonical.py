#!/usr/bin/env python3
"""Golf Phase 1 — Canonical Dataset Build. Run in stages via --step flag."""
import os, sys, json, time, re
from pathlib import Path
from collections import Counter

import numpy as np
import pandas as pd
import requests

# ── Config ──
try:
    from dotenv import load_dotenv; load_dotenv()
except Exception: pass

API_KEY = os.environ.get("DATAGOLF_API_KEY", "")
BASE = "https://feeds.datagolf.com"
DATA_DIR = Path("golf/data/canonical")
DATA_DIR.mkdir(parents=True, exist_ok=True)
SLEEP = 1.5
RETRY_WAIT = 65

TEAM_EVENT_IDS = {18}  # Zurich Classic
MAJOR_IDS = {14, 33, 26, 100}  # Masters, PGA, US Open, Open
TARGET_YEARS = list(range(2019, 2026))
BOOKS = ["draftkings", "fanduel", "pinnacle"]  # Primary books (add more later if needed)
MARKETS = ["win", "top_5", "top_10", "top_20", "make_cut"]


def dg_get(path, params=None):
    """DataGolf API call with rate limiting and retry."""
    if params is None: params = {}
    params["file_format"] = "json"
    params["key"] = API_KEY
    time.sleep(SLEEP)
    try:
        r = requests.get(BASE + path, params=params, timeout=45)
        if r.status_code == 429:
            print("    429 — waiting %ds..." % RETRY_WAIT, flush=True)
            time.sleep(RETRY_WAIT)
            r = requests.get(BASE + path, params=params, timeout=45)
        if r.status_code == 200:
            return r.json()
        return None
    except Exception as e:
        print("    Error: %s" % e, flush=True)
        return None


def parse_odds_str(s):
    """Parse American odds string to float."""
    if not s or s == "n/a": return np.nan
    try: return float(str(s).replace("+", ""))
    except: return np.nan


def american_to_implied(odds):
    if pd.isna(odds) or odds == 0: return np.nan
    return 100 / (odds + 100) if odds > 0 else abs(odds) / (abs(odds) + 100)


def parse_fin_text(ft):
    """Parse finish text to numeric position."""
    if not ft or pd.isna(ft): return 999
    ft = str(ft).strip().upper()
    if ft in ("CUT", "MC"): return 999
    if ft == "WD": return 998
    if ft == "DQ": return 997
    if ft == "MDF": return 996
    ft = ft.replace("T", "")
    try: return int(ft)
    except: return 999


def parse_tee_time_hour(tt):
    """Parse tee time string to 24h hour integer."""
    if not tt or pd.isna(tt): return np.nan
    tt = str(tt).strip().lower()
    m = re.match(r"(\d{1,2}):(\d{2})\s*(am|pm)?", tt)
    if m:
        h = int(m.group(1))
        ampm = m.group(3)
        if ampm == "pm" and h < 12: h += 12
        if ampm == "am" and h == 12: h = 0
        return h
    # Try datetime format
    m2 = re.match(r"\d{4}-\d{2}-\d{2}\s+(\d{1,2}):", tt)
    if m2: return int(m2.group(1))
    return np.nan


def parse_dead_heat(text):
    """Parse dead heat factor from bet_outcome_text."""
    if not text or pd.isna(text): return None
    text = str(text).lower()
    if "paid in full" in text: return 1.0
    if text == "loss": return 0.0
    m = re.search(r"(\d+)\s+for\s+(\d+)", text)
    if m:
        return int(m.group(1)) / int(m.group(2))
    return None


# ================================================================
# STEP 1 — EVENT UNIVERSE
# ================================================================
def step1_events():
    print("=" * 60); print("STEP 1 — EVENT UNIVERSE"); print("=" * 60, flush=True)

    # Raw data event list
    raw_el = dg_get("/historical-raw-data/event-list", {"tour": "pga"})
    if not isinstance(raw_el, list): raw_el = []
    print("Raw event list: %d events" % len(raw_el), flush=True)

    # Odds event list
    odds_el = dg_get("/historical-odds/event-list", {"tour": "pga"})
    if not isinstance(odds_el, list): odds_el = []
    print("Odds event list: %d events" % len(odds_el), flush=True)

    # Predictions: probe each event in odds list for 2020+
    preds_events = set()
    odds_2020_plus = [(e["event_id"], e["calendar_year"]) for e in odds_el
                      if e.get("calendar_year", 0) >= 2020]
    print("Probing %d events for predictions..." % len(odds_2020_plus), flush=True)
    for eid, yr in odds_2020_plus:
        d = dg_get("/preds/pre-tournament-archive", {"event_id": eid, "year": yr, "odds_format": "percent"})
        if d and isinstance(d, dict):
            bl = d.get("baseline_history_fit", d.get("baseline", []))
            if isinstance(bl, list) and len(bl) > 0:
                preds_events.add((eid, yr))
    print("Predictions confirmed: %d events" % len(preds_events), flush=True)

    # Build master table
    raw_set = {(e["event_id"], e["calendar_year"]) for e in raw_el}
    odds_set = {(e["event_id"], e["calendar_year"]) for e in odds_el}

    # Name lookup from raw events
    name_map = {}
    for e in raw_el:
        name_map[(e["event_id"], e["calendar_year"])] = e["event_name"]
    for e in odds_el:
        key = (e["event_id"], e["calendar_year"])
        if key not in name_map:
            name_map[key] = e.get("event_name", "")

    all_keys = raw_set | odds_set
    rows = []
    for eid, yr in sorted(all_keys):
        if yr not in TARGET_YEARS: continue
        rows.append({
            "event_id": eid,
            "calendar_year": yr,
            "event_name": name_map.get((eid, yr), ""),
            "has_rounds": (eid, yr) in raw_set,
            "has_odds": (eid, yr) in odds_set,
            "has_predictions": (eid, yr) in preds_events,
            "is_major": eid in MAJOR_IDS,
            "is_team_event": eid in TEAM_EVENT_IDS,
        })

    events = pd.DataFrame(rows)
    # Exclude team events
    events = events[~events["is_team_event"]].reset_index(drop=True)
    events.to_parquet(DATA_DIR / "events.parquet", index=False)

    # Report
    print("\nMaster events: %d" % len(events))
    has_both = events[events["has_rounds"] & events["has_odds"]]
    has_all3 = events[events["has_rounds"] & events["has_odds"] & events["has_predictions"]]
    print("Rounds + Odds: %d" % len(has_both))
    print("All three (rounds+odds+preds): %d" % len(has_all3))
    print("\nPer year:")
    for yr in TARGET_YEARS:
        sub = events[events["calendar_year"] == yr]
        r = sub["has_rounds"].sum()
        o = sub["has_odds"].sum()
        p = sub["has_predictions"].sum()
        both = (sub["has_rounds"] & sub["has_odds"]).sum()
        print("  %d: %d events, rounds=%d, odds=%d, preds=%d, rounds+odds=%d" % (yr, len(sub), r, o, p, both))

    if len(has_both) < 150:
        print("\n*** STOP: fewer than 150 events with rounds+odds (%d)" % len(has_both))
        return False
    return True


# ================================================================
# STEP 2 — PLAYER ROUNDS
# ================================================================
def step2_rounds():
    print("\n" + "=" * 60); print("STEP 2 — PLAYER ROUNDS"); print("=" * 60, flush=True)

    events = pd.read_parquet(DATA_DIR / "events.parquet")
    to_pull = events[events["has_rounds"]].sort_values(["calendar_year", "event_id"])

    # Resume support
    existing_file = DATA_DIR / "player_rounds.parquet"
    if existing_file.exists():
        existing = pd.read_parquet(existing_file)
        done = set(zip(existing["event_id"], existing["calendar_year"]))
        print("Resuming: %d events already done" % len(done), flush=True)
    else:
        existing = None
        done = set()

    all_rows = []
    api_calls = 0
    sg_report = {}

    for _, ev in to_pull.iterrows():
        eid, yr = ev["event_id"], ev["calendar_year"]
        if (eid, yr) in done: continue

        d = dg_get("/historical-raw-data/rounds", {"tour": "pga", "event_id": eid, "year": yr})
        api_calls += 1
        if not d or not isinstance(d, dict): continue

        scores = d.get("scores", [])
        if not scores: continue

        for player in scores:
            dgid = player.get("dg_id")
            pname = player.get("player_name", "")
            ft = player.get("fin_text", "")
            fn = parse_fin_text(ft)

            for rnd in range(1, 5):
                rkey = "round_%d" % rnd
                rdata = player.get(rkey)
                if not rdata or not isinstance(rdata, dict): continue

                tt = rdata.get("teetime", rdata.get("tee_time", ""))
                tt_hour = parse_tee_time_hour(tt)

                row = {
                    "event_id": eid, "event_name": ev["event_name"],
                    "calendar_year": yr,
                    "dg_id": dgid, "player_name": pname,
                    "round_num": rnd,
                    "round_score": rdata.get("score"),
                    "course_par": rdata.get("course_par"),
                    "course_name": rdata.get("course_name", ""),
                    "course_num": rdata.get("course_num"),
                    "sg_putt": rdata.get("sg_putt"),
                    "sg_arg": rdata.get("sg_arg"),
                    "sg_app": rdata.get("sg_app"),
                    "sg_ott": rdata.get("sg_ott"),
                    "sg_t2g": rdata.get("sg_t2g"),
                    "sg_total": rdata.get("sg_total"),
                    "driving_acc": rdata.get("driving_acc"),
                    "driving_dist": rdata.get("driving_dist"),
                    "gir": rdata.get("gir"),
                    "scrambling": rdata.get("scrambling"),
                    "prox_fw": rdata.get("prox_fw"),
                    "prox_rgh": rdata.get("prox_rgh"),
                    "birdies": rdata.get("birdies"),
                    "pars": rdata.get("pars"),
                    "bogies": rdata.get("bogies"),
                    "tee_time": tt,
                    "tee_time_hour": tt_hour,
                    "tee_wave": "AM" if pd.notna(tt_hour) and tt_hour < 12 else ("PM" if pd.notna(tt_hour) else None),
                    "start_hole": rdata.get("start_hole"),
                    "fin_text": ft, "fin_num": fn,
                    "made_cut": 1 if fn < 900 else 0,
                    "is_tie": 1 if str(ft).startswith("T") else 0,
                    "is_major": ev["is_major"],
                    "sg_complete": 1 if all(rdata.get(f) is not None for f in ["sg_putt","sg_arg","sg_app","sg_ott"]) else 0,
                }
                all_rows.append(row)

        # SG tracking
        sg_key = yr
        if sg_key not in sg_report: sg_report[sg_key] = {"events": 0, "sg_events": 0}
        sg_report[sg_key]["events"] += 1
        # Check if this event had SG
        has_sg = any(player.get("round_1", {}).get("sg_total") is not None for player in scores)
        if has_sg: sg_report[sg_key]["sg_events"] += 1

        if api_calls % 25 == 0:
            print("  %d API calls, %d rows so far..." % (api_calls, len(all_rows)), flush=True)

        # Incremental save every 50 events
        if api_calls % 50 == 0 and all_rows:
            chunk = pd.DataFrame(all_rows)
            if existing is not None:
                chunk = pd.concat([existing, chunk], ignore_index=True)
            chunk.to_parquet(existing_file, index=False)

    # Final save
    df = pd.DataFrame(all_rows)
    if existing is not None:
        df = pd.concat([existing, df], ignore_index=True)
    df = df.drop_duplicates(subset=["event_id", "calendar_year", "dg_id", "round_num"]).reset_index(drop=True)
    df.to_parquet(DATA_DIR / "player_rounds.parquet", index=False)

    print("\nPlayer rounds: %d rows, %d events" % (len(df), df[["event_id","calendar_year"]].drop_duplicates().shape[0]))
    print("API calls: %d" % api_calls)
    for yr in sorted(sg_report):
        sr = sg_report[yr]
        print("  %d: %d events pulled, %d with SG (%.0f%%)" % (yr, sr["events"], sr["sg_events"],
              sr["sg_events"]/sr["events"]*100 if sr["events"] else 0))


# ================================================================
# STEP 3 — TOURNAMENT RESULTS
# ================================================================
def step3_results():
    print("\n" + "=" * 60); print("STEP 3 — TOURNAMENT RESULTS"); print("=" * 60, flush=True)

    pr = pd.read_parquet(DATA_DIR / "player_rounds.parquet")

    agg = pr.groupby(["event_id", "event_name", "calendar_year", "dg_id", "player_name",
                       "fin_text", "fin_num", "made_cut", "is_tie", "is_major"]).agg(
        total_score=("round_score", "sum"),
        total_rounds_played=("round_num", "count"),
        total_sg_putt=("sg_putt", "sum"),
        total_sg_arg=("sg_arg", "sum"),
        total_sg_app=("sg_app", "sum"),
        total_sg_ott=("sg_ott", "sum"),
        total_sg_t2g=("sg_t2g", "sum"),
        total_sg_total=("sg_total", "sum"),
        avg_sg_total=("sg_total", "mean"),
        avg_sg_putt=("sg_putt", "mean"),
        avg_sg_app=("sg_app", "mean"),
        avg_sg_arg=("sg_arg", "mean"),
        avg_sg_ott=("sg_ott", "mean"),
    ).reset_index()

    agg["top_5"] = (agg["fin_num"] <= 5).astype(int)
    agg["top_10"] = (agg["fin_num"] <= 10).astype(int)
    agg["top_20"] = (agg["fin_num"] <= 20).astype(int)
    agg["winner"] = (agg["fin_num"] == 1).astype(int)

    # Field size
    field_size = pr[pr["round_num"] == 1].groupby(["event_id", "calendar_year"])["dg_id"].nunique().reset_index(name="field_size")
    agg = agg.merge(field_size, on=["event_id", "calendar_year"], how="left")

    agg.to_parquet(DATA_DIR / "tournament_results.parquet", index=False)
    print("Tournament results: %d rows" % len(agg))


# ================================================================
# STEP 4 — OUTRIGHT ODDS
# ================================================================
def step4_odds():
    print("\n" + "=" * 60); print("STEP 4 — OUTRIGHT ODDS"); print("=" * 60, flush=True)

    events = pd.read_parquet(DATA_DIR / "events.parquet")
    to_pull = events[events["has_odds"]].sort_values(["calendar_year", "event_id"])

    existing_file = DATA_DIR / "odds_outrights.parquet"
    if existing_file.exists():
        existing = pd.read_parquet(existing_file)
        done = set(zip(existing["event_id"], existing["calendar_year"], existing["market"], existing["book"]))
        print("Resuming: %d event-market-book combos done" % len(done), flush=True)
    else:
        existing = None
        done = set()

    all_rows = []
    api_calls = 0

    for _, ev in to_pull.iterrows():
        eid, yr = ev["event_id"], ev["calendar_year"]
        for market in MARKETS:
            for book in BOOKS:
                if (eid, yr, market, book) in done: continue
                d = dg_get("/historical-odds/outrights",
                           {"tour": "pga", "event_id": eid, "year": yr,
                            "market": market, "book": book, "odds_format": "american"})
                api_calls += 1
                if not d or not isinstance(d, dict): continue
                odds = d.get("odds", [])
                if not odds: continue

                for o in odds:
                    if not isinstance(o, dict): continue
                    open_o = parse_odds_str(o.get("open_odds"))
                    close_o = parse_odds_str(o.get("close_odds"))
                    all_rows.append({
                        "event_id": eid, "calendar_year": yr,
                        "market": market, "book": book,
                        "dg_id": o.get("dg_id"),
                        "player_name": o.get("player_name", ""),
                        "open_odds": open_o, "close_odds": close_o,
                        "open_time": o.get("open_time"), "close_time": o.get("close_time"),
                        "bet_outcome_numeric": o.get("bet_outcome_numeric"),
                        "bet_outcome_text": o.get("bet_outcome_text", ""),
                        "open_implied": american_to_implied(open_o),
                        "close_implied": american_to_implied(close_o),
                        "dead_heat_factor": parse_dead_heat(o.get("bet_outcome_text")),
                    })

                if api_calls % 100 == 0:
                    print("  %d calls, %d rows..." % (api_calls, len(all_rows)), flush=True)

        # Save every 10 events
        if api_calls % 200 == 0 and all_rows:
            chunk = pd.DataFrame(all_rows)
            if existing is not None:
                chunk = pd.concat([existing, chunk], ignore_index=True)
            chunk.to_parquet(existing_file, index=False)
            print("  Checkpoint saved: %d rows" % len(chunk), flush=True)

    df = pd.DataFrame(all_rows)
    if existing is not None:
        df = pd.concat([existing, df], ignore_index=True)
    df = df.drop_duplicates(subset=["event_id","calendar_year","market","book","dg_id"]).reset_index(drop=True)

    # De-vig
    devig_rows = []
    for (eid, yr, mkt, bk), grp in df.groupby(["event_id","calendar_year","market","book"]):
        sum_imp = grp["close_implied"].sum()
        if sum_imp > 0:
            grp = grp.copy()
            grp["fair_close_prob"] = grp["close_implied"] / sum_imp
            grp["overround"] = sum_imp - 1.0
        else:
            grp = grp.copy()
            grp["fair_close_prob"] = np.nan
            grp["overround"] = np.nan
        devig_rows.append(grp)

    df = pd.concat(devig_rows, ignore_index=True) if devig_rows else df
    df.to_parquet(existing_file, index=False)

    print("\nOutright odds: %d rows, %d API calls" % (len(df), api_calls))
    print("Markets: %s" % sorted(df["market"].unique()))
    print("Books: %s" % sorted(df["book"].unique()))

    # Overround by book
    or_summary = df.groupby("book")["overround"].mean()
    print("\nAvg overround by book:")
    for book, ov in or_summary.items():
        print("  %s: %.1f%%" % (book, ov * 100 if pd.notna(ov) else 0))


# ================================================================
# STEP 5 — MATCHUP ODDS
# ================================================================
def step5_matchups():
    print("\n" + "=" * 60); print("STEP 5 — MATCHUP ODDS"); print("=" * 60, flush=True)

    events = pd.read_parquet(DATA_DIR / "events.parquet")
    to_pull = events[events["has_odds"]].sort_values(["calendar_year", "event_id"])

    existing_file = DATA_DIR / "odds_matchups.parquet"
    if existing_file.exists():
        existing = pd.read_parquet(existing_file)
        done = set(zip(existing["event_id"], existing["calendar_year"], existing["book"]))
    else:
        existing = None
        done = set()

    all_rows = []
    api_calls = 0

    for _, ev in to_pull.iterrows():
        eid, yr = ev["event_id"], ev["calendar_year"]
        for book in BOOKS[:5]:  # Top 5 books for matchups
            if (eid, yr, book) in done: continue
            d = dg_get("/historical-odds/matchups",
                       {"tour": "pga", "event_id": eid, "year": yr,
                        "book": book, "odds_format": "american"})
            api_calls += 1
            if not d or not isinstance(d, dict): continue
            odds = d.get("odds", [])
            if not odds: continue

            for o in odds:
                if not isinstance(o, dict): continue
                row = {
                    "event_id": eid, "calendar_year": yr, "book": book,
                    "bet_type": o.get("bet_type", ""),
                    "p1_dg_id": o.get("p1_dg_id"), "p1_name": o.get("p1_player_name", ""),
                    "p1_open": parse_odds_str(o.get("p1_open")),
                    "p1_close": parse_odds_str(o.get("p1_close")),
                    "p1_outcome": o.get("p1_outcome"),
                    "p1_outcome_text": o.get("p1_outcome_text", ""),
                    "p2_dg_id": o.get("p2_dg_id"), "p2_name": o.get("p2_player_name", ""),
                    "p2_open": parse_odds_str(o.get("p2_open")),
                    "p2_close": parse_odds_str(o.get("p2_close")),
                    "p2_outcome": o.get("p2_outcome"),
                    "p2_outcome_text": o.get("p2_outcome_text", ""),
                    "open_time": o.get("open_time"), "close_time": o.get("close_time"),
                }
                # P3 for 3-balls
                if o.get("p3_dg_id"):
                    row["p3_dg_id"] = o.get("p3_dg_id")
                    row["p3_name"] = o.get("p3_player_name", "")
                    row["p3_open"] = parse_odds_str(o.get("p3_open"))
                    row["p3_close"] = parse_odds_str(o.get("p3_close"))
                    row["p3_outcome"] = o.get("p3_outcome")
                    row["p3_outcome_text"] = o.get("p3_outcome_text", "")

                # Void check
                voided = any("void" in str(o.get(k, "")).lower() or "push" in str(o.get(k, "")).lower()
                             for k in ["p1_outcome_text", "p2_outcome_text"])
                row["voided"] = voided
                all_rows.append(row)

            if api_calls % 50 == 0:
                print("  %d calls, %d rows..." % (api_calls, len(all_rows)), flush=True)

    df = pd.DataFrame(all_rows)
    if existing is not None:
        df = pd.concat([existing, df], ignore_index=True)
    df = df.drop_duplicates().reset_index(drop=True)
    df.to_parquet(existing_file, index=False)

    print("\nMatchup odds: %d rows, %d API calls" % (len(df), api_calls))
    if len(df) > 0:
        print("Bet types: %s" % df["bet_type"].value_counts().to_dict())
        print("Void rate: %.1f%%" % (df["voided"].mean() * 100))


# ================================================================
# STEP 6 — PREDICTIONS
# ================================================================
def step6_predictions():
    print("\n" + "=" * 60); print("STEP 6 — PREDICTIONS"); print("=" * 60, flush=True)

    events = pd.read_parquet(DATA_DIR / "events.parquet")
    to_pull = events[events["has_predictions"]].sort_values(["calendar_year", "event_id"])

    all_rows = []
    api_calls = 0

    for _, ev in to_pull.iterrows():
        eid, yr = ev["event_id"], ev["calendar_year"]
        d = dg_get("/preds/pre-tournament-archive",
                   {"event_id": eid, "year": yr, "odds_format": "percent"})
        api_calls += 1
        if not d or not isinstance(d, dict): continue

        # Try baseline_history_fit first, fall back to baseline
        bl = d.get("baseline_history_fit", d.get("baseline", []))
        if not bl: continue

        for p in bl:
            if not isinstance(p, dict): continue
            all_rows.append({
                "event_id": eid, "calendar_year": yr,
                "dg_id": p.get("dg_id"),
                "player_name": p.get("player_name", ""),
                "fin_text": p.get("fin_text", ""),
                "win_prob": p.get("win"),
                "top_5_prob": p.get("top_5"),
                "top_10_prob": p.get("top_10"),
                "top_20_prob": p.get("top_20"),
                "make_cut_prob": p.get("make_cut"),
                "is_major": ev["is_major"],
            })

        if api_calls % 25 == 0:
            print("  %d calls, %d rows..." % (api_calls, len(all_rows)), flush=True)

    df = pd.DataFrame(all_rows)
    df.to_parquet(DATA_DIR / "predictions.parquet", index=False)
    print("\nPredictions: %d rows, %d events, %d API calls" % (
        len(df), df[["event_id","calendar_year"]].drop_duplicates().shape[0], api_calls))


# ================================================================
# STEP 7+8 — VALIDATION
# ================================================================
def step7_validate():
    print("\n" + "=" * 60); print("STEPS 7-8 — VALIDATION"); print("=" * 60, flush=True)

    ev = pd.read_parquet(DATA_DIR / "events.parquet")
    pr = pd.read_parquet(DATA_DIR / "player_rounds.parquet")
    tr = pd.read_parquet(DATA_DIR / "tournament_results.parquet")

    files = {"events": ev, "player_rounds": pr, "tournament_results": tr}

    # Load optional files
    for name in ["odds_outrights", "odds_matchups", "predictions"]:
        f = DATA_DIR / ("%s.parquet" % name)
        if f.exists():
            files[name] = pd.read_parquet(f)

    lines = []
    lines.append("GOLF PHASE 1 — CANONICAL BUILD LOG")
    lines.append("=" * 60)

    # 1. Sizes
    lines.append("\n1. DATASET SIZES")
    for name, df in files.items():
        lines.append("  %s: %d rows" % (name, len(df)))

    # 2. Coverage matrix
    lines.append("\n2. COVERAGE MATRIX")
    lines.append("  Year | Events | +Rounds | +Odds | +Preds | Rnds+Odds")
    for yr in TARGET_YEARS:
        sub = ev[ev["calendar_year"] == yr]
        r = sub["has_rounds"].sum()
        o = sub["has_odds"].sum()
        p = sub["has_predictions"].sum()
        both = (sub["has_rounds"] & sub["has_odds"]).sum()
        lines.append("  %d | %6d | %7d | %5d | %6d | %9d" % (yr, len(sub), r, o, p, both))

    # 3. SG completeness
    lines.append("\n3. SG COMPLETENESS")
    for yr in TARGET_YEARS:
        sub = pr[pr["calendar_year"] == yr]
        if len(sub) == 0: continue
        pct = sub["sg_complete"].mean() * 100
        lines.append("  %d: %.1f%% of rounds with complete SG" % (yr, pct))

    # 4. Overround by book
    if "odds_outrights" in files:
        oo = files["odds_outrights"]
        lines.append("\n4. AVG OVERROUND BY BOOK (top_20)")
        t20 = oo[oo["market"] == "top_20"]
        if len(t20) > 0:
            for book in sorted(t20["book"].unique()):
                avg_or = t20[t20["book"] == book]["overround"].mean()
                lines.append("  %s: %.1f%%" % (book, avg_or * 100 if pd.notna(avg_or) else 0))

    # 5. Dead heat rate
    if "odds_outrights" in files:
        oo = files["odds_outrights"]
        lines.append("\n5. DEAD HEAT RATE BY MARKET")
        for mkt in ["top_5", "top_10", "top_20"]:
            sub = oo[oo["market"] == mkt]
            if len(sub) == 0: continue
            dh = sub["dead_heat_factor"].notna() & (sub["dead_heat_factor"] < 1.0) & (sub["dead_heat_factor"] > 0.0)
            lines.append("  %s: %.1f%% dead heat" % (mkt, dh.mean() * 100))

    # 6. Void rate
    if "odds_matchups" in files:
        mm = files["odds_matchups"]
        lines.append("\n6. MATCHUP VOID RATE: %.1f%%" % (mm["voided"].mean() * 100 if len(mm) > 0 else 0))

    # 7. Phase readiness
    lines.append("\n7. PHASE READINESS")
    if "predictions" in files and "odds_outrights" in files:
        preds = files["predictions"]
        oo = files["odds_outrights"]
        pred_evts = set(zip(preds["event_id"], preds["calendar_year"]))
        odds_evts = set(zip(oo["event_id"], oo["calendar_year"]))
        overlap = pred_evts & odds_evts
        lines.append("  Phase 2 (ΔR²): %d events with preds+odds" % len(overlap))

    rounds_evts = set(zip(pr["event_id"], pr["calendar_year"]))
    if "odds_outrights" in files:
        odds_evts2 = set(zip(files["odds_outrights"]["event_id"], files["odds_outrights"]["calendar_year"]))
        lines.append("  Phase 3 (rank bucket): %d events with rounds+odds" % len(rounds_evts & odds_evts2))

    if "odds_matchups" in files:
        mm_evts = set(zip(files["odds_matchups"]["event_id"], files["odds_matchups"]["calendar_year"]))
        lines.append("  Phase 5 (matchups): %d events with matchup odds" % len(mm_evts))

    tt_rounds = pr[pr["tee_time"].notna() & (pr["tee_time"] != "")]
    tt_evts = set(zip(tt_rounds["event_id"], tt_rounds["calendar_year"]))
    lines.append("  Phase 8 (weather): %d events with tee times" % len(tt_evts))

    # Player lookup
    players = pr[["dg_id", "player_name"]].drop_duplicates()
    players = players.sort_values("dg_id").drop_duplicates("dg_id", keep="last")
    players.to_parquet(DATA_DIR / "player_lookup.parquet", index=False)
    lines.append("\n  Player lookup: %d unique dg_ids" % len(players))

    report = "\n".join(lines)
    print(report, flush=True)

    with open(DATA_DIR / "build_log.txt", "w") as f:
        f.write(report)


# ================================================================
# MAIN
# ================================================================
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", type=int, default=0, help="Run specific step (1-8) or 0 for all")
    args = parser.parse_args()

    if args.step == 0 or args.step == 1:
        if not step1_events() and args.step == 1:
            sys.exit(1)
    if args.step == 0 or args.step == 2:
        step2_rounds()
    if args.step == 0 or args.step == 3:
        step3_results()
    if args.step == 0 or args.step == 4:
        step4_odds()
    if args.step == 0 or args.step == 5:
        step5_matchups()
    if args.step == 0 or args.step == 6:
        step6_predictions()
    if args.step in (0, 7, 8):
        step7_validate()

    print("\n" + "=" * 60)
    print("BUILD COMPLETE")
    print("=" * 60)
