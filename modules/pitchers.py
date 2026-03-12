"""
Pitcher metrics module — fetches xFIP and SIERA from FanGraphs API
and xERA from Baseball Savant.

Results are cached for the day to avoid redundant API calls.
"""

import logging
import os
import re
import json
from datetime import date
from typing import Optional
from io import StringIO

import pandas as pd
import requests

from config import CACHE_DIR, LEAGUE_AVG_ERA

logger = logging.getLogger(__name__)

_CACHE_FILE = os.path.join(CACHE_DIR, f"pitchers_{date.today().isoformat()}.json")

FANGRAPHS_PITCHING_URL = "https://www.fangraphs.com/api/leaders/major-league/data"
SAVANT_PITCHER_URL     = (
    "https://baseballsavant.mlb.com/leaderboard/expected_statistics"
    "?type=pitcher&year={year}&position=&team=&min=10&csv=true"
)

_HTML_NAME_RE = re.compile(r">([^<]+)</a>")


def _strip_html(name: str) -> str:
    """Extract plain text from FanGraphs HTML-wrapped name."""
    m = _HTML_NAME_RE.search(name)
    return m.group(1).strip() if m else name.strip()


def _load_cache() -> dict:
    if os.path.exists(_CACHE_FILE):
        with open(_CACHE_FILE) as f:
            return json.load(f)
    return {}


def _save_cache(data: dict) -> None:
    with open(_CACHE_FILE, "w") as f:
        json.dump(data, f)


def _fetch_fangraphs_pitching(year: int) -> dict:
    """
    Pull FanGraphs advanced pitching leaderboard (type=8).
    Returns name → {xfip, siera, era, ip, mlbam_id}.
    """
    params = {
        "age": 0, "pos": "all", "stats": "pit", "lg": "all",
        "qual": 0, "season": year, "season1": year, "ind": 0,
        "team": 0, "pageitems": 2000, "pagenum": 1, "type": 8,
    }
    headers = {
        "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"),
        "Referer": "https://www.fangraphs.com/leaders/major-league",
    }

    try:
        resp = requests.get(FANGRAPHS_PITCHING_URL, params=params,
                            headers=headers, timeout=30)
        resp.raise_for_status()
        rows = resp.json().get("data", [])
    except Exception as e:
        logger.error(f"FanGraphs pitching fetch failed: {e}")
        return {}

    db: dict = {}
    for row in rows:
        raw_name  = row.get("Name", "") or row.get("PlayerName", "")
        name      = _strip_html(raw_name)
        mlbam_id  = row.get("xMLBAMID") or row.get("mlbamid")
        fg_id     = str(row.get("playerid", ""))

        xfip  = row.get("xFIP")
        siera = row.get("SIERA")
        era   = row.get("ERA")
        ip    = row.get("IP")

        entry = {
            "xfip":  float(xfip)  if xfip  is not None else LEAGUE_AVG_ERA,
            "siera": float(siera) if siera is not None else LEAGUE_AVG_ERA,
            "era":   float(era)   if era   is not None else LEAGUE_AVG_ERA,
            "ip":    float(ip)    if ip    is not None else 0.0,
        }

        if name:
            db[name.lower()] = entry
        if mlbam_id:
            db[str(int(mlbam_id))] = entry
        if fg_id:
            db[f"fg:{fg_id}"] = entry

    logger.info(f"FanGraphs: loaded {len(rows)} pitchers")
    return db


def _fetch_savant_pitching(year: int) -> dict:
    """
    Pull Baseball Savant xERA as a stand-alone pitcher quality metric.
    Returns name (lowered) + mlbam_id → {xfip, siera, era, ip} compatible dict.
    xERA is used as proxy for both xFIP and SIERA when FanGraphs is unavailable.
    """
    try:
        url = SAVANT_PITCHER_URL.format(year=year)
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        df = pd.read_csv(StringIO(resp.text))
    except Exception as e:
        logger.warning(f"Savant pitcher CSV failed: {e}")
        return {}

    MIN_PA    = 30    # ignore pitchers with fewer than 30 plate appearances
    MAX_METRIC = 7.0  # cap extreme outliers (e.g., 1-inning callups)

    db: dict = {}
    for _, row in df.iterrows():
        pa = row.get("pa") or 0
        if float(pa) < MIN_PA:
            continue

        raw_name = str(row.get("last_name, first_name", "") or "")
        # Savant format: "Last, First" → convert to "First Last"
        if "," in raw_name:
            parts = [p.strip() for p in raw_name.split(",", 1)]
            name = f"{parts[1]} {parts[0]}" if len(parts) == 2 else raw_name
        else:
            name = raw_name

        pid  = str(int(row.get("player_id", 0) or 0))
        xera = row.get("xera")
        era  = row.get("era")

        xera_val = min(float(xera), MAX_METRIC) if pd.notna(xera) else LEAGUE_AVG_ERA
        era_val  = min(float(era),  MAX_METRIC) if pd.notna(era)  else LEAGUE_AVG_ERA

        entry = {
            "xfip":  xera_val,   # xERA is our best free proxy for xFIP
            "siera": xera_val,   # same for SIERA
            "era":   era_val,
            "ip":    0.0,
        }

        if name:
            db[name.lower()] = entry
        if pid and pid != "0":
            db[pid] = entry

    logger.info(f"Savant: loaded {len(db)//2} pitchers (xERA)")
    return db


def build_pitcher_db(year: Optional[int] = None) -> dict:
    """
    Build a lookup dict:
      name (lowercase)   → {xfip, siera, era, ip}
      mlbam_id (str)     → same
    Falls back to prior year if current year has no data (pre-season).
    """
    if year is None:
        year = date.today().year

    cache = _load_cache()
    if cache:
        return cache

    # Strategy: FanGraphs has xFIP+SIERA; Savant has xERA (good proxy).
    # Try FanGraphs first; fall back to Savant if blocked/unavailable.
    db: dict = {}
    for attempt_year in [year, year - 1]:
        logger.info(f"Fetching pitcher stats (FanGraphs) for {attempt_year}...")
        db = _fetch_fangraphs_pitching(attempt_year)
        if db:
            savant = _fetch_savant_pitching(attempt_year)
            # Enrich FanGraphs entries with Savant xERA where available
            for k, v in savant.items():
                if k in db:
                    db[k]["xera"] = v.get("era")
            break

    if not db:
        # FanGraphs fully blocked — use Savant xERA as primary source
        for attempt_year in [year, year - 1]:
            logger.info(f"Falling back to Savant xERA for {attempt_year}...")
            db = _fetch_savant_pitching(attempt_year)
            if db:
                break

    if not db:
        logger.warning("Pitcher DB empty — league averages will be used as fallback")
    else:
        _save_cache(db)
        logger.info(f"Cached {len(db)} pitcher entries")

    return db


def get_pitcher_metrics(pitcher_info: dict, pitcher_db: dict) -> dict:
    """
    Resolve a pitcher's xFIP and SIERA from the DB.
    Falls back to league average if not found.

    pitcher_info: {"id": mlbam_id, "name": "Full Name"}
    """
    name = pitcher_info.get("name", "TBD")
    pid  = str(pitcher_info.get("id") or "")

    default = {
        "name":   name,
        "xfip":   LEAGUE_AVG_ERA,
        "siera":  LEAGUE_AVG_ERA,
        "era":    LEAGUE_AVG_ERA,
        "ip":     0.0,
        "source": "default",
    }

    if not name or name == "TBD":
        return default

    def _clamp(entry: dict) -> dict:
        """Cap extreme xFIP/SIERA values; return league avg if too small sample."""
        for k in ("xfip", "siera", "era"):
            v = entry.get(k, LEAGUE_AVG_ERA)
            entry[k] = max(2.0, min(float(v), 7.0)) if v else LEAGUE_AVG_ERA
        return entry

    # By MLBAM ID (most reliable)
    if pid and pid in pitcher_db:
        entry = _clamp(dict(pitcher_db[pid]))
        entry.update({"name": name, "source": "id-match"})
        return entry

    # By exact lowercased name
    key = name.lower()
    if key in pitcher_db:
        entry = _clamp(dict(pitcher_db[key]))
        entry.update({"name": name, "source": "name-exact"})
        return entry

    # By last name (less reliable; skip if multiple matches)
    last = key.split()[-1] if " " in key else key
    matches = [(k, v) for k, v in pitcher_db.items()
               if not k.startswith(("fg:", "savant:")) and k.endswith(last)]
    if len(matches) == 1:
        entry = _clamp(dict(matches[0][1]))
        entry.update({"name": name, "source": "name-partial"})
        return entry

    logger.debug(f"Pitcher not found: '{name}' (id={pid}) — using league average")
    return default
