#!/usr/bin/env python3
"""
Every logged pick in the repo, normalised to one row per pick-leg.

Used by link_picks_to_slips.py (item 1) and build_pick_ledger.py (item 3) of
claude/ops_workorder_bet_ledger_2026-10-03.md. Read-only. Zero API calls.

SOURCES is an explicit list. Every file a source glob matches must parse; a file that does
not parse raises Halt (a quietly dropped source is how "0 of 146 teams" went unnoticed).

The work order named five sources. Reading the board folders on 2026-10-03 found more files
that hold picks or placements; they are listed below and tagged `extra` so the reports can
say which matches depend on them.

Leg identity for matching is (league, game, market, subject, side). Point and price are kept
but never used for identity: Jeff buys points and Hard Rock prices differ from the card.
"""
import glob, json, os, re
from datetime import timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(os.environ.get("MLB_REPO_ROOT") or Path(__file__).resolve().parent.parent.parent)


class Halt(Exception):
    pass


COLS = ["ticket_id", "lane", "kind", "build_time", "league", "game", "teams", "market", "subject",
        "side", "point", "price", "book", "reason", "leg_type", "stake", "commence_utc",
        "source_file", "source_set", "raw"]

# ------------------------------------------------------------------ teams
NFL = {
    "ARI": "cardinals", "ATL": "falcons", "BAL": "ravens", "BUF": "bills", "CAR": "panthers",
    "CHI": "bears", "CIN": "bengals", "CLE": "browns", "DAL": "cowboys", "DEN": "broncos",
    "DET": "lions", "GB": "packers", "HOU": "texans", "IND": "colts", "JAX": "jaguars",
    "KC": "chiefs", "LV": "raiders", "LAC": "chargers", "LAR": "rams", "MIA": "dolphins",
    "MIN": "vikings", "NE": "patriots", "NO": "saints", "NYG": "giants", "NYJ": "jets",
    "PHI": "eagles", "PIT": "steelers", "SF": "49ers", "SEA": "seahawks", "TB": "buccaneers",
    "TEN": "titans", "WAS": "commanders", "WSH": "commanders",
}
NFL_NICK = set(NFL.values())


def nfl_team(s):
    """'Philadelphia Eagles' | 'Eagles' | 'PHI' -> 'eagles'; None if no team named."""
    if not s:
        return None
    s = str(s).strip()
    if s.upper() in NFL:
        return NFL[s.upper()]
    for w in re.findall(r"[A-Za-z0-9]+", s.lower()):
        if w in NFL_NICK:
            return w
    return None


NCAAF_NOT_MASCOT = {"state", "st", "tech", "am", "a", "atlantic", "international", "christian",
                    "southern", "northern", "eastern", "western", "central", "oh", "monroe",
                    "lafayette", "el", "college", "u", "university", "poly", "carolina", "kentucky",
                    "illinois", "michigan", "florida", "texas", "georgia", "alabama", "arizona",
                    "washington", "colorado", "iowa", "ohio", "kansas", "mississippi", "utah",
                    "oregon", "virginia", "louisiana", "new", "north", "south", "west", "east"}


def ncaaf_norm(s):
    s = re.sub(r"#\d+\s*", "", str(s or "")).lower().replace("&", "")
    return re.findall(r"[a-z0-9]+", s)


def ncaaf_same(a, b):
    """Same school if one token list is a prefix of the other and the leftover is a mascot,
    never a school qualifier ('Iowa' is not 'Iowa State Cyclones')."""
    x, y = ncaaf_norm(a), ncaaf_norm(b)
    if not x or not y:
        return False
    if len(x) > len(y):
        x, y = y, x
    if y[:len(x)] != x:
        return False
    rest = y[len(x):]
    return not rest or rest[0] not in NCAAF_NOT_MASCOT


def split_game(g):
    """'A @ B' | 'A vs B' | 'A vs. B' | 'SEA@WAS' -> [A, B] (order not meaningful)."""
    if not g:
        return []
    g = str(g)
    # Strip trailing metadata: ", MNF 2026-09-29T00:15Z" or unbalanced "(..."
    # but preserve balanced parens like "Miami (OH)" by only stripping from the first comma
    g = re.split(r",", g)[0].strip()
    parts = re.split(r"\s*@\s*|\s+vs\.?\s+", g)
    return [p.strip() for p in parts if p.strip()][:2]


# ------------------------------------------------------------------ markets
def stat_key(text):
    t = str(text or "").lower().replace("player_", "").replace("_", " ")
    if "anytime" in t and "td" in t:
        return "atd"
    if re.search(r"2\+\s*td|score 2", t):
        return "td2"
    if "longest" in t and "rec" in t:
        return "long_rec"
    pas = re.search(r"\bpass(ing)?\b", t)
    rush = re.search(r"\brush(ing)?\b|\bcarries\b", t)
    yds = re.search(r"\byds?\b|\byards?\b", t)
    if pas and re.search(r"\btds?\b|touchdown", t):
        return "pass_td"
    if re.search(r"\bint\b|\bints\b|interception", t):
        return "int"
    if "completion" in t or re.search(r"\bcmp\b", t):
        return "pass_cmp"
    if pas and re.search(r"\batt", t):
        return "pass_att"
    if pas and yds:
        return "pass_yds"
    if rush and (re.search(r"\batt", t) or "carries" in t):
        return "rush_att"
    if rush and yds:
        return "rush_yds"
    if re.search(r"\brec|receiving|reception", t) and yds:
        return "rec_yds"
    if re.search(r"\brec\b|\brecs\b|receptions?\b", t):
        return "rec"
    return None


def player_tokens(name):
    toks = re.findall(r"[a-z0-9]+", str(name or "").lower().replace("'", "").replace(".", ""))
    return [t for t in toks if t not in {"jr", "sr", "ii", "iii", "iv"}]


# ------------------------------------------------------------------ free-text pick legs
_PLAYER_OU = re.compile(
    r"^(?P<player>.+?)\s+(?P<side>over|under|o|u)\s*(?P<line>\d+(?:\.\d+)?)\s+(?P<stat>[a-z .']+?)"
    r"(?:\s+[-+]\d+)?(?:\s*[\[(].*)?$", re.I)
_PLAYER_NPLUS = re.compile(r"^(?P<player>.+?)\s+(?P<n>\d+)\+\s*(?P<stat>[a-z .]+?)(?:\s*[\[(].*)?(?:\s+[-+]\d+.*)?$", re.I)
_ATD = re.compile(r"^(?P<player>.+?)\s+anytime\s+td\b", re.I)
_TOTAL = re.compile(r"^(?:(?P<game>[A-Z]{2,3}@[A-Z]{2,3})\s+|game\s+)?(?P<side>over|under)\s*(?P<line>\d+(?:\.\d+)?)", re.I)
_TEAM = re.compile(r"^(?P<team>[A-Za-z0-9 .']+?)\s+(?P<pt>ML|[-+]\d+(?:\.\d+)?)\b", re.I)


def parse_text_leg(s, game=None):
    """Free-text leg -> list of dicts(market, subject, side, point, game). [] if not parseable."""
    s = re.sub(r"\s+", " ", str(s).strip())
    m = re.match(r"^SGP\s+(?P<game>[A-Z]{2,3}@[A-Z]{2,3}):\s*(?P<body>.+)$", s)
    if m:
        body = re.sub(r"\s*\([-+]\d+\)\s*$", "", m.group("body"))
        out = []
        for part in body.split(" + "):
            out += parse_text_leg(part, m.group("game"))
        return out
    g = re.search(r"\(([A-Z]{2,3}@[A-Z]{2,3})\)", s)
    if g:
        game = g.group(1)
    m = _ATD.match(s)
    if m:
        return [dict(market="prop:atd", subject=m.group("player"), side="over", point=0.5, game=game)]
    m = _TOTAL.match(s)
    if m:
        return [dict(market="total", subject="", side=m.group("side").lower(), point=float(m.group("line")),
                     game=m.group("game") or game)]
    m = _PLAYER_OU.match(s)
    if m and stat_key(m.group("stat")):
        side = {"o": "over", "u": "under"}.get(m.group("side").lower(), m.group("side").lower())
        return [dict(market="prop:" + stat_key(m.group("stat")), subject=m.group("player").strip(), side=side,
                     point=float(m.group("line")), game=game)]
    m = _PLAYER_NPLUS.match(s)
    if m and stat_key(m.group("stat")):
        return [dict(market="prop:" + stat_key(m.group("stat")), subject=m.group("player").strip(), side="over",
                     point=float(m.group("n")) - 0.5, game=game)]
    m = _TEAM.match(s)
    if m and (nfl_team(m.group("team")) or len(m.group("team")) > 3):
        pt = m.group("pt")
        if pt.upper() == "ML":
            return [dict(market="moneyline", subject=m.group("team").strip(), side=m.group("team").strip(),
                         point=None, game=game)]
        return [dict(market="spread", subject=m.group("team").strip(), side=m.group("team").strip(),
                     point=float(pt), game=game)]
    return []


def odds_market(market_key):
    mk = str(market_key or "").lower()
    if mk in ("spreads", "spread", "alternate_spreads"):
        return "spread"
    if mk in ("totals", "total", "alternate_totals"):
        return "total"
    if mk in ("h2h", "moneyline", "ml"):
        return "moneyline"
    sk = stat_key(mk)
    return "prop:" + sk if sk else None


# ------------------------------------------------------------------ row builder
def _ts(x):
    if x is None or (isinstance(x, float) and pd.isna(x)) or x == "":
        return pd.NaT
    s = str(x).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z$", s):
        s = s[:-1] + ":00Z"
    return pd.to_datetime(s, utc=True, errors="coerce")


def _row(rows, *, ticket_id, lane, kind, build_time, league, game, market, subject, side, point,
         price=None, book=None, reason=None, leg_type="pick", stake=None, commence=None,
         source_file, source_set, raw):
    rows.append(dict(ticket_id=ticket_id, lane=lane, kind=kind, build_time=_ts(build_time), league=league,
                     game=game, teams=None, market=market, subject=subject or "", side=(side or ""),
                     point=point, price=price, book=book, reason=reason, leg_type=leg_type, stake=stake,
                     commence_utc=_ts(commence), source_file=source_file, source_set=source_set,
                     raw=json.dumps(raw, default=str)[:400] if not isinstance(raw, str) else raw[:400]))


def _text_legs(rows, legs, game, **kw):
    for raw in legs:
        txt = raw[0] if isinstance(raw, (list, tuple)) else raw
        parsed = parse_text_leg(txt, game)
        if not parsed:
            _row(rows, game=game, market=None, subject="", side="", point=None, raw=txt, **kw)
        for p in parsed:
            _row(rows, game=p["game"], market=p["market"], subject=p["subject"], side=p["side"],
                 point=p["point"], raw=txt, **kw)


# ------------------------------------------------------------------ parsers (one per source)
def p_ncaaf_tickets(path, rel, sset):
    rows = []
    for i, e in enumerate(json.load(open(path))):
        if "card_id" in e:
            tid, kind, legs = f"ncaaf_{e['card_id']}", "card", e["legs"]
            game_of = lambda l: l.get("game")
        elif "event_id" in e:
            sides = {(l["market"], l["side"]) for l in e["legs"]}
            both = any(l["market"] == "totals" and l["side"] == "Under" for l in e["legs"]) and \
                any(l["market"] == "totals" and l["side"] == "Over" for l in e["legs"])
            if both or len(e["legs"]) > 2:
                continue                       # pre-repair board row: both sides listed, not a pick
            tid, kind, legs = f"ncaaf_view_{e['event_id'][:8]}_{e['build_time'][:16]}", "game_view", e["legs"]
            gname = f"{e['away_team']} @ {e['home_team']}"
            game_of = lambda l, g=gname: g
        else:
            raise Halt(f"{rel}: entry {i} has neither card_id nor event_id")
        for l in legs:
            _row(rows, ticket_id=tid, lane="ncaaf", kind=kind, build_time=e["build_time"], league="NCAAF",
                 game=game_of(l), market=odds_market(l["market"]), subject=l["side"] if l["market"] != "totals" else "",
                 side=l["side"], point=l.get("point"), price=l.get("price"), book=l.get("book"),
                 reason=e.get("ai_rationale") or l.get("ai_reason"), leg_type="view" if kind == "game_view" else "pick",
                 stake=e.get("stake_usd"),
                 commence=l.get("commence_time"), source_file=rel, source_set=sset, raw=l)
    return rows


def p_ncaaf_placements(path, rel, sset):
    d, rows = json.load(open(path)), []
    for t in d["tickets"]:
        for l in t["legs"]:
            _row(rows, ticket_id=f"ncaaf_{t['ticket']}_{d['logged_utc'][:10]}", lane="ncaaf", kind="placement",
                 build_time=d["logged_utc"], league="NCAAF", game=l["game"], market=odds_market(l["market"]),
                 subject=l["side"] if l["market"] != "totals" else "", side=l["side"], point=l.get("line"),
                 price=l.get("price"), book="hardrockbet_fl", leg_type="placed", stake=t.get("stake"),
                 commence=l.get("kick_utc"), source_file=rel, source_set=sset, raw=l)
    return rows


def _freeze_point(market, freeze_side, line):
    """Convert freeze line to bettor's point. Spread + second-side → negate."""
    if line is None or (isinstance(line, float) and pd.isna(line)):
        return None
    pt = float(line)
    if market == "spread" and freeze_side == "second":
        pt = -pt
    return pt


def p_ai_opinions(path, rel, sset, lane="ncaaf", league="NCAAF"):
    d, rows = pd.read_parquet(path), []
    need = {"event_id", "home_team", "away_team", "market_key", "side", "side_name", "line", "logged_utc"}
    if not need <= set(d.columns):
        raise Halt(f"{rel}: missing columns {sorted(need - set(d.columns))}")
    for _, r in d.iterrows():
        if not r["side"] or str(r["side"]).lower() in ("none", "no_view", "pass", ""):
            continue
        mk = odds_market(r["market_key"])
        _row(rows, ticket_id=f"{lane}_op_{Path(path).stem[-16:]}_{r['event_id'][:8]}_{r['market_key']}",
             lane=lane, kind="ai_opinion", build_time=r["logged_utc"], league=league,
             game=f"{r['away_team']} @ {r['home_team']}", market=mk,
             subject=(r.get("player_name") or (r["side_name"] if mk in ("spread", "moneyline") else "")),
             side=r["side_name"], point=_freeze_point(mk, r["side"], r["line"]),
             price=r.get("side_price"), book=r.get("book"),
             reason=r.get("reason"), leg_type="view", commence=r["commence_time"], source_file=rel,
             source_set=sset, raw=dict(side=r["side"], side_name=r["side_name"], tag=r.get("tag"),
                                       window=r.get("window") if "window" in d.columns else None))
    return rows


def p_nfl_prop_tickets(path, rel, sset):
    rows = []
    for e in json.load(open(path)):
        kind = e.get("kind")
        if kind in ("slate_final", "slate_rule"):
            for l in e.get("legs") or []:
                _row(rows, ticket_id=f"nfl_{e['ticket_id']}_{e['build_time'][:16]}", lane="nfl", kind=kind,
                     build_time=e["build_time"], league="NFL", game=f"{l['away_team']} @ {l['home_team']}",
                     market=odds_market(l["market_key"]), subject=l["player_name"], side=l["pick_side"],
                     point=l["line"], price=l.get("pick_price"), leg_type="pick", commence=l.get("commence_time"),
                     source_file=rel, source_set=sset, raw={k: l.get(k) for k in ("player_name", "market_key", "line", "pick_side")})
        elif kind == "placement":
            for l in e.get("legs_placed") or []:
                _row(rows, ticket_id=f"nfl_{e['ticket_id']}_{e['build_time'][:16]}", lane="nfl", kind=kind,
                     build_time=e["build_time"], league="NFL", game=None, market=odds_market(l["market_key"]),
                     subject=l["player_name"], side=l["side"], point=l.get("line"), price=l.get("american"),
                     book="hardrockbet_fl", leg_type="placed", stake=e.get("stake"), source_file=rel,
                     source_set=sset, raw=l)
        else:
            raise Halt(f"{rel}: unknown kind {kind!r}")
    return rows


def p_game_ticket_ai(path, rel, sset):
    d, rows = json.load(open(path)), []
    bt = d.get("built_utc") or d.get("sent_utc")
    for l in d["legs"]:
        mk = odds_market(l["market"])
        _row(rows, ticket_id=f"nfl_{d['ticket_id']}_{bt}", lane="nfl", kind=d.get("kind", "game_ticket"),
             build_time=bt, league="NFL", game=l["game"], market=mk, subject=l["outcome"] if mk != "total" else "",
             side=l["outcome"], point=l.get("point"), price=l.get("american"), reason=l.get("ai_reason"),
             leg_type="pick", commence=l.get("commence_time"), source_file=rel, source_set=sset,
             raw={k: l.get(k) for k in ("game", "market", "outcome", "point")})
    return rows


def p_nfl_placements(path, rel, sset):
    d, rows = json.load(open(path)), []
    name = Path(path).name
    if "placements" in d:                                   # game_ticket_placements_*.json
        for t in d["placements"]:
            for l in t["legs"]:
                mk = odds_market(l["market"])
                _row(rows, ticket_id=f"nfl_{t['ticket_id']}", lane="nfl", kind="placement", build_time=d["logged_utc"],
                     league="NFL", game=l["game"], market=mk, subject=l["outcome"] if mk != "total" else "",
                     side=l["outcome"], point=l.get("point"), price=l.get("american"), book="hardrockbet_fl",
                     leg_type="placed", stake=t.get("stake"), source_file=rel, source_set=sset, raw=l)
    elif "placed" in d and isinstance(d["placed"], list):   # tnf_/mnf_ticket_placements_*.json
        game = d.get("game")
        for t in d["placed"]:
            _text_legs(rows, t["legs"], game, ticket_id=f"nfl_{t['ticket']}_{d['slate']}", lane="nfl",
                       kind="placement", build_time=d.get("placed_logged_utc"), league="NFL", leg_type="placed",
                       stake=t.get("stake") if isinstance(t.get("stake"), (int, float)) else None,
                       source_file=rel, source_set=sset)
        if d.get("card_sent"):
            _text_legs(rows, d["card_sent"], game, ticket_id=f"nfl_CARD_{d['slate']}", lane="nfl", kind="card",
                       build_time=d.get("sent_utc"), league="NFL", leg_type="pick", source_file=rel, source_set=sset)
    elif "tickets" in d:                                    # sun_ticket_placements_*.json
        for t in d["tickets"]:
            _text_legs(rows, t["legs"], None, ticket_id=f"nfl_{t['id']}_{d['slate']}", lane="nfl", kind="placement",
                       build_time=_slate_time(d), league="NFL", leg_type="placed", stake=t.get("stake"),
                       source_file=rel, source_set=sset)
    else:
        raise Halt(f"{rel}: unrecognised placements layout ({name})")
    return rows


def _slate_time(d):
    for k in ("written_utc", "logged_utc", "placed_logged_utc", "built_utc"):
        if d.get(k):
            return d[k]
    m = re.search(r"(\d{4}-\d{2}-\d{2})", str(d.get("slate", "")))
    return m.group(1) + "T12:00:00Z" if m else None


def p_mnf_sgp(path, rel, sset):
    d, rows = json.load(open(path)), []
    _text_legs(rows, [l["leg"] for l in d["legs"]], d.get("game"),
               ticket_id=f"nfl_{Path(path).stem}", lane="nfl", kind="sgp_card", build_time=d["built_utc"],
               league="NFL", leg_type="pick", source_file=rel, source_set=sset)
    return rows


def p_sun_cards(path, rel, sset):
    d, rows = json.load(open(path)), []
    for cid, c in d["cards"].items():
        legs = [(l["pick"] + (f" ({l['game']})" if "@" in l.get("game", "") and not nfl_team(l["pick"]) else ""))
                if isinstance(l, dict) else l for l in c["legs"]]
        games = [l.get("game") if isinstance(l, dict) else None for l in c["legs"]]
        for txt, g in zip(legs, games):
            _text_legs(rows, [txt], g, ticket_id=f"nfl_{cid}_{Path(path).stem}", lane="nfl", kind="card",
                       build_time=_slate_time(d), league="NFL", leg_type="pick", source_file=rel, source_set=sset)
    return rows


def p_sgp_ticket_ai(path, rel, sset):
    d, rows = json.load(open(path)), []
    _text_legs(rows, [l["leg"] for l in d["legs"]], d.get("game"), ticket_id=f"nfl_{d['ticket_id']}",
               lane="nfl", kind="sgp_card", build_time=d.get("sent_utc"), league="NFL", leg_type="pick",
               source_file=rel, source_set=sset)
    return rows


SOURCES = [
    # work-order sources (the five named on 2026-10-03)
    ("ncaaf/logs/ncaaf_board_tickets_2026.json", p_ncaaf_tickets, "workorder"),
    ("nfl/data/board/nfl_prop_tickets_2026.json", p_nfl_prop_tickets, "workorder"),
    ("nfl/data/board/week=*/game_ticket_ai_*.json", p_game_ticket_ai, "workorder"),
    ("nfl/data/board/week=*/*placements*.json", p_nfl_placements, "workorder"),
    ("ncaaf/data/board/week=*/ai_opinions/*.parquet", p_ai_opinions, "workorder"),
    # found on 2026-10-03 in the same folders, not in the work order's list
    ("ncaaf/data/board/week=*/*placements*.json", p_ncaaf_placements, "extra"),
    ("nfl/data/board/week=*/mnf_sgp*.json", p_mnf_sgp, "extra"),
    ("nfl/data/board/week=*/sun_cards*.json", p_sun_cards, "extra"),
    ("nfl/data/board/week=*/sgp_ticket_ai_*.json", p_sgp_ticket_ai, "extra"),
]


def load_picks(root=None, sources=SOURCES):
    root = Path(root or ROOT)
    rows, files = [], []
    for pattern, fn, sset in sources:
        hits = sorted(glob.glob(str(root / pattern)))
        if not hits:
            raise Halt(f"source glob matched nothing: {pattern}")
        for f in hits:
            if fn is p_game_ticket_ai and "opinion" in Path(f).name:
                fn_use = _p_game_ticket_opinion
            else:
                fn_use = fn
            rel = str(Path(f).relative_to(root))
            try:
                got = fn_use(f, rel, sset)
            except Halt:
                raise
            except Exception as e:
                raise Halt(f"{rel}: cannot parse ({type(e).__name__}: {e})")
            files.append((rel, sset, len(got)))
            rows += got
    P = pd.DataFrame(rows, columns=COLS)
    P["teams"] = [tuple(split_game(g)) for g in P.game]
    return P, pd.DataFrame(files, columns=["source_file", "source_set", "rows"])


def _p_game_ticket_opinion(path, rel, sset):
    d, rows = json.load(open(path)), []
    bt = d.get("correction_sent_utc") or d.get("sent_utc")
    for l in d["legs"]:
        mk = odds_market(l["market"])
        _row(rows, ticket_id=f"nfl_{d['ticket_id']}", lane="nfl", kind=d.get("kind", "game_opinion"),
             build_time=bt, league="NFL", game=l["game"], market=mk, subject=l["outcome"] if mk != "total" else "",
             side=l["outcome"], point=l.get("point"), price=l.get("american"), reason=l.get("ai_reason"),
             leg_type="pick", commence=l.get("commence_time"), source_file=rel, source_set=sset,
             raw={k: l.get(k) for k in ("game", "market", "outcome", "point")})
    return rows


if __name__ == "__main__":
    P, F = load_picks()
    print(F.to_string(index=False))
    print(f"{len(P)} pick-leg rows, {P.ticket_id.nunique()} tickets; unparsed legs: {int(P.market.isna().sum())}")
