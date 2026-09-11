#!/usr/bin/env python3
"""
NWS WEATHER CAPTURE — the show's own forecast-vs-observed tape, $0, public domain.

WHY
---
Every weather trial the show runs has to answer "was it knowable before kickoff?"
Observed conditions can't answer that; only an archive of what the forecast SAID
can, and no licence-clean historical-forecast source exists at the show's budget.
So we start the tape ourselves. Every run stores the full NWS hourly forecast for
every outdoor / retractable-roof NFL stadium, plus the last day of hourly
observations from the stadium's nearest NWS station. Any game's kickoff-hour
forecast at any lead time (24h / 48h / 72h) can be reconstructed later by joining
stadium + valid_time and picking the snapshot closest to kickoff - lead.

SOURCE
------
api.weather.gov (National Weather Service). Public domain, no key, no cost.
NWS asks for a User-Agent that identifies the app and a contact — set NWS_CONTACT
in .env (an email or URL). The script refuses to run without it.

DESIGN
------
* Append-only. Never rewrites a prior snapshot. The tape is the asset.
* Every row carries fetched_at_utc (when we asked) and the NWS generated_at /
  update_time (when NWS issued it), so any later analysis is PIT-safe by
  construction.
* Per-stadium failures are logged and skipped; the run only fails if nothing
  at all was captured. NWS 5xx errors are common — 2 retries, 10s backoff.
* Gridpoint + station lookups are cached in gridpoints.json after the first run.

COST
----
~25 stadiums x 2 calls x 8 runs/day = ~400 calls/day. No quota; be polite.

    python3 shared/pipeline/nws_weather_capture.py --selftest    # no network
    python3 shared/pipeline/nws_weather_capture.py --dry-run     # pull, write nothing
    python3 shared/pipeline/nws_weather_capture.py               # capture
    python3 shared/pipeline/nws_weather_capture.py --stadiums BUF GB

Cron (VM, UTC):  0 */3 * * *  cd /root/mlb-model && venv/bin/python3 shared/pipeline/nws_weather_capture.py >> logs/nws_capture.log 2>&1
"""

import argparse, json, logging, os, re, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=True)
except ImportError:  # dotenv is optional here; NWS_CONTACT can come from the shell
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("nws_capture")

BASE = "https://api.weather.gov"
CONTACT = os.getenv("NWS_CONTACT", "").strip()
UA = f"(the-show weather capture, {CONTACT})" if CONTACT else ""
HEADERS = {"User-Agent": UA, "Accept": "application/geo+json"}

STADIUM_INFO = ROOT / "nfl" / "data" / "stadium_info.json"
OUT_ROOT = ROOT / "data" / "weather_archive" / "nws"
GRID_CACHE = OUT_ROOT / "gridpoints.json"

# Legacy keys in stadium_info.json that are not 2026 venues. LA/LAR/LV/MIN/NO/DET
# are fixed domes and drop out via the roof filter; these need naming.
LEGACY_KEYS = {"OAK", "SD", "STL", "LA"}

OBS_LOOKBACK_HOURS = 27  # every-3h cron + slack; dedup happens at read time


# --------------------------------------------------------------------------- helpers

def nfl_season(dt_utc: datetime) -> int:
    return dt_utc.year if dt_utc.month >= 3 else dt_utc.year - 1


def load_stadiums(only=None) -> dict:
    """Outdoor + retractable-roof venues, deduplicated by location (NYG/NYJ share one)."""
    info = json.load(open(STADIUM_INFO))
    out, seen = {}, set()
    for key, s in info.items():
        if key in LEGACY_KEYS:
            continue
        if s.get("is_dome") and not s.get("has_retractable_roof"):
            continue
        if only and key not in only:
            continue
        loc = (round(float(s["lat"]), 3), round(float(s["lon"]), 3))
        if loc in seen:
            continue
        seen.add(loc)
        out[key] = {
            "team": s.get("team"), "stadium": s.get("stadium"), "city": s.get("city"),
            "lat": float(s["lat"]), "lon": float(s["lon"]),
            "roof": "retractable" if s.get("has_retractable_roof") else "outdoors",
        }
    return out


def parse_wind_mph(text):
    """'10 mph' -> (10,10,10.0); '5 to 10 mph' -> (5,10,7.5); None/'' -> (None,None,None)."""
    if not text:
        return None, None, None
    nums = [int(n) for n in re.findall(r"\d+", str(text))]
    if not nums:
        return None, None, None
    lo, hi = min(nums), max(nums)
    return lo, hi, (lo + hi) / 2.0


def c_to_f(v):
    return None if v is None else round(v * 9.0 / 5.0 + 32.0, 1)


def kmh_to_mph(v):
    return None if v is None else round(v * 0.621371, 1)


def _get(url, params=None, retries=2, backoff=10):
    for attempt in range(1 + retries):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=30)
        except requests.RequestException as e:
            if attempt < retries:
                log.warning(f"transient {type(e).__name__} on {url} — retry in {backoff}s")
                time.sleep(backoff); continue
            raise
        if r.status_code == 200:
            return r.json()
        if r.status_code >= 500 and attempt < retries:
            log.warning(f"HTTP {r.status_code} on {url} — retry in {backoff}s")
            time.sleep(backoff); continue
        raise RuntimeError(f"HTTP {r.status_code} on {url}: {r.text[:200]}")


# --------------------------------------------------------------------------- lookups

def resolve_gridpoint(key, st) -> dict:
    """One-time: /points -> hourly forecast URL + nearest observation station."""
    p = _get(f"{BASE}/points/{st['lat']:.4f},{st['lon']:.4f}")["properties"]
    stations = _get(p["observationStations"])
    feats = stations.get("features", [])
    station_id = feats[0]["properties"]["stationIdentifier"] if feats else None
    station_name = feats[0]["properties"].get("name") if feats else None
    return {
        "grid_id": p.get("gridId"), "grid_x": p.get("gridX"), "grid_y": p.get("gridY"),
        "forecast_hourly_url": p.get("forecastHourly"),
        "station_id": station_id, "station_name": station_name,
        "resolved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def load_grid_cache(stadiums, refresh=False) -> dict:
    cache = {}
    if GRID_CACHE.exists() and not refresh:
        cache = json.load(open(GRID_CACHE))
    changed = False
    for key, st in stadiums.items():
        if key in cache and cache[key].get("forecast_hourly_url") and cache[key].get("station_id"):
            continue
        try:
            cache[key] = resolve_gridpoint(key, st)
            changed = True
            log.info(f"  resolved {key}: grid {cache[key]['grid_id']} {cache[key]['grid_x']},{cache[key]['grid_y']} "
                     f"station {cache[key]['station_id']} ({cache[key]['station_name']})")
            time.sleep(0.5)
        except Exception as e:
            log.error(f"  could not resolve gridpoint for {key}: {e}")
    if changed:
        GRID_CACHE.parent.mkdir(parents=True, exist_ok=True)
        json.dump(cache, open(GRID_CACHE, "w"), indent=1)
    return cache


# --------------------------------------------------------------------------- parsing

def parse_forecast(payload: dict, key: str, st: dict, grid: dict, fetched_at: str) -> list:
    props = payload.get("properties", {})
    gen, upd = props.get("generatedAt"), props.get("updateTime")
    rows = []
    for per in props.get("periods", []):
        lo, hi, mean = parse_wind_mph(per.get("windSpeed"))
        pop = (per.get("probabilityOfPrecipitation") or {}).get("value")
        temp = per.get("temperature")
        if per.get("temperatureUnit") == "C" and temp is not None:
            temp = c_to_f(temp)
        rows.append({
            "fetched_at_utc": fetched_at, "generated_at": gen, "update_time": upd,
            "stadium_key": key, "team": st["team"], "stadium": st["stadium"], "roof": st["roof"],
            "lat": st["lat"], "lon": st["lon"],
            "grid_id": grid.get("grid_id"), "grid_x": grid.get("grid_x"), "grid_y": grid.get("grid_y"),
            "valid_start": per.get("startTime"), "valid_end": per.get("endTime"),
            "is_daytime": per.get("isDaytime"),
            "temp_f": temp,
            "wind_mph_low": lo, "wind_mph_high": hi, "wind_mph_mean": mean,
            "wind_text": per.get("windSpeed"), "wind_dir": per.get("windDirection"),
            "precip_prob_pct": pop, "short_forecast": per.get("shortForecast"),
        })
    return rows


def parse_observations(payload: dict, key: str, st: dict, grid: dict, fetched_at: str) -> list:
    rows = []
    for f in payload.get("features", []):
        p = f.get("properties", {})
        def val(name):
            v = p.get(name) or {}
            return v.get("value") if isinstance(v, dict) else None
        rows.append({
            "fetched_at_utc": fetched_at, "stadium_key": key, "team": st["team"],
            "station_id": grid.get("station_id"), "station_name": grid.get("station_name"),
            "observed_at": p.get("timestamp"),
            "temp_f": c_to_f(val("temperature")),
            "wind_mph": kmh_to_mph(val("windSpeed")),
            "wind_gust_mph": kmh_to_mph(val("windGust")),
            "wind_dir_deg": val("windDirection"),
            "precip_last_hour_mm": val("precipitationLastHour"),
            "description": p.get("textDescription"),
        })
    return rows


# --------------------------------------------------------------------------- output

def write_snapshot(rows, kind, season, snap_tag, dry_run):
    df = pd.DataFrame(rows)
    if df.empty:
        log.warning(f"  no {kind} rows this run"); return None
    if dry_run:
        log.info(f"  DRY RUN — {len(df):,} {kind} rows not written"); return None
    out_dir = OUT_ROOT / kind / f"season={season}"
    out_dir.mkdir(parents=True, exist_ok=True)
    f = out_dir / f"snap_{snap_tag}.parquet"
    try:
        df.to_parquet(f, index=False)
    except (ImportError, ValueError):
        f = out_dir / f"snap_{snap_tag}.csv.gz"
        df.to_csv(f, index=False, compression="gzip")
    log.info(f"  wrote {len(df):,} {kind} rows -> {f}")
    return f


# --------------------------------------------------------------------------- selftest

_SAMPLE_FORECAST = {
    "properties": {
        "generatedAt": "2026-09-11T15:03:11+00:00", "updateTime": "2026-09-11T14:41:00+00:00",
        "periods": [
            {"startTime": "2026-09-14T13:00:00-04:00", "endTime": "2026-09-14T14:00:00-04:00",
             "isDaytime": True, "temperature": 71, "temperatureUnit": "F",
             "windSpeed": "5 to 10 mph", "windDirection": "NW",
             "probabilityOfPrecipitation": {"unitCode": "wmoUnit:percent", "value": 20},
             "shortForecast": "Partly Sunny"},
            {"startTime": "2026-09-14T14:00:00-04:00", "endTime": "2026-09-14T15:00:00-04:00",
             "isDaytime": True, "temperature": 73, "temperatureUnit": "F",
             "windSpeed": "10 mph", "windDirection": "NW",
             "probabilityOfPrecipitation": {"unitCode": "wmoUnit:percent", "value": None},
             "shortForecast": "Sunny"},
        ],
    }
}
_SAMPLE_OBS = {
    "features": [{"properties": {
        "timestamp": "2026-09-11T14:53:00+00:00",
        "temperature": {"unitCode": "wmoUnit:degC", "value": 21.7},
        "windSpeed": {"unitCode": "wmoUnit:km_h-1", "value": 16.7},
        "windGust": {"unitCode": "wmoUnit:km_h-1", "value": None},
        "windDirection": {"unitCode": "wmoUnit:degree_(angle)", "value": 310},
        "precipitationLastHour": {"unitCode": "wmoUnit:mm", "value": None},
        "textDescription": "Mostly Cloudy",
    }}]
}


def selftest():
    assert parse_wind_mph("5 to 10 mph") == (5, 10, 7.5)
    assert parse_wind_mph("10 mph") == (10, 10, 10.0)
    assert parse_wind_mph("0 mph") == (0, 0, 0.0)
    assert parse_wind_mph(None) == (None, None, None)
    assert c_to_f(0) == 32.0 and c_to_f(21.7) == 71.1
    assert kmh_to_mph(16.7) == 10.4 and kmh_to_mph(None) is None
    st = {"team": "Buffalo Bills", "stadium": "Highmark Stadium", "roof": "outdoors", "lat": 42.7738, "lon": -78.7870}
    grid = {"grid_id": "BUF", "grid_x": 41, "grid_y": 31, "station_id": "KBUF", "station_name": "Buffalo"}
    fc = parse_forecast(_SAMPLE_FORECAST, "BUF", st, grid, "2026-09-11T15:05:00+00:00")
    assert len(fc) == 2 and fc[0]["wind_mph_mean"] == 7.5 and fc[0]["precip_prob_pct"] == 20
    assert fc[1]["precip_prob_pct"] is None and fc[1]["temp_f"] == 73
    ob = parse_observations(_SAMPLE_OBS, "BUF", st, grid, "2026-09-11T15:05:00+00:00")
    assert len(ob) == 1 and ob[0]["temp_f"] == 71.1 and ob[0]["wind_mph"] == 10.4 and ob[0]["wind_gust_mph"] is None
    stadiums = load_stadiums()
    assert 20 <= len(stadiums) <= 30, f"unexpected stadium count {len(stadiums)}"
    assert "NYJ" not in stadiums or "NYG" not in stadiums, "NYG/NYJ should dedupe to one location"
    assert not any(k in stadiums for k in LEGACY_KEYS)
    assert all(v["roof"] in ("outdoors", "retractable") for v in stadiums.values())
    assert nfl_season(datetime(2026, 9, 11, tzinfo=timezone.utc)) == 2026
    assert nfl_season(datetime(2027, 1, 20, tzinfo=timezone.utc)) == 2026
    df = pd.DataFrame(fc); assert list(df.columns)[0] == "fetched_at_utc"
    log.info(f"SELFTEST OK — parsing, unit conversion, {len(stadiums)} venues: {', '.join(sorted(stadiums))}")


# --------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stadiums", nargs="*", help="stadium keys to capture (default: all outdoor + retractable)")
    ap.add_argument("--dry-run", action="store_true", help="pull and report, write nothing")
    ap.add_argument("--selftest", action="store_true", help="parse canned samples, no network")
    ap.add_argument("--refresh-grid", action="store_true", help="re-resolve gridpoints and stations")
    args = ap.parse_args()

    if args.selftest:
        selftest(); return

    if not CONTACT:
        log.error("HARD STOP: NWS_CONTACT not set in .env (NWS requires an identifying User-Agent with a contact).")
        log.error("Add a line like  NWS_CONTACT=you@example.com  to .env and re-run."); sys.exit(1)

    now = datetime.now(timezone.utc)
    fetched_at = now.isoformat(timespec="seconds")
    snap_tag = now.strftime("%Y%m%dT%H%M%SZ")
    season = nfl_season(now)

    stadiums = load_stadiums(set(args.stadiums) if args.stadiums else None)
    log.info(f"capturing {len(stadiums)} venues, season={season}, UA={UA}")
    grid = load_grid_cache(stadiums, refresh=args.refresh_grid)

    fc_rows, ob_rows, ok, failed = [], [], 0, []
    obs_start = (now - timedelta(hours=OBS_LOOKBACK_HOURS)).isoformat(timespec="seconds")
    for key, st in stadiums.items():
        g = grid.get(key) or {}
        if not g.get("forecast_hourly_url"):
            failed.append(key); continue
        try:
            fc = _get(g["forecast_hourly_url"], params={"units": "us"})
            rows = parse_forecast(fc, key, st, g, fetched_at)
            fc_rows.extend(rows)
            n_obs = 0
            if g.get("station_id"):
                ob = _get(f"{BASE}/stations/{g['station_id']}/observations",
                          params={"start": obs_start, "end": fetched_at})
                orows = parse_observations(ob, key, st, g, fetched_at)
                ob_rows.extend(orows); n_obs = len(orows)
            ok += 1
            log.info(f"  {key}: {len(rows)} forecast hours (issued {fc['properties'].get('updateTime')}), {n_obs} obs")
            time.sleep(0.5)
        except Exception as e:
            failed.append(key)
            log.error(f"  {key}: FAILED — {type(e).__name__}: {str(e)[:200]}")

    if ok == 0:
        log.error("HARD STOP: nothing captured. Nothing written. Safe to re-run."); sys.exit(1)
    if failed:
        log.warning(f"  venues skipped this run ({len(failed)}): {', '.join(failed)}")

    write_snapshot(fc_rows, "forecasts", season, snap_tag, args.dry_run)
    write_snapshot(ob_rows, "observations", season, snap_tag, args.dry_run)
    log.info(f"done: {ok}/{len(stadiums)} venues, {len(fc_rows):,} forecast rows, {len(ob_rows):,} observation rows")
    log.info("APPEND-ONLY: this snapshot is part of the tape. Never overwrite it.")


if __name__ == "__main__":
    main()
