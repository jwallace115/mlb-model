#!/usr/bin/env python3
"""Export the Picks page data to a dict consumed by site/templates/picks.html.

Adapted from Cowork's export_picks.py (P42). The template is owned by ops/Cowork
and changed only with a screenshot.
"""
import json, re
from pathlib import Path

import build_site as bs
import sys, os

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "shared" / "pipeline"))
import build_top20 as bt, picks_ledger as pl

MARKET = {"prop:pass_td": "passing TDs", "prop:rec": "receptions", "prop:rec_yds": "receiving yards",
          "prop:rush_yds": "rushing yards", "prop:rush_att": "rush attempts", "prop:pass_yds": "passing yards",
          "prop:pass_att": "pass attempts", "prop:pass_cmp": "completions", "prop:atd": "anytime TD",
          "prop:int": "interceptions", "moneyline": "moneyline", "spread": "spread", "total": "total"}
TWO_WORD = {"Golden Flashes","Blue Raiders","Crimson Tide","Fighting Irish","Golden Hurricane","Red Raiders",
  "Nittany Lions","Tar Heels","Horned Frogs","Mean Green","Scarlet Knights","Golden Gophers","Yellow Jackets",
  "Black Knights","Ragin' Cajuns","Demon Deacons","Blue Devils","Green Wave","Golden Eagles","Rainbow Warriors",
  "Mountain Hawks","Red Wolves","Sun Devils","Fighting Illini","Golden Bears","Black Bears","Blue Hens","Red Flash",
  "Golden Panthers","Thundering Herd","Crimson Hawks","Delta Devils","Purple Aces","Mountain Lions","Golden Knights",
  "Blue Hose","Golden Lions","Fighting Hawks","Red Storm","Great Danes","Blue Demons","Golden Griffins","Golden Grizzlies",
  "Wolf Pack","River Hawks","Bobcats"}

def short_team(name, sport):
    if not name: return ""
    if sport == "NFL":
        return name.split()[-1]
    for m in TWO_WORD:
        if name.endswith(" " + m): return name[: -len(m) - 1]
    parts = name.split()
    return " ".join(parts[:-1]) if len(parts) > 1 else name

def plain_reason(r):
    """Deterministic rewrite of the reader_v3 reason string into a sentence; other readers' prose is kept."""
    if not r: return ""
    s = re.sub(r";\s*conf=[\d.]+;\s*rank=\d+\s*$", "", r.strip())
    s = re.sub(r";\s*conf=[\d.]+$", "", s)
    m = re.match(r"^(\d+) books \(Pin x3\) ([\d.]+) vs (?:HR|HAR) ([\d.]+)(.*)$", s)
    if not m: return s
    n, mk, hr, rest = m.groups()
    out = [f"Sharp consensus ({n} books, Pinnacle weighted) makes it {float(mk)*100:.0f}%; Hard Rock prices {float(hr)*100:.0f}%"]
    for part in [p.strip() for p in rest.split(";") if p.strip()]:
        p = part
        p = re.sub(r"^HR opened (\S+), now (\S+)$", r"Hard Rock opened \1, now \2", p)
        p = re.sub(r"^HR total ([\d.]+)->([\d.]+)$", r"Hard Rock total moved \1 → \2", p)
        p = re.sub(r"^HR spread ([-+\d.]+)->([-+\d.]+)$", r"Hard Rock spread moved \1 → \2", p)
        p = re.sub(r"^wind (\d+) mph/rain (\d+)% (Under|Over) shade$", r"wind \1 mph, \2% rain — leans \3", p)
        p = re.sub(r"^take (.+)\.?$", r"Take \1", p)
        out.append(p.rstrip("."))
    return ". ".join(out) + "."

def label(pick, sport):
    mk = pick.get("market") or ""; side = pick.get("side") or ""; pt = pick.get("point")
    if mk.startswith("prop"):
        return {"who": pick.get("player_name") or "", "what": f"{side} {bs.pt_label(pt, mk, side)} {MARKET.get(mk, mk)}".strip()}
    home, away = pick.get("home"), pick.get("away")
    if mk == "moneyline":
        return {"who": short_team(side, sport), "what": "moneyline"}
    if mk == "spread":
        return {"who": short_team(side, sport), "what": f"{bs.pt_label(pt, mk, side)}"}
    if mk == "total":
        return {"who": f"{side} {bs.pt_label(pt, mk, side)}", "what": f"{short_team(away, sport)} @ {short_team(home, sport)} total"}
    return {"who": side, "what": mk}

def moved(card):
    try:
        v = card["layers"]["line_movement"]["value"]; mp = v["book"].get("move_points")
        return None if mp is None else float(mp)
    except Exception:
        return None

def favour(card):
    try:
        txt = bs._summarize_lm(card)
    except Exception:
        return None
    if not txt: return None
    if "in your favour" in txt: return "favour"
    if "against you" in txt: return "against"
    if "unchanged" in txt: return "flat"
    return None

def picks_data(rows, now, ledger_dir, health, forward_status):
    """Build the full picks data dict for the template.

    rows: ledger view rows (from pl.view())
    now: datetime (UTC)
    ledger_dir: Path to the ledger directory
    health: parsed pipeline_health.json dict or None
    forward_status: parsed forward_status.json dict or None
    """
    layers_dir = Path(ledger_dir) / "layers"
    fs = forward_status or {}
    embargo_owners = set(fs.get("embargo_owners", []))

    # Health from page()'s counting (ERRORING/SILENT/NO_JOB = down; LATE/NOT_PUSHED/IGNORED = late)
    hsum = None; hbad = False
    if health:
        c = health.get("counts", {})
        bad = sum(c.get(k, 0) for k in ("ERRORING", "SILENT", "NO_JOB"))
        warn = sum(c.get(k, 0) for k in ("LATE", "NOT_PUSHED", "IGNORED"))
        hsum = f"{bad} down · {warn} late" if (bad or warn) else "all feeds on time"
        hbad = bool(bad)

    out = {"built_utc": now.isoformat(), "built_et": bs._utc_to_et(now.isoformat()),
           "health": {"summary": hsum, "bad": hbad}, "sports": {}}

    for sport in ["NFL", "NCAAF", "NHL", "NBA"]:
        res = bt.select_slate(rows, sport, now)
        if not res:
            out["sports"][sport] = {"events": [], "picks": [],
                                    "record_html": bs._record_section(rows, embargo_owners, sport, "")}
            continue
        events = []
        for e in res["events"]:
            ct = str(e["commence_time"]).replace(" ", "T")
            events.append({"event_id": e["event_id"], "away": e["away"], "home": e["home"],
                           "away_short": short_team(e["away"], sport), "home_short": short_team(e["home"], sport),
                           "kick_utc": ct, "kick_et": bs._utc_to_et(ct), "slot": bs._slot_for_commence(ct, sport),
                           "freeze_et": bs._utc_to_et(str(e["freeze_logged_utc"])), "window": e["window"], "n_picks": e["n_picks"]})
        picks = []
        for col in ("props", "sides"):
            for i, p in enumerate(res[col]):
                card = None; cp = layers_dir / f"{p['pick_id']}.json"
                if cp.exists():
                    try: card = json.loads(cp.read_text())
                    except Exception: card = None
                lab = label(p, sport); ct = str(p["commence_time"]).replace(" ", "T")
                picks.append({"pick_id": p["pick_id"], "col": col, "order": i, "who": lab["who"], "what": lab["what"],
                    "market": p.get("market"), "side": p.get("side"), "point": p.get("point"), "event_id": p["event_id"],
                    "game": f"{short_team(p['away'], sport)} @ {short_team(p['home'], sport)}", "kick_utc": ct,
                    "kick_et": bs._utc_to_et(ct), "slot": bs._slot_for_commence(ct, sport),
                    "price": bs.am(p.get("price_american")), "conf": p.get("conf"), "tag": p.get("tag"),
                    "reason": plain_reason(p.get("reason")), "window": p.get("window"),
                    "reader": "reader_v3" if "books (Pin x3)" in (p.get("reason") or "") else "AI reader",
                    "freeze_et": bs._utc_to_et(str(p["logged_utc"])),
                    "moved": moved(card) if card else None, "favour": favour(card) if card else None,
                    "card_html": bs._render_card(card, pick=p) if card else None})
        out["sports"][sport] = {"events": events, "picks": picks, "n_freezes": res.get("n_freezes"),
                                "unranked": len(res.get("unranked", [])),
                                "record_html": bs._record_section(rows, embargo_owners, sport, "")}

    pages = {"NFL": "nfl.html", "NCAAF": "ncaaf.html", "NHL": "nhl.html", "NBA": "nba.html"}
    counts = {s: sum(1 for e in v["events"] if e["kick_utc"] > now.isoformat()) for s, v in out["sports"].items()}
    out["pages"] = pages; out["counts"] = counts
    soonest = sorted([(e["kick_utc"], s) for s, v in out["sports"].items() for e in v["events"] if e["kick_utc"] > now.isoformat()])
    out["front"] = soonest[0][1] if soonest else "NFL"
    return out
