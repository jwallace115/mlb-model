#!/usr/bin/env python3
"""
Pull tonight's NHL lines + player props from the Odds API.
Saves raw JSON to logs/cowork_stage/live_<date>/ and writes a markdown report.

Usage:
  python3 nhl/pipeline/pull_nhl_live_lines.py
"""
import hashlib, json, os, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=True)

KEY = os.getenv("ODDS_API_KEY", "")
KEY_FP = hashlib.sha256(KEY.strip().encode()).hexdigest()[:8] if KEY else "UNSET"
BASE = "https://api.the-odds-api.com/v4"

BOOKS = ["pinnacle", "draftkings", "fanduel", "betmgm", "williamhill_us",
         "betrivers", "bovada", "pointsbetus", "unibet_us", "betonlineag"]
BOOKS_STR = ",".join(BOOKS)

GAME_MARKETS = "h2h,spreads,totals"
PROP_MARKETS = ("player_points,player_assists,player_shots_on_goal,"
                "player_goal_scorer_anytime,player_total_saves,player_blocked_shots")

BOOK_ABBR = {
    "pinnacle": "PIN", "draftkings": "DK", "fanduel": "FD", "betmgm": "MGM",
    "williamhill_us": "CZR", "betrivers": "BR", "bovada": "BOV",
    "pointsbetus": "PBS", "unibet_us": "UNI", "betonlineag": "BOL",
}

MKT_LABEL = {
    "player_points": "Points", "player_assists": "Assists",
    "player_shots_on_goal": "SOG", "player_goal_scorer_anytime": "AGS",
    "player_total_saves": "Saves", "player_blocked_shots": "Blocks",
}


def _now():
    return datetime.now(timezone.utc)


def _abbr(book):
    return BOOK_ABBR.get(book, book[:3].upper())


def pull_game_lines():
    """CALL 1: sport-level h2h/spreads/totals."""
    r = requests.get(f"{BASE}/sports/icehockey_nhl/odds",
                     params={"apiKey": KEY, "bookmakers": BOOKS_STR,
                             "markets": GAME_MARKETS, "oddsFormat": "american"},
                     timeout=45)
    used = int(r.headers.get("x-requests-last", "0"))
    rem = int(r.headers.get("x-requests-remaining", "0"))
    r.raise_for_status()
    return r.json(), used, rem


def pull_event_props(event_id):
    """CALL 2: per-event player props."""
    r = requests.get(f"{BASE}/sports/icehockey_nhl/events/{event_id}/odds",
                     params={"apiKey": KEY, "bookmakers": BOOKS_STR,
                             "markets": PROP_MARKETS, "oddsFormat": "american"},
                     timeout=45)
    used = int(r.headers.get("x-requests-last", "0"))
    rem = int(r.headers.get("x-requests-remaining", "0"))
    r.raise_for_status()
    return r.json(), used, rem


def filter_next_12h(games):
    """Keep only events commencing within 12 hours."""
    now = _now()
    cutoff = now + timedelta(hours=12)
    out = []
    for g in games:
        ct = datetime.fromisoformat(g["commence_time"].replace("Z", "+00:00"))
        if ct <= cutoff:
            out.append(g)
    return out


def format_game_lines(game):
    """Format game-line tables for one game."""
    home = game["home_team"]
    away = game["away_team"]
    ct = game["commence_time"]
    lines = []
    lines.append(f"## {away} @ {home}")
    lines.append(f"*{ct}*\n")

    # Collect all outcomes by market
    mkts = {}
    for bm in game.get("bookmakers", []):
        book = bm["key"]
        for mkt in bm.get("markets", []):
            mk = mkt["key"]
            if mk not in mkts:
                mkts[mk] = {}
            for oc in mkt.get("outcomes", []):
                name = oc["name"]
                price = oc["price"]
                point = oc.get("point")
                key = (name, point)
                if key not in mkts[mk]:
                    mkts[mk][key] = {}
                mkts[mk][key][book] = price

    # Moneyline
    if "h2h" in mkts:
        lines.append("### Moneyline")
        lines.append("| Side | Pinnacle | Best | Book |")
        lines.append("|------|----------|------|------|")
        for (name, _), prices in sorted(mkts["h2h"].items()):
            pin = prices.get("pinnacle")
            best_price, best_book = _best_price(prices)
            pin_s = _fmt(pin) if pin else "—"
            lines.append(f"| {name} | {pin_s} | {_fmt(best_price)} | {_abbr(best_book)} |")
        lines.append("")

    # Puck Line (spreads)
    if "spreads" in mkts:
        lines.append("### Puck Line")
        lines.append("| Side | Line | Pinnacle | Best | Book |")
        lines.append("|------|------|----------|------|------|")
        for (name, point), prices in sorted(mkts["spreads"].items(), key=lambda x: x[0][1] or 0):
            pin = prices.get("pinnacle")
            best_price, best_book = _best_price(prices)
            pin_s = _fmt(pin) if pin else "—"
            pt = f"{point:+.1f}" if point is not None else "—"
            lines.append(f"| {name} | {pt} | {pin_s} | {_fmt(best_price)} | {_abbr(best_book)} |")
        lines.append("")

    # Total
    if "totals" in mkts:
        lines.append("### Total")
        lines.append("| Side | Line | Pinnacle | Best | Book |")
        lines.append("|------|------|----------|------|------|")
        for (name, point), prices in sorted(mkts["totals"].items(), key=lambda x: (x[0][1] or 0, x[0][0])):
            pin = prices.get("pinnacle")
            best_price, best_book = _best_price(prices)
            pin_s = _fmt(pin) if pin else "—"
            pt = str(point) if point is not None else "—"
            lines.append(f"| {name} | {pt} | {pin_s} | {_fmt(best_price)} | {_abbr(best_book)} |")
        lines.append("")

    return "\n".join(lines)


def format_props(game, props_data):
    """Format props tables for one game."""
    home = game["home_team"]
    away = game["away_team"]
    lines = [f"## {away} @ {home}\n"]

    # Collect all prop outcomes: (player, market, line) -> {book: price}
    over_prices = {}   # (player, mkt_label, line) -> {book: price}
    under_prices = {}
    ags_prices = {}    # player -> {book: price}

    bms = props_data.get("bookmakers", []) if isinstance(props_data, dict) else []
    for bm in bms:
        book = bm["key"]
        for mkt in bm.get("markets", []):
            mk = mkt["key"]
            label = MKT_LABEL.get(mk, mk)
            for oc in mkt.get("outcomes", []):
                player = oc.get("description", oc.get("name", ""))
                name = oc["name"]
                price = oc["price"]
                point = oc.get("point")

                if mk == "player_goal_scorer_anytime":
                    if player not in ags_prices:
                        ags_prices[player] = {}
                    ags_prices[player][book] = price
                else:
                    key = (player, label, point)
                    if name == "Over":
                        if key not in over_prices:
                            over_prices[key] = {}
                        over_prices[key][book] = price
                    elif name == "Under":
                        if key not in under_prices:
                            under_prices[key] = {}
                        under_prices[key][book] = price

    # Target Props table (sorted by number of books quoting, descending)
    if over_prices or under_prices:
        all_keys = set(over_prices.keys()) | set(under_prices.keys())
        rows = []
        for key in all_keys:
            player, mkt_label, line = key
            overs = over_prices.get(key, {})
            unders = under_prices.get(key, {})
            n_books = len(set(overs.keys()) | set(unders.keys()))
            pin_o = overs.get("pinnacle")
            pin_u = unders.get("pinnacle")
            pin_s = f"{_fmt(pin_o)}/{_fmt(pin_u)}" if pin_o or pin_u else "—/—"
            if not pin_o and not pin_u:
                pin_s = "—/—"
            else:
                pin_s = f"{_fmt(pin_o) if pin_o else '—'}/{_fmt(pin_u) if pin_u else '—'}"
            best_o_price, best_o_book = _best_price(overs) if overs else (None, "")
            best_u_price, best_u_book = _best_price(unders, favor_low=True) if unders else (None, "")
            line_s = str(line) if line is not None else "—"
            rows.append((n_books, player, mkt_label, line_s, pin_s,
                          _fmt(best_o_price) if best_o_price else "—", _abbr(best_o_book) if best_o_book else "—",
                          _fmt(best_u_price) if best_u_price else "—", _abbr(best_u_book) if best_u_book else "—"))

        rows.sort(key=lambda x: (-x[0], x[1], x[2]))
        lines.append("### Target Props\n")
        lines.append("| Player | Mkt | Line | PIN O/U | Best Over | Bk | Best Under | Bk |")
        lines.append("|--------|-----|------|---------|-----------|-----|------------|-----|")
        for n, player, mkt, ln, pin_s, bo, bb_o, bu, bb_u in rows:
            lines.append(f"| {player} | {mkt} | {ln} | {pin_s} | {bo} | {bb_o} | {bu} | {bb_u} |")
        lines.append("")

    # Anytime Goal Scorer
    if ags_prices:
        # Sort by Pinnacle price ascending (best value first), then by best price
        ags_rows = []
        for player, prices in ags_prices.items():
            pin = prices.get("pinnacle")
            best_p, best_b = _best_price(prices)
            n_books = len(prices)
            ags_rows.append((pin if pin else 9999, player, pin, best_p, best_b))
        ags_rows.sort(key=lambda x: x[0])
        lines.append("### Top 10 Anytime Goal Scorer\n")
        lines.append("| Player | Pinnacle | Best | Book |")
        lines.append("|--------|----------|------|------|")
        for _, player, pin, best_p, best_b in ags_rows[:10]:
            pin_s = _fmt(pin) if pin else "—"
            lines.append(f"| {player} | {pin_s} | {_fmt(best_p)} | {_abbr(best_b)} |")
        lines.append("")

    return "\n".join(lines)


def _fmt(price):
    if price is None:
        return "—"
    p = int(price)
    return f"+{p}" if p > 0 else str(p)


def _best_price(prices, favor_low=False):
    """Best price = highest for over/ML, lowest for under."""
    if not prices:
        return None, ""
    if favor_low:
        best_book = min(prices, key=lambda b: prices[b])
    else:
        best_book = max(prices, key=lambda b: prices[b])
    return prices[best_book], best_book


def pin_sog_points_list(all_props):
    """List every player with a Pinnacle SOG or Points line."""
    players = []
    for eid, props_data in all_props.items():
        bms = props_data.get("bookmakers", []) if isinstance(props_data, dict) else []
        for bm in bms:
            if bm["key"] != "pinnacle":
                continue
            for mkt in bm.get("markets", []):
                if mkt["key"] not in ("player_shots_on_goal", "player_points"):
                    continue
                label = MKT_LABEL[mkt["key"]]
                for oc in mkt.get("outcomes", []):
                    player = oc.get("description", oc.get("name", ""))
                    point = oc.get("point")
                    price = oc["price"]
                    name = oc["name"]
                    players.append(f"{player} — {label} {point} {name} {_fmt(price)}")
    return sorted(set(players))


def main():
    now = _now()
    print(f"key fingerprint: {KEY_FP}")
    print(f"UTC: {now.isoformat()}")
    if not KEY:
        print("HALT: ODDS_API_KEY not set"); sys.exit(1)

    date_str = now.strftime("%Y-%m-%d")
    ts_tag = now.strftime("%H%MZ")

    # Directories
    raw_dir = ROOT / "logs" / "cowork_stage" / f"live_{date_str}"
    raw_dir.mkdir(parents=True, exist_ok=True)
    report_dir = ROOT / "research" / "nhl_layers" / "pilot_picks"
    report_dir.mkdir(parents=True, exist_ok=True)

    # CALL 1: game lines
    print("\n--- CALL 1: game lines ---")
    games_raw, used1, rem_before = pull_game_lines()
    # rem_before is AFTER call 1; initial was rem_before + used1
    initial_rem = rem_before + used1
    print(f"x-requests-remaining: {initial_rem} (before) -> {rem_before} (after call 1)")
    print(f"x-requests-last: {used1}")

    # Save raw
    (raw_dir / "main_odds.json").write_text(json.dumps(games_raw, indent=2))

    # Filter to next 12 hours
    tonight = filter_next_12h(games_raw)
    print(f"Events total: {len(games_raw)}, within 12h: {len(tonight)}")
    for g in tonight:
        print(f"  {g['away_team']} @ {g['home_team']}  {g['commence_time']}")

    # CALL 2: props per event
    n_events = len(tonight)
    projected_cost = used1 + n_events * 6
    print(f"\n--- CALL 2: props ({n_events} events) ---")
    print(f"Projected total cost: {used1} + {n_events} x 6 = {projected_cost} credits")
    if projected_cost > 200:
        print("HALT: projected cost exceeds 200"); sys.exit(1)

    total_used = used1
    all_props = {}
    for g in tonight:
        eid = g["id"]
        props_raw, used_p, rem_p = pull_event_props(eid)
        total_used += used_p
        all_props[eid] = props_raw
        print(f"  {g['away_team'][:3]}@{g['home_team'][:3]}: used={used_p} rem={rem_p}")
        (raw_dir / f"props_{eid}.json").write_text(json.dumps(props_raw, indent=2))

    final_rem = rem_p if tonight else rem_before
    print(f"\nx-requests-remaining: {final_rem}")
    print(f"Total credits used (header delta): {initial_rem - final_rem}")

    # Build report
    report_lines = [f"# NHL Live Lines — {date_str} (pulled {ts_tag})\n"]
    report_lines.append(f"**Credits:** {initial_rem} before -> {final_rem} after ({initial_rem - final_rem} used)\n")

    for g in tonight:
        report_lines.append(format_game_lines(g))

    report_lines.append("---")
    report_lines.append("# Player Props\n")
    for g in tonight:
        eid = g["id"]
        if eid in all_props:
            report_lines.append(format_props(g, all_props[eid]))

    # Pinnacle SOG/Points list
    pin_list = pin_sog_points_list(all_props)
    if pin_list:
        report_lines.append("---")
        report_lines.append("## Pinnacle SOG + Points Lines\n")
        for p in pin_list:
            report_lines.append(f"- {p}")

    report_path = report_dir / f"live_lines_{date_str}_{ts_tag}.md"
    report_path.write_text("\n".join(report_lines) + "\n")
    print(f"\nReport: {report_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
