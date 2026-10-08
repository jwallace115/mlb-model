#!/usr/bin/env python3
"""reader_v3: parameterised reader for the blind opinion log.

Port of reader_v2 (research/layers/_to_delete/ai_w4/reader_v2.py, 205 lines,
sha256 315b44e2…) with the same rules and arithmetic, but with --as-of and
--injury-report arguments so every input is chosen deterministically.

Rules (unchanged from reader_v2):
  market  - sharp-weighted consensus (Pinnacle x3, others x1); one-way ATD gets
            median of other books' implied Yes * 0.88
  news    - official injury report: Out/Doubtful noted in reason
  history - 0.005 Under lean on two-way props; 0.01 Under prior when no other
            book quotes the line
  Kalshi  - game-winner mid-price blended into h2h consensus (weight 2)
  NWS     - wind/precip Under shade on totals and pass/rec markets
  HR move - Hard Rock opening vs current for game lines

P24: this is the canonical reader; reader_v2 stays untouched in _to_delete.
"""
import argparse
import hashlib
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
TS_RE = re.compile(r"(\d{8}T\d{4}(?:\d{2})?Z)")


def _parse_ts(filename):
    """Extract UTC timestamp from a filename like snap_20261004T150000Z.parquet."""
    m = TS_RE.search(str(filename))
    if not m:
        return None
    s = m.group(1)
    if len(s) == 13:  # YYYYMMDDTHHMMZ
        s = s[:11] + "00" + s[11:]
    return datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)


def _newest_le(files, cutoff):
    """Return the file whose embedded timestamp is newest and <= cutoff, or None."""
    best, best_ts = None, None
    for f in files:
        ts = _parse_ts(f)
        if ts is None or ts > cutoff:
            continue
        if best_ts is None or ts > best_ts:
            best, best_ts = f, ts
    return best


def _kalshi_prefix(slate_date):
    """Derive the Kalshi ticker prefix from a slate date.
    2026-10-04 -> KXNFLGAME-26OCT04; 2026-10-11 -> KXNFLGAME-26OCT11."""
    d = datetime.strptime(str(slate_date)[:10], "%Y-%m-%d")
    return f"KXNFLGAME-{d.strftime('%y%b%d').upper()}"


def imp(a):
    a = float(a)
    return 100 / (a + 100) if a > 0 else -a / (-a + 100)


W = {"pinnacle": 3.0}
MK = {"player_anytime_td": "anytime TD", "player_reception_yds": "rec yds",
      "player_receptions": "receptions", "player_rush_yds": "rush yds",
      "player_rush_attempts": "rush att", "player_pass_attempts": "pass att",
      "player_pass_completions": "completions", "player_pass_interceptions": "INTs",
      "player_pass_tds": "pass TDs", "player_pass_yds": "pass yds",
      "h2h": "moneyline", "spreads": "spread", "totals": "total"}


def _load_inputs(as_of, root):
    """Select input files bounded by as_of. Returns (props, lines, KAL, WX, HIST, files_used)."""
    files_used = {}

    # --- Props: all data_*.parquet across all season/month dirs, rows with pull_timestamp <= as_of ---
    props_dir = root / "data" / "odds_archive" / "nfl" / "props"
    props_frames = []
    for pf in sorted(props_dir.glob("season=*/month=*/data_*.parquet")):
        df = pd.read_parquet(pf)
        df["player_name"] = df["player_name"].fillna("")
        df["line"] = df["line"].fillna(0.5).astype(float)
        df["_pt"] = pd.to_datetime(df["pull_timestamp"], format="mixed", utc=True)
        before = df[df["_pt"] <= as_of]
        if not before.empty:
            props_frames.append(before.drop(columns="_pt"))
            files_used[f"props:{pf.name}"] = str(before["pull_timestamp"].max())
    props = pd.concat(props_frames, ignore_index=True) if props_frames else pd.DataFrame()

    # --- Lines: newest snapshot <= as_of ---
    lines_dir = root / "data" / "odds_archive" / "nfl" / "line_history" / "season=2026"
    snaps = sorted(lines_dir.glob("snap_*.parquet"))
    snap_file = _newest_le(snaps, as_of)
    if snap_file is None:
        raise SystemExit("HALT: no game-line snapshot <= as-of")
    lines = pd.read_parquet(snap_file)
    snap_ts = _parse_ts(snap_file)
    files_used["lines"] = f"{snap_file.name} ({snap_ts.isoformat()})"

    # --- Kalshi: newest snapshot <= as_of ---
    kal_dir = root / "data" / "odds_archive" / "kalshi" / "nfl" / "season=2026"
    kal_snaps = sorted(kal_dir.glob("snap_*.parquet"))
    kal_file = _newest_le(kal_snaps, as_of)
    KAL = pd.DataFrame()
    if kal_file is not None:
        KAL = pd.read_parquet(kal_file)
        files_used["kalshi"] = f"{kal_file.name} ({_parse_ts(kal_file).isoformat()})"

    # --- NWS weather: newest snapshot <= as_of ---
    wx_dir = root / "data" / "weather_archive" / "nws" / "forecasts" / "season=2026"
    wx_snaps = sorted(wx_dir.glob("snap_*.parquet"))
    wx_file = _newest_le(wx_snaps, as_of)
    WX = pd.DataFrame()
    if wx_file is not None:
        WX = pd.read_parquet(wx_file)
        WX = WX[WX["roof"] == "outdoors"]
        files_used["nws"] = f"{wx_file.name} ({_parse_ts(wx_file).isoformat()})"

    # --- HR line history: all snapshots <= as_of, hardrockbet_fl only ---
    hist_frames = []
    for f in snaps:
        ts = _parse_ts(f)
        if ts is None or ts > as_of:
            continue
        d = pd.read_parquet(f, columns=["snapshot_utc", "event_id", "bookmaker",
                                        "market", "outcome_name", "point", "price"])
        d = d[d["bookmaker"].isin(["hardrockbet_fl", "hardrockbet"])]
        if len(d):
            hist_frames.append(d)
    HIST = pd.concat(hist_frames, ignore_index=True) if hist_frames else pd.DataFrame()

    return props, lines, KAL, WX, HIST, files_used


def _load_news(injury_report_path):
    """Load injury report CSV -> {player_name: note}. Empty dict if path is None or missing."""
    NEWS = {}
    if injury_report_path is None:
        return NEWS
    p = Path(injury_report_path)
    if not p.exists():
        return NEWS
    for x in pd.read_csv(p).itertuples(index=False):
        NEWS[x.player] = f"Official report: {x.game_status} ({x.injuries})."
    return NEWS


def consensus_prop(r, props):
    pull = props[(props["event_id"] == r.event_id) & (props["market_key"] == r.market_key)
                 & (props["player_name"] == r.player_name) & (props["line"] == float(r.line))
                 & (props["bookmaker"] != "hardrockbet_fl")]
    if pull.empty:
        return None, 0
    newest = pull.groupby("bookmaker")["pull_timestamp"].transform("max")
    pull = pull[pull["pull_timestamp"] == newest]
    vals, ws = [], []
    for _, b in pull.iterrows():
        if pd.isna(b.over_price):
            continue
        if r.two_way:
            if pd.isna(b.under_price):
                continue
            o, u = imp(b.over_price), imp(b.under_price)
            vals.append(o / (o + u))
        else:
            vals.append(imp(b.over_price) * 0.88)
        ws.append(W.get(b.bookmaker, 1.0))
    if not vals:
        return None, 0
    if r.two_way:
        return float(np.average(vals, weights=ws)), len(vals)
    return float(np.median(vals)), len(vals)


def consensus_game(r, lines):
    g = lines[(lines["event_id"] == r.event_id) & (lines["market"] == r.market_key)
              & (lines["bookmaker"] != "hardrockbet_fl")]
    vals, ws = [], []
    for bk, s in g.groupby("bookmaker"):
        a = s[s["outcome_name"] == r.first_side]
        b = s[s["outcome_name"] == r.second_side]
        if len(a) != 1 or len(b) != 1:
            continue
        a, b = a.iloc[0], b.iloc[0]
        if r.market_key != "h2h" and abs(float(a.point if pd.notna(a.point) else 0) - float(r.line)) > 1e-9:
            continue
        o, u = imp(a.price), imp(b.price)
        vals.append(o / (o + u))
        ws.append(W.get(bk, 1.0))
    if not vals:
        return None, 0
    return float(np.average(vals, weights=ws)), len(vals)


def kalshi_home(r, KAL):
    for _, k in KAL.iterrows():
        if str(r.home_team).startswith(str(k["yes_sub_title"])):
            try:
                return (float(k["yes_bid_dollars"]) + float(k["yes_ask_dollars"])) / 2
            except (TypeError, ValueError):
                return None
    return None


def weather(r, WX):
    w = WX[WX["team"] == r.home_team]
    if w.empty:
        return None
    k = pd.Timestamp(r.commence_time)
    vs = pd.to_datetime(w["valid_start"], utc=True)
    ve = pd.to_datetime(w["valid_end"], utc=True)
    x = w[(vs <= k) & (ve > k)]
    if x.empty:
        return None
    x = x.iloc[0]
    return float(x["wind_mph_mean"]), float(x["precip_prob_pct"] or 0)


def line_move(r, HIST):
    if HIST.empty:
        return None
    h = HIST[(HIST["event_id"] == r.event_id) & (HIST["market"] == r.market_key)
             & (HIST["outcome_name"] == r.first_side)]
    if h.empty:
        return None
    h = h.sort_values("snapshot_utc")
    col = "price" if r.market_key == "h2h" else "point"
    return h.iloc[0][col], h.iloc[-1][col]


def read_opinions(sheet, props, lines, KAL, WX, HIST, NEWS, kalshi_prefix):
    """Core reader logic — returns a DataFrame with columns matching reader_v2 output."""
    if kalshi_prefix and not KAL.empty:
        KAL = KAL[KAL["ticker"].str.startswith(kalshi_prefix)]
    else:
        KAL = pd.DataFrame()

    out = []
    for r in sheet.itertuples(index=False):
        game = r.market_key in ("h2h", "spreads", "totals")
        c, n = consensus_game(r, lines) if game else consensus_prop(r, props)
        book = r.q_first if r.two_way else imp(r.price_first)
        note = NEWS.get(r.player_name, "")
        if c is None:
            if game:
                p, tag, reason = float(np.clip(book, 0.02, 0.98)), "no_view", ""
            else:
                p = float(np.clip(book - 0.01, 0.02, 0.98))
                tag = "usage_trend"
                reason = f"No other book on this {MK.get(r.market_key, r.market_key)} line; props-Under prior only."
        else:
            extra = []
            if r.market_key == "h2h":
                kh = kalshi_home(r, KAL)
                if kh is not None:
                    c = (c * n + kh * 2) / (n + 2)
                    extra.append(f"Kalshi {kh:.2f}")
            p = c - (0.005 if (not game and r.two_way) else 0.0)
            wx = weather(r, WX)
            wind_mk = ("totals", "player_pass_yds", "player_pass_tds",
                        "player_reception_yds", "player_receptions",
                        "player_pass_completions")
            if wx and r.market_key in wind_mk and (wx[0] >= 15 or wx[1] >= 60):
                shade = ((0.02 if wx[0] >= 15 else 0.0)
                         + (0.02 if wx[0] >= 20 else 0.0)
                         + (0.01 if wx[1] >= 60 else 0.0))
                p -= shade
                extra.append(f"wind {wx[0]:.0f} mph/rain {wx[1]:.0f}% Under shade")
            lm = line_move(r, HIST) if game else None
            if lm is not None and lm[0] != lm[1]:
                extra.append(f"HR opened {lm[0]:+g}, now {lm[1]:+g}"
                             if r.market_key != "totals"
                             else f"HR total {lm[0]:g}->{lm[1]:g}")
            p = float(np.clip(p, 0.02, 0.98))
            tag = ("weather" if any(e.startswith("wind") for e in extra)
                   else ("line_move" if lm is not None and lm[0] != lm[1] and game
                         else "price_vs_sharp"))
            side_first = p > book
            sname = ((r.first_side if side_first else r.second_side) if r.two_way
                     else ("Yes" if side_first else "pass"))
            reason = (f"{n} books (Pin x3) {c:.3f} vs HR {book:.3f}"
                      + ("; " + "; ".join(extra) if extra else "")
                      + f"; take {sname}.")
        if note:
            reason = (reason + " " + note)[:160]
            tag = "injury_news" if tag != "no_view" else tag
            if "Questionable" in note and not game and r.two_way:
                p = float(np.clip(p - 0.01, 0.02, 0.98))
        edge = abs(p - book)
        no_bet = (not r.two_way) and p <= book
        if tag == "no_view" or no_bet:
            conf = 0.0
        else:
            conf = min(95.0, round(
                (edge * 500 + min(n, 9) * 1.0 + (0 if c is not None else -3))
                * min(1.0, n / 5), 1))
            conf = max(conf, 1.0)
        out.append({"event_id": r.event_id, "market_key": r.market_key,
                     "player_name": r.player_name, "line": r.line,
                     "p_first": round(p, 4), "tag": tag, "reason": reason,
                     "conf": conf, "_edge": edge, "_kick": r.commence_time})
    o = pd.DataFrame(out)
    o = o.sort_values(["conf", "_edge", "_kick"],
                      ascending=[False, False, True]).reset_index(drop=True)
    o["conf_rank"] = np.arange(1, len(o) + 1)
    return o


def main():
    ap = argparse.ArgumentParser(description="reader_v3: parameterised blind-opinion reader")
    ap.add_argument("sheet", help="path to the sheet CSV (from log_ai_opinions.py sheet)")
    ap.add_argument("output", help="path for the output CSV")
    ap.add_argument("--as-of", default=None,
                    help="UTC ISO timestamp; inputs are selected <= this time (default: now)")
    ap.add_argument("--injury-report", default=None,
                    help="path to official injury report CSV (absent -> no news layer)")
    ap.add_argument("--root", default=str(ROOT),
                    help="repo root (default: auto-detected)")
    args = ap.parse_args()

    root = Path(args.root)
    if args.as_of:
        as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=timezone.utc)
    else:
        as_of = datetime.now(timezone.utc)

    # Print own sha256
    own_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    print(f"reader_v3 sha256: {own_sha}")

    # Load sheet
    sheet = pd.read_csv(args.sheet)
    sheet["player_name"] = sheet["player_name"].fillna("")

    # Derive slate date from sheet's commence_time for the Kalshi prefix
    if not sheet.empty:
        first_kick = pd.to_datetime(sheet["commence_time"]).min()
        slate_date = first_kick.strftime("%Y-%m-%d")
        kalshi_prefix = _kalshi_prefix(slate_date)
    else:
        kalshi_prefix = None

    # Load inputs bounded by as-of
    props, lines, KAL, WX, HIST, files_used = _load_inputs(as_of, root)

    # Load injury report
    NEWS = _load_news(args.injury_report)
    if args.injury_report:
        files_used["injury_report"] = args.injury_report

    # Print input provenance
    print(f"as-of: {as_of.isoformat()}")
    print(f"kalshi prefix: {kalshi_prefix}")
    if NEWS:
        print(f"injury report: {len(NEWS)} players")
    else:
        print("injury report: none (no injury report)")
    for k, v in sorted(files_used.items()):
        print(f"  input {k}: {v}")
    print(f"props rows: {len(props)}")
    print(f"lines rows: {len(lines)}")
    print(f"kalshi rows: {len(KAL)}")
    print(f"NWS rows: {len(WX)}")
    print(f"HR history rows: {len(HIST)}")

    # Run reader
    o = read_opinions(sheet, props, lines, KAL, WX, HIST, NEWS, kalshi_prefix)

    # Save
    o.drop(columns=["_edge", "_kick"]).to_csv(args.output, index=False)
    print(f"\n{len(o)} rows; {o.tag.value_counts().to_dict()} | top 10:")
    print(o.head(10)[["market_key", "player_name", "line", "p_first", "conf",
                       "reason"]].to_string())


if __name__ == "__main__":
    main()
