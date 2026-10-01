#!/usr/bin/env python3
"""NBA packet builder — assembles the layers the reader sees before freezing.

Usage:
  python3 nba/layers/build_packet_nba.py --date 2026-10-20 [--built-utc ISO] [--news-file PATH]

Layers:
  L1 market  — Pinnacle open/current/move, min/max across books, Hard Rock price, event_markets
  L2 news    — newest official report + ESPN injuries ≤ built_utc, optional --news-file CSV
  L3 history — season-to-date from ESPN finals strictly before the slate date
  L4 model   — rw_sh signal from run_nba.py team lists; sim = absent (not built)
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone, date as _date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shared.layers.packet import (
    build_header, build_packet, to_canonical_json, packet_sha256, parse_utc, builder_sha256
)
from nfl.pipeline.log_ai_opinions import (
    SPORTS, set_sport, implied, GAME_MARKETS, date_season
)

ET = ZoneInfo("America/New_York")
BOOK = "pinnacle"


def _devig_pair(price_a, price_b):
    ia, ib = implied(price_a), implied(price_b)
    return ia / (ia + ib)


def _load_tape_snapshots(season):
    tape_dir = SPORTS["nba"]["lines"] / f"season={season}"
    if not tape_dir.exists():
        return []
    result = []
    for f in sorted(tape_dir.glob("snap_*.parquet")):
        df = pd.read_parquet(f)
        if df.empty:
            continue
        result.append((str(df["snapshot_utc"].iloc[0]), df))
    return result


def _market_layer(event_id, home_team, tape_snaps, built_t, season):
    """L1: Pinnacle open/current/move, min/max, Hard Rock price, event_markets."""
    layer = {}
    first_snap = None
    current_snap = None
    for snap_utc, df in tape_snaps:
        snap_t = parse_utc(snap_utc)
        ev = df[df["event_id"] == event_id]
        if ev.empty:
            continue
        if first_snap is None:
            first_snap = (snap_utc, ev)
        if snap_t <= built_t:
            current_snap = (snap_utc, ev)

    for mk in GAME_MARKETS:
        mk_data = {"market": mk}
        first_side = "Over" if mk == "totals" else home_team
        if first_snap:
            pin_open = first_snap[1][(first_snap[1]["bookmaker"] == BOOK) & (first_snap[1]["market"] == mk)]
            if len(pin_open) == 2:
                a = pin_open[pin_open["outcome_name"] == first_side]
                b = pin_open[pin_open["outcome_name"] != first_side]
                if len(a) == 1 and len(b) == 1:
                    mk_data["open"] = {
                        "snap": first_snap[0],
                        "price_first": float(a.iloc[0]["price"]),
                        "price_second": float(b.iloc[0]["price"]),
                        "q_first": round(_devig_pair(a.iloc[0]["price"], b.iloc[0]["price"]), 6),
                        "point": float(a.iloc[0]["point"]) if pd.notna(a.iloc[0]["point"]) else None,
                    }
        if current_snap:
            pin_cur = current_snap[1][(current_snap[1]["bookmaker"] == BOOK) & (current_snap[1]["market"] == mk)]
            if len(pin_cur) == 2:
                a = pin_cur[pin_cur["outcome_name"] == first_side]
                b = pin_cur[pin_cur["outcome_name"] != first_side]
                if len(a) == 1 and len(b) == 1:
                    mk_data["current"] = {
                        "snap": current_snap[0],
                        "price_first": float(a.iloc[0]["price"]),
                        "price_second": float(b.iloc[0]["price"]),
                        "q_first": round(_devig_pair(a.iloc[0]["price"], b.iloc[0]["price"]), 6),
                        "point": float(a.iloc[0]["point"]) if pd.notna(a.iloc[0]["point"]) else None,
                    }
            if "open" in mk_data and "current" in mk_data:
                mk_data["move"] = round(mk_data["current"]["q_first"] - mk_data["open"]["q_first"], 6)
            all_mk = current_snap[1][current_snap[1]["market"] == mk]
            if not all_mk.empty:
                a_all = all_mk[all_mk["outcome_name"] == first_side]
                b_all = all_mk[all_mk["outcome_name"] != first_side]
                if not a_all.empty:
                    mk_data["min_price_first"] = float(a_all["price"].min())
                    mk_data["max_price_first"] = float(a_all["price"].max())
                if not b_all.empty:
                    mk_data["min_price_second"] = float(b_all["price"].min())
                    mk_data["max_price_second"] = float(b_all["price"].max())
                mk_data["books_in_snap"] = sorted(all_mk["bookmaker"].unique().tolist())
                # Hard Rock price if present
                hr = all_mk[all_mk["bookmaker"].isin(["hardrockbet_fl", "hardrockbet"])]
                if not hr.empty:
                    hr_a = hr[hr["outcome_name"] == first_side]
                    hr_b = hr[hr["outcome_name"] != first_side]
                    if len(hr_a) == 1 and len(hr_b) == 1:
                        mk_data["hard_rock"] = {
                            "price_first": float(hr_a.iloc[0]["price"]),
                            "price_second": float(hr_b.iloc[0]["price"]),
                            "book": hr_a.iloc[0]["bookmaker"],
                        }
        if not mk_data.get("current") and not mk_data.get("open"):
            mk_data["missing"] = True
        layer[mk] = mk_data

    # Event markets summary
    em_dir = ROOT / "data" / "odds_archive" / "nba" / "event_markets" / f"season={season}"
    if em_dir.exists():
        for f in sorted(em_dir.glob("snap_*.parquet"), reverse=True):
            em = pd.read_parquet(f)
            ev_em = em[em["event_id"] == event_id] if "event_id" in em.columns else pd.DataFrame()
            if ev_em.empty:
                continue
            snap_col = "snapshot_utc" if "snapshot_utc" in em.columns else "pull_timestamp"
            if snap_col in em.columns and parse_utc(str(em[snap_col].iloc[0])) <= built_t:
                counts = ev_em.groupby(["bookmaker", "market"]).size().reset_index(name="lines")
                layer["event_markets_summary"] = counts.to_dict("records")
                break

    return layer


def _news_layer(slate_date, built_t, home_team, away_team, news_file=None):
    """L2: newest official report + ESPN injuries ≤ built_utc for the two teams."""
    layer = {"official_report": None, "espn_injuries": [], "manual_news": []}

    # Official injury reports
    report_dir = ROOT / "data" / "injury_archive" / "nba" / "season=2026" / "reports"
    if report_dir.exists():
        for pq in sorted(report_dir.glob("*.parquet"), reverse=True):
            try:
                rdf = pd.read_parquet(pq)
                if "report_timestamp" in rdf.columns and len(rdf) > 0:
                    rt = parse_utc(rdf["report_timestamp"].iloc[0])
                    if rt <= built_t:
                        # Filter to the two teams
                        team_rows = rdf[rdf["team"].isin([home_team, away_team])]
                        if len(team_rows) > 0:
                            layer["official_report"] = {
                                "report_timestamp": rdf["report_timestamp"].iloc[0],
                                "rows": team_rows.to_dict("records"),
                            }
                        break
            except Exception:
                continue

    # ESPN injuries
    espn_dir = ROOT / "data" / "injury_archive" / "nba" / "season=2026" / "espn"
    if espn_dir.exists():
        import gzip
        for gz in sorted(espn_dir.glob("injuries_*.json.gz"), reverse=True):
            # Parse timestamp from filename
            ts_str = gz.stem.replace("injuries_", "")
            try:
                ts = datetime.strptime(ts_str, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if ts <= built_t:
                data = json.loads(gzip.decompress(gz.read_bytes()))
                teams_data = data.get("injuries", [])
                for team in teams_data:
                    tn = team.get("displayName", "")
                    if tn in (home_team, away_team):
                        for inj in team.get("injuries", []):
                            layer["espn_injuries"].append({
                                "team": tn,
                                "player": inj.get("athlete", {}).get("displayName", ""),
                                "status": inj.get("status", ""),
                                "date": inj.get("date", ""),
                                "retrieval_utc": ts.isoformat(),
                            })
                break

    # Manual news CSV
    if news_file and Path(news_file).exists():
        import csv
        with open(news_file) as f:
            for row in csv.DictReader(f):
                if row.get("retrieved_utc"):
                    rt = parse_utc(row["retrieved_utc"])
                    if rt > built_t:
                        continue
                layer["manual_news"].append(row)

    return layer


def _history_layer(slate_date, home_abbr, away_abbr):
    """L3: season-to-date from ESPN finals, strictly before the slate date."""
    from nba.pipeline.nba_outcomes import fetch_scoreboard
    season = date_season(slate_date)
    target = _date.fromisoformat(str(slate_date))

    # Collect all games before slate_date in this season
    # Use the season's date range
    start = _date(season, 10, 15)  # NBA starts ~Oct 20
    layer = {}
    for abbr in (home_abbr, away_abbr):
        layer[abbr] = {"gp": 0, "w": 0, "l": 0, "pts_for": 0, "pts_against": 0,
                       "last_10": [], "rest_days": None, "back_to_back": False,
                       "n_games": 0}

    # Walk dates from start to slate_date - 1
    d = start
    last_game_date = {}
    while d < target:
        try:
            results = fetch_scoreboard(d.isoformat())
        except (Exception, SystemExit):
            d += timedelta(days=1)
            continue
        for g in results:
            if g["status"] != "STATUS_FINAL":
                continue
            for side, opp_side in [("home", "away"), ("away", "home")]:
                abbr = g.get(side, "")
                if abbr not in layer:
                    continue
                pts_for = g[f"{side}_score"]
                pts_against = g[f"{opp_side}_score"]
                layer[abbr]["gp"] += 1
                layer[abbr]["n_games"] += 1
                if pts_for > pts_against:
                    layer[abbr]["w"] += 1
                else:
                    layer[abbr]["l"] += 1
                layer[abbr]["pts_for"] += pts_for
                layer[abbr]["pts_against"] += pts_against
                layer[abbr]["last_10"].append({"date": d.isoformat(), "pf": pts_for, "pa": pts_against})
                layer[abbr]["last_10"] = layer[abbr]["last_10"][-10:]
                last_game_date[abbr] = d
        d += timedelta(days=1)

    for abbr in (home_abbr, away_abbr):
        if abbr in last_game_date:
            rest = (target - last_game_date[abbr]).days
            layer[abbr]["rest_days"] = rest
            layer[abbr]["back_to_back"] = rest == 1

    return layer


def _model_layer(home_abbr, away_abbr):
    """L4: rw_sh signal from run_nba.py team lists; sim absent."""
    from nba.run_nba import _ROAD_WARRIOR, _STRONG_HOME
    rw_sh_fires = away_abbr in _ROAD_WARRIOR and home_abbr in _STRONG_HOME
    return {
        "rw_sh": {
            "fires": rw_sh_fires,
            "direction": "OVER" if rw_sh_fires else None,
            "evidence": ("2025-26 prereg n101 60.4% ROI +16.3% SE 9.4 at Pinnacle close; "
                         "list frozen 7868c748e") if rw_sh_fires else None,
            "probability": None,
        },
        "sim": {"absent": "not built"},
    }


def build_nba_packet(slate_date, built_utc=None, news_file=None):
    """Build the full NBA packet for a slate date."""
    set_sport("nba")
    season = date_season(slate_date)
    built_t = built_utc or datetime.now(timezone.utc)
    if isinstance(built_t, str):
        built_t = parse_utc(built_t)

    tape_snaps = _load_tape_snapshots(season)
    if not tape_snaps:
        raise SystemExit(f"HALT: no tape snapshots for NBA season {season}")

    # Find all games on the ET slate date from tape
    target = _date.fromisoformat(str(slate_date))
    games = {}
    for snap_utc, df in tape_snaps:
        if parse_utc(snap_utc) > built_t:
            continue
        for eid in df["event_id"].unique():
            if eid in games:
                continue
            ev = df[df["event_id"] == eid].iloc[0]
            ct = parse_utc(ev["commence_time"])
            et_date = ct.astimezone(ET).date()
            if et_date == target:
                games[eid] = {
                    "event_id": eid,
                    "commence_time": ev["commence_time"],
                    "home_team": ev["home_team"],
                    "away_team": ev["away_team"],
                }

    if not games:
        raise SystemExit(f"HALT: no NBA games found for {slate_date} in tape")

    # Build sources
    sources = []
    for snap_utc, df in tape_snaps:
        if parse_utc(snap_utc) <= built_t:
            sources.append({"path": "tape", "sha256": "", "source_utc": snap_utc})

    builder_files = [Path(__file__)]
    header = build_header("nba", str(slate_date), built_t.isoformat(),
                          builder_files, sources[-1:])  # newest source

    # Build game entries
    from nba.pipeline.nba_outcomes import _ODDS_TO_ABBR
    game_entries = []
    first_ct = None
    for eid, g in sorted(games.items(), key=lambda x: x[1]["commence_time"]):
        ct = parse_utc(g["commence_time"])
        if first_ct is None or ct < first_ct:
            first_ct = ct
        home_abbr = _ODDS_TO_ABBR.get(g["home_team"], g["home_team"])
        away_abbr = _ODDS_TO_ABBR.get(g["away_team"], g["away_team"])
        entry = {
            "event_id": eid,
            "home": g["home_team"],
            "away": g["away_team"],
            "commence_time": g["commence_time"],
            "layers": {
                "market": _market_layer(eid, g["home_team"], tape_snaps, built_t, season),
                "news": _news_layer(str(slate_date), built_t, g["home_team"], g["away_team"],
                                    news_file),
                "history": _history_layer(str(slate_date), home_abbr, away_abbr),
                "model": _model_layer(home_abbr, away_abbr),
            }
        }
        game_entries.append(entry)

    return build_packet(header, game_entries, first_ct.isoformat() if first_ct else None)


def main():
    ap = argparse.ArgumentParser(description="NBA packet builder")
    ap.add_argument("--date", required=True, help="Slate date YYYY-MM-DD")
    ap.add_argument("--built-utc", default=None, help="Built timestamp (default: now)")
    ap.add_argument("--news-file", default=None, help="Manual news CSV")
    ap.add_argument("--out", default=None, help="Output JSON path")
    args = ap.parse_args()

    packet = build_nba_packet(args.date, args.built_utc, args.news_file)
    canonical = to_canonical_json(packet)
    sha = packet_sha256(packet)

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(canonical)
        print(f"packet -> {args.out}", file=sys.stderr)
    else:
        print(canonical)
    print(f"sha256 {sha}", file=sys.stderr)
    print(f"games: {len(packet['games'])}", file=sys.stderr)


if __name__ == "__main__":
    main()
