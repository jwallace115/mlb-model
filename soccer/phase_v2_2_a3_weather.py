"""
Phase V2.2-A3: Historical weather backfill using Open-Meteo archive API.

Pulls temperature, wind, precipitation at kickoff time for each game
using stadium coordinates per home team.

Output: soccer/data/weather_historical.parquet
"""

import logging
import os
import time
import warnings

import numpy as np
import pandas as pd
import requests

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_DIR  = os.path.join(BASE_DIR, "data")

CANONICAL_PATH = os.path.join(DATA_DIR, "soccer_canonical.parquet")
CACHE_DIR      = os.path.join(DATA_DIR, "cache", "weather")
OUTPUT_PATH    = os.path.join(DATA_DIR, "weather_historical.parquet")

os.makedirs(CACHE_DIR, exist_ok=True)

SEP = "═" * 72

# ── Stadium coordinates ────────────────────────────────────────────────────────
# (lat, lon) for each home team's primary stadium
STADIUM_COORDS = {
    # EPL
    "Arsenal":          (51.5549, -0.1083),
    "Aston Villa":      (52.5090, -1.8847),
    "Bournemouth":      (50.7352, -1.8382),
    "Brentford":        (51.4882, -0.2887),
    "Brighton":         (50.8618, -0.0830),
    "Burnley":          (53.7889, -2.2306),
    "Chelsea":          (51.4816, -0.1909),
    "Crystal Palace":   (51.3983, -0.0856),
    "Everton":          (53.4388, -2.9664),
    "Fulham":           (51.4749, -0.2217),
    "Ipswich":          (52.0543,  1.1447),
    "Leeds":            (53.7777, -1.5724),
    "Leicester":        (52.6204, -1.1423),
    "Liverpool":        (53.4308, -2.9608),
    "Luton":            (51.8842, -0.4299),
    "Man City":         (53.4831, -2.2004),
    "Man United":       (53.4631, -2.2913),
    "Newcastle":        (54.9757, -1.6215),
    "Norwich":          (52.6225,  1.3087),
    "Nott'm Forest":    (52.9399, -1.1328),
    "Sheffield United": (53.3703, -1.4706),
    "Southampton":      (50.9058, -1.3911),
    "Tottenham":        (51.6042, -0.0665),
    "Watford":          (51.6497, -0.4014),
    "West Brom":        (52.5090, -1.9642),
    "West Ham":         (51.5387,  0.0167),
    "Wolves":           (52.5902, -2.1304),
    # Bundesliga
    "Bayern Munich":    (48.2188, 11.6253),
    "Dortmund":         (51.4926,  7.4519),
    "RB Leipzig":       (51.3459, 12.3483),
    "Leverkusen":       (51.0380,  6.9836),
    "Frankfurt":        (50.0688,  8.6450),
    "Eintracht Frankfurt": (50.0688, 8.6450),
    "M'gladbach":       (51.1748,  6.3851),
    "Hoffenheim":       (49.2381,  8.8892),
    "Wolfsburg":        (52.4299, 10.8037),
    "Freiburg":         (48.0225,  7.8980),
    "Augsburg":         (48.3233, 10.9031),
    "Union Berlin":     (52.4576, 13.5686),
    "Hertha":           (52.5147, 13.2395),
    "Stuttgart":        (48.7928,  9.2322),
    "Werder Bremen":    (53.0665,  8.8377),
    "Mainz":            (49.9840,  8.2241),
    "Cologne":          (50.9333,  6.8750),
    "Bochum":           (51.4899,  7.2179),
    "Schalke 04":       (51.5543,  7.0676),
    "Bielefeld":        (51.9999,  8.5329),
    "Greuther Furth":   (49.4940, 10.9737),
    "Heidenheim":       (48.6851, 10.1507),
    "Darmstadt":        (49.8673,  8.6534),
    "Holstein Kiel":    (54.3350, 10.1390),
    "St. Pauli":        (53.5543,  9.9674),
}

# Fallback coordinates: London for EPL, Dortmund for BUN
FALLBACK_COORDS = {
    "EPL": (51.5, -0.1),
    "BUN": (51.5, 7.5),
}


def get_coords(home_team: str, league: str) -> tuple[float, float]:
    """Look up stadium coordinates, with fallback."""
    for name, coords in STADIUM_COORDS.items():
        if name.lower() in home_team.lower() or home_team.lower() in name.lower():
            return coords
    # Try partial match
    for name, coords in STADIUM_COORDS.items():
        if any(w in home_team.lower() for w in name.lower().split()):
            return coords
    return FALLBACK_COORDS.get(league, (51.5, -0.1))


def fetch_weather_season(lat: float, lon: float,
                          start_date: str, end_date: str) -> dict:
    """
    Fetch full season of hourly weather from Open-Meteo archive API.
    One call per (stadium, season) — returns a year of hourly data.
    """
    cache_key  = f"{lat:.4f}_{lon:.4f}_{start_date}_{end_date}"
    cache_path = os.path.join(CACHE_DIR, f"weather_{cache_key}.json")

    if os.path.exists(cache_path):
        import json
        with open(cache_path) as f:
            return json.load(f)

    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude":   lat,
        "longitude":  lon,
        "start_date": start_date,
        "end_date":   end_date,
        "hourly":     "temperature_2m,windspeed_10m,precipitation,snowfall",
        "timezone":   "UTC",
    }

    for attempt in range(3):
        try:
            r = requests.get(url, params=params, timeout=60)
            if r.status_code == 200:
                data = r.json()
                import json
                with open(cache_path, "w") as f:
                    json.dump(data, f)
                return data
            elif r.status_code == 429:
                time.sleep(5 * (attempt + 1))
            else:
                logger.warning(f"HTTP {r.status_code} for {lat},{lon} {start_date}")
                break
        except Exception as e:
            if attempt < 2:
                time.sleep(2)
    return {}


def extract_hourly(data: dict, hour: int) -> dict:
    """Extract weather at specific hour from Open-Meteo response."""
    empty = {
        "temperature_c": np.nan,
        "wind_kph":       np.nan,
        "precipitation_mm": np.nan,
        "snowfall_cm":    np.nan,
        "weathercode":    np.nan,
    }
    if not data or "hourly" not in data:
        return empty

    hourly = data["hourly"]
    times  = hourly.get("time", [])

    # Find the closest hour index
    target = None
    for i, t in enumerate(times):
        h = int(t.split("T")[1].split(":")[0])
        if h == hour:
            target = i
            break

    if target is None:
        # Use closest available hour
        target = min(range(len(times)),
                     key=lambda i: abs(int(times[i].split("T")[1].split(":")[0]) - hour),
                     default=0) if times else 0

    def get_val(key):
        vals = hourly.get(key, [])
        return vals[target] if target < len(vals) else np.nan

    return {
        "temperature_c":    get_val("temperature_2m"),
        "wind_kph":         get_val("windspeed_10m"),
        "precipitation_mm": get_val("precipitation"),
        "snowfall_cm":      get_val("snowfall"),
        "weathercode":      get_val("weathercode"),
    }


def main():
    """
    Batch approach: one Open-Meteo call per (stadium, season-year).
    ~50 stadiums × 6 seasons = ~300 API calls instead of 4,116.
    Lookups from the returned time-series use an in-memory index.
    """
    print(f"\n{SEP}")
    print("  PHASE V2.2-A3: WEATHER BACKFILL (Open-Meteo Archive, batch)")
    print(SEP)

    import json, glob, datetime

    canon = pd.read_parquet(CANONICAL_PATH)
    canon["game_date"] = pd.to_datetime(canon["game_date"])

    # Get kickoff hours from fixture JSONs
    fixture_times = {}
    for fpath in glob.glob(os.path.join(DATA_DIR, "cache", "api_football", "fixtures_league*.json")):
        with open(fpath) as f:
            d = json.load(f)
        for g in d.get("response", []):
            fid    = g.get("fixture", {}).get("id")
            dt_str = g.get("fixture", {}).get("date")
            if fid and dt_str:
                fixture_times[fid] = dt_str

    crosswalk = pd.read_parquet(os.path.join(DATA_DIR, "api_football_crosswalk.parquet"))
    cw_dict   = dict(zip(crosswalk["game_id"], crosswalk["fixture_id"]))

    # ── Build (home_team, season_year) → date range ────────────────────────────
    season_date_ranges = {
        "2019-20": ("2019-07-01", "2020-08-15"),
        "2020-21": ("2020-08-01", "2021-06-30"),
        "2021-22": ("2021-07-01", "2022-06-30"),
        "2022-23": ("2022-07-01", "2023-06-30"),
        "2023-24": ("2023-07-01", "2024-06-30"),
        "2024-25": ("2024-07-01", "2025-06-30"),
    }

    # Unique (home_team, league, season_year) combos
    unique_combos = (
        canon.groupby(["home_team", "league_id", "season_year"])
        .size().reset_index()
        [["home_team", "league_id", "season_year"]]
    )
    logger.info(f"Unique (stadium, season) combos: {len(unique_combos)}")

    # ── Fetch weather time-series per (stadium, season) ────────────────────────
    # Cache: weather_data[(lat, lon, season_year)] = hourly DataFrame
    weather_cache = {}
    n_fetched = 0

    for _, row in unique_combos.iterrows():
        home   = row["home_team"]
        league = row["league_id"]
        season = row["season_year"]
        lat, lon = get_coords(home, league)
        key = (round(lat, 4), round(lon, 4), season)

        if key in weather_cache:
            continue

        start_date, end_date = season_date_ranges.get(season, ("2019-07-01", "2025-06-30"))
        data = fetch_weather_season(lat, lon, start_date, end_date)

        if data and "hourly" in data:
            hourly = data["hourly"]
            times  = hourly.get("time", [])
            temps  = hourly.get("temperature_2m", [None] * len(times))
            winds  = hourly.get("windspeed_10m",  [None] * len(times))
            precips = hourly.get("precipitation", [None] * len(times))
            snows   = hourly.get("snowfall",       [None] * len(times))

            wx_df = pd.DataFrame({
                "dt":     pd.to_datetime(times, utc=True),
                "temp_c": [float(v) if v is not None else np.nan for v in temps],
                "wind":   [float(v) if v is not None else np.nan for v in winds],
                "precip": [float(v) if v is not None else np.nan for v in precips],
                "snow":   [float(v) if v is not None else np.nan for v in snows],
            })
            wx_df["date"]  = wx_df["dt"].dt.date
            wx_df["hour"]  = wx_df["dt"].dt.hour
            weather_cache[key] = wx_df
        else:
            weather_cache[key] = pd.DataFrame()

        n_fetched += 1
        if n_fetched % 10 == 0:
            logger.info(f"  Fetched {n_fetched}/{len(unique_combos)} stadium-seasons")
        time.sleep(0.3)  # polite throttle

    logger.info(f"Season-level weather data fetched for {len(weather_cache)} combos")

    # ── Lookup weather per game ────────────────────────────────────────────────
    rows = []

    for _, game in canon.iterrows():
        gid    = game["game_id"]
        league = game["league_id"]
        home   = game["home_team"]
        gdate  = game["game_date"]
        season = game["season_year"]

        lat, lon = get_coords(home, league)
        key = (round(lat, 4), round(lon, 4), season)

        # Get kickoff hour (UTC)
        fid = cw_dict.get(gid)
        hour_utc = 15
        if fid and fid in fixture_times:
            try:
                dt = datetime.datetime.fromisoformat(fixture_times[fid])
                if dt.tzinfo:
                    dt_utc = dt.astimezone(datetime.timezone.utc)
                    hour_utc = dt_utc.hour
                else:
                    hour_utc = dt.hour
            except Exception:
                pass

        temp_c = wind_kph = precip = snow_cm = np.nan

        wx_df = weather_cache.get(key, pd.DataFrame())
        if not wx_df.empty:
            game_date = gdate.date()
            # Find row closest to kickoff hour
            sub = wx_df[wx_df["date"] == game_date]
            if not sub.empty:
                idx  = (sub["hour"] - hour_utc).abs().idxmin()
                temp_c  = sub.loc[idx, "temp_c"]
                wind_kph = sub.loc[idx, "wind"]
                precip  = sub.loc[idx, "precip"]
                snow_cm = sub.loc[idx, "snow"]

        is_heavy_wind = float(wind_kph > 30) if not np.isnan(wind_kph) else 0.0
        is_rain       = float(precip > 1.0)  if not np.isnan(precip)   else 0.0
        is_snow       = float(snow_cm > 0.5) if not np.isnan(snow_cm)  else 0.0

        rows.append({
            "game_id":          gid,
            "temperature_c":    temp_c,
            "wind_kph":         wind_kph,
            "precipitation_mm": precip,
            "is_rain":          is_rain,
            "is_snow":          is_snow,
            "is_heavy_wind":    is_heavy_wind,
        })

    out = pd.DataFrame(rows)
    out.to_parquet(OUTPUT_PATH, index=False)
    logger.info(f"Saved: {OUTPUT_PATH}  ({len(out):,} rows)")

    print(f"\n  AUDIT")
    null_pct = out["temperature_c"].isna().mean() * 100
    print(f"  Total rows:        {len(out):,}")
    print(f"  Null temperature:  {null_pct:.1f}%")
    print(f"  Mean temp (C):     {out['temperature_c'].mean():.1f}")
    print(f"  Mean wind (kph):   {out['wind_kph'].mean():.1f}")
    print(f"  Heavy wind games:  {out['is_heavy_wind'].sum():.0f} ({out['is_heavy_wind'].mean():.1%})")
    print(f"  Rain games:        {out['is_rain'].sum():.0f} ({out['is_rain'].mean():.1%})")
    print(f"\n  Saved → {OUTPUT_PATH}\n")


if __name__ == "__main__":
    main()
