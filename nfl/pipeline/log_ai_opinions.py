#!/usr/bin/env python3
"""The blind opinion log: the reader's probability on EVERY line Hard Rock quotes, frozen pre-kick.

Jeff, 2026-09-21: "grade every single line the hard rock gives against our reasoning... pick a side,
save it to a file, then we'll grade them." He does not look at it. A card, when he asks for one, is
drawn from this log (largest gap to the book, distinct ideas per N58) - the log is never drawn from
a card.

Three steps, all offline (zero API credits; each runs in seconds):
  sheet   the newest pre-kick Hard Rock props pull + game-line snapshot -> one row per quoted line,
          with both prices and the book's de-vigged probability of the FIRST side.
          FIRST side = Over (props, totals) / Yes (anytime TD) / Home team (spreads, h2h).
  freeze  the reader's filled sheet (p_first, tag, reason per line) -> validated, stamped, written
          append-only with a sha256 in the manifest. Refuses: a line with no opinion, a line not in
          the sheet, a game that has kicked off, an existing output file.
  verify  recompute every manifest hash (an edited file fails).

PRE-REGISTERED scoring (written 2026-09-21 before any opinion existed; score step is a later build
and must implement exactly this):
  * Only revision 0 of a line is scored. Later revisions are kept and reported, never scored.
  * Files frozen with --pilot are never pooled into the record.
  * Two-way lines: Brier and log-loss of p_first vs the book's de-vigged q_first, game-cluster
    bootstrap. One-way lines (anytime TD): vs the vig-inclusive implied price, reported separately.
  * Sides: hit rate AND units at the real Hard Rock price of the side taken (flat -110 is not used).
  * Breakouts: by market, by tag, by |p - q| bucket (<0.03, 0.03-0.08, >0.08), by week, by game.
  * tag 'no_view' rows carry p_first = q_first and take no side; their share is reported every week.
  * P1: Brier(book) <= Brier(reader) on two-way lines. P2: the reader's sides with |p-q| > 0.08 lose
    units at real prices. Both expected to HOLD; the log exists to find where, if anywhere, they fail.

Usage:
  python3 nfl/pipeline/log_ai_opinions.py sheet  --week 2 --out _cowork_patches/ai_sheet.csv
  python3 nfl/pipeline/log_ai_opinions.py freeze --week 2 --filled _cowork_patches/ai_filled.csv [--pilot]
  (freeze re-reads the tape itself; add --props-file/--lines-file for a manual pull, --events "Rams")
  python3 nfl/pipeline/log_ai_opinions.py verify --week 2
"""
import argparse, hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BOOK = "hardrockbet_fl"
PROPS_DIR = ROOT / "data" / "odds_archive" / "nfl" / "props"
LINES_DIR = ROOT / "data" / "odds_archive" / "nfl" / "line_history"
TAGS = ("injury_news", "role_change", "game_script", "matchup", "weather", "price_vs_sharp",
        "usage_trend", "line_move", "no_view")
KEY = ["event_id", "market_key", "player_name", "line"]
P_MIN, P_MAX = 0.02, 0.98
REASON_MIN, REASON_MAX = 12, 160
NO_VIEW_TOL = 0.005
GAME_MARKETS = ("h2h", "spreads", "totals")


def implied(american):
    a = float(american)
    return 100.0 / (a + 100.0) if a > 0 else -a / (-a + 100.0)


def parse_utc(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def out_dir(season, week):
    return ROOT / "nfl" / "data" / "board" / f"week={season}_{week:02d}" / "ai_opinions"


def _finish(rows, now):
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["imp_first"] = df["price_first"].map(implied)
    df["imp_second"] = df["price_second"].map(lambda x: implied(x) if pd.notna(x) else np.nan)
    df["two_way"] = df["price_second"].notna()
    df["q_first"] = np.where(df["two_way"], df["imp_first"] / (df["imp_first"] + df["imp_second"]), np.nan)
    df["source_age_min"] = df["source_utc"].map(lambda s: round((now - parse_utc(s)).total_seconds() / 60, 1))
    df["player_name"] = df["player_name"].fillna("")
    df["line"] = df["line"].astype(float)
    dup = df.duplicated(KEY, keep=False)
    if dup.any():
        raise SystemExit(f"HALT: duplicate line keys in the pull: {df.loc[dup, KEY].values.tolist()[:5]}")
    return df.sort_values(["commence_time", "event_id", "market_key", "player_name", "line"]).reset_index(drop=True)


def build_sheet(props, lines, now):
    """props: rows of ONE pull per event (the newest); lines: rows of ONE snapshot. Pre-kick only."""
    rows = []
    p = props[(props["bookmaker"] == BOOK) & (props["commence_time"].map(parse_utc) > now)]
    for _, r in p.iterrows():
        if pd.isna(r["over_price"]):
            continue                      # an under-only quote has no first side to price
        rows.append({"event_id": r["event_id"], "commence_time": r["commence_time"],
                     "home_team": r["home_team"], "away_team": r["away_team"],
                     "market_key": r["market_key"], "player_name": r["player_name"],
                     "line": 0.5 if pd.isna(r["line"]) else r["line"],
                     "first_side": "Over", "second_side": "Under",
                     "price_first": r["over_price"], "price_second": r["under_price"],
                     "source_utc": r["pull_timestamp"]})
    g = lines[(lines["bookmaker"] == BOOK) & (lines["market"].isin(GAME_MARKETS))
              & (lines["commence_time"].map(parse_utc) > now)]
    for (eid, mk), s in g.groupby(["event_id", "market"]):
        h = s.iloc[0]
        first = "Over" if mk == "totals" else h["home_team"]
        a = s[s["outcome_name"] == first]
        b = s[s["outcome_name"] != first]
        if len(a) != 1 or len(b) != 1:
            raise SystemExit(f"HALT: {mk} for {h['away_team']} @ {h['home_team']} is not a two-outcome market")
        a, b = a.iloc[0], b.iloc[0]
        rows.append({"event_id": eid, "commence_time": h["commence_time"], "home_team": h["home_team"],
                     "away_team": h["away_team"], "market_key": mk, "player_name": "",
                     "line": 0.0 if pd.isna(a["point"]) else a["point"],
                     "first_side": first, "second_side": b["outcome_name"],
                     "price_first": a["price"], "price_second": b["price"],
                     "source_utc": h["snapshot_utc"]})
    return _finish(rows, now)


def newest_inputs(season, now, props_file=None, lines_file=None):
    """Newest pre-kick Hard Rock pull per event + the newest game-line snapshot, read from the tape.
    props_file / lines_file: a manual pull that has not reached the archive yet (_cowork_patches/)."""
    pf = [Path(props_file)] if props_file else sorted((PROPS_DIR / f"season={season}").glob("month=*/data_*.parquet"))[-2:]
    if not pf:
        raise SystemExit("HALT: no props archive for the season")
    props = pd.concat([pd.read_parquet(f) for f in pf], ignore_index=True)
    props = props[props["bookmaker"] == BOOK]
    props = props[props["pull_timestamp"].map(parse_utc) < props["commence_time"].map(parse_utc)]
    newest = props.groupby("event_id")["pull_timestamp"].transform("max")
    props = props[props["pull_timestamp"] == newest]
    lf = [Path(lines_file)] if lines_file else sorted((LINES_DIR / f"season={season}").glob("snap_*.parquet"))[-1:]
    if not lf:
        raise SystemExit("HALT: no game-line snapshots for the season")
    lines = pd.read_parquet(lf[0])
    return props, lines[lines["snapshot_utc"] == lines["snapshot_utc"].max()]


def validate(sheet, filled):
    """Returns the frozen frame (no stamps yet). Raises SystemExit on any breach."""
    f = filled.copy()
    f["player_name"] = f["player_name"].fillna("")
    f["line"] = f["line"].astype(float)
    need = set(KEY) | {"p_first", "tag", "reason"}
    if need - set(f.columns):
        raise SystemExit(f"HALT: filled sheet is missing columns {sorted(need - set(f.columns))}")
    if f.duplicated(KEY).any():
        raise SystemExit("HALT: filled sheet has duplicate lines")
    m = sheet.merge(f[KEY + ["p_first", "tag", "reason"]], on=KEY, how="outer", indicator=True)
    missing = m[m["_merge"] == "left_only"]
    extra = m[m["_merge"] == "right_only"]
    if len(missing):
        raise SystemExit(f"HALT: {len(missing)} quoted lines have no opinion, e.g. {missing[KEY].values.tolist()[:3]}")
    if len(extra):
        raise SystemExit(f"HALT: {len(extra)} opinions are on lines the book did not quote, e.g. {extra[KEY].values.tolist()[:3]}")
    m = m.drop(columns="_merge")
    if m["p_first"].isna().any() or not m["p_first"].between(P_MIN, P_MAX).all():
        raise SystemExit(f"HALT: p_first must be a number in [{P_MIN}, {P_MAX}] on every line")
    bad = sorted(set(m["tag"]) - set(TAGS))
    if bad:
        raise SystemExit(f"HALT: unknown tag(s) {bad}; allowed {TAGS}")
    book = m["q_first"].where(m["two_way"], m["imp_first"])
    nv = m["tag"] == "no_view"
    if ((m["p_first"] - book).abs()[nv] > NO_VIEW_TOL).any():
        raise SystemExit("HALT: a 'no_view' line must carry the book's own probability")
    rl = m["reason"].fillna("").str.len()
    if (~nv & ~rl.between(REASON_MIN, REASON_MAX)).any():
        raise SystemExit(f"HALT: every line with a view needs a reason of {REASON_MIN}-{REASON_MAX} characters")
    m["book_p_first"] = book
    m["gap"] = m["p_first"] - book
    # the side the reader would take; a one-way market has no second side to take
    m["side"] = np.where(nv, "none", np.where(m["gap"] > 0, "first",
                         np.where(m["two_way"], "second", "none")))
    m["side_name"] = np.where(m["side"] == "first", m["first_side"],
                              np.where(m["side"] == "second", m["second_side"], ""))
    m["side_price"] = np.where(m["side"] == "first", m["price_first"],
                               np.where(m["side"] == "second", m["price_second"], np.nan))
    return m


def prior_revisions(d):
    seen = {}
    for f in sorted(d.glob("ai_opinions_*.parquet")):
        for *k, rev in pd.read_parquet(f)[KEY + ["revision"]].itertuples(index=False, name=None):
            seen[tuple(k)] = max(seen.get(tuple(k), -1), int(rev))
    return seen


def freeze(sheet, filled, season, week, pilot, now, d=None):
    """sheet MUST come from build_sheet() in this process: prices are read from the tape at freeze
    time, never from a CSV the reader could have touched."""
    d = d or out_dir(season, week)
    late = sheet[sheet["commence_time"].map(parse_utc) <= now]
    if len(late):
        raise SystemExit(f"HALT: {late['event_id'].nunique()} game(s) in the sheet have kicked off - nothing is frozen")
    m = validate(sheet, filled)
    d.mkdir(parents=True, exist_ok=True)
    seen = prior_revisions(d)
    m["revision"] = [seen.get((r.event_id, r.market_key, r.player_name, r.line), -1) + 1
                     for r in m.itertuples(index=False)]
    m["season"], m["week"], m["pilot"] = season, week, bool(pilot)
    m["logged_utc"] = now.isoformat()
    dest = d / f"ai_opinions_{now.strftime('%Y%m%dT%H%M%SZ')}.parquet"
    if dest.exists():
        raise SystemExit(f"HALT: {dest.name} exists - the log is append-only")
    m.to_parquet(dest, index=False)
    sha = hashlib.sha256(dest.read_bytes()).hexdigest()
    man = d / "manifest.json"
    entries = json.loads(man.read_text()) if man.exists() else []
    entries.append({"file": dest.name, "sha256": sha, "logged_utc": now.isoformat(), "rows": len(m),
                    "pilot": bool(pilot), "games": int(m["event_id"].nunique()),
                    "no_view_share": round(float((m["tag"] == "no_view").mean()), 3),
                    "revised_rows": int((m["revision"] > 0).sum()),
                    "oldest_source_age_min": float(m["source_age_min"].max()),
                    "first_kickoff_utc": str(m["commence_time"].min())})
    man.write_text(json.dumps(entries, indent=1) + "\n")
    return dest, sha, m


def verify(season, week, d=None):
    d = d or out_dir(season, week)
    man = d / "manifest.json"
    entries = json.loads(man.read_text()) if man.exists() else []
    bad = [e["file"] for e in entries
           if not (d / e["file"]).exists() or hashlib.sha256((d / e["file"]).read_bytes()).hexdigest() != e["sha256"]]
    unlisted = sorted({f.name for f in d.glob("ai_opinions_*.parquet")} - {e["file"] for e in entries})
    return entries, bad, unlisted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sheet", "freeze", "verify"])
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--out"), ap.add_argument("--filled")
    ap.add_argument("--props-file"), ap.add_argument("--lines-file")
    ap.add_argument("--events", help="comma list of team-name fragments; default every pre-kick game")
    ap.add_argument("--window-hours", type=float, help="only games kicking off within this many hours")
    ap.add_argument("--pilot", action="store_true")
    a = ap.parse_args()
    now = datetime.now(timezone.utc)
    if a.cmd in ("sheet", "freeze"):
        sheet = build_sheet(*newest_inputs(a.season, now, a.props_file, a.lines_file), now)
        if a.events and len(sheet):
            fr = [x.strip().lower() for x in a.events.split(",")]
            sheet = sheet[(sheet.home_team + " " + sheet.away_team).str.lower().map(lambda t: any(x in t for x in fr))]
        if a.window_hours and len(sheet):
            hrs = sheet["commence_time"].map(lambda c: (parse_utc(c) - now).total_seconds() / 3600)
            sheet = sheet[hrs <= a.window_hours]
        if sheet.empty:
            sys.exit("HALT: no pre-kick Hard Rock lines found")
    if a.cmd == "sheet":
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        sheet.to_csv(a.out, index=False)
        print(f"{len(sheet)} lines, {sheet.event_id.nunique()} game(s), two-way {int(sheet.two_way.sum())} -> {a.out}")
        print(sheet.groupby(["away_team", "home_team"])["source_age_min"].agg(["count", "min", "max"]).to_string())
    elif a.cmd == "freeze":
        dest, sha, m = freeze(sheet, pd.read_csv(a.filled), a.season, a.week, a.pilot, now)
        print(f"FROZEN {len(m)} lines -> {dest.relative_to(ROOT)}\nsha256 {sha}\n"
              f"pilot={a.pilot} no_view={(m.tag == 'no_view').mean():.1%} oldest source {m.source_age_min.max()} min")
    else:
        entries, bad, unlisted = verify(a.season, a.week)
        print(f"{len(entries)} frozen file(s); hash mismatch/missing: {bad or 'none'}; not in manifest: {unlisted or 'none'}")
        if bad or unlisted:
            sys.exit(1)


if __name__ == "__main__":
    main()
