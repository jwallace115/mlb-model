#!/usr/bin/env python3
"""
Grade pick-ledger rows from official results via the event crosswalk.

Game-level markets (h2h/ML, spreads, totals) from crosswalked final score.
Props: UNRESOLVED in v1 (per-player stat derivation deferred to v2).
Push rule: point hit exactly → P.
VOID: only when official source marks game cancelled/postponed.

Grades are appended as rows (same pick_id, result, graded_utc, result_source),
never edits. sim_nfl and ai_nfl graded here like everyone else; the embargo
is on the page (Item 4), not here.

OPS2 Item 3.
"""
import hashlib, os, sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import picks_ledger as pl
import pick_sources as ps

ROOT = Path(os.environ.get("MLB_REPO_ROOT") or Path(__file__).resolve().parent.parent.parent)
LEDGER_DIR = Path(os.environ.get("PICKS_LEDGER_DIR") or "/root/private/ledger")

# ---- settlement definitions (P6) ----
# Spread: home_score - away_score vs point (from home perspective if side is home team,
#   from away perspective if side is away team). Push if margin == -point.
# Total: home_score + away_score vs point. Push if total == point.
# Moneyline: home wins → home side W, away side L. Tie → P (NFL has no ties in playoffs, rare in regular season).

# Rush attempts include kneels (book-faithful).


def _normalise_side(side, home, away):
    """Is this side the home team, away team, over, or under?"""
    s = str(side).strip().lower()
    if s in ("over", "o"):
        return "over"
    if s in ("under", "u"):
        return "under"
    # Team matching
    h = str(home).strip().lower()
    a = str(away).strip().lower()
    # Try exact
    if s == h or s in h:
        return "home"
    if s == a or s in a:
        return "away"
    # Try NFL normaliser
    sn = ps.nfl_team(side)
    hn = ps.nfl_team(home)
    an = ps.nfl_team(away)
    if sn and sn == hn:
        return "home"
    if sn and sn == an:
        return "away"
    # NCAAF
    if ps.ncaaf_same(side, home):
        return "home"
    if ps.ncaaf_same(side, away):
        return "away"
    return None


def _grade_game_market(market, side_type, point, home_score, away_score):
    """Grade a game-level market. Returns W/L/P or None."""
    hs, as_ = float(home_score), float(away_score)
    total = hs + as_

    if market == "spread":
        if side_type == "home":
            margin = hs - as_
        elif side_type == "away":
            margin = as_ - hs
        else:
            return None
        # point is from the bettor's perspective (e.g., -3.5 means they need to win by 4+)
        adjusted = margin + (point or 0)
        if adjusted > 0:
            return "W"
        elif adjusted < 0:
            return "L"
        else:
            return "P"

    elif market == "total":
        pt = float(point) if point is not None else None
        if pt is None:
            return None
        if side_type == "over":
            if total > pt:
                return "W"
            elif total < pt:
                return "L"
            else:
                return "P"
        elif side_type == "under":
            if total < pt:
                return "W"
            elif total > pt:
                return "L"
            else:
                return "P"
        return None

    elif market == "moneyline":
        if hs > as_:
            winner = "home"
        elif as_ > hs:
            winner = "away"
        else:
            return "P"  # tie
        return "W" if side_type == winner else "L"

    return None


def grade(ledger_dir):
    """Grade all ungraded ledger rows with results available. Returns list of grade rows to append."""
    ledger_dir = Path(ledger_dir)
    rows = pl._read_all(ledger_dir)
    if not rows:
        return []

    # Get current view (latest per pick_id)
    current = {r["pick_id"]: r for r in pl.view(ledger_dir)}

    # Load crosswalks
    crosswalks = {}
    for sport in ("nfl", "ncaaf", "nhl", "nba"):
        xw_path = ledger_dir / f"crosswalk_{sport}.parquet"
        if xw_path.exists():
            crosswalks[sport.upper()] = pd.read_parquet(xw_path)

    now = datetime.now(timezone.utc)
    grade_rows = []
    already_graded = {r["pick_id"] for r in rows if r.get("result")}

    for pid, row in current.items():
        # Skip already graded
        if row.get("result"):
            continue
        if pid in already_graded:
            continue

        # Skip future games
        try:
            ct = pl._parse_utc(row.get("commence_time"), "commence")
            if ct > now:
                continue
        except (ValueError, TypeError):
            continue

        sport = row.get("sport", "").upper()
        xw = crosswalks.get(sport)
        if xw is None or xw.empty:
            continue

        eid = row.get("event_id")
        match = xw[xw.event_id == eid]
        if match.empty:
            continue  # not in crosswalk → UNRESOLVED

        game = match.iloc[0]
        if not game.completed:
            continue  # game not finished

        hs = game.home_score
        as_ = game.away_score
        if pd.isna(hs) or pd.isna(as_):
            continue

        market = row.get("market", "")
        if market and "prop" in market:
            continue  # props UNRESOLVED in v1

        side_type = _normalise_side(row.get("side"), game.home_team, game.away_team)
        if side_type is None:
            continue  # can't determine side

        result = _grade_game_market(market, side_type, row.get("point"), hs, as_)
        if result is None:
            continue

        # Build grade row
        xw_path = ledger_dir / f"crosswalk_{sport.lower()}.parquet"
        xw_sha = hashlib.sha256(xw_path.read_bytes()).hexdigest()[:12] if xw_path.exists() else "?"

        grade_row = dict(row)  # copy all fields
        grade_row["result"] = result
        grade_row["graded_utc"] = now.isoformat()
        grade_row["result_source"] = f"crosswalk_{sport.lower()}.parquet@{xw_sha}"
        grade_row["ingested_utc"] = now.isoformat()
        grade_rows.append(grade_row)

    return grade_rows


def main():
    if not LEDGER_DIR.exists():
        print(f"HALT: PICKS_LEDGER_DIR={LEDGER_DIR} does not exist")
        sys.exit(1)

    # Check: if a sport has ungraded past-commence picks but no crosswalk, exit non-zero
    rows = pl._read_all(LEDGER_DIR)
    now = datetime.now(timezone.utc)
    graded_pids = {r["pick_id"] for r in rows if r.get("result")}
    current = {r["pick_id"]: r for r in pl.view(LEDGER_DIR)}
    sports_needing_xw = set()
    for pid, row in current.items():
        if row.get("result") or pid in graded_pids:
            continue
        market = row.get("market", "")
        if market and "prop" in market:
            continue
        try:
            ct = pl._parse_utc(row.get("commence_time"), "commence")
            if ct < now:
                sports_needing_xw.add(row.get("sport", "").upper())
        except (ValueError, TypeError):
            continue
    missing_xw = []
    for sport in sports_needing_xw:
        xw_path = LEDGER_DIR / f"crosswalk_{sport.lower()}.parquet"
        if not xw_path.exists():
            missing_xw.append(sport)
    if missing_xw:
        print(f"HALT: sports with ungraded past-commence picks but no crosswalk: {sorted(missing_xw)}")
        sys.exit(1)

    graded = grade(LEDGER_DIR)
    if graded:
        appended, skipped = pl.append(graded, LEDGER_DIR)
        print(f"graded: {len(graded)}, appended: {appended}, skipped: {skipped}")

        # Summary by owner × sport × result
        df = pd.DataFrame(graded)
        print("\nresults by owner × sport:")
        print(df.groupby(["owner", "sport", "result"]).size().to_string())
    else:
        print("nothing to grade (no new results available)")


if __name__ == "__main__":
    main()
