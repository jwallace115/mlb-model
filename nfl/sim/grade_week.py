#!/usr/bin/env python3
"""
NFL Sim Phase 4B — Grade a week's picks_log against actual PBP results.

Usage: python3 nfl/sim/grade_week.py --season 2026 --week 1 [--extra path.parquet ...]
"""

import sys, argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from nfl.sim.calibration import actual_player_stats
from nfl.sim.names import (load_roster, _build_roster_lookup, resolve_player,
                           FULL_TO_ABBR)

OUT_BASE = ROOT / "nfl" / "data" / "sim" / "outputs"

TEAM_MAP_INV = {v: k for k, v in FULL_TO_ABBR.items()}


def load_picks(season, week, extra_paths=None):
    """Load picks_log.parquet for the week, plus any extra files."""
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

    # Handle old MNF format: has 'leg' column like "Kelce rec O4.5" instead of
    # player_id/family/line/side
    if "leg" in picks.columns and "player_id" not in picks.columns:
        picks = _convert_old_format(picks, season, week)

    # Deduplicate: keep last occurrence per (player_id, family, line, side)
    dedup_cols = [c for c in ["player_id", "family", "line", "side"] if c in picks.columns]
    if dedup_cols:
        picks = picks.drop_duplicates(subset=dedup_cols, keep="last")
    return picks


def _convert_old_format(df, season, week):
    """Convert old MNF picks format to new schema."""
    import re
    roster = load_roster()
    by_team, by_fi, by_league = _build_roster_lookup(roster, season, week)

    rows = []
    for _, row in df.iterrows():
        leg_str = row.get("leg", "")
        game_str = row.get("game", "")
        # Parse "Kelce rec O4.5" or "Worthy rec O3.5"
        m = re.match(r'(.+?)\s+(rec|rush|anytime\s*TD)\s+O([\d.]+)', leg_str)
        if not m:
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
            continue

        # Resolve player
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
            "position": "WR",  # default, will be overridden if we can look up
            "family": family,
            "line": line, "side": "over",
            "sim_p": None,
            "cal_p": row.get("calibrated_prob"),
            "tier": row.get("trust", "see board"),
            "book_price": row.get("book_price"),
            "book_implied": None,
            "one_sided": True,
            "pull_batch": None,
            "pull_timestamp": None,
            "board_generated_utc": row.get("ts"),
            "status": "unbet",
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
    if "@" not in game_str:
        return game_str
    parts = game_str.split("@")
    away, home = parts[0], parts[1]
    for gid in pbp_games:
        if f"_{away}_" in gid or gid.endswith(f"_{away}"):
            if f"_{home}" in gid:
                return gid
    # Also try matching the other way
    for gid in pbp_games:
        g = pbp_games[gid]
        if len(g) > 0:
            h = g["home_team"].iloc[0]
            a = g["away_team"].iloc[0]
            if h == home and a == away:
                return gid
    return None


def grade_leg(row, rec_stats, rush_stats, td_stats):
    """Grade a single leg against actual stats.

    Returns: 'hit', 'miss', or 'void'.
    """
    pid = row["player_id"]
    family = row["family"]
    side = row["side"]
    line = row["line"]

    if family == "receptions":
        k = int(line + 0.5)
        ar = rec_stats[rec_stats["player_id"] == pid]
        if len(ar) == 0:
            # Player not in passing plays — could be void
            return "void"
        actual = int(ar["actual_rec"].iloc[0])
        hit = actual >= k

    elif family == "reception_yds":
        k = int(line + 0.5)
        ar = rec_stats[rec_stats["player_id"] == pid]
        actual = int(ar["actual_rec_yds"].iloc[0]) if len(ar) else 0
        hit = actual >= k

    elif family == "rush_attempts":
        k = int(line + 0.5)
        ar = rush_stats[rush_stats["player_id"] == pid]
        actual = int(ar["actual_carries"].iloc[0]) if len(ar) else 0
        hit = actual >= k

    elif family == "rush_yds":
        k = int(line + 0.5)
        ar = rush_stats[rush_stats["player_id"] == pid]
        actual = int(ar["actual_rush_yds"].iloc[0]) if len(ar) else 0
        hit = actual >= k

    elif family == "anytime_td":
        ar = td_stats[td_stats["player_id"] == pid]
        actual = 1 if len(ar) > 0 else 0
        hit = actual >= 1

    else:
        return "void"

    if side == "under":
        hit = not hit

    return "hit" if hit else "miss"


def grade_week(season, week, extra_paths=None):
    picks = load_picks(season, week, extra_paths)
    print(f"Loaded {len(picks)} legs for season={season} week={week}")

    pbp_games = load_game_pbp(season)
    print(f"PBP games available: {len(pbp_games)}")

    # Grade each leg
    results = []
    actuals_cache = {}

    for _, row in picks.iterrows():
        game_str = row.get("game_id", row.get("game", ""))
        pbp_gid = find_game_id(game_str, season, pbp_games)

        if pbp_gid is None or pbp_gid not in pbp_games:
            results.append("void-pending")
            continue

        if pbp_gid not in actuals_cache:
            game_pbp = pbp_games[pbp_gid]
            rec, rush, td = actual_player_stats(game_pbp)
            actuals_cache[pbp_gid] = (rec, rush, td)
        else:
            rec, rush, td = actuals_cache[pbp_gid]

        # Check if player had any snaps (if not in any stat, void)
        pid = row["player_id"]
        in_game = (len(rec[rec["player_id"] == pid]) > 0 or
                   len(rush[rush["player_id"] == pid]) > 0 or
                   len(td[td["player_id"] == pid]) > 0)

        if not in_game:
            # Check if player appears in any PBP columns at all
            game_pbp = pbp_games[pbp_gid]
            has_plays = False
            for col in ["receiver_player_id", "rusher_player_id", "passer_player_id"]:
                if col in game_pbp.columns:
                    if pid in game_pbp[col].values:
                        has_plays = True
                        break
            if not has_plays:
                results.append("void")
                continue

        grade = grade_leg(row, rec, rush, td)
        results.append(grade)

    picks["grade"] = results
    return picks


def write_report(picks, season, week):
    """Write grade_report.md and grades.parquet."""
    out_dir = OUT_BASE / f"week={season}_{week:02d}"
    out_dir.mkdir(parents=True, exist_ok=True)

    picks.to_parquet(out_dir / "grades.parquet", index=False)

    graded = picks[picks["grade"].isin(["hit", "miss"])]
    lines = []
    lines.append(f"# NFL Week {week} ({season}) Grade Report")
    lines.append(f"\nTotal legs: {len(picks)}")
    lines.append(f"Graded: {len(graded)} (hit: {(graded['grade']=='hit').sum()}, "
                 f"miss: {(graded['grade']=='miss').sum()})")
    lines.append(f"Void: {(picks['grade']=='void').sum()}")
    lines.append(f"Void-pending (game not in PBP): {(picks['grade']=='void-pending').sum()}")
    lines.append("")
    lines.append("**One week cannot validate anything -- this is a log, not evidence.**")
    lines.append("")

    if len(graded) == 0:
        lines.append("No graded legs available.")
        report = "\n".join(lines)
        with open(out_dir / "grade_report.md", "w") as f:
            f.write(report)
        return report

    # Hit rate and Brier by family x position
    lines.append("## By family x position")
    lines.append("")
    lines.append("| Family | Position | N | Hit rate | Brier |")
    lines.append("|--------|----------|---|----------|-------|")
    for (fam, pos), g in graded.groupby(["family", "position"]):
        hr = (g["grade"] == "hit").mean()
        hit_int = (g["grade"] == "hit").astype(int)
        cal_p = g["cal_p"].values
        brier = ((cal_p - hit_int.values) ** 2).mean()
        lines.append(f"| {fam:20s} | {pos:4s} | {len(g):4d} | {hr:.3f} | {brier:.3f} |")

    # By cal_p bin
    lines.append("")
    lines.append("## By calibrated probability bin")
    lines.append("")
    lines.append("| Bin | N | Hit rate | Mean cal_p | Brier |")
    lines.append("|-----|---|----------|------------|-------|")
    bins = [(0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 1.0)]
    for lo, hi in bins:
        g = graded[(graded["cal_p"] >= lo) & (graded["cal_p"] < hi)]
        if len(g) == 0:
            continue
        hr = (g["grade"] == "hit").mean()
        hit_int = (g["grade"] == "hit").astype(int)
        brier = ((g["cal_p"].values - hit_int.values) ** 2).mean()
        lines.append(f"| {lo:.1f}-{hi:.1f} | {len(g):4d} | {hr:.3f} | {g['cal_p'].mean():.3f} | {brier:.3f} |")

    # By tier
    lines.append("")
    lines.append("## By tier")
    lines.append("")
    lines.append("| Tier | N | Hit rate |")
    lines.append("|------|---|----------|")
    for tier in sorted(graded["tier"].unique()):
        g = graded[graded["tier"] == tier]
        hr = (g["grade"] == "hit").mean()
        lines.append(f"| {tier:40s} | {len(g):4d} | {hr:.3f} |")

    # CLV (if closing pull exists)
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
                clv = (g["cal_p"] - g["book_implied"]).mean()
                lines.append(f"| {fam:20s} | {len(g):4d} | {clv:+.4f} |")

    lines.append("")
    lines.append(f"Sample size: {len(graded)} graded legs from {len(graded['game_id'].unique())} games.")
    lines.append("One week cannot validate anything.")

    report = "\n".join(lines)
    with open(out_dir / "grade_report.md", "w") as f:
        f.write(report)
    print(f"Grade report: {out_dir / 'grade_report.md'}")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--extra", nargs="*", default=[])
    args = parser.parse_args()

    picks = grade_week(args.season, args.week, args.extra)
    report = write_report(picks, args.season, args.week)
    print("\n" + report)


if __name__ == "__main__":
    main()
