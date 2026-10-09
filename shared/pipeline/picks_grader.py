#!/usr/bin/env python3
"""
Grade pick-ledger rows from official results via the event crosswalk.

Game-level markets (h2h/ML, spreads, totals) from crosswalked final score.
Props (v2, P46): from nflverse weekly player stats; DNP = V (void).
Push rule: point hit exactly → P.
VOID: only when official source marks game cancelled/postponed.

Grades are appended as rows (same pick_id, result, graded_utc, result_source),
never edits. sim_nfl and ai_nfl graded here like everyone else; the embargo
is on the page (Item 4), not here.

OPS2 Item 3; OPS6 Item 2 (prop grading).
"""
import hashlib, json, os, re, sys
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

# ---- prop stat mapping (P46) ----
_PROP_STAT_MAP = {
    "prop:pass_yds": "passing_yards",
    "prop:pass_td":  "passing_tds",
    "prop:pass_att": "attempts",
    "prop:pass_cmp": "completions",
    "prop:int":      "passing_interceptions",
    "prop:rush_yds": "rushing_yards",
    "prop:rush_att": "carries",
    "prop:rec":      "receptions",
    "prop:rec_yds":  "receiving_yards",
    "prop:atd":      "_anytime_td",  # special: rushing_tds + receiving_tds >= 1
}

# ---- player name normalization (P46) ----
_NAME_SUFFIXES = re.compile(r'\b(jr|sr|ii|iii|iv)\b', re.I)

def _normalize_name(name):
    """Lowercase, strip periods and suffixes (Jr/Sr/II/III/IV), collapse spaces."""
    if not name:
        return ""
    s = str(name).lower().replace(".", "").strip()
    s = _NAME_SUFFIXES.sub("", s)
    return " ".join(s.split())


def _resolve_player_name(ledger_name, overrides):
    """Resolve a ledger player name to a normalized name, consulting overrides first."""
    if overrides and ledger_name in overrides:
        return _normalize_name(overrides[ledger_name])
    return _normalize_name(ledger_name)


def _load_name_overrides():
    """Load shared/pipeline/player_name_overrides.json if it exists."""
    p = Path(__file__).resolve().parent / "player_name_overrides.json"
    if p.exists():
        return json.loads(p.read_text())
    return {}


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


def _load_newest_player_stats(root):
    """Load the newest player_stats_2026_*.parquet from results_archive/nfl/."""
    results_dir = Path(os.environ.get("RESULTS_ARCHIVE_DIR") or (root / "data" / "results_archive"))
    stats_dir = results_dir / "nfl"
    if not stats_dir.exists():
        return None, None
    files = sorted(stats_dir.glob("player_stats_2026_*.parquet"))
    if not files:
        return None, None
    newest = files[-1]
    return pd.read_parquet(newest), newest.name


def _grade_prop(row, game, stats_df, overrides, unmatched_names):
    """Grade a prop market. Returns result (W/L/P/V) or None."""
    market = row.get("market", "")
    stat_col = _PROP_STAT_MAP.get(market)
    if stat_col is None:
        return None

    player_name = row.get("player_name")
    if not player_name:
        return None

    point = row.get("point")
    if point is None:
        return None

    side_type = _normalise_side(row.get("side"), game.home_team, game.away_team)
    if side_type not in ("over", "under"):
        return None

    # Find the game's week from the crosswalk
    week = game.get("week") if hasattr(game, "get") else getattr(game, "week", None)

    # Match player in stats
    resolved = _resolve_player_name(player_name, overrides)
    # Build index of normalized names → stats rows
    candidates = stats_df[stats_df.season == 2026].copy()
    if week is not None and not pd.isna(week):
        candidates = candidates[candidates.week == int(week)]

    # Filter by team: player must be on one of the two teams
    home_team = str(game.home_team)
    away_team = str(game.away_team)
    candidates = candidates[candidates.team.isin([home_team, away_team])]

    if candidates.empty:
        # No stats for this game/week at all — can't grade
        return None

    # Try name match
    candidates = candidates.copy()
    candidates["_norm"] = candidates.player_display_name.apply(_normalize_name)
    matched = candidates[candidates._norm == resolved]

    if len(matched) == 0:
        # DNP: completed game + player not in stats = void
        unmatched_names.add(player_name)
        return "V"
    if len(matched) > 1:
        # Multiple matches — ambiguous, skip
        return None

    stats_row = matched.iloc[0]

    # Get the stat value
    if stat_col == "_anytime_td":
        rushing_tds = float(stats_row.get("rushing_tds", 0) or 0)
        receiving_tds = float(stats_row.get("receiving_tds", 0) or 0)
        stat_val = rushing_tds + receiving_tds
        # ATD lines are 0.5: Over wins if scored >= 1 TD
        if stat_val >= 1:
            return "W" if side_type == "over" else "L"
        else:
            return "L" if side_type == "over" else "W"

    if stat_col not in stats_row.index:
        return None

    stat_val = float(stats_row[stat_col] or 0)
    pt = float(point)

    if side_type == "over":
        if stat_val > pt:
            return "W"
        elif stat_val < pt:
            return "L"
        else:
            return "P"
    else:  # under
        if stat_val < pt:
            return "W"
        elif stat_val > pt:
            return "L"
        else:
            return "P"


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

    # Load player stats for prop grading
    root = Path(os.environ.get("MLB_REPO_ROOT") or Path(__file__).resolve().parent.parent.parent)
    stats_df, stats_file = _load_newest_player_stats(root)
    overrides = _load_name_overrides()
    unmatched_names = set()

    # Load schedules for week lookup (needed for prop grading)
    schedules_df = _load_newest_schedules(root)

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
            # Prop grading (P46)
            if stats_df is None:
                continue  # no stats file available

            # Enrich game with week from schedules
            game_with_week = _enrich_game_week(game, schedules_df)

            result = _grade_prop(row, game_with_week, stats_df, overrides, unmatched_names)
            if result is None:
                continue

            grade_row = dict(row)
            grade_row["result"] = result
            grade_row["graded_utc"] = now.isoformat()
            grade_row["result_source"] = f"player_stats: {stats_file}"
            grade_row["ingested_utc"] = now.isoformat()
            grade_rows.append(grade_row)
            continue

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

    if unmatched_names:
        print(f"prop grading: {len(unmatched_names)} unmatched player names (DNP/void): {sorted(unmatched_names)}")

    return grade_rows


def _load_newest_schedules(root):
    """Load the newest schedules_2026_*.parquet for week lookup."""
    results_dir = Path(os.environ.get("RESULTS_ARCHIVE_DIR") or (root / "data" / "results_archive"))
    stats_dir = results_dir / "nfl"
    if not stats_dir.exists():
        return None
    files = sorted(stats_dir.glob("schedules_2026_*.parquet"))
    if not files:
        return None
    return pd.read_parquet(files[-1])


def _enrich_game_week(game, schedules_df):
    """Add week to game from schedules if not already present."""
    if hasattr(game, "week") and not pd.isna(getattr(game, "week", None)):
        return game

    if schedules_df is None:
        return game

    # Match by home_team + away_team
    home = str(game.home_team)
    away = str(game.away_team)
    match = schedules_df[(schedules_df.home_team == home) & (schedules_df.away_team == away)]
    if match.empty:
        return game

    # Take the first (should be unique in a season for NFL)
    game_copy = game.copy()
    game_copy["week"] = match.iloc[0].week
    return game_copy


def main():
    if not LEDGER_DIR.exists():
        print(f"HALT: PICKS_LEDGER_DIR={LEDGER_DIR} does not exist")
        sys.exit(1)

    # Check: if a sport has ungraded past-commence game picks but no crosswalk, exit non-zero
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
            continue  # props don't need crosswalk check here (they need stats)
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
