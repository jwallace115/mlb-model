"""
fg_historical.py — FanGraphs data fetcher for historical seasons (2022-2024).

Separate from the daily pipeline caches to avoid conflicts.  Applies per-stat
Bayesian shrinkage with proper league-average priors before any merge.

League average priors:
  xFIP / SIERA : 4.25
  K%           : 0.224
  BB%          : 0.085
  wRC+         : 100

Pitcher regression constant: 300 BF (same as daily pipeline)
Offense regression constant: 150 PA (per-team seasonal sample is large; lighter shrinkage)

Cache paths (all under sim/data/cache/):
  fg_pitch_{year}.json    — full pitcher DB (starters + relievers), shrunk
  fg_offense_{year}.json  — team batting stats + platoon splits
"""

import json
import logging
import os
from collections import defaultdict
from io import StringIO
from typing import Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

SIM_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "cache")
os.makedirs(SIM_CACHE_DIR, exist_ok=True)

FANGRAPHS_PITCHING_URL = "https://www.fangraphs.com/api/leaders/major-league/data"
FANGRAPHS_BATTING_URL  = "https://www.fangraphs.com/api/leaders/major-league/data"

_FG_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "Referer": "https://www.fangraphs.com/leaders/major-league",
}

# FanGraphs team abbreviation normalisation
_FG_TEAM_MAP = {
    "ATH": "OAK", "KCR": "KCR", "SDP": "SDP", "SFG": "SFG",
    "TBR": "TBR", "WSN": "WSN",
}
_SKIP_ABBS = {"2 Tms", "3 Tms", "4 Tms", "- - -"}

# Bayesian shrinkage constants
_PITCHER_BF_PRIOR = 300     # BF prior weight for pitcher stats
_OFFENSE_PA_PRIOR = 150     # PA prior weight for team offense

# League-average priors
_LG_XFIP  = 4.25
_LG_SIERA = 4.25
_LG_K_PCT = 0.224
_LG_BB_PCT = 0.085
_LG_WRC   = 100.0
_LG_XWOBA = 0.318

# Min BF before any non-trivial shrinkage is applied
_MIN_BF = 30


# ---------------------------------------------------------------------------
# Shrinkage helpers
# ---------------------------------------------------------------------------

def _shrink(stat: float, bf: int, league_avg: float,
            prior: int = _PITCHER_BF_PRIOR) -> float:
    """
    Bayesian shrinkage toward league_avg.
    shrunk = (stat * BF + league_avg * prior) / (BF + prior)
    Returns league_avg if BF < _MIN_BF.
    """
    if bf < _MIN_BF:
        return league_avg
    return (stat * bf + league_avg * prior) / (bf + prior)


def _pct(v) -> Optional[float]:
    """Parse a percentage value that may be a string, decimal, or percent (>1)."""
    if v is None:
        return None
    try:
        f = float(v)
        return f / 100.0 if f > 1.0 else f
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Pitcher DB
# ---------------------------------------------------------------------------

def _cache_path_pitch(year: int) -> str:
    return os.path.join(SIM_CACHE_DIR, f"fg_pitch_{year}.json")


def _fetch_fg_pitching_raw(year: int) -> list[dict]:
    """Pull raw FanGraphs advanced pitching leaderboard (type=8, all pitchers)."""
    params = {
        "age": 0, "pos": "all", "stats": "pit", "lg": "all",
        "qual": 0, "season": year, "season1": year, "ind": 0,
        "team": 0, "pageitems": 3000, "pagenum": 1, "type": 8,
    }
    try:
        resp = requests.get(FANGRAPHS_PITCHING_URL, params=params,
                            headers=_FG_HEADERS, timeout=30)
        resp.raise_for_status()
        rows = resp.json().get("data", [])
        logger.info(f"FanGraphs pitching: {len(rows)} rows for {year}")
        return rows
    except Exception as e:
        logger.error(f"FanGraphs pitching fetch failed ({year}): {e}")
        return []


def _build_pitcher_db_from_rows(rows: list[dict]) -> dict:
    """
    Parse FanGraphs pitching rows into a pitcher DB with Bayesian shrinkage applied.

    Keys (all pointing to the same entry dict):
      - str(mlbam_id)       — most reliable join key
      - "fg:{fg_id}"        — FanGraphs internal ID
      - name.lower()        — name fallback

    Entry fields:
      name, mlbam_id, fg_id, team, gs, bf, ip, avg_ip_per_start,
      xfip, siera, k_pct, bb_pct, gb_pct, fb_pct,  ← all shrunk
      throws (not in FG response — added separately from game_starters)
    """
    import re
    _html_re = re.compile(r">([^<]+)</a>")

    def _strip_html(s: str) -> str:
        m = _html_re.search(s)
        return m.group(1).strip() if m else (s or "").strip()

    db: dict = {}

    for row in rows:
        raw_name = row.get("Name", "") or row.get("PlayerName", "")
        name     = _strip_html(raw_name)
        if not name:
            continue

        mlbam_id = row.get("xMLBAMID") or row.get("mlbamid")
        fg_id    = str(row.get("playerid", ""))
        team     = str(row.get("Team", "")).upper().strip()
        team     = _FG_TEAM_MAP.get(team, team)

        gs  = int(float(row.get("GS")  or 0))
        ip  = float(row.get("IP")  or 0)
        tbf = int(float(row.get("TBF") or row.get("BF") or 0))

        xfip_raw  = row.get("xFIP")
        siera_raw = row.get("SIERA")
        k_raw     = row.get("K%")   or row.get("SO%")
        bb_raw    = row.get("BB%")
        gb_raw    = row.get("GB%")  or row.get("GB_pct")
        fb_raw    = row.get("FB%")  or row.get("FB_pct")

        xfip  = float(xfip_raw)  if xfip_raw  is not None else _LG_XFIP
        siera = float(siera_raw) if siera_raw is not None else _LG_SIERA
        k_pct  = _pct(k_raw)
        bb_pct = _pct(bb_raw)
        gb_pct = _pct(gb_raw)
        fb_pct = _pct(fb_raw)

        # Bayesian shrinkage (applied here, before any merge)
        xfip_s  = _shrink(xfip,  tbf, _LG_XFIP)
        siera_s = _shrink(siera, tbf, _LG_SIERA)
        k_pct_s = _shrink(k_pct  if k_pct  is not None else _LG_K_PCT,
                           tbf, _LG_K_PCT)
        bb_pct_s = _shrink(bb_pct if bb_pct is not None else _LG_BB_PCT,
                            tbf, _LG_BB_PCT)

        # Clamp ERA-like metrics to realistic range
        xfip_s  = round(max(2.0, min(xfip_s,  7.5)), 3)
        siera_s = round(max(2.0, min(siera_s, 7.5)), 3)
        k_pct_s = round(max(0.05, min(k_pct_s, 0.50)), 4)
        bb_pct_s = round(max(0.02, min(bb_pct_s, 0.25)), 4)

        # IP per start (clamped; None if <3 GS)
        avg_ip = round(ip / gs, 2) if gs >= 3 else None
        if avg_ip is not None:
            avg_ip = max(3.0, min(avg_ip, 7.5))

        mid_str = str(int(mlbam_id)) if mlbam_id else None

        entry = {
            "name":             name,
            "mlbam_id":         mid_str,
            "fg_id":            fg_id,
            "team":             team,
            "gs":               gs,
            "bf":               tbf,
            "ip":               round(ip, 1),
            "avg_ip_per_start": avg_ip,
            "xfip":             xfip_s,
            "siera":            siera_s,
            "k_pct":            k_pct_s,
            "bb_pct":           bb_pct_s,
            "gb_pct":           round(gb_pct, 4) if gb_pct is not None else None,
            "fb_pct":           round(fb_pct, 4) if fb_pct is not None else None,
        }

        if name:
            db[name.lower()] = entry
        if mid_str:
            db[mid_str] = entry
        if fg_id:
            db[f"fg:{fg_id}"] = entry

    return db


def _fetch_mlb_stats_pitcher_season(year: int) -> dict:
    """
    Fetch per-pitcher season stats from MLB Stats API (SO, BB, BF, IP, GS).
    Returns dict: str(mlbam_id) → {so, bb, bf, ip, gs, k_pct, bb_pct, avg_ip_per_start}

    Used to enrich Savant pitcher entries with K%, BB%, and avg_ip which are
    unavailable from the expected_statistics endpoint.
    """
    MLB_API = "https://statsapi.mlb.com/api/v1"
    result: dict = {}
    offset = 0
    page_size = 500

    while True:
        params = {
            "stats":      "season",
            "group":      "pitching",
            "season":     year,
            "sportId":    1,
            "playerPool": "All",
            "limit":      page_size,
            "offset":     offset,
        }
        try:
            resp = requests.get(f"{MLB_API}/stats", params=params, timeout=30)
            resp.raise_for_status()
            data    = resp.json()
            stats   = data.get("stats", [{}])[0]
            splits  = stats.get("splits", [])
            total   = stats.get("totalSplits", 0)
        except Exception as e:
            logger.warning(f"MLB Stats pitcher season fetch failed ({year}, offset={offset}): {e}")
            break

        try:
            from config import TEAM_ID_TO_ABB
        except ImportError:
            TEAM_ID_TO_ABB = {}

        for split in splits:
            pid      = split.get("player", {}).get("id")
            team_id  = split.get("team", {}).get("id")
            stat     = split.get("stat", {})
            if not pid:
                continue

            team_abb = TEAM_ID_TO_ABB.get(team_id, "") if team_id else ""

            so  = int(stat.get("strikeOuts", 0) or 0)
            bb  = int(stat.get("baseOnBalls", 0) or 0)
            bf  = int(stat.get("battersFaced", 0) or 0)
            gs  = int(stat.get("gamesStarted", 0) or 0)
            ip  = float(stat.get("inningsPitched", 0) or 0)
            # Convert IP "whole.partial" format to decimal innings
            whole   = int(ip)
            partial = round(ip - whole, 1)
            ip_dec  = whole + (partial / 0.3) * (1 / 3)   # .1 → 1/3 inn, .2 → 2/3 inn

            k_pct_v  = _shrink(so / bf if bf >= _MIN_BF else _LG_K_PCT,
                               bf, _LG_K_PCT)
            bb_pct_v = _shrink(bb / bf if bf >= _MIN_BF else _LG_BB_PCT,
                               bf, _LG_BB_PCT)
            avg_ip   = round(ip_dec / gs, 2) if gs >= 3 else None
            if avg_ip is not None:
                avg_ip = max(3.0, min(avg_ip, 7.5))

            result[str(pid)] = {
                "team":             team_abb,
                "gs":               gs,
                "bf":               bf,
                "ip":               round(ip_dec, 1),
                "k_pct":            round(max(0.05, min(k_pct_v,  0.50)), 4),
                "bb_pct":           round(max(0.02, min(bb_pct_v, 0.25)), 4),
                "avg_ip_per_start": avg_ip,
            }

        offset += page_size
        if offset >= total:
            break

    logger.info(f"MLB Stats pitcher season {year}: {len(result)} pitchers fetched")
    return result


def _enrich_pitcher_db_from_mlb_stats(db: dict, year: int) -> dict:
    """
    Merge MLB Stats API K%, BB%, GS, avg_ip into an existing pitcher DB.
    Only updates entries that already exist (keyed by str(mlbam_id)).
    """
    mlb_stats = _fetch_mlb_stats_pitcher_season(year)
    enriched = 0

    for pid_str, mlb in mlb_stats.items():
        if pid_str in db:
            entry = dict(db[pid_str])
            # Only overwrite if MLB Stats has a meaningful sample
            if mlb["bf"] >= _MIN_BF:
                entry["gs"]               = mlb["gs"]
                entry["bf"]               = mlb["bf"]
                entry["ip"]               = mlb["ip"]
                entry["k_pct"]            = mlb["k_pct"]
                entry["bb_pct"]           = mlb["bb_pct"]
                entry["avg_ip_per_start"] = mlb["avg_ip_per_start"]
                if mlb.get("team"):           # also backfill team from MLB Stats
                    entry["team"] = mlb["team"]
                db[pid_str] = entry

                # Also update name-key entry if it exists
                name_key = entry.get("name", "").lower()
                if name_key and name_key in db:
                    db[name_key] = entry

                enriched += 1

    logger.info(f"Enriched {enriched} pitchers with MLB Stats K%/BB%/GS data ({year})")
    return db


def _fetch_savant_pitching_historical(year: int) -> dict:
    """
    Fallback: Baseball Savant pitcher expected statistics for a historical season.
    Provides xera (used as xfip/siera proxy), k%, bb%, bf.
    Returns same DB format as _build_pitcher_db_from_rows but with Savant data.
    """
    url = (
        f"https://baseballsavant.mlb.com/leaderboard/expected_statistics"
        f"?type=pitcher&year={year}&position=&team=&min=10&csv=true"
    )
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        df = pd.read_csv(StringIO(resp.text))
    except Exception as e:
        logger.error(f"Savant pitcher fallback failed ({year}): {e}")
        return {}

    db: dict = {}
    loaded = 0
    for _, row in df.iterrows():
        pa   = float(row.get("pa") or 0)
        if pa < 10:
            continue

        raw  = str(row.get("last_name, first_name", "") or "")
        if "," in raw:
            parts = [p.strip() for p in raw.split(",", 1)]
            name = f"{parts[1]} {parts[0]}" if len(parts) == 2 else raw
        else:
            name = raw.strip()
        if not name:
            continue

        pid   = str(int(row.get("player_id", 0) or 0))
        xera  = row.get("xera")
        era   = row.get("era")
        k_pct = row.get("k_percent")
        bb_pct= row.get("walk_percent")

        xfip_raw  = float(xera) if pd.notna(xera) else _LG_XFIP
        era_raw   = float(era)  if pd.notna(era)  else _LG_XFIP
        k_raw     = _pct(k_pct)
        bb_raw    = _pct(bb_pct)

        bf = int(pa)
        xfip_s  = _shrink(min(xfip_raw, 7.5), bf, _LG_XFIP)
        siera_s = xfip_s   # xERA → both xFIP and SIERA proxies
        k_pct_s = _shrink(k_raw  if k_raw  is not None else _LG_K_PCT,  bf, _LG_K_PCT)
        bb_pct_s= _shrink(bb_raw if bb_raw is not None else _LG_BB_PCT, bf, _LG_BB_PCT)

        entry = {
            "name":             name,
            "mlbam_id":         pid if pid != "0" else None,
            "fg_id":            None,
            "team":             "",      # Savant doesn't give current team easily
            "gs":               None,    # not available from Savant leaderboard
            "bf":               bf,
            "ip":               0.0,
            "avg_ip_per_start": None,    # will default to 5.5 in lookup
            "xfip":             round(max(2.0, min(xfip_s, 7.5)), 3),
            "siera":            round(max(2.0, min(siera_s, 7.5)), 3),
            "k_pct":            round(max(0.05, min(k_pct_s, 0.50)), 4),
            "bb_pct":           round(max(0.02, min(bb_pct_s, 0.25)), 4),
            "gb_pct":           None,
            "fb_pct":           None,
            "_source":          "savant",
        }

        if name:
            db[name.lower()] = entry
        if pid and pid != "0":
            db[pid] = entry

        loaded += 1

    logger.info(f"Savant pitcher fallback {year}: {loaded} pitchers")
    return db


def build_pitcher_db_historical(year: int,
                                 force_refresh: bool = False) -> dict:
    """
    Build (or load from cache) a pitcher DB for a historical season.
    Tries FanGraphs first; falls back to Savant xERA if FanGraphs is blocked.

    Returns dict with keys: str(mlbam_id), name.lower()
    All ERA-type stats are Bayesian-shrunk before storage.
    """
    path = _cache_path_pitch(year)
    if not force_refresh and os.path.exists(path):
        try:
            with open(path) as f:
                db = json.load(f)
            logger.info(f"Loaded pitcher DB for {year} from cache ({len(db)} keys)")
            return db
        except Exception:
            pass

    logger.info(f"Building pitcher DB for {year} from FanGraphs...")
    rows = _fetch_fg_pitching_raw(year)

    if rows:
        db = _build_pitcher_db_from_rows(rows)
        logger.info(f"Pitcher DB {year} [FanGraphs]: {len(rows)} rows → {len(db)} keys")
    else:
        logger.warning(f"FanGraphs blocked for {year} — falling back to Savant xERA")
        db = _fetch_savant_pitching_historical(year)
        if not db:
            logger.error(f"Both FanGraphs and Savant failed for {year} — empty pitcher DB")
            return {}
        logger.info(f"Pitcher DB {year} [Savant]: {len(db)} keys")

        # Enrich Savant entries with K%, BB%, GS, avg_ip from MLB Stats API
        logger.info(f"Enriching pitcher DB {year} with K%/BB%/GS from MLB Stats API...")
        db = _enrich_pitcher_db_from_mlb_stats(db, year)

    with open(path, "w") as f:
        json.dump(db, f)

    return db


def lookup_pitcher(pitcher_id: Optional[int], pitcher_name: str,
                   pitcher_db: dict, team: str = "") -> tuple[dict, int]:
    """
    Look up a pitcher in the DB.  Returns (entry_dict, fallback_level).

    Fallback levels:
      0 = matched by MLBAM ID (most reliable)
      1 = matched by exact full name
      2 = matched by last name (partial)
      3 = team average (if team provided and has starters in DB)
      4 = league average
    """
    # Level 0: MLBAM ID
    if pitcher_id:
        entry = pitcher_db.get(str(pitcher_id))
        if entry:
            return entry, 0

    # Level 1: exact name
    if pitcher_name:
        entry = pitcher_db.get(pitcher_name.lower())
        if entry:
            return entry, 1

    # Level 2: last-name match
    if pitcher_name:
        last = pitcher_name.split()[-1].lower() if pitcher_name else ""
        if last:
            candidates = [v for k, v in pitcher_db.items()
                          if not k.startswith("fg:") and not k.isdigit()
                          and k.split()[-1] == last]
            if len(candidates) == 1:
                return candidates[0], 2

    # Level 3: team average of starters in DB
    if team:
        team_starters = [
            v for k, v in pitcher_db.items()
            if not k.startswith("fg:") and not k.isdigit()
            and isinstance(v, dict)
            and v.get("team", "").upper() == team.upper()
            and (v.get("gs") or 0) >= 3
        ]
        if team_starters:
            avg = {
                "name":             f"{team} team avg",
                "mlbam_id":         None,
                "gs":               0,
                "bf":               0,
                "xfip":             round(sum(e["xfip"]  for e in team_starters) / len(team_starters), 3),
                "siera":            round(sum(e["siera"] for e in team_starters) / len(team_starters), 3),
                "k_pct":            round(sum(e["k_pct"] for e in team_starters) / len(team_starters), 4),
                "bb_pct":           round(sum(e["bb_pct"] for e in team_starters) / len(team_starters), 4),
                "gb_pct":           None,
                "fb_pct":           None,
                "avg_ip_per_start": 5.5,
            }
            return avg, 3

    # Level 4: league average
    league_avg = {
        "name":             "league_avg",
        "mlbam_id":         None,
        "gs":               0,
        "bf":               0,
        "xfip":             _LG_XFIP,
        "siera":            _LG_SIERA,
        "k_pct":            _LG_K_PCT,
        "bb_pct":           _LG_BB_PCT,
        "gb_pct":           None,
        "fb_pct":           None,
        "avg_ip_per_start": 5.5,
    }
    return league_avg, 4


# ---------------------------------------------------------------------------
# Team Offense DB
# ---------------------------------------------------------------------------

def _cache_path_offense(year: int) -> str:
    return os.path.join(SIM_CACHE_DIR, f"fg_offense_{year}.json")


def _fetch_fg_batting_raw(year: int) -> list[dict]:
    """Pull raw FanGraphs individual batting (type=8, qual=10 PA)."""
    params = {
        "age": 0, "pos": "all", "stats": "bat", "lg": "all",
        "qual": 10, "season": year, "season1": year, "ind": 0,
        "team": 0, "pageitems": 3000, "pagenum": 1, "type": 8,
    }
    try:
        resp = requests.get(FANGRAPHS_BATTING_URL, params=params,
                            headers=_FG_HEADERS, timeout=30)
        resp.raise_for_status()
        rows = resp.json().get("data", [])
        logger.info(f"FanGraphs batting: {len(rows)} rows for {year}")
        return rows
    except Exception as e:
        logger.error(f"FanGraphs batting fetch failed ({year}): {e}")
        return []


def _aggregate_team_offense(rows: list[dict]) -> dict:
    """PA-weighted wRC+ aggregation per team from individual batter rows."""
    team_agg: dict = defaultdict(lambda: {"wrc_sum": 0.0, "pa_sum": 0.0})

    for row in rows:
        fg_abb = (row.get("TeamNameAbb") or "").strip()
        if not fg_abb or fg_abb in _SKIP_ABBS:
            continue
        abb = _FG_TEAM_MAP.get(fg_abb, fg_abb)

        try:
            wrc = float(row.get("wRC+") or 0)
            pa  = float(row.get("PA")   or 0)
        except (TypeError, ValueError):
            continue

        if pa <= 0:
            continue

        team_agg[abb]["wrc_sum"] += wrc * pa
        team_agg[abb]["pa_sum"]  += pa

    db: dict = {}
    for abb, agg in team_agg.items():
        pa_sum = agg["pa_sum"]
        wrc    = agg["wrc_sum"] / pa_sum if pa_sum > 0 else _LG_WRC
        # Light Bayesian shrinkage on team wRC+ (150 PA prior toward 100)
        wrc_s  = _shrink(wrc, int(pa_sum), _LG_WRC, prior=_OFFENSE_PA_PRIOR)
        db[abb] = {"wrc_plus": round(wrc_s, 1)}

    return db


def _fetch_savant_platoon(year: int) -> dict:
    """
    Fetch team wRC+ proxy vs LHP and vs RHP from Baseball Savant.
    Returns team_abb → {wrc_plus_vs_lhp, wrc_plus_vs_rhp}.
    Uses xwOBA: (team_xwOBA / LEAGUE_AVG_XWOBA) * 100.
    """
    MLB_API = "https://statsapi.mlb.com/api/v1"

    # Build player → team map
    player_team: dict = {}
    try:
        from config import TEAM_ID_TO_ABB
        resp = requests.get(f"{MLB_API}/sports/1/players",
                            params={"season": year}, timeout=20)
        resp.raise_for_status()
        for p in resp.json().get("people", []):
            pid = str(p.get("id", ""))
            tid = p.get("currentTeam", {}).get("id")
            if pid and tid:
                abb = TEAM_ID_TO_ABB.get(tid, "")
                if abb:
                    player_team[pid] = abb
    except Exception as e:
        logger.warning(f"Player-team mapping failed (platoon {year}): {e}")
        return {}

    splits: dict = {}
    for hand, key in [("L", "wrc_plus_vs_lhp"), ("R", "wrc_plus_vs_rhp")]:
        url = (
            f"https://baseballsavant.mlb.com/leaderboard/expected_statistics"
            f"?type=batter&year={year}&position=&team=&min=20"
            f"&pitcherHand={hand}&csv=true"
        )
        try:
            r = requests.get(url, timeout=20)
            r.raise_for_status()
            df = pd.read_csv(StringIO(r.text))
        except Exception as e:
            logger.warning(f"Savant platoon ({hand}, {year}) failed: {e}")
            continue

        team_agg: dict = defaultdict(lambda: {"xwoba_sum": 0.0, "pa_sum": 0.0})
        for _, row in df.iterrows():
            pid   = str(int(row.get("player_id", 0) or 0))
            xwoba = row.get("est_woba")
            pa    = row.get("pa")
            team  = player_team.get(pid)
            if not team or pd.isna(xwoba) or pd.isna(pa) or float(pa) <= 0:
                continue
            team_agg[team]["xwoba_sum"] += float(xwoba) * float(pa)
            team_agg[team]["pa_sum"]    += float(pa)

        for abb, agg in team_agg.items():
            if agg["pa_sum"] > 0:
                wrc_proxy = (agg["xwoba_sum"] / agg["pa_sum"]) / _LG_XWOBA * 100
                # Light shrinkage on split wRC+
                wrc_s = _shrink(wrc_proxy, int(agg["pa_sum"]), _LG_WRC,
                                prior=_OFFENSE_PA_PRIOR)
                splits.setdefault(abb, {})[key] = round(wrc_s, 1)

    logger.info(f"Savant platoon splits {year}: {len(splits)} teams")
    return splits


def _fetch_savant_offense_historical(year: int) -> dict:
    """
    Fallback: derive team wRC+ proxy from Baseball Savant xwOBA aggregated per team.
    Uses MLB Stats API to map player_id → current team for that season.
    Returns team_abb → {wrc_plus: float, _source: "savant"}.
    """
    MLB_API = "https://statsapi.mlb.com/api/v1"

    # Player → team mapping
    player_team: dict = {}
    try:
        from config import TEAM_ID_TO_ABB
        resp = requests.get(f"{MLB_API}/sports/1/players",
                            params={"season": year}, timeout=20)
        resp.raise_for_status()
        for p in resp.json().get("people", []):
            pid = str(p.get("id", ""))
            tid = p.get("currentTeam", {}).get("id")
            if pid and tid:
                abb = TEAM_ID_TO_ABB.get(tid, "")
                if abb:
                    player_team[pid] = abb
    except Exception as e:
        logger.warning(f"Player-team mapping failed ({year}): {e}")
        return {}

    url = (
        f"https://baseballsavant.mlb.com/leaderboard/expected_statistics"
        f"?type=batter&year={year}&position=&team=&min=50&csv=true"
    )
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        df = pd.read_csv(StringIO(r.text))
    except Exception as e:
        logger.error(f"Savant batter CSV failed ({year}): {e}")
        return {}

    team_agg: dict = defaultdict(lambda: {"xwoba_sum": 0.0, "pa_sum": 0.0})
    for _, row in df.iterrows():
        pid   = str(int(row.get("player_id", 0) or 0))
        xwoba = row.get("est_woba")
        pa    = row.get("pa")
        team  = player_team.get(pid)
        if not team or pd.isna(xwoba) or pd.isna(pa) or float(pa) <= 0:
            continue
        team_agg[team]["xwoba_sum"] += float(xwoba) * float(pa)
        team_agg[team]["pa_sum"]    += float(pa)

    db: dict = {}
    for abb, agg in team_agg.items():
        if agg["pa_sum"] > 0:
            wrc_proxy = (agg["xwoba_sum"] / agg["pa_sum"]) / _LG_XWOBA * 100
            wrc_s = _shrink(wrc_proxy, int(agg["pa_sum"]), _LG_WRC,
                            prior=_OFFENSE_PA_PRIOR)
            db[abb] = {"wrc_plus": round(wrc_s, 1), "_source": "savant"}

    logger.info(f"Savant offense fallback {year}: {len(db)} teams")
    return db


def build_offense_db_historical(year: int,
                                 force_refresh: bool = False) -> dict:
    """
    Build (or load from cache) a team offense DB for a historical season.
    Tries FanGraphs first; falls back to Savant xwOBA if FanGraphs is blocked.

    Returns dict: team_abb → {
        wrc_plus,           ← overall PA-weighted, Bayesian-shrunk
        wrc_plus_vs_lhp,    ← vs LHP (from Savant; may be absent)
        wrc_plus_vs_rhp,    ← vs RHP (from Savant; may be absent)
    }
    """
    path = _cache_path_offense(year)
    if not force_refresh and os.path.exists(path):
        try:
            with open(path) as f:
                db = json.load(f)
            logger.info(f"Loaded offense DB for {year} from cache ({len(db)} teams)")
            return db
        except Exception:
            pass

    logger.info(f"Building offense DB for {year} from FanGraphs + Savant...")
    rows = _fetch_fg_batting_raw(year)
    db = _aggregate_team_offense(rows) if rows else {}

    if not db:
        logger.warning(f"FanGraphs batting blocked for {year} — falling back to Savant xwOBA")
        db = _fetch_savant_offense_historical(year)
        if not db:
            logger.error(f"Both FanGraphs and Savant offense failed for {year}")
            return {}

    # Enrich with platoon splits (best-effort regardless of primary source)
    platoon = _fetch_savant_platoon(year)
    for abb, sp in platoon.items():
        if abb in db:
            db[abb].update(sp)

    n_splits = sum(1 for v in db.values() if "wrc_plus_vs_lhp" in v)
    logger.info(f"Offense DB {year}: {len(db)} teams, {n_splits} with platoon splits")

    with open(path, "w") as f:
        json.dump(db, f)

    return db


def get_team_wrc(team_abb: str, offense_db: dict,
                 opp_throws: Optional[str] = None) -> tuple[float, int]:
    """
    Return (wrc_plus, fallback_level) for a team against the opposing SP's hand.

    Fallback levels:
      0 = handedness-split wRC+ from Savant
      1 = overall wRC+ from FanGraphs
      2 = league average (100)
    """
    entry = offense_db.get(team_abb)
    if entry is None:
        return _LG_WRC, 2

    if opp_throws:
        hand = opp_throws.upper()
        split_key = "wrc_plus_vs_lhp" if hand == "L" else "wrc_plus_vs_rhp"
        split_val = entry.get(split_key)
        if split_val is not None:
            return float(split_val), 0

    overall = entry.get("wrc_plus")
    if overall is not None:
        return float(overall), 1

    return _LG_WRC, 2


# ---------------------------------------------------------------------------
# Bullpen DB (derived from pitcher DB — relievers only)
# ---------------------------------------------------------------------------

def build_bullpen_db_historical(pitcher_db: dict) -> dict:
    """
    Extract team-level bullpen quality from the pitcher DB.
    Requires pitchers with gs < 3 and bf >= 20 (FanGraphs data).

    When the pitcher DB comes from Savant (gs=None for all entries), GS is
    unavailable so the bullpen DB returns empty — phase2 applies league-average
    bullpen quality (xFIP=4.25) automatically via the bp_fallback=1 path.

    Returns dict: team_abb → {
        avg_xfip,      ← mean reliever xFIP (Bayesian-shrunk)
        arm_count,     ← number of relievers in sample
    }
    """
    team_arms: dict = defaultdict(list)

    seen = set()
    for key, entry in pitcher_db.items():
        if key.startswith("fg:") or key.isdigit():
            continue  # skip non-name keys to avoid triple-counting
        if not isinstance(entry, dict):
            continue

        name = (entry.get("name") or key).lower()
        if name in seen:
            continue
        seen.add(name)

        team = (entry.get("team") or "").upper()
        gs   = entry.get("gs")    # None for Savant-sourced pitchers
        bf   = entry.get("bf") or 0

        # gs is None when data comes from Savant — skip (can't identify relievers)
        if not team or gs is None or gs >= 3 or bf < 20:
            continue

        team_arms[team].append(entry["xfip"])

    result = {}
    for team, xfips in team_arms.items():
        if len(xfips) >= 2:
            avg    = sum(xfips) / len(xfips)
            shrunk = _shrink(avg, 600, _LG_XFIP, prior=_PITCHER_BF_PRIOR)
            result[team] = {
                "avg_xfip":  round(shrunk, 3),
                "arm_count": len(xfips),
            }

    source_note = "(FanGraphs)" if result else "(Savant fallback — no GS data, using league avg)"
    logger.info(f"Bullpen DB {source_note}: {len(result)} teams from {len(seen)} relievers")
    return result
