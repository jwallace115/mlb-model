#!/usr/bin/env python3
"""AI reader: packet -> Messages API -> freeze through log_ai_opinions.

Sport-parameterised (nfl, ncaaf now; nhl/nba stubs that HALT).
Three stages:
  (a) PACKET: build_packet(sport, event_ids, inputs, ...) -> text + saved file
  (b) READ:   one Messages API call per game -> strict JSON picks
  (c) FREEZE: picks written through existing log_ai_opinions freeze

The API key lives ONLY in /root/private/env on the VM as ANTHROPIC_API_KEY.
This module never prints, logs, or commits it.

P61 decision. OPS-CAD1 Item 1.
"""
import hashlib
import json
import os
import re
import sys
import gzip
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# Sport configs
# ---------------------------------------------------------------------------
SUPPORTED = {"nfl", "ncaaf"}

VALID_TAGS = ("injury_news", "role_change", "game_script", "matchup", "weather",
              "price_vs_sharp", "usage_trend", "line_move", "no_view", "sim_v1")

THESIS_LINKS = {"plays", "pass_rate", "run_rate", "share", "efficiency",
                "availability", "script", "points", "turnovers", "price"}
THESIS_DIRS = {"up", "down"}

PROP_ABBR = {
    "player_receptions": "rec", "player_reception_yds": "recyd",
    "player_rush_yds": "ruyd", "player_rush_attempts": "ruatt",
    "player_pass_yds": "payd", "player_pass_attempts": "paatt",
    "player_pass_completions": "cmp", "player_pass_tds": "patd",
    "player_pass_interceptions": "int", "player_anytime_td": "atd",
}

# NFL team abbreviations for Kalshi event ticker matching
NFL_NICK_TO_ABB = {
    "Cardinals": "ARI", "Falcons": "ATL", "Ravens": "BAL", "Bills": "BUF",
    "Panthers": "CAR", "Bears": "CHI", "Bengals": "CIN", "Browns": "CLE",
    "Cowboys": "DAL", "Broncos": "DEN", "Lions": "DET", "Packers": "GB",
    "Texans": "HOU", "Colts": "IND", "Jaguars": "JAC", "Chiefs": "KC",
    "Raiders": "LV", "Chargers": "LAC", "Rams": "LAR", "Dolphins": "MIA",
    "Vikings": "MIN", "Patriots": "NE", "Saints": "NO", "Giants": "NYG",
    "Jets": "NYJ", "Eagles": "PHI", "Steelers": "PIT", "49ers": "SF",
    "Seahawks": "SEA", "Buccaneers": "TB", "Titans": "TEN", "Commanders": "WAS",
}

# 2026 international games (venue table from the prototype)
INTL_GAMES = {
    ("2026-09-10", "Rams", "49ers"): ("Melbourne Cricket Ground", "Melbourne", 11),
    ("2026-09-27", "Ravens", "Cowboys"): ("Maracana", "Rio de Janeiro", -3),
    ("2026-10-04", "Colts", "Commanders"): ("Tottenham Hotspur Stadium", "London", 1),
    ("2026-10-11", "Jaguars", "Eagles"): ("Tottenham Hotspur Stadium", "London", 1),
    ("2026-10-18", "Jaguars", "Texans"): ("Wembley Stadium", "London", 1),
    ("2026-10-25", "Steelers", "Saints"): ("Stade de France", "Paris", 2),
    ("2026-11-08", "Falcons", "Bengals"): ("Santiago Bernabeu", "Madrid", 2),
    ("2026-11-15", "Patriots", "Lions"): ("Allianz Arena", "Munich", 2),
    ("2026-11-22", "Vikings", "49ers"): ("Estadio Banorte", "Mexico City", -6),
}
INTL_BASE_RATES = (
    "base rates (56 intl games thru 2025): favorites 41-14-1 SU / 35-21 ATS, "
    "FG+ favorites 24-16 ATS; unders 30-26 overall, Wembley 15-12 under & "
    "favorites 17-10 ATS, Tottenham 7-5 OVER; London-only favorites ~17-16 ATS "
    "(LSR) - venue alone is not a spread edge; 2025 intl games 4-3 over, 6/7 within 6 pts"
)
TEAM_TZ = {
    "Seahawks": -7, "49ers": -7, "Rams": -7, "Chargers": -7, "Raiders": -7,
    "Cardinals": -7, "Broncos": -6, "Cowboys": -5, "Texans": -5, "Chiefs": -5,
    "Saints": -5, "Titans": -5, "Bears": -5, "Packers": -5, "Vikings": -5,
}

# Default AI reader model (newest Sonnet-class from the Anthropic Console).
# Live /v1/models list pulled 2026-10-23T11:50Z:
#   claude-haiku-5-5, claude-sonnet-5-5 (2026-09-28), claude-opus-5-5,
#   claude-fable-5-1, claude-opus-5, claude-sonnet-5, claude-fable-5,
#   claude-opus-4-8, claude-opus-4-7, claude-sonnet-4-6, claude-opus-4-6,
#   claude-opus-4-5-20251101, claude-haiku-4-5-20251001, claude-sonnet-4-5-20250929
DEFAULT_MODEL = "claude-sonnet-5-5"

# Monthly cap (USD) for AI reader spend
DEFAULT_MONTHLY_CAP_USD = 150.0

# ---------------------------------------------------------------------------
# READER_SYSTEM — the method from the Cowork reads, stated verbatim
# ---------------------------------------------------------------------------
READER_SYSTEM = """\
You are a sports betting reader. You read a data packet for one game and form \
picks on the lines the book quotes.

METHOD:
1. VIEW FIRST. Read who plays, how the game goes, where the number is wrong. \
Form a view BEFORE looking at the price.
2. PRICE. Compare: Pinnacle no-vig (the sharp anchor), the Hard Rock gap, \
Kalshi mid where volume > 1,500 contracts, the sim where confidence >= 20.
3. PICK only on two-way markets and game lines. \
NEVER pick a one-way market (anytime TD). \
NEVER pick a moneyline longshot (implied probability < 28.6%, i.e. +250 or worse).
4. MIX: aim for a mix of sides, totals, QB yards/attempts, RB carries, receptions \
across the full slate. Do not over-concentrate on one market type.
5. Each pick needs: market, player (empty string for game lines), line, \
side ("first" = Over/Home, "second" = Under/Away), \
tag (one of: injury_news, role_change, game_script, matchup, weather, \
price_vs_sharp, usage_trend, line_move, sim_v1), \
conf (1-30, your confidence), \
reason (12-160 chars, carry the numbers: the line, the price, the key stat), \
thesis (1-3 claims, each "link:dir" with link in {plays, pass_rate, run_rate, \
share, efficiency, availability, script, points, turnovers, price} and dir in {up, down}, \
semicolon-separated).
6. Everything else is a PASS with a one-line reason carrying the HR/Pinnacle numbers \
(tag = "no_view", conf = 0).

OUTPUT: strict JSON array. Each element:
{
  "market": "<market_key>",
  "player": "<player_name or empty>",
  "line": <number>,
  "side": "first" or "second",
  "tag": "<tag>",
  "conf": <1-30 for picks, 0 for passes>,
  "reason": "<12-160 chars>",
  "thesis": "<link:dir; ...>" or ""
}

You must emit exactly one element per line in the packet's sheet. \
Do not add lines the book does not quote. Do not omit any quoted line. \
Output ONLY the JSON array, no other text.
"""

# ---------------------------------------------------------------------------
# JSON schema for pick validation
# ---------------------------------------------------------------------------
PICK_SCHEMA_KEYS = {"market", "player", "line", "side", "tag", "conf", "reason", "thesis"}
VALID_SIDES = {"first", "second"}
ML_LONGSHOT_THRESHOLD = 250  # +250 or worse is a longshot


def _parse_utc(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def _implied(american):
    a = float(american)
    return 100.0 / (a + 100.0) if a > 0 else -a / (-a + 100.0)


def _fmt_price(p):
    if p is None or (isinstance(p, float) and np.isnan(p)):
        return "-"
    p = int(p)
    return f"+{p}" if p > 0 else str(p)


def _nv(over, under):
    """No-vig probability of over (first side) from American prices."""
    a = _implied(over)
    b = _implied(under)
    return a / (a + b)


def _nick(team_name):
    """Extract nickname from full team name."""
    return team_name.split()[-1]


# ---------------------------------------------------------------------------
# PACKET builder
# ---------------------------------------------------------------------------

def _load_hr_open_week(snaps, now):
    """HR open prices since Tuesday (or Monday for MNF) from weekly snapshots."""
    tue = (now - timedelta(days=(now.weekday() - 1) % 7)).strftime("%Y%m%d")
    wk = [s for s in snaps if os.path.basename(str(s))[5:13] >= tue]
    opn = {}
    for s in wk[::4]:
        d = pd.read_parquet(s)
        d = d[d.bookmaker == "hardrockbet_fl"]
        for r in d.itertuples():
            k = (r.event_id, r.market, r.outcome_name)
            if k not in opn:
                opn[k] = (r.point, r.price, os.path.basename(str(s))[5:13])
    return opn


def _load_kalshi_nfl(root, now):
    """Load newest NFL Kalshi snapshot."""
    ks = sorted((root / "data" / "odds_archive" / "kalshi" / "nfl" / "season=2026").glob("snap_*.parquet"))
    if not ks:
        return pd.DataFrame(), None
    K = pd.read_parquet(ks[-1])
    K["mid"] = (K.yes_bid_dollars.astype(float) + K.yes_ask_dollars.astype(float)) / 2
    return K, os.path.basename(str(ks[-1]))


def _kalshi_for_game(K, home, away, commence_time):
    """Extract Kalshi ML/spread/total rows for one game."""
    if K.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    d = _parse_utc(commence_time)
    tags = [(d + timedelta(days=x)).strftime("%y%b%d").upper() for x in (-1, 0)]
    h_abb = NFL_NICK_TO_ABB.get(_nick(home), "")
    a_abb = NFL_NICK_TO_ABB.get(_nick(away), "")
    ev = [f"{t}{a_abb}{h_abb}" for t in tags]
    pat = "|".join(ev)
    e = K[K.event_ticker.str.contains(pat, regex=True, na=False)]
    ml_ = e[e.ticker.str.startswith("KXNFLGAME")]
    sp_ = e[e.ticker.str.startswith("KXNFLSPREAD")]
    to_ = e[e.ticker.str.startswith("KXNFLTOTAL")]
    return ml_, sp_, to_


def _kalshi_near(df, pt_, pref=None):
    """Find nearest Kalshi contracts to a point."""
    if pt_ is None or df.empty:
        return []
    df = df.copy()
    df["pt"] = df.title.str.extract(r"(\d+\.5)").astype(float)
    if pref:
        df = df[df.title.str.startswith(pref)]
    df = df.dropna(subset=["pt"])
    df["dd"] = (df.pt - abs(pt_)).abs()
    return [(t[:38], round(float(m), 2), int(float(v)))
            for t, m, v in df.sort_values("dd")[["title", "mid", "volume_fp"]].values[:2]]


def _load_injuries(root, now):
    """Load newest NFL injury report."""
    inj_dir = root / "data" / "injury_archive" / "nfl" / "season=2026"
    if not inj_dir.exists():
        return {}, ""
    files = sorted(inj_dir.glob("injuries_*.json.gz"))
    if not files:
        return {}, ""
    inf = files[-1]
    d = json.load(gzip.open(str(inf), "rt"))
    inj = {t["displayName"]: t["injuries"] for t in d.get("injuries", [])}
    return inj, os.path.basename(str(inf))


def _load_news(root, now):
    """Load team news from last 5 days."""
    news_dir = root / "data" / "news_archive" / "nfl" / "season=2026"
    if not news_dir.exists():
        return {}
    news = {}
    cutoff = now - timedelta(days=5)
    for f in sorted(news_dir.glob("news_*"))[-20:]:
        try:
            items = json.load(gzip.open(str(f), "rt"))
        except Exception:
            continue
        for it in items:
            pub = it.get("published", "")[:16]
            teams = {c.get("description") for c in it.get("categories", [])
                     if c.get("type") == "team"}
            hl = it.get("headline", "")
            # Filter league-wide noise
            if re.search(r"every game|predictions|betting guide|uniforms|Power Rankings|betting:", hl):
                continue
            for t in teams:
                news.setdefault(t, {})[hl] = pub
    return news


def _load_sim_views(root, event_ids):
    """Load newest sim freeze views for the given events."""
    simrows = pd.DataFrame()
    simtag = ""
    for wd in sorted((root / "nfl" / "data" / "board").glob("week=2026_*/ai_opinions/manifest.json"))[-2:]:
        m = json.load(open(wd))
        sims = [e for e in m if (e.get("reader_model") or "").startswith("nfl_sim")]
        if sims:
            fp = wd.parent / sims[-1]["file"]
            if fp.exists():
                simrows = pd.read_parquet(fp)
                simtag = os.path.basename(str(fp))[12:27]
    if simrows.empty or not event_ids:
        return simrows, simtag
    simrows = simrows[simrows.event_id.isin(set(event_ids))]
    return simrows, simtag


def _intl_note(home, away, commence_time):
    """Build international game note (2026 venue table)."""
    d = commence_time[:10]
    h_nick = _nick(home)
    a_nick = _nick(away)
    k = [(kk, v) for kk, v in INTL_GAMES.items()
         if kk[0] == d and {kk[1], kk[2]} == {h_nick, a_nick}]
    if not k:
        return None
    (_, hn, an), (stad, city, off) = k[0]
    from datetime import date as _date
    prev = (_date.fromisoformat(d) - timedelta(days=7)).isoformat()
    stayed = [t for t in (h_nick, a_nick)
              if any(kk[0] == prev and t in kk[1:]
                     and INTL_GAMES[kk][1] == city for kk in INTL_GAMES)]
    hr = int(commence_time[11:13])

    def body(t):
        return f"{t} body clock {(hr + TEAM_TZ.get(t, -4)) % 24:02d}:{commence_time[14:16]}"

    return (
        f"  INTERNATIONAL: {stad}, {city} (UTC{off:+d}); "
        f"kick {commence_time[11:16]}Z = {body(h_nick)}, {body(a_nick)}; "
        f"second straight week in {city}: {stayed or 'neither team'}; "
        f"JAX all-time London 8-7, 2-0 in week-two-abroad games (2023 BUF, 2024 NE)\n"
        f"    {INTL_BASE_RATES}"
    )


def build_packet(sport, event_ids, sheet, props_df, lines_df, now,
                 root=ROOT, triggers=None):
    """Build the text packet for the AI reader.

    Args:
        sport: "nfl" or "ncaaf"
        event_ids: list of event_id strings to include
        sheet: DataFrame from build_sheet (the full sheet)
        props_df: raw props DataFrame (all books)
        lines_df: raw lines DataFrame (all books, one snapshot)
        now: UTC datetime
        root: repo root path
        triggers: dict of {event_id: "trigger description"} for WHAT CHANGED header

    Returns:
        (header_line, {event_id: packet_text})
    """
    if sport not in SUPPORTED:
        raise SystemExit(f"HALT: ai_reader not wired for {sport}")

    triggers = triggers or {}
    cur = lines_df[lines_df.snapshot_utc == lines_df.snapshot_utc.max()] if not lines_df.empty else lines_df

    # Load supporting data
    snaps = sorted((root / "data" / "odds_archive" / "nfl" / "line_history" / "season=2026").glob("snap_*.parquet"))
    opn = _load_hr_open_week(snaps, now) if sport == "nfl" else {}
    K, kalshi_file = _load_kalshi_nfl(root, now) if sport == "nfl" else (pd.DataFrame(), None)
    inj, inj_file = _load_injuries(root, now) if sport == "nfl" else ({}, "")
    news = _load_news(root, now) if sport == "nfl" else {}
    simrows, simtag = _load_sim_views(root, event_ids) if sport == "nfl" else (pd.DataFrame(), "")

    # Filter sheet to requested events
    sh = sheet[sheet.event_id.isin(set(event_ids))].copy()
    sh["player_name"] = sh.player_name.fillna("")

    packets = {}
    for eid in event_ids:
        g = sh[sh.event_id == eid]
        if g.empty:
            continue
        h, a, ct = g.home_team.iloc[0], g.away_team.iloc[0], g.commence_time.iloc[0]
        Lc = cur[cur.event_id == eid] if not cur.empty else pd.DataFrame()

        def line(bk, mk, side):
            x = Lc[(Lc.bookmaker == bk) & (Lc.market == mk) & (Lc.outcome_name == side)]
            return None if x.empty else (x.point.iloc[0], int(x.price.iloc[0]))

        s = []
        # WHAT CHANGED header
        trig = triggers.get(eid, "")
        if trig:
            s.append(f"  WHAT CHANGED: {trig}")

        # Game lines: HR + Pinnacle + open
        ps = line("pinnacle", "spreads", h)
        pt = line("pinnacle", "totals", "Over")
        pu = line("pinnacle", "totals", "Under")
        pm = line("pinnacle", "h2h", h)
        pam = line("pinnacle", "h2h", a)
        pin_nv = round(_implied(pm[1]) / (_implied(pm[1]) + _implied(pam[1])), 3) if pm and pam else None

        # HR lines from sheet
        gl = {}
        for mk in ("h2h", "spreads", "totals"):
            mask = (g.market_key == mk) & (g.player_name == "")
            if mask.any():
                gl[mk] = g[mask].iloc[0]

        hs = gl.get("spreads")
        ht = gl.get("totals")
        hm = gl.get("h2h")

        o_s = opn.get((eid, "spreads", h))
        o_t = opn.get((eid, "totals", "Over"))

        s.append(f"######## {a} @ {h}  kick {ct[5:16]}Z")
        if hm is not None:
            s.append(f"  HR ML: {_nick(h)} {_fmt_price(hm.price_first)} / "
                     f"{_nick(a)} {_fmt_price(hm.price_second)} "
                     f"(no-vig home {hm.q_first:.3f}) | Pinnacle no-vig home {pin_nv}")
        if hs is not None:
            s.append(f"  HR spread: {_nick(h)} {hs.line:+g} {_fmt_price(hs.price_first)} / "
                     f"{_nick(a)} {-hs.line:+g} {_fmt_price(hs.price_second)}"
                     f" | Pinnacle {_nick(h)} {ps[0] if ps else '?'} ({_fmt_price(ps[1]) if ps else '?'})"
                     f" | HR open {o_s[0] if o_s else '?'} ({o_s[2] if o_s else ''})")
        if ht is not None:
            s.append(f"  HR total: {ht.line:g} O{_fmt_price(ht.price_first)}/U{_fmt_price(ht.price_second)}"
                     f" | Pinnacle {pt[0] if pt else '?'} O{_fmt_price(pt[1]) if pt else '?'}"
                     f"/U{_fmt_price(pu[1]) if pu else '?'}"
                     f" | HR open {o_t[0] if o_t else '?'}")

        # Kalshi (NFL only)
        if sport == "nfl" and not K.empty:
            ml_, sp_, to_ = _kalshi_for_game(K, h, a, ct)
            fav = h if (hs is not None and hs.line < 0) else a
            kml = [(t[:22], round(float(m), 2), int(float(v)))
                   for t, m, v in ml_[["title", "mid", "volume_fp"]].values]
            fav_nick = _nick(fav)
            fav_abb = NFL_NICK_TO_ABB.get(fav_nick, "")
            pref = None
            if len(ml_):
                cand = ml_[ml_.ticker.str.endswith("-" + fav_abb)]
                if len(cand):
                    pref = cand.title.str.replace(" wins", "").iloc[0]
            ksp = _kalshi_near(sp_, hs.line if hs is not None else None, pref=pref)
            kto = _kalshi_near(to_, ht.line if ht is not None else None)
            s.append(f"  Kalshi ML {kml} | spread {ksp} | total {kto}")

        # INTERNATIONAL layer
        if sport == "nfl":
            intl = _intl_note(h, a, ct)
            if intl:
                s.append(intl)

        # SIM views
        if sport == "nfl" and len(simrows):
            sv = simrows[(simrows.event_id == eid) & (simrows.tag != "no_view")].sort_values(
                "conf", ascending=False)
            sim_text = "; ".join(
                f"{PROP_ABBR.get(r.market_key, r.market_key)} {r.player_name} {r.line:g} "
                f"{r.side_name or r.side} p={r.p_first:.2f} c{r.conf:g}"
                for r in sv.head(8).itertuples()
            ) if len(sv) else "no views"
            s.append(f"  SIM {simtag}: {sim_text}")

        # Injuries (NFL only)
        if sport == "nfl":
            for team in (a, h):
                s.append(f"  -- {team} injuries ({inj_file[9:22] if inj_file else 'none'})")
                for i in inj.get(team, []):
                    at = i.get("athlete", {})
                    pos = at.get("position", {}).get("abbreviation", "")
                    st = i.get("status") or ""
                    c = (i.get("shortComment") or "")[:150]
                    if pos in ("QB", "RB", "WR", "TE") or st in ("Out", "Doubtful", "Questionable", "Injured Reserve"):
                        s.append(f"     {st[:4]:4} {pos:2} {at.get('firstName', '')} "
                                 f"{at.get('lastName', '')}: {c}")
                nn = sorted(news.get(team, {}).items(), key=lambda kv: kv[1])[-5:]
                for hl, p in nn:
                    s.append(f"     news {p[5:16]} {hl[:100]}")
        elif sport == "ncaaf":
            s.append(f"  -- injuries: NCAAF has no ESPN injury feed")

        # Props with consensus delta (NFL only)
        if sport == "nfl":
            pr = g[g.player_name != ""]
            # Get all-book props for consensus
            allp = props_df[props_df.home_team == h] if not props_df.empty else pd.DataFrame()
            if not allp.empty:
                allp = allp[allp.pull_timestamp == allp.pull_timestamp.max()]
            s.append(f"  -- props (pull {str(pr.source_utc.max())[:16] if len(pr) else 'none'})")
            for pl, pg in pr.groupby("player_name"):
                items = []
                for r in pg.itertuples():
                    it = f"{PROP_ABBR.get(r.market_key, r.market_key)} {r.line:g} ({_fmt_price(r.price_first)}"
                    if r.two_way:
                        it += f"/{_fmt_price(r.price_second)})"
                        if not allp.empty:
                            o = allp[(allp.bookmaker != "hardrockbet_fl") &
                                     (allp.market_key == r.market_key) &
                                     (allp.player_name == pl) &
                                     (allp.line == r.line) &
                                     allp.over_price.notna() & allp.under_price.notna()]
                            if len(o):
                                c = float(np.median([_nv(x, y) for x, y in zip(o.over_price, o.under_price)]))
                                dlt = c - r.q_first
                                it += f" cons{len(o)} {'+' if dlt >= 0 else ''}{100 * dlt:.0f}pp"
                    else:
                        it += ")"
                    items.append(it)
                # Skip anytime TD longshots
                if (len(items) > 1 or
                        not items[0].startswith("atd 0.5 (+") or
                        int(pg.price_first.iloc[0]) < 800):
                    s.append(f"     * {pl}: " + ", ".join(items))

        packets[eid] = "\n".join(s)

    # Build header
    snap_name = os.path.basename(str(snaps[-1])) if snaps else "?"
    props_ts = str(sh[sh.player_name != ""].source_utc.max())[:16] if "source_utc" in sh.columns and len(sh[sh.player_name != ""]) else "none"
    header = (f"packet built {now.strftime('%Y-%m-%dT%H:%MZ')} | "
              f"snap {snap_name} | props pull {props_ts} | "
              f"kalshi {kalshi_file or 'none'} | injuries {inj_file or 'none'}")

    return header, packets


# ---------------------------------------------------------------------------
# READ — Messages API
# ---------------------------------------------------------------------------

def _load_spend(root):
    """Load or initialize the spend tracker."""
    p = root / "status" / "ai_reader_spend.json"
    if p.exists():
        return json.loads(p.read_text())
    return {"month": "", "calls": 0, "input_tokens": 0, "output_tokens": 0,
            "usd_estimate": 0.0, "model": ""}


def _save_spend(root, spend):
    """Save the spend tracker (committed file)."""
    p = root / "status" / "ai_reader_spend.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(spend, indent=1) + "\n")


def _check_spend_cap(root, cap_usd=None):
    """HALT if monthly spend exceeds the cap."""
    cap = cap_usd or float(os.environ.get("AI_READER_MONTHLY_CAP_USD", DEFAULT_MONTHLY_CAP_USD))
    spend = _load_spend(root)
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    if spend.get("month") == current_month and spend.get("usd_estimate", 0) >= cap:
        raise SystemExit(
            f"HALT: AI reader monthly spend ${spend['usd_estimate']:.2f} >= cap ${cap:.2f}")


def _update_spend(root, model, input_tokens, output_tokens):
    """Update the cumulative spend file."""
    spend = _load_spend(root)
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    if spend.get("month") != current_month:
        spend = {"month": current_month, "calls": 0, "input_tokens": 0,
                 "output_tokens": 0, "usd_estimate": 0.0, "model": model}
    spend["calls"] += 1
    spend["input_tokens"] += input_tokens
    spend["output_tokens"] += output_tokens
    spend["model"] = model
    # Estimate cost (Sonnet-class pricing: $3/M input, $15/M output)
    if "sonnet" in model.lower():
        cost = input_tokens * 3e-6 + output_tokens * 15e-6
    else:
        # Opus-class pricing: $15/M input, $75/M output
        cost = input_tokens * 15e-6 + output_tokens * 75e-6
    spend["usd_estimate"] = round(spend["usd_estimate"] + cost, 4)
    _save_spend(root, spend)
    return spend


def validate_pick(pick, sheet_row, sport):
    """Validate a single pick from the API response.
    Returns (is_valid, error_message).
    """
    if not isinstance(pick, dict):
        return False, "pick is not a dict"
    missing = PICK_SCHEMA_KEYS - set(pick.keys())
    if missing:
        return False, f"missing keys: {missing}"
    if pick["side"] not in VALID_SIDES:
        return False, f"invalid side: {pick['side']}"
    if pick["tag"] not in VALID_TAGS:
        return False, f"invalid tag: {pick['tag']}"
    conf = pick["conf"]
    if not isinstance(conf, (int, float)) or conf < 0 or conf > 30:
        return False, f"conf {conf} not in [0, 30]"
    reason = pick.get("reason", "")
    if pick["tag"] != "no_view":
        if len(reason) < 12 or len(reason) > 160:
            return False, f"reason length {len(reason)} not in [12, 160]"
    # Thesis validation
    thesis = pick.get("thesis", "")
    if pick["tag"] != "no_view" and sport == "nfl":
        if not thesis:
            return False, "NFL view pick missing thesis"
        claims = [c.strip() for c in thesis.split(";")]
        if len(claims) < 1 or len(claims) > 3:
            return False, f"thesis must have 1-3 claims, got {len(claims)}"
        for claim in claims:
            parts = claim.split(":")
            if len(parts) != 2:
                return False, f"invalid thesis claim: {claim}"
            link, dir_ = parts[0].strip(), parts[1].strip()
            if link not in THESIS_LINKS or dir_ not in THESIS_DIRS:
                return False, f"invalid thesis claim: {claim}"
    # Reject one-way picks (anytime TD)
    mk = pick["market"]
    if mk == "player_anytime_td" and pick["tag"] != "no_view":
        return False, "one-way market pick (anytime TD) is not allowed"
    # Reject ML longshots
    if mk == "h2h" and pick["tag"] != "no_view":
        # Check if implied prob < 28.6% (i.e. +250 or worse)
        if sheet_row is not None:
            price = (sheet_row.get("price_first") if pick["side"] == "first"
                     else sheet_row.get("price_second"))
            if price is not None:
                try:
                    p = float(price)
                    if p > 0 and p >= ML_LONGSHOT_THRESHOLD:
                        return False, f"ML longshot +{int(p)} rejected (>= +{ML_LONGSHOT_THRESHOLD})"
                except (ValueError, TypeError):
                    pass
    return True, ""


def read_game(packet_text, sheet_df, sport, model=None, root=ROOT, dry_run=False):
    """Call the Messages API for one game.

    Args:
        packet_text: the text packet for one game
        sheet_df: DataFrame of sheet rows for this game
        sport: "nfl" or "ncaaf"
        model: model ID (default from env or DEFAULT_MODEL)
        root: repo root
        dry_run: if True, skip the API call

    Returns:
        (picks_list, input_tokens, output_tokens) or raises SystemExit on HALT
    """
    model = model or os.environ.get("AI_READER_MODEL", DEFAULT_MODEL)

    # Check spend cap before calling
    _check_spend_cap(root)

    if dry_run:
        return [], 0, 0

    # Import anthropic (installed on the VM only)
    try:
        import anthropic
    except ImportError:
        raise SystemExit("HALT: anthropic package not installed (VM only)")

    # The key comes from the environment (loaded by the caller from /root/private/env)
    client = anthropic.Anthropic()  # uses ANTHROPIC_API_KEY from env

    # Build the user message: sheet summary + packet
    n_lines = len(sheet_df)
    sheet_summary = f"This game has {n_lines} quoted lines. "
    sheet_summary += "You must return exactly one JSON element per quoted line.\n\n"
    sheet_summary += packet_text

    message = client.messages.create(
        model=model,
        max_tokens=8192,
        system=READER_SYSTEM,
        messages=[{"role": "user", "content": sheet_summary}],
    )

    # Record spend FIRST — the call is paid for even if the response cannot be parsed
    input_tokens = message.usage.input_tokens
    output_tokens = message.usage.output_tokens
    _update_spend(root, model, input_tokens, output_tokens)

    # Extract the TEXT blocks only (claude-sonnet-5-5 returns a thinking block first)
    content = "".join(getattr(b, "text", "") for b in (message.content or [])
                      if getattr(b, "type", "") == "text")

    # Parse JSON
    picks = _parse_response(content, sheet_df, sport)
    return picks, input_tokens, output_tokens


def _parse_response(content, sheet_df, sport, retry_content=None):
    """Parse the API response into validated picks.

    Returns list of pick dicts. Raises SystemExit on unrecoverable errors.
    """
    text = retry_content or content
    # Try to extract JSON array from the response
    text = text.strip()
    if not text.startswith("["):
        # Try to find JSON array in the response
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            text = match.group(0)

    try:
        picks_raw = json.loads(text)
    except json.JSONDecodeError as e:
        if retry_content is not None:
            raise SystemExit(f"HALT: invalid JSON on retry: {e}")
        raise  # caller handles retry

    if not isinstance(picks_raw, list):
        raise SystemExit("HALT: response is not a JSON array")

    # Build lookup from sheet
    sheet_lookup = {}
    for _, r in sheet_df.iterrows():
        key = (r.market_key, r.player_name or "", float(r.line))
        sheet_lookup[key] = r.to_dict()

    picks = []
    errors = []
    for pick in picks_raw:
        key = (pick.get("market", ""), pick.get("player", ""), float(pick.get("line", 0)))
        sheet_row = sheet_lookup.get(key)
        ok, err = validate_pick(pick, sheet_row, sport)
        if not ok:
            errors.append(f"{key}: {err}")
        picks.append(pick)

    if errors:
        # Log errors but don't halt — the freeze validation will catch real issues
        for e in errors:
            print(f"  WARNING: {e}", file=sys.stderr)

    return picks


def picks_to_filled(picks, sheet_df, sport, event_id=None):
    """Convert API picks to a filled DataFrame matching the log_ai_opinions schema.

    p_first = book no-vig +/- conf/250 on the view's side, clipped [0.02, 0.98].
    P67: when event_id is set, match picks only against that event's rows.
    A pick naming a (market, player, line) not quoted for the event raises SystemExit.
    """
    # P67: filter sheet to the event if specified
    if event_id is not None:
        sheet_df = sheet_df[sheet_df.event_id == event_id].copy()
        if sheet_df.empty:
            raise SystemExit(f"HALT: no sheet rows for event {event_id}")
        # Validate: every pick must name a line quoted for this event
        sheet_keys = {(r.market_key, r.player_name or "", float(r.line))
                      for _, r in sheet_df.iterrows()}
        for p in picks:
            if p.get("tag") == "no_view" or p.get("conf", 0) == 0:
                continue
            pk = (p.get("market", ""), p.get("player", ""), float(p.get("line", 0)))
            # Spread sign normalisation: the sheet quotes the spread from the home (first) side;
            # a pick echoing the away number (+2.5 for a -2.5 quote) is the same contract, other side.
            if pk not in sheet_keys and pk[0] == "spreads" and (pk[0], pk[1], -pk[2]) in sheet_keys:
                p["line"] = -pk[2]
                p["side"] = "second" if p.get("side") == "first" else "first"
                pk = (pk[0], pk[1], -pk[2])
            if pk not in sheet_keys:
                raise SystemExit(
                    f"HALT for {event_id}: pick names unquoted line "
                    f"{pk} (only {len(sheet_keys)} lines quoted for this event)")

    filled_rows = []
    for _, row in sheet_df.iterrows():
        key = (row.event_id, row.market_key, row.player_name or "", float(row.line))
        # Find matching pick (P67: match by event_id too)
        match = None
        for p in picks:
            pk = (row.event_id, p.get("market", ""), p.get("player", ""), float(p.get("line", 0)))
            if pk == key:
                match = p
                break

        # Default: no_view pass with book probability
        if match is None or match.get("tag") == "no_view" or match.get("conf", 0) == 0:
            q = row.q_first if pd.notna(row.get("q_first")) else row.imp_first
            q_clipped = np.clip(q, 0.02, 0.98)
            filled_rows.append({
                "event_id": row.event_id, "market_key": row.market_key,
                "player_name": row.player_name or "", "line": float(row.line),
                "p_first": round(float(q_clipped), 4),
                "tag": "no_view",
                "reason": (match.get("reason", "") if match else
                           f"pass: HR {_fmt_price(row.price_first)}/{_fmt_price(row.price_second)}"),
                "conf": 0,
                "conf_rank": 0,  # placeholder, ranked later
                "thesis": "",
            })
        else:
            # Compute p_first from book no-vig +/- conf/250
            q = row.q_first if pd.notna(row.get("q_first")) else row.imp_first
            conf = int(match["conf"])
            side = match["side"]
            adjustment = conf / 250.0
            if side == "first":
                p_first = q + adjustment
            else:
                p_first = q - adjustment
            p_first = round(float(np.clip(p_first, 0.02, 0.98)), 4)

            filled_rows.append({
                "event_id": row.event_id, "market_key": row.market_key,
                "player_name": row.player_name or "", "line": float(row.line),
                "p_first": p_first,
                "tag": match["tag"],
                "reason": match["reason"][:160],
                "conf": conf,
                "conf_rank": 0,  # placeholder
                "thesis": match.get("thesis", ""),
            })

    # Assign conf_rank: ranked by conf desc (views first), then alphabetical
    df = pd.DataFrame(filled_rows)
    df = df.sort_values(["conf", "event_id", "market_key", "player_name"],
                        ascending=[False, True, True, True]).reset_index(drop=True)
    df["conf_rank"] = range(1, len(df) + 1)
    return df


# ---------------------------------------------------------------------------
# FREEZE — through existing log_ai_opinions
# ---------------------------------------------------------------------------

def freeze_reads(filled_df, sport, season, week, now, window="event",
                 reader_model=None, root=ROOT, triggers=None,
                 props_file=None, lines_file=None, inputs_digest=None,
                 packet_dir=None):
    """Freeze the filled picks through log_ai_opinions.freeze().

    Args:
        filled_df: DataFrame from picks_to_filled
        sport: "nfl" or "ncaaf"
        season: int
        week: int
        now: UTC datetime
        window: freeze window (default "event" for event-driven)
        reader_model: model string (default "ai_reader_v1b/<model>")
        root: repo root
        triggers: dict of {event_id: description}
        props_file: pinned props file path
        lines_file: pinned lines file path
        inputs_digest: digest string for dedup
        packet_dir: directory where packet files are saved

    Returns:
        (dest_path, sha256, frozen_df)
    """
    # Import and configure log_ai_opinions
    sys.path.insert(0, str(root / "nfl" / "pipeline"))
    import log_ai_opinions as lao
    lao.set_sport(sport)

    model = reader_model or f"ai_reader_v1b/{os.environ.get('AI_READER_MODEL', DEFAULT_MODEL)}"

    # Rebuild the sheet from the same tape
    props, lines = lao.newest_inputs(season, now,
                                     props_file=props_file, lines_file=lines_file)
    sheet = lao.build_sheet(props, lines, now)

    # Filter to the events in the filled df
    event_ids = set(filled_df.event_id.unique())
    sheet = sheet[sheet.event_id.isin(event_ids)].reset_index(drop=True)

    # Build pinned_inputs for manifest
    pinned = {}
    if props_file:
        pinned["props_file"] = str(props_file)
    if lines_file:
        pinned["lines_file"] = str(lines_file)
    if inputs_digest:
        pinned["inputs_digest"] = inputs_digest
    if triggers:
        pinned["triggers"] = triggers

    # Add "event" to valid windows
    if "event" not in lao.VALID_WINDOWS:
        lao.VALID_WINDOWS = set(lao.VALID_WINDOWS) | {"event"}

    dest, sha, frozen = lao.freeze(
        sheet, filled_df, season, week,
        pilot=False, now=now,
        reader_model=model,
        window=window,
        reader_file=str(Path(__file__)),
        pinned_inputs=pinned if pinned else None,
    )
    return dest, sha, frozen


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse
    ap = argparse.ArgumentParser(description="AI reader: packet -> API -> freeze")
    ap.add_argument("--sport", required=True, choices=["nfl", "ncaaf", "nhl", "nba"])
    ap.add_argument("--event-ids", required=True,
                    help="comma-separated event IDs")
    ap.add_argument("--props-file", default=None)
    ap.add_argument("--lines-file", default=None)
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--window", default="event")
    ap.add_argument("--triggers", default=None,
                    help="JSON dict of {event_id: trigger_text}")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--root", default=str(ROOT))
    args = ap.parse_args()

    if args.sport in ("nhl", "nba"):
        raise SystemExit(f"HALT: ai_reader not wired for {args.sport}")

    root = Path(args.root)
    now = datetime.now(timezone.utc)
    event_ids = [e.strip() for e in args.event_ids.split(",")]
    triggers = json.loads(args.triggers) if args.triggers else {}

    # Configure sport
    sys.path.insert(0, str(root / "nfl" / "pipeline"))
    import log_ai_opinions as lao
    lao.set_sport(args.sport)

    # Resolve inputs
    props, lines = lao.newest_inputs(
        args.season, now,
        props_file=args.props_file, lines_file=args.lines_file)
    sheet = lao.build_sheet(props, lines, now)
    sheet = sheet[sheet.event_id.isin(set(event_ids))].reset_index(drop=True)

    if sheet.empty:
        raise SystemExit("HALT: no lines for the requested events")

    # Build packets
    header, packets = build_packet(
        args.sport, event_ids, sheet, props, lines, now,
        root=root, triggers=triggers)
    print(header)

    # Save packets
    freeze_dir = lao.out_dir(args.season, args.week)
    freeze_dir.mkdir(parents=True, exist_ok=True)
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    packet_path = freeze_dir / f"packet_{ts}.txt"
    packet_path.write_text(header + "\n\n" + "\n\n".join(packets.values()))
    print(f"packet saved: {packet_path}")

    # Read each game
    model = os.environ.get("AI_READER_MODEL", DEFAULT_MODEL)
    all_picks = []
    for eid in event_ids:
        if eid not in packets:
            print(f"  skip {eid}: no packet")
            continue
        game_sheet = sheet[sheet.event_id == eid]
        print(f"\n  reading {eid} ({len(game_sheet)} lines)...")
        try:
            picks, in_tok, out_tok = read_game(
                packets[eid], game_sheet, args.sport,
                model=model, root=root, dry_run=args.dry_run)
            print(f"  {len(picks)} picks, {in_tok} in / {out_tok} out tokens")
            all_picks.extend(picks)
        except json.JSONDecodeError:
            # Retry once
            print(f"  JSON error on {eid}, retrying...")
            try:
                picks, in_tok, out_tok = read_game(
                    packets[eid], game_sheet, args.sport,
                    model=model, root=root, dry_run=args.dry_run)
                all_picks.extend(picks)
            except Exception as e:
                print(f"  HALT for {eid}: {e}")
                continue

    if not all_picks and not args.dry_run:
        raise SystemExit("HALT: no picks from any game")

    # Convert to filled DataFrame
    filled = picks_to_filled(all_picks, sheet, args.sport)
    print(f"\nfilled: {len(filled)} rows, {(filled.tag != 'no_view').sum()} views")

    if args.dry_run:
        print("dry run — skipping freeze")
        return

    # Freeze
    reader_model = f"ai_reader_v1b/{model}"
    dest, sha, frozen = freeze_reads(
        filled, args.sport, args.season, args.week, now,
        window=args.window, reader_model=reader_model, root=root,
        triggers=triggers, props_file=args.props_file, lines_file=args.lines_file)
    print(f"\nFROZEN: {dest.name} sha={sha[:16]} rows={len(frozen)}")

    # Print spend
    spend = _load_spend(root)
    print(f"spend: {json.dumps(spend)}")


if __name__ == "__main__":
    main()
