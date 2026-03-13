"""
Props data module — pitcher K stats and batter TB stats.

Sources:
  - pybaseball (FanGraphs via scraper): K/9, K%, GB%, SwStr% for pitchers;
    SLG, xSLG, xBA, Barrel%, HardHit%, EV, wRC+ for batters
  - Falls back to prior year if current year has < 50 rows (spring training)

All data cached to data/cache/props_*.json with 24-hour TTL.
Fails gracefully — returns empty dict if sources are unavailable.
"""

import json
import logging
import os
from datetime import date, datetime, timedelta
from typing import Optional

from config import CACHE_DIR

logger = logging.getLogger(__name__)

LEAGUE_AVG_K_RATE  = 0.224   # team K rate (batters striking out)
LEAGUE_AVG_SWSTR   = 0.112   # pitcher swing-and-miss rate
LEAGUE_AVG_GB_PCT  = 0.440   # pitcher ground ball rate
LEAGUE_AVG_K9      = 8.9     # pitcher K/9 league average

# FanGraphs team abbreviation normalisation (pybaseball uses same FG abbrevs)
_FG_TEAM_MAP = {
    "WSH": "WSN", "TB": "TBR", "KC": "KCR", "SF": "SFG",
    "SD": "SDP", "CWS": "CHW", "ANA": "LAA", "ATH": "OAK",
}


def _norm_team(t: str) -> str:
    return _FG_TEAM_MAP.get((t or "").upper().strip(), (t or "").upper().strip())


def _stats_year() -> int:
    """Use last season's stats during spring training (before May 1)."""
    n = date.today()
    return n.year - 1 if n.month < 5 else n.year


def _cache_path(key: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"props_{key}.json")


def _load_cache(key: str, ttl_hours: int = 24):
    path = _cache_path(key)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            data = json.load(f)
        cached_at = datetime.fromisoformat(data.get("cached_at", "2000-01-01"))
        if datetime.now() - cached_at > timedelta(hours=ttl_hours):
            return None
        return data.get("payload")
    except Exception:
        return None


def _save_cache(key: str, payload) -> None:
    try:
        with open(_cache_path(key), "w") as f:
            json.dump({"cached_at": datetime.now().isoformat(), "payload": payload}, f)
    except Exception:
        pass


def _pct(val, raw_is_0_to_100: bool = True) -> float:
    """Normalise a percentage value to 0.0–1.0."""
    v = float(val or 0)
    return v / 100 if (raw_is_0_to_100 and v > 1.0) else v


# ── Pitcher K database ─────────────────────────────────────────────────────────

def _fetch_pitcher_stats(year: int) -> dict:
    """Fetch pitcher stats via pybaseball (FanGraphs scraper)."""
    try:
        from pybaseball import pitching_stats
        df = pitching_stats(year, qual=1)
    except Exception as e:
        logger.warning(f"pybaseball pitching_stats({year}) failed: {e}")
        return {}

    if df is None or len(df) == 0:
        return {}

    db = {}
    for _, row in df.iterrows():
        name = str(row.get("Name") or "").strip()
        if not name:
            continue
        team   = _norm_team(str(row.get("Team") or ""))
        ip     = float(row.get("IP") or 0)
        gs     = int(float(row.get("GS") or 0))
        k9     = float(row.get("K/9") or 0)
        k_pct  = _pct(row.get("K%", 0))
        gb_pct = _pct(row.get("GB%", 0))
        swstr  = _pct(row.get("SwStr%", 0))

        # Use default IP if pitcher has fewer than 5 starts or raw value is
        # implausible (reliever-heavy stint or data anomaly).
        if gs >= 5:
            raw_ip_per_start = round(ip / gs, 2)
            avg_ip = raw_ip_per_start if 3.0 <= raw_ip_per_start <= 7.5 else 5.5
        else:
            avg_ip = 5.5

        db[name.lower()] = {
            "name":             name,
            "team":             team,
            "k_per_9":          k9,
            "k_pct":            k_pct,
            "gb_pct":           gb_pct if gb_pct > 0 else LEAGUE_AVG_GB_PCT,
            "ip":               ip,
            "gs":               gs,
            "avg_ip_per_start": avg_ip,
            "swstr_pct":        swstr if swstr > 0 else LEAGUE_AVG_SWSTR,
        }

    logger.info(f"pybaseball pitcher DB: {len(db)} pitchers for {year}")
    return db


def build_pitcher_k_db() -> dict:
    """
    Build pitcher K database. Returns dict keyed by name.lower().
    Falls back to previous year if current year has no data.
    """
    year      = _stats_year()
    cache_key = f"pitcher_k_{year}"
    cached    = _load_cache(cache_key)
    if cached is not None:
        return cached

    db = {}
    for attempt_year in [year, year - 1]:
        db = _fetch_pitcher_stats(attempt_year)
        if len(db) >= 50:
            break

    if db:
        _save_cache(cache_key, db)
    return db


# ── Batter props database ──────────────────────────────────────────────────────

def _fetch_batter_stats(year: int) -> dict:
    """Fetch batter stats via pybaseball (FanGraphs scraper)."""
    try:
        from pybaseball import batting_stats
        df = batting_stats(year, qual=10)
    except Exception as e:
        logger.warning(f"pybaseball batting_stats({year}) failed: {e}")
        return {}

    if df is None or len(df) == 0:
        return {}

    db = {}
    for _, row in df.iterrows():
        name = str(row.get("Name") or "").strip()
        if not name:
            continue
        team = _norm_team(str(row.get("Team") or ""))
        pa   = int(float(row.get("PA") or 0))
        if pa < 10:
            continue

        # xSLG: pybaseball column is "xSLG"
        xslg_raw = row.get("xSLG")
        xslg     = float(xslg_raw) if xslg_raw is not None and str(xslg_raw) != "nan" else None

        xba_raw  = row.get("xBA")
        xba      = float(xba_raw)  if xba_raw  is not None and str(xba_raw)  != "nan" else None

        # Barrel%: column is "Barrel%" — already a percentage (e.g. 8.3 means 8.3%)
        brrl_raw = row.get("Barrel%")
        barrel   = _pct(brrl_raw) if brrl_raw is not None and str(brrl_raw) != "nan" else None

        # HardHit%: column "HardHit%" or "Hard%"
        hard_raw = row.get("HardHit%") or row.get("Hard%")
        hard     = _pct(hard_raw) if hard_raw is not None and str(hard_raw) != "nan" else None

        # Exit velocity: column "EV"
        ev_raw   = row.get("EV")
        ev       = float(ev_raw) if ev_raw is not None and str(ev_raw) != "nan" else None

        db[name.lower()] = {
            "name":          name,
            "team":          team,
            "pa":            pa,
            "slg":           float(row.get("SLG") or 0),
            "k_pct":         _pct(row.get("K%", 0)),
            "bb_pct":        _pct(row.get("BB%", 0)),
            "wrc_plus":      float(row.get("wRC+") or 100),
            "xslg":          xslg,
            "xba":           xba,
            "barrel_pct":    barrel,
            "hard_pct":      hard,
            "avg_exit_velo": ev,
        }

    logger.info(f"pybaseball batter DB: {len(db)} batters for {year}")
    return db


def build_batter_props_db() -> dict:
    """
    Build batter props database. Returns dict keyed by name.lower().
    Falls back to previous year if current year has no data.
    """
    year      = _stats_year()
    cache_key = f"batter_props_{year}"
    cached    = _load_cache(cache_key)
    if cached is not None:
        return cached

    db = {}
    for attempt_year in [year, year - 1]:
        db = _fetch_batter_stats(attempt_year)
        if len(db) >= 50:
            break

    if db:
        _save_cache(cache_key, db)
    return db


# ── Lookup helpers ─────────────────────────────────────────────────────────────

def get_pitcher_k_profile(name: str, k_db: dict) -> Optional[dict]:
    """Resolve pitcher by name with fuzzy fallback."""
    if not name or name == "TBD" or not k_db:
        return None
    key = name.lower()
    if key in k_db:
        return k_db[key]
    # Last name fallback
    parts = key.split()
    if parts:
        last = parts[-1]
        candidates = [(k, v) for k, v in k_db.items() if k.endswith(last)]
        if len(candidates) == 1:
            return candidates[0][1]
    return None


def get_team_top_batters(team_abb: str, batter_db: dict, n: int = 3) -> list[dict]:
    """Return top N batters for a team ranked by TB potential (xSLG primary)."""
    batters = [
        b for b in batter_db.values()
        if b.get("team", "").upper() == team_abb.upper() and b.get("pa", 0) >= 20
    ]

    def _score(b: dict) -> float:
        xslg   = b.get("xslg") or b.get("slg") or 0
        barrel = (b.get("barrel_pct") or 0) * 3
        hard   = (b.get("hard_pct") or 0) * 0.5
        return xslg + barrel + hard

    batters.sort(key=_score, reverse=True)
    return batters[:n]


def get_team_k_rate(team_abb: str, batter_db: dict) -> float:
    """Return team average batter K rate for opponent K projection adjustments."""
    team_batters = [
        b for b in batter_db.values()
        if b.get("team", "").upper() == team_abb.upper()
        and b.get("pa", 0) >= 20
        and b.get("k_pct", 0) > 0
    ]
    if not team_batters:
        return LEAGUE_AVG_K_RATE
    return sum(b["k_pct"] for b in team_batters) / len(team_batters)
