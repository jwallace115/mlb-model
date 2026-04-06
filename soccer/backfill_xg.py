#!/usr/bin/env python3
"""One-time backfill: populate xG + shots from cached API-Football stats responses."""
import json
import pandas as pd
import numpy as np
from pathlib import Path

STATS_CACHE = Path("soccer/data/cache/stats")
CANON_PATH = Path("soccer/data/soccer_canonical.parquet")
CACHE_DIR = Path("soccer/data/cache/refresh")


def get_stat(statistics, team_name, stat_type):
    """Match stat by type, normalizing underscores to spaces."""
    for s in statistics:
        if team_name.lower() in s.get("team", {}).get("name", "").lower():
            for item in s.get("statistics", []):
                api_type = item.get("type", "").lower().replace("_", " ")
                if stat_type.lower() == api_type:
                    v = item.get("value")
                    if v is not None and v != "":
                        try:
                            return float(str(v).replace("%", ""))
                        except Exception:
                            return None
    return None


def main():
    # Build fixture_id -> canonical mapping from cached date responses
    fid_map = {}
    for f in sorted(CACHE_DIR.iterdir()):
        if not f.name.endswith(".json"):
            continue
        try:
            data = json.loads(f.read_text())
            for fix in data.get("response", []):
                fid = fix.get("fixture", {}).get("id")
                status = fix.get("fixture", {}).get("status", {}).get("short", "")
                if status not in ("FT", "AET", "PEN") or not fid:
                    continue
                home = fix.get("teams", {}).get("home", {}).get("name", "")
                away = fix.get("teams", {}).get("away", {}).get("name", "")
                date = fix.get("fixture", {}).get("date", "")[:10]
                fid_map[fid] = {"home": home, "away": away, "date": date}
        except Exception:
            pass

    canon = pd.read_parquet(CANON_PATH)
    c26 = canon[canon["game_date"] >= "2025-08-01"]
    canon_lookup = {}
    for idx, row in c26.iterrows():
        key = (row["home_team"], row["game_date"])
        canon_lookup[key] = idx

    print(f"Fixtures: {len(fid_map)}, Canonical 2025-26: {len(c26)}")

    got_xg = 0
    got_shots = 0
    no_stats = 0
    unmatched = 0

    for fid, info in fid_map.items():
        cache_file = STATS_CACHE / f"stats_{fid}.json"
        if not cache_file.exists():
            continue

        data = json.loads(cache_file.read_text())
        stats = data.get("response", [])

        key = (info["home"], info["date"])
        canon_idx = canon_lookup.get(key)
        if canon_idx is None:
            unmatched += 1
            continue

        if not stats:
            no_stats += 1
            continue

        home_xg = get_stat(stats, info["home"], "expected goals")
        away_xg = get_stat(stats, info["away"], "expected goals")
        home_shots = get_stat(stats, info["home"], "total shots")
        away_shots = get_stat(stats, info["away"], "total shots")
        home_sot = get_stat(stats, info["home"], "shots on goal")
        away_sot = get_stat(stats, info["away"], "shots on goal")

        if home_xg is not None:
            canon.at[canon_idx, "home_xg_raw"] = home_xg
            canon.at[canon_idx, "away_xg_raw"] = away_xg
            canon.at[canon_idx, "xg_source"] = "api_football"
            got_xg += 1
        if home_shots is not None:
            canon.at[canon_idx, "home_shots"] = home_shots
            canon.at[canon_idx, "away_shots"] = away_shots
            got_shots += 1
        if home_sot is not None:
            canon.at[canon_idx, "home_shots_on_target"] = home_sot
            canon.at[canon_idx, "away_shots_on_target"] = away_sot

    canon.to_parquet(CANON_PATH, index=False)

    print(f"\n=== BACKFILL COMPLETE ===")
    print(f"Got xG: {got_xg}")
    print(f"Got shots: {got_shots}")
    print(f"No stats: {no_stats}")
    print(f"Unmatched: {unmatched}")

    # Verify
    c26_after = pd.read_parquet(CANON_PATH)
    c26_after = c26_after[c26_after["game_date"] >= "2025-08-01"]
    print(f"\nAfter backfill:")
    print(f"  home_xg_raw coverage: {c26_after['home_xg_raw'].notna().mean():.1%}")
    print(f"  home_shots coverage: {c26_after['home_shots'].notna().mean():.1%}")
    print(f"  home_shots_on_target coverage: {c26_after['home_shots_on_target'].notna().mean():.1%}")

    # Diagnostic
    bun = c26_after[(c26_after["league_id"] == "BUN") & (c26_after["home_xg_raw"].notna())]
    if len(bun) > 0:
        row = bun.iloc[-1]
        print(f"\nDiagnostic: {row['home_team']} vs {row['away_team']} ({row['game_date']})")
        print(f"  home_xg={row['home_xg_raw']}, away_xg={row['away_xg_raw']}")
        print(f"  home_shots={row['home_shots']}, away_shots={row['away_shots']}")
        print(f"  score: {int(row['home_score'])}-{int(row['away_score'])}")
    else:
        print("\nNo BUN games with xG found!")


if __name__ == "__main__":
    main()
