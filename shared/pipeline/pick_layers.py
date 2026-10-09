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
import pick_sources as ps
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
    window_start = commence_dt - timedelta(days=7)

    sources_used = []
    rows = []

    # Normalise side for matching tape outcome_name
    side_norm = ps.nfl_team(side) if side else None  # nickname like "seahawks"

    def _outcome_matches(outcome_name):
        """Does this tape outcome match the pick's side?"""
        if not side:
            return True
        s_lower = str(side).lower()
        o_lower = str(outcome_name).lower()
        if s_lower == "over" or s_lower == "under":
            return o_lower == s_lower
        # NFL team matching
        o_nick = ps.nfl_team(outcome_name)
        if side_norm and o_nick:
            return side_norm == o_nick
        return s_lower in o_lower or o_lower in s_lower

    def _nearest_line_per_group(candidates_df, pick_point, ts_col, book_col="bookmaker"):
        """Apply nearest-line within each (timestamp, bookmaker) group, not across the file."""
        if pick_point is None or candidates_df.empty:
            return candidates_df
        line_col = "line" if "line" in candidates_df.columns else "point"
        if line_col not in candidates_df.columns:
            return candidates_df
        result_parts = []
        for (ts_val, bk), grp in candidates_df.groupby([ts_col, book_col], dropna=False):
            grp = grp.copy()
            grp["_dist"] = (grp[line_col].astype(float) - float(pick_point)).abs()
            best_dist = grp["_dist"].min()
            result_parts.append(grp[grp["_dist"] == best_dist].drop(columns=["_dist"]))
        if not result_parts:
            return candidates_df.iloc[:0]
        return pd.concat(result_parts, ignore_index=True)

    if is_prop:
        tape_dir = root / "data" / "odds_archive" / sport_folder / "props"
        prop_market = ps.ledger_to_tape_market(market) if ":" in market else market
        for month_dir in tape_dir.glob("season=*/month=*"):
            for p in month_dir.glob("data_*.parquet"):
                df = _load_tape_cached(p)
                if "pull_timestamp" not in df.columns:
                    continue
                df["_pt"] = pd.to_datetime(df.pull_timestamp, utc=True, errors="coerce")
                mask = (df.event_id == eid) & (df._pt >= window_start) & (df._pt <= logged_dt)
                if player_name:
                    mask &= df.player_name == player_name
                # Filter by market_key
                if "market_key" in df.columns:
                    mask &= df.market_key == prop_market
                matched = _nearest_line_per_group(df[mask], point, "_pt", "bookmaker")
                if not matched.empty:
                    for _, r in matched.iterrows():
                        rows.append({"ts": r["_pt"], "file": p.name, **{k: v for k, v in r.items() if k not in ("_pt",)}})
                    sources_used.append(p.name)
        rows.sort(key=lambda r: r.get("ts") or datetime.min.replace(tzinfo=timezone.utc))
    else:
        tape_dir = root / "data" / "odds_archive" / sport_folder / "line_history"
        files = []
        for season_dir in tape_dir.glob("season=*"):
            for ts, p in _files_before(season_dir, "snap_*Z.parquet", logged_dt):
                if ts >= window_start:
                    files.append((ts, p))
        for ts, p in files:
            df = _load_tape_cached(p)
            tape_market = {"spread": "spreads", "moneyline": "h2h", "total": "totals"}.get(market, market)
            mask = (df.event_id == eid) & (df.market == tape_market)
            # Filter by outcome_name for the pick's side
            if "outcome_name" in df.columns:
                mask &= df.outcome_name.apply(_outcome_matches)
            filtered = df[mask].copy()
            if not filtered.empty:
                filtered["_snap_ts"] = str(ts)
                matched = _nearest_line_per_group(filtered, point, "_snap_ts", "bookmaker")
                matched = matched.drop(columns=["_snap_ts"], errors="ignore")
                for _, r in matched.iterrows():
                    rows.append({"ts": ts, "file": p.name, **r.to_dict()})
                sources_used.append(p.name)

    if not rows:
        return _no_data(logged_dt, "no tape rows for this event/market")

    def _price_from_row(r, is_prop_mkt):
        if is_prop_mkt:
            if side and "over" in str(side).lower():
                return r.get("over_price")
            elif side and "under" in str(side).lower():
                return r.get("under_price")
            return r.get("over_price")
        else:
            return r.get("price")

    def _point_from_row(r, is_prop_mkt):
        if is_prop_mkt:
            return r.get("line")
        return r.get("point")

    # Build structured result: book open/close + consensus
    book_rows = [r for r in rows if r.get("bookmaker") == book] if book else []
    all_rows_by_ts = {}
    for r in rows:
        ts_key = str(r.get("ts"))[:19]
        all_rows_by_ts.setdefault(ts_key, []).append(r)

    ts_keys = sorted(all_rows_by_ts.keys())
    earliest_ts = ts_keys[0] if ts_keys else None
    latest_ts = ts_keys[-1] if ts_keys else None

    def _consensus_at(ts_key):
        """Median point across books (one row per book, nearest line)."""
        ts_rows = all_rows_by_ts.get(ts_key, [])
        by_book = {}
        for r in ts_rows:
            bk = r.get("bookmaker", "?")
            if bk not in by_book:
                by_book[bk] = r
        points = [_point_from_row(r, is_prop) for r in by_book.values() if _point_from_row(r, is_prop) is not None]
        if not points:
            return None
        points.sort()
        mid = len(points) // 2
        median = points[mid] if len(points) % 2 else (points[mid - 1] + points[mid]) / 2
        return {"median_point": median, "n_books": len(points), "as_of": ts_key}

    book_open = book_rows[0] if book_rows else None
    book_close = book_rows[-1] if book_rows else None

    result = {
        "book": {
            "open": {"point": _point_from_row(book_open, is_prop), "price": _price_from_row(book_open, is_prop),
                     "as_of": str(book_open.get("ts"))[:19]} if book_open else None,
            "close": {"point": _point_from_row(book_close, is_prop), "price": _price_from_row(book_close, is_prop),
                      "as_of": str(book_close.get("ts"))[:19]} if book_close else None,
        } if book_rows else None,
        "consensus": {
            "open": _consensus_at(earliest_ts),
            "close": _consensus_at(latest_ts),
        },
        "n_rows": len(rows),
    }
    if book_open and book_close:
        op = _point_from_row(book_open, is_prop)
        cp = _point_from_row(book_close, is_prop)
        opr = _price_from_row(book_open, is_prop)
        cpr = _price_from_row(book_close, is_prop)
        result["book"]["move_points"] = (cp - op) if op is not None and cp is not None else None
        result["book"]["move_price"] = (cpr - opr) if opr is not None and cpr is not None else None

    return _layer(result, ", ".join(sorted(set(sources_used))[:5]) + (f" (+{len(set(sources_used))-5})" if len(set(sources_used)) > 5 else ""),
                  rows[-1].get("ts") if rows else logged_dt)


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
_sim_file_is_sim = {}  # cache: str(path) -> bool

def _is_sim_file(p):
    """Check if an ai_opinions parquet has nfl_sim rows (cached per path)."""
    s = str(p)
    if s not in _sim_file_is_sim:
        try:
            rm = pd.read_parquet(p, columns=["reader_model"])
            _sim_file_is_sim[s] = rm.reader_model.str.startswith("nfl_sim", na=False).any()
        except Exception:
            _sim_file_is_sim[s] = False
    return _sim_file_is_sim[s]


def _sim(pick, root, logged_dt):
    sport = pick.get("sport", "")
    if sport != "NFL":
        return _no_data(logged_dt, "sim: no number for this sport")

    # Find the newest sim freeze ≤ logged_dt (only files with nfl_sim rows)
    sim_dir = root / "nfl" / "data" / "board"
    best_file = None
    best_ts = None
    for week_dir in sim_dir.glob("week=*"):
        ai_dir = week_dir / "ai_opinions"
        if not ai_dir.exists():
            continue
        for p in ai_dir.glob("ai_opinions_*.parquet"):
            ts = _file_ts(p)
            if ts <= logged_dt and _is_sim_file(p):
                if best_ts is None or ts > best_ts:
                    best_ts = ts
                    best_file = p

    if best_file is None:
        return _no_data(logged_dt, "sim: no freeze file")

    df = pd.read_parquet(best_file)
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
        mk = ps.ledger_to_tape_market(market)

    mask = (sim_rows.event_id == eid) & (sim_rows.market_key == mk)
    if player_name:
        mask &= sim_rows.player_name == player_name
    if point is not None:
        mask &= sim_rows.line == point

    matched = sim_rows[mask]
    if matched.empty:
        return _no_data(logged_dt, "sim: no number for this leg")

    row = matched.iloc[0]
    pilot = bool(row.pilot) if "pilot" in df.columns and pd.notna(row.pilot) else False
    return _layer({
        "p_first": float(row.p_first) if pd.notna(row.p_first) else None,
        "book_p_first": float(row.book_p_first) if pd.notna(row.book_p_first) else None,
        "edge": float(row.edge) if pd.notna(row.edge) else None,
        "reader_model": str(row.reader_model),
        "pilot": pilot,
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


def rebuild_card(pick, root, layers_dir, reason):
    """Rebuild a card whose line_movement.value is null. Write-once cards with
    a value are never touched. Returns (status, path)."""
    layers_dir = Path(layers_dir)
    pid = pick.get("pick_id")
    path = layers_dir / f"{pid}.json"
    if path.exists():
        existing = json.loads(path.read_text())
        lm = existing.get("layers", {}).get("line_movement", {})
        if lm.get("value") is not None:
            return "untouched", path  # has movement data — write-once stands
    card = build_card(pick, root)
    card["rebuilt_utc"] = datetime.now(timezone.utc).isoformat()
    card["rebuilt_reason"] = reason
    path.write_text(json.dumps(card, indent=1, default=str))
    return "rebuilt", path


def rebuild_layer(pick, root, layers_dir, layer_name, reason):
    """Rebuild a single layer in a card. Cards whose layer already has a value
    are untouched. Returns (status, path)."""
    layers_dir = Path(layers_dir)
    pid = pick.get("pick_id")
    path = layers_dir / f"{pid}.json"
    if not path.exists():
        return "no_card", path
    existing = json.loads(path.read_text())
    layer = existing.get("layers", {}).get(layer_name, {})
    if layer.get("value") is not None:
        return "untouched", path
    # Rebuild just this layer
    logged_dt = _parse_dt(pick.get("logged_utc"))
    if not logged_dt:
        return "no_logged_utc", path
    layer_fn = {"sim": _sim, "line_movement": _line_movement, "weather": _weather,
                "injuries": _injuries, "news": _news}
    fn = layer_fn.get(layer_name)
    if not fn:
        return "unknown_layer", path
    root = Path(root)
    new_layer = fn(pick, root, logged_dt)
    if new_layer.get("value") is None:
        return "still_null", path
    existing["layers"][layer_name] = new_layer
    existing["rebuilt_utc"] = datetime.now(timezone.utc).isoformat()
    existing["rebuilt_reason"] = reason
    # Recompute sha256
    card_for_hash = dict(existing)
    card_for_hash.pop("sha256", None)
    card_for_hash.pop("rebuilt_utc", None)
    card_for_hash.pop("rebuilt_reason", None)
    existing["sha256"] = hashlib.sha256(
        json.dumps(card_for_hash, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]
    path.write_text(json.dumps(existing, indent=1, default=str))
    return "rebuilt", path


def main():
    ap = argparse.ArgumentParser(description="Build detail cards for ranked picks")
    ap.add_argument("--build-missing", action="store_true", help="Build cards for currently ranked picks")
    ap.add_argument("--rebuild-empty-movement", action="store_true",
                    help="Rebuild cards whose line_movement.value is null (P27)")
    ap.add_argument("--as-of", help="UTC datetime for selection (default: now)")
    ap.add_argument("--pick-id", help="Build card for a specific pick_id")
    ap.add_argument("--rebuild-layer", help="Rebuild a specific layer (e.g. sim) on null cards")
    ap.add_argument("--freeze", help="Scope rebuild to picks from this freeze (logged_utc)")
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

    if a.rebuild_layer:
        if not a.freeze:
            print("HALT: --rebuild-layer requires --freeze <logged_utc>")
            sys.exit(1)
        freeze_dt = _parse_dt(a.freeze)
        if not freeze_dt:
            print(f"HALT: cannot parse --freeze {a.freeze}")
            sys.exit(1)
        rebuilt = 0
        untouched = 0
        skipped = 0
        for pick in view_rows:
            pdt = _parse_dt(pick.get("logged_utc"))
            if pdt is None or abs((pdt - freeze_dt).total_seconds()) > 1:
                skipped += 1
                continue
            status, path = rebuild_layer(pick, ROOT, layers_dir, a.rebuild_layer, f"P32 {a.rebuild_layer} lookup")
            if status == "rebuilt":
                rebuilt += 1
                print(f"  rebuilt: {pick.get('pick_id')}")
            else:
                untouched += 1
        print(f"rebuilt {rebuilt} / untouched {untouched} (skipped {skipped} other freezes)")
        return

    if a.rebuild_empty_movement:
        rebuilt = 0
        untouched = 0
        for pick in view_rows:
            status, path = rebuild_card(pick, ROOT, layers_dir, "P27 market map")
            if status == "rebuilt":
                rebuilt += 1
            else:
                untouched += 1
        print(f"rebuilt {rebuilt} / untouched {untouched}")
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
