#!/usr/bin/env python3
"""
WO10b Item 2b: Pull NFL injuries (league endpoint) + depth charts (per-team) from ESPN.
Gzipped output. Content-hash skip: if payload hash (minus ESPN's `timestamp` field)
matches the previous capture, skip the write and log to _pulls.jsonl instead.

No API key. Zero credits.
  injuries:    site.api.espn.com/apis/site/v2/sports/football/nfl/injuries
  depth chart: site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{id}/depthcharts

Output (raw JSON, append-only):
  data/injury_archive/nfl/season=2026/injuries_<UTC>.json.gz
  data/depth_archive/nfl/season=2026/depth_<UTC>.json.gz
  (or _pulls.jsonl entry if content unchanged)

Asserts 32 teams in each file. HALT on non-200, empty payload, or wrong team count.
"""

import argparse, gzip, hashlib, json, sys, time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent.parent
NFL_TEAM_MAP = ROOT / "nfl" / "pipeline" / "espn_team_map.json"
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
EXPECTED_TEAMS = 32


def _strip_volatile(obj, exclude_keys=("timestamp", "_pull_time")):
    """Recursively strip volatile keys from nested dicts/lists."""
    if isinstance(obj, dict):
        return {k: _strip_volatile(v, exclude_keys)
                for k, v in obj.items() if k not in exclude_keys}
    if isinstance(obj, list):
        return [_strip_volatile(v, exclude_keys) for v in obj]
    return obj


def _content_hash(data):
    """SHA-256 of JSON with volatile fields recursively removed."""
    clean = _strip_volatile(data)
    return hashlib.sha256(json.dumps(clean, sort_keys=True).encode()).hexdigest()


def _last_hash(pulls_path):
    """Read the last content hash from _pulls.jsonl."""
    if not pulls_path.exists():
        return None
    last_line = None
    with open(pulls_path) as f:
        for line in f:
            line = line.strip()
            if line:
                last_line = line
    if last_line:
        try:
            return json.loads(last_line).get("sha256")
        except json.JSONDecodeError:
            pass
    return None


def _log_pull(pulls_path, utc, sha, status):
    """Append a line to _pulls.jsonl."""
    pulls_path.parent.mkdir(parents=True, exist_ok=True)
    with open(pulls_path, "a") as f:
        f.write(json.dumps({"utc": utc, "sha256": sha, "status": status}) + "\n")


def pull_injuries(season):
    now = datetime.now(timezone.utc)
    ts_label = now.strftime("%Y%m%dT%H%MZ")

    r = requests.get(f"{ESPN_BASE}/injuries", timeout=30)
    if r.status_code != 200:
        print(f"HALT: injuries endpoint HTTP {r.status_code}")
        sys.exit(1)

    data = r.json()
    teams = data.get("injuries", [])
    print(f"  injuries: {len(teams)} teams")

    if len(teams) != EXPECTED_TEAMS:
        print(f"HALT: expected {EXPECTED_TEAMS} teams, got {len(teams)}")
        sys.exit(1)

    data["_pull_time"] = now.isoformat()

    out_dir = ROOT / "data" / "injury_archive" / "nfl" / f"season={season}"
    out_dir.mkdir(parents=True, exist_ok=True)
    pulls_path = out_dir / "_pulls.jsonl"

    h = _content_hash(data)
    prev = _last_hash(pulls_path)

    if h == prev:
        _log_pull(pulls_path, ts_label, h, "unchanged")
        print(f"  injuries unchanged (hash={h[:12]}), logged to _pulls.jsonl")
        return None

    out_path = out_dir / f"injuries_{ts_label}.json.gz"
    with gzip.open(out_path, "wt", encoding="utf-8") as f:
        json.dump(data, f)

    _log_pull(pulls_path, ts_label, h, "written")
    size_kb = out_path.stat().st_size / 1024
    total_athletes = sum(len(t.get("injuries", [])) for t in teams)
    print(f"  saved {total_athletes} athlete entries to {out_path} ({size_kb:.0f} KB)")
    return out_path


def pull_depth_charts(season):
    now = datetime.now(timezone.utc)
    ts_label = now.strftime("%Y%m%dT%H%MZ")

    with open(NFL_TEAM_MAP) as f:
        team_map = json.load(f)

    assert len(team_map) == EXPECTED_TEAMS, (
        f"team map has {len(team_map)} teams, expected {EXPECTED_TEAMS}")

    all_depth = {"_pull_time": now.isoformat(), "teams": []}
    errors = 0

    for team_name, info in sorted(team_map.items()):
        espn_id = info["id"]
        try:
            r = requests.get(
                f"{ESPN_BASE}/teams/{espn_id}/depthcharts", timeout=30)
        except requests.RequestException as e:
            print(f"  {team_name} (id={espn_id}): request error {e}")
            errors += 1
            time.sleep(0.5)
            continue

        if r.status_code != 200:
            print(f"  {team_name} (id={espn_id}): HTTP {r.status_code}")
            errors += 1
            time.sleep(0.5)
            continue

        data = r.json()
        data["_team_name"] = team_name
        data["_espn_id"] = espn_id
        all_depth["teams"].append(data)
        time.sleep(0.5)

    print(f"  depth charts: {len(all_depth['teams'])} teams fetched, {errors} errors")

    if len(all_depth["teams"]) != EXPECTED_TEAMS:
        print(f"HALT: expected {EXPECTED_TEAMS} depth chart teams, "
              f"got {len(all_depth['teams'])}")
        sys.exit(1)

    out_dir = ROOT / "data" / "depth_archive" / "nfl" / f"season={season}"
    out_dir.mkdir(parents=True, exist_ok=True)
    pulls_path = out_dir / "_pulls.jsonl"

    h = _content_hash(all_depth)
    prev = _last_hash(pulls_path)

    if h == prev:
        _log_pull(pulls_path, ts_label, h, "unchanged")
        print(f"  depth unchanged (hash={h[:12]}), logged to _pulls.jsonl")
        return None

    out_path = out_dir / f"depth_{ts_label}.json.gz"
    with gzip.open(out_path, "wt", encoding="utf-8") as f:
        json.dump(all_depth, f)

    _log_pull(pulls_path, ts_label, h, "written")
    size_kb = out_path.stat().st_size / 1024
    print(f"  saved to {out_path} ({size_kb:.0f} KB)")
    return out_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, default=2026)
    args = parser.parse_args()

    print(f"pull_espn_nfl_status --season {args.season}")
    t0 = time.time()

    pull_injuries(args.season)
    pull_depth_charts(args.season)

    elapsed = time.time() - t0
    print(f"  elapsed: {elapsed:.1f}s")


if __name__ == "__main__":
    main()
