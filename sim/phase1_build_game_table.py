#!/usr/bin/env python3
"""
sim/phase1_build_game_table.py — Phase 1: Canonical Historical Game Table

Builds a master game table for 2022, 2023, and 2024 MLB regular seasons.

Column categories
─────────────────
OUTCOME / TARGET fields (used only as regression targets and evaluation labels —
never as model inputs at prediction time):
  home_score, away_score, actual_total, actual_f5_total

PREGAME CONTEXT fields (safe to use as model features — all reflect only
information available before first pitch):
  game_pk, date, season, home_team, away_team,
  venue_id, venue_name, park_id,
  home_rest_days, away_rest_days, doubleheader_flag, game_number,
  temperature, wind_speed, wind_direction, roof_status,
  park_factor_runs, park_factor_hr,
  umpire_name, umpire_id, umpire_over_rate, umpire_k_rate

METADATA / AUDIT fields (kept for validation only — not model inputs):
  game_hour_utc, innings_played, completed_early

actual_f5_total is populated only when all 5 innings were completed with
confirmed run values. It is left null for games called before 5 innings or
when inning data is incomplete.

Usage:
    cd /Users/jw115/mlb-model
    python sim/phase1_build_game_table.py                   # full build
    python sim/phase1_build_game_table.py --seasons 2024    # single season
    python sim/phase1_build_game_table.py --audit-only      # re-audit existing table
    python sim/phase1_build_game_table.py --no-weather      # skip weather (fast test)
"""

import argparse
import json
import math
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

# ── Paths ──────────────────────────────────────────────────────────────────────

ROOT      = Path(__file__).parent.parent
SIM_DIR   = Path(__file__).parent
DATA_DIR  = SIM_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
OUT_PATH  = DATA_DIR / "game_table.parquet"

DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT))

from config import STADIUMS, TEAM_ID_TO_ABB
from modules.umpires import get_umpire_rating

# ── Constants ──────────────────────────────────────────────────────────────────

MLB_API    = "https://statsapi.mlb.com/api/v1"
WX_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"

SEASON_WINDOWS = {
    2022: ("2022-04-07", "2022-10-05"),
    2023: ("2023-03-30", "2023-10-01"),
    2024: ("2024-03-20", "2024-09-29"),
    2025: ("2025-03-27", "2025-09-28"),
    2026: ("2026-03-26", "2026-09-27"),
}

# Expected completed-game counts per season (games actually played).
# 2022 and 2023: full 2,430 (30 teams × 162 / 2).
# 2024: 2,427 — three end-of-season games never played:
#   game_pk 746577  2024-09-29  HOU @ CLE  — Cancelled (season finale)
#   game_pk 747139  2024-09-30  NYM @ ATL  — Postponed, never made up
#   game_pk 747064  2024-09-30  NYM @ ATL  — Postponed, never made up (DH)
# ATL and NYM each played 160 games; CLE and HOU each played 161.
# 2025: 2,430 assumed (full 162-game schedule; adjust if final count differs).
EXPECTED_GAME_COUNTS = {2022: 2430, 2023: 2430, 2024: 2427, 2025: 2430, 2026: 2430}

DOME_TEAMS        = {"TBR"}
RETRACTABLE_TEAMS = {"TOR", "HOU", "TEX", "MIA", "MIL", "ARI"}

# Roof-status weather policy:
# Dome parks (TBR): always neutral — correct.
# Retractable-roof parks (ARI, HOU, TEX, TOR, MIA, MIL): historical open/closed
# status is not available game-by-game from any reliable free source. Using
# fetched outdoor weather for these games would silently corrupt training rows
# where the roof was actually closed. Policy: neutralize all retractable-roof
# games (72°F, 0 wind) until per-game roof status can be sourced. The outdoor
# weather cache is preserved on disk for a future Phase 2 enrichment pass.
RETRACTABLE_WEATHER_NEUTRAL = True  # set False only once per-game roof data added

# Approximate UTC offset during MLB season (DST active Apr–Oct)
STADIUM_UTC_OFFSET = {
    "BOS": -4, "NYY": -4, "TBR": -4, "TOR": -4, "BAL": -4,
    "CHW": -5, "CLE": -4, "DET": -4, "KCR": -5, "MIN": -5,
    "HOU": -5, "LAA": -7, "OAK": -7, "SEA": -7, "TEX": -5,
    "ATL": -4, "MIA": -4, "NYM": -4, "PHI": -4, "WSN": -4,
    "CHC": -5, "CIN": -4, "MIL": -5, "PIT": -4, "STL": -5,
    "ARI": -7, "COL": -6, "LAD": -7, "SDP": -7, "SFG": -7,
}

# ── HTTP helpers ───────────────────────────────────────────────────────────────

def _get(url: str, params: dict = None, retries: int = 4, base_delay: float = 1.5) -> dict | None:
    """GET with exponential backoff retry."""
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=30)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                wait = base_delay * (2 ** attempt)
                print(f"  [rate limit] sleeping {wait:.0f}s ...", file=sys.stderr)
                time.sleep(wait)
                continue
            print(f"  [HTTP {r.status_code}] {url}", file=sys.stderr)
            return None
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(base_delay * (2 ** attempt))
            else:
                print(f"  [request failed] {e}", file=sys.stderr)
                return None
    return None


def _cache_path(name: str) -> Path:
    return CACHE_DIR / f"{name}.json"

def _load_cache(name: str):
    p = _cache_path(name)
    if p.exists():
        return json.loads(p.read_text())
    return None

def _save_cache(name: str, data) -> None:
    _cache_path(name).write_text(json.dumps(data, default=str))


# ── MLB Stats API ──────────────────────────────────────────────────────────────

def fetch_season_schedule(year: int) -> list[dict]:
    """
    Fetch all regular-season games for a year in monthly chunks.
    Caches each chunk separately; returns flat list of raw game dicts.
    """
    cached = _load_cache(f"schedule_{year}_full")
    if cached is not None:
        print(f"  [cache] schedule_{year} ({len(cached):,} games)")
        return cached

    start_str, end_str = SEASON_WINDOWS[year]
    start_dt = datetime.fromisoformat(start_str)
    end_dt   = datetime.fromisoformat(end_str)

    chunks = []
    cur = start_dt
    while cur <= end_dt:
        month_end = (cur.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        chunk_end = min(month_end, end_dt)
        chunks.append((cur.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d")))
        cur = chunk_end + timedelta(days=1)

    all_games = []
    for chunk_start, chunk_end in chunks:
        chunk_key = f"schedule_{year}_{chunk_start[:7]}"
        cached_chunk = _load_cache(chunk_key)
        if cached_chunk is not None:
            all_games.extend(cached_chunk)
            continue

        print(f"  Fetching {year} {chunk_start} → {chunk_end} ...", end=" ", flush=True)
        data = _get(f"{MLB_API}/schedule", params={
            "sportId":  1,
            "gameType": "R",
            "startDate": chunk_start,
            "endDate":   chunk_end,
            "hydrate":  "team,linescore,officials",
        })
        if not data:
            print("FAILED — skipping chunk", file=sys.stderr)
            continue

        games = [g for db in data.get("dates", []) for g in db.get("games", [])]
        _save_cache(chunk_key, games)
        all_games.extend(games)
        print(f"{len(games)} games")
        time.sleep(0.3)

    _save_cache(f"schedule_{year}_full", all_games)
    print(f"  Season {year}: {len(all_games):,} total games fetched")
    return all_games


def fetch_game_linescore(game_pk: int) -> dict | None:
    """Fetch per-inning linescore for a game. Caches per game_pk."""
    cache_key = f"ls_{game_pk}"
    cached = _load_cache(cache_key)
    if cached is not None:
        return cached
    data = _get(f"{MLB_API}/game/{game_pk}/linescore")
    if data:
        _save_cache(cache_key, data)
    time.sleep(0.08)
    return data


# ── Weather (Open-Meteo Archive) ───────────────────────────────────────────────

def fetch_historical_weather(game_pk: int, lat: float, lon: float,
                              date_str: str, game_hour_local: int) -> dict:
    """
    Pull hourly weather from Open-Meteo archive for a game date and stadium.
    Picks the hour closest to local first pitch. Caches per game_pk.
    """
    cache_key = f"wx_{game_pk}"
    cached = _load_cache(cache_key)
    if cached is not None:
        return cached

    NEUTRAL = {"temperature_f": 72.0, "wind_speed_mph": 0.0,
                "wind_direction_deg": 0.0, "source": "missing"}

    data = _get(WX_ARCHIVE, params={
        "latitude":         round(lat, 4),
        "longitude":        round(lon, 4),
        "start_date":       date_str,
        "end_date":         date_str,
        "hourly":           "temperature_2m,windspeed_10m,winddirection_10m",
        "wind_speed_unit":  "mph",
        "temperature_unit": "fahrenheit",
        "timezone":         "auto",
    })

    if not data or "hourly" not in data:
        _save_cache(cache_key, NEUTRAL)
        return NEUTRAL

    times = data["hourly"].get("time", [])
    temps = data["hourly"].get("temperature_2m", [])
    winds = data["hourly"].get("windspeed_10m", [])
    dirs  = data["hourly"].get("winddirection_10m", [])

    if not times:
        _save_cache(cache_key, NEUTRAL)
        return NEUTRAL

    target = game_hour_local % 24
    best_idx, best_diff = 0, 99
    for i, t in enumerate(times):
        try:
            h    = int(t.split("T")[1].split(":")[0])
            diff = min(abs(h - target), 24 - abs(h - target))
            if diff < best_diff:
                best_diff = diff
                best_idx  = i
        except Exception:
            continue

    def _val(lst, idx, default):
        v = lst[idx] if idx < len(lst) else None
        return default if (v is None or (isinstance(v, float) and math.isnan(v))) else v

    result = {
        "temperature_f":      _val(temps, best_idx, 72.0),
        "wind_speed_mph":     _val(winds, best_idx, 0.0),
        "wind_direction_deg": _val(dirs,  best_idx, 0.0),
        "source":             "archive",
    }
    _save_cache(cache_key, result)
    time.sleep(0.05)
    return result


# ── F5 total ───────────────────────────────────────────────────────────────────

def _f5_total(innings: list) -> float | None:
    """
    Return sum of home + away runs in the first 5 innings.

    Returns None (leave null) in any of these cases:
      - fewer than 5 innings present in the data
      - any of the first 5 innings has a null runs value (incomplete inning)

    This is strict by design: actual_f5_total should only be populated
    when 5 complete innings of run data are confirmed.
    """
    if not innings or len(innings) < 5:
        return None
    total = 0.0
    for inning in innings[:5]:
        h_runs = inning.get("home", {}).get("runs")
        a_runs = inning.get("away", {}).get("runs")
        if h_runs is None or a_runs is None:
            return None   # incomplete inning — do not infer
        total += h_runs + a_runs
    return total


# ── Parse one game ─────────────────────────────────────────────────────────────

_VALID_STATES = {"Final", "Game Over", "Completed Early"}

def parse_game(raw: dict, year: int) -> dict | None:
    """
    Parse one raw MLB Stats API game dict into a target row.
    Returns None for games to skip (non-final, postponed, unknown teams).
    """
    status = raw.get("status", {}).get("detailedState", "")
    if status not in _VALID_STATES:
        return None

    game_pk     = raw.get("gamePk")
    game_date   = raw.get("officialDate") or raw.get("gameDate", "")[:10]
    game_dt_utc = raw.get("gameDate", "")

    teams     = raw.get("teams", {})
    home_info = teams.get("home", {})
    away_info = teams.get("away", {})

    home_score = home_info.get("score")
    away_score = away_info.get("score")
    if home_score is None or away_score is None:
        return None

    home_id  = home_info.get("team", {}).get("id")
    away_id  = away_info.get("team", {}).get("id")
    home_abb = TEAM_ID_TO_ABB.get(home_id, "UNK")
    away_abb = TEAM_ID_TO_ABB.get(away_id, "UNK")
    if home_abb == "UNK" or away_abb == "UNK":
        return None  # Spring Training / All-Star exhibition

    venue    = raw.get("venue", {})
    venue_id = venue.get("id")
    venue_nm = venue.get("name", "")

    # Linescore — inline first, fall back to game-level call
    linescore = raw.get("linescore", {})
    innings   = linescore.get("innings", [])
    if not innings:
        ls = fetch_game_linescore(game_pk)
        if ls:
            innings = ls.get("innings", [])

    innings_played = len(innings)
    f5             = _f5_total(innings)

    # Umpire
    officials   = raw.get("officials", [])
    umpire_name = None
    umpire_id   = None
    for off in officials:
        if off.get("officialType") == "Home Plate":
            ump         = off.get("official", {})
            umpire_name = ump.get("fullName")
            umpire_id   = ump.get("id")
            break

    dh_flag  = 1 if raw.get("doubleHeader", "N") != "N" else 0
    game_num = raw.get("gameNumber", 1)

    game_hour_utc = 23  # default ~7pm ET
    if game_dt_utc:
        try:
            dt = datetime.fromisoformat(game_dt_utc.replace("Z", "+00:00"))
            game_hour_utc = dt.hour
        except Exception:
            pass

    return {
        "game_pk":          game_pk,
        "date":             game_date,
        "season":           year,
        "home_team":        home_abb,
        "away_team":        away_abb,
        "home_team_id":     home_id,
        "away_team_id":     away_id,
        # OUTCOME / TARGET fields
        "home_score":       int(home_score),
        "away_score":       int(away_score),
        "actual_total":     int(home_score) + int(away_score),
        "actual_f5_total":  f5,
        # PREGAME CONTEXT fields
        "venue_id":          venue_id,
        "venue_name":        venue_nm,
        "doubleheader_flag": dh_flag,
        "game_number":       game_num,
        "umpire_name":       umpire_name,
        "umpire_id":         umpire_id,
        # METADATA / AUDIT fields
        "game_hour_utc":    game_hour_utc,
        "innings_played":   innings_played,
        "completed_early":  (status == "Completed Early"),
    }


# ── Rest days ──────────────────────────────────────────────────────────────────

def compute_rest_days(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add home_rest_days and away_rest_days (days since team's last game).
    First game of season capped at 5. Doubleheader game 2 correctly gets 0.
    """
    df = df.sort_values(["date", "game_number"]).reset_index(drop=True)
    last_played: dict[str, str] = {}
    home_rest_list, away_rest_list = [], []

    for _, row in df.iterrows():
        d  = row["date"]
        ht = row["home_team"]
        at = row["away_team"]

        def _rest(team: str) -> int:
            if team not in last_played:
                return 5
            try:
                delta = (datetime.fromisoformat(d) -
                         datetime.fromisoformat(last_played[team])).days
                return min(delta, 5)
            except Exception:
                return 5

        home_rest_list.append(_rest(ht))
        away_rest_list.append(_rest(at))
        last_played[ht] = d
        last_played[at] = d

    df["home_rest_days"] = home_rest_list
    df["away_rest_days"] = away_rest_list
    return df


# ── Park + umpire enrichment ───────────────────────────────────────────────────

def enrich_park_and_umpire(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add park_factor_runs, park_factor_hr (100 = neutral integer scale from config),
    roof_status, park_id, and umpire columns.
    park_factor_hr uses the same value as park_factor_runs in Phase 1;
    Phase 2 will differentiate using Savant HR/barrel data.
    """
    pf_runs, pf_hr, roof_statuses, park_ids = [], [], [], []
    ump_over, ump_k = [], []

    for _, row in df.iterrows():
        ht = row["home_team"]
        st = STADIUMS.get(ht, {})

        pf = st.get("park_factor", 100)
        pf_runs.append(pf)
        pf_hr.append(pf)

        if st.get("dome"):
            roof = "dome"
        elif st.get("retractable_roof"):
            roof = "retractable"
        else:
            roof = "open"
        roof_statuses.append(roof)

        park_ids.append(row.get("venue_id") or ht)

        ump = get_umpire_rating(row.get("umpire_name") or "")
        ump_over.append(round(ump.get("runs_factor", 1.0), 4))
        ump_k.append(round(ump.get("k_tendency", 0.0), 4))

    df["park_factor_runs"] = pf_runs
    df["park_factor_hr"]   = pf_hr
    df["roof_status"]      = roof_statuses
    df["park_id"]          = park_ids
    df["umpire_over_rate"] = ump_over
    df["umpire_k_rate"]    = ump_k
    return df


# ── Weather enrichment ────────────────────────────────────────────────────────

def enrich_weather(df: pd.DataFrame, skip: bool = False) -> pd.DataFrame:
    """
    Fetch historical hourly weather from Open-Meteo archive per game.
    Dome parks always get neutral values (72°F, 0 wind).
    Retractable roof parks get actual fetched weather — Phase 2 will apply
    open/closed adjustments once historical roof status is available.
    skip=True sets all weather to neutral (fast build test without API calls).
    """
    temps, wind_spds, wind_dirs, local_hours = [], [], [], []
    n = len(df)

    for i, (_, row) in enumerate(df.iterrows()):
        if i % 200 == 0:
            print(f"\r  Weather: {i}/{n} ...", end="", flush=True)

        ht = row["home_team"]

        is_neutral = (
            row["roof_status"] == "dome"
            or (row["roof_status"] == "retractable" and RETRACTABLE_WEATHER_NEUTRAL)
            or skip
        )
        if is_neutral:
            temps.append(72.0)
            wind_spds.append(0.0)
            wind_dirs.append(0.0)
            local_hours.append(None)
            continue

        st  = STADIUMS.get(ht, {})
        lat = st.get("lat")
        lon = st.get("lon")

        if lat is None:
            temps.append(72.0)
            wind_spds.append(0.0)
            wind_dirs.append(0.0)
            local_hours.append(None)
            continue

        utc_offset  = STADIUM_UTC_OFFSET.get(ht, -4)
        local_hour  = (row["game_hour_utc"] + utc_offset) % 24
        local_hours.append(local_hour)

        wx = fetch_historical_weather(
            game_pk         = row["game_pk"],
            lat             = lat,
            lon             = lon,
            date_str        = row["date"],
            game_hour_local = local_hour,
        )
        temps.append(wx["temperature_f"])
        wind_spds.append(wx["wind_speed_mph"])
        wind_dirs.append(wx["wind_direction_deg"])

    print(f"\r  Weather: {n}/{n} done.      ")
    df["temperature"]     = temps
    df["wind_speed"]      = wind_spds
    df["wind_direction"]  = wind_dirs
    df["local_start_hour"] = local_hours   # audit metadata only
    return df


# ── Final column order ─────────────────────────────────────────────────────────

FINAL_COLS = [
    # identifiers
    "game_pk", "date", "season",
    # teams
    "home_team", "away_team",
    # OUTCOME / TARGET fields
    "home_score", "away_score", "actual_total", "actual_f5_total",
    # venue
    "venue_id", "venue_name", "park_id",
    # PREGAME CONTEXT — game state
    "home_rest_days", "away_rest_days", "doubleheader_flag", "game_number",
    # PREGAME CONTEXT — environment
    "temperature", "wind_speed", "wind_direction", "roof_status",
    # PREGAME CONTEXT — park
    "park_factor_runs", "park_factor_hr",
    # PREGAME CONTEXT — officials
    "umpire_name", "umpire_id", "umpire_over_rate", "umpire_k_rate",
    # METADATA / AUDIT (not model inputs)
    "game_hour_utc", "local_start_hour", "innings_played", "completed_early",
]


# ── Main build ────────────────────────────────────────────────────────────────

def build_game_table(seasons: list[int], skip_weather: bool = False) -> pd.DataFrame:
    season_frames = []

    for year in seasons:
        print(f"\n{'='*60}")
        print(f" Season {year}")
        print("="*60)

        raw_games = fetch_season_schedule(year)
        rows, skipped = [], 0

        for g in raw_games:
            row = parse_game(g, year)
            if row is None:
                skipped += 1
            else:
                rows.append(row)

        print(f"  Parsed {len(rows):,} games  |  skipped {skipped:,}")

        df_yr = pd.DataFrame(rows)

        # Deduplicate: postponed games appear in both original and makeup date
        before = len(df_yr)
        df_yr = (df_yr
                 .sort_values("date", ascending=False)
                 .drop_duplicates(subset=["game_pk"], keep="first")
                 .sort_values("date"))
        dupes_removed = before - len(df_yr)
        if dupes_removed:
            print(f"  Removed {dupes_removed} duplicate game_pks (rescheduled games)")

        df_yr = compute_rest_days(df_yr)
        season_frames.append(df_yr)

    df = pd.concat(season_frames, ignore_index=True)

    print(f"\n{'='*60}")
    print(" Enriching park factors and umpire ratings ...")
    df = enrich_park_and_umpire(df)

    print(" Fetching historical weather ...")
    df = enrich_weather(df, skip=skip_weather)

    present = [c for c in FINAL_COLS if c in df.columns]
    df = df[present]
    df.to_parquet(OUT_PATH, index=False)
    print(f"\n✓ Wrote {OUT_PATH}  ({len(df):,} rows × {len(present)} columns)")
    return df


# ── Data quality audit ────────────────────────────────────────────────────────

def run_audit(df: pd.DataFrame) -> None:
    SEP  = "=" * 64
    sep2 = "-" * 64

    print(f"\n{SEP}")
    print("  PHASE 1 — DATA QUALITY AUDIT")
    print(SEP)

    # ── 1. Row counts by season ───────────────────────────────────────────────
    print("\n── 1. Row counts by season ──")
    for yr, cnt in df.groupby("season").size().items():
        expected = EXPECTED_GAME_COUNTS.get(yr, 2430)
        delta = cnt - expected
        flag = f"  ✓" if delta == 0 else f"  ⚠ EXPECTED {expected} (delta {delta:+d})"
        print(f"  {yr}: {cnt:,} games{flag}")
    print(f"  Total: {len(df):,} games")

    # ── 2. Missing values ─────────────────────────────────────────────────────
    print(f"\n{sep2}")
    print("── 2. Missing values by column ──")
    # local_start_hour is intentionally null for dome+retractable games (neutralized weather)
    expected_null = {"local_start_hour": (df["roof_status"].isin(["dome","retractable"])).sum()}
    missing = df.isnull().sum()
    missing = missing[missing > 0]
    if missing.empty:
        print("  None ✓")
    else:
        printed = False
        for col, n in missing.sort_values(ascending=False).items():
            exp = expected_null.get(col, 0)
            unexpected = n - exp
            if unexpected == 0 and exp > 0:
                print(f"  {col:<30} {n:>5,}  (intentional — dome+retractable games) ✓")
            else:
                pct  = n / len(df) * 100
                flag = "  ⚠" if pct > 5 or unexpected > 0 else ""
                print(f"  {col:<30} {n:>5,}  ({pct:.1f}%){flag}")
                printed = True
        if not printed:
            pass  # all missing values were expected

    # ── 3. Duplicate game_pks ─────────────────────────────────────────────────
    print(f"\n{sep2}")
    dupes = df.duplicated(subset=["game_pk"]).sum()
    print(f"── 3. Duplicate game_pks: {dupes}")
    if dupes > 0:
        d = df[df.duplicated(subset=["game_pk"], keep=False)]
        print(d[["game_pk", "date", "home_team", "away_team"]].head(10).to_string(index=False))

    # ── 4. Impossible totals ──────────────────────────────────────────────────
    print(f"\n{sep2}")
    impossible = df[(df["actual_total"] < 1) | (df["actual_total"] > 30)]
    print(f"── 4. Impossible totals (<1 or >30): {len(impossible)}")
    if len(impossible) > 0:
        print(impossible[["game_pk", "date", "home_team", "away_team",
                           "actual_total"]].to_string(index=False))

    # ── 5. ROOF / WEATHER AUDIT ───────────────────────────────────────────────
    print(f"\n{sep2}")
    print("── 5. Roof status breakdown ──")
    for rs, cnt in df["roof_status"].value_counts().items():
        print(f"  {rs:<12} {cnt:,} games")

    # 5a. Dome/retractable teams missing roof_status
    expected_dome = df[df["home_team"].isin(DOME_TEAMS) & (df["roof_status"] != "dome")]
    expected_retr = df[df["home_team"].isin(RETRACTABLE_TEAMS) & (df["roof_status"] != "retractable")]
    if len(expected_dome):
        print(f"  ⚠ {len(expected_dome)} dome-team games not flagged as 'dome'")
    if len(expected_retr):
        print(f"  ⚠ {len(expected_retr)} retractable-team games not flagged as 'retractable'")
    if not len(expected_dome) and not len(expected_retr):
        print("  Dome/retractable classification consistent ✓")

    # 5b. Games with roof_status='closed' but non-neutral weather
    # (Phase 1 never sets 'closed' — this is a forward-looking data-integrity check)
    closed_games = df[df["roof_status"] == "closed"]
    if len(closed_games):
        bad_wx = closed_games[
            (closed_games["temperature"] != 72.0) |
            (closed_games["wind_speed"]  != 0.0)
        ]
        if len(bad_wx):
            print(f"  ⚠ {len(bad_wx)} 'closed' roof games have non-neutral weather values")
        else:
            print(f"  {len(closed_games)} 'closed' roof games all have neutral weather ✓")
    else:
        print("  No 'closed' roof_status games in Phase 1 data (expected — set in Phase 2)")

    # 5c. Retractable roof weather policy confirmation
    retr = df[df["roof_status"] == "retractable"]
    retr_neutral = ((retr["wind_speed"] == 0.0) & (retr["temperature"] == 72.0)).sum()
    retr_live    = len(retr) - retr_neutral
    policy = "NEUTRAL (RETRACTABLE_WEATHER_NEUTRAL=True)" if RETRACTABLE_WEATHER_NEUTRAL else "LIVE FETCHED"
    print(f"  Retractable policy: {policy}")
    print(f"  Retractable: {len(retr):,} games — {retr_neutral} neutral, {retr_live} live weather")
    if RETRACTABLE_WEATHER_NEUTRAL and retr_live > 0:
        print(f"  ⚠ {retr_live} retractable games still have non-neutral weather — check enrich_weather")
    elif RETRACTABLE_WEATHER_NEUTRAL and retr_live == 0:
        print(f"  All retractable games correctly neutralized ✓")

    # ── 6. F5 TOTAL AUDIT ─────────────────────────────────────────────────────
    print(f"\n{sep2}")
    print("── 6. actual_f5_total — missing rate by season ──")
    print("   (null only when <5 innings played or incomplete inning data)")
    for yr, grp in df.groupby("season"):
        n_miss = grp["actual_f5_total"].isnull().sum()
        n_tot  = len(grp)
        print(f"  {yr}: {n_miss:>4} missing / {n_tot:,}  ({n_miss/n_tot*100:.1f}%)")
    total_miss = df["actual_f5_total"].isnull().sum()
    print(f"  All:  {total_miss:>4} missing / {len(df):,}  ({total_miss/len(df)*100:.1f}%)")

    if "innings_played" in df.columns:
        # Show that all missing F5 correspond to <5 innings or 0 innings in data
        null_f5 = df[df["actual_f5_total"].isnull()]
        print(f"  innings_played distribution for null-F5 rows:")
        for inn, cnt in null_f5["innings_played"].value_counts().sort_index().items():
            print(f"    innings_played={inn}: {cnt} games")

    # ── 7. ACTUAL TOTAL DISTRIBUTION ─────────────────────────────────────────
    print(f"\n{sep2}")
    print("── 7. Actual total distribution — by season ──")
    print(f"  {'Season':<8} {'N':>5} {'Mean':>6} {'Std':>5} {'Min':>4} {'Median':>7} {'Max':>4}")
    for yr, grp in df.groupby("season"):
        at = grp["actual_total"]
        print(f"  {yr:<8} {len(at):>5} {at.mean():>6.2f} {at.std():>5.2f} "
              f"{at.min():>4} {at.median():>7.1f} {at.max():>4}")
    at_all = df["actual_total"]
    print(f"  {'All':<8} {len(at_all):>5} {at_all.mean():>6.2f} {at_all.std():>5.2f} "
          f"{at_all.min():>4} {at_all.median():>7.1f} {at_all.max():>4}")

    print(f"\n── 10 lowest-scoring games ──")
    low_cols = ["date", "season", "away_team", "home_team", "actual_total",
                "innings_played", "completed_early"]
    low_cols = [c for c in low_cols if c in df.columns]
    print(df.nsmallest(10, "actual_total")[low_cols].to_string(index=False))

    print(f"\n── 10 highest-scoring games ──")
    print(df.nlargest(10, "actual_total")[low_cols].to_string(index=False))

    if "innings_played" in df.columns:
        xi = (df["innings_played"] > 9).sum()
        print(f"\n── Extra-inning games (>9 inn played): {xi:,} "
              f"({xi/len(df)*100:.1f}%)")

    if "completed_early" in df.columns:
        ce = df["completed_early"].sum()
        print(f"── Games completed early: {ce:,} ({ce/len(df)*100:.1f}%)")

    # ── 8. TIMEZONE / WEATHER VALIDATION SAMPLE ───────────────────────────────
    print(f"\n{sep2}")
    print("── 8. Timezone / weather validation — 10 open-roof games ──")
    print("   (confirms UTC→local conversion and DST handling before weather as feature)")
    open_wx = df[df["roof_status"] == "open"].copy()
    if "local_start_hour" in df.columns and len(open_wx) >= 10:
        open_wx["utc_hour"] = open_wx["game_hour_utc"]
        open_wx["local_hour"] = open_wx["local_start_hour"]
        sample_cols = ["date", "home_team", "venue_name", "utc_hour",
                       "local_hour", "temperature", "wind_speed"]
        sample_cols = [c for c in sample_cols if c in open_wx.columns]
        sample = open_wx[sample_cols].dropna(subset=["local_hour"]).sample(
            10, random_state=7
        )
        # Format hours as HH:00 strings
        def _fmt_hour(h):
            try:
                h = int(h)
                return f"{h:02d}:00"
            except Exception:
                return "—"
        if "utc_hour" in sample.columns:
            sample = sample.copy()
            sample["utc_hour"]   = sample["utc_hour"].apply(_fmt_hour)
            sample["local_hour"] = sample["local_hour"].apply(_fmt_hour)
        print(sample.to_string(index=False))
    else:
        print("  (local_start_hour not present — re-run full build to populate)")

    # ── 9. Park factor coverage ───────────────────────────────────────────────
    print(f"\n{sep2}")
    print("── 9. Park factors ──")
    print(f"  Teams with park data: {df['home_team'].nunique()}/30")
    missing_pf = df[df["park_factor_runs"].isnull()]["home_team"].unique()
    if len(missing_pf):
        print(f"  ⚠ Missing: {list(missing_pf)}")
    else:
        print("  All 30 teams have park factors ✓")
    pf = df["park_factor_runs"]
    print(f"  Range: {pf.min()}–{pf.max()} (100 = neutral)")

    # ── 10. Umpire coverage ───────────────────────────────────────────────────
    print(f"\n{sep2}")
    ump_miss = df["umpire_name"].isnull().sum()
    print(f"── 10. Umpire assignments missing: {ump_miss:,} ({ump_miss/len(df)*100:.1f}%)")
    print(f"   Unique umpires found: {df['umpire_name'].nunique()}")

    # ── Sample rows ───────────────────────────────────────────────────────────
    print(f"\n{sep2}")
    print("── Sample rows (5 random games) ──")
    sample_cols = ["game_pk", "date", "season", "home_team", "away_team",
                   "actual_total", "actual_f5_total", "innings_played",
                   "temperature", "wind_speed", "umpire_name", "park_factor_runs"]
    sample_cols = [c for c in sample_cols if c in df.columns]
    try:
        print(df[sample_cols].sample(5, random_state=42).to_string(index=False))
    except Exception:
        print(df[sample_cols].head(5).to_string(index=False))

    print(f"\n{SEP}")
    print("  AUDIT COMPLETE")
    print(SEP)


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Phase 1: Build MLB game table")
    parser.add_argument("--seasons",    nargs="+", type=int,
                        default=[2022, 2023, 2024],
                        help="Seasons to include (default: 2022 2023 2024)")
    parser.add_argument("--audit-only", action="store_true",
                        help="Re-run audit on existing game_table.parquet")
    parser.add_argument("--no-weather", action="store_true",
                        help="Skip weather fetches (neutral values; fast test)")
    args = parser.parse_args()

    if args.audit_only:
        if not OUT_PATH.exists():
            print(f"ERROR: {OUT_PATH} not found. Run without --audit-only first.")
            import sys; sys.exit(1)
        df = pd.read_parquet(OUT_PATH)
        print(f"Loaded {len(df):,} rows from {OUT_PATH}")
        run_audit(df)
        return

    df = build_game_table(args.seasons, skip_weather=args.no_weather)
    run_audit(df)


if __name__ == "__main__":
    main()
