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

    # Batted ball rates and plate-discipline rates: prefer current year; fall back to prior year
    gb_pct = cur.get("gb_pct")
    if gb_pct is None and prior:
        gb_pct = prior.get("gb_pct")
    fb_pct = cur.get("fb_pct")
    if fb_pct is None and prior:
        fb_pct = prior.get("fb_pct")
    k_pct = cur.get("k_pct")
    if k_pct is None and prior:
        k_pct = prior.get("k_pct")
    bb_pct = cur.get("bb_pct")
    if bb_pct is None and prior:
        bb_pct = prior.get("bb_pct")

    result = dict(cur)
    result.update({
        "xfip":              round(max(2.0, min(xfip,  7.0)), 3),
        "siera":             round(max(2.0, min(siera, 7.0)), 3),
        "era":               round(max(2.0, min(era,   7.0)), 3),
        "avg_ip_per_start":  avg_ip,
        "gb_pct":            gb_pct,
        "fb_pct":            fb_pct,
        "k_pct":             k_pct,
        "bb_pct":            bb_pct,
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

        # Batted ball rates (GB%, FB%) and plate-discipline rates (K%, BB%)
        # — all present in FanGraphs type=8 response
        gb_raw = row.get("GB%") or row.get("GB_pct")
        fb_raw = row.get("FB%") or row.get("FB_pct")
        k_raw  = row.get("K%")  or row.get("K_pct")
        bb_raw = row.get("BB%") or row.get("BB_pct")

        def _pct(v) -> Optional[float]:
            if v is None:
                return None
            try:
                f = float(v)
                return f / 100.0 if f > 1.0 else f
            except (TypeError, ValueError):
                return None

        gb_pct = _pct(gb_raw)
        fb_pct = _pct(fb_raw)
        k_pct  = _pct(k_raw)
        bb_pct = _pct(bb_raw)

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
            "gb_pct":            gb_pct,
            "fb_pct":            fb_pct,
            "k_pct":             k_pct,
            "bb_pct":            bb_pct,
        }

        if name:
            db[name.lower()] = entry
        if mid_str:
            db[mid_str] = entry
        if fg_id:
            db[f"fg:{fg_id}"] = entry

    logger.info(f"FanGraphs: loaded {len(rows)} pitchers for {year}")
    return db


def _fetch_savant_csw(year: int = None) -> dict:
    """
    Load CSW%, Whiff%, and F-Strike% from pitcher_start_metrics_per_start.csv.

    Uses rolling 5-start average (csw_r5, whiff_r5, f_strike_r5) from the
    most recent start per pitcher — the same data source and feature definition
    used to train S2.

    Fallback chain per pitcher:
      1. Latest available row overall (2026 if it exists, else 2025)
      2. Latest 2024 row
      3. League median (CSW=27.0, whiff=22.2, fstrike=61.7)

    Returns {mlbam_id_str: {"csw_pct": float, "whiff_pct": float,
             "f_strike_pct": float, "csw_source": str}, ...}
    Also keyed by lowercase "first last" name for fallback matching.
    """
    csv_path = os.path.join(os.path.dirname(__file__), "..",
                            "research", "mlb_phase_a",
                            "pitcher_start_metrics_per_start.csv")
    if not os.path.exists(csv_path):
        logger.warning(f"Per-start CSW file not found: {csv_path}")
        return {}

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        logger.warning(f"Per-start CSW load failed: {e}")
        return {}

    # Sort by date to get most recent start per pitcher
    df = df.sort_values("game_date")
    latest = df.groupby("pitcher_id").last().reset_index()

    CSW_MEDIAN = 27.0
    WHIFF_MEDIAN = 22.2
    FSTRIKE_MEDIAN = 61.7

    db: dict = {}
    for _, row in latest.iterrows():
        pid = str(int(row["pitcher_id"]))
        season = int(row.get("season", 0))
        raw_name = str(row.get("pitcher_name", "") or "")

        # Use rolling-5 if available, fall back to single-start pct
        csw = row.get("csw_r5")
        whiff = row.get("whiff_r5")
        fstrike = row.get("f_strike_r5")

        if pd.isna(csw):
            csw = row.get("csw_pct")
        if pd.isna(whiff):
            whiff = row.get("whiff_pct")
        if pd.isna(fstrike):
            fstrike = row.get("f_strike_pct")

        # Determine source label
        if season >= 2026:
            source = "rolling_2026"
        elif season >= 2025:
            source = "rolling_2025"
        elif season >= 2024:
            source = "rolling_2024"
        else:
            source = "rolling_prior"

        # Apply league median fallback for any remaining nulls
        if pd.isna(csw):
            csw = CSW_MEDIAN
            source = "league_median"
        if pd.isna(whiff):
            whiff = WHIFF_MEDIAN
        if pd.isna(fstrike):
            fstrike = FSTRIKE_MEDIAN

        entry = {
            "csw_pct": round(float(csw), 2),
            "whiff_pct": round(float(whiff), 2),
            "f_strike_pct": round(float(fstrike), 2),
            "csw_source": source,
            "csw_insufficient_sample": False,
        }

        db[pid] = entry
        if raw_name:
            # "Last, First" -> "first last" lowercase for name matching
            if "," in raw_name:
                parts = [p.strip() for p in raw_name.split(",", 1)]
                name_key = f"{parts[1]} {parts[0]}".lower()
            else:
                name_key = raw_name.lower()
            db[name_key] = entry

    logger.info(f"CSW from per-start CSV: {len(latest)} pitchers "
                f"(latest seasons: {latest['season'].value_counts().to_dict()})")
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

    # --- Enrich with CSW/Whiff/F-Strike from per-start Statcast CSV ---
    try:
        csw_db = _fetch_savant_csw()
        csw_matched = 0
        for key, entry in blended.items():
            if key == "_meta":
                continue
            csw_entry = csw_db.get(str(entry.get("mlbam_id", ""))) or csw_db.get(key)
            if csw_entry:
                entry["csw_pct"] = csw_entry.get("csw_pct")
                entry["whiff_pct"] = csw_entry.get("whiff_pct")
                entry["f_strike_pct"] = csw_entry.get("f_strike_pct")
                entry["csw_source"] = csw_entry.get("csw_source", "unknown")
                entry["csw_insufficient_sample"] = csw_entry.get("csw_insufficient_sample", False)
                csw_matched += 1
        logger.info(f"CSW enrichment: {csw_matched} pitchers matched")
    except Exception as e:
        logger.warning(f"CSW enrichment failed (non-fatal): {e}")

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
        "gb_pct":            None,
        "fb_pct":            None,
        "k_pct":             None,   # -> sim model uses LEAGUE_AVG_K_RATE if None
        "bb_pct":            None,   # -> sim model uses LEAGUE_AVG_BB_RATE if None
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
        e.setdefault("gb_pct", None)
        e.setdefault("fb_pct", None)
        e.setdefault("k_pct",  None)
        e.setdefault("bb_pct", None)
        e.setdefault("csw_pct", None)
        e.setdefault("whiff_pct", None)
        e.setdefault("f_strike_pct", None)
        e.setdefault("csw_source", "default")
        e.setdefault("csw_insufficient_sample", True)
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


# ── Daily CSW refresh: append yesterday's starts to per-start CSV ────────────

def refresh_daily_csw(game_date_str: str):
    """
    Pull pitch-level Statcast for yesterday's completed starts and append
    to pitcher_start_metrics_per_start.csv with updated rolling metrics.

    Idempotent: skips pitcher+date combos already in the CSV.
    Only processes the given date — never repulls full history.
    """
    csv_path = os.path.join(os.path.dirname(__file__), "..",
                            "research", "mlb_phase_a",
                            "pitcher_start_metrics_per_start.csv")
    if not os.path.exists(csv_path):
        logger.warning("Per-start CSV not found — skipping CSW refresh")
        return 0

    try:
        from pybaseball import statcast
    except ImportError:
        logger.warning("pybaseball not installed — skipping CSW refresh")
        return 0

    df_csv = pd.read_csv(csv_path)
    df_csv["game_date"] = df_csv["game_date"].astype(str)

    # Pull all pitches for this date
    try:
        pitches = statcast(start_dt=game_date_str, end_dt=game_date_str)
    except Exception as e:
        logger.warning(f"Statcast pull failed for {game_date_str}: {e}")
        return 0

    if pitches is None or len(pitches) == 0:
        logger.info(f"CSW refresh: no pitches found for {game_date_str}")
        return 0

    # Identify starters: pitcher with pitch_number=1 in inning 1
    starters = pitches[
        (pitches["inning"] == 1) & (pitches["inning_topbot"].isin(["Top", "Bot"]))
    ].groupby("game_pk")["pitcher"].first().reset_index()
    # Also get starters from the other half-inning
    starters2 = pitches[
        (pitches["inning"] == 1)
    ].groupby(["game_pk", "inning_topbot"])["pitcher"].first().reset_index()
    starter_ids = set(starters2["pitcher"].unique())

    # Filter to starter pitches only
    starter_pitches = pitches[pitches["pitcher"].isin(starter_ids)].copy()

    new_rows = []
    year = int(game_date_str[:4])

    for (game_pk, pitcher_id), grp in starter_pitches.groupby(["game_pk", "pitcher"]):
        pitcher_id = int(pitcher_id)
        game_pk = int(game_pk)

        # Idempotency: skip if already in CSV
        existing = df_csv[
            (df_csv["pitcher_id"] == pitcher_id) &
            (df_csv["game_date"] == game_date_str)
        ]
        if len(existing) > 0:
            continue

        total = len(grp)
        if total < 10:
            continue  # not a real start

        # Derive per-start metrics from pitch descriptions
        called = (grp["description"] == "called_strike").sum()
        swinging = grp["description"].str.contains("swinging_strike", na=False).sum()
        csw_pct = round((called + swinging) / total * 100, 2)

        # Whiff: swinging strikes / swings
        swing_events = ["swinging_strike", "swinging_strike_blocked",
                        "foul", "foul_tip", "foul_bunt", "missed_bunt",
                        "hit_into_play", "hit_into_play_no_out",
                        "hit_into_play_score"]
        swings = grp["description"].isin(swing_events).sum()
        whiff_pct = round(swinging / swings * 100, 2) if swings > 0 else 0.0

        # F-Strike: first-pitch strikes
        if "pitch_number" in grp.columns:
            fp = grp[grp["pitch_number"] == 1]
            fp_strikes = fp[fp["type"].isin(["S", "X"])].shape[0]
            fstrike_pct = round(fp_strikes / len(fp) * 100, 2) if len(fp) > 0 else 0.0
        else:
            fstrike_pct = 0.0

        # Pitcher name
        name_col = grp["player_name"].iloc[0] if "player_name" in grp.columns else ""

        # K and BB counts
        k_count = 0
        bb_count = 0
        if "events" in grp.columns:
            events = grp["events"].dropna()
            k_count = int(events.str.contains("strikeout", case=False).sum())
            bb_count = int(events.str.contains("walk", case=False).sum())

        # Compute rolling 5-start averages from CSV history + this new start
        prior = df_csv[df_csv["pitcher_id"] == pitcher_id].sort_values("game_date").tail(4)
        prior_csw = prior["csw_pct"].tolist()
        prior_whiff = prior["whiff_pct"].tolist()
        prior_fstrike = prior["f_strike_pct"].tolist()

        all_csw = prior_csw + [csw_pct]
        all_whiff = prior_whiff + [whiff_pct]
        all_fstrike = prior_fstrike + [fstrike_pct]

        csw_r5 = round(sum(all_csw) / len(all_csw), 2)
        whiff_r5 = round(sum(all_whiff) / len(all_whiff), 2)
        fstrike_r5 = round(sum(all_fstrike) / len(all_fstrike), 2)

        starts_to_date = len(prior) + 1
        rolling_complete = 1 if starts_to_date >= 5 else 0

        new_rows.append({
            "pitcher_id": pitcher_id,
            "pitcher_name": name_col,
            "game_date": game_date_str,
            "game_pk": game_pk,
            "f_strike_pct": fstrike_pct,
            "whiff_pct": whiff_pct,
            "csw_pct": csw_pct,
            "fb_velo": None,
            "fb_velo_max": None,
            "total_pitches": total,
            "strikes_pct": round((grp["type"] == "S").sum() / total * 100, 2),
            "k_count": k_count,
            "bb_count": bb_count,
            "season": year,
            "starts_to_date": starts_to_date,
            "f_strike_r5": fstrike_r5,
            "whiff_r5": whiff_r5,
            "csw_r5": csw_r5,
            "fb_velo_r5": None,
            "fb_velo_r3": None,
            "f_strike_season": None,
            "whiff_season": None,
            "fb_velo_season": None,
            "f_strike_trend": None,
            "whiff_trend": None,
            "velo_trend": None,
            "rolling_complete": rolling_complete,
        })

    if new_rows:
        new_df = pd.DataFrame(new_rows)
        combined = pd.concat([df_csv, new_df], ignore_index=True)
        combined.to_csv(csv_path, index=False)
        logger.info(f"CSW refresh: appended {len(new_rows)} starts for {game_date_str}")
    else:
        logger.info(f"CSW refresh: no new starts to add for {game_date_str}")

    return len(new_rows)
