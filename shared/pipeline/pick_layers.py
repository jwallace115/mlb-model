#!/usr/bin/env python3
"""
Build frozen detail cards for ranked picks. Write-once to PICKS_LEDGER_DIR/layers/.

Each card contains layers (line_movement, weather, sim, injuries, news, reasoning)
frozen at the pick's logged_utc — no file timestamped after logged_utc is ever read (A2).

OPS3 Item 2, P11.
"""
import argparse
import gzip
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_top20 as bt
import picks_ledger as pl

ROOT = Path(os.environ.get("MLB_REPO_ROOT") or Path(__file__).resolve().parent.parent.parent)
LEDGER_DIR = Path(os.environ.get("PICKS_LEDGER_DIR") or "/root/private/ledger")
TS_RE = re.compile(r"(\d{8}T\d{4}(?:\d{2})?Z)")

# ---- helpers ----
def _parse_dt(s):
    if not s:
        return None
    s = str(s).strip()
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def _file_ts(p):
    m = TS_RE.search(p.name)
    if m:
        s = m.group(1)
        fmt = "%Y%m%dT%H%M%SZ" if len(s) == 16 else "%Y%m%dT%H%MZ"
        return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
    return datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)


def _files_before(folder, glob_pat, before_utc):
    """Return files matching glob whose timestamp <= before_utc, sorted by timestamp."""
    if not folder.exists():
        return []
    files = []
    for p in folder.glob(glob_pat):
        ts = _file_ts(p)
        if ts <= before_utc:
            files.append((ts, p))
    return sorted(files, key=lambda x: x[0])


def _layer(value, source, as_of):
    return {"value": value, "source": str(source), "as_of": str(as_of) if as_of else None}


def _no_data(logged_utc, reason="no data"):
    return {"value": None, "source": None, "as_of": str(logged_utc), "note": f"{reason} as of {str(logged_utc)[:19]}"}


# ---- tape cache ----
_tape_cache = {}

def _load_tape_cached(path):
    s = str(path)
    if s not in _tape_cache:
        _tape_cache[s] = pd.read_parquet(path)
    return _tape_cache[s]


# ---- line movement ----
def _line_movement(pick, root, logged_dt):
    sport_folder = {"NFL": "nfl", "NCAAF": "ncaaf", "NHL": "nhl", "NBA": "nba"}.get(pick.get("sport"))
    if not sport_folder:
        return _no_data(logged_dt, "unsupported sport")

    eid = pick.get("event_id")
    market = pick.get("market", "")
    player_name = pick.get("player_name")
    book = pick.get("book")
    side = pick.get("side")
    point = pick.get("point")
    commence_dt = _parse_dt(pick.get("commence_time"))
    if not commence_dt:
        return _no_data(logged_dt, "no commence_time")

    # Determine tape folder
    is_prop = market and (market.startswith("prop") or "player_" in market)
    if is_prop:
        tape_dir = root / "data" / "odds_archive" / sport_folder / "props"
    else:
        tape_dir = root / "data" / "odds_archive" / sport_folder / "line_history"

    window_start = commence_dt - timedelta(days=7)
    files = []
    for season_dir in tape_dir.glob("season=*") if not is_prop else tape_dir.glob("season=*/month=*"):
        pat = "data_*.parquet" if is_prop else "snap_*Z.parquet"
        for ts, p in _files_before(season_dir, pat, logged_dt):
            if ts >= window_start:
                files.append((ts, p))

    if not files:
        return _no_data(logged_dt, "no tape files in window")

    # Read and filter for this event + market
    sources_used = []
    rows = []
    for ts, p in files:
        df = _load_tape_cached(p)
        if is_prop:
            mask = df.event_id == eid
            if player_name:
                mask &= df.player_name == player_name
        else:
            mask = (df.event_id == eid)
            tape_market = {"spread": "spreads", "moneyline": "h2h", "total": "totals"}.get(market, market)
            mask &= df.market == tape_market
        matched = df[mask]
        if not matched.empty:
            for _, r in matched.iterrows():
                rows.append({"ts": ts, "file": p.name, **r.to_dict()})
            sources_used.append(p.name)

    if not rows:
        return _no_data(logged_dt, "no tape rows for this event/market")

    # Build summary: earliest and latest for pick's book + consensus
    earliest = rows[0]
    latest = rows[-1]

    # Filter for pick's book
    book_rows = [r for r in rows if r.get("bookmaker") == book] if book else []
    book_open = book_rows[0] if book_rows else None
    book_close = book_rows[-1] if book_rows else None

    def _price_from_row(r, is_prop_mkt):
        if is_prop_mkt:
            if side and "over" in str(side).lower():
                return r.get("over_price")
            elif side and "under" in str(side).lower():
                return r.get("under_price")
            return r.get("over_price")
        else:
            return r.get("price")

    result = {
        "event_id": eid, "market": market, "book": book,
        "open": {"price": _price_from_row(earliest, is_prop), "source": earliest.get("file"), "as_of": str(earliest.get("ts"))[:19]} if earliest else None,
        "close": {"price": _price_from_row(latest, is_prop), "source": latest.get("file"), "as_of": str(latest.get("ts"))[:19]} if latest else None,
    }
    if book_open:
        result["book_open"] = {"price": _price_from_row(book_open, is_prop), "source": book_open.get("file")}
    if book_close:
        result["book_close"] = {"price": _price_from_row(book_close, is_prop), "source": book_close.get("file")}

    return _layer(result, ", ".join(sources_used[:5]) + (f" (+{len(sources_used)-5})" if len(sources_used) > 5 else ""),
                  latest.get("ts") if latest else logged_dt)


# ---- weather ----
def _weather(pick, root, logged_dt):
    sport = pick.get("sport", "")
    if sport not in ("NFL",):
        return _no_data(logged_dt, "no NWS source for this sport")

    home = pick.get("home", "")
    forecast_dir = root / "data" / "weather_archive" / "nws" / "forecasts"
    files = []
    for sd in forecast_dir.glob("season=*"):
        for ts, p in _files_before(sd, "snap_*Z.parquet", logged_dt):
            files.append((ts, p))

    if not files:
        return _no_data(logged_dt, "no NWS files")

    # Use the nearest-before file
    ts, path = files[-1]
    df = pd.read_parquet(path)

    # Match by team name
    team_rows = df[df.team.str.contains(home.split()[-1] if home else "NOMATCH", case=False, na=False)]
    if team_rows.empty:
        # Try stadium_key abbreviation
        for abbr in ("ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN",
                     "GB", "HOU", "IND", "JAX", "KC", "MIA", "NE", "NYG", "PHI", "PIT",
                     "SEA", "SF", "TB", "TEN", "WAS"):
            if abbr.lower() in home.lower() or home.lower() in df[df.stadium_key == abbr].team.str.lower().values.tolist():
                team_rows = df[df.stadium_key == abbr]
                break

    if team_rows.empty:
        return _no_data(logged_dt, f"no NWS data for {home}")

    roof = team_rows.iloc[0].get("roof", "")
    if roof in ("dome", "retractable"):
        return _layer({"indoor": True, "stadium": team_rows.iloc[0].get("stadium", ""), "roof": roof},
                      path.name, ts)

    # Find forecast window covering commence_time
    commence_dt = _parse_dt(pick.get("commence_time"))
    if not commence_dt:
        return _no_data(logged_dt, "no commence_time for weather")

    best = None
    for _, r in team_rows.iterrows():
        vs = _parse_dt(r.get("valid_start"))
        ve = _parse_dt(r.get("valid_end"))
        if vs and ve and vs <= commence_dt < ve:
            best = r
            break

    if best is None:
        # Take the closest
        best = team_rows.iloc[0]

    wx = {
        "stadium": best.get("stadium", ""),
        "roof": roof,
        "temp_f": best.get("temp_f"),
        "wind_mph": best.get("wind_mph_mean"),
        "wind_dir": best.get("wind_dir"),
        "precip_prob_pct": best.get("precip_prob_pct"),
        "forecast": best.get("short_forecast"),
    }
    return _layer(wx, path.name, ts)


# ---- sim ----
def _sim(pick, root, logged_dt):
    sport = pick.get("sport", "")
    if sport != "NFL":
        return _no_data(logged_dt, "sim: no number for this sport")

    # Find sim freezes (ai_opinions with reader_model nfl_sim_v1_*)
    sim_dir = root / "nfl" / "data" / "board"
    best_file = None
    best_ts = None
    for week_dir in sim_dir.glob("week=*"):
        ai_dir = week_dir / "ai_opinions"
        if not ai_dir.exists():
            continue
        for p in ai_dir.glob("ai_opinions_*.parquet"):
            ts = _file_ts(p)
            if ts <= logged_dt:
                if best_ts is None or ts > best_ts:
                    best_ts = ts
                    best_file = p

    if best_file is None:
        return _no_data(logged_dt, "sim: no freeze file")

    df = pd.read_parquet(best_file)
    if "reader_model" not in df.columns:
        return _no_data(logged_dt, "sim: no reader_model column")

    sim_rows = df[df.reader_model.str.startswith("nfl_sim", na=False)]
    if sim_rows.empty:
        return _no_data(logged_dt, "sim: no sim rows in freeze")

    eid = pick.get("event_id")
    market = pick.get("market", "")
    player_name = pick.get("player_name")
    point = pick.get("point")
    side = pick.get("side")

    # Map market to market_key
    market_key_map = {"spread": "spreads", "moneyline": "h2h", "total": "totals"}
    mk = market_key_map.get(market, market)
    if market.startswith("prop:"):
        mk = "player_" + market.split(":", 1)[1]

    mask = (sim_rows.event_id == eid) & (sim_rows.market_key == mk)
    if player_name:
        mask &= sim_rows.player_name == player_name
    if point is not None:
        mask &= sim_rows.line == point

    matched = sim_rows[mask]
    if matched.empty:
        return _no_data(logged_dt, "sim: no number for this leg")

    row = matched.iloc[0]
    return _layer({
        "p_first": float(row.p_first) if pd.notna(row.p_first) else None,
        "book_p_first": float(row.book_p_first) if pd.notna(row.book_p_first) else None,
        "edge": float(row.edge) if pd.notna(row.edge) else None,
        "reader_model": str(row.reader_model),
    }, best_file.name, best_ts)


# ---- injuries ----
def _injuries(pick, root, logged_dt):
    sport = pick.get("sport", "")
    home = pick.get("home", "")
    away = pick.get("away", "")
    player_name = pick.get("player_name")

    if sport == "NFL":
        inj_dir = root / "data" / "injury_archive" / "nfl"
    else:
        return _no_data(logged_dt, "no injury source for this sport")

    files = []
    for sd in inj_dir.glob("season=*"):
        for ts, p in _files_before(sd, "injuries_*Z.json.gz", logged_dt):
            files.append((ts, p))

    if not files:
        return _no_data(logged_dt, "no injury files")

    ts, path = files[-1]  # newest before logged_utc
    try:
        with gzip.open(path, "rt") as f:
            data = json.load(f)
    except Exception:
        return _no_data(logged_dt, f"cannot read {path.name}")

    result = {"player": None, "home_team": [], "away_team": []}
    for team in data.get("injuries", []):
        team_name = team.get("displayName", "")
        is_home = home and home.split()[-1].lower() in team_name.lower()
        is_away = away and away.split()[-1].lower() in team_name.lower()
        for inj in team.get("injuries", []):
            athlete = inj.get("athlete", {})
            entry = {
                "name": athlete.get("displayName", ""),
                "status": inj.get("status", ""),
                "comment": (inj.get("shortComment") or "")[:200],
            }
            if player_name and athlete.get("displayName", "").lower() == player_name.lower():
                result["player"] = entry
            if is_home and inj.get("status") in ("Out", "Doubtful", "Questionable"):
                result["home_team"].append(entry)
            elif is_away and inj.get("status") in ("Out", "Doubtful", "Questionable"):
                result["away_team"].append(entry)

    return _layer(result, path.name, ts)


# ---- news ----
def _news(pick, root, logged_dt):
    sport = pick.get("sport", "")
    sport_folder = {"NFL": "nfl", "NCAAF": "ncaaf"}.get(sport)
    if not sport_folder:
        return _no_data(logged_dt, "no news source for this sport")

    news_dir = root / "data" / "news_archive" / sport_folder
    files = []
    cutoff = logged_dt - timedelta(hours=72)
    for sd in news_dir.glob("season=*"):
        for ts, p in _files_before(sd, "news_*Z.json.gz", logged_dt):
            if ts >= cutoff:
                files.append((ts, p))

    if not files:
        return _no_data(logged_dt, "no news files within 72h")

    # Read and filter for player/team mentions
    home = pick.get("home", "")
    away = pick.get("away", "")
    player_name = pick.get("player_name")
    items = []
    sources = []

    for ts, p in files:
        try:
            with gzip.open(p, "rt") as f:
                data = json.load(f)
        except Exception:
            continue
        sources.append(p.name)
        if isinstance(data, list):
            # news files are article objects
            for article in data:
                headline = article.get("headline", "") or article.get("title", "")
                text = headline + " " + (article.get("description", "") or "")
                # Check mentions
                mentioned = False
                if player_name and player_name.lower() in text.lower():
                    mentioned = True
                if home and home.split()[-1].lower() in text.lower():
                    mentioned = True
                if away and away.split()[-1].lower() in text.lower():
                    mentioned = True
                if mentioned:
                    items.append({
                        "headline": headline[:200],
                        "published": str(article.get("published", ""))[:19],
                        "source_file": p.name,
                    })

    if not items:
        return _layer([], ", ".join(sources[:3]), logged_dt)

    return _layer(items[:10], ", ".join(sources[:3]), files[-1][0])


# ---- reasoning ----
def _reasoning(pick):
    return {
        "value": {
            "reason": pick.get("reason"),
            "tag": pick.get("tag"),
            "conf": pick.get("conf"),
        },
        "source": "picks.jsonl",
        "as_of": pick.get("logged_utc"),
    }


# ---- card builder ----
def build_card(pick, root):
    """Build a detail card for a single pick. Returns the card dict."""
    logged_dt = _parse_dt(pick.get("logged_utc"))
    if not logged_dt:
        raise pl.Halt(f"pick {pick.get('pick_id')} has no logged_utc")

    root = Path(root)
    card = {
        "pick_id": pick.get("pick_id"),
        "logged_utc": pick.get("logged_utc"),
        "commence_time": pick.get("commence_time"),
        "sport": pick.get("sport"),
        "market": pick.get("market"),
        "player_name": pick.get("player_name"),
        "side": pick.get("side"),
        "point": pick.get("point"),
        "home": pick.get("home"),
        "away": pick.get("away"),
        "layers": {
            "line_movement": _line_movement(pick, root, logged_dt),
            "weather": _weather(pick, root, logged_dt),
            "sim": _sim(pick, root, logged_dt),
            "injuries": _injuries(pick, root, logged_dt),
            "news": _news(pick, root, logged_dt),
            "reasoning": _reasoning(pick),
        },
    }
    card["sha256"] = hashlib.sha256(json.dumps(card, sort_keys=True, default=str).encode()).hexdigest()[:16]
    return card


def write_card(pick, root, layers_dir):
    """Write-once: build and write card if absent. Returns (status, path)."""
    layers_dir = Path(layers_dir)
    layers_dir.mkdir(parents=True, exist_ok=True)
    pid = pick.get("pick_id")
    path = layers_dir / f"{pid}.json"
    if path.exists():
        return "exists", path
    card = build_card(pick, root)
    path.write_text(json.dumps(card, indent=1, default=str))
    return "built", path


def main():
    ap = argparse.ArgumentParser(description="Build detail cards for ranked picks")
    ap.add_argument("--build-missing", action="store_true", help="Build cards for currently ranked picks")
    ap.add_argument("--as-of", help="UTC datetime for selection (default: now)")
    ap.add_argument("--pick-id", help="Build card for a specific pick_id")
    a = ap.parse_args()

    now = datetime.fromisoformat(a.as_of) if a.as_of else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    if not LEDGER_DIR.exists():
        print(f"HALT: PICKS_LEDGER_DIR={LEDGER_DIR} does not exist")
        sys.exit(1)

    layers_dir = LEDGER_DIR / "layers"
    view_rows = pl.view(LEDGER_DIR)

    if a.pick_id:
        pick = next((r for r in view_rows if r.get("pick_id") == a.pick_id), None)
        if not pick:
            print(f"HALT: pick_id {a.pick_id} not found")
            sys.exit(1)
        status, path = write_card(pick, ROOT, layers_dir)
        print(f"{a.pick_id}: {status} → {path}")
        return

    if a.build_missing:
        built = 0
        exists = 0
        for sport in bt.SPORTS:
            result = bt.select(view_rows, sport, now)
            if result is None:
                print(f"{sport}: no upcoming freeze")
                continue
            picks = result["props"] + result["sides"]
            for pick in picks:
                status, path = write_card(pick, ROOT, layers_dir)
                if status == "built":
                    built += 1
                else:
                    exists += 1
        print(f"built {built} / exists {exists}")
        return

    print("use --build-missing or --pick-id <id>")


if __name__ == "__main__":
    main()
