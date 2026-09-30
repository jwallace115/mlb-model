#!/usr/bin/env python3
"""NHL packet builder — assembles the layers the reader sees before freezing.

Usage:
  python3 nhl/layers/build_packet_nhl.py --date 2026-09-29 [--built-utc ISO] [--news-file PATH]

Layers:
  L1 market  — Pinnacle open/current/move, min/max across books, event_markets summary
  L2 news    — goalie-probe observations + --news-file CSV
  L3 history — season-to-date records from NHL API finals strictly before the slate date
  L4 model   — pre-game probability from nhl_model_outputs.parquet, else {"absent": reason}
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone, date as _date
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shared.layers.packet import (
    build_header, build_packet, to_canonical_json, packet_sha256, parse_utc, builder_sha256
)
from nfl.pipeline.log_ai_opinions import (
    SPORTS, set_sport, implied, GAME_MARKETS, nhl_season
)

ET = ZoneInfo("America/New_York")
BOOK = "pinnacle"


def _load_tape_snapshots(season):
    """Load all tape snapshots for a season, sorted by snapshot_utc."""
    tape_dir = SPORTS["nhl"]["lines"] / f"season={season}"
    if not tape_dir.exists():
        return []
    result = []
    for f in sorted(tape_dir.glob("snap_*.parquet")):
        df = pd.read_parquet(f)
        if df.empty:
            continue
        result.append((str(df["snapshot_utc"].iloc[0]), df))
    return result


def _devig_pair(price_a, price_b):
    """De-vig two-outcome prices -> probability of side A."""
    ia, ib = implied(price_a), implied(price_b)
    return ia / (ia + ib)


def _market_layer(event_id, home_team, tape_snaps, built_t, event_markets_dir, season):
    """L1: market data for one game."""
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
        # Open (first tape snapshot)
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
        # Current (newest <= built_utc)
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
            # Move
            if "open" in mk_data and "current" in mk_data:
                mk_data["move"] = round(mk_data["current"]["q_first"] - mk_data["open"]["q_first"], 6)
            # Min/max across ALL books in current snap
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
        if not mk_data.get("current") and not mk_data.get("open"):
            mk_data["missing"] = True
        layer[mk] = mk_data

    # Event markets summary (WO12's files, when present)
    em_dir = ROOT / "data" / "odds_archive" / "nhl" / "event_markets" / f"season={season}"
    if em_dir.exists():
        em_snaps = sorted(em_dir.glob("snap_*.parquet"))
        newest_em = None
        for f in em_snaps:
            em = pd.read_parquet(f)
            ev_em = em[em["event_id"] == event_id] if "event_id" in em.columns else pd.DataFrame()
            if ev_em.empty:
                continue
            snap_col = "snapshot_utc" if "snapshot_utc" in em.columns else "pull_timestamp"
            if snap_col not in em.columns:
                continue
            snap_t = parse_utc(str(em[snap_col].iloc[0]))
            if snap_t <= built_t:
                newest_em = ev_em
        if newest_em is not None and "bookmaker" in newest_em.columns and "market" in newest_em.columns:
            counts = newest_em.groupby(["bookmaker", "market"]).size().reset_index(name="lines")
            layer["event_markets_summary"] = counts.to_dict("records")

    return layer


def _news_layer(event_id, slate_date, built_t, goalie_dir=None, news_file=None):
    """L2: news (goalie probes + manual news CSV)."""
    layer = {"goalie_probes": [], "manual_news": []}
    # Goalie probes from item 4
    gd = goalie_dir or (ROOT / "data" / "news_archive" / "nhl" / "goalies" / f"date={slate_date}")
    if gd.exists():
        pulls_file = gd / "_pulls.jsonl"
        if pulls_file.exists():
            for line in pulls_file.read_text().strip().split("\n"):
                if not line.strip():
                    continue
                rec = json.loads(line)
                rec_t = parse_utc(rec.get("retrieved_utc", "9999-01-01T00:00:00Z"))
                if rec_t <= built_t:
                    layer["goalie_probes"].append(rec)
    # Manual news CSV
    if news_file:
        nf = Path(news_file)
        if not nf.exists():
            raise SystemExit(f"HALT: news file {news_file} not found")
        import csv
        with open(nf) as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                if not row.get("url"):
                    raise SystemExit(f"HALT: news row missing url: {row}")
                if not row.get("retrieved_utc"):
                    raise SystemExit(f"HALT: news row missing retrieved_utc: {row}")
                layer["manual_news"].append(row)
    if not layer["goalie_probes"] and not layer["manual_news"]:
        layer["status"] = "no observations yet"
    return layer


def _history_layer(event_id, home_abbr, away_abbr, slate_date, season):
    """L3: point-in-time season-to-date records from cached boxscores."""
    from nhl.pipeline.nhl_outcomes import load_all_results
    results = load_all_results(season)
    sd = _date.fromisoformat(str(slate_date))
    layer = {}
    for abbr in (home_abbr, away_abbr):
        gp = w = l = otl = gf = ga = 0
        last_10 = []
        last_game_date = None
        team_games = sorted(
            [r for r in results if abbr in (r["home_abbr"], r["away_abbr"])
             and _date.fromisoformat(str(r["game_date"])[:10]) < sd],
            key=lambda r: r["game_date"]
        )
        for g in team_games:
            gp += 1
            is_home = g["home_abbr"] == abbr
            team_score = g["home_score"] if is_home else g["away_score"]
            opp_score = g["away_score"] if is_home else g["home_score"]
            gf += team_score
            ga += opp_score
            if team_score > opp_score:
                w += 1
                last_10.append("W")
            elif team_score < opp_score:
                if g["went_to_ot"]:
                    otl += 1
                    last_10.append("OTL")
                else:
                    l += 1
                    last_10.append("L")
            else:
                last_10.append("T")  # shouldn't happen with OT/SO
            last_game_date = str(g["game_date"])[:10]
        # Rest days and back-to-back
        rest_days = None
        back_to_back = False
        if last_game_date:
            rest_days = (sd - _date.fromisoformat(last_game_date)).days
            back_to_back = rest_days == 1
        layer[abbr] = {
            "gp": gp, "w": w, "l": l, "otl": otl,
            "gf": gf, "ga": ga,
            "last_10": last_10[-10:] if last_10 else [],
            "rest_days": rest_days,
            "back_to_back": back_to_back,
        }
    # 2025-26 final record (for context)
    prev_results = load_all_results(season - 1) if season > 2021 else []
    if prev_results:
        for abbr in (home_abbr, away_abbr):
            prev_games = [r for r in prev_results if abbr in (r["home_abbr"], r["away_abbr"])]
            pw = sum(1 for g in prev_games if
                     (g["home_score"] > g["away_score"] and g["home_abbr"] == abbr) or
                     (g["away_score"] > g["home_score"] and g["away_abbr"] == abbr))
            pl = sum(1 for g in prev_games if
                     (g["home_score"] < g["away_score"] and g["home_abbr"] == abbr and not g["went_to_ot"]) or
                     (g["away_score"] < g["home_score"] and g["away_abbr"] == abbr and not g["went_to_ot"]))
            potl = len(prev_games) - pw - pl
            layer[abbr]["prev_season"] = {"gp": len(prev_games), "w": pw, "l": pl, "otl": potl}
    return layer


def _model_layer(event_id, home_abbr, away_abbr, slate_date, built_t, season):
    """L4: pre-game probability from existing NHL model output."""
    model_path = ROOT / "nhl" / "nhl_model_outputs.parquet"
    if not model_path.exists():
        return {"absent": f"model output file not found: {model_path.relative_to(ROOT)}"}
    df = pd.read_parquet(model_path)
    # Check if any row covers this game
    sd = str(slate_date)[:10]
    match = df[(df["game_date"].astype(str).str[:10] == sd) &
               (((df["home_team"] == home_abbr) & (df["away_team"] == away_abbr)) |
                ((df["home_team"] == away_abbr) & (df["away_team"] == home_abbr)))]
    if match.empty:
        last_date = str(df["game_date"].max())[:10]
        return {"absent": f"no model output for {away_abbr}@{home_abbr} on {sd}; outputs end {last_date}"}
    row = match.iloc[0]
    return {
        "sim_over_prob": round(float(row["sim_over_prob_closing"]), 6),
        "sim_under_prob": round(float(row["sim_under_prob_closing"]), 6),
        "closing_total": float(row["closing_total"]),
        "source_file": str(model_path.relative_to(ROOT)),
    }


def build_nhl_packet(slate_date, built_utc=None, news_file=None):
    """Build the full NHL packet for a slate date."""
    set_sport("nhl")
    season = nhl_season(slate_date)
    if built_utc is None:
        built_utc = datetime.now(timezone.utc).isoformat()
    built_t = parse_utc(built_utc)
    tape_snaps = _load_tape_snapshots(season)
    # Get all games on this ET date from the tape
    sd = _date.fromisoformat(str(slate_date)[:10])
    games_seen = {}
    for snap_utc, df in tape_snaps:
        pin = df[df["bookmaker"] == BOOK]
        for eid in pin["event_id"].unique():
            if eid in games_seen:
                continue
            ev = pin[pin["event_id"] == eid].iloc[0]
            ct = parse_utc(ev["commence_time"])
            if ct.astimezone(ET).date() == sd:
                from nhl.pipeline.nhl_outcomes import odds_to_nhl
                home_abbr = odds_to_nhl(ev["home_team"])
                away_abbr = odds_to_nhl(ev["away_team"])
                games_seen[eid] = {
                    "event_id": eid,
                    "home": ev["home_team"],
                    "away": ev["away_team"],
                    "home_abbr": home_abbr,
                    "away_abbr": away_abbr,
                    "commence_time": str(ev["commence_time"]),
                }
    if not games_seen:
        raise SystemExit(f"HALT: no games found on {slate_date} in the tape")

    # Sources
    sources = []
    for snap_utc, _ in tape_snaps:
        snap_t = parse_utc(snap_utc)
        if snap_t < built_t:
            snap_dir = SPORTS["nhl"]["lines"] / f"season={season}"
            # Find the file for this snap
            for f in snap_dir.glob("snap_*.parquet"):
                df_check = pd.read_parquet(f, columns=["snapshot_utc"])
                if str(df_check["snapshot_utc"].iloc[0]) == snap_utc:
                    sources.append({
                        "path": str(f.relative_to(ROOT)),
                        "sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
                        "source_utc": snap_utc,
                    })
                    break

    # Builder source files
    builder_files = [
        Path(__file__).resolve(),
        ROOT / "shared" / "layers" / "packet.py",
    ]
    header = build_header("nhl", slate_date, built_utc, builder_files, sources)

    # Build game entries
    game_entries = []
    for eid, ginfo in sorted(games_seen.items(), key=lambda x: x[1]["commence_time"]):
        layers = {
            "market": _market_layer(eid, ginfo["home"], tape_snaps, built_t,
                                     ROOT / "data" / "odds_archive" / "nhl" / "event_markets", season),
            "news": _news_layer(eid, slate_date, built_t, news_file=news_file),
            "history": _history_layer(eid, ginfo["home_abbr"], ginfo["away_abbr"], slate_date, season),
            "model": _model_layer(eid, ginfo["home_abbr"], ginfo["away_abbr"], slate_date, built_t, season),
        }
        game_entries.append({
            "event_id": eid,
            "home": ginfo["home"],
            "away": ginfo["away"],
            "commence_time": ginfo["commence_time"],
            "layers": layers,
        })

    first_ct = min(g["commence_time"] for g in game_entries)
    return build_packet(header, game_entries, first_ct)


def main():
    ap = argparse.ArgumentParser(description="Build NHL packet for a slate date")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD slate date (ET)")
    ap.add_argument("--built-utc", default=None, help="ISO UTC timestamp for built_utc")
    ap.add_argument("--news-file", default=None, help="CSV with columns: game, url, retrieved_utc, text")
    ap.add_argument("--out", default=None, help="output path (default: stdout)")
    a = ap.parse_args()
    packet = build_nhl_packet(a.date, a.built_utc, a.news_file)
    text = to_canonical_json(packet)
    sha = hashlib.sha256(text.encode()).hexdigest()
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(text + "\n")
        print(f"Packet written: {a.out}")
    else:
        print(text)
    print(f"sha256: {sha}", file=sys.stderr)
    print(f"games: {len(packet['games'])}, sources: {len(packet['header']['sources'])}", file=sys.stderr)


if __name__ == "__main__":
    main()
