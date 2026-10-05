#!/usr/bin/env python3
"""
Adapt every logged pick source onto the picks_ledger contract and append.

Sources:
  1. OPS1 pick_sources.SOURCES (NCAAF + NFL cards, tickets, placements, AI opinions)
  2. nfl/data/board/week=*/ai_opinions/ai_opinions_*.parquet (only rows with side set = a pick)
  3. site/tickets/*.json (zero files today → report, not HALT)

Rows without event_id resolve from the odds tape: snapshots in [commence−7d, commence],
normalised teams, |snapshot commence − leg commence| ≤ 6h → exactly ONE event_id, else HALT.

OPS2 Item 1.
"""
import glob, json, os, re, sys, time as _time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pick_sources as ps
import picks_ledger as pl
import ticket_id as tk

ROOT = Path(os.environ.get("MLB_REPO_ROOT") or Path(__file__).resolve().parent.parent.parent)
LEDGER_DIR = Path(os.environ.get("PICKS_LEDGER_DIR") or "/root/private/ledger")

# ---- owner map for pick_sources source files ----
# P1 decision: one owner per source kind/lane
OWNER_MAP = {
    # NCAAF
    ("ncaaf", "card"): "ai_ncaaf",
    ("ncaaf", "game_view"): "ai_ncaaf",
    ("ncaaf", "ai_opinion"): "ai_ncaaf",
    ("ncaaf", "placement"): "jeff",
    # NFL
    ("nfl", "slate_rule"): "ai_nfl",
    ("nfl", "slate_final"): "ai_nfl",
    ("nfl", "game_ticket_ai"): "ai_nfl",
    ("nfl", "game_ticket_ai_opinion"): "ai_nfl",
    ("nfl", "card"): "ai_nfl",
    ("nfl", "sgp_card"): "ai_nfl",
    ("nfl", "placement"): "jeff",
}

# ---- source map ----
SOURCE_MAP = {
    "card": "ticket_card",
    "game_view": "ai_opinion",
    "ai_opinion": "ai_opinion",
    "placement": "jeff_manual",
    "slate_rule": "ai_opinion",
    "slate_final": "ai_opinion",
    "game_ticket_ai": "ticket_card",
    "game_ticket_ai_opinion": "ai_opinion",
    "sgp_card": "ticket_card",
}


def _tape_events(sport_folder, season=2026):
    """Load unique (event_id, home, away, commence) from tape snapshots."""
    tape_dir = ROOT / "data" / "odds_archive" / sport_folder / "line_history" / f"season={season}"
    if not tape_dir.exists():
        return pd.DataFrame(columns=["event_id", "home_team", "away_team", "commence_time", "snap_commence"])
    frames = []
    for f in sorted(tape_dir.glob("snap_*.parquet")):
        try:
            df = pd.read_parquet(f, columns=["event_id", "home_team", "away_team", "commence_time"])
            frames.append(df)
        except Exception:
            continue
    if not frames:
        return pd.DataFrame(columns=["event_id", "home_team", "away_team", "commence_time", "snap_commence"])
    df = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["event_id", "commence_time"])
    df["snap_commence"] = pd.to_datetime(df["commence_time"], utc=True, errors="coerce")
    return df


# cache loaded tapes
_tape_cache = {}


def _get_tape(sport_folder):
    if sport_folder not in _tape_cache:
        _tape_cache[sport_folder] = _tape_events(sport_folder)
    return _tape_cache[sport_folder]


def _normalise_team(name, league):
    """Normalise a team name for matching against the tape."""
    if not name:
        return ""
    name = str(name).strip()
    if league == "NFL":
        n = ps.nfl_team(name)
        return n if n else name.lower()
    # NCAAF: use ncaaf_norm tokens joined
    return " ".join(ps.ncaaf_norm(name))


def _resolve_event_id(home, away, commence_utc, league, sport_folder):
    """Resolve event_id from the tape. Returns (event_id, commence_from_tape) or raises Halt."""
    tape = _get_tape(sport_folder)
    if tape.empty:
        raise pl.Halt(f"no tape for {sport_folder}; cannot resolve event_id for {away} @ {home}")

    if commence_utc is None or pd.isna(commence_utc):
        raise pl.Halt(f"no commence_time for {away} @ {home}; cannot resolve event_id")

    ct = pd.to_datetime(str(commence_utc), utc=True)
    window_start = ct - timedelta(days=7)
    window_end = ct

    candidates = tape[(tape.snap_commence >= window_start) & (tape.snap_commence <= window_end + timedelta(hours=6))]

    # normalise for matching
    hn = _normalise_team(home, league)
    an = _normalise_team(away, league)

    matches = []
    for _, row in candidates.iterrows():
        rhn = _normalise_team(row.home_team, league)
        ran = _normalise_team(row.away_team, league)

        if league == "NCAAF":
            home_match = ps.ncaaf_same(home, row.home_team) or ps.ncaaf_same(home, row.away_team)
            away_match = ps.ncaaf_same(away, row.away_team) or ps.ncaaf_same(away, row.home_team)
            team_match = home_match and away_match
        else:
            team_match = (hn == rhn and an == ran) or (hn == ran and an == rhn)

        if not team_match:
            continue

        # |snapshot commence − leg commence| ≤ 6h
        delta = abs((row.snap_commence - ct).total_seconds()) / 3600
        if delta <= 6:
            matches.append(row)

    if not matches:
        raise pl.Halt(f"no tape match for {away} @ {home} commence={commence_utc} in {sport_folder}")

    eids = {r.event_id for r in matches}
    if len(eids) > 1:
        raise pl.Halt(f"multiple event_ids for {away} @ {home}: {eids}")

    # Take commence_time from the LATEST matching snapshot
    best = max(matches, key=lambda r: r.snap_commence)
    return matches[0].event_id, str(best.snap_commence)


def _extract_event_id_from_raw(raw_str):
    """Try to extract event_id from the raw JSON column."""
    try:
        d = json.loads(raw_str) if isinstance(raw_str, str) else raw_str
        eid = d.get("event_id")
        if eid and re.fullmatch(r"[0-9a-f]{32}", str(eid)):
            return str(eid)
    except (json.JSONDecodeError, TypeError, AttributeError):
        pass
    return None


def _extract_teams_from_raw(raw_str):
    """Try to extract home/away from raw JSON."""
    try:
        d = json.loads(raw_str) if isinstance(raw_str, str) else raw_str
        return d.get("home_team"), d.get("away_team")
    except (json.JSONDecodeError, TypeError, AttributeError):
        pass
    return None, None


def _sport_folder(league):
    return {"NFL": "nfl", "NCAAF": "ncaaf", "NHL": "nhl", "NBA": "nba", "MLB": "baseball_mlb"}.get(league)


def adapt_pick_sources(root=None):
    """Map OPS1 pick_sources rows to the picks_ledger contract."""
    root = Path(root or ROOT)
    os.environ.setdefault("MLB_REPO_ROOT", str(root))
    P, F = ps.load_picks(root)
    rows = []
    rejected = []

    for _, r in P.iterrows():
        kind = r.kind
        lane = r.lane
        league = r.league
        owner = OWNER_MAP.get((lane, kind))
        if owner is None:
            owner = f"ai_{lane}" if kind != "placement" else "jeff"
        source = SOURCE_MAP.get(kind, "ai_opinion")

        # Get event_id
        event_id = _extract_event_id_from_raw(r.raw)
        home, away = _extract_teams_from_raw(r.raw)

        # For AI opinions from parquet, re-read to get event_id
        if event_id is None and kind == "ai_opinion":
            # The parquet source has event_id but pick_sources doesn't carry it in raw
            # We need to resolve from the tape or re-read the parquet
            # Use tape resolution as fallback
            pass

        # For game_view, extract event_id from ticket_id (format: ncaaf_view_{event_id[:8]}_{build_time})
        if event_id is None and kind == "game_view" and r.ticket_id:
            # ticket_id format: ncaaf_view_{eid8}_{time} — not enough for 32 hex
            pass

        if event_id is None:
            # Resolve from tape
            sf = _sport_folder(league)
            if sf is None:
                rejected.append((r.source_file, r.ticket_id, "no_tape_folder", league))
                continue

            # Get home/away from game string or side
            if home is None or away is None:
                if r.game and "@" in str(r.game):
                    parts = ps.split_game(r.game)
                    if len(parts) == 2:
                        away, home = parts[0], parts[1]

            # For NCAAF spreads/ML, the side IS a team name
            if (home is None or away is None) and league == "NCAAF" and r.teams and len(r.teams) == 2:
                away, home = r.teams[0], r.teams[1]

            if home is None or away is None:
                # For placement legs with game like "Navy @ UAB"
                if r.game:
                    parts = ps.split_game(r.game)
                    if len(parts) == 2:
                        away, home = parts[0], parts[1]

            if home is None or away is None:
                rejected.append((r.source_file, r.ticket_id, "no_home_away", str(r.game)))
                continue

            commence = r.commence_utc
            if pd.isna(commence):
                rejected.append((r.source_file, r.ticket_id, "no_commence", str(r.game)))
                continue

            # Check logged < commence BEFORE resolving
            logged = r.build_time
            if not pd.isna(logged) and not pd.isna(commence) and logged >= commence:
                rejected.append((r.source_file, r.ticket_id, "logged_after_commence",
                                 f"logged={logged} >= commence={commence}"))
                continue

            try:
                event_id, tape_commence = _resolve_event_id(home, away, commence, league, sf)
            except pl.Halt as e:
                rejected.append((r.source_file, r.ticket_id, "tape_resolve_fail", str(e)))
                continue
        else:
            tape_commence = None

        # Build the contract row
        logged_utc = str(r.build_time) if not pd.isna(r.build_time) else None
        commence_time = tape_commence or (str(r.commence_utc) if not pd.isna(r.commence_utc) else None)

        # Validate logged < commence
        if logged_utc and commence_time:
            try:
                l_dt = pl._parse_utc(logged_utc, "logged")
                c_dt = pl._parse_utc(commence_time, "commence")
                if l_dt >= c_dt:
                    rejected.append((r.source_file, r.ticket_id, "logged_after_commence",
                                     f"{logged_utc} >= {commence_time}"))
                    continue
            except (ValueError, TypeError):
                pass

        # Player name
        player_name = r.subject if r.subject and r.market and "prop" in str(r.market) else None

        # Side normalisation
        side = str(r.side).strip() if r.side else ""

        # Price
        price = None
        if r.price is not None and not (isinstance(r.price, float) and pd.isna(r.price)):
            try:
                price = int(float(r.price))
                if price == 0:
                    price = None
            except (ValueError, TypeError):
                pass

        # Reason: carry conf/conf_rank for AI opinions
        reason = str(r.reason)[:200] if r.reason and not pd.isna(r.reason) else None

        # Market
        market = r.market

        row = {
            "ticket_id": r.ticket_id,
            "owner": owner,
            "source": source,
            "logged_utc": logged_utc,
            "sport": league,
            "event_id": event_id,
            "commence_time": commence_time,
            "home": home or "",
            "away": away or "",
            "market": market,
            "player_id": None,
            "player_name": player_name,
            "side": side,
            "point": float(r.point) if r.point is not None and not (isinstance(r.point, float) and pd.isna(r.point)) else None,
            "price_american": price,
            "book": r.book if r.book and not (isinstance(r.book, float) and pd.isna(r.book)) else None,
            "reason": reason,
            "share_link": None,
            "supersedes": None,
            "result": None,
            "graded_utc": None,
            "result_source": None,
            "source_file": r.source_file,
            "source_row": int(r.name) if hasattr(r, 'name') else None,
        }
        rows.append(row)

    return rows, rejected, F


def adapt_nfl_ai_opinions(root=None):
    """Read NFL AI opinion parquets: only rows where side is set (= a pick)."""
    root = Path(root or ROOT)
    pattern = str(root / "nfl" / "data" / "board" / "week=*" / "ai_opinions" / "ai_opinions_*.parquet")
    files = sorted(glob.glob(pattern))
    rows = []
    rejected = []

    for f in files:
        try:
            df = pd.read_parquet(f)
        except Exception as e:
            raise pl.Halt(f"cannot parse {f}: {e}")

        picks = df[df.side.isin(["first", "second"])]
        rel = str(Path(f).relative_to(root))

        for idx, r in picks.iterrows():
            event_id = str(r.event_id) if r.event_id else None
            if event_id and not re.fullmatch(r"[0-9a-f]{32}", event_id):
                event_id = None

            logged_utc = str(r.logged_utc) if r.logged_utc else None
            commence_time = str(r.commence_time) if r.commence_time else None

            # Check logged < commence
            if logged_utc and commence_time:
                try:
                    l_dt = pl._parse_utc(logged_utc, "logged")
                    c_dt = pl._parse_utc(commence_time, "commence")
                    if l_dt >= c_dt:
                        rejected.append((rel, str(r.event_id), "logged_after_commence",
                                         f"{logged_utc} >= {commence_time}"))
                        continue
                except (ValueError, TypeError):
                    pass

            if event_id is None:
                # Resolve from tape
                try:
                    event_id, tape_commence = _resolve_event_id(
                        r.home_team, r.away_team, r.commence_time, "NFL", "nfl")
                    if tape_commence:
                        commence_time = tape_commence
                except pl.Halt as e:
                    rejected.append((rel, str(r.get("event_id", "?")), "tape_resolve_fail", str(e)))
                    continue

            # Build ticket_id
            tid = tk.make_ticket_id("nfl", str(r.get("week", "?")),
                                     "ai_opinion", logged_utc)

            # Reason: conf + conf_rank
            reason = None
            parts = []
            if r.get("reason") and str(r.reason) != "nan":
                parts.append(str(r.reason)[:150])
            if r.get("conf") and str(r.conf) != "nan":
                parts.append(f"conf={r.conf}")
            if r.get("conf_rank") and str(r.conf_rank) != "nan":
                parts.append(f"rank={r.conf_rank}")
            if parts:
                reason = "; ".join(parts)

            price = None
            sp = r.get("side_price")
            if sp is not None and not (isinstance(sp, float) and pd.isna(sp)):
                try:
                    price = int(float(sp))
                    if price == 0:
                        price = None
                except (ValueError, TypeError):
                    pass

            # Market
            mk = ps.odds_market(r.market_key)

            # Player name for props
            pn = r.get("player_name")
            player_name = str(pn) if pn and str(pn) != "nan" else None

            row = {
                "ticket_id": tid,
                "owner": "ai_nfl",
                "source": "ai_opinion",
                "logged_utc": logged_utc,
                "sport": "NFL",
                "event_id": event_id,
                "commence_time": commence_time,
                "home": str(r.home_team),
                "away": str(r.away_team),
                "market": mk,
                "player_id": None,
                "player_name": player_name,
                "side": str(r.side_name),
                "point": float(r.line) if r.line is not None and not (isinstance(r.line, float) and pd.isna(r.line)) else None,
                "price_american": price,
                "book": str(r.book) if r.get("book") and str(r.get("book")) != "nan" else None,
                "reason": reason,
                "share_link": None,
                "supersedes": None,
                "result": None,
                "graded_utc": None,
                "result_source": None,
                "source_file": rel,
                "source_row": int(idx),
            }
            rows.append(row)

    return rows, rejected, len(files)


def adapt_site_tickets(root=None):
    """Read site/tickets/*.json — zero files today = report, not HALT."""
    root = Path(root or ROOT)
    tdir = root / "site" / "tickets"
    files = sorted(tdir.glob("*.json")) if tdir.exists() else []
    rows = []
    rejected = []

    for f in files:
        try:
            d = json.loads(f.read_text())
        except Exception as e:
            raise pl.Halt(f"cannot parse {f}: {e}")

        logged_utc = d.get("logged_utc")
        rel = str(f.relative_to(root))

        for i, leg in enumerate(d.get("legs", [])):
            # These are display-only cards; they don't carry event_id
            # Skip for now — they're already in pick_sources via the ticket parsers
            pass

    return rows, rejected, len(files)


def main():
    if not LEDGER_DIR.exists():
        print(f"HALT: PICKS_LEDGER_DIR={LEDGER_DIR} does not exist")
        sys.exit(1)

    members = pl.load_members(LEDGER_DIR)
    all_rows = []
    all_rejected = []

    # Source 1: OPS1 pick_sources
    t0 = _time.time()
    ps_rows, ps_rejected, ps_files = adapt_pick_sources()
    t_ps = _time.time() - t0
    all_rows.extend(ps_rows)
    all_rejected.extend(ps_rejected)
    print(f"pick_sources: {len(ps_rows)} rows adapted, {len(ps_rejected)} rejected in {t_ps:.1f}s")

    # Source 2: NFL AI opinions
    t0 = _time.time()
    nfl_rows, nfl_rejected, nfl_files = adapt_nfl_ai_opinions()
    t_nfl = _time.time() - t0
    all_rows.extend(nfl_rows)
    all_rejected.extend(nfl_rejected)
    print(f"nfl_ai_opinions: {len(nfl_rows)} rows from {nfl_files} files, {len(nfl_rejected)} rejected in {t_nfl:.1f}s")

    # Source 3: site/tickets
    t0 = _time.time()
    st_rows, st_rejected, st_files = adapt_site_tickets()
    t_st = _time.time() - t0
    all_rows.extend(st_rows)
    all_rejected.extend(st_rejected)
    print(f"site_tickets: {len(st_rows)} rows from {st_files} files in {t_st:.1f}s")

    # Filter: skip rows with null/blank required fields that would fail admit
    valid_rows = []
    for r in all_rows:
        if pl._is_blank(r.get("event_id")) or pl._is_blank(r.get("side")) or pl._is_blank(r.get("market")):
            all_rejected.append((r.get("source_file", "?"), r.get("ticket_id", "?"),
                                 "missing_required", f"event_id={r.get('event_id')}, side={r.get('side')}, market={r.get('market')}"))
            continue
        valid_rows.append(r)

    print(f"\ntotal: {len(valid_rows)} valid rows, {len(all_rejected)} rejected")

    # Compute pick_id for each row
    for r in valid_rows:
        r["pick_id"] = pl.make_pick_id(
            r["ticket_id"], r["owner"], r["source"], r["event_id"],
            r["market"], r.get("player_name"), r["side"], r.get("point"))

    # Admit
    try:
        pl.admit(valid_rows, members)
    except pl.Halt as e:
        print(f"\n{e}")
        sys.exit(1)

    # Append
    appended, skipped = pl.append(valid_rows, LEDGER_DIR)
    print(f"appended: {appended}, skipped (already present): {skipped}")

    # Report by owner × sport × source
    if valid_rows:
        df = pd.DataFrame(valid_rows)
        print("\nrows by owner × sport × source:")
        print(df.groupby(["owner", "sport", "source"]).size().to_string())

    # Report rejected by reason
    if all_rejected:
        print(f"\nrejected ({len(all_rejected)}) by reason:")
        from collections import Counter
        reasons = Counter(r[2] for r in all_rejected)
        for reason, n in reasons.most_common():
            print(f"  {reason}: {n}")

    # Report files read
    print(f"\nfiles read: {len(ps_files)} pick_source files, {nfl_files} NFL AI opinion files, {st_files} site ticket files")


if __name__ == "__main__":
    main()
