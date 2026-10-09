#!/usr/bin/env python3
"""
Static site builder for iamnotuncertain.net — runs on the VM from cron, writes plain HTML.

Every number on every page is read from a file in this repo (or a VM log named on the page),
and shows that file and its time. Missing or stale input renders as "no data", never a guess.

Inputs
  status/pipeline_health.json              (shared/pipeline/pipeline_health.py)
  data/odds_archive/<sport>/line_history/  (newest snapshot per sport → Today's slate, book coverage)
  site/tickets/*.json                      (AI parlay cards, one file per card — see site/tickets/README.md)
  site/signals_registry.json               (which signals exist, their label, their log)
  site/forward_status.json                 (NFL forward experiment: what was frozen, when — no results)
Output
  --out directory (default /var/www/iamnotuncertain): index.html (Picks), today.html,
  health.html, tracking.html, signal-<id>.html, forward.html, archive.html.
  Written to a temp dir and swapped in, so a reader never sees a half-built site.
"""

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(os.environ.get("SITE_REPO_ROOT") or Path(__file__).resolve().parent.parent)
ET = ZoneInfo("America/New_York")
TS_RE = re.compile(r"(\d{8}T\d{4}(?:\d{2})?Z)")
SPORTS = [  # label, archive folder, max snapshot age (min) before the slate shows "no data"
    ("NFL", "nfl", 90), ("NCAAF", "ncaaf", 90), ("NHL", "nhl", 90), ("NBA", "nba", 90),
]
BOOK_NAMES = {"hardrockbet_fl": "Hard Rock", "pinnacle": "Pinnacle", "draftkings": "DK", "fanduel": "FanDuel",
              "betmgm": "MGM", "williamhill_us": "Caesars", "betrivers": "BetRivers", "betonlineag": "BetOnline",
              "bovada": "Bovada", "lowvig": "LowVig"}
ARCHIVE_DIRS = [
    ("NFL game-line tape", "data/odds_archive/nfl/line_history", "ML, spread, total · 10 books"),
    ("NCAAF game-line tape", "data/odds_archive/ncaaf/line_history", "ML, spread, total · 10 books"),
    ("NHL game-line tape", "data/odds_archive/nhl/line_history", "ML, puck line, total · 10 books"),
    ("NBA game-line tape", "data/odds_archive/nba/line_history", "ML, spread, total · 10 books"),
    ("MLB game-line tape (off-season; MLB restarts 2027)", "data/odds_archive/baseball_mlb/line_history", "ML, run line, total · 10 books"),
    ("NFL props", "data/odds_archive/nfl/props", "10 player markets · 10 books"),
    ("NFL other markets", "data/odds_archive/nfl/event_markets", "alts, team totals, halves"),
    ("NHL event markets", "data/odds_archive/nhl/event_markets", "props + derivatives"),
    ("NFL history", "data/odds_archive/nfl/history", "past seasons: hourly lines, props, alts"),
    ("NCAAF history", "data/odds_archive/ncaaf/history", "past seasons: hourly lines, alts"),
    ("NHL history", "data/odds_archive/nhl/history", "past seasons: lines, props, derivatives, in-play"),
    ("MLB history (off-season; MLB restarts 2027)", "data/odds_archive/baseball_mlb/history", "past seasons: hourly lines, props, F5"),
    ("Kalshi NFL", "data/odds_archive/kalshi/nfl", "game, spread, total"),
    ("Kalshi NCAAF", "data/odds_archive/kalshi/ncaaf", "game, spread, total"),
]

# ------------------------------------------------------------------ helpers
E = html.escape


def now_utc():
    return datetime.now(timezone.utc)


def fmt_utc(dt):
    return dt.strftime("%Y-%m-%d %H:%MZ") if dt else "—"


def fmt_age(minutes):
    if minutes is None:
        return "—"
    m = int(minutes)
    if m < 90:
        return f"{m}m"
    if m < 60 * 48:
        return f"{m // 60}h {m % 60}m"
    return f"{m // 1440}d {(m % 1440) // 60}h"


def ts_from_name(name):
    m = TS_RE.search(name)
    if not m:
        return None
    s = m.group(1)
    return datetime.strptime(s, "%Y%m%dT%H%M%SZ" if len(s) == 16 else "%Y%m%dT%H%MZ").replace(tzinfo=timezone.utc)


def am(p):
    """American price as text with a real minus sign."""
    if p is None or (isinstance(p, float) and pd.isna(p)):
        return "—"
    p = int(round(float(p)))
    return f"+{p}" if p > 0 else f"−{abs(p)}"


def pt(x):
    if x is None or pd.isna(x):
        return "—"
    x = float(x)
    s = f"{abs(x):g}"
    return ("+" if x > 0 else "−" if x < 0 else "") + s


def load_json(path):
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return None


def src(text):
    return f'<span class="src">{E(text)}</span>'


NODATA = '<span class="nodata">no data</span>'

CSS = """
:root{--bg:#F5F6F7;--card:#FFFFFF;--line:#DADDE1;--line2:#E6E8EB;--ink:#14181F;--ink2:#2B323D;--muted:#4A5361;--head:#EEF0F2;
--accent:#0B6E69;--ok-bg:#E3F2E7;--ok:#146C2E;--sh-bg:#E3ECF8;--sh:#1E4E8C;--wa-bg:#FBEFD9;--wa:#7A4B00;--bad-bg:#F6E3E3;--bad:#8A1C1C;--pu-bg:#EEE5F6;--pu:#5B2A86;--off-bg:#ECEEF1;--off:#4A5361}
@media (prefers-color-scheme: dark){:root{--bg:#101318;--card:#171B22;--line:#2B313B;--line2:#232933;--ink:#E8EBEF;--ink2:#C9CFD8;--muted:#9AA3AF;--head:#1E232B;
--accent:#5CC8C0;--ok-bg:#16301F;--ok:#7FD39A;--sh-bg:#16263D;--sh:#9CC2F2;--wa-bg:#33270F;--wa:#F2C46B;--bad-bg:#3A1A1A;--bad:#F29C9C;--pu-bg:#2A1D38;--pu:#C9A6EE;--off-bg:#232933;--off:#9AA3AF}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:'IBM Plex Sans',system-ui,sans-serif;font-size:15px;line-height:1.45}
a{color:var(--accent)}header.top{background:#14181F;color:#F5F6F7}
.wrap{max-width:1200px;margin:0 auto;padding:0 16px}
.bar{display:flex;align-items:center;gap:22px;flex-wrap:wrap;padding:12px 0}
.brand{font-weight:700;font-size:18px;color:#fff;text-decoration:none}
nav{display:flex;gap:4px;flex-wrap:wrap;flex:1}nav a{color:#C9CFD8;padding:8px 12px;border-radius:6px;text-decoration:none;font-size:14px}
nav a.on{background:#2A313C;color:#fff;font-weight:600}
.pill{display:inline-flex;align-items:center;gap:8px;padding:6px 12px;border-radius:999px;font-size:13px;text-decoration:none}
.pill.good{background:#12301C;color:#9DE0B2}.pill.warn{background:#3A2A10;color:#F7D9A0}.pill.bad{background:#3D1616;color:#F5B5B5}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block}
main{padding:24px 0 48px;display:flex;flex-direction:column;gap:24px}
h1{margin:4px 0 0;font-size:32px;letter-spacing:-.02em}h2{margin:0;font-size:19px}h3{margin:0;font-size:16px}
.kicker{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;font-weight:600}
.lede{margin:6px 0 0;max-width:780px;color:var(--ink2)}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px}
.pad{padding:16px 18px}.row{display:flex;justify-content:space-between;align-items:baseline;gap:10px;flex-wrap:wrap}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 14px}
.tile .k{font-size:12px;color:var(--muted)}.tile .v{font-family:'IBM Plex Mono',monospace;font-size:20px}
.tablewrap{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:10px}
table{border-collapse:collapse;width:100%;font-size:14px}
th{background:var(--head);text-align:left;padding:9px 12px;font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);white-space:nowrap}
td{padding:9px 12px;border-top:1px solid var(--line2);vertical-align:top}
.mono,td.mono{font-family:'IBM Plex Mono',monospace}.num{text-align:right;font-family:'IBM Plex Mono',monospace;white-space:nowrap}
.src{font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--muted);overflow-wrap:anywhere}
.nodata{color:var(--bad);font-weight:600}
.b{font-size:11px;font-weight:700;letter-spacing:.06em;padding:3px 8px;border-radius:4px;white-space:nowrap;display:inline-block}
.s-FIRING,.s-LIVE{background:var(--ok-bg);color:var(--ok)}.s-SHADOW{background:var(--sh-bg);color:var(--sh)}
.s-LATE,.s-UNVALIDATED,.s-QUIET{background:var(--wa-bg);color:var(--wa)}
.s-SILENT,.s-ERRORING,.s-NO_JOB,.s-DEAD{background:var(--bad-bg);color:var(--bad)}
.s-NOT_PUSHED,.s-IGNORED{background:var(--pu-bg);color:var(--pu)}.s-OFF{background:var(--off-bg);color:var(--off)}
.note{font-size:13px;color:var(--muted)}.warnbox{background:var(--wa-bg);color:var(--wa);border-radius:10px;padding:12px 16px}
.legs td:first-child{font-weight:500}.muted{color:var(--muted)}
footer{font-size:12px;color:var(--muted);border-top:1px solid var(--line);padding-top:14px}
.card-layer{margin:6px 0;padding:6px 0;border-bottom:1px solid var(--line2)}
@media (max-width:640px){h1{font-size:26px}.bar{gap:10px}nav a{padding:8px 9px}
.tab-panel div[style*="grid-template-columns:1fr 1fr"]{grid-template-columns:1fr!important}}
"""

PAGES = [("index.html", "Picks"), ("today.html", "Today"), ("health.html", "Pipeline health"),
         ("tracking.html", "Tracking"), ("forward.html", "NFL forward"), ("archive.html", "Odds archive")]


def page(fname, title, body, health, built):
    nav = "".join(f'<a href="{f}" class="{"on" if f == fname else ""}">{E(t)}</a>' for f, t in PAGES)
    if health:
        c = health.get("counts", {})
        bad = sum(c.get(k, 0) for k in ("ERRORING", "SILENT", "NO_JOB"))
        warn = sum(c.get(k, 0) for k in ("LATE", "NOT_PUSHED", "IGNORED"))
        cls = "bad" if bad else ("warn" if warn else "good")
        col = {"bad": "#F05252", "warn": "#F0A830", "good": "#4CC27A"}[cls]
        txt = f"{bad} down · {warn} late" if (bad or warn) else "all feeds on time"
        pill = f'<a class="pill {cls}" href="health.html"><span class="dot" style="background:{col}"></span>{txt} · built {built:%H:%M}Z</a>'
    else:
        pill = f'<a class="pill bad" href="health.html"><span class="dot" style="background:#F05252"></span>health file missing · built {built:%H:%M}Z</a>'
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow">
<meta http-equiv="refresh" content="300"><title>{E(title)} · iamnotuncertain</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body>
<header class="top"><div class="wrap bar"><a class="brand" href="index.html">iamnotuncertain</a><nav>{nav}</nav>{pill}</div></header>
<div class="wrap"><main>{body}
<footer>Built {fmt_utc(built)} from files on the server. Every number names its source file and that file's time; a missing or stale file shows "no data".</footer>
</main></div></body></html>"""


def badge(s):
    return f'<span class="b s-{E(s)}">{E(s.replace("_", " "))}</span>'


# ------------------------------------------------------------------ odds snapshots
def newest_snapshot(folder):
    d = ROOT / "data" / "odds_archive" / folder / "line_history"
    files = sorted(d.glob("season=*/snap_*Z.parquet"), key=lambda p: ts_from_name(p.name) or datetime.min.replace(tzinfo=timezone.utc))
    for p in reversed(files[-3:]):  # newest readable of the last three
        try:
            return p, ts_from_name(p.name), pd.read_parquet(p)
        except Exception:
            continue
    return None, None, None


def book_line(g, book):
    b = g[g.bookmaker == book]
    if b.empty:
        return None
    parts = []
    sp = b[b.market == "spreads"]
    if not sp.empty:
        fav = sp.sort_values("point").iloc[0]
        parts.append(f"{short(fav.outcome_name)} {pt(fav.point)} ({am(fav.price)})")
    tot = b[b.market == "totals"]
    if not tot.empty:
        o = tot[tot.outcome_name == "Over"]
        u = tot[tot.outcome_name == "Under"]
        if not o.empty:
            parts.append(f"{float(o.iloc[0].point):g} ({am(o.iloc[0].price)}/{am(u.iloc[0].price) if not u.empty else '—'})")
    if not parts:
        ml = b[b.market == "h2h"]
        if not ml.empty:
            parts.append(" / ".join(f"{short(r.outcome_name)} {am(r.price)}" for r in ml.itertuples()))
    return " · ".join(parts) if parts else None


_ABBR = {}


_TWO_WORD = ("Red Sox", "White Sox", "Blue Jays", "Blue Jackets", "Golden Knights", "Maple Leafs", "Red Wings",
             "Trail Blazers", "Golden Hurricane", "Mean Green", "Green Wave", "Crimson Tide", "Golden Gophers",
             "Fighting Irish", "Sun Devils", "Yellow Jackets", "Tar Heels", "Blue Devils", "Red Raiders", "Horned Frogs",
             "Golden Bears", "Golden Eagles", "Black Knights", "Scarlet Knights", "Nittany Lions", "Demon Deacons",
             "Wolf Pack", "Rainbow Warriors", "Ragin' Cajuns", "Golden Flashes", "Thundering Herd", "Red Wolves")


def short(team):
    t = str(team)
    for m in _TWO_WORD:
        if t.endswith(" " + m):
            return m
    w = t.split()
    return w[-1] if len(w) > 1 else t


# ------------------------------------------------------------------ Today
def build_today(now, health):
    today = now.astimezone(ET).date()
    body = [f'<div class="row"><div><div class="kicker">{today:%A, %B} {today.day} · times ET</div><h1>Today</h1></div></div>']

    # tickets
    tdir = ROOT / "site" / "tickets"
    cards = []
    for p in sorted(tdir.glob("*.json")):
        c = load_json(p)
        if isinstance(c, dict) and str(c.get("slate_date")) == today.isoformat():
            cards.append((p, c))
    tick = ['<section class="card"><div class="pad row"><div><h2>AI parlay tickets</h2>'
            '<div class="note">As logged before kickoff. One price per leg: that price or better, bet it; worse, skip the leg.</div></div>'
            f'{src("site/tickets/")}</div>']
    if not cards:
        tick.append('<div class="pad" style="border-top:1px solid var(--line2)"><span class="muted">No tickets logged for today.</span></div>')
    for p, c in cards:
        legs = "".join(
            f"<tr><td>{E(str(l.get('leg', '')))}</td><td class='muted'>{E(str(l.get('game', '')))}</td>"
            f"<td class='num'>{E(am(l.get('price')) if isinstance(l.get('price'), (int, float)) else str(l.get('price', '—')))}</td>"
            f"<td>{E(str(l.get('why', '')))}</td></tr>" for l in c.get("legs", []))
        tick.append(f'<div class="pad" style="border-top:1px solid var(--line2)"><div class="row"><h3>{E(str(c.get("ticket", p.stem)))} · {len(c.get("legs", []))} leg{"s" if len(c.get("legs", [])) != 1 else ""}</h3>'
                    f'{src(f"{p.name} · logged {c.get("logged_utc", "?")} · prices from {c.get("prices_from", "?")}")}</div>'
                    f'<div class="tablewrap" style="margin-top:10px"><table class="legs"><tr><th>Leg</th><th>Game</th><th>Play to</th><th>Why (AI)</th></tr>{legs}</table></div></div>')
    tick.append("</section>")
    body.append("".join(tick))

    # slate
    rows, tiles, srcs = [], [], []
    for label, folder, max_age in SPORTS:
        path, ts, df = newest_snapshot(folder)
        if df is None:
            tiles.append(f'<div class="tile"><div class="k">{label}</div><div class="v">{NODATA}</div></div>')
            continue
        age = (now - ts).total_seconds() / 60
        srcs.append(f"{label} {path.name} ({fmt_age(age)} old)")
        if age > max_age:
            tiles.append(f'<div class="tile"><div class="k">{label}</div><div class="v">{NODATA}</div><div class="src">tape {fmt_age(age)} old</div></div>')
            continue
        df = df.copy()
        df["ct"] = pd.to_datetime(df.commence_time, utc=True)
        games = df[df.ct.dt.tz_convert(ET).dt.date == today]
        n = games.event_id.nunique()
        tiles.append(f'<div class="tile"><div class="k">{label}</div><div class="v">{n} game{"s" if n != 1 else ""}</div></div>')
        for eid, g in sorted(games.groupby("event_id"), key=lambda kv: kv[1].ct.iloc[0]):
            r0 = g.iloc[0]
            start = r0.ct.tz_convert(ET)
            started = r0.ct <= now
            hr = book_line(g, "hardrockbet_fl")
            pin = book_line(g, "pinnacle")
            rows.append(f"<tr><td class='muted'>{label}</td><td>{E(r0.away_team)} @ {E(r0.home_team)}</td>"
                        f"<td class='mono'>{start:%-I:%M %p}{' · live' if started else ''}</td>"
                        f"<td class='mono'>{E(hr) if hr else '<span class=muted>not on feed</span>'}</td>"
                        f"<td class='mono'>{E(pin) if pin else '<span class=muted>not on feed</span>'}</td></tr>")
    body.append(f'<div class="tiles">{"".join(tiles)}</div>')
    body.append('<section style="display:flex;flex-direction:column;gap:10px"><div class="row"><h2>Slate</h2>'
                f'{src(" · ".join(srcs))}</div>'
                + (f'<div class="tablewrap"><table><tr><th>Sport</th><th>Game</th><th>Start</th><th>Hard Rock</th><th>Pinnacle</th></tr>{"".join(rows)}</table></div>'
                   if rows else '<div class="card pad muted">No games today in any fresh snapshot.</div>')
                + '<div class="note">Hard Rock is only in the odds feed for NFL. For other sports its price comes from the app.</div></section>')

    # signals today
    reg = load_json(ROOT / "site" / "signals_registry.json") or {"signals": []}
    sig_cards = []
    for s in reg["signals"]:
        if not s.get("today"):
            continue
        rows_today = today_rows(s, today)
        if rows_today is None:
            val = NODATA
        else:
            val = f"{len(rows_today)} today" + ("".join(f"<div class='mono' style='font-size:13px'>{E(x)}</div>" for x in rows_today[:8]))
        sig_cards.append(f'<div class="card pad" style="display:flex;flex-direction:column;gap:6px"><div class="row"><h3>{E(s["name"])}</h3>{badge(s["label"])}</div>'
                         f'<div class="note">{E(s.get("market", ""))}</div><div>{val}</div>{src(s["path"])}</div>')
    body.append('<section style="display:flex;flex-direction:column;gap:10px"><h2>Signals today</h2>'
                f'<div class="tiles" style="grid-template-columns:repeat(auto-fit,minmax(260px,1fr))">{"".join(sig_cards) or "<span class=muted>none registered</span>"}</div></section>')
    return page("today.html", "Today", "\n".join(body), health, now)


def today_rows(s, today):
    data = load_json(ROOT / s["path"])
    if data is None:
        return None
    L = data if isinstance(data, list) else data.get(s.get("list_key", "signals"), [])
    out = []
    for e in L:
        if str(e.get(s.get("date_field", "date")))[:10] != today.isoformat():
            continue
        if s.get("fired_field") and not e.get(s["fired_field"]):
            continue
        out.append(" ".join(str(e.get(k, "")) for k in s.get("show", ["away_team", "home_team"])))
    return out


# ------------------------------------------------------------------ Tracking
def bets_for(s):
    """Rows of (date, result W/L/P, real_profit or None, price or None)."""
    data = load_json(ROOT / s["path"])
    if data is None:
        return None
    L = data if isinstance(data, list) else data.get(s.get("list_key", "signals"), [])
    out = []
    for e in L:
        if s.get("fired_field") and not e.get(s["fired_field"]):
            continue
        r = e.get(s["result_field"])
        if r is None or r == "":
            continue
        wv = s.get("win_values", ["WIN", 1, True])
        lv = s.get("loss_values", ["LOSS", 0, False])
        res = "W" if r in wv else "L" if r in lv else "P" if str(r).upper() == "PUSH" else None
        if res is None:
            continue
        profit = e.get(s["profit_field"]) if s.get("profit_field") else None
        price = e.get(s["price_field"]) if s.get("price_field") else None
        if profit is None and isinstance(price, (int, float)) and price != 0:
            # 1-unit stake at the price captured in the log
            win = price / 100 if price > 0 else 100 / abs(price)
            profit = round(win, 4) if res == "W" else (-1.0 if res == "L" else 0.0)
        out.append((str(e.get(s["date_field"]))[:10], res, profit, price))
    return out


def summarize(rows):
    n = len(rows)
    w = sum(r[1] == "W" for r in rows)
    l = sum(r[1] == "L" for r in rows)
    p = n - w - l
    flat = (w * (100 / 110) - l) / n if n else None
    real_rows = [r for r in rows if r[2] is not None]
    real = sum(float(r[2]) for r in real_rows) / len(real_rows) if real_rows else None
    return {"n": n, "w": w, "l": l, "p": p, "hit": w / (w + l) if (w + l) else None, "flat": flat, "real": real,
            "n_priced": len(real_rows),
            "first": min(r[0] for r in rows) if rows else None, "last": max(r[0] for r in rows) if rows else None}


def pct(x, signed=False):
    if x is None:
        return "—"
    return (f"{x * 100:+.1f}%" if signed else f"{x * 100:.1f}%").replace("-", "−")


def build_tracking(now, health, outdir):
    reg = load_json(ROOT / "site" / "signals_registry.json") or {"signals": []}
    rows = []
    for s in reg["signals"]:
        bets = bets_for(s) if s.get("result_field") else None
        detail = f'signal-{s["id"]}.html'
        if bets is None:
            stats_html = f"<td class='num'>{NODATA if s.get('result_field') else '—'}</td><td>—</td><td class='num'>—</td><td class='num'>—</td><td class='num'>—</td>"
        else:
            st = summarize(bets)
            real = pct(st["real"], True) if st["real"] is not None else ('<span class="muted">no captured price</span>' if st["n"] else "—")
            if st["real"] is not None and st["n_priced"] < st["n"]:
                real += f'<div class="note">{st["n_priced"]} of {st["n"]} priced</div>'
            stats_html = (f"<td class='num'>{st['n']}</td><td class='mono' style='font-size:12px;white-space:nowrap'>{st['first'] or '—'}<br>→ {st['last'] or '—'}</td>"
                          f"<td class='num'>{pct(st['hit'])}</td><td class='num'><b>{real}</b></td><td class='num muted'>{pct(st['flat'], True)}</td>")
            write_signal_page(s, bets, now, health, outdir)
        name = f'<a href="{detail}">{E(s["name"])}</a>' if bets else E(s["name"])
        rows.append(f"<tr><td>{name}<div class='src'>{E(s['path'])}</div></td><td class='muted'>{E(s.get('market', ''))}</td>"
                    f"<td>{badge(s['label'])}</td>{stats_html}<td class='note'>{E(s.get('note', ''))}</td></tr>")
    legend = "".join(f'<span style="display:inline-flex;gap:6px;align-items:center;margin-right:14px">{badge(k)}<span class="note">{v}</span></span>'
                     for k, v in [("LIVE", "passed every gate, money allowed"), ("SHADOW", "logged and graded, no money"),
                                  ("UNVALIDATED", "a record, not evidence"), ("DEAD", "failed or withdrawn")])
    body = (f'<div><h1>Tracking</h1><p class="lede">NFL, NCAAF, NHL, NBA — every signal and logged opinion, graded from its own log. '
            f'<b>Real-price ROI</b> uses the price captured when the pick was logged and is the number that counts. '
            f'Flat −110 ROI is a quick check only. Every figure shows its count and dates.</p></div><div>{legend}</div>'
            f'<div class="tablewrap"><table><tr><th>Signal</th><th>Market</th><th>Label</th><th>N</th><th>Dates</th><th>Hit</th>'
            f'<th style="color:var(--ink)">Real-price ROI</th><th>−110 (triage only)</th><th>Note</th></tr>{"".join(rows)}</table></div>'
            f'<div class="note">Labels come from site/signals_registry.json, which mirrors the project registry; they change only by decision, never from these numbers.</div>')
    return page("tracking.html", "Tracking", body, health, now)


def write_signal_page(s, bets, now, health, outdir):
    by = defaultdict(list)
    for r in bets:
        by[r[0][:7]].append(r)
    trs = []
    for m in sorted(by):
        st = summarize(by[m])
        trs.append(f"<tr><td class='mono'>{m}</td><td class='num'>{st['n']}</td><td class='num'>{st['w']}-{st['l']}-{st['p']}</td>"
                   f"<td class='num'>{pct(st['hit'])}</td><td class='num'>{pct(st['real'], True) if st['real'] is not None else '—'}</td>"
                   f"<td class='num muted'>{pct(st['flat'], True)}</td></tr>")
    tot = summarize(bets)
    share = max(len(v) for v in by.values()) / len(bets) if bets else 0
    warn = (f'<div class="warnbox">{share * 100:.0f}% of this record sits in one month — read the total with that in mind.</div>'
            if share >= 0.6 and len(by) > 1 else "")
    bands = defaultdict(list)
    for r in bets:
        if r[3] is None:
            continue
        p = float(r[3])
        band = "≤ −150" if p <= -150 else "−149…−111" if p <= -111 else "−110…+109" if p < 110 else "≥ +110"
        bands[band].append(r)
    band_rows = "".join(f"<tr><td>{b}</td><td class='num'>{summarize(v)['n']}</td><td class='num'>{pct(summarize(v)['hit'])}</td>"
                        f"<td class='num'>{pct(summarize(v)['real'], True) if summarize(v)['real'] is not None else '—'}</td></tr>"
                        for b, v in bands.items())
    body = (f'<div><div class="kicker"><a href="tracking.html">Tracking</a></div><h1>{E(s["name"])}</h1>'
            f'<p class="lede">{badge(s["label"])} {E(s.get("market", ""))} · {tot["n"]} graded, {tot["first"]} → {tot["last"]} · {src(s["path"])}</p></div>{warn}'
            f'<h2>By month</h2><div class="tablewrap"><table><tr><th>Month</th><th>N</th><th>W-L-P</th><th>Hit</th><th>Real-price ROI</th><th>−110 (triage)</th></tr>{"".join(trs)}</table></div>'
            + (f'<h2>By price band</h2><div class="tablewrap"><table><tr><th>Price</th><th>N</th><th>Hit</th><th>Real-price ROI</th></tr>{band_rows}</table></div>' if band_rows else
               '<div class="note">No captured prices in this log, so there is no price-band or real-price breakdown.</div>')
            + f'<div class="note">{E(s.get("note", ""))}</div>')
    (outdir / f'signal-{s["id"]}.html').write_text(page("tracking.html", s["name"], body, health, now))


# ------------------------------------------------------------------ Health
def build_health(now, health):
    if not health:
        return page("health.html", "Pipeline health", f"<h1>Pipeline health</h1><p>{NODATA}: status/pipeline_health.json is missing.</p>", None, now)
    gen = datetime.fromisoformat(health["generated_utc"])
    age = (now - gen).total_seconds() / 60
    stale = f'<div class="warnbox">The health file is {fmt_age(age)} old — the checker itself may have stopped.</div>' if age > 35 else ""
    order = ["FIRING", "QUIET", "LATE", "SILENT", "ERRORING", "NOT_PUSHED", "IGNORED", "NO_JOB", "OFF"]
    tiles = "".join(f'<div class="tile"><div class="k">{badge(k)}</div><div class="v">{health["counts"].get(k, 0)}</div></div>'
                    for k in order if health["counts"].get(k))
    rows = []
    for f in health["feeds"]:
        sched = "<br>".join(E(x) for x in f.get("schedule", [])[:4]) or "—"
        rows.append(f"<tr><td>{E(f.get('label', f['id']))}<div class='src'>{E(f['id'])}</div></td><td class='muted'>{E(f.get('sport', ''))}</td>"
                    f"<td class='muted'>{E(f.get('host', ''))}</td><td class='mono' style='font-size:12px'>{sched}</td>"
                    f"<td class='src'>{E(f.get('newest_file') or '—')}</td><td class='num'>{fmt_age(f.get('age_min'))}</td>"
                    f"<td>{badge(f['status'])}</td><td class='src'>{E((f.get('log_last_line') or f.get('note') or '')[:140])}</td></tr>")
    vm = health.get("vm") or {}
    pdm = health.get("push_daemon") or {}
    cr = health.get("credits") or {}
    side = (f'<div class="tiles" style="grid-template-columns:repeat(auto-fit,minmax(260px,1fr))">'
            f'<div class="card pad"><h3>VM</h3><div class="mono" style="font-size:13px;line-height:1.8">RAM {vm.get("ram_available_mb", "—")} MB free of {vm.get("ram_total_mb", "—")}<br>'
            f'swap used {vm.get("swap_used_mb", "—")} MB<br>disk {vm.get("disk_used_gb", "—")} / {vm.get("disk_total_gb", "—")} GB</div></div>'
            f'<div class="card pad"><h3>Push to GitHub</h3><div class="mono" style="font-size:13px;line-height:1.8">last good cycle {E(str(pdm.get("last_ok_utc") or "—"))}<br>failed cycles, 24 h: {pdm.get("failures_24h", "—")}</div>{src("/root/logs/push_daemon.log")}</div>'
            f'<div class="card pad"><h3>Odds API credits</h3><div class="mono" style="font-size:13px;line-height:1.8">'
            + (f'used {cr["used"]:,} of {cr["plan"]:,}<br>remaining {cr["remaining"]:,}<br>as of {E(cr["as_of_utc"][:16])}Z' if cr else NODATA)
            + f'</div>{src(cr.get("source", "") if cr else "")}</div></div>')
    body = (f'<div><div class="kicker">checked every 15 min on the VM · status/pipeline_health.json · {fmt_utc(gen)}</div><h1>Pipeline health</h1>'
            f'<p class="lede">Each job is judged against its own schedule, read from the VM crontab. Missing one due slot is LATE, two is SILENT. '
            f'A job whose log shows a crash after its last slot is ERRORING. QUIET means it ran and had nothing new to write; OFF means out of season.</p></div>'
            f'{stale}<div class="tiles">{tiles}</div>'
            f'<div class="tablewrap"><table><tr><th>Job</th><th>Sport</th><th>Host</th><th>Schedule (UTC)</th><th>Newest file</th><th>Age</th><th>Status</th><th>Last log line</th></tr>{"".join(rows)}</table></div>{side}')
    # Retired feeds
    retired = health.get("retired", [])
    if retired:
        ret_rows = "".join(f"<tr><td>{E(r.get('label', r['id']))}<div class='src'>{E(r['id'])}</div></td>"
                           f"<td class='muted'>{E(r.get('sport', ''))}</td>"
                           f"<td class='mono'>{E((r.get('newest_utc') or '—')[:16])}</td></tr>"
                           for r in retired)
        body += (f'<details><summary style="cursor:pointer;margin-top:24px;color:var(--muted)">Retired until 2027 ({len(retired)} feeds)</summary>'
                 f'<div class="tablewrap"><table><tr><th>Job</th><th>Sport</th><th>Last output</th></tr>{ret_rows}</table></div></details>')
    return page("health.html", "Pipeline health", body, health, now)


# ------------------------------------------------------------------ Forward
def build_forward(now, health):
    fs = load_json(ROOT / "site" / "forward_status.json")
    if not fs:
        inner = f"<p>{NODATA}: site/forward_status.json is missing.</p>"
    else:
        rows = "".join(f"<tr><td class='mono'>{E(str(r.get('week', '')))}</td><td>{E(r.get('slate', ''))}</td><td class='mono'>{E(r.get('frozen_at', ''))}</td>"
                       f"<td>{E(r.get('kind', ''))}</td><td class='src'>{E(r.get('receipt', ''))}</td></tr>" for r in fs.get("runs", []))
        inner = (f'<div class="warnbox"><b>No interim results.</b> Hit rates, Brier scores or profit for this experiment are not shown here before its pre-registered scoring exists.</div>'
                 f'<div class="tiles"><div class="tile"><div class="k">Scoring</div><div class="v" style="font-size:16px">{E(fs.get("scoring", "—"))}</div></div>'
                 f'<div class="tile"><div class="k">Next freeze</div><div class="v" style="font-size:16px">{E(fs.get("next", "—"))}</div></div></div>'
                 f'<div class="tablewrap"><table><tr><th>Week</th><th>Slate</th><th>Frozen at</th><th>Kind</th><th>Receipt</th></tr>{rows}</table></div>'
                 f'{src("site/forward_status.json · updated " + fs.get("updated_utc", "?"))}')
    body = (f'<div><h1>NFL forward experiment</h1><p class="lede">Status only. The sim\'s numbers are frozen before kickoff and scored later under rules '
            f'written in advance.</p></div>{inner}')
    return page("forward.html", "NFL forward", body, health, now)


# ------------------------------------------------------------------ Archive
def build_archive(now, health):
    cr = (health or {}).get("credits")
    if cr:
        used_pct = cr["used"] / cr["plan"] * 100
        first = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        nxt = (first + timedelta(days=32)).replace(day=1)
        credits = (f'<div class="row"><h2>Odds API credits — {now:%B}</h2>{src(cr["source"] + " · " + cr["as_of_utc"][:16] + "Z")}</div>'
                   f'<div style="height:16px;background:var(--line2);border-radius:4px;overflow:hidden;margin:10px 0"><div style="width:{max(used_pct, 0.4):.2f}%;height:100%;background:var(--accent)"></div></div>'
                   f'<div class="tiles"><div class="tile"><div class="k">Used</div><div class="v">{cr["used"]:,}</div></div>'
                   f'<div class="tile"><div class="k">Remaining</div><div class="v">{cr["remaining"]:,}</div></div>'
                   f'<div class="tile"><div class="k">Plan</div><div class="v">{cr["plan"]:,}</div></div>'
                   f'<div class="tile"><div class="k">Resets</div><div class="v" style="font-size:16px">{nxt:%b} 1, 00:00Z</div></div></div>'
                   f'<div class="note">No rollover: what is left at the reset is lost.</div>')
    else:
        credits = f"<h2>Odds API credits</h2><p>{NODATA}</p>"
    # coverage
    grid = []
    books = list(BOOK_NAMES)
    for label, folder, _ in SPORTS:
        path, ts, df = newest_snapshot(folder)
        if df is None:
            grid.append(f"<tr><td>{label}</td><td colspan='{len(books)}'>{NODATA}</td></tr>")
            continue
        ev = df.event_id.nunique()
        cells = []
        for b in books:
            n = df[df.bookmaker == b].event_id.nunique()
            v = round(n / ev * 100) if ev else 0
            cls = "s-SILENT" if v == 0 else "s-LATE" if v < 60 else ""
            cells.append(f"<td class='num {cls}' style='text-align:center'>{v}</td>")
        grid.append(f"<tr><td>{label}<div class='src'>{ev} events · {path.name}</div></td>{''.join(cells)}</tr>")
    cov = (f'<div class="row"><h2>Book coverage</h2><span class="note">% of events each book quoted in the newest snapshot</span></div>'
           f'<div class="tablewrap"><table><tr><th>Feed</th>{"".join(f"<th>{BOOK_NAMES[b]}</th>" for b in books)}</tr>{"".join(grid)}</table></div>')
    # holdings
    hold = []
    for label, rel, what in ARCHIVE_DIRS:
        d = ROOT / rel
        files = [p for p in d.rglob("*") if p.is_file() and p.suffix in (".parquet", ".gz", ".json")] if d.exists() else []
        if not files:
            hold.append(f"<tr><td>{label}</td><td class='muted'>{what}</td><td colspan='3'>{NODATA}</td></tr>")
            continue
        tss = [t for t in (ts_from_name(p.name) for p in files) if t]
        size = sum(p.stat().st_size for p in files) / 1e6
        span = f"{min(tss):%Y-%m-%d} → {max(tss):%Y-%m-%d %H:%MZ}" if tss else "—"
        hold.append(f"<tr><td>{label}<div class='src'>{rel}</div></td><td class='muted'>{what}</td><td class='num'>{len(files):,}</td>"
                    f"<td class='mono' style='font-size:12px'>{span}</td><td class='num'>{size:,.1f} MB</td></tr>")
    sp = load_json(ROOT / "status" / "history_spender.json")
    if sp and sp.get("latest"):
        L = sp["latest"]
        jr = "".join(f"<tr><td>{E(j)}</td><td class='num'>{c.get('ok', 0):,}</td><td class='num'>{c.get('empty', 0):,}</td>"
                     f"<td class='num'>{c.get('skip', 0):,}</td><td class='num'>{c.get('other', 0) + c.get('unsupported', 0):,}</td></tr>"
                     for j, c in (L.get("jobs") or {}).items())
        spender = (f'<section class="card pad"><div class="row"><h2>History spender — last night</h2>{src("status/history_spender.json · " + str(L.get("finished_utc")))}</div>'
                   f'<div class="tiles" style="margin-top:10px"><div class="tile"><div class="k">Spent</div><div class="v">{L.get("spent", 0):,}</div></div>'
                   f'<div class="tile"><div class="k">Calls</div><div class="v">{L.get("calls", 0):,}</div></div>'
                   f'<div class="tile"><div class="k">Reserve kept</div><div class="v">{L.get("reserve", 0):,}</div></div></div>'
                   f'<p class="note">Stopped because: {E(str(L.get("stop_reason")))}</p>'
                   + (f'<div class="tablewrap"><table><tr><th>Job</th><th>Bought</th><th>Empty</th><th>Already held</th><th>Errors</th></tr>{jr}</table></div>' if jr else "")
                   + '</section>')
    else:
        spender = f'<section class="card pad"><h2>History spender</h2><p>{NODATA}: it has not run yet.</p></section>'
    body = (f'<div><h1>Odds archive</h1><p class="lede">What is captured, from which books, and what it costs. Every capture is a new timestamped file; nothing is overwritten.</p></div>'
            f'<section class="card pad">{credits}</section>{spender}{cov}'
            f'<h2>Holdings on the server</h2><div class="tablewrap"><table><tr><th>Feed</th><th>Markets</th><th>Files</th><th>Span</th><th>Size</th></tr>{"".join(hold)}</table></div>')
    return page("archive.html", "Odds archive", body, health, now)


# ------------------------------------------------------------------ main
# ------------------------------------------------------------------ Picks
def _load_picks_ledger():
    """Load the picks ledger from PICKS_LEDGER_DIR. Returns (rows, sha12, mtime_utc) or (None, None, None)."""
    ledger_dir = os.environ.get("PICKS_LEDGER_DIR") or "/root/private/ledger"
    p = Path(ledger_dir) / "picks.jsonl"
    if not p.exists():
        return None, None, None
    try:
        text = p.read_bytes()
        sha12 = hashlib.sha256(text).hexdigest()[:12]
        mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
        rows = []
        for line in text.decode().strip().split("\n"):
            if line.strip():
                rows.append(json.loads(line))
        # Apply view logic: latest row per pick_id, then supersedes
        by_id = {}
        for r in rows:
            pid = r["pick_id"]
            ex = by_id.get(pid)
            if ex is None or (r.get("ingested_utc") or "") > (ex.get("ingested_utc") or ""):
                by_id[pid] = r
        superseded = {r["supersedes"] for r in by_id.values() if r.get("supersedes")}
        view = [r for pid, r in by_id.items() if pid not in superseded]
        return view, sha12, mtime
    except Exception:
        return None, None, None


def _picks_roi(rows):
    """Compute ROI from real prices. Returns (hit_rate, roi, n, n_priced, flat_roi)."""
    graded = [r for r in rows if r.get("result") in ("W", "L", "P")]
    if not graded:
        return None, None, 0, 0, None
    w = sum(1 for r in graded if r["result"] == "W")
    l = sum(1 for r in graded if r["result"] == "L")
    n = w + l
    hit = w / n if n else None
    # Real-price ROI
    priced = []
    for r in graded:
        pa = r.get("price_american")
        if pa is None or r["result"] == "P":
            continue
        try:
            p = int(float(pa))
            if p == 0:
                continue
            win = p / 100 if p > 0 else 100 / abs(p)
            profit = round(win, 4) if r["result"] == "W" else -1.0
            priced.append(profit)
        except (ValueError, TypeError):
            continue
    roi = sum(priced) / len(priced) if priced else None
    flat = (w * (100 / 110) - l) / len(graded) if len(graded) else None
    return hit, roi, len(graded), len(priced), flat


def _utc_to_et(s):
    """Convert a UTC datetime string to ET display string."""
    if not s:
        return ""
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return dt.astimezone(ET).strftime("%b %d %I:%M %p ET").lstrip("0").replace(" 0", " ")
    except Exception:
        return str(s)[:19]


def _slot_for_commence(commence_utc, sport):
    """Compute the slot label for a game's commence_time in ET.

    NFL: Thu / Fri / Sat / Sun early / Sun late / SNF / MNF / day name.
    NCAAF: day name, except Saturday splits Sat early / Sat afternoon / Sat night.
    NHL, NBA: the ET date like "Thu Oct 9".
    """
    if not commence_utc:
        return "unknown"
    try:
        dt = datetime.fromisoformat(str(commence_utc).replace("Z", "+00:00"))
        dt_et = dt.astimezone(ET)
    except Exception:
        return "unknown"

    day_name = dt_et.strftime("%a")  # Mon, Tue, ...
    hour_min = dt_et.hour * 60 + dt_et.minute

    if sport == "NFL":
        if day_name == "Thu":
            return "Thu"
        elif day_name == "Fri":
            return "Fri"
        elif day_name == "Sat":
            return "Sat"
        elif day_name == "Sun":
            if hour_min < 15 * 60:       # before 3:00 PM ET
                return "Sun early"
            elif hour_min < 19 * 60:     # 3:00–6:59 PM ET
                return "Sun late"
            else:                         # 7:00 PM ET+
                return "SNF"
        elif day_name == "Mon":
            return "MNF"
        else:
            return day_name
    elif sport == "NCAAF":
        if day_name == "Sat":
            if hour_min < 15 * 60 + 30:      # before 3:30 PM ET
                return "Sat early"
            elif hour_min < 19 * 60:          # 3:30–6:59 PM ET
                return "Sat afternoon"
            else:
                return "Sat night"
        return day_name
    else:
        # NHL, NBA: "Thu Oct 9"
        return dt_et.strftime("%a %b %-d")


def pt_label(point, market, side):
    """Format a point for display. Signs only on spreads; totals/props get plain number."""
    if point is None:
        return ""
    try:
        x = float(point)
    except (ValueError, TypeError):
        return str(point)
    is_spread = (market == "spread" or market == "spreads"
                 or (bool(market) and "spread" in market.lower()
                     and side not in ("Over", "Under")))
    s = f"{abs(x):g}"
    if is_spread:
        return ("+" if x > 0 else "\u2212" if x < 0 else "") + s
    return s


def _summarize_lm(card):
    """Plain-English summary of the line_movement layer."""
    layer = card.get("layers", {}).get("line_movement", {})
    val = layer.get("value")
    if not val or not isinstance(val, dict):
        return None

    side = card.get("side", "")
    market = card.get("market", "")
    point = card.get("point")
    book_name = BOOK_NAMES.get(card.get("book", ""), card.get("book", ""))
    home = card.get("home", "")
    away = card.get("away", "")
    logged_utc = card.get("logged_utc", "")

    parts = []

    # Market + game
    if market.startswith("prop:"):
        player = card.get("player_name", "")
        mkt_label = market.replace("prop:", "").replace("_", " ")
        parts.append(f"{player} {mkt_label} ({away} at {home}).")
    else:
        parts.append(f"{market.title()} market, {away} at {home}.")

    # Consensus open
    cons = val.get("consensus", {})
    cons_open = cons.get("open", {})
    cons_close = cons.get("close", {})
    if cons_open and cons_open.get("median_point") is not None:
        parts.append(f"Opened at {cons_open['median_point']} across {cons_open.get('n_books', '?')} books"
                     f" on {_utc_to_et(cons_open.get('as_of'))}.")

    # Book open
    bk = val.get("book")
    if bk:
        bk_open = bk.get("open")
        bk_close = bk.get("close")
        if bk_open:
            op = bk_open.get("point")
            opr = bk_open.get("price")
            parts.append(f"{book_name} first posted {pt(op) if op is not None else '—'}@{am(opr)}"
                         f" on {_utc_to_et(bk_open.get('as_of'))}.")

        # Pick time
        if bk_close:
            cp = bk_close.get("point")
            cpr = bk_close.get("price")
            parts.append(f"At pick time ({_utc_to_et(logged_utc)}) {book_name} was"
                         f" {pt(cp) if cp is not None else '—'}@{am(cpr)}")
            if cons_close and cons_close.get("median_point") is not None:
                parts[-1] += f" and the {cons_close.get('n_books', '?')}-book consensus was {cons_close['median_point']}."
            else:
                parts[-1] += "."

        # Movement
        if bk_open and bk_close:
            op = bk_open.get("point")
            cp = bk_close.get("point")
            opr = bk_open.get("price")
            cpr = bk_close.get("price")
            move_pts = bk.get("move_points")
            if move_pts is not None and op is not None:
                parts.append(f"Moved {move_pts:+.1f} points at {book_name} since it posted"
                             + (f"; price {am(opr)} → {am(cpr)}." if opr is not None and cpr is not None else "."))
            elif opr is not None and cpr is not None and opr != cpr:
                parts.append(f"Price {am(opr)} → {am(cpr)} at {book_name}.")
            if cons_open.get("median_point") is not None and cons_close.get("median_point") is not None:
                cons_move = cons_close["median_point"] - cons_open["median_point"]
                if abs(cons_move) > 0.001:
                    parts.append(f"Consensus moved {cons_move:+.1f} since the market opened.")

        # Direction sentence
        direction = _lm_direction(card)
        if direction:
            parts.append(direction)
    elif not bk:
        if book_name:
            parts.append(f"{book_name} had no quote in the window; consensus only.")

    # Source line
    n_rows = val.get("n_rows", 0)
    source_str = layer.get("source", "")
    n_files = len([s for s in source_str.split(", ") if s]) if source_str else 0
    as_of = layer.get("as_of", "")
    if n_rows:
        parts.append(f"{n_rows} snapshots / {n_files} pulls.")

    return " ".join(parts)


def _lm_direction(card):
    """One sentence: 'That is the line moving in your favour / against you / unchanged'."""
    layer = card.get("layers", {}).get("line_movement", {})
    val = layer.get("value")
    if not val or not isinstance(val, dict):
        return None

    side = card.get("side", "")
    market = card.get("market", "")
    point = card.get("point")
    bk = val.get("book")
    if not bk:
        return None

    bk_open = bk.get("open", {})
    bk_close = bk.get("close", {})
    op = bk_open.get("point") if bk_open else None
    cp = bk_close.get("point") if bk_close else None
    opr = bk_open.get("price") if bk_open else None
    cpr = bk_close.get("price") if bk_close else None

    favour = None

    if market == "moneyline":
        # No point; direction from price. Longer price = in favour.
        if opr is not None and cpr is not None:
            if opr < 0 and cpr < 0:
                # -150 → -130: abs decreases → price longer → in favour
                favour = abs(cpr) < abs(opr)
            elif opr > 0 and cpr > 0:
                # +120 → +140: increases → longer → in favour
                favour = cpr > opr
            elif opr < 0 and cpr > 0:
                favour = True  # moved from fav to dog → longer
            elif opr > 0 and cpr < 0:
                favour = False  # moved from dog to fav → shorter
            if opr == cpr:
                favour = None  # unchanged
    elif market == "spread":
        # Bettor's point going UP is in favour (+7.5→+8.5, −9.5→−8.5 both go up numerically)
        if op is not None and cp is not None:
            if cp > op:
                favour = True
            elif cp < op:
                favour = False
            # equal → unchanged
    elif market in ("total", "totals") or market.startswith("prop"):
        # Over: number going DOWN is in favour; Under: number going UP is in favour
        if op is not None and cp is not None:
            s_lower = str(side).lower()
            if s_lower == "over":
                if cp < op:
                    favour = True
                elif cp > op:
                    favour = False
            elif s_lower == "under":
                if cp > op:
                    favour = True
                elif cp < op:
                    favour = False

    side_s = f"{side} {pt(point)}" if point is not None else side
    if favour is True:
        return f"That is the line moving in your favour for {side_s}."
    elif favour is False:
        return f"That is the line moving against you for {side_s}."
    else:
        return f"The line is unchanged for {side_s}."


def _summarize_weather(layer):
    """Plain-English weather summary."""
    val = layer.get("value")
    if not val or not isinstance(val, dict):
        return None
    if val.get("indoor"):
        return f"Indoor ({val.get('stadium', '')}; {val.get('roof', 'dome')})."
    stadium = val.get("stadium", "")
    wind = val.get("wind_mph")
    wind_dir = val.get("wind_dir", "")
    precip = val.get("precip_prob_pct")
    temp = val.get("temp_f")
    forecast = val.get("forecast", "")
    as_of_et = _utc_to_et(layer.get("as_of"))
    parts = [f"Outdoor at {stadium}:"]
    if temp is not None:
        parts.append(f"{temp}°F,")
    if wind is not None:
        parts.append(f"{wind} mph wind" + (f" {wind_dir}" if wind_dir else "") + ",")
    if precip is not None:
        parts.append(f"{precip}% rain chance at kickoff")
    if forecast:
        parts.append(f"({forecast})")
    parts.append(f"(NWS forecast as of {as_of_et}).")
    return " ".join(parts)


def _summarize_sim(layer, point):
    """Plain-English sim summary."""
    val = layer.get("value")
    if not val or not isinstance(val, dict):
        return None
    p_first = val.get("p_first")
    edge = val.get("edge")
    parts = []
    if p_first is not None:
        parts.append(f"The sim's number for this market: {p_first:.1%}")
        if point is not None:
            parts.append(f"vs the line {pt(point)}.")
        else:
            parts.append(".")
    if edge is not None:
        parts.append(f"Edge: {edge:+.1%}.")
    return " ".join(parts) if parts else None


def _render_card(card, pick=None):
    """Render a detail card as HTML — plain-English summary above raw data in <details>.
    pick: optional pick row dict to supplement card fields (e.g. book)."""
    if not card:
        return '<div class="note muted">card not built yet</div>'
    # Merge pick fields into card for summary generation (card fields take precedence if present)
    merged = dict(card)
    if pick:
        for k in ("book", "side", "market", "point", "home", "away", "player_name", "logged_utc"):
            if merged.get(k) is None and pick.get(k) is not None:
                merged[k] = pick[k]
    parts = []
    for layer_name, layer in card.get("layers", {}).items():
        if not layer:
            continue
        label = layer_name.replace("_", " ").title()
        source_s = f' · {src(str(layer.get("source", ""))[:80])}' if layer.get("source") else ""
        as_of_s = f' · as of {E(str(layer.get("as_of", ""))[:19])}' if layer.get("as_of") else ""
        val = layer.get("value")
        note = layer.get("note")

        # Generate plain-English summary based on layer type
        summary = None
        if layer_name == "line_movement" and val and isinstance(val, dict):
            summary = _summarize_lm(merged)
        elif layer_name == "weather" and val and isinstance(val, dict):
            summary = _summarize_weather(layer)
        elif layer_name == "sim" and val and isinstance(val, dict):
            summary = _summarize_sim(layer, merged.get("point"))

        if note:
            parts.append(f'<div class="card-layer"><b>{label}</b>{source_s}{as_of_s}<br>'
                         f'<span class="muted">{E(str(note))}</span></div>')
        elif val is None:
            continue
        elif isinstance(val, dict):
            items = " · ".join(f"{k}: {E(str(v))}" for k, v in val.items() if v is not None)
            summary_html = f'<p>{E(summary)}</p>' if summary else ""
            raw_html = f'<details><summary class="muted" style="cursor:pointer;font-size:0.85em">Raw data</summary><div class="note" style="margin-top:4px">{items}</div></details>'
            parts.append(f'<div class="card-layer"><b>{label}</b>{source_s}{as_of_s}{summary_html}{raw_html}</div>')
        elif isinstance(val, list):
            if not val:
                parts.append(f'<div class="card-layer"><b>{label}</b>{source_s}: none found</div>')
            else:
                li = "".join(f'<div class="note">{E(str(item.get("headline", item.get("name", str(item))))[:150])}</div>' for item in val[:5])
                parts.append(f'<div class="card-layer"><b>{label}</b>{source_s}{as_of_s}{li}</div>')
        else:
            parts.append(f'<div class="card-layer"><b>{label}</b>{source_s}: {E(str(val))}</div>')
    return "".join(parts) if parts else '<div class="note muted">no layers</div>'


def _render_pick_row(rank, pick, card, is_prop, data_attrs=None):
    """Render a single ranked pick row with expandable detail card."""
    pid = pick.get("pick_id", "")
    market = pick.get("market", "")
    side = pick.get("side", "")
    if is_prop:
        label = f'{E(str(pick.get("player_name", "")))} {E(str(market))} {E(str(side))}'
        if pick.get("point") is not None:
            label += f' {pt_label(pick["point"], market, side)}'
    else:
        label = f'{E(str(side))} {E(str(market))}'
        if pick.get("point") is not None:
            label += f' {pt_label(pick["point"], market, side)}'
    game = f'{E(str(pick.get("away", "")))} @ {E(str(pick.get("home", "")))}'
    price_s = am(pick.get("price_american"))
    conf_s = str(int(pick["conf"])) if pick.get("conf") is not None else "—"
    reason_s = E(str(pick.get("reason") or "")[:120])
    card_html = _render_card(card, pick=pick)

    # "moved since open" from the card's line_movement layer
    move_s = "—"
    if card:
        lm = card.get("layers", {}).get("line_movement", {})
        val = lm.get("value")
        if isinstance(val, dict) and isinstance(val.get("book"), dict):
            mp = val["book"].get("move_points")
            if mp is not None:
                move_s = f'{mp:+.1f} pts'

    # Data attributes for JS filtering
    da = ""
    if data_attrs:
        da = " " + " ".join(f'{k}="{E(str(v))}"' for k, v in data_attrs.items())

    # Freeze info line
    freeze_line = ""
    if data_attrs:
        window = pick.get("window") or "legacy"
        reader = pick.get("_reader") or ""
        freeze_et = _utc_to_et(pick.get("logged_utc"))
        freeze_line = f'<br><span class="muted" style="margin-left:36px;font-size:11px">{E(window)} · {E(reader)} · {E(freeze_et)}</span>'

    return (f'<details id="{E(pid)}"{da}><summary style="cursor:pointer;padding:8px 0;border-bottom:1px solid var(--line2)">'
            f'<span class="rank" style="display:inline-block;width:28px;text-align:right;margin-right:8px"><b>{rank}</b></span>'
            f'{label}<br><span class="muted" style="margin-left:36px">{game} · {price_s} · conf {conf_s} · moved: {move_s}</span>'
            f'<br><span class="note" style="margin-left:36px">{reason_s}</span>'
            f'{freeze_line}'
            f'</summary><div class="card pad" style="margin:8px 0 16px 36px">{card_html}</div></details>')


def _load_clv(ledger_dir):
    """Load clv.jsonl and return dict of pick_id → row."""
    p = Path(ledger_dir) / "clv.jsonl"
    if not p.exists():
        return {}
    clv_by_pid = {}
    try:
        for line in p.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                clv_by_pid[r["pick_id"]] = r
    except Exception:
        pass
    return clv_by_pid


def _record_section(rows, embargo_owners, sport, source_info):
    """Build the Record section for a sport tab."""
    graded = [r for r in rows if r.get("result") in ("W", "L", "P", "VOID") and r.get("sport") == sport]
    if not graded:
        return '<div class="card pad muted">No graded picks yet.</div>'

    # Load CLV
    ledger_dir = Path(os.environ.get("PICKS_LEDGER_DIR") or "/root/private/ledger")
    clv_by_pid = _load_clv(ledger_dir)

    trs = []
    by_key = defaultdict(list)
    for r in graded:
        by_key[(r.get("owner", "?"), r.get("window", "legacy"))].append(r)

    for (owner, window), orows in sorted(by_key.items()):
        if owner in embargo_owners:
            dates = [r.get("commence_time", "")[:10] for r in orows if r.get("commence_time")]
            first = min(dates) if dates else "—"
            last = max(dates) if dates else "—"
            trs.append(f"<tr><td>{E(owner)}</td><td class='muted'>{E(window)}</td>"
                       f"<td class='num'>{len(orows)}</td>"
                       f"<td class='mono' style='font-size:12px'>{first} → {last}</td>"
                       f"<td colspan='4'>scoring not published</td></tr>")
            continue

        hit, roi, n_graded, n_priced, flat = _picks_roi(orows)
        dates = [r.get("commence_time", "")[:10] for r in orows if r.get("commence_time")]
        first = min(dates) if dates else "—"
        last = max(dates) if dates else "—"

        # CLV summary
        clv_rows = [clv_by_pid.get(r.get("pick_id")) for r in orows if clv_by_pid.get(r.get("pick_id"))]
        clv_vals = [c["clv_points"] for c in clv_rows if c.get("clv_points") is not None]
        clv_s = f'{sum(clv_vals)/len(clv_vals):+.1f} ({len(clv_vals)}N, {sum(1 for v in clv_vals if v > 0)/len(clv_vals)*100:.0f}%>0)' if clv_vals else "—"

        by_month = defaultdict(list)
        for r in orows:
            m = (r.get("commence_time") or "")[:7]
            if m:
                by_month[m].append(r)
        month_parts = []
        max_share = 0
        for m in sorted(by_month):
            mh, mr, mn, _, _ = _picks_roi(by_month[m])
            month_parts.append(f"{m}: {mn}N {pct(mh)}")
            if n_graded and mn / n_graded > max_share:
                max_share = mn / n_graded
        flag = ' <span class="b s-LATE">≥60% in one month</span>' if max_share >= 0.6 else ""

        trs.append(f"<tr><td>{E(owner)}</td><td class='muted'>{E(window)}</td>"
                   f"<td class='num'>{n_graded}</td>"
                   f"<td class='mono' style='font-size:12px'>{first} → {last}</td>"
                   f"<td class='num'>{pct(hit)}</td>"
                   f"<td class='num'><b>{pct(roi, True) if roi is not None else '—'}</b></td>"
                   f"<td class='num muted'>{pct(flat, True) if flat is not None else '—'}{flag}</td>"
                   f"<td class='num muted'>{clv_s}</td></tr>"
                   f"<tr><td colspan='8' class='note' style='padding-top:0'>{' · '.join(month_parts)}</td></tr>")

    return (f'<div class="tablewrap"><table><tr><th>Owner</th><th>Window</th><th>N</th>'
            f'<th>Dates</th><th>Hit</th><th>Real-price ROI</th><th>−110 (triage)</th><th>CLV</th></tr>'
            f'{"".join(trs)}</table></div>{source_info}')


def build_picks(now, health):
    import sys as _sys
    _sys.path.insert(0, str(ROOT / "shared" / "pipeline"))
    import build_top20 as bt

    fs = load_json(ROOT / "site" / "forward_status.json") or {}
    embargo_owners = set(fs.get("embargo_owners", []))
    rows, sha12, mtime = _load_picks_ledger()

    if rows is None:
        inner = f"<p>{NODATA}: picks ledger not found (PICKS_LEDGER_DIR not set or file absent).</p>"
        return page("index.html", "Picks", f'<div><h1>Picks</h1></div>{inner}', health, now)

    source_info = src(f"picks.jsonl {sha12} {fmt_utc(mtime)}")
    ledger_dir = Path(os.environ.get("PICKS_LEDGER_DIR") or "/root/private/ledger")
    layers_dir = ledger_dir / "layers"

    # Build tabs
    tab_order = ["NFL", "NCAAF", "NHL", "NBA"]
    tab_links = []
    tab_bodies = []

    for sport in tab_order:
        result = bt.select_slate(rows, sport, now)
        anchor = sport.lower()
        tab_links.append(f'<a href="#tab-{anchor}" class="tab-link" style="padding:8px 16px;text-decoration:none;'
                         f'border-bottom:2px solid var(--accent);font-weight:600">{sport}</a>')

        if result is None:
            tab_bodies.append(f'<div id="tab-{anchor}" class="tab-panel">'
                              f'<div class="card pad muted">No picks logged yet for {sport}.</div></div>')
            rec = _record_section(rows, embargo_owners, sport, source_info)
            tab_bodies[-1] = tab_bodies[-1][:-6] + f'<h3 style="margin-top:24px">Record — {sport}</h3>{rec}</div>'
            continue

        # Header: "showing N picks on G games from F freezes · newest <window> freeze <ET>"
        n_total = len(result["props"]) + len(result["sides"])
        n_games = len(result["events"])
        n_freezes = result["n_freezes"]
        newest_ev = max(result["events"], key=lambda e: e.get("freeze_logged_utc", ""))
        newest_window = newest_ev.get("window", "legacy")
        newest_et = _utc_to_et(newest_ev.get("freeze_logged_utc"))
        header_text = (f"showing {n_total} picks on {n_games} games from {n_freezes} freezes "
                       f"· newest {newest_window} freeze {newest_et}")
        header_html = f'<div class="picks-header muted" style="margin-bottom:8px">{E(header_text)}</div>'

        # Compute slots for each event
        import os as _os
        events_with_slots = []
        for ev in result["events"]:
            slot = _slot_for_commence(ev["commence_time"], sport)
            kick_et = _utc_to_et(ev["commence_time"])
            events_with_slots.append({**ev, "slot": slot, "kick_et": kick_et})

        # Slot chips
        from collections import OrderedDict
        slots = OrderedDict()
        for ev in events_with_slots:
            s = ev["slot"]
            if s not in slots:
                slots[s] = {"n_games": 0, "first_kick": ev["commence_time"], "event_ids": []}
            slots[s]["n_games"] += 1
            slots[s]["event_ids"].append(ev["event_id"])
            if ev["commence_time"] < slots[s]["first_kick"]:
                slots[s]["first_kick"] = ev["commence_time"]

        slot_chips_html = []
        for s, info in slots.items():
            kick_et = _utc_to_et(info["first_kick"])
            eids_json = E(json.dumps(info["event_ids"]))
            slot_chips_html.append(
                f'<button class="slot-chip" data-slot="{E(s)}" data-events="{eids_json}" '
                f'data-sport="{E(anchor)}" '
                f'style="padding:4px 10px;margin:2px;border:1px solid var(--line);border-radius:12px;'
                f'background:var(--bg2);cursor:pointer;font-size:12px">'
                f'{E(s)} · {info["n_games"]} game{"s" if info["n_games"] != 1 else ""} · first kick {E(kick_et)}'
                f'</button>')

        # "Sunday" super-chip for NFL (Sun early + Sun late + SNF, NOT MNF)
        if sport == "NFL":
            sun_eids = []
            for s in ("Sun early", "Sun late", "SNF"):
                if s in slots:
                    sun_eids.extend(slots[s]["event_ids"])
            if sun_eids:
                sun_eids_json = E(json.dumps(sun_eids))
                slot_chips_html.append(
                    f'<button class="slot-chip" data-slot="Sunday" data-events="{sun_eids_json}" '
                    f'data-sport="{E(anchor)}" '
                    f'style="padding:4px 10px;margin:2px;border:1px solid var(--line);border-radius:12px;'
                    f'background:var(--bg2);cursor:pointer;font-size:12px">'
                    f'Sunday · {len(sun_eids)} games</button>')

        # "All upcoming" chip
        all_eids = [ev["event_id"] for ev in events_with_slots]
        all_eids_json = E(json.dumps(all_eids))
        slot_chips_html.append(
            f'<button class="slot-chip" data-slot="All upcoming" data-events="{all_eids_json}" '
            f'data-sport="{E(anchor)}" '
            f'style="padding:4px 10px;margin:2px;border:1px solid var(--line);border-radius:12px;'
            f'background:var(--bg2);cursor:pointer;font-size:12px">'
            f'All upcoming · {len(all_eids)} games</button>')

        slot_row = f'<div class="slot-chips" data-sport="{E(anchor)}" style="margin-bottom:8px;display:flex;flex-wrap:wrap;gap:2px">{"".join(slot_chips_html)}</div>'

        # Game chips
        game_chips_html = []
        for ev in events_with_slots:
            game_chips_html.append(
                f'<button class="game-chip" data-event="{E(ev["event_id"])}" '
                f'data-slot="{E(ev["slot"])}" data-kick="{E(str(ev["commence_time"]))}" '
                f'data-sport="{E(anchor)}" '
                f'style="padding:3px 8px;margin:2px;border:1px solid var(--line);border-radius:8px;'
                f'background:var(--bg2);cursor:pointer;font-size:11px">'
                f'{E(ev["away"])} @ {E(ev["home"])} · {E(ev["kick_et"])}'
                f'</button>')
        game_row = f'<div class="game-chips" data-sport="{E(anchor)}" style="margin-bottom:12px;display:flex;flex-wrap:wrap;gap:2px">{"".join(game_chips_html)}</div>'

        # Build event_id → slot mapping for rows
        event_slot = {ev["event_id"]: ev["slot"] for ev in events_with_slots}
        event_reader = {}
        for ev in events_with_slots:
            event_reader[ev["event_id"]] = ev.get("reader", "")

        # Load cards
        def _load_card(pid):
            p = layers_dir / f"{pid}.json"
            if p.exists():
                try:
                    return json.loads(p.read_text())
                except Exception:
                    pass
            return None

        # Props column with data attributes
        props_html = []
        for i, pick in enumerate(result["props"]):
            card = _load_card(pick.get("pick_id"))
            eid = pick.get("event_id", "")
            slot = event_slot.get(eid, "unknown")
            kick = pick.get("commence_time", "")
            pick["_reader"] = event_reader.get(eid, "")
            da = {"data-event": eid, "data-slot": slot,
                  "data-kick": str(kick), "data-col": "props",
                  "data-order": str(i)}
            props_html.append(_render_pick_row(i + 1, pick, card, is_prop=True, data_attrs=da))

        # Sides column with data attributes
        sides_html = []
        for i, pick in enumerate(result["sides"]):
            card = _load_card(pick.get("pick_id"))
            eid = pick.get("event_id", "")
            slot = event_slot.get(eid, "unknown")
            kick = pick.get("commence_time", "")
            pick["_reader"] = event_reader.get(eid, "")
            da = {"data-event": eid, "data-slot": slot,
                  "data-kick": str(kick), "data-col": "sides",
                  "data-order": str(i)}
            sides_html.append(_render_pick_row(i + 1, pick, card, is_prop=False, data_attrs=da))

        cols = (f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:24px">'
                f'<div><h3>Top 20 — player props</h3>{"".join(props_html) if props_html else "<div class=\"muted\">none</div>"}</div>'
                f'<div><h3>Top 20 — sides / totals / ML</h3>{"".join(sides_html) if sides_html else "<div class=\"muted\">none</div>"}</div></div>')

        # Unranked
        unranked_html = ""
        if result["unranked"]:
            unranked_html = (f'<details style="margin-top:16px"><summary class="muted" style="cursor:pointer">'
                             f'{len(result["unranked"])} unranked — no confidence recorded</summary>'
                             f'<div class="note" style="margin-top:8px">'
                             + ", ".join(f'{E(str(r.get("player_name") or r.get("side", "")))} ({E(str(r.get("market", "")))})'
                                        for r in result["unranked"][:30])
                             + ("..." if len(result["unranked"]) > 30 else "")
                             + '</div></details>')

        # Record section
        rec = _record_section(rows, embargo_owners, sport, source_info)

        tab_bodies.append(f'<div id="tab-{anchor}" class="tab-panel">'
                          f'{header_html}{slot_row}{game_row}{cols}{unranked_html}'
                          f'<h3 style="margin-top:24px">Record — {sport}</h3>{rec}</div>')

    tabs_nav = f'<div style="display:flex;gap:4px;border-bottom:1px solid var(--line);margin-bottom:16px">{"".join(tab_links)}</div>'
    tabs_content = "".join(tab_bodies)

    # Inline JS for slot/game filtering
    filter_js = _picks_filter_js()

    body = (f'<div><h1>Picks</h1><p class="lede">NFL, NCAAF, NHL, NBA — top 20 picks by confidence, '
            f'ranked from the reader\'s latest freeze. Click a pick to see its detail card. '
            f'No stakes, slip ids or share links.</p></div>'
            f'{tabs_nav}{tabs_content}{filter_js}')
    return page("index.html", "Picks", body, health, now)


def _picks_filter_js():
    """Inline JS for slot/game chip filtering and rank renumbering."""
    return '''<script>
(function(){
var PF={};
function init(){
  document.querySelectorAll('.tab-panel').forEach(function(panel){
    var sport=panel.id.replace('tab-','');
    var slots=panel.querySelectorAll('.slot-chip');
    var games=panel.querySelectorAll('.game-chip');
    var rows=panel.querySelectorAll('details[data-event]');
    if(!rows.length)return;
    // Build state: which game event_ids are ticked
    var ticked={};
    games.forEach(function(g){ticked[g.getAttribute('data-event')]=false;});
    // Find next slot to kick
    var now=Date.now();
    var slotKick={};
    games.forEach(function(g){
      var k=new Date(g.getAttribute('data-kick')).getTime();
      var s=g.getAttribute('data-slot');
      if(k>now&&(!slotKick[s]||k<slotKick[s]))slotKick[s]=k;
    });
    // Hide past games from chips
    games.forEach(function(g){
      var k=new Date(g.getAttribute('data-kick')).getTime();
      if(k<=now)g.style.display='none';
    });
    // Find next slot: smallest first-kick still > now
    var nextSlot=null,nextKick=Infinity;
    for(var s in slotKick){if(slotKick[s]<nextKick){nextKick=slotKick[s];nextSlot=s;}}
    // Default: tick the next slot
    function tickSlot(slotName){
      slots.forEach(function(btn){
        var eids=JSON.parse(btn.getAttribute('data-events').replace(/&quot;/g,\'"\'));
        if(btn.getAttribute('data-slot')===slotName){
          btn.style.background='var(--accent)';btn.style.color='#fff';
          eids.forEach(function(eid){
            var k=games.length?null:null;
            // Only tick if game is upcoming
            var g=panel.querySelector('.game-chip[data-event="'+eid+'"]');
            if(g&&new Date(g.getAttribute('data-kick')).getTime()>now)ticked[eid]=true;
          });
        }
      });
      games.forEach(function(g){
        if(ticked[g.getAttribute('data-event')]){
          g.style.background='var(--accent)';g.style.color='#fff';
        }
      });
    }
    if(nextSlot)tickSlot(nextSlot);
    else{// tick all
      games.forEach(function(g){
        var k=new Date(g.getAttribute('data-kick')).getTime();
        if(k>now){ticked[g.getAttribute('data-event')]=true;g.style.background='var(--accent)';g.style.color='#fff';}
      });
    }
    function applyFilter(){
      var cols={props:[],sides:[]};
      rows.forEach(function(r){
        var eid=r.getAttribute('data-event');
        var col=r.getAttribute('data-col');
        var order=parseInt(r.getAttribute('data-order'),10);
        if(ticked[eid]){r.style.display='';cols[col].push({el:r,order:order});}
        else{r.style.display='none';}
      });
      // Sort by server order, renumber, cap at 20
      for(var c in cols){
        cols[c].sort(function(a,b){return a.order-b.order;});
        var shown=0;
        cols[c].forEach(function(item,idx){
          var rankSpan=item.el.querySelector('.rank');
          if(idx<20){rankSpan.innerHTML='<b>'+(idx+1)+'</b>';item.el.style.display='';shown++;}
          else{item.el.style.display='none';}
        });
        // Show "20 of N" if needed
        var hdr=panel.querySelector('h3');
        if(cols[c].length>20&&hdr){
          var existing=panel.querySelector('.cap-note-'+c);
          if(!existing){
            var note=document.createElement('span');
            note.className='muted cap-note-'+c;
            note.style.fontSize='11px';note.style.marginLeft='8px';
            hdr.parentNode.insertBefore(note,hdr.nextSibling);
            existing=note;
          }
          existing.textContent='20 of '+cols[c].length+' shown';
        }
      }
    }
    applyFilter();
    // Slot chip click
    slots.forEach(function(btn){
      btn.addEventListener('click',function(){
        var eids=JSON.parse(btn.getAttribute('data-events').replace(/&quot;/g,\'"\'));
        // Toggle: if all ticked → untick; else tick all
        var allOn=eids.every(function(eid){return ticked[eid];});
        // Reset all slots/games visuals
        slots.forEach(function(b){b.style.background='var(--bg2)';b.style.color='';});
        if(allOn){eids.forEach(function(eid){ticked[eid]=false;});}
        else{
          // Clear all first
          for(var k in ticked)ticked[k]=false;
          eids.forEach(function(eid){
            var g=panel.querySelector('.game-chip[data-event="'+eid+'"]');
            if(g&&new Date(g.getAttribute('data-kick')).getTime()>now)ticked[eid]=true;
          });
          btn.style.background='var(--accent)';btn.style.color='#fff';
        }
        games.forEach(function(g){
          if(ticked[g.getAttribute('data-event')]){g.style.background='var(--accent)';g.style.color='#fff';}
          else{g.style.background='var(--bg2)';g.style.color='';}
        });
        applyFilter();
      });
    });
    // Game chip click
    games.forEach(function(g){
      g.addEventListener('click',function(){
        var eid=g.getAttribute('data-event');
        ticked[eid]=!ticked[eid];
        if(ticked[eid]){g.style.background='var(--accent)';g.style.color='#fff';}
        else{g.style.background='var(--bg2)';g.style.color='';}
        // Update slot chip visuals
        slots.forEach(function(btn){
          var seids=JSON.parse(btn.getAttribute('data-events').replace(/&quot;/g,\'"\'));
          var allOn=seids.every(function(e){return ticked[e];});
          if(allOn&&seids.length){btn.style.background='var(--accent)';btn.style.color='#fff';}
          else{btn.style.background='var(--bg2)';btn.style.color='';}
        });
        applyFilter();
      });
    });
  });
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);
else init();
})();
</script>'''


def build(out, now=None):
    now = now or now_utc()
    health = load_json(ROOT / "status" / "pipeline_health.json")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=".site-", dir=out.parent))
    pages = {"index.html": build_picks(now, health), "today.html": build_today(now, health),
             "health.html": build_health(now, health),
             "tracking.html": build_tracking(now, health, tmp),
             "forward.html": build_forward(now, health),
             "archive.html": build_archive(now, health)}
    for name, text in pages.items():
        (tmp / name).write_text(text)
    os.chmod(tmp, 0o755)
    old = out.with_name(out.name + ".old")
    if old.exists():
        shutil.rmtree(old)
    if out.exists():
        os.replace(out, old)
    os.replace(tmp, out)
    if old.exists():
        shutil.rmtree(old)
    return sorted(p.name for p in out.iterdir())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/var/www/iamnotuncertain")
    a = ap.parse_args()
    files = build(a.out)
    print(f"site built {fmt_utc(now_utc())} -> {a.out}: {', '.join(files)}")


if __name__ == "__main__":
    main()
