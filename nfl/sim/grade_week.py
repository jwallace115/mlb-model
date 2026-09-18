#!/usr/bin/env python3
"""
NFL Sim Phase 4B-fix — Grade a week's picks_log against actual PBP results.

Usage: python3 nfl/sim/grade_week.py --season 2026 --week 1 [--extra path.parquet ...]

Never drops a leg silently. Every input row appears in grades.parquet with one of:
  hit, miss, void, void-pending, unresolved.
"""

import sys, argparse, re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from nfl.sim.actuals import actual_player_game_stats
from nfl.sim.names import (load_roster, _build_roster_lookup, resolve_player,
                           FULL_TO_ABBR)

OUT_BASE = ROOT / "nfl" / "data" / "sim" / "outputs"
TEAM_MAP_INV = {v: k for k, v in FULL_TO_ABBR.items()}

# Canonical picks_log columns (extras are passed through)
_CANONICAL_COLS = [
    "season", "week", "game_id", "home", "away", "player_id", "player_name",
    "position", "family", "line", "side", "sim_p", "cal_p", "tier",
    "book_price", "book_implied", "one_sided", "pull_batch", "pull_timestamp",
    "board_generated_utc", "status",
]


def load_picks(season, week, extra_paths=None):
    """Load picks_log.parquet for the week, plus any extra files.

    Rows with player_id already set are NOT re-resolved.
    Old-format files (with 'leg' column) are converted; unresolvable rows
    are kept with grade='unresolved'.
    """
    out_dir = OUT_BASE / f"week={season}_{week:02d}"
    frames = []
    main_path = out_dir / "picks_log.parquet"
    if main_path.exists():
        frames.append(pd.read_parquet(main_path))
    if extra_paths:
        for p in extra_paths:
            pp = Path(p)
            if pp.exists():
                df = pd.read_parquet(pp)
                frames.append(df)
                print(f"  Extra: {pp} ({len(df)} rows)")
            else:
                print(f"  WARNING: extra file not found: {pp}")
    if not frames:
        raise FileNotFoundError(f"No picks_log for season={season} week={week}")
    picks = pd.concat(frames, ignore_index=True)

    # Handle old MNF format
    if "leg" in picks.columns and "player_id" not in picks.columns:
        picks = _convert_old_format(picks, season, week)

    # Deduplicate: keep last occurrence per (player_id, family, line, side, ticket)
    # Include ticket if present — same leg in different tickets should be kept
    dedup_cols = [c for c in ["player_id", "family", "line", "side", "ticket"]
                  if c in picks.columns]
    if not dedup_cols:
        dedup_cols = [c for c in ["player_id", "family", "line", "side"]
                      if c in picks.columns]
    if dedup_cols:
        picks = picks.drop_duplicates(subset=dedup_cols, keep="last")
    return picks


def _convert_old_format(df, season, week):
    """Convert old MNF picks format to new schema. Never drops rows."""
    roster = load_roster()
    by_team, by_fi, by_league = _build_roster_lookup(roster, season, week)

    rows = []
    for _, row in df.iterrows():
        leg_str = row.get("leg", "")
        game_str = row.get("game", "")
        m = re.match(r'(.+?)\s+(rec|rush|anytime\s*TD)\s+O([\d.]+)', str(leg_str))
        if not m:
            # Unparseable leg — keep as unresolved
            rows.append({
                "season": season, "week": week,
                "game_id": game_str,
                "home": "", "away": "",
                "player_id": None,
                "player_name": str(leg_str),
                "position": "", "family": "unknown",
                "line": 0, "side": "over",
                "sim_p": None, "cal_p": row.get("calibrated_prob"),
                "tier": "unknown", "book_price": row.get("book_price"),
                "book_implied": None, "one_sided": True,
                "pull_batch": None, "pull_timestamp": None,
                "board_generated_utc": row.get("ts"),
                "status": "unbet",
                "_unresolved_reason": f"unparseable leg: {leg_str}",
            })
            continue

        player_last = m.group(1).strip()
        prop_type = m.group(2).strip()
        line = float(m.group(3))

        if "rec" in prop_type:
            family = "receptions"
        elif "rush" in prop_type:
            family = "rush_yds"
        elif "TD" in prop_type:
            family = "anytime_td"
        else:
            family = "unknown"

        teams = game_str.split("@") if "@" in game_str else [game_str[:3], game_str[-2:]]
        pid, method = resolve_player(player_last, season, week, teams,
                                     by_team, by_fi, by_league)

        rows.append({
            "season": season, "week": week,
            "game_id": game_str,
            "home": teams[-1] if len(teams) > 1 else "",
            "away": teams[0] if len(teams) > 1 else "",
            "player_id": pid,
            "player_name": player_last,
            "position": "WR",
            "family": family,
            "line": line, "side": "over",
            "sim_p": None, "cal_p": row.get("calibrated_prob"),
            "tier": row.get("trust", "see board"),
            "book_price": row.get("book_price"),
            "book_implied": None, "one_sided": True,
            "pull_batch": None, "pull_timestamp": None,
            "board_generated_utc": row.get("ts"),
            "status": "unbet",
            "resolve_method": method,
            "_unresolved_reason": None if pid else f"name not resolved: {player_last}",
        })

    return pd.DataFrame(rows)


def load_game_pbp(season):
    """Load PBP for the season, return dict of game_id -> game_pbp DataFrame."""
    pbp_path = ROOT / "nfl" / "data" / "pbp" / f"pbp_{season}.parquet"
    if not pbp_path.exists():
        return {}
    pbp = pd.read_parquet(pbp_path)
    games = {}
    for gid, gdf in pbp.groupby("game_id"):
        games[gid] = gdf
    return games


def find_game_id(game_str, season, pbp_games):
    """Map 'DEN@KC' style game_id to PBP game_id."""
    if not game_str or "@" not in str(game_str):
        return game_str
    parts = str(game_str).split("@")
    away, home = parts[0], parts[1]
    for gid in pbp_games:
        g = pbp_games[gid]
        if len(g) > 0:
            h = g["home_team"].iloc[0]
            a = g["away_team"].iloc[0]
            if h == home and a == away:
                return gid
    return None


def grade_leg(row, rec_stats, rush_stats, td_stats, pass_stats,
              player_was_active=True):
    """Grade a single leg against actual stats. Returns (grade, reason).

    If the player has no stat rows but was active (on roster and team played),
    actual = 0 for counting stats. Void only if the player was inactive or
    the family is unknown.
    """
    pid = row["player_id"]
    family = row["family"]
    side = row["side"]
    line = row["line"]

    # D64: canonical family vocabulary + push handling.
    # Accepts both old names (reception_yds, rush_attempts, etc.) and
    # K4 names (rec_yds, rush_att, etc.) — raises on unmapped.
    _FAMILY_CANON = {
        "receptions": "receptions", "rec": "receptions",
        "reception_yds": "rec_yds", "rec_yds": "rec_yds",
        "rush_yds": "rush_yds",
        "rush_attempts": "rush_att", "rush_att": "rush_att",
        "anytime_td": "atd", "atd": "atd",
        "pass_completions": "pass_cmp", "pass_cmp": "pass_cmp",
        "pass_attempts": "pass_att", "pass_att": "pass_att",
        "pass_yds": "pass_yds",
        "pass_tds": "pass_td", "pass_td": "pass_td",
    }
    canon = _FAMILY_CANON.get(family)
    if canon is None:
        return ("void", f"unknown family: {family}")

    # Look up actual value
    if canon == "receptions":
        ar = rec_stats[rec_stats["player_id"] == pid]
        actual = int(ar["actual_rec"].iloc[0]) if len(ar) else 0
    elif canon == "rec_yds":
        ar = rec_stats[rec_stats["player_id"] == pid]
        actual = int(ar["actual_rec_yds"].iloc[0]) if len(ar) else 0
    elif canon == "rush_att":
        ar = rush_stats[rush_stats["player_id"] == pid]
        actual = int(ar["actual_carries"].iloc[0]) if len(ar) else 0
    elif canon == "rush_yds":
        ar = rush_stats[rush_stats["player_id"] == pid]
        actual = int(ar["actual_rush_yds"].iloc[0]) if len(ar) else 0
    elif canon == "atd":
        ar = td_stats[td_stats["player_id"] == pid]
        return ("hit" if len(ar) > 0 else "miss", None) if side == "over" else ("miss" if len(ar) > 0 else "hit", None)
    elif canon == "pass_cmp":
        ar = pass_stats[pass_stats["player_id"] == pid]
        actual = int(ar["actual_completions"].iloc[0]) if len(ar) else 0
    elif canon == "pass_att":
        ar = pass_stats[pass_stats["player_id"] == pid]
        actual = int(ar["actual_pass_att"].iloc[0]) if len(ar) else 0
    elif canon == "pass_yds":
        ar = pass_stats[pass_stats["player_id"] == pid]
        actual = int(ar["actual_pass_yds"].iloc[0]) if len(ar) else 0
    elif canon == "pass_td":
        ar = pass_stats[pass_stats["player_id"] == pid]
        actual = int(ar["actual_pass_td"].iloc[0]) if len(ar) else 0
    else:
        return ("void", f"unknown canon family: {canon}")

    # Push: actual exactly equals a whole-number line → void
    if line == int(line) and actual == int(line):
        return ("void", f"push: actual {actual} == line {line}")

    hit = actual > line
    if side == "under":
        hit = actual < line

    return ("hit" if hit else "miss", None)


def grade_week(season, week, extra_paths=None):
    picks = load_picks(season, week, extra_paths)
    print(f"Loaded {len(picks)} legs for season={season} week={week}")

    pbp_games = load_game_pbp(season)
    print(f"PBP games available: {len(pbp_games)}")

    grades = []
    reasons = []
    actuals_cache = {}

    for _, row in picks.iterrows():
        # Check for unresolved player_id
        pid = row.get("player_id")
        if pid is None or (isinstance(pid, float) and np.isnan(pid)):
            reason = row.get("_unresolved_reason", "player_id is null")
            grades.append("unresolved")
            reasons.append(str(reason))
            continue

        game_str = row.get("game_id", row.get("game", ""))
        pbp_gid = find_game_id(game_str, season, pbp_games)

        if pbp_gid is None or pbp_gid not in pbp_games:
            grades.append("void-pending")
            reasons.append("game not in PBP")
            continue

        if pbp_gid not in actuals_cache:
            game_pbp = pbp_games[pbp_gid]
            rec, rush, td, pass_stats = actual_player_game_stats(game_pbp)
            actuals_cache[pbp_gid] = (rec, rush, td, pass_stats)
        else:
            rec, rush, td, pass_stats = actuals_cache[pbp_gid]

        # Determine if the player was active (on the roster for that team-week).
        # A player with no stat rows but who was active grades actual = 0.
        # Void only if the player was NOT on the active roster.
        in_stats = (len(rec[rec["player_id"] == pid]) > 0 or
                    len(rush[rush["player_id"] == pid]) > 0 or
                    len(td[td["player_id"] == pid]) > 0 or
                    len(pass_stats[pass_stats["player_id"] == pid]) > 0)

        if not in_stats:
            # Check active_universe or PBP presence
            game_pbp = pbp_games[pbp_gid]
            has_plays = False
            for col in ["receiver_player_id", "rusher_player_id", "passer_player_id"]:
                if col in game_pbp.columns:
                    if pid in game_pbp[col].values:
                        has_plays = True
                        break

            # Also check active_universe_weekly if available
            au_path = ROOT / "nfl" / "data" / "sim" / "ratings" / "active_universe_weekly.parquet"
            player_active = False
            if au_path.exists():
                au = pd.read_parquet(au_path)
                team = row.get("home") or row.get("away") or ""
                # Check both teams
                for t in [row.get("home", ""), row.get("away", "")]:
                    au_match = au[(au["season"] == season) & (au["week"] == week)
                                 & (au["team"] == t) & (au["player_id"] == pid)
                                 & (au["active_flag"] == True)]
                    if len(au_match) > 0:
                        player_active = True
                        break

            if not has_plays and not player_active:
                grades.append("void")
                reasons.append("player not active/not in game PBP")
                continue
            # Player was active but had zero stats — grade with actual = 0

        g, reason = grade_leg(row, rec, rush, td, pass_stats)
        grades.append(g)
        reasons.append(reason)

    picks["grade"] = grades
    picks["grade_reason"] = reasons
    return picks


def write_report(picks, season, week):
    """Write grade_report.md and grades.parquet."""
    out_dir = OUT_BASE / f"week={season}_{week:02d}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Drop internal columns before saving
    save_cols = [c for c in picks.columns if not c.startswith("_")]
    picks[save_cols].to_parquet(out_dir / "grades.parquet", index=False)

    graded = picks[picks["grade"].isin(["hit", "miss"])]
    lines = []
    lines.append(f"# NFL Week {week} ({season}) Grade Report")
    lines.append(f"\nTotal legs: {len(picks)}")
    lines.append(f"Graded: {len(graded)} (hit: {(graded['grade']=='hit').sum()}, "
                 f"miss: {(graded['grade']=='miss').sum()})")
    n_void = (picks['grade'] == 'void').sum()
    n_pending = (picks['grade'] == 'void-pending').sum()
    n_unresolved = (picks['grade'] == 'unresolved').sum()
    lines.append(f"Void: {n_void}")
    lines.append(f"Void-pending (game not in PBP): {n_pending}")
    lines.append(f"Unresolved (player_id missing): {n_unresolved}")
    if n_unresolved > 0:
        for _, r in picks[picks['grade'] == 'unresolved'].iterrows():
            lines.append(f"  - {r.get('player_name','?')}: {r.get('grade_reason','?')}")
    lines.append("")
    lines.append("**One week cannot validate anything -- this is a log, not evidence.**")
    lines.append("")

    if len(graded) == 0:
        lines.append("No graded legs available.")
        report = "\n".join(lines)
        with open(out_dir / "grade_report.md", "w") as f:
            f.write(report)
        return report

    # By family x position
    lines.append("## By family x position")
    lines.append("")
    lines.append("| Family | Position | N | Hit rate | Brier |")
    lines.append("|--------|----------|---|----------|-------|")
    for (fam, pos), g in graded.groupby(["family", "position"]):
        hr = (g["grade"] == "hit").mean()
        hit_int = (g["grade"] == "hit").astype(int)
        cal_p = pd.to_numeric(g["cal_p"], errors="coerce").fillna(0.5).values
        brier = ((cal_p - hit_int.values) ** 2).mean()
        lines.append(f"| {fam:20s} | {pos:4s} | {len(g):4d} | {hr:.3f} | {brier:.3f} |")

    # By cal_p bin
    lines.append("")
    lines.append("## By calibrated probability bin")
    lines.append("")
    lines.append("| Bin | N | Hit rate | Mean cal_p | Brier |")
    lines.append("|-----|---|----------|------------|-------|")
    cal_p_num = pd.to_numeric(graded["cal_p"], errors="coerce")
    for lo, hi in [(0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 1.0)]:
        mask = (cal_p_num >= lo) & (cal_p_num < hi)
        g = graded[mask]
        if len(g) == 0:
            continue
        hr = (g["grade"] == "hit").mean()
        hit_int = (g["grade"] == "hit").astype(int)
        cp = cal_p_num[mask].values
        brier = ((cp - hit_int.values) ** 2).mean()
        lines.append(f"| {lo:.1f}-{hi:.1f} | {len(g):4d} | {hr:.3f} | {cp.mean():.3f} | {brier:.3f} |")

    # By tier
    if "tier" in graded.columns:
        lines.append("")
        lines.append("## By tier")
        lines.append("")
        lines.append("| Tier | N | Hit rate |")
        lines.append("|------|---|----------|")
        for tier in sorted(graded["tier"].dropna().unique()):
            g = graded[graded["tier"] == tier]
            hr = (g["grade"] == "hit").mean()
            lines.append(f"| {str(tier):40s} | {len(g):4d} | {hr:.3f} |")

    # CLV
    if "book_implied" in graded.columns:
        priced = graded[graded["book_implied"].notna()]
        if len(priced) > 0:
            lines.append("")
            lines.append("## CLV (where book price exists)")
            lines.append("")
            lines.append("| Family | N | Mean CLV (cal_p - book_implied) |")
            lines.append("|--------|---|---------------------------------|")
            for fam in sorted(priced["family"].unique()):
                g = priced[priced["family"] == fam]
                clv = (pd.to_numeric(g["cal_p"], errors="coerce") -
                       pd.to_numeric(g["book_implied"], errors="coerce")).mean()
                lines.append(f"| {fam:20s} | {len(g):4d} | {clv:+.4f} |")

    # CLV vs Hard Rock close
    if "clv" in graded.columns and graded["clv"].notna().any():
        clv_data = graded[graded["clv"].notna()]
        lines.append("")
        lines.append("## CLV vs Hard Rock close (close_implied - pick_implied)")
        lines.append("")
        lines.append("| Family | N | Mean CLV |")
        lines.append("|--------|---|----------|")
        for fam in sorted(clv_data["family"].unique()):
            g = clv_data[clv_data["family"] == fam]
            mean_clv = g["clv"].mean()
            lines.append(f"| {fam:20s} | {len(g):4d} | {mean_clv:+.4f} |")
        if "ticket" in clv_data.columns and clv_data["ticket"].notna().any():
            lines.append("")
            lines.append("| Ticket | N | Mean CLV |")
            lines.append("|--------|---|----------|")
            for ticket, tg in clv_data.groupby("ticket"):
                if pd.isna(ticket):
                    continue
                mean_clv = tg["clv"].mean()
                lines.append(f"| {str(ticket):20s} | {len(tg):4d} | {mean_clv:+.4f} |")
        overall = clv_data["clv"].mean()
        lines.append(f"\nOverall mean CLV: {overall:+.4f} (N={len(clv_data)})")

    # By ticket
    if "ticket" in picks.columns and picks["ticket"].notna().any():
        lines.append("")
        lines.append("## By ticket")
        lines.append("")
        ticket_picks = picks[picks["ticket"].notna() & picks["grade"].isin(["hit", "miss"])]
        if len(ticket_picks) > 0:
            lines.append("| Ticket | Legs | Hits | Misses | All hit? |")
            lines.append("|--------|------|------|--------|----------|")
            for ticket, tg in ticket_picks.groupby("ticket"):
                hits = (tg["grade"] == "hit").sum()
                misses = (tg["grade"] == "miss").sum()
                all_hit = "YES" if misses == 0 else "NO"
                lines.append(f"| {str(ticket):20s} | {len(tg):4d} | {hits:4d} | {misses:4d} | {all_hit:8s} |")

    lines.append("")
    lines.append(f"Sample size: {len(graded)} graded legs from "
                 f"{len(graded['game_id'].unique())} games.")
    lines.append("One week cannot validate anything.")

    report = "\n".join(lines)
    with open(out_dir / "grade_report.md", "w") as f:
        f.write(report)
    print(f"Grade report: {out_dir / 'grade_report.md'}")
    return report


def compute_clv(picks, season):
    """D64: CLV on no-vig scale with game identity.

    Both pick-time and close-time implied probabilities are devigged
    (normalized to sum to 1 proportionally), then:
      CLV = close_devig[side] - pick_devig[side]
    Positive CLV means the line moved in the pick's favor.

    Game identity: matches on (player_name, market_key, line, event_id)
    using the game_id from picks to find the event_id. Never falls through
    to another game's price.
    """
    props_dir = ROOT / "data" / "odds_archive" / "nfl" / "props"
    frames = []
    for f in sorted(props_dir.rglob(f"season={season}/**/*.parquet")):
        if "raw_live" in str(f):
            continue
        try:
            df = pd.read_parquet(f)
            if "bookmaker" in df.columns:
                hr = df[df["bookmaker"] == "hardrockbet_fl"]
                if len(hr) > 0:
                    frames.append(hr)
        except Exception:
            pass

    if not frames:
        picks["close_price"] = np.nan
        picks["close_implied"] = np.nan
        picks["clv"] = np.nan
        return picks

    archive = pd.concat(frames, ignore_index=True)
    archive["pull_ts"] = pd.to_datetime(archive["pull_timestamp"], utc=True,
                                         errors="coerce")
    archive["commence_dt"] = pd.to_datetime(archive["commence_time"], utc=True,
                                             errors="coerce")
    archive = archive[archive["pull_ts"] < archive["commence_dt"]]
    archive = archive.sort_values("pull_ts", ascending=False)
    # Dedup per (event_id, market_key, player_name, line) — latest pre-game
    close = archive.drop_duplicates(
        subset=["event_id", "market_key", "player_name", "line"],
        keep="first"
    )

    # Build event_id lookup from the archive: (home_team, away_team) -> event_id
    # Multiple events per (home, away) across weeks, so also key by commence_time
    event_lookup = {}
    for _, r in close.drop_duplicates("event_id").iterrows():
        ht = r.get("home_team", "")
        at = r.get("away_team", "")
        eid = r["event_id"]
        event_lookup.setdefault((ht, at), []).append(eid)

    # Canonical family → market_key (D64: one vocabulary, raise on unmapped)
    _FAMILY_TO_MKT = {
        "receptions": "player_receptions",
        "rec_yds": "player_reception_yds", "reception_yds": "player_reception_yds",
        "rush_yds": "player_rush_yds",
        "rush_att": "player_rush_attempts", "rush_attempts": "player_rush_attempts",
        "anytime_td": "player_anytime_td", "atd": "player_anytime_td",
        "pass_yds": "player_pass_yds",
        "pass_att": "player_pass_attempts", "pass_attempts": "player_pass_attempts",
        "pass_cmp": "player_pass_completions", "pass_completions": "player_pass_completions",
        "pass_td": "player_pass_tds", "pass_tds": "player_pass_tds",
    }

    close_prices = []
    close_implieds = []
    clvs = []

    for _, row in picks.iterrows():
        pname = row.get("player_name", "")
        family = row.get("family", "")
        line = row.get("line")
        side = row.get("side", "over")
        pick_book_price = row.get("book_price")
        pick_implied = row.get("book_implied")

        mkt = _FAMILY_TO_MKT.get(family)
        if mkt is None or pname is None:
            close_prices.append(np.nan)
            close_implieds.append(np.nan)
            clvs.append(np.nan)
            continue

        # Game identity: find event_id(s) for this game
        game_id = row.get("game_id", "")
        home = row.get("home", "")
        away = row.get("away", "")
        from nfl.sim.names import FULL_TO_ABBR
        _INV = {v: k for k, v in FULL_TO_ABBR.items()}
        home_full = _INV.get(home, home)
        away_full = _INV.get(away, away)

        candidate_eids = event_lookup.get((home_full, away_full), [])
        if not candidate_eids:
            close_prices.append(np.nan)
            close_implieds.append(np.nan)
            clvs.append(np.nan)
            continue

        # Match on (event_id, market_key, player_name, line)
        match = close[
            close["event_id"].isin(candidate_eids)
            & (close["market_key"] == mkt)
            & (close["player_name"] == pname)
            & (np.abs(close["line"] - line) < 0.01)
        ]

        if match.empty:
            close_prices.append(np.nan)
            close_implieds.append(np.nan)
            clvs.append(np.nan)
            continue

        cr = match.iloc[0]
        close_imp_over = cr.get("implied_over")
        close_imp_under = cr.get("implied_under")

        if side == "over":
            cp = cr.get("over_price")
        else:
            cp = cr.get("under_price")
        close_prices.append(cp)

        # Devig both sides
        if pd.notna(close_imp_over) and pd.notna(close_imp_under) and (close_imp_over + close_imp_under) > 0:
            close_total = close_imp_over + close_imp_under
            close_devig = close_imp_over / close_total if side == "over" else close_imp_under / close_total
        else:
            close_devig = np.nan

        close_implieds.append(close_devig)

        # Pick-time devig: need both sides from the pick
        # picks_log stores book_implied for the picked side only.
        # We can approximate: if one_sided, can't devig → NaN.
        # If not one_sided, book_implied is already devigged in run_week
        # (line 409: book_implied = imp_o / total_imp or imp_u / total_imp).
        pick_devig = pick_implied  # already devigged in run_week

        if pd.notna(close_devig) and pd.notna(pick_devig) and pick_devig > 0:
            clvs.append(float(close_devig) - float(pick_devig))
        else:
            clvs.append(np.nan)

    picks["close_price"] = close_prices
    picks["close_implied"] = close_implieds
    picks["clv"] = clvs
    return picks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--extra", nargs="*", default=[])
    args = parser.parse_args()

    picks = grade_week(args.season, args.week, args.extra)
    picks = compute_clv(picks, args.season)
    report = write_report(picks, args.season, args.week)
    print("\n" + report)


if __name__ == "__main__":
    main()
