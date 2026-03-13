"""
Pitcher metrics module — fetches xFIP and SIERA from FanGraphs API
and xERA from Baseball Savant.

Results are cached for the day to avoid redundant API calls.
Stats are regressed toward league average using batters-faced as sample weight,
then blended 70% current year / 30% prior year.
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

_CACHE_FILE = os.path.join(CACHE_DIR, f"pitchers_v2_{date.today().isoformat()}.json")

FANGRAPHS_PITCHING_URL = "https://www.fangraphs.com/api/leaders/major-league/data"
SAVANT_PITCHER_URL     = (
    "https://baseballsavant.mlb.com/leaderboard/expected_statistics"
    "?type=pitcher&year={year}&position=&team=&min=10&csv=true"
)

_HTML_NAME_RE = re.compile(r">([^<]+)</a>")

# Regression prior strength: pitcher needs this many BF before stats are fully trusted
_REGRESSION_BF = 300


def _strip_html(name: str) -> str:
    m = _HTML_NAME_RE.search(name)
    return m.group(1).strip() if m else name.strip()


def _load_cache() -> dict:
    if os.path.exists(_CACHE_FILE):
        try:
            with open(_CACHE_FILE) as f:
                data = json.load(f)
            # Only accept v2 caches that have already been regressed
            if data.get("_meta", {}).get("regressed"):
                return data
        except Exception:
            pass
    return {}


def _save_cache(data: dict) -> None:
    with open(_CACHE_FILE, "w") as f:
        json.dump(data, f)


def _regress_stat(stat: float, bf: int) -> float:
    """
    Bayesian regression toward league average.
    regressed = (stat * BF + LEAGUE_AVG * 300) / (BF + 300)
    If BF < 30, return league average entirely.
    """
    if bf < 30:
        return LEAGUE_AVG_ERA
    return (stat * bf + LEAGUE_AVG_ERA * _REGRESSION_BF) / (bf + _REGRESSION_BF)


def _blend_pitcher_entry(cur: dict, prior: Optional[dict]) -> dict:
    """
    Apply BF-based regression to current year stats, then blend
    70% current / 30% prior year (if prior year data is available).
    """
    cur_bf   = cur.get("bf", 0) or 0
    cur_xfip = _regress_stat(cur.get("xfip",  LEAGUE_AVG_ERA), cur_bf)
    cur_siera= _regress_stat(cur.get("siera", LEAGUE_AVG_ERA), cur_bf)
    cur_era  = _regress_stat(cur.get("era",   LEAGUE_AVG_ERA), cur_bf)

    if prior:
        pri_bf    = prior.get("bf", 0) or 0
        pri_xfip  = _regress_stat(prior.get("xfip",  LEAGUE_AVG_ERA), pri_bf)
        pri_siera = _regress_stat(prior.get("siera", LEAGUE_AVG_ERA), pri_bf)
        pri_era   = _regress_stat(prior.get("era",   LEAGUE_AVG_ERA), pri_bf)
        xfip  = 0.7 * cur_xfip  + 0.3 * pri_xfip
        siera = 0.7 * cur_siera + 0.3 * pri_siera
        era   = 0.7 * cur_era   + 0.3 * pri_era
    else:
        xfip, siera, era = cur_xfip, cur_siera, cur_era

    # IP/start: prefer current year (if >= 3 GS), else prior year, else None (-> 5.5 default)
    avg_ip = cur.get("avg_ip_per_start")
    if avg_ip is None and prior:
        avg_ip = prior.get("avg_ip_per_start")

    result = dict(cur)
    result.update({
        "xfip":              round(max(2.0, min(xfip,  7.0)), 3),
        "siera":             round(max(2.0, min(siera, 7.0)), 3),
        "era":               round(max(2.0, min(era,   7.0)), 3),
        "avg_ip_per_start":  avg_ip,
        "regressed":         True,
    })
    return result


def _fetch_fangraphs_pitching(year: int) -> dict:
    """
    Pull FanGraphs advanced pitching leaderboard (type=8).
    Returns name -> {xfip, siera, era, ip, bf, gs, team, mlbam_id, avg_ip_per_start}.
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
        raw_name = row.get("Name", "") or row.get("PlayerName", "")
        name     = _strip_html(raw_name)
        mlbam_id = row.get("xMLBAMID") or row.get("mlbamid")
        fg_id    = str(row.get("playerid", ""))

        xfip  = row.get("xFIP")
        siera = row.get("SIERA")
        era   = row.get("ERA")
        ip    = row.get("IP")
        tbf   = row.get("TBF") or row.get("BF") or 0
        gs    = int(float(row.get("GS") or 0))
        team  = str(row.get("Team") or "").upper().strip()

        ip_val = float(ip) if ip is not None else 0.0
        bf_val = int(float(tbf)) if tbf else 0

        # IP per start: only meaningful for pitchers with 3+ starts
        avg_ip = round(ip_val / gs, 2) if gs >= 3 else None
        if avg_ip is not None:
            avg_ip = max(3.0, min(avg_ip, 7.5))  # clamp outliers

        mid_str = str(int(mlbam_id)) if mlbam_id else None

        entry = {
            "xfip":              float(xfip)  if xfip  is not None else LEAGUE_AVG_ERA,
            "siera":             float(siera) if siera is not None else LEAGUE_AVG_ERA,
            "era":               float(era)   if era   is not None else LEAGUE_AVG_ERA,
            "ip":                ip_val,
            "bf":                bf_val,
            "gs":                gs,
            "team":              team,
            "mlbam_id":          mid_str,
            "avg_ip_per_start":  avg_ip,
        }

        if name:
            db[name.lower()] = entry
        if mid_str:
            db[mid_str] = entry
        if fg_id:
            db[f"fg:{fg_id}"] = entry

    logger.info(f"FanGraphs: loaded {len(rows)} pitchers for {year}")
    return db


def _fetch_savant_pitching(year: int) -> dict:
    """
    Pull Baseball Savant xERA as a stand-alone pitcher quality metric.
    BF is sourced from Savant's 'pa' column.
    """
    try:
        url = SAVANT_PITCHER_URL.format(year=year)
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        df = pd.read_csv(StringIO(resp.text))
    except Exception as e:
        logger.warning(f"Savant pitcher CSV failed: {e}")
        return {}

    MIN_PA    = 30
    MAX_METRIC = 7.0

    db: dict = {}
    for _, row in df.iterrows():
        pa = row.get("pa") or 0
        if float(pa) < MIN_PA:
            continue

        raw_name = str(row.get("last_name, first_name", "") or "")
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
            "xfip":             xera_val,
            "siera":            xera_val,
            "era":              era_val,
            "ip":               0.0,
            "bf":               int(float(pa)),
            "gs":               None,   # not available from Savant leaderboard
            "team":             "",
            "mlbam_id":         pid if pid != "0" else None,
            "avg_ip_per_start": None,
        }

        if name:
            db[name.lower()] = entry
        if pid and pid != "0":
            db[pid] = entry

    logger.info(f"Savant: loaded {len(db)//2} pitchers (xERA) for {year}")
    return db


def build_pitcher_db(year: Optional[int] = None) -> dict:
    """
    Build pitcher lookup dict with regression + year blending applied.
    Keys: name (lowercase), mlbam_id (str), fg:<id>
    Falls back to prior year if current year has no data.
    Blends 70% current / 30% prior year after BF-based regression.
    """
    if year is None:
        year = date.today().year

    cache = _load_cache()
    if cache:
        return {k: v for k, v in cache.items() if k != "_meta"}

    # --- Fetch current year ---
    cur_db: dict = {}
    cur_year = year
    for attempt_year in [year, year - 1]:
        logger.info(f"Fetching pitcher stats (FanGraphs) for {attempt_year}...")
        cur_db = _fetch_fangraphs_pitching(attempt_year)
        if cur_db:
            cur_year = attempt_year
            # Enrich with Savant xERA
            savant = _fetch_savant_pitching(attempt_year)
            for k, v in savant.items():
                if k in cur_db:
                    cur_db[k]["xera"] = v.get("xfip")
            break

    if not cur_db:
        for attempt_year in [year, year - 1]:
            logger.info(f"Falling back to Savant xERA for {attempt_year}...")
            cur_db = _fetch_savant_pitching(attempt_year)
            if cur_db:
                cur_year = attempt_year
                break

    if not cur_db:
        logger.warning("Pitcher DB empty — league averages will be used as fallback")
        return {}

    # --- Fetch prior year for blending ---
    prior_db: dict = {}
    prior_year = cur_year - 1
    logger.info(f"Fetching prior year pitcher stats for {prior_year} (for 70/30 blend)...")
    prior_db = _fetch_fangraphs_pitching(prior_year)
    if not prior_db:
        prior_db = _fetch_savant_pitching(prior_year)

    # --- Build blended + regressed DB ---
    all_keys = set(cur_db.keys()) | set(prior_db.keys())
    blended: dict = {}
    for key in all_keys:
        if key == "_meta":
            continue
        cur   = cur_db.get(key)
        prior = prior_db.get(key)
        if cur:
            blended[key] = _blend_pitcher_entry(cur, prior)
        else:
            # Pitcher only in prior year — regress heavily, no current data
            blended[key] = _blend_pitcher_entry(prior, None)

    blended["_meta"] = {"regressed": True, "year": cur_year}
    _save_cache(blended)
    logger.info(f"Pitcher DB built: {len(blended)-1} entries (year={cur_year}, prior={prior_year})")

    return {k: v for k, v in blended.items() if k != "_meta"}


def get_pitcher_metrics(pitcher_info: dict, pitcher_db: dict) -> dict:
    """
    Resolve a pitcher's metrics from the DB.
    Returns regressed+blended xFIP, SIERA, and avg_ip_per_start.
    Falls back to league average if not found.
    """
    name = pitcher_info.get("name", "TBD")
    pid  = str(pitcher_info.get("id") or "")

    default = {
        "name":              name,
        "xfip":              LEAGUE_AVG_ERA,
        "siera":             LEAGUE_AVG_ERA,
        "era":               LEAGUE_AVG_ERA,
        "ip":                0.0,
        "bf":                0,
        "gs":                0,
        "avg_ip_per_start":  None,   # -> will use 5.5 default in projection
        "source":            "default",
    }

    if not name or name == "TBD":
        return default

    def _clamp(entry: dict) -> dict:
        for k in ("xfip", "siera", "era"):
            v = entry.get(k, LEAGUE_AVG_ERA)
            entry[k] = max(2.0, min(float(v), 7.0)) if v else LEAGUE_AVG_ERA
        return entry

    def _enrich(entry: dict, source: str) -> dict:
        e = _clamp(dict(entry))
        e.update({"name": name, "source": source})
        e.setdefault("avg_ip_per_start", None)
        return e

    # By MLBAM ID (most reliable)
    if pid and pid in pitcher_db:
        return _enrich(pitcher_db[pid], "id-match")

    # By exact lowercased name
    key = name.lower()
    if key in pitcher_db:
        return _enrich(pitcher_db[key], "name-exact")

    # By last name (skip if multiple matches)
    last = key.split()[-1] if " " in key else key
    matches = [(k, v) for k, v in pitcher_db.items()
               if not k.startswith(("fg:", "savant:")) and not k.isdigit() and k.endswith(last)]
    if len(matches) == 1:
        return _enrich(matches[0][1], "name-partial")

    logger.debug(f"Pitcher not found: '{name}' (id={pid}) — using league average")
    return default
